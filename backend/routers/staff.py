"""Bus staff, assigned staff, and staff address management endpoints."""

import os
import io
import csv
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File
from bson import ObjectId

from services.database import db
from services.helpers import get_active_season_id, point_in_polygon
from services.geocoding import geocode_address_cached
from models.schemas import (
    BusStaffConfig, BusAssignedStaffCreate, BusAssignedStaffUpdate,
    StaffAddressCreate, StaffAddressUpdate, RouteOrderSave
)
from bus_config import (
    get_bus_capacity, get_bus_location, get_bus_driver,
    get_bus_counselor, get_bus_home_location
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Staff"])

@router.get("/bus-staff")
async def get_all_bus_staff():
    """Get all bus staff configurations from database for the active season"""
    try:
        # Filter by active season
        query = {}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id
        
        staff_configs = await db.bus_staff.find(query).to_list(None)
        
        # Convert to dict format
        result = {}
        for config in staff_configs:
            bus_num = config.get('bus_number', '')
            result[bus_num] = {
                'bus_number': bus_num,
                'driver_name': config.get('driver_name', 'TBD'),
                'counselor_name': config.get('counselor_name', 'TBD'),
                'home_address': config.get('home_address', ''),
                'capacity': config.get('capacity', get_bus_capacity(bus_num)),
                'location_name': config.get('location_name', get_bus_location(bus_num)),
                'lat': config.get('lat'),
                'lng': config.get('lng'),
                'last_updated': config.get('last_updated')
            }
        
        return {
            "status": "success",
            "staff": result,
            "count": len(result)
        }
    except Exception as e:
        logging.error(f"Error getting bus staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-staff/{bus_number}")
async def get_bus_staff(bus_number: str):
    """Get staff configuration for a specific bus in the active season"""
    import urllib.parse
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        query = {"bus_number": decoded_bus}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id
        
        config = await db.bus_staff.find_one(query)
        
        if config:
            return {
                "status": "success",
                "bus_number": decoded_bus,
                "driver_name": config.get('driver_name', 'TBD'),
                "counselor_name": config.get('counselor_name', 'TBD'),
                "home_address": config.get('home_address', ''),
                "capacity": config.get('capacity', get_bus_capacity(decoded_bus)),
                "location_name": config.get('location_name', get_bus_location(decoded_bus)),
                "lat": config.get('lat'),
                "lng": config.get('lng')
            }
        else:
            # Return defaults from bus_config
            return {
                "status": "success",
                "bus_number": decoded_bus,
                "driver_name": get_bus_driver(decoded_bus),
                "counselor_name": get_bus_counselor(decoded_bus),
                "home_address": get_bus_home_location(decoded_bus),
                "capacity": get_bus_capacity(decoded_bus),
                "location_name": get_bus_location(decoded_bus),
                "lat": None,
                "lng": None
            }
    except Exception as e:
        logging.error(f"Error getting bus staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bus-staff")
async def save_bus_staff(config: BusStaffConfig):
    """Save or update bus staff configuration for the active season"""
    try:
        # Geocode the address if provided (using cached version)
        lat = None
        lng = None
        if config.home_address:
            location = await geocode_address_cached(config.home_address, "", "")
            if location:
                lat = location.latitude
                lng = location.longitude
                logging.info(f"Geocoded {config.home_address} to {lat}, {lng}")
        
        # Get active season
        season_id = await get_active_season_id()
        
        # Prepare document
        staff_doc = {
            "bus_number": config.bus_number,
            "driver_name": config.driver_name,
            "counselor_name": config.counselor_name,
            "home_address": config.home_address,
            "capacity": config.capacity or get_bus_capacity(config.bus_number),
            "location_name": config.location_name or get_bus_location(config.bus_number),
            "lat": lat,
            "lng": lng,
            "season_id": season_id,  # Add season_id
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert to database (matching bus_number AND season_id)
        query = {"bus_number": config.bus_number}
        if season_id:
            query["season_id"] = season_id
        
        result = await db.bus_staff.replace_one(
            query,
            staff_doc,
            upsert=True
        )
        
        logging.info(f"Saved staff config for {config.bus_number}: Driver={config.driver_name}, Counselor={config.counselor_name}")
        
        return {
            "status": "success",
            "message": f"Saved configuration for {config.bus_number}",
            "bus_number": config.bus_number,
            "driver_name": config.driver_name,
            "counselor_name": config.counselor_name,
            "was_update": result.modified_count > 0
        }
    except Exception as e:
        logging.error(f"Error saving bus staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bus-staff/{bus_number}")
async def delete_bus_staff(bus_number: str):
    """Delete bus staff configuration from the active season"""
    import urllib.parse
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        query = {"bus_number": decoded_bus}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id
        
        result = await db.bus_staff.delete_one(query)
        
        if result.deleted_count > 0:
            return {
                "status": "success",
                "message": f"Deleted configuration for {decoded_bus}"
            }
        else:
            raise HTTPException(status_code=404, detail="Bus staff configuration not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting bus staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/bus-assigned-staff")
async def get_all_bus_assigned_staff():
    """Get all assigned staff members for the active season"""
    try:
        query = {}
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id
        
        staff = await db.bus_assigned_staff.find(query).to_list(None)
        result = []
        for s in staff:
            result.append({
                "id": str(s.get("_id", "")),
                "staff_name": s.get("staff_name"),
                "bus_number": s.get("bus_number"),
                "session": s.get("session"),
                "created_at": s.get("created_at"),
            })
        return {"status": "success", "assigned_staff": result, "count": len(result)}
    except Exception as e:
        logging.error(f"Error getting assigned staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/route-order/{bus_number}")
async def get_route_order(bus_number: str):
    """Get custom route order for a bus"""
    import urllib.parse
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        season_id = await get_active_season_id()
        
        query = {"bus_number": decoded_bus}
        if season_id:
            query["season_id"] = season_id
        
        order = await db.route_orders.find_one(query)
        
        if order:
            return {
                "status": "success",
                "bus_number": decoded_bus,
                "am_order": order.get("am_order", []),
                "pm_order": order.get("pm_order", []),
                "updated_at": order.get("updated_at")
            }
        else:
            return {
                "status": "success",
                "bus_number": decoded_bus,
                "am_order": [],
                "pm_order": [],
                "updated_at": None
            }
    except Exception as e:
        logging.error(f"Error getting route order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/route-order")
async def save_route_order(order_data: RouteOrderSave):
    """Save custom route order for a bus"""
    try:
        season_id = await get_active_season_id()
        
        query = {"bus_number": order_data.bus_number}
        if season_id:
            query["season_id"] = season_id
        
        # Get existing order or create new
        existing = await db.route_orders.find_one(query)
        
        update_field = f"{order_data.route_type}_order"
        
        if existing:
            await db.route_orders.update_one(
                query,
                {"$set": {
                    update_field: order_data.stop_order,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            new_order = {
                "bus_number": order_data.bus_number,
                "am_order": order_data.stop_order if order_data.route_type == "am" else [],
                "pm_order": order_data.stop_order if order_data.route_type == "pm" else [],
                "season_id": season_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.route_orders.insert_one(new_order)
        
        logging.info(f"Saved {order_data.route_type.upper()} route order for {order_data.bus_number}: {len(order_data.stop_order)} stops")
        return {
            "status": "success",
            "message": f"Saved {order_data.route_type.upper()} route order for {order_data.bus_number}"
        }
    except Exception as e:
        logging.error(f"Error saving route order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/route-order/{bus_number}")
async def delete_route_order(bus_number: str):
    """Delete custom route order for a bus (revert to auto-generated)"""
    import urllib.parse
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        season_id = await get_active_season_id()
        
        query = {"bus_number": decoded_bus}
        if season_id:
            query["season_id"] = season_id
        
        result = await db.route_orders.delete_one(query)
        
        if result.deleted_count > 0:
            return {"status": "success", "message": f"Route order deleted for {decoded_bus}"}
        else:
            return {"status": "success", "message": "No custom route order found"}
    except Exception as e:
        logging.error(f"Error deleting route order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/search-address")
async def search_address(address: str):
    """Search for an address and find which buses service that area"""
    try:
        if not address or len(address.strip()) < 3:
            raise HTTPException(status_code=400, detail="Address too short")
        
        # Geocode the address
        POSITIONSTACK_KEY = os.environ.get("POSITIONSTACK_API_KEY")
        GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
        
        lat = None
        lng = None
        formatted_address = address
        
        # Try Google Maps first
        if GOOGLE_MAPS_KEY:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"https://maps.googleapis.com/maps/api/geocode/json",
                        params={"address": address, "key": GOOGLE_MAPS_KEY}
                    )
                    data = response.json()
                    if data.get("status") == "OK" and data.get("results"):
                        location = data["results"][0]["geometry"]["location"]
                        lat = location["lat"]
                        lng = location["lng"]
                        formatted_address = data["results"][0]["formatted_address"]
            except Exception as e:
                logging.warning(f"Google geocoding failed: {e}")
        
        # Fallback to PositionStack
        if lat is None and POSITIONSTACK_KEY:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"http://api.positionstack.com/v1/forward",
                        params={"access_key": POSITIONSTACK_KEY, "query": address}
                    )
                    data = response.json()
                    if data.get("data") and len(data["data"]) > 0:
                        result = data["data"][0]
                        lat = result["latitude"]
                        lng = result["longitude"]
                        formatted_address = result.get("label", address)
            except Exception as e:
                logging.warning(f"PositionStack geocoding failed: {e}")
        
        if lat is None or lng is None:
            raise HTTPException(status_code=404, detail="Address not found")
        
        # Find buses that service this area
        # Check bus zones that contain this point
        season_id = await get_active_season_id()
        zone_query = {}
        if season_id:
            zone_query["season_id"] = season_id
        
        zones = await db.bus_zones.find(zone_query).to_list(None)
        
        servicing_buses = []
        for zone in zones:
            points = zone.get("points", [])
            if points and point_in_polygon(lat, lng, points):
                servicing_buses.append({
                    "bus_number": zone.get("bus_number"),
                    "zone_name": zone.get("name", ""),
                    "color": zone.get("color", "")
                })
        
        # Also check nearby campers to find buses in the area
        nearby_buses = set()
        campers = await db.campers.find({
            "location.latitude": {"$exists": True, "$ne": 0},
            "location.longitude": {"$exists": True, "$ne": 0}
        }).to_list(None)
        
        for camper in campers:
            clat = camper.get("location", {}).get("latitude", 0)
            clng = camper.get("location", {}).get("longitude", 0)
            
            # Check if within ~0.5 mile radius
            distance = ((clat - lat) ** 2 + (clng - lng) ** 2) ** 0.5
            if distance < 0.01:  # Roughly 0.5-1 mile
                am_bus = camper.get("am_bus_number", "")
                pm_bus = camper.get("pm_bus_number", "")
                if am_bus and am_bus.startswith("Bus"):
                    nearby_buses.add(am_bus)
                if pm_bus and pm_bus.startswith("Bus"):
                    nearby_buses.add(pm_bus)
        
        return {
            "status": "success",
            "address": formatted_address,
            "location": {"lat": lat, "lng": lng},
            "servicing_buses": servicing_buses,
            "nearby_buses": sorted(list(nearby_buses))
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error searching address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bus-assigned-staff/by-bus/{bus_number}")
async def get_assigned_staff_by_bus(bus_number: str):
    """Get all assigned staff on a specific bus for the active season"""
    import urllib.parse
    try:
        decoded_bus = urllib.parse.unquote(bus_number)
        query = {"bus_number": decoded_bus}
        
        season_id = await get_active_season_id()
        if season_id:
            query["season_id"] = season_id
        
        staff = await db.bus_assigned_staff.find(query).to_list(None)
        result = []
        for s in staff:
            result.append({
                "id": str(s.get("_id", "")),
                "staff_name": s.get("staff_name"),
                "bus_number": s.get("bus_number"),
                "session": s.get("session"),
                "created_at": s.get("created_at"),
            })
        return {"status": "success", "assigned_staff": result, "count": len(result)}
    except Exception as e:
        logging.error(f"Error getting assigned staff by bus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bus-assigned-staff")
async def create_bus_assigned_staff(staff_data: BusAssignedStaffCreate):
    """Create a new assigned staff member on a bus"""
    try:
        season_id = await get_active_season_id()
        
        staff_doc = {
            "staff_name": staff_data.staff_name.strip(),
            "bus_number": staff_data.bus_number,
            "session": staff_data.session or "Full Season- 5 Days",
            "season_id": season_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        result = await db.bus_assigned_staff.insert_one(staff_doc)
        staff_doc["id"] = str(result.inserted_id)
        if "_id" in staff_doc:
            del staff_doc["_id"]
        
        logging.info(f"Created assigned staff '{staff_data.staff_name}' on {staff_data.bus_number}")
        return {"status": "success", "assigned_staff": staff_doc}
    except Exception as e:
        logging.error(f"Error creating assigned staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bus-assigned-staff/{staff_id}")
async def delete_bus_assigned_staff(staff_id: str):
    """Delete an assigned staff member"""
    from bson import ObjectId
    try:
        result = await db.bus_assigned_staff.delete_one({"_id": ObjectId(staff_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Assigned staff not found")
        
        logging.info(f"Deleted assigned staff: {staff_id}")
        return {"status": "success", "message": "Assigned staff deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting assigned staff: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/staff-addresses")
async def get_all_staff_addresses():
    """Get all staff with addresses for the active season"""
    try:
        season_id = await get_active_season_id()
        query = {}
        if season_id:
            query["season_id"] = season_id
        
        staff_list = await db.staff_addresses.find(query).to_list(None)
        result = []
        for s in staff_list:
            result.append({
                "id": str(s.get("_id", "")),
                "name": s.get("name"),
                "address": s.get("address"),
                "lat": s.get("lat"),
                "lng": s.get("lng"),
                "bus_number": s.get("bus_number"),
                "session": s.get("session"),
                "zone_info": s.get("zone_info"),
                "nearby_buses": s.get("nearby_buses", []),
                "created_at": s.get("created_at"),
            })
        return {"status": "success", "staff": result, "count": len(result)}
    except Exception as e:
        logging.error(f"Error getting staff addresses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/staff-addresses")
async def create_staff_address(staff_data: StaffAddressCreate):
    """Create a new staff member with address - geocodes and finds zone"""
    try:
        season_id = await get_active_season_id()
        
        # Geocode the address
        lat = None
        lng = None
        formatted_address = staff_data.address
        
        GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
        POSITIONSTACK_KEY = os.environ.get("POSITIONSTACK_API_KEY")
        
        # Try Google Maps first
        if GOOGLE_MAPS_KEY:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"https://maps.googleapis.com/maps/api/geocode/json",
                        params={"address": staff_data.address, "key": GOOGLE_MAPS_KEY}
                    )
                    data = response.json()
                    if data.get("status") == "OK" and data.get("results"):
                        location = data["results"][0]["geometry"]["location"]
                        lat = location["lat"]
                        lng = location["lng"]
                        formatted_address = data["results"][0]["formatted_address"]
            except Exception as e:
                logging.warning(f"Google geocoding failed for staff: {e}")
        
        # Fallback to PositionStack
        if lat is None and POSITIONSTACK_KEY:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"http://api.positionstack.com/v1/forward",
                        params={"access_key": POSITIONSTACK_KEY, "query": staff_data.address}
                    )
                    data = response.json()
                    if data.get("data") and len(data["data"]) > 0:
                        result = data["data"][0]
                        lat = result["latitude"]
                        lng = result["longitude"]
                        formatted_address = result.get("label", staff_data.address)
            except Exception as e:
                logging.warning(f"PositionStack geocoding failed for staff: {e}")
        
        if lat is None or lng is None:
            raise HTTPException(status_code=400, detail="Could not geocode address")
        
        # Find which zone this staff falls into
        zone_query = {}
        if season_id:
            zone_query["season_id"] = season_id
        zones = await db.bus_zones.find(zone_query).to_list(None)
        
        zone_info = None
        nearby_buses = []
        
        for zone in zones:
            points = zone.get("points", [])
            if points and point_in_polygon(lat, lng, points):
                zone_info = {
                    "bus_number": zone.get("bus_number"),
                    "zone_name": zone.get("name", ""),
                    "color": zone.get("color", "")
                }
                break
        
        # Find nearby buses (within ~1 mile)
        campers = await db.campers.find({
            "location.latitude": {"$exists": True, "$ne": 0},
            "location.longitude": {"$exists": True, "$ne": 0}
        }).to_list(None)
        
        nearby_bus_set = set()
        for camper in campers:
            clat = camper.get("location", {}).get("latitude", 0)
            clng = camper.get("location", {}).get("longitude", 0)
            distance = ((clat - lat) ** 2 + (clng - lng) ** 2) ** 0.5
            if distance < 0.015:  # ~1 mile
                am_bus = camper.get("am_bus_number", "")
                pm_bus = camper.get("pm_bus_number", "")
                if am_bus and am_bus.startswith("Bus"):
                    nearby_bus_set.add(am_bus)
                if pm_bus and pm_bus.startswith("Bus"):
                    nearby_bus_set.add(pm_bus)
        
        nearby_buses = sorted(list(nearby_bus_set), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        # Auto-assign bus if staff falls within a zone (unless explicitly set by user)
        auto_assigned_bus = None
        if zone_info and zone_info.get("bus_number"):
            auto_assigned_bus = zone_info["bus_number"]
        
        staff_doc = {
            "name": staff_data.name.strip(),
            "address": formatted_address,
            "lat": lat,
            "lng": lng,
            "bus_number": staff_data.bus_number or auto_assigned_bus,  # Use zone bus if not specified
            "session": staff_data.session or "Full Season- 5 Days",
            "zone_info": zone_info,
            "nearby_buses": nearby_buses,
            "season_id": season_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        result = await db.staff_addresses.insert_one(staff_doc)
        staff_doc["id"] = str(result.inserted_id)
        if "_id" in staff_doc:
            del staff_doc["_id"]
        
        logging.info(f"Created staff with address: {staff_data.name} at {formatted_address}" + 
                    (f" - Auto-assigned to {auto_assigned_bus}" if auto_assigned_bus and not staff_data.bus_number else ""))
        return {"status": "success", "staff": staff_doc}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating staff address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/staff-addresses/{staff_id}")
async def update_staff_address(staff_id: str, staff_data: StaffAddressUpdate):
    """Update a staff member (typically to assign a bus)"""
    from bson import ObjectId
    try:
        update_fields = {}
        if staff_data.name is not None:
            update_fields["name"] = staff_data.name.strip()
        if staff_data.bus_number is not None:
            update_fields["bus_number"] = staff_data.bus_number
        if staff_data.session is not None:
            update_fields["session"] = staff_data.session
        if staff_data.address is not None:
            # Re-geocode if address changed
            lat = None
            lng = None
            formatted_address = staff_data.address
            
            GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
            if GOOGLE_MAPS_KEY:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(
                            f"https://maps.googleapis.com/maps/api/geocode/json",
                            params={"address": staff_data.address, "key": GOOGLE_MAPS_KEY}
                        )
                        data = response.json()
                        if data.get("status") == "OK" and data.get("results"):
                            location = data["results"][0]["geometry"]["location"]
                            lat = location["lat"]
                            lng = location["lng"]
                            formatted_address = data["results"][0]["formatted_address"]
                except Exception as e:
                    logging.warning(f"Geocoding failed during update: {e}")
            
            if lat and lng:
                update_fields["address"] = formatted_address
                update_fields["lat"] = lat
                update_fields["lng"] = lng
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.staff_addresses.update_one(
            {"_id": ObjectId(staff_id)},
            {"$set": update_fields}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Staff not found")
        
        # Return updated document
        updated = await db.staff_addresses.find_one({"_id": ObjectId(staff_id)})
        return {
            "status": "success",
            "staff": {
                "id": str(updated["_id"]),
                "name": updated.get("name"),
                "address": updated.get("address"),
                "lat": updated.get("lat"),
                "lng": updated.get("lng"),
                "bus_number": updated.get("bus_number"),
                "session": updated.get("session"),
                "zone_info": updated.get("zone_info"),
                "nearby_buses": updated.get("nearby_buses", []),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating staff address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/staff-addresses/{staff_id}")
async def delete_staff_address(staff_id: str):
    """Delete a staff member"""
    from bson import ObjectId
    try:
        result = await db.staff_addresses.delete_one({"_id": ObjectId(staff_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Staff not found")
        
        logging.info(f"Deleted staff address: {staff_id}")
        return {"status": "success", "message": "Staff deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting staff address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/staff-addresses/upload-csv")
async def upload_staff_csv(file: UploadFile = File(...)):
    """Upload CSV with staff names and addresses - bulk import"""
    from fastapi import UploadFile, File
    import io
    try:
        season_id = await get_active_season_id()
        
        # Read CSV content
        content = await file.read()
        text_content = content.decode('utf-8')
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(text_content))
        
        # Normalize column names (handle various formats)
        fieldnames = reader.fieldnames
        name_col = None
        address_col = None
        
        for col in fieldnames:
            col_lower = col.lower().strip()
            if col_lower in ['name', 'staff name', 'staff_name', 'staffname']:
                name_col = col
            elif col_lower in ['address', 'staff address', 'staff_address', 'staffaddress', 'home address', 'home_address']:
                address_col = col
        
        if not name_col or not address_col:
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must have 'Name' and 'Address' columns. Found columns: {fieldnames}"
            )
        
        results = {
            "success": [],
            "failed": [],
            "total": 0
        }
        
        GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
        POSITIONSTACK_KEY = os.environ.get("POSITIONSTACK_API_KEY")
        
        for row in reader:
            results["total"] += 1
            name = row.get(name_col, "").strip()
            address = row.get(address_col, "").strip()
            
            if not name or not address:
                results["failed"].append({
                    "name": name or "Unknown",
                    "address": address or "Missing",
                    "error": "Missing name or address"
                })
                continue
            
            # Geocode the address
            lat = None
            lng = None
            formatted_address = address
            
            if GOOGLE_MAPS_KEY:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(
                            f"https://maps.googleapis.com/maps/api/geocode/json",
                            params={"address": address, "key": GOOGLE_MAPS_KEY}
                        )
                        data = response.json()
                        if data.get("status") == "OK" and data.get("results"):
                            location = data["results"][0]["geometry"]["location"]
                            lat = location["lat"]
                            lng = location["lng"]
                            formatted_address = data["results"][0]["formatted_address"]
                except Exception as e:
                    logging.warning(f"Geocoding failed for {name}: {e}")
            
            if lat is None and POSITIONSTACK_KEY:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(
                            f"http://api.positionstack.com/v1/forward",
                            params={"access_key": POSITIONSTACK_KEY, "query": address}
                        )
                        data = response.json()
                        if data.get("data") and len(data["data"]) > 0:
                            result_data = data["data"][0]
                            lat = result_data["latitude"]
                            lng = result_data["longitude"]
                            formatted_address = result_data.get("label", address)
                except Exception as e:
                    logging.warning(f"PositionStack failed for {name}: {e}")
            
            if lat is None or lng is None:
                results["failed"].append({
                    "name": name,
                    "address": address,
                    "error": "Could not geocode address"
                })
                continue
            
            # Find zone info
            zone_query = {}
            if season_id:
                zone_query["season_id"] = season_id
            zones = await db.bus_zones.find(zone_query).to_list(None)
            
            zone_info = None
            for zone in zones:
                points = zone.get("points", [])
                if points and point_in_polygon(lat, lng, points):
                    zone_info = {
                        "bus_number": zone.get("bus_number"),
                        "zone_name": zone.get("name", ""),
                        "color": zone.get("color", "")
                    }
                    break
            
            # Find nearby buses
            campers = await db.campers.find({
                "location.latitude": {"$exists": True, "$ne": 0}
            }).to_list(None)
            
            nearby_bus_set = set()
            for camper in campers:
                clat = camper.get("location", {}).get("latitude", 0)
                clng = camper.get("location", {}).get("longitude", 0)
                distance = ((clat - lat) ** 2 + (clng - lng) ** 2) ** 0.5
                if distance < 0.015:
                    am_bus = camper.get("am_bus_number", "")
                    pm_bus = camper.get("pm_bus_number", "")
                    if am_bus and am_bus.startswith("Bus"):
                        nearby_bus_set.add(am_bus)
                    if pm_bus and pm_bus.startswith("Bus"):
                        nearby_bus_set.add(pm_bus)
            
            nearby_buses = sorted(list(nearby_bus_set), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
            
            # Auto-assign bus if staff falls within a zone
            auto_assigned_bus = None
            if zone_info and zone_info.get("bus_number"):
                auto_assigned_bus = zone_info["bus_number"]
            
            # Create staff document
            staff_doc = {
                "name": name,
                "address": formatted_address,
                "lat": lat,
                "lng": lng,
                "bus_number": auto_assigned_bus,  # Auto-assign based on zone
                "session": "Full Season- 5 Days",
                "zone_info": zone_info,
                "nearby_buses": nearby_buses,
                "season_id": season_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            insert_result = await db.staff_addresses.insert_one(staff_doc)
            staff_doc["id"] = str(insert_result.inserted_id)
            del staff_doc["_id"]
            
            results["success"].append({
                "name": name,
                "address": formatted_address,
                "auto_assigned": auto_assigned_bus,
                "zone": zone_info.get("bus_number") if zone_info else None,
                "nearby_buses": nearby_buses[:5]
            })
        
        logging.info(f"CSV upload complete: {len(results['success'])} success, {len(results['failed'])} failed")
        return {
            "status": "success",
            "message": f"Imported {len(results['success'])} of {results['total']} staff members",
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error uploading staff CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
