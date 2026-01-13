"""Sync operations router - Google Sheet, CampMinder integration."""

import logging
import csv
from io import StringIO
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
import httpx

from models.schemas import GeoLocation, CamperPin
from services.database import (
    db, gmaps, campminder_api, 
    CAMPMINDER_SHEET_ID, OUTPUT_SHEET_ID, GOOGLE_SHEETS_WEBHOOK_URL
)
from services.bus_utils import get_bus_color
from services.geocoding import geocode_address
from sibling_offset import apply_sibling_offset

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sync"])


@router.post("/sync-campers")
async def sync_campers(csv_data: Dict[str, Any]):
    """Sync campers from CSV data."""
    try:
        pins = []
        csv_content = csv_data.get('csv_content', '')
        
        if not csv_content:
            raise HTTPException(status_code=400, detail="No CSV content provided")
        
        csv_file = StringIO(csv_content)
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
            
            if am_address.strip():
                location = geocode_address(am_address, am_town, am_zip)
                if not location:
                    location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {am_address}")
                    logger.warning(f"Geocoding failed for {first_name} {last_name}: {am_address}")
                
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
                location_pm = geocode_address(pm_final_address, pm_final_town, pm_final_zip)
                if not location_pm:
                    location_pm = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {pm_final_address}")
                    logger.warning(f"PM geocoding failed for {first_name} {last_name}: {pm_final_address}")
                
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
        
        await apply_sibling_offset(db)
        
        return {"status": "success", "count": len(pins)}
    except Exception as e:
        logger.error(f"Error syncing campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-sync")
async def trigger_manual_sync():
    """Manually trigger a sync from Google Sheet."""
    from .sync_helpers import auto_sync_campminder
    try:
        await auto_sync_campminder()
        return {"status": "success", "message": "Sync from Google Sheet completed"}
    except Exception as e:
        logger.error(f"Error in manual sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-campminder-api")
async def test_campminder_api():
    """Test CampMinder API connectivity."""
    try:
        result = await campminder_api.test_api_connectivity()
        return result
    except Exception as e:
        logger.error(f"Error testing CampMinder API: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/sync-from-campminder-api")
async def sync_from_campminder_api():
    """Sync camper bus data directly from CampMinder API."""
    try:
        logger.info("Starting sync from CampMinder API")
        
        token = await campminder_api.get_jwt_token()
        if not token:
            return {
                "status": "error",
                "message": "CampMinder API authentication failed.",
                "campers_processed": 0,
                "recommendation": "Use 'Refresh from CSV Now' button instead."
            }
        
        campers_data = await campminder_api.get_all_campers_with_bus_data(season_id="2026")
        
        if not campers_data:
            return {
                "status": "warning",
                "message": "CampMinder API returned no camper data.",
                "campers_processed": 0,
                "recommendation": "Use Google Sheet sync as fallback."
            }
        
        new_count = 0
        updated_count = 0
        skipped_count = 0
        
        for camper in campers_data:
            if not camper.get('address'):
                skipped_count += 1
                continue
            
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            if not am_bus and not pm_bus:
                skipped_count += 1
                continue
            
            location = geocode_address(
                camper['address'],
                camper.get('town', ''),
                camper.get('zip_code', '')
            )
            
            if not location or location.latitude == 0:
                skipped_count += 1
                continue
            
            camper_id = f"{camper['last_name']}_{camper['first_name']}_{camper.get('zip_code', 'NOZIP')}".replace(' ', '_')
            
            primary_bus = am_bus if am_bus and am_bus.startswith('Bus') else pm_bus
            bus_color = get_bus_color(primary_bus) if primary_bus else "#808080"
            
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
                "am_bus_number": am_bus,
                "pm_bus_number": pm_bus,
                "bus_color": bus_color,
                "synced_from": "campminder_api",
                "created_at": datetime.now(timezone.utc)
            }
            
            result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
            
            if result.upserted_id:
                new_count += 1
            elif result.modified_count > 0:
                updated_count += 1
        
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


@router.post("/sync-to-google-sheet")
async def sync_bus_assignments_to_sheet():
    """Sync all bus assignments to Google Sheet via webhook."""
    try:
        webhook_url = GOOGLE_SHEETS_WEBHOOK_URL
        if not webhook_url:
            return {
                "status": "error",
                "message": "GOOGLE_SHEETS_WEBHOOK_URL not configured"
            }
        
        all_campers = await db.campers.find({}).to_list(None)
        
        updates = []
        seen_campers = set()
        
        for camper in all_campers:
            first_name = camper.get('first_name', '').strip()
            last_name = camper.get('last_name', '').strip()
            camper_id = camper.get('_id', '')
            
            if camper_id.endswith('_PM'):
                continue
            
            key = f"{first_name}|{last_name}"
            if key in seen_campers:
                continue
            seen_campers.add(key)
            
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            if am_bus == 'NONE':
                am_bus = ''
            if pm_bus == 'NONE':
                pm_bus = ''
            
            if am_bus or pm_bus:
                updates.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "am_bus": am_bus,
                    "pm_bus": pm_bus
                })
        
        logger.info(f"Syncing {len(updates)} campers to Google Sheet via webhook")
        
        payload = {
            "action": "bulk_update",
            "campers": updates
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(webhook_url, json=payload)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Updated {len(updates)} bus assignments in Google Sheet",
                    "updates_count": len(updates)
                }
            else:
                logger.error(f"Webhook error: {response.status_code} - {response.text}")
                return {
                    "status": "error",
                    "message": f"Webhook returned status {response.status_code}"
                }
        
    except Exception as e:
        logger.error(f"Error syncing to sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-changes")
async def detect_bus_assignment_changes():
    """
    Detect changes in bus assignments between database and Google Sheet.
    """
    try:
        db_campers = await db.campers.find({}).to_list(None)
        
        db_lookup = {}
        for camper in db_campers:
            first_name = camper.get('first_name', '').strip()
            last_name = camper.get('last_name', '').strip()
            camper_id = camper.get('_id', '')
            
            if camper_id.endswith('_PM'):
                continue
            
            key = f"{first_name}|{last_name}".lower()
            
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            if am_bus == 'NONE':
                am_bus = ''
            if pm_bus == 'NONE':
                pm_bus = ''
            
            db_lookup[key] = {
                'first_name': first_name,
                'last_name': last_name,
                'am_bus': am_bus,
                'pm_bus': pm_bus,
                'address': camper.get('location', {}).get('address', ''),
                'has_location': bool(camper.get('location', {}).get('latitude'))
            }
        
        sheet_id = CAMPMINDER_SHEET_ID
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
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
            if 'AM Bus' in col and 'Trans' in col:
                am_bus_col = col
            elif 'PM Bus' in col and 'Trans' in col:
                pm_bus_col = col
        
        sheet_lookup = {}
        for row in reader:
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            
            if not first_name or not last_name:
                continue
            
            key = f"{first_name}|{last_name}".lower()
            
            sheet_am = row.get(am_bus_col, '').strip() if am_bus_col else ''
            sheet_pm = row.get(pm_bus_col, '').strip() if pm_bus_col else ''
            
            if sheet_am.upper() == 'NONE':
                sheet_am = ''
            if sheet_pm.upper() == 'NONE':
                sheet_pm = ''
            
            sheet_lookup[key] = {
                'first_name': first_name,
                'last_name': last_name,
                'am_bus': sheet_am,
                'pm_bus': sheet_pm
            }
        
        changes = []
        
        for key, db_data in db_lookup.items():
            sheet_data = sheet_lookup.get(key)
            
            if not sheet_data:
                continue
            
            first_name = db_data['first_name']
            last_name = db_data['last_name']
            full_name = f"{first_name} {last_name}"
            
            db_am = db_data['am_bus']
            db_pm = db_data['pm_bus']
            sheet_am = sheet_data['am_bus']
            sheet_pm = sheet_data['pm_bus']
            
            had_am = bool(sheet_am and sheet_am.startswith('Bus'))
            has_am = bool(db_am and db_am.startswith('Bus'))
            
            if not had_am and has_am:
                changes.append({
                    'name': full_name,
                    'type': 'AM_ADDED',
                    'old_value': sheet_am or 'EMPTY',
                    'new_value': db_am,
                    'message': f"{full_name}: AM bus ADDED ({db_am})"
                })
            elif had_am and not has_am:
                changes.append({
                    'name': full_name,
                    'type': 'AM_REMOVED',
                    'old_value': sheet_am,
                    'new_value': 'EMPTY',
                    'message': f"{full_name}: AM bus REMOVED (was {sheet_am})"
                })
            elif had_am and has_am and sheet_am != db_am:
                changes.append({
                    'name': full_name,
                    'type': 'AM_CHANGED',
                    'old_value': sheet_am,
                    'new_value': db_am,
                    'message': f"{full_name}: AM bus CHANGED ({sheet_am} → {db_am})"
                })
            
            had_pm = bool(sheet_pm and sheet_pm.startswith('Bus'))
            has_pm = bool(db_pm and db_pm.startswith('Bus'))
            
            if not had_pm and has_pm:
                changes.append({
                    'name': full_name,
                    'type': 'PM_ADDED',
                    'old_value': sheet_pm or 'EMPTY',
                    'new_value': db_pm,
                    'message': f"{full_name}: PM bus ADDED ({db_pm})"
                })
            elif had_pm and not has_pm:
                changes.append({
                    'name': full_name,
                    'type': 'PM_REMOVED',
                    'old_value': sheet_pm,
                    'new_value': 'EMPTY',
                    'message': f"{full_name}: PM bus REMOVED (was {sheet_pm})"
                })
            elif had_pm and has_pm and sheet_pm != db_pm:
                changes.append({
                    'name': full_name,
                    'type': 'PM_CHANGED',
                    'old_value': sheet_pm,
                    'new_value': db_pm,
                    'message': f"{full_name}: PM bus CHANGED ({sheet_pm} → {db_pm})"
                })
        
        am_added = [c for c in changes if c['type'] == 'AM_ADDED']
        pm_added = [c for c in changes if c['type'] == 'PM_ADDED']
        am_removed = [c for c in changes if c['type'] == 'AM_REMOVED']
        pm_removed = [c for c in changes if c['type'] == 'PM_REMOVED']
        am_changed = [c for c in changes if c['type'] == 'AM_CHANGED']
        pm_changed = [c for c in changes if c['type'] == 'PM_CHANGED']
        
        logger.info(f"Total changes detected: {len(changes)}")
        
        sync_result = None
        if changes:
            logger.info("Syncing changes to Google Sheet...")
            sync_response = await sync_bus_assignments_to_sheet()
            sync_result = sync_response
        
        return {
            "status": "success",
            "total_changes": len(changes),
            "summary": {
                "am_added": len(am_added),
                "pm_added": len(pm_added),
                "am_removed": len(am_removed),
                "pm_removed": len(pm_removed),
                "am_changed": len(am_changed),
                "pm_changed": len(pm_changed)
            },
            "changes": changes,
            "am_added_campers": [c['name'] for c in am_added],
            "pm_added_campers": [c['name'] for c in pm_added],
            "sync_result": sync_result
        }
        
    except Exception as e:
        logger.error(f"Error detecting changes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto-sync-status")
async def get_auto_sync_status():
    """Get current auto-sync status."""
    from services.database import AUTO_SYNC_ENABLED, SYNC_INTERVAL_MINUTES, last_sync_time
    
    sync_status = await db.sync_status.find_one({"_id": "auto_sync"})
    
    return {
        "enabled": AUTO_SYNC_ENABLED,
        "interval_minutes": SYNC_INTERVAL_MINUTES,
        "last_sync": last_sync_time.isoformat() if last_sync_time else None,
        "sync_info": sync_status if sync_status else {}
    }
