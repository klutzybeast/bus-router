"""Sync helper functions."""

import logging
import csv
from io import StringIO
from datetime import datetime, timezone

import httpx

from services.database import (
    db, CAMPMINDER_SHEET_ID, GOOGLE_SHEETS_WEBHOOK_URL
)
from services.bus_utils import get_bus_color
from services.geocoding import geocode_address
from models.schemas import GeoLocation, CamperPin
from sibling_offset import apply_sibling_offset

logger = logging.getLogger(__name__)


async def auto_sync_campminder():
    """
    Auto-sync from Google Sheet (CampMinder export).
    This is the main sync function that refreshes data from the source sheet.
    """
    global last_sync_time
    
    logger.info("=== AUTO-SYNC: Starting sync from Google Sheet ===")
    
    try:
        sheet_id = CAMPMINDER_SHEET_ID
        if not sheet_id:
            logger.warning("No CAMPMINDER_SHEET_ID configured")
            return {"status": "skipped", "reason": "No sheet ID configured"}
        
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        logger.info(f"Fetching from: {csv_url}")
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(csv_url)
            csv_content = response.text
        
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        reader = csv.DictReader(StringIO(csv_content))
        
        fieldnames = reader.fieldnames
        am_bus_col = None
        pm_bus_col = None
        
        for col in fieldnames:
            if '2026Transportation M AM Bus' in col:
                am_bus_col = col
            elif '2026Transportation M PM Bus' in col:
                pm_bus_col = col
        
        if not am_bus_col:
            for col in fieldnames:
                if 'AM Bus' in col:
                    am_bus_col = col
                    break
        if not pm_bus_col:
            for col in fieldnames:
                if 'PM Bus' in col:
                    pm_bus_col = col
                    break
        
        logger.info(f"AM Bus Column: {am_bus_col}")
        logger.info(f"PM Bus Column: {pm_bus_col}")
        
        pins = []
        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '')
            
            if 'AM Bus' not in am_method:
                continue
            
            am_bus = row.get(am_bus_col, '').strip() if am_bus_col else ''
            pm_bus = row.get(pm_bus_col, '').strip() if pm_bus_col else ''
            
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
            
            final_pm_bus = pm_bus.strip() if pm_bus and pm_bus.strip() else am_bus
            if final_pm_bus and any(x in final_pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM', 'NONE']):
                final_pm_bus = am_bus
            
            pm_final_address = pm_address if pm_address.strip() else am_address
            pm_final_town = pm_town if pm_town.strip() else am_town
            pm_final_zip = pm_zip if pm_zip.strip() else am_zip
            
            camper_id = f"{last_name}_{first_name}_{am_zip}".replace(' ', '_')
            
            if am_address.strip():
                existing = await db.campers.find_one({"_id": camper_id})
                
                if existing and existing.get('location', {}).get('latitude', 0) != 0:
                    location = GeoLocation(
                        latitude=existing['location']['latitude'],
                        longitude=existing['location']['longitude'],
                        address=existing['location'].get('address', '')
                    )
                else:
                    location = geocode_address(am_address, am_town, am_zip)
                    if not location:
                        location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {am_address}")
                
                existing_count = len([p for p in pins if 
                    abs(p.location.latitude - location.latitude) < 0.0001 and
                    abs(p.location.longitude - location.longitude) < 0.0001
                ])
                offset = existing_count * 0.00002
                
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
            
            if am_bus != "NONE" and pm_final_address != am_address and pm_final_address.strip():
                pm_camper_id = f"{camper_id}_PM"
                existing_pm = await db.campers.find_one({"_id": pm_camper_id})
                
                if existing_pm and existing_pm.get('location', {}).get('latitude', 0) != 0:
                    location_pm = GeoLocation(
                        latitude=existing_pm['location']['latitude'],
                        longitude=existing_pm['location']['longitude'],
                        address=existing_pm['location'].get('address', '')
                    )
                else:
                    location_pm = geocode_address(pm_final_address, pm_final_town, pm_final_zip)
                    if not location_pm:
                        location_pm = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {pm_final_address}")
                
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
            pins_to_insert = []
            for i, pin in enumerate(pins):
                pin_dict = pin.model_dump()
                
                base_id = f"{pin.last_name}_{pin.first_name}_{pin.zip_code}".replace(' ', '_')
                if pin.pickup_type == "PM Drop-off Only":
                    pin_dict['_id'] = f"{base_id}_PM"
                else:
                    pin_dict['_id'] = base_id
                
                pins_to_insert.append(pin_dict)
            
            await db.campers.insert_many(pins_to_insert)
        
        await apply_sibling_offset(db)
        
        from services import database
        database.last_sync_time = datetime.now(timezone.utc)
        
        logger.info(f"AUTO-SYNC COMPLETE: {len(pins)} campers synced")
        
        return {
            "status": "success",
            "campers_synced": len(pins),
            "sync_time": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"AUTO-SYNC ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}
