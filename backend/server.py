"""Bus Routing Application - Main Server Entry Point.

This is the lean application setup file. All route handlers have been
modularized into individual router files under /routers/.
"""

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

# Load environment early
from dotenv import load_dotenv
load_dotenv()

# Shared services and config
from services.database import (
    db, client, is_atlas, route_optimizer,
    campminder_api, CAMPMINDER_SHEET_ID,
    AUTO_SYNC_ENABLED, SYNC_INTERVAL_MINUTES
)
from services.geocoding import geocode_address_cached
from services.bus_utils import get_bus_color
from models.schemas import GeoLocation
from sibling_offset import apply_sibling_offset

# Router imports
from routers import (
    config as config_router,
    seasons as seasons_router,
    campers as campers_router,
    tracking as tracking_router,
    shadows as shadows_router,
    zones as zones_router,
    buses as buses_router,
    audit as audit_router,
    staff as staff_router,
    sheets as sheets_router,
    roster as roster_router,
    sync as sync_router,
)

logger = logging.getLogger(__name__)

# Sync state
sync_task = None
last_sync_time = None
db_connected = False


# ============================================
# AUTO-SYNC FUNCTION (kept in server.py for lifecycle management)
# ============================================

async def auto_sync_campminder():
    """Background task to auto-sync from Google Sheets - handles ADD, UPDATE, DELETE."""
    global last_sync_time

    logger.info("Starting auto-sync from CampMinder Google Sheet...")

    try:
        sheet_id = CAMPMINDER_SHEET_ID
        if not sheet_id:
            logger.error("No CAMPMINDER_SHEET_ID configured")
            return

        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
            response = await http_client.get(csv_url)

            if response.status_code != 200:
                logger.error(f"Failed to download Google Sheet: {response.status_code}")
                return

            csv_content = response.text
            logger.info(f"Downloaded CSV from Google Sheets ({len(csv_content)} chars)")

        from io import StringIO
        import csv

        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]

        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)

        sheet_camper_ids = set()
        new_count = 0
        updated_count = 0

        active_season = await db.seasons.find_one({"is_active": True})
        sync_season_id = str(active_season["_id"]) if active_season else None

        existing_routes = None

        async def get_existing_routes():
            nonlocal existing_routes
            if existing_routes is not None:
                return existing_routes
            all_db_campers = await db.campers.find({"am_bus_number": {"$exists": True}}).to_list(None)
            existing_routes = {}
            for ec in all_db_campers:
                bus_str = ec.get('am_bus_number', '') or ec.get('pm_bus_number', '')
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
            return existing_routes

        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '').strip()
            pm_method = row.get('Trans-PMDismissalMethod', '').strip()

            am_needs_bus = 'am bus' in am_method.lower()
            pm_needs_bus = 'pm bus' in pm_method.lower()

            if not am_needs_bus and not pm_needs_bus:
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

            if not am_needs_bus:
                am_bus = 'NONE'
            if not pm_needs_bus:
                pm_bus = 'NONE'

            is_pm_only_camper = not am_needs_bus and pm_needs_bus

            final_am_bus = None
            final_pm_bus = None

            if am_needs_bus:
                if am_bus and am_bus.strip() and 'NONE' not in am_bus.upper():
                    final_am_bus = am_bus.strip()
                elif am_address.strip():
                    routes = await get_existing_routes()
                    location_temp = await geocode_address_cached(am_address, am_town, am_zip)
                    if location_temp:
                        optimal_bus = route_optimizer.find_optimal_bus(
                            {'lat': location_temp.latitude, 'lng': location_temp.longitude},
                            routes
                        )
                        final_am_bus = f"Bus #{optimal_bus:02d}"
                        logger.info(f"AUTO-ASSIGNED (new): {first_name} {last_name} -> {final_am_bus}")

                        is_am_only = am_needs_bus and not pm_needs_bus
                        sync_pm_bus = "NONE" if is_am_only else final_am_bus

                        try:
                            webhook_url = "https://script.google.com/macros/s/AKfycbw8JoFhHDgyigOLy8Y6jbKxC-dB-x_FivZHVTsI29fUzcRZmJ--dz3EmpVkTOEWXSkn/exec"
                            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as webhook_client:
                                params = {
                                    "action": "updateBus",
                                    "first_name": first_name.strip(),
                                    "last_name": last_name.strip(),
                                    "am_bus_number": final_am_bus,
                                    "pm_bus_number": sync_pm_bus
                                }
                                await webhook_client.get(webhook_url, params=params)
                        except Exception as we:
                            logger.warning(f"Failed to sync auto-assignment to sheet: {str(we)}")
            else:
                final_am_bus = "NONE"

            if pm_needs_bus:
                if pm_bus and pm_bus.strip() and 'NONE' not in pm_bus.upper():
                    final_pm_bus = pm_bus.strip()
                elif final_am_bus and final_am_bus != "NONE":
                    final_pm_bus = final_am_bus
                else:
                    auto_assign_address = pm_address.strip() or am_address.strip()
                    auto_assign_town = pm_town.strip() or am_town.strip()
                    auto_assign_zip = pm_zip.strip() or am_zip.strip()

                    if auto_assign_address:
                        routes = await get_existing_routes()
                        location_temp = await geocode_address_cached(auto_assign_address, auto_assign_town, auto_assign_zip)
                        if location_temp:
                            optimal_bus = route_optimizer.find_optimal_bus(
                                {'lat': location_temp.latitude, 'lng': location_temp.longitude},
                                routes
                            )
                            final_pm_bus = f"Bus #{optimal_bus:02d}"
                            logger.info(f"AUTO-ASSIGNED PM (PM-only): {first_name} {last_name} -> {final_pm_bus}")

                            try:
                                webhook_url = "https://script.google.com/macros/s/AKfycbw8JoFhHDgyigOLy8Y6jbKxC-dB-x_FivZHVTsI29fUzcRZmJ--dz3EmpVkTOEWXSkn/exec"
                                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as webhook_client:
                                    params = {
                                        "action": "updateBus",
                                        "first_name": first_name.strip(),
                                        "last_name": last_name.strip(),
                                        "am_bus_number": "NONE",
                                        "pm_bus_number": final_pm_bus
                                    }
                                    await webhook_client.get(webhook_url, params=params)
                            except Exception as we:
                                logger.warning(f"Failed to sync PM auto-assignment: {str(we)}")
                        else:
                            final_pm_bus = "NONE"
                    else:
                        final_pm_bus = "NONE"
            else:
                final_pm_bus = "NONE"

            if final_pm_bus and any(x in final_pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM']):
                final_pm_bus = "NONE"

            effective_address = am_address.strip() if am_needs_bus else pm_address.strip()
            effective_town = am_town.strip() if am_needs_bus else pm_town.strip()
            effective_zip = am_zip.strip() if am_needs_bus else pm_zip.strip()

            if not effective_address:
                effective_address = pm_address.strip() or am_address.strip()
                effective_town = pm_town.strip() or am_town.strip()
                effective_zip = pm_zip.strip() or am_zip.strip()

            has_any_bus = (final_am_bus and final_am_bus != "NONE") or (final_pm_bus and final_pm_bus != "NONE")

            if not effective_address and not has_any_bus:
                continue

            if am_needs_bus and pm_needs_bus:
                pickup_type_val = "AM & PM"
            elif am_needs_bus:
                pickup_type_val = "AM Pickup Only"
            elif pm_needs_bus:
                pickup_type_val = "PM Drop-off Only"
            else:
                pickup_type_val = "Unknown"

            pm_final_address = pm_address if pm_address.strip() else am_address
            pm_final_town = pm_town if pm_town.strip() else am_town
            pm_final_zip = pm_zip if pm_zip.strip() else am_zip

            id_zip = effective_zip if effective_zip else "NOADDR"
            camper_id = f"{last_name}_{first_name}_{id_zip}".replace(' ', '_')
            sheet_camper_ids.add(camper_id)

            if effective_address:
                location = await geocode_address_cached(effective_address, effective_town, effective_zip)
                if not location:
                    location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {effective_address}")
                    logger.warning(f"Geocoding failed: {first_name} {last_name} - {effective_address}")

                existing_at_address = await db.campers.count_documents({
                    "location.latitude": {"$gte": location.latitude - 0.001, "$lte": location.latitude + 0.001},
                    "location.longitude": {"$gte": location.longitude - 0.001, "$lte": location.longitude + 0.001}
                })

                offset = existing_at_address * 0.00002

                if pickup_type_val == "PM Drop-off Only":
                    bus_color = get_bus_color(final_pm_bus) if final_pm_bus != "NONE" else "#808080"
                elif final_am_bus == "NONE":
                    bus_color = "#808080"
                else:
                    bus_color = get_bus_color(final_am_bus)

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
                    "season_id": sync_season_id,
                    "created_at": datetime.now(timezone.utc)
                }

                result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
                if result.upserted_id:
                    new_count += 1
                elif result.modified_count > 0:
                    updated_count += 1
            else:
                if is_pm_only_camper and final_pm_bus and final_pm_bus != "NONE":
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
                    "season_id": sync_season_id,
                    "created_at": datetime.now(timezone.utc)
                }
                result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
                if result.upserted_id:
                    new_count += 1

            has_different_pm_address = pm_final_address.strip() and pm_final_address != am_address
            if has_different_pm_address and am_needs_bus and pm_needs_bus:
                camper_id_pm = f"{last_name}_{first_name}_{pm_zip}_PM".replace(' ', '_')
                sheet_camper_ids.add(camper_id_pm)

                pm_location = await geocode_address_cached(pm_final_address, pm_final_town, pm_final_zip)
                if not pm_location:
                    pm_location = GeoLocation(latitude=0.0, longitude=0.0, address=f"GEOCODING FAILED: {pm_final_address}")

                existing_at_pm = await db.campers.count_documents({
                    "location.latitude": {"$gte": pm_location.latitude - 0.001, "$lte": pm_location.latitude + 0.001},
                    "location.longitude": {"$gte": pm_location.longitude - 0.001, "$lte": pm_location.longitude + 0.001}
                })

                pm_offset = existing_at_pm * 0.00008

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
                    "season_id": sync_season_id,
                    "created_at": datetime.now(timezone.utc)
                }
                result = await db.campers.replace_one({"_id": camper_id_pm}, camper_doc_pm, upsert=True)
                if result.upserted_id:
                    new_count += 1
                elif result.modified_count > 0:
                    updated_count += 1

        # Delete campers no longer in sheet
        delete_query = {}
        if sync_season_id:
            delete_query["season_id"] = sync_season_id
        all_db_campers = await db.campers.find(delete_query).to_list(None)
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
    """Continuous sync loop with retry logic."""
    global last_sync_time, db_connected

    if db is None:
        logger.error("Database not configured - sync loop disabled")
        return

    logger.info("Waiting 30 seconds before first sync to allow MongoDB Atlas connection...")
    await asyncio.sleep(30)

    retry_count = 0
    max_retries = 5
    base_delay = 15

    while True:
        try:
            logger.info("Testing database connection...")
            await asyncio.wait_for(db.command('ping'), timeout=30.0)
            db_connected = True
            logger.info("Database connection verified, starting sync...")
            await auto_sync_campminder()
            retry_count = 0
            logger.info("Sync completed successfully")
        except asyncio.TimeoutError:
            retry_count += 1
            db_connected = False
            logger.error(f"Database connection timeout (attempt {retry_count}/{max_retries})")

            if retry_count >= max_retries:
                logger.warning("Max retries reached, waiting 5 minutes...")
                await asyncio.sleep(300)
                retry_count = 0
            else:
                delay = base_delay * (2 ** retry_count)
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                continue
        except Exception as e:
            retry_count += 1
            logger.error(f"Error in sync loop (attempt {retry_count}/{max_retries}): {str(e)}")

            if retry_count >= max_retries:
                logger.warning("Max retries reached, waiting 5 minutes...")
                await asyncio.sleep(300)
                retry_count = 0
            else:
                delay = base_delay * (2 ** retry_count)
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                continue

        await asyncio.sleep(SYNC_INTERVAL_MINUTES * 60)


# ============================================
# APP LIFECYCLE
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_task

    try:
        logger.info("Checking season data migration...")
        active_season = await db.seasons.find_one({"is_active": True})

        if not active_season:
            current_year = datetime.now().year
            new_season = {
                "_id": str(uuid.uuid4()),
                "name": f"{current_year} Bus Route Management",
                "year": current_year,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "archived_at": None
            }
            await db.seasons.insert_one(new_season)
            active_season = new_season
            logger.info(f"Created default season: {new_season['name']}")

        season_id = active_season["_id"]

        collections_to_migrate = ['campers', 'shadows', 'bus_zones', 'bus_staff', 'bus_assigned_staff']
        for collection_name in collections_to_migrate:
            collection = db[collection_name]
            result = await collection.update_many(
                {"$or": [
                    {"season_id": {"$exists": False}},
                    {"season_id": None}
                ]},
                {"$set": {"season_id": season_id}}
            )
            if result.modified_count > 0:
                logger.info(f"Migrated {result.modified_count} {collection_name} to season {str(season_id)[:8]}...")

        logger.info("Season data migration complete")
    except Exception as e:
        logger.error(f"Error during season migration: {e}")

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


# ============================================
# APP CREATION & ROUTER REGISTRATION
# ============================================

app = FastAPI(lifespan=lifespan)

# Create the main /api prefix router
api_router = APIRouter(prefix="/api")

# Include all modular routers
api_router.include_router(config_router.router)
api_router.include_router(seasons_router.router)
api_router.include_router(campers_router.router)
api_router.include_router(sync_router.router)
api_router.include_router(sheets_router.router)
api_router.include_router(staff_router.router)
api_router.include_router(shadows_router.router)
api_router.include_router(zones_router.router)
api_router.include_router(buses_router.router)
api_router.include_router(audit_router.router)
api_router.include_router(roster_router.router)
api_router.include_router(tracking_router.router)

app.include_router(api_router)


# ============================================
# APP-LEVEL ENDPOINTS (outside /api prefix)
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes liveness/readiness probes"""
    return {"status": "healthy"}


@app.get("/db-status")
async def db_status():
    """Check database connection status"""
    try:
        await asyncio.wait_for(db.command('ping'), timeout=10.0)
        camper_count = await asyncio.wait_for(db.campers.count_documents({}), timeout=10.0)
        return {
            "status": "connected",
            "database": os.environ.get('DB_NAME', 'unknown'),
            "camper_count": camper_count,
            "mongo_url_type": "atlas" if is_atlas else "local"
        }
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "error": "Database connection timed out after 10 seconds",
            "mongo_url_type": "atlas" if is_atlas else "local"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "mongo_url_type": "atlas" if is_atlas else "local"
        }


@app.post("/force-sync")
async def force_sync():
    """Force a sync from Google Sheets"""
    try:
        await asyncio.wait_for(db.command('ping'), timeout=10.0)
        await auto_sync_campminder()
        camper_count = await db.campers.count_documents({})
        return {"status": "success", "message": "Sync completed", "camper_count": camper_count}
    except asyncio.TimeoutError:
        return {"status": "error", "error": "Database connection timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e), "error_type": type(e).__name__}


# ============================================
# CORS MIDDLEWARE
# ============================================

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
