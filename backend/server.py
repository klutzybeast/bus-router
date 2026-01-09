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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

gmaps = googlemaps.Client(key=os.environ['GOOGLE_MAPS_API_KEY'])

app = FastAPI()
api_router = APIRouter(prefix="/api")

BUS_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff",
    "#9a6324", "#fffac8", "#800000", "#aaffc3", "#808000", "#ffd8b1",
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
        campminder_url = os.environ.get('CAMPMINDER_API_URL')
        api_key = os.environ.get('CAMPMINDER_API_KEY')
        
        existing_campers = await db.campers.find({}, {"_id": 0}).to_list(None)
        
        if existing_campers:
            return existing_campers
        
        return []
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
            
            first_name = row.get('First Name', '')
            last_name = row.get('Last Name', '')
            session = row.get('Enrolled Child Sessions', '')
            
            am_address = row.get('Trans-PickUpAddress', '')
            am_town = row.get('Trans-PickUpTown', '')
            am_zip = row.get('Trans-PickUpZip', '')
            
            pm_address = row.get('Trans-DropOffAddress', '')
            pm_town = row.get('Trans-DropOffTown', '')
            pm_zip = row.get('Trans-DropOffZip', '')
            
            if am_bus and am_address.strip():
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
            
            if pm_bus and pm_address.strip() and pm_address != am_address:
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

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()