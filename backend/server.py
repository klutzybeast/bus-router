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
from services.sync_engine import auto_sync_campminder

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
