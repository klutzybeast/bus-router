"""
Sync helper functions for auto-sync from Google Sheets.
This module contains the complete auto-sync logic.
"""

import logging
import csv
import asyncio
from io import StringIO
from datetime import datetime, timezone

import httpx

from services.database import (
    db, route_optimizer, 
    CAMPMINDER_SHEET_ID, AUTO_SYNC_ENABLED, SYNC_INTERVAL_MINUTES
)
from services.bus_utils import get_bus_color
from services.geocoding import geocode_address
from models.schemas import GeoLocation
from sibling_offset import apply_sibling_offset

logger = logging.getLogger(__name__)

# Global sync state
last_sync_time = None


async def auto_sync_campminder():
    """Background task to automatically sync from Google Sheets - handles ADD, UPDATE, DELETE"""
    global last_sync_time
    
    logger.info("Starting auto-sync from CampMinder Google Sheet...")
    
    try:
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
        
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        sheet_camper_ids = set()
        new_count = 0
        updated_count = 0
        existing_routes = None
        
        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '')
            pm_bus_raw = row.get('2026Transportation M PM Bus', '').strip()
            
            has_pm_bus = pm_bus_raw and 'NONE' not in pm_bus_raw.upper() and not any(x in pm_bus_raw.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM'])
            
            if 'AM Bus' not in am_method and not has_pm_bus:
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
            
            am_bus = row.get('2026Transportation M AM Bus', '')
            pm_bus = row.get('2026Transportation M PM Bus', '')
            
            has_valid_pm_bus = pm_bus and pm_bus.strip() and 'NONE' not in pm_bus.upper() and not any(x in pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM'])
            is_pm_only_camper = (not am_bus or 'NONE' in am_bus.upper()) and has_valid_pm_bus
            
            final_am_bus = None
            final_pm_bus = None
            
            if am_bus and am_bus.strip() and 'NONE' not in am_bus.upper():
                final_am_bus = am_bus.strip()
            elif am_address.strip() and not is_pm_only_camper:
                if existing_routes is None:
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
                final_pm_bus = pm_bus.strip()
            else:
                final_pm_bus = final_am_bus if final_am_bus else "NONE"
            
            if final_pm_bus and any(x in final_pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM']):
                final_pm_bus = final_am_bus if final_am_bus else "NONE"
            
            if not final_am_bus:
                final_am_bus = "NONE"
            if not final_pm_bus:
                final_pm_bus = "NONE"
            
            effective_address = am_address.strip() or pm_address.strip()
            effective_town = am_town.strip() or pm_town.strip()
            effective_zip = am_zip.strip() or pm_zip.strip()
            
            has_any_bus = (final_am_bus and final_am_bus != "NONE") or (final_pm_bus and final_pm_bus != "NONE")
            
            if not effective_address and not has_any_bus:
                continue
            
            is_pm_only = ('AM Bus' not in am_method and has_pm_bus) or (final_am_bus == "NONE" and final_pm_bus != "NONE")
            
            pm_final_address = pm_address if pm_address.strip() else am_address
            pm_final_town = pm_town if pm_town.strip() else am_town
            pm_final_zip = pm_zip if pm_zip.strip() else am_zip
            
            id_zip = effective_zip if effective_zip else "NOADDR"
            camper_id = f"{last_name}_{first_name}_{id_zip}".replace(' ', '_')
            sheet_camper_ids.add(camper_id)
            
            if effective_address:
                location = geocode_address(effective_address, effective_town, effective_zip)
                if not location:
                    location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {effective_address}")
                    logger.warning(f"Geocoding failed: {first_name} {last_name} - {effective_address}")
                
                existing_at_address = await db.campers.count_documents({
                    "location.latitude": {"$gte": location.latitude - 0.001, "$lte": location.latitude + 0.001},
                    "location.longitude": {"$gte": location.longitude - 0.001, "$lte": location.longitude + 0.001}
                })
                
                offset = existing_at_address * 0.00002
                
                if is_pm_only:
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
            
            if pm_final_address.strip() and pm_final_address != am_address and not is_pm_only:
                camper_id_pm = f"{last_name}_{first_name}_{pm_zip}_PM".replace(' ', '_')
                sheet_camper_ids.add(camper_id_pm)
                
                pm_location = geocode_address(pm_final_address, pm_final_town, pm_final_zip)
                if not pm_location:
                    pm_location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {pm_final_address}")
                    logger.warning(f"PM geocoding failed: {first_name} {last_name} - {pm_final_address}")
                
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
        
        all_db_campers = await db.campers.find({}).to_list(None)
        deleted_count = 0
        for db_camper in all_db_campers:
            if db_camper['_id'] not in sheet_camper_ids:
                await db.campers.delete_one({"_id": db_camper['_id']})
                deleted_count += 1
                logger.info(f"Deleted: {db_camper.get('first_name')} {db_camper.get('last_name')}")
        
        last_sync_time = datetime.now(timezone.utc)
        logger.info(f"Auto-sync complete: {new_count} new, {updated_count} updated, {deleted_count} deleted")
        
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


def get_last_sync_time():
    """Get the last sync time."""
    return last_sync_time
