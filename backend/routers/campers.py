"""Camper management endpoints."""

import os
import logging
import urllib.parse
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from io import StringIO
import csv

import httpx
from fastapi import APIRouter, HTTPException

from services.database import db, campminder_api, route_optimizer, GOOGLE_SHEETS_WEBHOOK_URL
from services.helpers import get_active_season_id
from services.geocoding import geocode_address_cached
from services.bus_utils import get_bus_color
from models.schemas import GeoLocation, CamperPin, ManualCamperInput
from sibling_offset import apply_sibling_offset

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Campers"])

db_connected = False

@router.get("/campers")
async def get_campers(season_id: Optional[str] = None):
    global db_connected
    try:
        # Get active season if no season_id provided
        if not season_id:
            active_season = await db.seasons.find_one({"is_active": True})
            if active_season:
                season_id = str(active_season["_id"])
        
        # Build query - filter by season if we have one
        query = {
            "location.latitude": {"$ne": 0.0},
            "$or": [
                {"am_bus_number": {"$regex": "^Bus"}},
                {"pm_bus_number": {"$regex": "^Bus"}}
            ]
        }
        
        if season_id:
            query["season_id"] = season_id
        
        # Return campers with valid locations and at least one valid bus assignment
        existing_campers = await asyncio.wait_for(
            db.campers.find(query).to_list(None),
            timeout=30.0  # 30 second timeout
        )
        
        db_connected = True
        
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
                "session_type": camper.get('session_type', ''),
                "pickup_type": camper.get('pickup_type', ''),
                "pickup_dropoff": camper.get('pickup_dropoff', ''),
                "address": camper.get('address', ''),
                "town": camper.get('town', ''),
                "zip_code": camper.get('zip_code', ''),
                "season_id": camper.get('season_id', ''),
                "personID": camper.get('personID', None)
            }
            result.append(camper_dict)
        
        return result
    except asyncio.TimeoutError:
        logging.error("Timeout fetching campers - database may be slow or unavailable")
        raise HTTPException(status_code=503, detail="Database timeout - please try again")
    except Exception as e:
        logging.error(f"Error fetching campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/campers/needs-address")
async def get_campers_needing_address():
    """Get campers who have bus assignments but no address in the active season"""
    try:
        query = {
            "location.latitude": 0.0,
            "$or": [
                {"am_bus_number": {"$exists": True, "$regex": "^Bus"}},
                {"pm_bus_number": {"$exists": True, "$regex": "^Bus"}}
            ]
        }
        
        # Filter by active season
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id
        
        campers = await db.campers.find(query).to_list(None)
        
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

@router.post("/campers/add")
async def add_camper_manually(camper: ManualCamperInput):
    """Manually add a camper to the map"""
    try:
        # Geocode the address (using cached version)
        location = await geocode_address_cached(camper.address, camper.town, camper.zip_code)
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
        
        # Get active season
        season_id = await get_active_season_id()
        
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
            "season_id": season_id,  # Add season_id
            "created_at": datetime.now(timezone.utc),
            "manually_added": True
        }
        
        result = await db.campers.replace_one({"_id": camper_id}, camper_doc, upsert=True)
        
        # Trigger instant update to Google Sheet for this camper
        webhook_url = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '')
        if webhook_url and am_bus != "NONE":
            try:
                payload = {
                    "action": "update_camper",
                    "first_name": camper.first_name,
                    "last_name": camper.last_name,
                    "am_bus": am_bus,
                    "pm_bus": pm_bus
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(webhook_url, json=payload)
                    logger.info(f"✓ Google Sheet updated instantly for {camper.first_name} {camper.last_name}")
            except Exception as e:
                logger.warning(f"Failed to update sheet instantly: {str(e)}")
        
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
@router.delete("/campers/{camper_id}")
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
@router.get("/campers/filter")
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

@router.get("/reports/missing-addresses")
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

@router.post("/campers/{camper_id}/change-bus")
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
            # INSTANTLY update Google Sheet via webhook (using GET with query params)
            # HARDCODED URL to avoid environment variable caching issues in production
            webhook_url = "https://script.google.com/macros/s/AKfycbw8JoFhHDgyigOLy8Y6jbKxC-dB-x_FivZHVTsI29fUzcRZmJ--dz3EmpVkTOEWXSkn/exec"
            print(f"=== WEBHOOK DEBUG ===")
            print(f"Using hardcoded webhook URL")
            
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    # Always send BOTH AM and PM bus numbers to keep sheet in sync
                    am_bus_to_send = updates.get('am_bus_number') if updates.get('am_bus_number') else camper.get('am_bus_number', '')
                    pm_bus_to_send = updates.get('pm_bus_number') if updates.get('pm_bus_number') else camper.get('pm_bus_number', '')
                    
                    params = {
                        "action": "updateBus",
                        "first_name": camper.get('first_name', '').strip(),
                        "last_name": camper.get('last_name', '').strip(),
                        "am_bus_number": am_bus_to_send,
                        "pm_bus_number": pm_bus_to_send
                    }
                    
                    print(f"Sending webhook with params: {params}")
                    response = await client.get(webhook_url, params=params)
                    print(f"Webhook response: {response.status_code} - {response.text[:300]}")
                    
                    if response.status_code == 200:
                        logger.info(f"✓ Google Sheet updated for {camper.get('first_name')} {camper.get('last_name')}: {response.text[:200]}")
                    else:
                        logger.warning(f"Webhook response: {response.status_code} - {response.text[:200]}")
            except Exception as e:
                print(f"WEBHOOK ERROR: {str(e)}")
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

