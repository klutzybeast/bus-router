"""Bus information endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from services.database import db
from bus_config import (
    get_all_buses, get_bus_info, get_bus_capacity,
    get_bus_location, get_bus_driver, get_bus_counselor,
    get_camp_address
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Buses"])


@router.get("/buses")
async def get_buses():
    """Get all buses with their info including home locations and staff"""
    try:
        staff_configs = await db.bus_staff.find({}).to_list(None)
        staff_dict = {c['bus_number']: c for c in staff_configs}

        buses = []
        for bus_number in get_all_buses():
            bus_info = get_bus_info(bus_number)

            if bus_number in staff_dict:
                db_config = staff_dict[bus_number]
                bus_info['driver'] = db_config.get('driver_name', bus_info.get('driver', 'TBD'))
                bus_info['counselor'] = db_config.get('counselor_name', bus_info.get('counselor', 'TBD'))
                bus_info['home_location'] = db_config.get('home_address', bus_info.get('home_location', ''))
                if db_config.get('capacity'):
                    bus_info['capacity'] = db_config['capacity']

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
        logging.error(f"Error getting buses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buses/{bus_number}")
async def get_bus_details(bus_number: str):
    """Get detailed info for a specific bus"""
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
        logging.error(f"Error getting bus details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
