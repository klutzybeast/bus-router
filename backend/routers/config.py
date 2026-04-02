"""Health check, configuration, and status endpoints."""

import os
import logging
import asyncio

from fastapi import APIRouter

from services.database import db, is_atlas
from services.geocoding import get_geocode_memory_cache_size

logger = logging.getLogger(__name__)

db_connected = False

router = APIRouter(tags=["Config"])


@router.get("/")
async def root():
    return {"message": "Bus Routing API", "status": "running"}


@router.get("/health")
async def api_health_check():
    """Health check endpoint for API"""
    return {"status": "healthy", "service": "bus-routing-api"}


@router.get("/geocode-cache-stats")
async def get_geocode_cache_stats():
    """Get statistics about the geocoding cache"""
    try:
        total_cached = await db.geocode_cache.count_documents({})
        google_cached = await db.geocode_cache.count_documents({"source": "google"})
        positionstack_cached = await db.geocode_cache.count_documents({"source": "positionstack"})
        memory_cache_size = get_geocode_memory_cache_size()

        return {
            "status": "success",
            "total_cached_addresses": total_cached,
            "by_source": {
                "google": google_cached,
                "positionstack": positionstack_cached
            },
            "memory_cache_size": memory_cache_size,
            "message": f"Cache has {total_cached} addresses. New addresses will use Google first, PositionStack as backup."
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/config-check")
async def config_check():
    """Check if critical environment variables are configured"""
    webhook_url = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '')
    return {
        "webhook_configured": bool(webhook_url),
        "webhook_url_preview": webhook_url[:50] + "..." if len(webhook_url) > 50 else webhook_url if webhook_url else "NOT SET",
        "positionstack_configured": bool(os.environ.get('POSITIONSTACK_API_KEY', '')),
        "google_maps_configured": bool(os.environ.get('GOOGLE_MAPS_API_KEY', ''))
    }


@router.get("/db-status")
async def api_db_status():
    """Check database connection status"""
    global db_connected
    if db is None:
        return {"status": "error", "error": "Database not configured"}
    try:
        await asyncio.wait_for(db.command('ping'), timeout=10.0)
        camper_count = await asyncio.wait_for(db.campers.count_documents({}), timeout=10.0)
        db_connected = True
        return {
            "status": "connected",
            "camper_count": camper_count,
            "db_type": "atlas" if is_atlas else "local"
        }
    except asyncio.TimeoutError:
        db_connected = False
        return {"status": "timeout", "error": "Database connection timed out"}
    except Exception as e:
        db_connected = False
        return {"status": "error", "error": str(e)}
