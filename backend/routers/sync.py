"""Sync and CampMinder integration endpoints."""

import os
import csv
import logging
import asyncio
from io import StringIO
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from services.database import (
    db, campminder_api, route_optimizer, 
    CAMPMINDER_SHEET_ID, GOOGLE_SHEETS_WEBHOOK_URL,
    AUTO_SYNC_ENABLED, SYNC_INTERVAL_MINUTES, last_sync_time
)
from services.helpers import get_active_season_id
from services.geocoding import geocode_address_cached
from services.sync_engine import auto_sync_campminder
from services.bus_utils import get_bus_color
from models.schemas import GeoLocation, CamperPin
from sibling_offset import apply_sibling_offset

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sync"])

@router.post("/sync-campers")
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
                location = await geocode_address_cached(am_address, am_town, am_zip)
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
                    location_pm = await geocode_address_cached(pm_final_address, pm_final_town, pm_final_zip)
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

@router.post("/refresh-colors")
async def refresh_colors():
    try:
        campers = await db.campers.find({}).to_list(None)
        
        for camper in campers:
            # Use am_bus_number as primary, fallback to bus_number for legacy
            bus_num = camper.get('am_bus_number') or camper.get('bus_number', '')
            if bus_num and bus_num != 'NONE' and bus_num.startswith('Bus'):
                new_color = get_bus_color(bus_num)
            else:
                # Use PM bus if AM is not valid
                pm_bus = camper.get('pm_bus_number', '')
                if pm_bus and pm_bus != 'NONE' and pm_bus.startswith('Bus'):
                    new_color = get_bus_color(pm_bus)
                else:
                    new_color = "#808080"  # Gray for no bus
            
            await db.campers.update_one(
                {"_id": camper["_id"]},
                {"$set": {"bus_color": new_color}}
            )
        
        return {"status": "success", "updated": len(campers)}
    except Exception as e:
        logging.error(f"Error refreshing colors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize-routes")
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

@router.post("/auto-assign-new-camper")
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
@router.post("/sync-assignments-to-campminder")
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

@router.get("/auto-sync-status")
async def get_auto_sync_status():
    """Get current auto-sync status"""
    sync_status = await db.sync_status.find_one({"_id": "auto_sync"})
    
    return {
        "enabled": AUTO_SYNC_ENABLED,
        "interval_minutes": SYNC_INTERVAL_MINUTES,
        "last_sync": last_sync_time.isoformat() if last_sync_time else None,
        "sync_info": sync_status if sync_status else {}
    }

@router.post("/trigger-sync")
async def trigger_manual_sync():
    """Manually trigger a sync with CampMinder (from Google Sheet)"""
    try:
        await auto_sync_campminder()
        return {"status": "success", "message": "Sync from Google Sheet completed"}
    except Exception as e:
        logging.error(f"Error in manual sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear-guardian-cache")
async def clear_guardian_cache():
    """
    Clear the cached guardian/parent contact data.
    Use this if parent phone numbers are not showing correctly.
    The next roster request will re-fetch from CampMinder API.
    """
    try:
        result = await db.campminder_relatives_cache.delete_many({})
        return {
            "status": "success", 
            "message": f"Cleared {result.deleted_count} cached entries. Next roster request will fetch fresh data."
        }
    except Exception as e:
        logging.error(f"Error clearing guardian cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/test-campminder-api")
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


@router.post("/sync-from-campminder-api")
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
            
            # Geocode address (using cached version)
            location = await geocode_address_cached(
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
@router.post("/sync-to-google-sheet")
async def sync_bus_assignments_to_sheet():
    """
    Sync all bus assignments back to the Google Sheet.
    Updates the AM Bus and PM Bus columns for all campers.
    
    Sheet ID: 1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k
    """
    import httpx
    import csv
    from io import StringIO
    
    logger.info("=== SYNCING BUS ASSIGNMENTS TO GOOGLE SHEET ===")
    
    try:
        # Get all campers from database
        db_campers = await db.campers.find({}).to_list(None)
        logger.info(f"Found {len(db_campers)} campers in database")
        
        # Build a lookup by first_name + last_name
        bus_lookup = {}
        for camper in db_campers:
            first_name = camper.get('first_name', '').strip()
            last_name = camper.get('last_name', '').strip()
            camper_id = camper.get('_id', '')
            
            # Skip PM-specific entries
            if camper_id.endswith('_PM'):
                continue
            
            key = f"{first_name}|{last_name}".lower()
            
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            # Clean up
            if am_bus == 'NONE':
                am_bus = ''
            if pm_bus == 'NONE':
                pm_bus = ''
            
            bus_lookup[key] = {
                'am_bus': am_bus,
                'pm_bus': pm_bus
            }
        
        logger.info(f"Built lookup for {len(bus_lookup)} unique campers")
        
        # Read current sheet data
        sheet_id = CAMPMINDER_SHEET_ID
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(csv_url)
            original_csv = response.text
        
        # Parse CSV
        if original_csv.startswith('\ufeff'):
            original_csv = original_csv[1:]
        
        reader = csv.DictReader(StringIO(original_csv))
        fieldnames = reader.fieldnames
        
        # Find the AM Bus and PM Bus column names and indices
        am_bus_col = None
        pm_bus_col = None
        am_bus_idx = None
        pm_bus_idx = None
        
        for idx, col in enumerate(fieldnames):
            if 'AM Bus' in col and 'Trans' in col:
                am_bus_col = col
                am_bus_idx = idx + 1  # 1-based for Sheets
            elif 'PM Bus' in col and 'Trans' in col:
                pm_bus_col = col
                pm_bus_idx = idx + 1
        
        if not am_bus_col or not pm_bus_col:
            logger.error(f"Could not find AM/PM Bus columns in sheet. Columns: {fieldnames}")
            return {
                "status": "error",
                "message": "Could not find AM Bus or PM Bus columns in sheet",
                "available_columns": [c for c in fieldnames if 'bus' in c.lower() or 'trans' in c.lower()]
            }
        
        logger.info(f"AM Bus column: {am_bus_col} (index {am_bus_idx})")
        logger.info(f"PM Bus column: {pm_bus_col} (index {pm_bus_idx})")
        
        # Count updates needed
        updates_needed = []
        rows = list(csv.DictReader(StringIO(original_csv)))
        
        for row_idx, row in enumerate(rows):
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            
            if not first_name or not last_name:
                continue
            
            key = f"{first_name}|{last_name}".lower()
            
            if key in bus_lookup:
                db_am = bus_lookup[key]['am_bus']
                db_pm = bus_lookup[key]['pm_bus']
                sheet_am = row.get(am_bus_col, '').strip()
                sheet_pm = row.get(pm_bus_col, '').strip()
                
                if db_am and db_am != sheet_am:
                    updates_needed.append({
                        'row': row_idx + 2,  # +2 for header and 1-based index
                        'col': am_bus_idx,
                        'name': f"{first_name} {last_name}",
                        'type': 'AM',
                        'from': sheet_am or 'EMPTY',
                        'to': db_am
                    })
                
                if db_pm and db_pm != sheet_pm:
                    updates_needed.append({
                        'row': row_idx + 2,
                        'col': pm_bus_idx,
                        'name': f"{first_name} {last_name}",
                        'type': 'PM',
                        'from': sheet_pm or 'EMPTY',
                        'to': db_pm
                    })
        
        logger.info(f"Found {len(updates_needed)} updates needed")
        
        if not updates_needed:
            return {
                "status": "success",
                "message": "No updates needed - sheet is already in sync",
                "updates_count": 0
            }
        
        # Try to use webhook if available
        webhook_url = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '')
        if webhook_url:
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    # Send updates in batches
                    batch_size = 50
                    success_count = 0
                    
                    for i in range(0, len(updates_needed), batch_size):
                        batch = updates_needed[i:i+batch_size]
                        
                        payload = {
                            'action': 'updateBusAssignments',
                            'updates': [
                                {
                                    'row': u['row'],
                                    'col': u['col'],
                                    'value': u['to']
                                }
                                for u in batch
                            ]
                        }
                        
                        response = await client.post(
                            webhook_url,
                            json=payload,
                            headers={'Content-Type': 'application/json'}
                        )
                        
                        if response.status_code == 200:
                            success_count += len(batch)
                    
                    if success_count > 0:
                        return {
                            "status": "success",
                            "message": f"Updated {success_count} bus assignments in Google Sheet",
                            "updates_count": success_count
                        }
            except Exception as e:
                logger.warning(f"Webhook update failed: {str(e)}")
        
        # Return update information for manual or script-based update
        return {
            "status": "updates_available",
            "message": f"Found {len(updates_needed)} bus assignments that need updating in the Google Sheet",
            "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
            "am_bus_column": am_bus_col,
            "am_bus_column_index": am_bus_idx,
            "pm_bus_column": pm_bus_col,
            "pm_bus_column_index": pm_bus_idx,
            "updates_needed": updates_needed[:100],
            "total_updates": len(updates_needed),
            "instructions": [
                "Option 1: Copy the Google Apps Script below to your sheet",
                "Option 2: Download CSV from /api/export-campers-csv and import",
                "Option 3: Manually update each row in the sheet"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error syncing to sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-changes")
async def detect_bus_assignment_changes():
    """
    Detect changes in bus assignments between database and Google Sheet.
    Identifies:
    - AM bus added (was empty, now has value)
    - PM bus added (was empty, now has value)
    - AM bus removed (had value, now empty)
    - PM bus removed (had value, now empty)
    - AM bus changed (different value)
    - PM bus changed (different value)
    
    After detection, automatically syncs changes to Google Sheet.
    """
    import csv
    from io import StringIO
    
    logger.info("=== DETECTING BUS ASSIGNMENT CHANGES ===")
    
    try:
        # Load database state
        db_campers = await db.campers.find({}).to_list(None)
        
        # Build lookup from database
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
        
        # Load Google Sheet state
        sheet_id = CAMPMINDER_SHEET_ID
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(csv_url)
            csv_content = response.text
        
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        reader = csv.DictReader(StringIO(csv_content))
        
        # Find bus columns
        fieldnames = reader.fieldnames
        am_bus_col = None
        pm_bus_col = None
        
        for col in fieldnames:
            if 'AM Bus' in col and 'Trans' in col:
                am_bus_col = col
            elif 'PM Bus' in col and 'Trans' in col:
                pm_bus_col = col
        
        # Build sheet lookup
        sheet_lookup = {}
        for row in reader:
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            
            if not first_name or not last_name:
                continue
            
            key = f"{first_name}|{last_name}".lower()
            
            sheet_am = row.get(am_bus_col, '').strip() if am_bus_col else ''
            sheet_pm = row.get(pm_bus_col, '').strip() if pm_bus_col else ''
            
            # Normalize NONE values
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
        
        # Detect changes
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
            
            # Check AM changes
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
                logger.info(f"✓ {full_name}: AM bus ADDED ({db_am})")
                
            elif had_am and not has_am:
                changes.append({
                    'name': full_name,
                    'type': 'AM_REMOVED',
                    'old_value': sheet_am,
                    'new_value': 'EMPTY',
                    'message': f"{full_name}: AM bus REMOVED (was {sheet_am})"
                })
                logger.info(f"✓ {full_name}: AM bus REMOVED (was {sheet_am})")
                
            elif had_am and has_am and sheet_am != db_am:
                changes.append({
                    'name': full_name,
                    'type': 'AM_CHANGED',
                    'old_value': sheet_am,
                    'new_value': db_am,
                    'message': f"{full_name}: AM bus CHANGED ({sheet_am} → {db_am})"
                })
                logger.info(f"✓ {full_name}: AM bus CHANGED ({sheet_am} → {db_am})")
            
            # Check PM changes
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
                logger.info(f"✓ {full_name}: PM bus ADDED ({db_pm})")
                
            elif had_pm and not has_pm:
                changes.append({
                    'name': full_name,
                    'type': 'PM_REMOVED',
                    'old_value': sheet_pm,
                    'new_value': 'EMPTY',
                    'message': f"{full_name}: PM bus REMOVED (was {sheet_pm})"
                })
                logger.info(f"✓ {full_name}: PM bus REMOVED (was {sheet_pm})")
                
            elif had_pm and has_pm and sheet_pm != db_pm:
                changes.append({
                    'name': full_name,
                    'type': 'PM_CHANGED',
                    'old_value': sheet_pm,
                    'new_value': db_pm,
                    'message': f"{full_name}: PM bus CHANGED ({sheet_pm} → {db_pm})"
                })
                logger.info(f"✓ {full_name}: PM bus CHANGED ({sheet_pm} → {db_pm})")
        
        # Categorize changes
        am_added = [c for c in changes if c['type'] == 'AM_ADDED']
        pm_added = [c for c in changes if c['type'] == 'PM_ADDED']
        am_removed = [c for c in changes if c['type'] == 'AM_REMOVED']
        pm_removed = [c for c in changes if c['type'] == 'PM_REMOVED']
        am_changed = [c for c in changes if c['type'] == 'AM_CHANGED']
        pm_changed = [c for c in changes if c['type'] == 'PM_CHANGED']
        
        logger.info(f"Total changes detected: {len(changes)}")
        
        # If changes exist, sync to sheet
        sync_result = None
        if changes:
            logger.info("Syncing changes to Google Sheet...")
            # Call the sync endpoint logic
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


@router.post("/refresh-and-sync")
async def refresh_and_sync():
    """
    Complete workflow:
    1. Refresh data from Google Sheet
    2. Detect any bus assignment changes
    3. Auto-assign buses to unassigned campers
    4. Sync all changes back to Google Sheet
    5. Return summary of all operations
    """
    logger.info("=== REFRESH AND SYNC WORKFLOW ===")
    
    results = {
        "step1_refresh": None,
        "step2_detect": None,
        "step3_sync": None,
        "summary": None
    }
    
    try:
        # Step 1: Trigger sync from Google Sheet
        logger.info("Step 1: Refreshing data from Google Sheet...")
        # This loads data from sheet into database
        await auto_sync_campminder()
        results["step1_refresh"] = {"status": "success", "message": "Data refreshed from Google Sheet"}
        
        # Step 2: Detect changes
        logger.info("Step 2: Detecting bus assignment changes...")
        detect_result = await detect_bus_assignment_changes()
        results["step2_detect"] = detect_result
        
        # Step 3: Sync back to sheet
        logger.info("Step 3: Syncing changes back to Google Sheet...")
        sync_result = await sync_bus_assignments_to_sheet()
        results["step3_sync"] = sync_result
        
        # Summary
        results["summary"] = {
            "status": "success",
            "message": "Refresh and sync completed successfully",
            "changes_detected": detect_result.get("total_changes", 0),
            "changes_synced": sync_result.get("updates_count", 0) if isinstance(sync_result, dict) else 0
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Error in refresh and sync: {str(e)}")
        results["summary"] = {"status": "error", "message": str(e)}
        return results


@router.get("/google-apps-script")
async def get_google_apps_script():
    """
    Returns the Google Apps Script code that should be deployed to the Google Sheet
    to enable instant bus assignment updates.
    
    Instructions:
    1. Open your Google Sheet
    2. Extensions > Apps Script
    3. Paste this code
    4. Deploy as Web App (execute as yourself, allow anyone)
    5. Copy the deployment URL to GOOGLE_SHEETS_WEBHOOK_URL in .env
    """
    
    script = '''
// Google Apps Script for Bus Route Management
// Deploy this as a Web App to enable instant updates from the bus routing system

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);
    
    if (data.action === 'updateBusAssignments') {
      // Batch update bus assignments
      var updates = data.updates || [];
      var updatedCount = 0;
      
      for (var i = 0; i < updates.length; i++) {
        var update = updates[i];
        if (update.row && update.col && update.value) {
          sheet.getRange(update.row, update.col).setValue(update.value);
          updatedCount++;
        }
      }
      
      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        message: 'Updated ' + updatedCount + ' cells',
        count: updatedCount
      })).setMimeType(ContentService.MimeType.JSON);
      
    } else if (data.action === 'updateSingleCamper') {
      // Update a single camper's bus assignment
      var firstName = data.first_name;
      var lastName = data.last_name;
      var amBus = data.am_bus_number || '';
      var pmBus = data.pm_bus_number || '';
      
      // Find the row with this camper
      var dataRange = sheet.getDataRange();
      var values = dataRange.getValues();
      var headers = values[0];
      
      // Find column indices
      var firstNameCol = headers.indexOf('First Name');
      var lastNameCol = headers.indexOf('Last Name');
      var amBusCol = -1;
      var pmBusCol = -1;
      
      for (var h = 0; h < headers.length; h++) {
        if (headers[h].toString().indexOf('AM Bus') > -1 && headers[h].toString().indexOf('Trans') > -1) {
          amBusCol = h;
        }
        if (headers[h].toString().indexOf('PM Bus') > -1 && headers[h].toString().indexOf('Trans') > -1) {
          pmBusCol = h;
        }
      }
      
      if (firstNameCol < 0 || lastNameCol < 0 || amBusCol < 0 || pmBusCol < 0) {
        return ContentService.createTextOutput(JSON.stringify({
          success: false,
          message: 'Could not find required columns'
        })).setMimeType(ContentService.MimeType.JSON);
      }
      
      // Find and update the camper row
      for (var row = 1; row < values.length; row++) {
        if (values[row][firstNameCol] === firstName && values[row][lastNameCol] === lastName) {
          if (amBus) {
            sheet.getRange(row + 1, amBusCol + 1).setValue(amBus);
          }
          if (pmBus) {
            sheet.getRange(row + 1, pmBusCol + 1).setValue(pmBus);
          }
          
          return ContentService.createTextOutput(JSON.stringify({
            success: true,
            message: 'Updated ' + firstName + ' ' + lastName,
            row: row + 1
          })).setMimeType(ContentService.MimeType.JSON);
        }
      }
      
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        message: 'Camper not found: ' + firstName + ' ' + lastName
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      message: 'Unknown action'
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: 'ok',
    message: 'Bus Route Sheet Webhook is running'
  })).setMimeType(ContentService.MimeType.JSON);
}

// Test function - run this to verify the script works
function testScript() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  
  Logger.log('Headers found: ' + headers.join(', '));
  
  var amBusCol = -1;
  var pmBusCol = -1;
  
  for (var h = 0; h < headers.length; h++) {
    if (headers[h].toString().indexOf('AM Bus') > -1) {
      amBusCol = h + 1;
      Logger.log('AM Bus column: ' + amBusCol + ' (' + headers[h] + ')');
    }
    if (headers[h].toString().indexOf('PM Bus') > -1) {
      pmBusCol = h + 1;
      Logger.log('PM Bus column: ' + pmBusCol + ' (' + headers[h] + ')');
    }
  }
  
  Logger.log('Script is ready to use!');
}
'''
    
    return {
        "status": "success",
        "script": script,
        "instructions": [
            "1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k/edit",
            "2. Go to Extensions > Apps Script",
            "3. Delete any existing code and paste the script above",
            "4. Save the project (Ctrl+S)",
            "5. Click 'Deploy' > 'New deployment'",
            "6. Select 'Web app' as the type",
            "7. Set 'Execute as' to 'Me'",
            "8. Set 'Who has access' to 'Anyone'",
            "9. Click 'Deploy' and authorize when prompted",
            "10. Copy the Web App URL",
            "11. Update GOOGLE_SHEETS_WEBHOOK_URL in the backend .env file with this URL"
        ]
    }



