"""Pydantic models for the bus routing application."""

from pydantic import BaseModel
from typing import Optional, List, Dict


class GeoLocation(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None


class CamperPin(BaseModel):
    first_name: str
    last_name: str
    location: GeoLocation
    am_bus_number: str
    pm_bus_number: str
    bus_color: str
    session: str
    pickup_type: str
    town: Optional[str] = None
    zip_code: Optional[str] = None


class ManualCamperInput(BaseModel):
    first_name: str
    last_name: str
    address: str
    town: str
    zip_code: str
    am_bus_number: Optional[str] = "NONE"
    pm_bus_number: Optional[str] = None
    session: Optional[str] = ""


class SeasonCreate(BaseModel):
    name: str
    year: int
    copy_from_season_id: Optional[str] = None


class SeasonResponse(BaseModel):
    id: str
    name: str
    year: int
    is_active: bool
    camper_count: int
    created_at: str
    archived_at: Optional[str] = None


class BusStaffConfig(BaseModel):
    bus_number: str
    driver_name: str
    counselor_name: str
    home_address: str
    capacity: Optional[int] = None
    location_name: Optional[str] = None


class ShadowCreate(BaseModel):
    shadow_name: str
    camper_id: str
    bus_number: Optional[str] = None


class ShadowUpdate(BaseModel):
    shadow_name: Optional[str] = None
    camper_id: Optional[str] = None


class BusAssignedStaffCreate(BaseModel):
    staff_name: str
    bus_number: str
    session: Optional[str] = "Full Season- 5 Days"


class BusAssignedStaffUpdate(BaseModel):
    staff_name: Optional[str] = None
    bus_number: Optional[str] = None
    session: Optional[str] = None


class RouteOrderSave(BaseModel):
    bus_number: str
    route_type: str
    stop_order: List[str]


class StaffAddressCreate(BaseModel):
    name: str
    address: str
    bus_number: Optional[str] = None
    session: Optional[str] = "Full Season- 5 Days"


class StaffAddressUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    bus_number: Optional[str] = None
    session: Optional[str] = None


class ZonePoint(BaseModel):
    lat: float
    lng: float


class BusZoneCreate(BaseModel):
    bus_number: str
    points: List[ZonePoint]
    name: Optional[str] = None
    color: Optional[str] = None


class BusZoneUpdate(BaseModel):
    points: Optional[List[ZonePoint]] = None
    name: Optional[str] = None
    color: Optional[str] = None


class PickupDropoffRequest(BaseModel):
    pickup_dropoff: str


class BusLocationUpdate(BaseModel):
    bus_number: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None


class BusLoginRequest(BaseModel):
    pin: str


class AttendanceUpdate(BaseModel):
    camper_id: str
    status: str


class BulkAttendanceUpdate(BaseModel):
    bus_number: str
    date: str
    attendance: List[Dict[str, str]]
