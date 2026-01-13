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
import httpx
import googlemaps
from io import StringIO
import csv
from route_optimizer import RouteOptimizer
from campminder_integration import CampMinderAPI
from sheets_generator import SheetsDataGenerator
from cover_sheet_generator import CoverSheetGenerator
from route_printer import RoutePrinter
from sibling_offset import apply_sibling_offset
from bus_config import get_bus_info, get_all_buses, get_camp_address, get_bus_home_location
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
cover_sheet_generator = CoverSheetGenerator()
route_printer = RoutePrinter(gmaps)
campminder_api = CampMinderAPI(
    api_key=os.environ.get('CAMPMINDER_API_KEY', ''),
    subscription_key=os.environ.get('CAMPMINDER_SUBSCRIPTION_KEY', '')
)

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Auto-sync configuration
AUTO_SYNC_ENABLED = os.environ.get('AUTO_SYNC_ENABLED', 'true').lower() == 'true'
SYNC_INTERVAL_MINUTES = int(os.environ.get('SYNC_INTERVAL_MINUTES', '15'))
CAMPMINDER_SHEET_ID = os.environ.get('CAMPMINDER_SHEET_ID', '')
sync_task = None
last_sync_time = None

BUS_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff",
    "#9a6324", "#000000", "#800000", "#aaffc3", "#808000", "#ffd8b1",
    "#000075", "#9370DB", "#FFB6C1", "#FF69B4", "#FF1493", "#FFD700",
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
    am_bus_number: str
    pm_bus_number: str
    bus_color: str
    session: str
    pickup_type: str
    town: Optional[str] = None
    zip_code: Optional[str] = None

def get_bus_color(bus_number: str) -> str:
    try:
        bus_num = int(''.join(filter(str.isdigit, bus_number)))
        return BUS_COLORS[(bus_num - 1) % len(BUS_COLORS)]
    except (ValueError, IndexError):
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

@api_router.get("/campers")
async def get_campers():
    try:
        # Return campers with valid locations and at least one valid bus assignment
        existing_campers = await db.campers.find({
            "location.latitude": {"$ne": 0.0},
            "$or": [
                {"am_bus_number": {"$regex": "^Bus"}},
                {"pm_bus_number": {"$regex": "^Bus"}}
            ]
        }).to_list(None)
        
        # Convert _id to string and clean up data
        result = []
        for camper in existing_campers:
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            # Clean up NONE values - replace with empty string
            if am_bus == 'NONE' or not am_bus.startswith('Bus'):
                am_bus = ''
            if pm_bus == 'NONE' or not pm_bus.startswith('Bus'):
                pm_bus = ''
            
            # Skip campers with no valid bus at all
            if not am_bus and not pm_bus:
                continue
            
            camper_dict = {
                "_id": str(camper['_id']),
                "first_name": camper.get('first_name', ''),
                "last_name": camper.get('last_name', ''),
                "location": camper.get('location', {}),
                "am_bus_number": am_bus,
                "pm_bus_number": pm_bus,
                "bus_number": am_bus or pm_bus,  # For compatibility - use whichever is valid
                "bus_color": camper.get('bus_color', ''),
                "session": camper.get('session', ''),
                "pickup_type": camper.get('pickup_type', ''),
                "town": camper.get('town', ''),
                "zip_code": camper.get('zip_code', '')
            }
            result.append(camper_dict)
        
        return result
    except Exception as e:
        logging.error(f"Error fetching campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/campers/needs-address")
async def get_campers_needing_address():
    """Get campers who have bus assignments but no address"""
    try:
        campers = await db.campers.find({
            "location.latitude": 0.0,
            "$or": [
                {"am_bus_number": {"$exists": True, "$regex": "^Bus"}},
                {"pm_bus_number": {"$exists": True, "$regex": "^Bus"}}
            ]
        }).to_list(None)
        
        result = []
        for camper in campers:
            result.append({
                "_id": str(camper['_id']),
                "first_name": camper.get('first_name', ''),
                "last_name": camper.get('last_name', ''),
                "am_bus_number": camper.get('am_bus_number', ''),
                "pm_bus_number": camper.get('pm_bus_number', ''),
                "pickup_type": camper.get('pickup_type', '')
            })
        
        return result
    except Exception as e:
        logging.error(f"Error fetching campers needing address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class ManualCamperInput(BaseModel):
    first_name: str
    last_name: str
    address: str
    town: str
    zip_code: str
    am_bus_number: Optional[str] = "NONE"
    pm_bus_number: Optional[str] = None
    session: Optional[str] = ""

@api_router.post("/campers/add")
async def add_camper_manually(camper: ManualCamperInput):
    """Manually add a camper to the map"""
    try:
        # Geocode the address
        location = geocode_address(camper.address, camper.town, camper.zip_code)
        if not location:
            raise HTTPException(status_code=400, detail=f"Could not geocode address: {camper.address}, {camper.town}, {camper.zip_code}")
        
        # Generate camper ID
        camper_id = f"{camper.last_name}_{camper.first_name}_{camper.zip_code}".replace(' ', '_')
        
        # Check for existing campers at same location for offset
        existing_at_address = await db.campers.count_documents({
            "location.latitude": {"$gte": location.latitude - 0.001, "$lte": location.latitude + 0.001},
            "location.longitude": {"$gte": location.longitude - 0.001, "$lte": location.longitude + 0.001}
        })
        offset = existing_at_address * 0.00002
        
        # Determine bus values
        am_bus = camper.am_bus_number if camper.am_bus_number else "NONE"
        pm_bus = camper.pm_bus_number if camper.pm_bus_number else am_bus
        
        # Determine color and pickup type
        if am_bus == "NONE":
            bus_color = "#808080"
            pickup_type = "NEEDS BUS"
        else:
            bus_color = get_bus_color(am_bus)
            pickup_type = "AM & PM"
        
        camper_doc = {
            "_id": camper_id,
            "first_name": camper.first_name,
            "last_name": camper.last_name,
            "session": camper.session or "",
            "location": {
                "latitude": location.latitude + offset,
                "longitude": location.longitude + offset,
                "address": location.address
            },
            "town": camper.town,
            "zip_code": camper.zip_code,
            "pickup_type": pickup_type,
            "am_bus_number": am_bus,
            "pm_bus_number": pm_bus,
            "bus_color": bus_color,
            "created_at": datetime.now(timezone.utc),
            "manually_added": True
        }
        
        result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
        
        return {
            "success": True,
            "message": f"Added {camper.first_name} {camper.last_name}",
            "camper_id": camper_id,
            "location": {"latitude": location.latitude + offset, "longitude": location.longitude + offset},
            "was_update": result.modified_count > 0
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error adding camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/campers/{camper_id}")
async def delete_camper(camper_id: str):
    """Delete a camper from the database"""
    try:
        # URL decode the camper_id
        import urllib.parse
        decoded_id = urllib.parse.unquote(camper_id)
        
        result = await db.campers.delete_one({"_id": decoded_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Camper not found")
        
        # Also delete any PM-specific entry
        await db.campers.delete_many({"_id": {"$regex": f"^{decoded_id}_PM"}})
        
        return {"success": True, "message": "Camper deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@api_router.post("/sync-campers")
async def sync_campers(csv_data: Dict[str, Any]):
    try:
        pins = []
        csv_content = csv_data.get('csv_content', '')
        
        if not csv_content:
            raise HTTPException(status_code=400, detail="No CSV content provided")
        
        csv_file = StringIO(csv_content)
        # Remove BOM if present
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
            csv_file = StringIO(csv_content)
        
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '')
            
            if 'AM Bus' not in am_method:
                continue
            
            am_bus = row.get('2026Transportation M AM Bus', '').strip()
            pm_bus = row.get('2026Transportation M PM Bus', '').strip()
            
            # If no bus assigned, set to NONE (but still import the camper)
            if not am_bus or 'NONE' in am_bus.upper():
                am_bus = 'NONE'
            
            first_name = row.get('First Name', '')
            last_name = row.get('Last Name', '')
            session = row.get('Enrolled Child Sessions', '')
            
            am_address = row.get('Trans-PickUpAddress', '')
            am_town = row.get('Trans-PickUpTown', '')
            am_zip = row.get('Trans-PickUpZip', '')
            
            pm_address = row.get('Trans-DropOffAddress', '')
            pm_town = row.get('Trans-DropOffTown', '')
            pm_zip = row.get('Trans-DropOffZip', '')
            
            # Determine final PM values
            final_pm_bus = pm_bus.strip() if pm_bus and pm_bus.strip() else am_bus
            if final_pm_bus and any(x in final_pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM', 'NONE']):
                final_pm_bus = am_bus
            
            pm_final_address = pm_address if pm_address.strip() else am_address
            pm_final_town = pm_town if pm_town.strip() else am_town
            pm_final_zip = pm_zip if pm_zip.strip() else am_zip
            
            # Process ALL campers (including those with NONE bus)
            if am_address.strip():
                location = geocode_address(am_address, am_town, am_zip)
                if not location:
                    location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {am_address}")
                    logger.warning(f"Geocoding failed for {first_name} {last_name}: {am_address}")
                
                # Count existing in CURRENT batch (pins list) for offset
                existing_count = len([p for p in pins if 
                    abs(p.location.latitude - location.latitude) < 0.0001 and
                    abs(p.location.longitude - location.longitude) < 0.0001
                ])
                offset = existing_count * 0.00002  # Reduced to ~6 feet per sibling
                
                # Set bus color - gray for NONE, otherwise use bus color
                bus_color = "#808080" if am_bus == "NONE" else get_bus_color(am_bus)
                
                pins.append(CamperPin(
                    first_name=first_name,
                    last_name=last_name,
                    location=GeoLocation(
                        latitude=location.latitude + offset,
                        longitude=location.longitude + offset,
                        address=location.address
                    ),
                    am_bus_number=am_bus,
                    pm_bus_number=final_pm_bus,
                    bus_color=bus_color,
                    session=session,
                    pickup_type="AM & PM" if am_bus != "NONE" else "NEEDS BUS",
                    town=am_town,
                    zip_code=am_zip
                ))
            else:
                # No address - still add for tracking
                bus_color = "#808080" if am_bus == "NONE" else get_bus_color(am_bus)
                pins.append(CamperPin(
                    first_name=first_name,
                    last_name=last_name,
                    location=GeoLocation(latitude=0.0, longitude=0.0, address="ADDRESS NEEDED"),
                    am_bus_number=am_bus,
                    pm_bus_number=final_pm_bus,
                    bus_color=bus_color,
                    session=session,
                    pickup_type="NO ADDRESS",
                    town=am_town or "UNKNOWN",
                    zip_code=am_zip or "UNKNOWN"
                ))
            
            # Add separate PM pin only if has assigned bus and address is different
            if am_bus != "NONE" and pm_final_address != am_address and pm_final_address.strip():
                    location_pm = geocode_address(pm_final_address, pm_final_town, pm_final_zip)
                    if not location_pm:
                        # Geocoding failed - use placeholder
                        location_pm = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {pm_final_address}")
                        logger.warning(f"PM geocoding failed for {first_name} {last_name}: {pm_final_address}")
                    
                    # Count existing at PM location
                    existing_pm_count = len([p for p in pins if 
                        abs(p.location.latitude - location_pm.latitude) < 0.001 and
                        abs(p.location.longitude - location_pm.longitude) < 0.001
                    ])
                    pm_offset = existing_pm_count * 0.00008
                    
                    pins.append(CamperPin(
                        first_name=first_name,
                        last_name=last_name,
                        location=GeoLocation(
                            latitude=location_pm.latitude + pm_offset,
                            longitude=location_pm.longitude + pm_offset,
                            address=location_pm.address
                        ),
                        am_bus_number=am_bus,
                        pm_bus_number=final_pm_bus,
                        bus_color=get_bus_color(final_pm_bus),
                        session=session,
                        pickup_type="PM Drop-off Only",
                        town=pm_final_town,
                        zip_code=pm_final_zip
                    ))
        
        await db.campers.delete_many({})
        
        if pins:
            pins_dict = [pin.model_dump() for pin in pins]
            await db.campers.insert_many(pins_dict)
        
        # AUTOMATICALLY apply sibling offset after inserting
        await apply_sibling_offset(db)
        
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
    """Manually trigger a sync with CampMinder (from Google Sheet)"""
    try:
        await auto_sync_campminder()
        return {"status": "success", "message": "Sync from Google Sheet completed"}
    except Exception as e:
        logging.error(f"Error in manual sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/test-campminder-api")
async def test_campminder_api():
    """
    Test CampMinder API connectivity and endpoints
    
    Returns comprehensive diagnostic information about API access
    """
    try:
        # Use the built-in test method
        result = await campminder_api.test_api_connectivity()
        return result
    except Exception as e:
        logger.error(f"Error testing CampMinder API: {str(e)}")
        return {"status": "error", "message": str(e)}


@api_router.post("/sync-from-campminder-api")
async def sync_from_campminder_api():
    """
    Sync camper bus data directly from CampMinder API
    
    Uses:
    - Custom Field API for AM/PM bus assignments
    - Day Travel API for transportation assignments
    - Camper Data API for camper information
    """
    try:
        logger.info("Starting sync from CampMinder API")
        
        # First test if API is accessible
        token = await campminder_api.get_jwt_token()
        if not token:
            return {
                "status": "error",
                "message": "CampMinder API authentication failed. Please verify API credentials in .env file.",
                "campers_processed": 0,
                "recommendation": "Use 'Refresh from CSV Now' button to sync from Google Sheet instead."
            }
        
        # Get campers with bus data from CampMinder API
        campers_data = await campminder_api.get_all_campers_with_bus_data(season_id="2026")
        
        if not campers_data:
            return {
                "status": "warning",
                "message": "CampMinder API returned no camper data. The API endpoints may not be available for your subscription level.",
                "campers_processed": 0,
                "recommendation": "Contact CampMinder support to verify API access or use Google Sheet sync as fallback."
            }
        
        new_count = 0
        updated_count = 0
        skipped_count = 0
        
        for camper in campers_data:
            # Skip if no address
            if not camper.get('address'):
                skipped_count += 1
                continue
            
            # Skip if no valid bus assignment
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            if not am_bus and not pm_bus:
                skipped_count += 1
                continue
            
            # Geocode address
            location = geocode_address(
                camper['address'],
                camper.get('town', ''),
                camper.get('zip_code', '')
            )
            
            if not location or location.latitude == 0:
                skipped_count += 1
                continue
            
            # Generate camper ID
            camper_id = f"{camper['last_name']}_{camper['first_name']}_{camper.get('zip_code', 'NOZIP')}".replace(' ', '_')
            
            # Determine bus color - use AM bus if available, else PM bus
            primary_bus = am_bus if am_bus and am_bus.startswith('Bus') else pm_bus
            bus_color = get_bus_color(primary_bus) if primary_bus else "#808080"
            
            # Determine pickup type based on session
            if camper.get('has_am_session') and camper.get('has_pm_session'):
                pickup_type = "AM & PM"
            elif camper.get('has_am_session'):
                pickup_type = "AM Only"
            elif camper.get('has_pm_session'):
                pickup_type = "PM Only"
            else:
                pickup_type = "Unknown"
            
            camper_doc = {
                "_id": camper_id,
                "first_name": camper['first_name'],
                "last_name": camper['last_name'],
                "session": camper.get('session_type', ''),
                "location": {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "address": location.address
                },
                "town": camper.get('town', ''),
                "zip_code": camper.get('zip_code', ''),
                "pickup_type": pickup_type,
                "am_bus_number": am_bus,  # Empty string if no AM bus/session
                "pm_bus_number": pm_bus,  # Empty string if no PM bus/session
                "bus_color": bus_color,
                "synced_from": "campminder_api",
                "created_at": datetime.now(timezone.utc)
            }
            
            result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
            
            if result.upserted_id:
                new_count += 1
            elif result.modified_count > 0:
                updated_count += 1
        
        # Apply sibling offset
        await apply_sibling_offset(db)
        
        logger.info(f"CampMinder API sync complete: {new_count} new, {updated_count} updated, {skipped_count} skipped")
        
        return {
            "status": "success",
            "message": "Sync from CampMinder API completed",
            "new_campers": new_count,
            "updated_campers": updated_count,
            "skipped_campers": skipped_count,
            "total_processed": len(campers_data)
        }
        
    except Exception as e:
        logger.error(f"Error syncing from CampMinder API: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sheets/seat-availability")
async def get_seat_availability_for_sheets():
    """Get formatted seat availability data for Google Sheets - COVER SHEET FORMAT"""
    try:
        # Include ALL campers with bus assignments (even without valid locations)
        campers = await db.campers.find({
            "am_bus_number": {"$exists": True, "$nin": ["NONE", ""]}
        }).to_list(None)
        
        # Use compact Cover Sheet format
        sheet_data = cover_sheet_generator.generate_cover_sheet(campers)
        
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
        campers = await db.campers.find({
            "bus_number": {"$exists": True, "$nin": ["NONE", ""]}
        }).to_list(None)
        compact_data = sheets_generator.generate_compact_availability(campers)
        
        return {
            "status": "success",
            "data": compact_data,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"Error generating compact data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/buses")
async def get_buses():
    """Get all buses with their info including home locations"""
    try:
        buses = []
        for bus_number in get_all_buses():
            bus_info = get_bus_info(bus_number)
            # Get camper count for this bus
            am_count = await db.campers.count_documents({"am_bus_number": bus_number})
            pm_count = await db.campers.count_documents({"pm_bus_number": bus_number})
            bus_info['am_camper_count'] = am_count
            bus_info['pm_camper_count'] = pm_count
            buses.append(bus_info)
        
        return {
            "status": "success",
            "buses": buses,
            "camp_address": get_camp_address()
        }
    except Exception as e:
        logging.error(f"Error getting buses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/buses/{bus_number}")
async def get_bus_details(bus_number: str):
    """Get detailed info for a specific bus"""
    try:
        bus_info = get_bus_info(bus_number)
        
        # Get campers for this bus
        am_campers = await db.campers.find({"am_bus_number": bus_number}).to_list(None)
        pm_campers = await db.campers.find({"pm_bus_number": bus_number}).to_list(None)
        
        return {
            "status": "success",
            "bus": bus_info,
            "camp_address": get_camp_address(),
            "am_campers": [
                {"name": f"{c['first_name']} {c['last_name']}", "address": c.get('location', {}).get('address', '')}
                for c in am_campers
            ],
            "pm_campers": [
                {"name": f"{c['first_name']} {c['last_name']}", "address": c.get('location', {}).get('address', '')}
                for c in pm_campers
            ]
        }
    except Exception as e:
        logging.error(f"Error getting bus details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/audit/campers")
async def audit_all_campers():
    """
    Comprehensive audit of ALL campers to verify bus assignments are correct.
    Compares database values against Google Sheet source data.
    
    Distinguishes between:
    - TRUE ERRORS: Database has different bus than Sheet (Sheet has valid bus)
    - AUTO-ASSIGNMENTS: Database has bus, Sheet has NONE (system auto-assigned)
    """
    import httpx
    import csv
    from io import StringIO
    
    logger.info("=== STARTING COMPREHENSIVE CAMPER AUDIT ===")
    
    results = {
        "status": "success",
        "total_checked": 0,
        "true_errors": [],         # DB differs from valid sheet bus
        "auto_assignments": [],     # DB has bus, sheet has NONE
        "summary": {}
    }
    
    try:
        # Step 1: Load all campers from database
        db_campers = await db.campers.find({}).to_list(None)
        logger.info(f"Loaded {len(db_campers)} campers from database")
        
        # Step 2: Load Google Sheet data for comparison
        sheet_id = CAMPMINDER_SHEET_ID
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(csv_url)
            csv_content = response.text
        
        # Parse Google Sheet data
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        reader = csv.DictReader(StringIO(csv_content))
        sheet_data = {}
        
        for row in reader:
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            am_bus = row.get('2026Transportation M AM Bus', '').strip()
            pm_bus = row.get('2026Transportation M PM Bus', '').strip()
            
            if first_name and last_name:
                key = f"{last_name}_{first_name}".lower()
                sheet_data[key] = {
                    'name': f"{first_name} {last_name}",
                    'sheet_am_bus': am_bus,
                    'sheet_pm_bus': pm_bus
                }
        
        logger.info(f"Loaded {len(sheet_data)} campers from Google Sheet")
        
        # Step 3: Audit each camper
        seen_campers = set()
        
        for camper in db_campers:
            first_name = camper.get('first_name', '')
            last_name = camper.get('last_name', '')
            camper_id = camper.get('_id', '')
            db_am_bus = camper.get('am_bus_number', '')
            db_pm_bus = camper.get('pm_bus_number', '')
            
            # Skip PM-specific entries
            if camper_id.endswith('_PM'):
                continue
            
            # Skip if already checked
            full_name = f"{first_name} {last_name}"
            if full_name in seen_campers:
                continue
            seen_campers.add(full_name)
            
            results["total_checked"] += 1
            
            # Find in sheet data
            key = f"{last_name}_{first_name}".lower()
            sheet_camper = sheet_data.get(key)
            
            if not sheet_camper:
                continue
            
            sheet_am = sheet_camper['sheet_am_bus']
            sheet_pm = sheet_camper['sheet_pm_bus']
            
            # Determine if sheet value is valid bus
            def is_valid_sheet_bus(val):
                if not val:
                    return False
                val_upper = val.upper()
                if val_upper == 'NONE' or val_upper == '':
                    return False
                if any(x in val_upper for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM']):
                    return False
                return val.startswith('Bus')
            
            # Check AM
            if db_am_bus and db_am_bus != 'NONE' and db_am_bus.startswith('Bus'):
                if is_valid_sheet_bus(sheet_am):
                    # Both have valid buses - check if they match
                    db_norm = db_am_bus.replace(' ', '')
                    sheet_norm = sheet_am.replace(' ', '')
                    if db_norm != sheet_norm:
                        results["true_errors"].append({
                            "camper": full_name,
                            "type": "AM",
                            "database_value": db_am_bus,
                            "sheet_value": sheet_am,
                            "issue": f"TRUE ERROR: AM bus mismatch"
                        })
                else:
                    # DB has bus, sheet has NONE - auto-assignment
                    results["auto_assignments"].append({
                        "camper": full_name,
                        "type": "AM",
                        "auto_assigned_bus": db_am_bus,
                        "sheet_value": sheet_am or "NONE"
                    })
            
            # Check PM
            if db_pm_bus and db_pm_bus != 'NONE' and db_pm_bus.startswith('Bus'):
                if is_valid_sheet_bus(sheet_pm):
                    # Both have valid buses - check if they match
                    db_norm = db_pm_bus.replace(' ', '')
                    sheet_norm = sheet_pm.replace(' ', '')
                    if db_norm != sheet_norm:
                        results["true_errors"].append({
                            "camper": full_name,
                            "type": "PM",
                            "database_value": db_pm_bus,
                            "sheet_value": sheet_pm,
                            "issue": f"TRUE ERROR: PM bus mismatch"
                        })
                else:
                    # DB has bus, sheet has NONE - auto-assignment
                    results["auto_assignments"].append({
                        "camper": full_name,
                        "type": "PM",
                        "auto_assigned_bus": db_pm_bus,
                        "sheet_value": sheet_pm or "NONE"
                    })
        
        # Step 4: Generate summary
        results["summary"] = {
            "total_campers_checked": results["total_checked"],
            "true_errors_count": len(results["true_errors"]),
            "auto_assignments_count": len(results["auto_assignments"]),
            "validation_passed": len(results["true_errors"]) == 0,
            "message": "✓✓✓ ALL BUS LABELS MATCH GOOGLE SHEET" if len(results["true_errors"]) == 0 else f"❌ Found {len(results['true_errors'])} bus mismatches"
        }
        
        if len(results["true_errors"]) > 0:
            results["status"] = "errors_found"
            logger.error(f"AUDIT FOUND {len(results['true_errors'])} TRUE ERRORS")
        else:
            logger.info(f"AUDIT PASSED - {len(results['auto_assignments'])} auto-assignments detected (expected)")
        
        return results
        
    except Exception as e:
        logger.error(f"Error during audit: {str(e)}")
        results["status"] = "error"
        results["message"] = str(e)
        return results


@api_router.get("/audit/bus/{bus_number}")
async def audit_single_bus(bus_number: str):
    """Audit all campers on a specific bus"""
    
    # Get all campers assigned to this bus
    campers = await db.campers.find({
        "$or": [
            {"am_bus_number": bus_number},
            {"pm_bus_number": bus_number}
        ]
    }).to_list(None)
    
    results = {
        "bus_number": bus_number,
        "am_campers": [],
        "pm_campers": [],
        "am_count": 0,
        "pm_count": 0
    }
    
    seen_am = set()
    seen_pm = set()
    
    for camper in campers:
        name = f"{camper['first_name']} {camper['last_name']}"
        camper_id = camper.get('_id', '')
        
        # Check AM assignment
        if camper.get('am_bus_number') == bus_number and name not in seen_am:
            if not camper_id.endswith('_PM'):
                results["am_campers"].append({
                    "name": name,
                    "address": camper.get('location', {}).get('address', ''),
                    "am_bus": camper.get('am_bus_number', ''),
                    "pm_bus": camper.get('pm_bus_number', '')
                })
                seen_am.add(name)
        
        # Check PM assignment
        if camper.get('pm_bus_number') == bus_number and name not in seen_pm:
            results["pm_campers"].append({
                "name": name,
                "address": camper.get('location', {}).get('address', ''),
                "am_bus": camper.get('am_bus_number', ''),
                "pm_bus": camper.get('pm_bus_number', '')
            })
            seen_pm.add(name)
    
    results["am_count"] = len(results["am_campers"])
    results["pm_count"] = len(results["pm_campers"])
    
    return results


@api_router.get("/route-sheet/{bus_number}")
async def get_route_sheet(bus_number: str):
    """Get printable route sheet with turn-by-turn directions for a specific bus"""
    try:
        # Get campers for this bus (check both AM and PM bus fields)
        campers = await db.campers.find({
            "$or": [
                {"am_bus_number": bus_number},
                {"pm_bus_number": bus_number}
            ]
        }).to_list(None)
        
        if not campers:
            raise HTTPException(status_code=404, detail=f"No campers found for {bus_number}")
        
        # Generate route sheet with directions
        route_sheet = route_printer.generate_route_sheet(bus_number, campers)
        
        return route_sheet
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating route sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/route-sheet/{bus_number}/print")
async def get_printable_route_sheet(bus_number: str):
    """Get printable HTML route sheet"""
    try:
        from fastapi.responses import HTMLResponse
        
        # Get campers for this bus
        campers = await db.campers.find({
            "$or": [
                {"am_bus_number": bus_number},
                {"pm_bus_number": bus_number}
            ]
        }).to_list(None)
        
        if not campers:
            return HTMLResponse(content=f"<h1>No campers found for {bus_number}</h1>", status_code=404)
        
        # Generate route sheet
        route_sheet = route_printer.generate_route_sheet(bus_number, campers)
        
        # Generate HTML
        html = route_printer.generate_printable_html(route_sheet)
        
        return HTMLResponse(content=html)
    except Exception as e:
        logging.error(f"Error generating printable route: {str(e)}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

@api_router.get("/campers/filter")
async def filter_campers(bus_number: str = None, session: str = None, pickup_type: str = None):
    """Filter campers by bus, session, or pickup type"""
    try:
        query = {"bus_number": {"$exists": True, "$nin": ["NONE", ""]}}
        
        if bus_number:
            query["bus_number"] = bus_number
        
        if session:
            query["session"] = {"$regex": session, "$options": "i"}
        
        if pickup_type:
            query["pickup_type"] = pickup_type
        
        campers = await db.campers.find(query, {"_id": 0}).to_list(None)
        
        return {
            "status": "success",
            "count": len(campers),
            "campers": campers
        }
    except Exception as e:
        logging.error(f"Error filtering campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/reports/missing-addresses")
async def get_missing_addresses_report():
    """Get report of campers with bus assignments but no addresses"""
    try:
        missing = await db.campers.find({
            "location.latitude": 0.0,
            "bus_number": {"$exists": True, "$ne": "NONE"}
        }).to_list(None)
        
        report = []
        for camper in missing:
            report.append({
                "first_name": camper.get('first_name'),
                "last_name": camper.get('last_name'),
                "bus_number": camper.get('bus_number'),
                "session": camper.get('session'),
                "town": camper.get('town'),
                "zip_code": camper.get('zip_code')
            })
        
        return {
            "status": "warning",
            "count": len(report),
            "message": f"{len(report)} campers need addresses to appear on map",
            "campers": report
        }
    except Exception as e:
        logging.error(f"Error generating report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/campers/{camper_id}/change-bus")
async def change_camper_bus(camper_id: str, am_bus_number: str = None, pm_bus_number: str = None):
    """Manually override bus assignment - updates database AND Google Sheet instantly"""
    try:
        # Get camper data first
        camper = await db.campers.find_one({"_id": camper_id})
        if not camper:
            raise HTTPException(status_code=404, detail="Camper not found")
        
        updates = {}
        
        if am_bus_number:
            updates["am_bus_number"] = am_bus_number
            updates["bus_color"] = get_bus_color(am_bus_number)
        
        if pm_bus_number:
            updates["pm_bus_number"] = pm_bus_number
        
        if not updates:
            raise HTTPException(status_code=400, detail="No bus assignments provided")
        
        # Update database
        result = await db.campers.update_one(
            {"_id": camper_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            # INSTANTLY update Google Sheet via webhook
            webhook_url = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '')
            if webhook_url:
                try:
                    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                        webhook_data = {
                            "first_name": camper.get('first_name'),
                            "last_name": camper.get('last_name'),
                            "am_bus_number": updates.get('am_bus_number') or camper.get('am_bus_number'),
                            "pm_bus_number": updates.get('pm_bus_number') or camper.get('pm_bus_number')
                        }
                        
                        response = await client.post(
                            webhook_url,
                            json=webhook_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            logger.info(f"✓ Google Sheet updated instantly for {camper.get('first_name')} {camper.get('last_name')}")
                        else:
                            logger.warning(f"Webhook response: {response.status_code} - {response.text[:100]}")
                except Exception as e:
                    logger.error(f"Webhook error: {str(e)}")
            
            return {
                "status": "success",
                "message": "Updated bus assignments and Google Sheet"
            }
        else:
            raise HTTPException(status_code=404, detail="Camper not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error changing bus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/download/bus-assignments")
async def download_bus_assignments():
    """Download bus assignments as CSV for importing to CampMinder"""
    from fastapi.responses import StreamingResponse
    from io import StringIO
    import csv as csv_module
    
    try:
        campers = await db.campers.find({
            "am_bus_number": {"$exists": True, "$nin": ["NONE", ""]}
        }).to_list(None)
        
        # Create CSV
        output = StringIO()
        writer = csv_module.writer(output)
        
        # Header
        writer.writerow([
            'Last Name',
            'First Name', 
            'Bus Assignment',
            'Session',
            'Pickup Address',
            'Town',
            'Zip',
            'Type'
        ])
        
        # Data rows - sorted by last name, first name
        # Show both AM and PM for each camper
        for camper in sorted(campers, key=lambda x: (x.get('last_name', '').lower(), x.get('first_name', '').lower())):
            am_bus = camper.get('am_bus_number', camper.get('bus_number', ''))
            pm_bus = camper.get('pm_bus_number', camper.get('bus_number', ''))
            
            # AM row
            writer.writerow([
                camper.get('last_name', ''),
                camper.get('first_name', ''),
                am_bus,
                camper.get('session', ''),
                camper.get('location', {}).get('address', ''),
                camper.get('town', ''),
                camper.get('zip_code', ''),
                'AM Pickup'
            ])
            
            # PM row (if not "PM Drop-off Only" type, use same address)
            if camper.get('pickup_type') == 'PM Drop-off Only':
                # Already a separate PM entry, skip
                pass
            else:
                # Add PM row with same or different bus
                writer.writerow([
                    camper.get('last_name', ''),
                    camper.get('first_name', ''),
                    pm_bus,
                    camper.get('session', ''),
                    camper.get('location', {}).get('address', ''),
                    camper.get('town', ''),
                    camper.get('zip_code', ''),
                    'PM Drop-off'
                ])
        
        # Add separate PM-only entries
        pm_only = [c for c in campers if c.get('pickup_type') == 'PM Drop-off Only']
        for camper in sorted(pm_only, key=lambda x: (x.get('last_name', '').lower(), x.get('first_name', '').lower())):
            pm_bus = camper.get('pm_bus_number', camper.get('bus_number', ''))
            writer.writerow([
                camper.get('last_name', ''),
                camper.get('first_name', ''),
                pm_bus,
                camper.get('session', ''),
                camper.get('location', {}).get('address', ''),
                camper.get('town', ''),
                camper.get('zip_code', ''),
                'PM Drop-off'
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=bus_assignments_{datetime.now().strftime('%Y%m%d')}.csv"
            }
        )
    except Exception as e:
        logging.error(f"Error generating download: {str(e)}")
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
    """Background task to automatically sync from Google Sheets - handles ADD, UPDATE, DELETE"""
    global last_sync_time
    
    logger.info("Starting auto-sync from CampMinder Google Sheet...")
    
    try:
        # Download CSV from Google Sheets
        sheet_id = CAMPMINDER_SHEET_ID
        if not sheet_id:
            logger.error("No CAMPMINDER_SHEET_ID configured")
            return
        
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(csv_url)
            
            if response.status_code != 200:
                logger.error(f"Failed to download Google Sheet: {response.status_code}")
                return
            
            csv_content = response.text
            logger.info(f"Downloaded CSV from Google Sheets ({len(csv_content)} chars)")
        
        # Process CSV same as manual upload
        from io import StringIO
        import csv
        
        # Remove BOM if present
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        # Track camper IDs from sheet
        sheet_camper_ids = set()
        new_count = 0
        updated_count = 0
        
        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '')
            pm_bus_raw = row.get('2026Transportation M PM Bus', '').strip()
            
            # Include if: AM Bus method OR has valid PM bus (for car drop-off AM cases)
            has_pm_bus = pm_bus_raw and 'NONE' not in pm_bus_raw.upper() and not any(x in pm_bus_raw.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM'])
            
            if 'AM Bus' not in am_method and not has_pm_bus:
                continue
            
            # Get all required fields first
            first_name = row.get('First Name', '')
            last_name = row.get('Last Name', '')
            session = row.get('Enrolled Child Sessions', '')
            
            am_address = row.get('Trans-PickUpAddress', '')
            am_town = row.get('Trans-PickUpTown', '')
            am_zip = row.get('Trans-PickUpZip', '')
            
            pm_address = row.get('Trans-DropOffAddress', '')
            pm_town = row.get('Trans-DropOffTown', '')
            pm_zip = row.get('Trans-DropOffZip', '')
            
            am_bus = row.get('2026Transportation M AM Bus', '')
            pm_bus = row.get('2026Transportation M PM Bus', '')
            
            # Check if this is a PM-only camper (has PM bus but no AM bus)
            has_valid_pm_bus = pm_bus and pm_bus.strip() and 'NONE' not in pm_bus.upper() and not any(x in pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM'])
            is_pm_only_camper = (not am_bus or 'NONE' in am_bus.upper()) and has_valid_pm_bus
            
            # PRESERVE existing bus assignments, AUTO-ASSIGN if empty/NONE (but NOT for PM-only campers)
            final_am_bus = None
            final_pm_bus = None
            
            if am_bus and am_bus.strip() and 'NONE' not in am_bus.upper():
                # Has valid AM bus in sheet - KEEP IT (don't override)
                final_am_bus = am_bus.strip()
            elif am_address.strip() and not is_pm_only_camper:
                # Bus is empty/NONE but has address AND not a PM-only camper - AUTO-ASSIGN
                if 'existing_routes' not in locals():
                    all_db_campers = await db.campers.find({"am_bus_number": {"$exists": True}}).to_list(None)
                    existing_routes = {}
                    for ec in all_db_campers:
                        bus_str = ec.get('am_bus_number', '')
                        if bus_str and 'NONE' not in bus_str.upper():
                            try:
                                bus_num = int(''.join(filter(str.isdigit, bus_str)))
                                if bus_num not in existing_routes:
                                    existing_routes[bus_num] = []
                                if ec.get('location', {}).get('latitude', 0) != 0:
                                    existing_routes[bus_num].append({
                                        'lat': ec['location']['latitude'],
                                        'lng': ec['location']['longitude']
                                    })
                            except (ValueError, IndexError):
                                pass
                
                location_temp = geocode_address(am_address, am_town, am_zip)
                if location_temp:
                    optimal_bus = route_optimizer.find_optimal_bus(
                        {'lat': location_temp.latitude, 'lng': location_temp.longitude},
                        existing_routes
                    )
                    final_am_bus = f"Bus #{optimal_bus:02d}"
                    logger.info(f"AUTO-ASSIGNED (new): {first_name} {last_name} → {final_am_bus}")
            
            if pm_bus and pm_bus.strip() and 'NONE' not in pm_bus.upper():
                # Has valid PM bus - KEEP IT
                final_pm_bus = pm_bus.strip()
            else:
                # Use AM bus for PM (or NONE if AM is also NONE)
                final_pm_bus = final_am_bus if final_am_bus else "NONE"
            
            # Filter out non-bus PM values
            if final_pm_bus and any(x in final_pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM']):
                final_pm_bus = final_am_bus if final_am_bus else "NONE"
            
            # If no bus was assigned, set to NONE (so we can track and display these campers)
            if not final_am_bus:
                final_am_bus = "NONE"
            if not final_pm_bus:
                final_pm_bus = "NONE"
            
            # For PM-only campers (car drop-off AM OR AM bus is NONE but has PM bus), use PM address if AM address is empty
            effective_address = am_address.strip() or pm_address.strip()
            effective_town = am_town.strip() or pm_town.strip()
            effective_zip = am_zip.strip() or pm_zip.strip()
            
            # For campers without address but with valid bus, still add them (for route planning)
            has_any_bus = (final_am_bus and final_am_bus != "NONE") or (final_pm_bus and final_pm_bus != "NONE")
            
            if not effective_address and not has_any_bus:
                # Skip campers with no address AND no bus
                continue
            
            # Determine pickup type - PM only if: no AM method, OR AM bus is NONE but has valid PM bus
            is_pm_only = ('AM Bus' not in am_method and has_pm_bus) or (final_am_bus == "NONE" and final_pm_bus != "NONE")
            
            # Calculate final PM values
            pm_final_address = pm_address if pm_address.strip() else am_address
            pm_final_town = pm_town if pm_town.strip() else am_town
            pm_final_zip = pm_zip if pm_zip.strip() else am_zip
            
            # Process camper with BOTH AM and PM info
            # Create ONE entry if same address, TWO entries if different addresses
            
            # Generate camper ID - use zip if available, otherwise use "NOADDR"
            id_zip = effective_zip if effective_zip else "NOADDR"
            camper_id = f"{last_name}_{first_name}_{id_zip}".replace(' ', '_')
            sheet_camper_ids.add(camper_id)
            
            if effective_address:
                location = geocode_address(effective_address, effective_town, effective_zip)
                if not location:
                    location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {effective_address}")
                    logger.warning(f"Geocoding failed: {first_name} {last_name} - {effective_address}")
                
                # Calculate offset based on existing campers at this address
                address_key = f"{location.latitude:.6f}_{location.longitude:.6f}"
                existing_at_address = await db.campers.count_documents({
                    "location.latitude": {"$gte": location.latitude - 0.001, "$lte": location.latitude + 0.001},
                    "location.longitude": {"$gte": location.longitude - 0.001, "$lte": location.longitude + 0.001}
                })
                
                offset = existing_at_address * 0.00002  # ~6 feet per existing camper
                
                # Determine bus color and pickup type
                if is_pm_only:
                    # PM-only camper (car drop-off in AM)
                    bus_color = get_bus_color(final_pm_bus) if final_pm_bus != "NONE" else "#808080"
                    pickup_type_val = "PM Drop-off Only"
                elif final_am_bus == "NONE":
                    bus_color = "#808080"
                    pickup_type_val = "NEEDS BUS"
                else:
                    bus_color = get_bus_color(final_am_bus)
                    pickup_type_val = "AM Pickup" if (pm_final_address.strip() and pm_final_address != am_address) else "AM & PM"
                
                camper_doc = {
                    "_id": camper_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "session": session,
                    "location": {
                        "latitude": location.latitude + offset,
                        "longitude": location.longitude + offset,
                        "address": location.address
                    },
                    "town": effective_town,
                    "zip_code": effective_zip,
                    "pickup_type": pickup_type_val,
                    "am_bus_number": final_am_bus,
                    "pm_bus_number": final_pm_bus,
                    "bus_color": bus_color,
                    "created_at": datetime.now(timezone.utc)
                }
                
                result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
                if result.upserted_id:
                    new_count += 1
                elif result.modified_count > 0:
                    updated_count += 1
            else:
                # No address - still add for route planning
                # For PM-only campers, use PM bus color
                if is_pm_only and final_pm_bus and final_pm_bus != "NONE":
                    bus_color = get_bus_color(final_pm_bus)
                    pickup_type_val = "PM Drop-off Only - NO ADDRESS"
                elif final_am_bus and final_am_bus != "NONE":
                    bus_color = get_bus_color(final_am_bus)
                    pickup_type_val = "NO ADDRESS"
                else:
                    bus_color = "#808080"
                    pickup_type_val = "NO ADDRESS - NO BUS"
                
                camper_doc = {
                    "_id": camper_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "session": session,
                    "location": {"latitude": 0.0, "longitude": 0.0, "address": "ADDRESS NEEDED"},
                    "town": effective_town or "UNKNOWN",
                    "zip_code": effective_zip or "UNKNOWN",
                    "pickup_type": pickup_type_val,
                    "am_bus_number": final_am_bus,
                    "pm_bus_number": final_pm_bus,
                    "bus_color": bus_color,
                    "created_at": datetime.now(timezone.utc)
                }
                result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
                if result.upserted_id:
                    new_count += 1
            
            # Only create separate PM entry if:
            # 1. PM address is different from AM address
            # 2. AND this is NOT a PM-only camper (PM-only campers already have their entry with PM address)
            if pm_final_address.strip() and pm_final_address != am_address and not is_pm_only:
                camper_id_pm = f"{last_name}_{first_name}_{pm_zip}_PM".replace(' ', '_')
                sheet_camper_ids.add(camper_id_pm)
                
                pm_location = geocode_address(pm_final_address, pm_final_town, pm_final_zip)
                if not pm_location:
                    pm_location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {pm_final_address}")
                    logger.warning(f"PM geocoding failed: {first_name} {last_name} - {pm_final_address}")
                
                # Calculate offset for PM address based on existing campers
                existing_at_pm_address = await db.campers.count_documents({
                    "location.latitude": {"$gte": pm_location.latitude - 0.001, "$lte": pm_location.latitude + 0.001},
                    "location.longitude": {"$gte": pm_location.longitude - 0.001, "$lte": pm_location.longitude + 0.001}
                })
                
                pm_offset = existing_at_pm_address * 0.00008
                
                camper_doc_pm = {
                    "_id": camper_id_pm,
                    "first_name": first_name,
                    "last_name": last_name,
                    "session": session,
                    "location": {
                        "latitude": pm_location.latitude + pm_offset,
                        "longitude": pm_location.longitude + pm_offset,
                        "address": pm_location.address
                    },
                    "town": pm_final_town,
                    "zip_code": pm_final_zip,
                    "pickup_type": "PM Drop-off Only",
                    "am_bus_number": final_am_bus,
                    "pm_bus_number": final_pm_bus,
                    "bus_color": get_bus_color(final_pm_bus),
                    "created_at": datetime.now(timezone.utc)
                }
                result = await db.campers.replace_one({"_id": camper_id_pm}, camper_doc_pm, upsert=True)
                if result.upserted_id:
                    new_count += 1
                elif result.modified_count > 0:
                    updated_count += 1
        
        # Delete campers no longer in sheet
        all_db_campers = await db.campers.find({}).to_list(None)
        deleted_count = 0
        for db_camper in all_db_campers:
            if db_camper['_id'] not in sheet_camper_ids:
                await db.campers.delete_one({"_id": db_camper['_id']})
                deleted_count += 1
                logger.info(f"Deleted: {db_camper.get('first_name')} {db_camper.get('last_name')}")
        
        last_sync_time = datetime.now(timezone.utc)
        logger.info(f"Auto-sync complete: {new_count} new, {updated_count} updated, {deleted_count} deleted")
        
        # AUTOMATICALLY apply sibling offset after sync
        await apply_sibling_offset(db)
        
        await db.sync_status.update_one(
            {"_id": "auto_sync"},
            {"$set": {
                "last_sync": last_sync_time,
                "new_campers": new_count,
                "updated_campers": updated_count,
                "deleted_campers": deleted_count,
                "status": "success",
                "source": "Google Sheets"
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
        
        await asyncio.sleep(SYNC_INTERVAL_MINUTES * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_task
    
    logger.info(f"Auto-sync enabled: {AUTO_SYNC_ENABLED}")
    if AUTO_SYNC_ENABLED:
        logger.info(f"Starting auto-sync from Google Sheets (interval: {SYNC_INTERVAL_MINUTES} min)")
        sync_task = asyncio.create_task(sync_loop())
    
    yield
    
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

# Recreate app with lifespan
app = FastAPI(lifespan=lifespan)
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

