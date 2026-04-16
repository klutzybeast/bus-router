"""GPS bus tracking, attendance, and history endpoints."""

import logging
import asyncio
import urllib.parse
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.database import db
from services.helpers import get_active_season_id
from services.snapshot_sync import push_attendance_to_snapshot
from models.schemas import (
    BusLocationUpdate, BusLoginRequest, AttendanceUpdate,
    BulkAttendanceUpdate, PickupDropoffRequest
)
from bus_config import get_bus_driver, get_bus_counselor

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")


def today_eastern():
    """Get today's date string in Eastern Time."""
    return datetime.now(EASTERN).strftime("%Y-%m-%d")


def period_eastern():
    """Get AM/PM based on Eastern Time."""
    return "AM" if datetime.now(EASTERN).hour < 12 else "PM"

router = APIRouter(tags=["Bus Tracking"])


@router.post("/bus-tracking/login")
async def bus_tracking_login(request: BusLoginRequest):
    """Counselor login with bus number as PIN."""
    try:
        pin = request.pin.strip().lstrip('0') or '0'
        bus_number = f"Bus #{pin.zfill(2)}"

        season_id = await get_active_season_id()

        query = {
            "$or": [
                {"am_bus_number": bus_number},
                {"pm_bus_number": bus_number}
            ]
        }
        if season_id:
            query["season_id"] = season_id

        camper_count = await db.campers.count_documents(query)

        if camper_count == 0:
            raise HTTPException(status_code=401, detail="Invalid bus number")

        driver = get_bus_driver(bus_number)
        counselor = get_bus_counselor(bus_number)

        campers_cursor = db.campers.find(
            {"am_bus_number": bus_number, "season_id": season_id} if season_id else {"am_bus_number": bus_number},
            {"_id": 1, "first_name": 1, "last_name": 1, "location.address": 1, "am_bus_number": 1, "pm_bus_number": 1}
        ).sort([("last_name", 1), ("first_name", 1)])

        campers = []
        async for c in campers_cursor:
            campers.append({
                "id": c["_id"],
                "first_name": c.get("first_name", ""),
                "last_name": c.get("last_name", ""),
                "address": c.get("location", {}).get("address", ""),
                "am_bus": c.get("am_bus_number", ""),
                "pm_bus": c.get("pm_bus_number", "")
            })

        today = today_eastern()
        attendance_doc = await db.bus_attendance.find_one({
            "bus_number": bus_number,
            "date": today
        })

        attendance = {}
        if attendance_doc:
            for record in attendance_doc.get("records", []):
                attendance[record["camper_id"]] = record["status"]

        logging.info(f"Bus tracking login successful: {bus_number} with {len(campers)} campers")

        return {
            "success": True,
            "bus_number": bus_number,
            "driver": driver,
            "counselor": counselor,
            "campers": campers,
            "attendance": attendance,
            "date": today
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Bus tracking login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bus-tracking/location")
async def update_bus_location(request: BusLocationUpdate):
    """Update bus GPS location (called from counselor app)."""
    try:
        bus_number = request.bus_number
        now = datetime.now(timezone.utc)
        today = today_eastern()

        prev_location = await db.bus_locations.find_one({"bus_number": bus_number})

        is_stopped = False
        stop_duration = 0

        if prev_location and prev_location.get("latitude") and prev_location.get("longitude"):
            R = 6371000
            lat1, lon1 = radians(prev_location["latitude"]), radians(prev_location["longitude"])
            lat2, lon2 = radians(request.latitude), radians(request.longitude)
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            distance = R * 2 * atan2(sqrt(a), sqrt(1-a))

            if distance < 20:
                is_stopped = True
                stop_started = prev_location.get("stop_started_at")
                if stop_started:
                    if isinstance(stop_started, str):
                        stop_started = datetime.fromisoformat(stop_started.replace('Z', '+00:00'))
                    if stop_started.tzinfo is None:
                        stop_started = stop_started.replace(tzinfo=timezone.utc)
                    stop_duration = (now - stop_started).total_seconds()

        location_data = {
            "bus_number": bus_number,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "accuracy": request.accuracy,
            "speed": request.speed,
            "heading": request.heading,
            "updated_at": now.isoformat(),
            "timestamp": now,
            "is_stopped": is_stopped,
            "stop_duration": stop_duration if is_stopped else 0,
        }

        if is_stopped:
            if prev_location and prev_location.get("is_stopped"):
                location_data["stop_started_at"] = prev_location.get("stop_started_at", now)
            else:
                location_data["stop_started_at"] = now
        else:
            location_data["stop_started_at"] = None

        await db.bus_locations.update_one(
            {"bus_number": bus_number},
            {"$set": location_data},
            upsert=True
        )

        history_entry = {
            "bus_number": bus_number,
            "date": today,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "accuracy": request.accuracy,
            "speed": request.speed,
            "heading": request.heading,
            "timestamp": now,
            "is_stopped": is_stopped,
            "period": period_eastern()
        }

        await db.bus_location_history.insert_one(history_entry)

        if is_stopped and stop_duration >= 30:
            await db.bus_stops_log.update_one(
                {
                    "bus_number": bus_number,
                    "date": today,
                    "stop_started_at": location_data["stop_started_at"],
                },
                {
                    "$set": {
                        "latitude": request.latitude,
                        "longitude": request.longitude,
                        "duration_seconds": stop_duration,
                        "last_updated": now,
                        "period": period_eastern()
                    }
                },
                upsert=True
            )

        return {"success": True, "message": "Location updated", "is_stopped": is_stopped, "stop_duration": stop_duration}

    except Exception as e:
        logging.error(f"Error updating bus location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/location/{bus_number}")
async def get_bus_location_tracking(bus_number: str):
    """Get current GPS location for a bus (for admin tracking popup)."""
    try:
        bus_number = urllib.parse.unquote(bus_number)

        location = await db.bus_locations.find_one(
            {"bus_number": bus_number},
            {"_id": 0}
        )

        if not location:
            return {
                "success": False,
                "message": "No location data available for this bus",
                "bus_number": bus_number,
                "tracking_active": False
            }

        updated_at = location.get("timestamp")
        is_stale = False
        if updated_at:
            try:
                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
                is_stale = age_seconds > 300
            except Exception:
                is_stale = True

        return {
            "success": True,
            "bus_number": bus_number,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "accuracy": location.get("accuracy"),
            "speed": location.get("speed"),
            "heading": location.get("heading"),
            "updated_at": location.get("updated_at"),
            "tracking_active": not is_stale,
            "is_stale": is_stale,
            "is_stopped": location.get("is_stopped", False),
            "stop_duration": location.get("stop_duration", 0)
        }

    except Exception as e:
        logging.error(f"Error getting bus location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/all-locations")
async def get_all_bus_locations():
    """Get current GPS locations for all buses (for admin overview)."""
    try:
        locations_cursor = db.bus_locations.find({}, {"_id": 0})
        locations = await locations_cursor.to_list(length=100)

        now = datetime.now(timezone.utc)
        for loc in locations:
            updated_at = loc.get("timestamp")
            if updated_at:
                try:
                    if isinstance(updated_at, str):
                        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    age_seconds = (now - updated_at).total_seconds()
                    loc["is_stale"] = age_seconds > 300
                    loc["tracking_active"] = age_seconds <= 300
                except Exception:
                    loc["is_stale"] = True
                    loc["tracking_active"] = False
            else:
                loc["is_stale"] = True
                loc["tracking_active"] = False

        return {
            "success": True,
            "locations": locations,
            "count": len(locations)
        }

    except Exception as e:
        logging.error(f"Error getting all bus locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bus-tracking/attendance")
async def update_attendance(request: AttendanceUpdate, bus_number: str):
    """Update attendance for a single camper."""
    try:
        today = today_eastern()

        if request.status not in ["present", "absent"]:
            raise HTTPException(status_code=400, detail="Status must be 'present' or 'absent'")

        existing = await db.bus_attendance.find_one({
            "bus_number": bus_number,
            "date": today
        })

        if existing:
            records = existing.get("records", [])
            records = [r for r in records if r["camper_id"] != request.camper_id]
            records.append({
                "camper_id": request.camper_id,
                "status": request.status,
                "marked_at": datetime.now(timezone.utc).isoformat()
            })

            await db.bus_attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": {"records": records, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        else:
            await db.bus_attendance.insert_one({
                "bus_number": bus_number,
                "date": today,
                "records": [{
                    "camper_id": request.camper_id,
                    "status": request.status,
                    "marked_at": datetime.now(timezone.utc).isoformat()
                }],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })

        logging.info(f"Attendance updated: {bus_number} - {request.camper_id} = {request.status}")

        # Fire-and-forget push to CamperSnapshot
        asyncio.create_task(push_attendance_to_snapshot(request.camper_id, request.status, today))

        return {"success": True, "message": "Attendance updated"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating attendance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/attendance/{bus_number}")
async def get_attendance(bus_number: str, date: Optional[str] = None):
    """Get attendance for a bus on a specific date (defaults to today)."""
    try:
        bus_number = urllib.parse.unquote(bus_number)

        if not date:
            date = today_eastern()

        attendance_doc = await db.bus_attendance.find_one({
            "bus_number": bus_number,
            "date": date
        })

        if not attendance_doc:
            return {
                "success": True,
                "bus_number": bus_number,
                "date": date,
                "records": [],
                "summary": {"present": 0, "absent": 0, "unmarked": 0}
            }

        records = attendance_doc.get("records", [])
        present_count = sum(1 for r in records if r["status"] == "present")
        absent_count = sum(1 for r in records if r["status"] == "absent")

        return {
            "success": True,
            "bus_number": bus_number,
            "date": date,
            "records": records,
            "summary": {
                "present": present_count,
                "absent": absent_count
            }
        }

    except Exception as e:
        logging.error(f"Error getting attendance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/history/{bus_number}")
async def get_bus_tracking_history(bus_number: str, date: Optional[str] = None, period: Optional[str] = None):
    """Get tracking history for a bus on a specific date."""
    try:
        bus_number = urllib.parse.unquote(bus_number)

        if not date:
            date = today_eastern()

        query = {"bus_number": bus_number, "date": date}
        if period and period.upper() in ['AM', 'PM']:
            query["period"] = period.upper()

        history_cursor = db.bus_location_history.find(
            query,
            {"_id": 0, "latitude": 1, "longitude": 1, "timestamp": 1, "speed": 1, "is_stopped": 1, "period": 1}
        ).sort("timestamp", 1)

        history = await history_cursor.to_list(length=10000)

        for point in history:
            if point.get("timestamp"):
                if isinstance(point["timestamp"], datetime):
                    point["timestamp"] = point["timestamp"].isoformat()

        stops_cursor = db.bus_stops_log.find(
            {"bus_number": bus_number, "date": date},
            {"_id": 0}
        ).sort("stop_started_at", 1)
        stops = await stops_cursor.to_list(length=100)

        for stop in stops:
            if stop.get("stop_started_at"):
                if isinstance(stop["stop_started_at"], datetime):
                    stop["stop_started_at"] = stop["stop_started_at"].isoformat()
            if stop.get("last_updated"):
                if isinstance(stop["last_updated"], datetime):
                    stop["last_updated"] = stop["last_updated"].isoformat()

        return {
            "success": True,
            "bus_number": bus_number,
            "date": date,
            "period": period,
            "points": history,
            "point_count": len(history),
            "stops": stops,
            "stop_count": len(stops)
        }

    except Exception as e:
        logging.error(f"Error getting tracking history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/history-dates/{bus_number}")
async def get_bus_tracking_dates(bus_number: str):
    """Get list of dates that have tracking data for a bus."""
    try:
        bus_number = urllib.parse.unquote(bus_number)

        dates = await db.bus_location_history.distinct("date", {"bus_number": bus_number})
        dates.sort(reverse=True)

        return {
            "success": True,
            "bus_number": bus_number,
            "dates": dates,
            "count": len(dates)
        }

    except Exception as e:
        logging.error(f"Error getting tracking dates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/stops/{bus_number}")
async def get_bus_stops_log(bus_number: str, date: Optional[str] = None):
    """Get all stops made by a bus on a specific date with durations."""
    try:
        bus_number = urllib.parse.unquote(bus_number)

        if not date:
            date = today_eastern()

        stops_cursor = db.bus_stops_log.find(
            {"bus_number": bus_number, "date": date},
            {"_id": 0}
        ).sort("stop_started_at", 1)

        stops = await stops_cursor.to_list(length=100)

        for stop in stops:
            if stop.get("stop_started_at"):
                if isinstance(stop["stop_started_at"], datetime):
                    stop["stop_started_at"] = stop["stop_started_at"].isoformat()
            if stop.get("last_updated"):
                if isinstance(stop["last_updated"], datetime):
                    stop["last_updated"] = stop["last_updated"].isoformat()
            duration = stop.get("duration_seconds", 0)
            if duration >= 3600:
                stop["duration_formatted"] = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m"
            elif duration >= 60:
                stop["duration_formatted"] = f"{int(duration // 60)}m {int(duration % 60)}s"
            else:
                stop["duration_formatted"] = f"{int(duration)}s"

        return {
            "success": True,
            "bus_number": bus_number,
            "date": date,
            "stops": stops,
            "total_stops": len(stops),
            "total_stop_time": sum(s.get("duration_seconds", 0) for s in stops)
        }

    except Exception as e:
        logging.error(f"Error getting bus stops: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/attendance-report")
async def get_attendance_report(date: Optional[str] = None):
    """Get attendance report for all buses - returns HTML for printing."""
    try:
        if not date:
            date = today_eastern()

        attendance_cursor = db.bus_attendance.find({"date": date})
        attendance_docs = await attendance_cursor.to_list(length=100)

        season_id = await get_active_season_id()

        camper_cursor = db.campers.find(
            {"season_id": season_id} if season_id else {},
            {"_id": 1, "first_name": 1, "last_name": 1, "am_bus_number": 1}
        )
        campers = await camper_cursor.to_list(length=1000)
        camper_map = {c["_id"]: c for c in campers}

        bus_reports = []
        for doc in sorted(attendance_docs, key=lambda x: x.get("bus_number", "")):
            bus_number = doc.get("bus_number", "Unknown")
            records = doc.get("records", [])

            present = []
            absent = []

            for record in records:
                camper_id = record.get("camper_id")
                camper = camper_map.get(camper_id, {})
                name = f"{camper.get('first_name', '')} {camper.get('last_name', '')}".strip() or camper_id

                if record.get("status") == "present":
                    present.append(name)
                else:
                    absent.append(name)

            bus_reports.append({
                "bus_number": bus_number,
                "present": sorted(present),
                "absent": sorted(absent),
                "present_count": len(present),
                "absent_count": len(absent)
            })

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Attendance Report - {date}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1e40af; border-bottom: 2px solid #1e40af; padding-bottom: 10px; }}
        .bus-section {{ margin-bottom: 30px; page-break-inside: avoid; }}
        .bus-header {{ background: #3b82f6; color: white; padding: 10px 15px; border-radius: 8px 8px 0 0; }}
        .bus-header h2 {{ margin: 0; font-size: 1.2em; }}
        .bus-content {{ border: 1px solid #ddd; border-top: none; padding: 15px; border-radius: 0 0 8px 8px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 15px; }}
        .stat {{ padding: 10px 15px; border-radius: 6px; }}
        .stat-present {{ background: #dcfce7; color: #166534; }}
        .stat-absent {{ background: #fee2e2; color: #991b1b; }}
        .list-section {{ margin-top: 15px; }}
        .list-section h3 {{ font-size: 0.9em; color: #666; margin-bottom: 8px; }}
        .name-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .name-tag {{ background: #f3f4f6; padding: 4px 10px; border-radius: 4px; font-size: 0.85em; }}
        .name-tag.present {{ background: #dcfce7; }}
        .name-tag.absent {{ background: #fee2e2; }}
        .no-data {{ color: #999; font-style: italic; }}
        .print-btn {{ background: #1e40af; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; margin-bottom: 20px; }}
        @media print {{ .print-btn {{ display: none; }} }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">Print Report</button>
    <h1>Bus Attendance Report</h1>
    <p><strong>Date:</strong> {date}</p>"""

        if not bus_reports:
            html += "<p class='no-data'>No attendance data recorded for this date.</p>"
        else:
            total_present = sum(b["present_count"] for b in bus_reports)
            total_absent = sum(b["absent_count"] for b in bus_reports)
            html += f"<p><strong>Total:</strong> {total_present} present, {total_absent} absent across {len(bus_reports)} buses</p>"

            for bus in bus_reports:
                html += f"""<div class="bus-section">
                    <div class="bus-header"><h2>{bus['bus_number']}</h2></div>
                    <div class="bus-content">
                        <div class="stats">
                            <div class="stat stat-present"><strong>{bus['present_count']}</strong> Present</div>
                            <div class="stat stat-absent"><strong>{bus['absent_count']}</strong> Absent</div>
                        </div>"""

                if bus['present']:
                    html += f"""<div class="list-section"><h3>Present ({bus['present_count']})</h3>
                        <div class="name-list">{"".join(f'<span class="name-tag present">{name}</span>' for name in bus['present'])}</div></div>"""

                if bus['absent']:
                    html += f"""<div class="list-section"><h3>Absent ({bus['absent_count']})</h3>
                        <div class="name-list">{"".join(f'<span class="name-tag absent">{name}</span>' for name in bus['absent'])}</div></div>"""

                html += "</div></div>"

        html += "</body></html>"
        return HTMLResponse(content=html)

    except Exception as e:
        logging.error(f"Error generating attendance report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-tracking/attendance-report/json")
async def get_attendance_report_json(date: Optional[str] = None):
    """Get attendance report data as JSON."""
    try:
        if not date:
            date = today_eastern()

        attendance_cursor = db.bus_attendance.find({"date": date})
        attendance_docs = await attendance_cursor.to_list(length=100)

        season_id = await get_active_season_id()

        camper_cursor = db.campers.find(
            {"season_id": season_id} if season_id else {},
            {"_id": 1, "first_name": 1, "last_name": 1, "am_bus_number": 1}
        )
        campers = await camper_cursor.to_list(length=1000)
        camper_map = {c["_id"]: c for c in campers}

        bus_reports = []
        for doc in sorted(attendance_docs, key=lambda x: x.get("bus_number", "")):
            bus_number = doc.get("bus_number", "Unknown")
            records = doc.get("records", [])

            detailed_records = []
            for record in records:
                camper_id = record.get("camper_id")
                camper = camper_map.get(camper_id, {})
                detailed_records.append({
                    "camper_id": camper_id,
                    "name": f"{camper.get('first_name', '')} {camper.get('last_name', '')}".strip(),
                    "status": record.get("status"),
                    "marked_at": record.get("marked_at")
                })

            present_count = sum(1 for r in records if r.get("status") == "present")
            absent_count = sum(1 for r in records if r.get("status") == "absent")

            bus_reports.append({
                "bus_number": bus_number,
                "records": detailed_records,
                "summary": {
                    "present": present_count,
                    "absent": absent_count,
                    "total": len(records)
                }
            })

        return {
            "success": True,
            "date": date,
            "buses": bus_reports,
            "totals": {
                "buses_reporting": len(bus_reports),
                "total_present": sum(b["summary"]["present"] for b in bus_reports),
                "total_absent": sum(b["summary"]["absent"] for b in bus_reports)
            }
        }

    except Exception as e:
        logging.error(f"Error getting attendance report JSON: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campers/{camper_id}/pickup-dropoff")
async def update_pickup_dropoff(camper_id: str, request: PickupDropoffRequest):
    """Update the pickup/dropoff status for a camper."""
    try:
        if request.pickup_dropoff == "CLEAR":
            result = await db.campers.update_one(
                {"_id": camper_id},
                {"$unset": {"pickup_dropoff": ""}}
            )
            if result.modified_count > 0 or result.matched_count > 0:
                logging.info(f"Cleared pickup/dropoff for {camper_id}")
                return {"status": "success", "message": "Pickup/dropoff status cleared"}
            else:
                raise HTTPException(status_code=404, detail="Camper not found")

        valid_options = ["Early Pickup", "Late Drop Off", "Early Pickup and Late Drop Off"]
        if request.pickup_dropoff not in valid_options:
            raise HTTPException(status_code=400, detail=f"Invalid option. Must be one of: {valid_options}")

        result = await db.campers.update_one(
            {"_id": camper_id},
            {"$set": {"pickup_dropoff": request.pickup_dropoff}}
        )

        if result.modified_count > 0 or result.matched_count > 0:
            logging.info(f"Updated pickup/dropoff for {camper_id}: {request.pickup_dropoff}")
            return {"status": "success", "message": f"Pickup/dropoff updated to: {request.pickup_dropoff}"}
        else:
            raise HTTPException(status_code=404, detail="Camper not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating pickup/dropoff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
