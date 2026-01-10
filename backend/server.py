from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import requests
import googlemaps
from io import StringIO
import csv
from route_optimizer import RouteOptimizer
from campminder_integration import CampMinderAPI
from sheets_generator import SheetsDataGenerator
from route_printer import RoutePrinter
from contextlib import asynccontextmanager
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize services
gmaps = googlemaps.Client(key=os.environ['GOOGLE_MAPS_API_KEY'])
route_optimizer = RouteOptimizer(num_buses=34)
sheets_generator = SheetsDataGenerator()
route_printer = RoutePrinter(gmaps)
campminder_api = CampMinderAPI(
    api_key=os.environ.get('CAMPMINDER_API_KEY', ''),
    api_url=os.environ.get('CAMPMINDER_API_URL', 'https://webapi.campminder.com')
)

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Auto-sync configuration
AUTO_SYNC_ENABLED = os.environ.get('AUTO_SYNC_ENABLED', 'true').lower() == 'true'
SYNC_INTERVAL_MINUTES = int(os.environ.get('SYNC_INTERVAL_MINUTES', '15'))
sync_task = None
last_sync_time = None

BUS_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff",
    "#9a6324", "#000000", "#800000", "#aaffc3", "#808000", "#ffd8b1",
    "#000075", "#808080", "#FFB6C1", "#FF69B4", "#FF1493", "#FFD700",
    "#FFA500", "#FF4500", "#DC143C", "#8B0000", "#006400", "#228B22",
    "#20B2AA", "#00CED1", "#191970"
]

class GeoLocation(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None

class CamperPin(BaseModel):
    first_name: str
    last_name: str
    location: GeoLocation
    bus_number: str
    bus_color: str
    session: str
    pickup_type: str
    town: Optional[str] = None
    zip_code: Optional[str] = None

def get_bus_color(bus_number: str) -> str:
    try:
        bus_num = int(''.join(filter(str.isdigit, bus_number)))
        return BUS_COLORS[(bus_num - 1) % len(BUS_COLORS)]
    except:
        return BUS_COLORS[0]

def geocode_address(address: str, town: str = "", zip_code: str = "") -> Optional[GeoLocation]:
    try:
        full_address = f"{address}, {town}, {zip_code}" if town else address
        if not full_address.strip():
            return None
        
        result = gmaps.geocode(full_address)
        if result and len(result) > 0:
            location = result[0]['geometry']['location']
            return GeoLocation(
                latitude=location['lat'],
                longitude=location['lng'],
                address=result[0]['formatted_address']
            )
        return None
    except Exception as e:
        logging.error(f"Geocoding error for {full_address}: {str(e)}")
        return None

@api_router.get("/")
async def root():
    return {"message": "Bus Routing API"}

@api_router.get("/campers", response_model=List[CamperPin])
async def get_campers():
    try:
        # Only return campers with valid bus assignments (exclude NONE)
        existing_campers = await db.campers.find({
            "bus_number": {"$exists": True, "$ne": "NONE", "$ne": ""}
        }, {"_id": 0}).to_list(None)
        
        return existing_campers
    except Exception as e:
        logging.error(f"Error fetching campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/sync-campers")
async def sync_campers(csv_data: Dict[str, Any]):
    try:
        pins = []
        csv_content = csv_data.get('csv_content', '')
        
        if not csv_content:
            raise HTTPException(status_code=400, detail="No CSV content provided")
        
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '')
            
            if 'AM Bus' not in am_method:
                continue
            
            am_bus = row.get('2026Transportation M AM Bus', '')
            pm_bus = row.get('2026Transportation M PM Bus', '')
            
            # Skip if no valid bus assignment
            if not am_bus or 'NONE' in am_bus.upper():
                continue
            
            first_name = row.get('First Name', '')
            last_name = row.get('Last Name', '')
            session = row.get('Enrolled Child Sessions', '')
            
            am_address = row.get('Trans-PickUpAddress', '')
            am_town = row.get('Trans-PickUpTown', '')
            am_zip = row.get('Trans-PickUpZip', '')
            
            pm_address = row.get('Trans-DropOffAddress', '')
            pm_town = row.get('Trans-DropOffTown', '')
            pm_zip = row.get('Trans-DropOffZip', '')
            
            if am_bus and am_address.strip() and 'NONE' not in am_bus.upper():
                location = geocode_address(am_address, am_town, am_zip)
                if location:
                    pins.append(CamperPin(
                        first_name=first_name,
                        last_name=last_name,
                        location=location,
                        bus_number=am_bus,
                        bus_color=get_bus_color(am_bus),
                        session=session,
                        pickup_type="AM Pickup",
                        town=am_town,
                        zip_code=am_zip
                    ))
            
            if pm_bus and pm_address.strip() and pm_address != am_address and 'NONE' not in pm_bus.upper():
                location = geocode_address(pm_address, pm_town, pm_zip)
                if location:
                    pins.append(CamperPin(
                        first_name=first_name,
                        last_name=last_name,
                        location=location,
                        bus_number=pm_bus,
                        bus_color=get_bus_color(pm_bus),
                        session=session,
                        pickup_type="PM Drop-off",
                        town=pm_town,
                        zip_code=pm_zip
                    ))
        
        await db.campers.delete_many({})
        
        if pins:
            pins_dict = [pin.model_dump() for pin in pins]
            await db.campers.insert_many(pins_dict)
        
        return {"status": "success", "count": len(pins)}
    except Exception as e:
        logging.error(f"Error syncing campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/refresh-colors")
async def refresh_colors():
    try:
        campers = await db.campers.find({}).to_list(None)
        
        for camper in campers:
            new_color = get_bus_color(camper['bus_number'])
            await db.campers.update_one(
                {"_id": camper["_id"]},
                {"$set": {"bus_color": new_color}}
            )
        
        return {"status": "success", "updated": len(campers)}
    except Exception as e:
        logging.error(f"Error refreshing colors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/optimize-routes")
async def optimize_routes():
    """Automatically optimize bus routes for all campers"""
    try:
        # Get all campers without bus assignments
        campers = await db.campers.find({}).to_list(None)
        
        if not campers:
            return {"status": "success", "message": "No campers to optimize"}
        
        # Run route optimization
        optimized_routes = route_optimizer.optimize_routes(campers)
        
        # Rebalance for efficiency
        balanced_routes = route_optimizer.rebalance_routes(optimized_routes)
        
        # Update database with assignments
        updates = []
        for bus_num, route in balanced_routes.items():
            for camper_data in route:
                camper_id = camper_data['camper_id']
                bus_number_str = f"Bus #{bus_num:02d}"
                
                await db.campers.update_one(
                    {"_id": camper_id},
                    {"$set": {
                        "bus_number": bus_number_str,
                        "bus_color": get_bus_color(bus_number_str)
                    }}
                )
                
                updates.append({
                    "camper_id": camper_id,
                    "bus_number": bus_num
                })
        
        return {
            "status": "success",
            "optimized_buses": len(balanced_routes),
            "assigned_campers": len(updates),
            "routes": {f"Bus #{k:02d}": len(v) for k, v in balanced_routes.items()}
        }
    except Exception as e:
        logging.error(f"Error optimizing routes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auto-assign-new-camper")
async def auto_assign_new_camper(camper_id: str):
    """Automatically assign optimal bus to a new camper"""
    try:
        # Get the new camper
        new_camper = await db.campers.find_one({"_id": camper_id})
        if not new_camper:
            raise HTTPException(status_code=404, detail="Camper not found")
        
        # Get existing bus routes
        all_campers = await db.campers.find({"bus_number": {"$exists": True}}).to_list(None)
        existing_routes = {}
        
        for camper in all_campers:
            bus_num_str = camper.get('bus_number', '')
            if bus_num_str:
                # Extract bus number
                bus_num = int(''.join(filter(str.isdigit, bus_num_str)))
                if bus_num not in existing_routes:
                    existing_routes[bus_num] = []
                
                if camper.get('location'):
                    existing_routes[bus_num].append({
                        'lat': camper['location']['latitude'],
                        'lng': camper['location']['longitude']
                    })
        
        # Find optimal bus
        camper_address = {
            'lat': new_camper['location']['latitude'],
            'lng': new_camper['location']['longitude']
        }
        
        optimal_bus = route_optimizer.find_optimal_bus(camper_address, existing_routes)
        bus_number_str = f"Bus #{optimal_bus:02d}"
        
        # Update in database
        await db.campers.update_one(
            {"_id": camper_id},
            {"$set": {
                "bus_number": bus_number_str,
                "bus_color": get_bus_color(bus_number_str)
            }}
        )
        
        # Update in CampMinder
        success = await campminder_api.update_camper_bus_assignment(camper_id, optimal_bus)
        
        return {
            "status": "success",
            "camper_id": camper_id,
            "assigned_bus": bus_number_str,
            "synced_to_campminder": success
        }
    except Exception as e:
        logging.error(f"Error auto-assigning camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/sync-assignments-to-campminder")
async def sync_assignments_to_campminder():
    """Sync all bus assignments back to CampMinder"""
    try:
        # Get all campers with bus assignments
        campers = await db.campers.find({"bus_number": {"$exists": True}}).to_list(None)
        
        assignments = []
        for camper in campers:
            bus_num_str = camper.get('bus_number', '')
            if bus_num_str:
                bus_num = int(''.join(filter(str.isdigit, bus_num_str)))
                assignments.append({
                    "camper_id": camper['_id'],
                    "bus_number": bus_num
                })
        
        # Bulk update in CampMinder
        results = await campminder_api.bulk_update_bus_assignments(assignments)
        
        successful = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)
        
        return {
            "status": "success",
            "total": len(assignments),
            "successful": successful,
            "failed": failed
        }
    except Exception as e:
        logging.error(f"Error syncing to CampMinder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/auto-sync-status")
async def get_auto_sync_status():
    """Get current auto-sync status"""
    sync_status = await db.sync_status.find_one({"_id": "auto_sync"})
    
    return {
        "enabled": AUTO_SYNC_ENABLED,
        "interval_minutes": SYNC_INTERVAL_MINUTES,
        "last_sync": last_sync_time.isoformat() if last_sync_time else None,
        "sync_info": sync_status if sync_status else {}
    }

@api_router.post("/trigger-sync")
async def trigger_manual_sync():
    """Manually trigger a sync with CampMinder"""
    try:
        await auto_sync_campminder()
        return {"status": "success", "message": "Sync completed"}
    except Exception as e:
        logging.error(f"Error in manual sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sheets/seat-availability")
async def get_seat_availability_for_sheets():
    """Get formatted seat availability data for Google Sheets"""
    try:
        campers = await db.campers.find({}).to_list(None)
        sheet_data = sheets_generator.generate_seat_availability_data(campers)
        
        return {
            "status": "success",
            "data": sheet_data,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"Error generating sheets data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sheets/compact-availability")
async def get_compact_availability():
    """Get compact seat availability summary for Google Sheets"""
    try:
        campers = await db.campers.find({}).to_list(None)
        compact_data = sheets_generator.generate_compact_availability(campers)
        
        return {
            "status": "success",
            "data": compact_data,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"Error generating compact data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    global sync_task
    if sync_task:
        sync_task.cancel()
    client.close()

# Auto-sync functions
async def auto_sync_campminder():
    """Background task to automatically sync with CampMinder"""
    global last_sync_time
    
    logger.info("Starting auto-sync with CampMinder...")
    
    try:
        # Fetch new campers from CampMinder
        new_campers_data = await campminder_api.get_new_campers(since=last_sync_time)
        
        if not new_campers_data:
            logger.info("No new campers found")
            last_sync_time = datetime.now(timezone.utc)
            return
        
        logger.info(f"Found {len(new_campers_data)} new/updated campers")
        
        new_campers_count = 0
        
        for camper_data in new_campers_data:
            # Check if camper requires bus transportation
            trans_type = camper_data.get('Trans-AMDropOffMethod', '')
            if 'AM Bus' not in trans_type:
                continue
            
            # Get AM pickup information
            am_address = camper_data.get('Trans-PickUpAddress', '')
            am_town = camper_data.get('Trans-PickUpTown', '')
            am_zip = camper_data.get('Trans-PickUpZip', '')
            
            # Get PM drop-off information
            pm_address = camper_data.get('Trans-DropOffAddress', '')
            pm_town = camper_data.get('Trans-DropOffTown', '')
            pm_zip = camper_data.get('Trans-DropOffZip', '')
            
            first_name = camper_data.get('First Name', '')
            last_name = camper_data.get('Last Name', '')
            session = camper_data.get('Enrolled Child Sessions', '')
            
            # Get existing routes for optimization
            all_campers = await db.campers.find({"bus_number": {"$exists": True}}).to_list(None)
            existing_routes = {}
            
            for existing_camper in all_campers:
                bus_num_str = existing_camper.get('bus_number', '')
                if bus_num_str:
                    bus_num = int(''.join(filter(str.isdigit, bus_num_str)))
                    if bus_num not in existing_routes:
                        existing_routes[bus_num] = []
                    
                    if existing_camper.get('location'):
                        existing_routes[bus_num].append({
                            'lat': existing_camper['location']['latitude'],
                            'lng': existing_camper['location']['longitude']
                        })
            
            # Process AM pickup
            if am_address.strip():
                location = geocode_address(am_address, am_town, am_zip)
                if location:
                    camper_id = f"{last_name}_{first_name}_{am_zip}_AM".replace(' ', '_')
                    existing = await db.campers.find_one({"_id": camper_id})
                    
                    if not existing:
                        camper_address = {'lat': location.latitude, 'lng': location.longitude}
                        optimal_bus = route_optimizer.find_optimal_bus(camper_address, existing_routes)
                        bus_number_str = f"Bus #{optimal_bus:02d}"
                        
                        camper = {
                            "_id": camper_id,
                            "first_name": first_name,
                            "last_name": last_name,
                            "session": session,
                            "location": {
                                "latitude": location.latitude,
                                "longitude": location.longitude,
                                "address": location.address
                            },
                            "town": am_town,
                            "zip_code": am_zip,
                            "pickup_type": "AM Pickup",
                            "bus_number": bus_number_str,
                            "bus_color": get_bus_color(bus_number_str),
                            "created_at": datetime.now(timezone.utc)
                        }
                        
                        await db.campers.insert_one(camper)
                        await campminder_api.update_camper_bus_assignment(camper_id, optimal_bus)
                        logger.info(f"✓ Auto-assigned {first_name} {last_name} AM pickup to {bus_number_str}")
                        new_campers_count += 1
            
            # Process PM drop-off (if different from AM address)
            if pm_address.strip() and pm_address != am_address:
                location = geocode_address(pm_address, pm_town, pm_zip)
                if location:
                    camper_id = f"{last_name}_{first_name}_{pm_zip}_PM".replace(' ', '_')
                    existing = await db.campers.find_one({"_id": camper_id})
                    
                    if not existing:
                        camper_address = {'lat': location.latitude, 'lng': location.longitude}
                        optimal_bus = route_optimizer.find_optimal_bus(camper_address, existing_routes)
                        bus_number_str = f"Bus #{optimal_bus:02d}"
                        
                        camper = {
                            "_id": camper_id,
                            "first_name": first_name,
                            "last_name": last_name,
                            "session": session,
                            "location": {
                                "latitude": location.latitude,
                                "longitude": location.longitude,
                                "address": location.address
                            },
                            "town": pm_town,
                            "zip_code": pm_zip,
                            "pickup_type": "PM Drop-off",
                            "bus_number": bus_number_str,
                            "bus_color": get_bus_color(bus_number_str),
                            "created_at": datetime.now(timezone.utc)
                        }
                        
                        await db.campers.insert_one(camper)
                        await campminder_api.update_camper_bus_assignment(camper_id, optimal_bus)
                        logger.info(f"✓ Auto-assigned {first_name} {last_name} PM drop-off to {bus_number_str}")
                        new_campers_count += 1
        
        last_sync_time = datetime.now(timezone.utc)
        logger.info(f"Auto-sync complete: {new_campers_count} new campers processed")
        
        # Store sync status in database
        await db.sync_status.update_one(
            {"_id": "auto_sync"},
            {"$set": {
                "last_sync": last_sync_time,
                "new_campers": new_campers_count,
                "status": "success"
            }},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Error in auto-sync: {str(e)}")
        await db.sync_status.update_one(
            {"_id": "auto_sync"},
            {"$set": {
                "last_sync": datetime.now(timezone.utc),
                "status": "error",
                "error": str(e)
            }},
            upsert=True
        )

async def sync_loop():
    """Continuous sync loop"""
    global last_sync_time
    
    while True:
        try:
            await auto_sync_campminder()
        except Exception as e:
            logger.error(f"Error in sync loop: {str(e)}")
        
        # Wait for next sync interval
        await asyncio.sleep(SYNC_INTERVAL_MINUTES * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_task
    
    # Startup
    logger.info(f"Auto-sync enabled: {AUTO_SYNC_ENABLED}")
    if AUTO_SYNC_ENABLED:
        logger.info(f"Starting auto-sync task (interval: {SYNC_INTERVAL_MINUTES} minutes)")
        sync_task = asyncio.create_task(sync_loop())
    
    yield
    
    # Shutdown
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

# Update app with lifespan
app = FastAPI(lifespan=lifespan)

# Register router and middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)