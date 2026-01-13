"""Camper CRUD operations router."""

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from models.schemas import ManualCamperInput, GeoLocation, CamperPin
from services.database import db
from services.bus_utils import get_bus_color
from services.geocoding import geocode_address
from io import StringIO
import csv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Campers"])


@router.get("/campers")
async def get_campers():
    """Get all campers with valid locations and bus assignments."""
    try:
        existing_campers = await db.campers.find({
            "location.latitude": {"$ne": 0.0},
            "$or": [
                {"am_bus_number": {"$regex": "^Bus"}},
                {"pm_bus_number": {"$regex": "^Bus"}}
            ]
        }).to_list(None)
        
        result = []
        for camper in existing_campers:
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            if am_bus == 'NONE' or not am_bus.startswith('Bus'):
                am_bus = ''
            if pm_bus == 'NONE' or not pm_bus.startswith('Bus'):
                pm_bus = ''
            
            if not am_bus and not pm_bus:
                continue
            
            camper_dict = {
                "_id": str(camper['_id']),
                "first_name": camper.get('first_name', ''),
                "last_name": camper.get('last_name', ''),
                "location": camper.get('location', {}),
                "am_bus_number": am_bus,
                "pm_bus_number": pm_bus,
                "bus_number": am_bus or pm_bus,
                "bus_color": camper.get('bus_color', ''),
                "session": camper.get('session', ''),
                "pickup_type": camper.get('pickup_type', ''),
                "town": camper.get('town', ''),
                "zip_code": camper.get('zip_code', '')
            }
            result.append(camper_dict)
        
        return result
    except Exception as e:
        logger.error(f"Error fetching campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campers/needs-address")
async def get_campers_needing_address():
    """Get campers who have bus assignments but no address."""
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
        logger.error(f"Error fetching campers needing address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campers/add")
async def add_camper_manually(camper: ManualCamperInput):
    """Manually add a camper to the map."""
    try:
        location = geocode_address(camper.address, camper.town, camper.zip_code)
        if not location:
            raise HTTPException(status_code=400, detail=f"Could not geocode address: {camper.address}, {camper.town}, {camper.zip_code}")
        
        camper_id = f"{camper.last_name}_{camper.first_name}_{camper.zip_code}".replace(' ', '_')
        
        existing_at_address = await db.campers.count_documents({
            "location.latitude": {"$gte": location.latitude - 0.001, "$lte": location.latitude + 0.001},
            "location.longitude": {"$gte": location.longitude - 0.001, "$lte": location.longitude + 0.001}
        })
        offset = existing_at_address * 0.00002
        
        am_bus = camper.am_bus_number if camper.am_bus_number else "NONE"
        pm_bus = camper.pm_bus_number if camper.pm_bus_number else am_bus
        
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
        logger.error(f"Error adding camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/campers/{camper_id}")
async def delete_camper(camper_id: str):
    """Delete a camper from the database."""
    try:
        decoded_id = urllib.parse.unquote(camper_id)
        
        result = await db.campers.delete_one({"_id": decoded_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Camper not found")
        
        await db.campers.delete_many({"_id": {"$regex": f"^{decoded_id}_PM"}})
        
        return {"success": True, "message": "Camper deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campers/filter")
async def filter_campers(bus_number: str = None, session: str = None, pickup_type: str = None):
    """Filter campers by various criteria."""
    try:
        query = {}
        
        if bus_number:
            query["$or"] = [
                {"am_bus_number": bus_number},
                {"pm_bus_number": bus_number}
            ]
        
        if session:
            query["session"] = {"$regex": session, "$options": "i"}
        
        if pickup_type:
            query["pickup_type"] = pickup_type
        
        campers = await db.campers.find(query).to_list(None)
        
        result = []
        for camper in campers:
            result.append({
                "_id": str(camper['_id']),
                "first_name": camper.get('first_name', ''),
                "last_name": camper.get('last_name', ''),
                "am_bus_number": camper.get('am_bus_number', ''),
                "pm_bus_number": camper.get('pm_bus_number', ''),
                "session": camper.get('session', ''),
                "pickup_type": camper.get('pickup_type', '')
            })
        
        return result
    except Exception as e:
        logger.error(f"Error filtering campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campers/{camper_id}/change-bus")
async def change_camper_bus(camper_id: str, am_bus_number: str = None, pm_bus_number: str = None):
    """Change a camper's bus assignment and sync to Google Sheet."""
    import httpx
    import os
    
    try:
        decoded_id = urllib.parse.unquote(camper_id)
        
        camper = await db.campers.find_one({"_id": decoded_id})
        if not camper:
            raise HTTPException(status_code=404, detail="Camper not found")
        
        updates = {}
        
        if am_bus_number:
            updates["am_bus_number"] = am_bus_number
            updates["bus_color"] = get_bus_color(am_bus_number)
        
        if pm_bus_number:
            updates["pm_bus_number"] = pm_bus_number
            if not am_bus_number:
                updates["bus_color"] = get_bus_color(pm_bus_number)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No bus number provided")
        
        await db.campers.update_one({"_id": decoded_id}, {"$set": updates})
        
        # Also update any PM-specific entries for this camper
        if pm_bus_number:
            base_id = decoded_id.replace('_PM', '')
            await db.campers.update_many(
                {"_id": {"$regex": f"^{base_id}_PM"}},
                {"$set": {"pm_bus_number": pm_bus_number, "bus_color": get_bus_color(pm_bus_number)}}
            )
        
        # Sync to Google Sheet via webhook
        webhook_url = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '')
        if webhook_url:
            try:
                first_name = camper.get('first_name', '')
                last_name = camper.get('last_name', '')
                
                payload = {
                    "action": "update_camper",
                    "first_name": first_name,
                    "last_name": last_name,
                    "am_bus": am_bus_number if am_bus_number else camper.get('am_bus_number', ''),
                    "pm_bus": pm_bus_number if pm_bus_number else camper.get('pm_bus_number', '')
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(webhook_url, json=payload)
                    logger.info(f"Webhook response for {first_name} {last_name}: {response.status_code}")
            except Exception as e:
                logger.warning(f"Failed to sync to sheet: {str(e)}")
        
        return {
            "success": True,
            "camper_id": decoded_id,
            "updated": updates
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing bus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/missing-addresses")
async def get_missing_addresses_report():
    """Get a report of all campers missing addresses."""
    try:
        campers = await db.campers.find({
            "$or": [
                {"location.latitude": 0.0},
                {"location.latitude": {"$exists": False}},
                {"location": {"$exists": False}}
            ]
        }).to_list(None)
        
        result = []
        for camper in campers:
            result.append({
                "name": f"{camper.get('first_name', '')} {camper.get('last_name', '')}",
                "am_bus": camper.get('am_bus_number', ''),
                "pm_bus": camper.get('pm_bus_number', ''),
                "session": camper.get('session', ''),
                "town": camper.get('town', ''),
                "zip_code": camper.get('zip_code', '')
            })
        
        return {
            "status": "success",
            "count": len(result),
            "campers": result
        }
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
