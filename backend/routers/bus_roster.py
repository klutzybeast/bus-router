"""Public bus roster endpoints for external Bus Mapping App integration.
GET endpoints proxy to CamperSnapshot (session-aware, bus riders only).
PUT endpoints write locally and push to CamperSnapshot.
"""

import logging
import urllib.parse
import asyncio as _asyncio
from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.database import db
from services.snapshot_sync import sync_person_ids, fetch_snapshot_roster

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")

router = APIRouter(tags=["Bus Roster"])


def today_eastern():
    return datetime.now(EASTERN).strftime("%Y-%m-%d")


class RosterMarkRequest(BaseModel):
    camper_id: str
    status: str
    date: Optional[str] = None


class RosterBulkRequest(BaseModel):
    bus_number: str
    records: List[dict]
    date: Optional[str] = None


@router.get("/bus-roster")
async def get_bus_roster(date: Optional[str] = None, bus_number: Optional[str] = None):
    """Pull daily roster from CamperSnapshot — session-aware, bus riders only.
    Only shows campers scheduled to be at camp on the given date.
    """
    if not date:
        date = today_eastern()

    if bus_number:
        data = await fetch_snapshot_roster(date=date, bus_number=urllib.parse.quote(bus_number, safe=""))
    else:
        data = await fetch_snapshot_roster(date=date)

    if data.get("fallback"):
        raise HTTPException(status_code=502, detail=data.get("error", "CamperSnapshot unavailable"))

    return data


@router.get("/bus-roster/{bus_number}")
async def get_bus_roster_single(bus_number: str, date: Optional[str] = None):
    """Pull roster for ONE bus from CamperSnapshot — session-aware."""
    if not date:
        date = today_eastern()

    encoded_bus = urllib.parse.quote(urllib.parse.unquote(bus_number), safe="")
    data = await fetch_snapshot_roster(date=date, bus_number=encoded_bus)

    if data.get("fallback"):
        raise HTTPException(status_code=502, detail=data.get("error", "CamperSnapshot unavailable"))

    return data


@router.put("/bus-roster/mark")
async def mark_roster_single(request: RosterMarkRequest):
    """Push single camper attendance status from external app."""
    date = request.date or today_eastern()

    if request.status not in ("present", "absent"):
        raise HTTPException(status_code=400, detail="Status must be 'present' or 'absent'")

    camper = await db.campers.find_one({"_id": request.camper_id}, {"am_bus_number": 1})
    if not camper:
        raise HTTPException(status_code=404, detail="Camper not found")

    bus_number = camper.get("am_bus_number", "NONE")
    now_iso = datetime.now(timezone.utc).isoformat()

    existing = await db.bus_attendance.find_one({"bus_number": bus_number, "date": date})

    if existing:
        records = [r for r in existing.get("records", []) if r["camper_id"] != request.camper_id]
        records.append({"camper_id": request.camper_id, "status": request.status, "marked_at": now_iso})
        await db.bus_attendance.update_one(
            {"_id": existing["_id"]},
            {"$set": {"records": records, "updated_at": now_iso}}
        )
    else:
        await db.bus_attendance.insert_one({
            "bus_number": bus_number,
            "date": date,
            "records": [{"camper_id": request.camper_id, "status": request.status, "marked_at": now_iso}],
            "created_at": now_iso,
            "updated_at": now_iso
        })

    return {"success": True, "camper_id": request.camper_id, "bus_number": bus_number, "status": request.status, "date": date}


@router.put("/bus-roster/bulk")
async def mark_roster_bulk(request: RosterBulkRequest):
    """Push multiple camper attendance statuses from external app."""
    date = request.date or today_eastern()
    bus_number = urllib.parse.unquote(request.bus_number)
    now_iso = datetime.now(timezone.utc).isoformat()

    for rec in request.records:
        if rec.get("status") not in ("present", "absent"):
            raise HTTPException(status_code=400, detail=f"Invalid status for camper {rec.get('camper_id')}")

    existing = await db.bus_attendance.find_one({"bus_number": bus_number, "date": date})

    if existing:
        records = existing.get("records", [])
        incoming_ids = {r["camper_id"] for r in request.records}
        records = [r for r in records if r["camper_id"] not in incoming_ids]
        for rec in request.records:
            records.append({"camper_id": rec["camper_id"], "status": rec["status"], "marked_at": now_iso})
        await db.bus_attendance.update_one(
            {"_id": existing["_id"]},
            {"$set": {"records": records, "updated_at": now_iso}}
        )
    else:
        records = [{"camper_id": r["camper_id"], "status": r["status"], "marked_at": now_iso} for r in request.records]
        await db.bus_attendance.insert_one({
            "bus_number": bus_number,
            "date": date,
            "records": records,
            "created_at": now_iso,
            "updated_at": now_iso
        })

    return {"success": True, "bus_number": bus_number, "date": date, "updated": len(request.records)}


# --- Person ID sync endpoints ---

_sync_status = {"running": False, "last_result": None}


@router.post("/sync-person-ids")
async def trigger_person_id_sync():
    """Trigger CampMinder person ID sync as a background task."""
    if _sync_status["running"]:
        return {"success": True, "message": "Sync already running", "status": _sync_status}

    async def _run_sync():
        _sync_status["running"] = True
        try:
            result = await sync_person_ids()
            _sync_status["last_result"] = result
        finally:
            _sync_status["running"] = False

    _asyncio.create_task(_run_sync())
    return {"success": True, "message": "Person ID sync started in background. Check /api/sync-person-ids/status for results."}


@router.get("/sync-person-ids/status")
async def get_person_id_sync_status():
    """Check status of the background person ID sync."""
    return {"running": _sync_status["running"], "last_result": _sync_status["last_result"]}
