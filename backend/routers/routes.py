"""Routes and bus information router."""

import logging
from datetime import datetime, timezone
from typing import Optional
from io import StringIO, BytesIO
import csv

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from services.database import (
    db, route_printer, sheets_generator, cover_sheet_generator
)
from services.bus_utils import get_bus_color
from bus_config import get_bus_info, get_all_buses, get_camp_address

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Routes"])


@router.get("/buses")
async def get_buses():
    """Get all buses with their info including home locations."""
    try:
        buses = []
        for bus_number in get_all_buses():
            bus_info = get_bus_info(bus_number)
            am_count = await db.campers.count_documents({"am_bus_number": bus_number})
            pm_count = await db.campers.count_documents({"pm_bus_number": bus_number})
            bus_info['am_camper_count'] = am_count
            bus_info['pm_camper_count'] = pm_count
            buses.append(bus_info)
        
        return {
            "status": "success",
            "buses": buses,
            "camp_address": get_camp_address()
        }
    except Exception as e:
        logger.error(f"Error getting buses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buses/{bus_number}")
async def get_bus_details(bus_number: str):
    """Get detailed info for a specific bus."""
    try:
        bus_info = get_bus_info(bus_number)
        
        am_campers = await db.campers.find({"am_bus_number": bus_number}).to_list(None)
        pm_campers = await db.campers.find({"pm_bus_number": bus_number}).to_list(None)
        
        return {
            "status": "success",
            "bus": bus_info,
            "camp_address": get_camp_address(),
            "am_campers": [
                {"name": f"{c['first_name']} {c['last_name']}", "address": c.get('location', {}).get('address', '')}
                for c in am_campers
            ],
            "pm_campers": [
                {"name": f"{c['first_name']} {c['last_name']}", "address": c.get('location', {}).get('address', '')}
                for c in pm_campers
            ]
        }
    except Exception as e:
        logger.error(f"Error getting bus details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/route-sheet/{bus_number}")
async def get_route_sheet(bus_number: str):
    """Get route data for a specific bus."""
    import urllib.parse
    
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        
        am_campers = await db.campers.find({
            "am_bus_number": decoded_bus,
            "location.latitude": {"$ne": 0.0}
        }).to_list(None)
        
        pm_campers = await db.campers.find({
            "pm_bus_number": decoded_bus,
            "location.latitude": {"$ne": 0.0}
        }).to_list(None)
        
        return {
            "status": "success",
            "bus_number": decoded_bus,
            "am_campers": len(am_campers),
            "pm_campers": len(pm_campers),
            "am_route": [
                {
                    "name": f"{c['first_name']} {c['last_name']}",
                    "address": c.get('location', {}).get('address', ''),
                    "location": c.get('location', {})
                }
                for c in am_campers
            ],
            "pm_route": [
                {
                    "name": f"{c['first_name']} {c['last_name']}",
                    "address": c.get('location', {}).get('address', ''),
                    "location": c.get('location', {})
                }
                for c in pm_campers
            ]
        }
    except Exception as e:
        logger.error(f"Error getting route sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/route-sheet/{bus_number}/print")
async def get_printable_route_sheet(bus_number: str):
    """Generate a printable HTML route sheet for a bus."""
    import urllib.parse
    
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        
        am_campers = await db.campers.find({
            "am_bus_number": decoded_bus,
            "location.latitude": {"$ne": 0.0}
        }).to_list(None)
        
        pm_campers = await db.campers.find({
            "pm_bus_number": decoded_bus,
            "location.latitude": {"$ne": 0.0}
        }).to_list(None)
        
        html_content = await route_printer.generate_route_sheet_html(
            decoded_bus,
            am_campers,
            pm_campers
        )
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error generating printable route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sheets/seat-availability")
async def get_seat_availability_for_sheets():
    """Get formatted seat availability data for Google Sheets - COVER SHEET FORMAT."""
    try:
        campers = await db.campers.find({
            "am_bus_number": {"$exists": True, "$nin": ["NONE", ""]}
        }).to_list(None)
        
        sheet_data = cover_sheet_generator.generate_cover_sheet(campers)
        
        return {
            "status": "success",
            "data": sheet_data,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating sheets data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sheets/compact-availability")
async def get_compact_availability():
    """Get compact seat availability summary for Google Sheets."""
    try:
        campers = await db.campers.find({
            "bus_number": {"$exists": True, "$nin": ["NONE", ""]}
        }).to_list(None)
        compact_data = sheets_generator.generate_compact_availability(campers)
        
        return {
            "status": "success",
            "data": compact_data,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating compact data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-colors")
async def refresh_colors():
    """Refresh bus colors for all campers."""
    try:
        campers = await db.campers.find({}).to_list(None)
        
        for camper in campers:
            bus_num = camper.get('am_bus_number') or camper.get('bus_number', '')
            new_color = get_bus_color(bus_num)
            await db.campers.update_one(
                {"_id": camper["_id"]},
                {"$set": {"bus_color": new_color}}
            )
        
        return {"status": "success", "updated": len(campers)}
    except Exception as e:
        logger.error(f"Error refreshing colors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/bus-assignments")
async def download_bus_assignments():
    """Download all bus assignments as CSV."""
    try:
        all_campers = await db.campers.find({}).to_list(None)
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'First Name', 'Last Name', 'AM Bus', 'PM Bus', 
            'Address', 'Town', 'Zip', 'Session', 'Pickup Type'
        ])
        
        seen_campers = set()
        for camper in all_campers:
            first_name = camper.get('first_name', '')
            last_name = camper.get('last_name', '')
            camper_id = camper.get('_id', '')
            
            if camper_id.endswith('_PM'):
                continue
            
            key = f"{first_name}|{last_name}"
            if key in seen_campers:
                continue
            seen_campers.add(key)
            
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            if am_bus == 'NONE':
                am_bus = ''
            if pm_bus == 'NONE':
                pm_bus = ''
            
            writer.writerow([
                first_name,
                last_name,
                am_bus,
                pm_bus,
                camper.get('location', {}).get('address', ''),
                camper.get('town', ''),
                camper.get('zip_code', ''),
                camper.get('session', ''),
                camper.get('pickup_type', '')
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=bus_assignments_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error downloading assignments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export-campers-csv")
async def export_campers_csv():
    """Export all camper data as CSV."""
    try:
        all_campers = await db.campers.find({}).to_list(None)
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'First Name', 'Last Name', 'AM Bus', 'PM Bus',
            'Latitude', 'Longitude', 'Address', 'Town', 'Zip',
            'Session', 'Pickup Type', 'Bus Color'
        ])
        
        for camper in all_campers:
            writer.writerow([
                camper.get('_id', ''),
                camper.get('first_name', ''),
                camper.get('last_name', ''),
                camper.get('am_bus_number', ''),
                camper.get('pm_bus_number', ''),
                camper.get('location', {}).get('latitude', 0),
                camper.get('location', {}).get('longitude', 0),
                camper.get('location', {}).get('address', ''),
                camper.get('town', ''),
                camper.get('zip_code', ''),
                camper.get('session', ''),
                camper.get('pickup_type', ''),
                camper.get('bus_color', '')
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=campers_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting campers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
