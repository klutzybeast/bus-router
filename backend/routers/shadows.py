"""Shadow staff management endpoints."""

import logging
import urllib.parse
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from services.database import db
from services.helpers import get_active_season_id
from models.schemas import ShadowCreate, ShadowUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Shadows"])


@router.get("/shadows")
async def get_all_shadows():
    """Get all shadow staff members for the active season"""
    try:
        query = {}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id

        shadows = await db.shadows.find(query).to_list(None)
        result = []
        for shadow in shadows:
            result.append({
                "id": str(shadow.get("_id", "")),
                "shadow_name": shadow.get("shadow_name"),
                "camper_id": shadow.get("camper_id"),
                "camper_name": shadow.get("camper_name"),
                "bus_number": shadow.get("bus_number"),
                "session": shadow.get("session"),
                "town": shadow.get("town", ""),
                "created_at": shadow.get("created_at"),
                "updated_at": shadow.get("updated_at")
            })
        return {"status": "success", "shadows": result, "count": len(result)}
    except Exception as e:
        logging.error(f"Error getting shadows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shadows/by-bus/{bus_number}")
async def get_shadows_by_bus(bus_number: str):
    """Get all shadows assigned to campers on a specific bus"""
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        query = {"bus_number": decoded_bus}

        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id

        shadows = await db.shadows.find(query).to_list(None)
        result = []
        for shadow in shadows:
            result.append({
                "id": str(shadow.get("_id", "")),
                "shadow_name": shadow.get("shadow_name"),
                "camper_id": shadow.get("camper_id"),
                "camper_name": shadow.get("camper_name"),
                "bus_number": shadow.get("bus_number"),
                "session": shadow.get("session"),
                "created_at": shadow.get("created_at")
            })
        return {"status": "success", "shadows": result, "count": len(result)}
    except Exception as e:
        logging.error(f"Error getting shadows by bus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shadows/by-camper/{camper_id}")
async def get_shadow_by_camper(camper_id: str):
    """Get shadow for a specific camper"""
    try:
        decoded_id = urllib.parse.unquote(camper_id)
        shadow = await db.shadows.find_one({"camper_id": decoded_id})
        if shadow:
            return {
                "status": "success",
                "shadow": {
                    "id": str(shadow.get("_id", "")),
                    "shadow_name": shadow.get("shadow_name"),
                    "camper_id": shadow.get("camper_id"),
                    "camper_name": shadow.get("camper_name"),
                    "bus_number": shadow.get("bus_number"),
                    "session": shadow.get("session")
                }
            }
        return {"status": "success", "shadow": None}
    except Exception as e:
        logging.error(f"Error getting shadow by camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shadows")
async def create_shadow(shadow_data: ShadowCreate):
    """Create a new shadow staff member linked to a camper"""
    try:
        camper = await db.campers.find_one({"_id": shadow_data.camper_id})
        if not camper:
            raise HTTPException(status_code=404, detail=f"Camper not found: {shadow_data.camper_id}")

        season_id = await get_active_season_id()

        existing_query = {"camper_id": shadow_data.camper_id}
        if season_id:
            existing_query["season_id"] = season_id
        existing = await db.shadows.find_one(existing_query)
        if existing:
            raise HTTPException(status_code=400, detail=f"Shadow already exists for this camper. Use PUT to update.")

        if shadow_data.bus_number:
            bus_number = shadow_data.bus_number
        else:
            bus_number = camper.get('am_bus_number', '')
            if not bus_number or bus_number == 'NONE':
                bus_number = camper.get('pm_bus_number', '')

        shadow_doc = {
            "shadow_name": shadow_data.shadow_name.strip(),
            "camper_id": shadow_data.camper_id,
            "camper_name": f"{camper.get('first_name', '')} {camper.get('last_name', '')}".strip(),
            "bus_number": bus_number,
            "session": camper.get('session', 'Full Season- 5 Days'),
            "town": camper.get('town', ''),
            "season_id": season_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        result = await db.shadows.insert_one(shadow_doc)
        shadow_doc["id"] = str(result.inserted_id)
        if "_id" in shadow_doc:
            del shadow_doc["_id"]

        logging.info(f"Created shadow '{shadow_data.shadow_name}' for camper {shadow_doc['camper_name']} on {bus_number}")
        return {"status": "success", "shadow": shadow_doc}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating shadow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/shadows/{shadow_id}")
async def update_shadow(shadow_id: str, shadow_data: ShadowUpdate):
    """Update an existing shadow"""
    try:
        update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

        if shadow_data.shadow_name is not None:
            update_fields["shadow_name"] = shadow_data.shadow_name.strip()

        if shadow_data.camper_id is not None:
            camper = await db.campers.find_one({"_id": shadow_data.camper_id})
            if not camper:
                raise HTTPException(status_code=404, detail=f"Camper not found: {shadow_data.camper_id}")

            update_fields["camper_id"] = shadow_data.camper_id
            update_fields["camper_name"] = f"{camper.get('first_name', '')} {camper.get('last_name', '')}".strip()
            update_fields["session"] = camper.get('session', 'Full Season- 5 Days')

            bus_number = camper.get('am_bus_number', '')
            if not bus_number or bus_number == 'NONE':
                bus_number = camper.get('pm_bus_number', '')
            update_fields["bus_number"] = bus_number

        result = await db.shadows.update_one(
            {"_id": ObjectId(shadow_id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Shadow not found")

        return {"status": "success", "message": "Shadow updated"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating shadow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shadows/{shadow_id}")
async def delete_shadow(shadow_id: str):
    """Delete a shadow staff member"""
    try:
        result = await db.shadows.delete_one({"_id": ObjectId(shadow_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Shadow not found")

        logging.info(f"Deleted shadow: {shadow_id}")
        return {"status": "success", "message": "Shadow deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting shadow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shadows/by-camper/{camper_id}")
async def delete_shadow_by_camper(camper_id: str):
    """Delete shadow by camper ID"""
    try:
        decoded_id = urllib.parse.unquote(camper_id)
        result = await db.shadows.delete_one({"camper_id": decoded_id})
        if result.deleted_count == 0:
            return {"status": "success", "message": "No shadow found for this camper"}

        logging.info(f"Deleted shadow for camper: {decoded_id}")
        return {"status": "success", "message": "Shadow deleted"}
    except Exception as e:
        logging.error(f"Error deleting shadow by camper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
