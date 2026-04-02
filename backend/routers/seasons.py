"""Season management endpoints."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from services.database import db
from models.schemas import SeasonCreate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Seasons"])


@router.get("/seasons")
async def get_all_seasons():
    """Get all seasons"""
    try:
        seasons = await db.seasons.find({}).sort("year", -1).to_list(None)
        result = []
        for season in seasons:
            camper_count = await db.campers.count_documents({"season_id": str(season["_id"])})
            result.append({
                "id": str(season["_id"]),
                "name": season.get("name", f"{season.get('year', 'Unknown')} Bus Route Management"),
                "year": season.get("year", 0),
                "is_active": season.get("is_active", False),
                "camper_count": camper_count,
                "created_at": season.get("created_at", ""),
                "archived_at": season.get("archived_at")
            })
        return {"status": "success", "seasons": result}
    except Exception as e:
        logging.error(f"Error getting seasons: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seasons/active")
async def get_active_season():
    """Get the currently active season"""
    try:
        season = await db.seasons.find_one({"is_active": True})
        if not season:
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

            await db.campers.update_many(
                {"season_id": {"$exists": False}},
                {"$set": {"season_id": new_season["_id"]}}
            )
            await db.shadows.update_many(
                {"season_id": {"$exists": False}},
                {"$set": {"season_id": new_season["_id"]}}
            )
            await db.bus_zones.update_many(
                {"season_id": {"$exists": False}},
                {"$set": {"season_id": new_season["_id"]}}
            )
            await db.bus_staff.update_many(
                {"season_id": {"$exists": False}},
                {"$set": {"season_id": new_season["_id"]}}
            )

            season = new_season

        camper_count = await db.campers.count_documents({"season_id": str(season["_id"])})

        return {
            "status": "success",
            "season": {
                "id": str(season["_id"]),
                "name": season.get("name", ""),
                "year": season.get("year", 0),
                "is_active": True,
                "camper_count": camper_count,
                "created_at": season.get("created_at", ""),
                "archived_at": None
            }
        }
    except Exception as e:
        logging.error(f"Error getting active season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seasons")
async def create_season(season_data: SeasonCreate):
    """Create a new season, optionally copying data from a previous season"""
    try:
        await db.seasons.update_many({}, {"$set": {"is_active": False}})

        new_season_id = str(uuid.uuid4())
        new_season = {
            "_id": new_season_id,
            "name": season_data.name,
            "year": season_data.year,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "archived_at": None
        }

        await db.seasons.insert_one(new_season)

        copied_counts = {"campers": 0, "shadows": 0, "bus_zones": 0, "bus_staff": 0, "assigned_staff": 0}

        if season_data.copy_from_season_id:
            old_campers = await db.campers.find({"season_id": season_data.copy_from_season_id}).to_list(None)
            if old_campers:
                for camper in old_campers:
                    old_id = camper["_id"]
                    camper["_id"] = f"{old_id}_{new_season_id[:8]}"
                    camper["season_id"] = new_season_id
                    camper["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.campers.insert_many(old_campers)
                copied_counts["campers"] = len(old_campers)

            old_shadows = await db.shadows.find({"season_id": season_data.copy_from_season_id}).to_list(None)
            if old_shadows:
                for shadow in old_shadows:
                    shadow.pop("_id", None)
                    shadow["season_id"] = new_season_id
                    shadow["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.shadows.insert_many(old_shadows)
                copied_counts["shadows"] = len(old_shadows)

            old_zones = await db.bus_zones.find({"season_id": season_data.copy_from_season_id}).to_list(None)
            if old_zones:
                for zone in old_zones:
                    zone.pop("_id", None)
                    zone["season_id"] = new_season_id
                    zone["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.bus_zones.insert_many(old_zones)
                copied_counts["bus_zones"] = len(old_zones)

            old_staff = await db.bus_staff.find({"season_id": season_data.copy_from_season_id}).to_list(None)
            if old_staff:
                for staff in old_staff:
                    staff.pop("_id", None)
                    staff["season_id"] = new_season_id
                    staff["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.bus_staff.insert_many(old_staff)
                copied_counts["bus_staff"] = len(old_staff)

            old_assigned = await db.bus_assigned_staff.find({"season_id": season_data.copy_from_season_id}).to_list(None)
            if old_assigned:
                for assigned in old_assigned:
                    assigned.pop("_id", None)
                    assigned["season_id"] = new_season_id
                    assigned["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.bus_assigned_staff.insert_many(old_assigned)
                copied_counts["assigned_staff"] = len(old_assigned)

        logging.info(f"Created new season: {season_data.name} (Year: {season_data.year})")
        if season_data.copy_from_season_id:
            logging.info(f"Copied data: {copied_counts}")

        return {
            "status": "success",
            "message": f"Season '{season_data.name}' created",
            "season_id": new_season_id,
            "copied": copied_counts if season_data.copy_from_season_id else None
        }
    except Exception as e:
        logging.error(f"Error creating season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/seasons/{season_id}/activate")
async def activate_season(season_id: str):
    """Set a season as the active season"""
    try:
        season = await db.seasons.find_one({"_id": season_id})
        if not season:
            raise HTTPException(status_code=404, detail="Season not found")

        await db.seasons.update_many({}, {"$set": {"is_active": False}})

        await db.seasons.update_one(
            {"_id": season_id},
            {"$set": {"is_active": True, "archived_at": None}}
        )

        return {"status": "success", "message": f"Season '{season['name']}' is now active"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error activating season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/seasons/{season_id}/archive")
async def archive_season(season_id: str):
    """Archive a season (marks it as archived but keeps data)"""
    try:
        season = await db.seasons.find_one({"_id": season_id})
        if not season:
            raise HTTPException(status_code=404, detail="Season not found")

        if season.get("is_active"):
            raise HTTPException(status_code=400, detail="Cannot archive the active season")

        await db.seasons.update_one(
            {"_id": season_id},
            {"$set": {"archived_at": datetime.now(timezone.utc).isoformat()}}
        )

        return {"status": "success", "message": f"Season '{season['name']}' archived"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error archiving season: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
