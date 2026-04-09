"""Public bus roster endpoints for external Bus Mapping App integration.
Provides real-time camper roster with attendance status, grouped by AM bus.
Designed for polling every 10-30s between 7:30-9:30 AM EST.
"""

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.database import db
from services.helpers import get_active_season_id

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
    """Pull full AM roster grouped by bus with real-time attendance.
    Optional filters: ?date=YYYY-MM-DD&bus_number=Bus%20%2301
    """
    if not date:
        date = today_eastern()

    season_id = await get_active_season_id()

    camper_query = {}
    if season_id:
        camper_query["season_id"] = season_id
    if bus_number:
        camper_query["am_bus_number"] = urllib.parse.unquote(bus_number)

    campers_cursor = db.campers.find(
        camper_query,
        {"_id": 1, "first_name": 1, "last_name": 1, "am_bus_number": 1}
    ).sort([("am_bus_number", 1), ("last_name", 1), ("first_name", 1)])

    campers = await campers_cursor.to_list(length=2000)

    # Fetch all attendance for this date in one query
    att_query = {"date": date}
    if bus_number:
        att_query["bus_number"] = urllib.parse.unquote(bus_number)

    att_cursor = db.bus_attendance.find(att_query)
    att_docs = await att_cursor.to_list(length=200)

    # Build attendance lookup: {bus_number: {camper_id: status}}
    att_map = {}
    for doc in att_docs:
        bn = doc.get("bus_number", "")
        att_map[bn] = {}
        for rec in doc.get("records", []):
            att_map[bn][rec["camper_id"]] = rec["status"]

    # Group campers by AM bus
    buses = {}
    for c in campers:
        bn = c.get("am_bus_number", "NONE")
        if bn not in buses:
            buses[bn] = {"bus_number": bn, "campers": [], "summary": {"present": 0, "absent": 0, "unmarked": 0, "total": 0}}

        cid = c["_id"]
        status = att_map.get(bn, {}).get(cid, "unmarked")

        buses[bn]["campers"].append({
            "id": cid,
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "bus_number": bn,
            "status": status
        })
        buses[bn]["summary"]["total"] += 1
        if status == "present":
            buses[bn]["summary"]["present"] += 1
        elif status == "absent":
            buses[bn]["summary"]["absent"] += 1
        else:
            buses[bn]["summary"]["unmarked"] += 1

    roster = sorted(buses.values(), key=lambda b: b["bus_number"])

    totals = {
        "total_campers": sum(b["summary"]["total"] for b in roster),
        "total_present": sum(b["summary"]["present"] for b in roster),
        "total_absent": sum(b["summary"]["absent"] for b in roster),
        "total_unmarked": sum(b["summary"]["unmarked"] for b in roster),
        "buses": len(roster)
    }

    return {
        "success": True,
        "date": date,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "roster": roster,
        "totals": totals
    }


@router.get("/bus-roster/{bus_number}")
async def get_bus_roster_single(bus_number: str, date: Optional[str] = None):
    """Pull roster for ONE bus with real-time attendance."""
    bus_number = urllib.parse.unquote(bus_number)

    if not date:
        date = today_eastern()

    season_id = await get_active_season_id()

    camper_query = {"am_bus_number": bus_number}
    if season_id:
        camper_query["season_id"] = season_id

    campers_cursor = db.campers.find(
        camper_query,
        {"_id": 1, "first_name": 1, "last_name": 1, "am_bus_number": 1}
    ).sort([("last_name", 1), ("first_name", 1)])

    campers = await campers_cursor.to_list(length=200)

    att_doc = await db.bus_attendance.find_one({"bus_number": bus_number, "date": date})
    att_lookup = {}
    if att_doc:
        for rec in att_doc.get("records", []):
            att_lookup[rec["camper_id"]] = rec["status"]

    roster_campers = []
    present = absent = unmarked = 0
    for c in campers:
        cid = c["_id"]
        status = att_lookup.get(cid, "unmarked")
        roster_campers.append({
            "id": cid,
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "bus_number": bus_number,
            "status": status
        })
        if status == "present":
            present += 1
        elif status == "absent":
            absent += 1
        else:
            unmarked += 1

    return {
        "success": True,
        "date": date,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bus_number": bus_number,
        "campers": roster_campers,
        "summary": {"present": present, "absent": absent, "unmarked": unmarked, "total": len(roster_campers)}
    }


@router.put("/bus-roster/mark")
async def mark_roster_single(request: RosterMarkRequest):
    """Push single camper attendance status from external app."""
    date = request.date or today_eastern()

    if request.status not in ("present", "absent"):
        raise HTTPException(status_code=400, detail="Status must be 'present' or 'absent'")

    # Find camper's AM bus
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
    """Push multiple camper attendance statuses from external app.
    Body: { "bus_number": "Bus #01", "records": [{"camper_id": "...", "status": "present"}], "date": "2026-02-15" }
    """
    date = request.date or today_eastern()
    bus_number = urllib.parse.unquote(request.bus_number)
    now_iso = datetime.now(timezone.utc).isoformat()

    for rec in request.records:
        if rec.get("status") not in ("present", "absent"):
            raise HTTPException(status_code=400, detail=f"Invalid status '{rec.get('status')}' for camper {rec.get('camper_id')}. Must be 'present' or 'absent'")

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

    return {
        "success": True,
        "bus_number": bus_number,
        "date": date,
        "updated": len(request.records)
    }
