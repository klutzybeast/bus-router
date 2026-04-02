"""Bus zone management endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from services.database import db
from services.helpers import get_active_season_id
from models.schemas import BusZoneCreate, BusZoneUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Zones"])


@router.get("/bus-zones")
async def get_bus_zones():
    """Get all user-defined bus zones for the active season"""
    try:
        query = {}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id

        zones = await db.bus_zones.find(query).to_list(None)
        result = []
        for zone in zones:
            result.append({
                "id": str(zone.get("_id", "")),
                "bus_number": zone.get("bus_number"),
                "points": zone.get("points", []),
                "name": zone.get("name", ""),
                "color": zone.get("color", ""),
                "created_at": zone.get("created_at"),
                "updated_at": zone.get("updated_at")
            })
        return {"zones": result}
    except Exception as e:
        logging.error(f"Error getting bus zones: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-zones/{bus_number}")
async def get_bus_zone(bus_number: str):
    """Get zone for a specific bus in the active season"""
    try:
        query = {"bus_number": bus_number}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id

        zone = await db.bus_zones.find_one(query)
        if not zone:
            return {"zone": None}
        return {
            "zone": {
                "id": str(zone.get("_id", "")),
                "bus_number": zone.get("bus_number"),
                "points": zone.get("points", []),
                "name": zone.get("name", ""),
                "color": zone.get("color", ""),
                "created_at": zone.get("created_at"),
                "updated_at": zone.get("updated_at")
            }
        }
    except Exception as e:
        logging.error(f"Error getting bus zone: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bus-zones")
async def create_bus_zone(zone_data: BusZoneCreate):
    """Create a new bus zone (one zone per bus per season)"""
    try:
        season_id = await get_active_season_id()

        existing_query = {"bus_number": zone_data.bus_number}
        if season_id:
            existing_query["season_id"] = season_id

        existing = await db.bus_zones.find_one(existing_query)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Zone already exists for {zone_data.bus_number}. Use PUT to update."
            )

        zone_doc = {
            "bus_number": zone_data.bus_number,
            "points": [{"lat": p.lat, "lng": p.lng} for p in zone_data.points],
            "name": zone_data.name or f"{zone_data.bus_number} Zone",
            "color": zone_data.color or "",
            "season_id": season_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        result = await db.bus_zones.insert_one(zone_doc)
        zone_doc["id"] = str(result.inserted_id)
        if "_id" in zone_doc:
            del zone_doc["_id"]

        return {"status": "success", "zone": zone_doc}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating bus zone: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/bus-zones/{bus_number}")
async def update_bus_zone(bus_number: str, zone_data: BusZoneUpdate):
    """Update an existing bus zone"""
    try:
        query = {"bus_number": bus_number}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id

        existing = await db.bus_zones.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail=f"No zone found for {bus_number}")

        update_doc = {"updated_at": datetime.now(timezone.utc).isoformat()}

        if zone_data.points is not None:
            update_doc["points"] = [{"lat": p.lat, "lng": p.lng} for p in zone_data.points]
        if zone_data.name is not None:
            update_doc["name"] = zone_data.name
        if zone_data.color is not None:
            update_doc["color"] = zone_data.color

        await db.bus_zones.update_one(query, {"$set": update_doc})

        updated = await db.bus_zones.find_one(query)
        return {
            "status": "success",
            "zone": {
                "id": str(updated.get("_id", "")),
                "bus_number": updated.get("bus_number"),
                "points": updated.get("points", []),
                "name": updated.get("name", ""),
                "color": updated.get("color", ""),
                "created_at": updated.get("created_at"),
                "updated_at": updated.get("updated_at")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating bus zone: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bus-zones/{bus_number}")
async def delete_bus_zone(bus_number: str):
    """Delete a bus zone from the active season"""
    try:
        query = {"bus_number": bus_number}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id

        result = await db.bus_zones.delete_one(query)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No zone found for {bus_number}")
        return {"status": "success", "message": f"Zone for {bus_number} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting bus zone: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
