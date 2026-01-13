"""Pydantic models for the bus routing application."""

from pydantic import BaseModel
from typing import Optional


class GeoLocation(BaseModel):
    """Geographic location with coordinates and optional address."""
    latitude: float
    longitude: float
    address: Optional[str] = None


class CamperPin(BaseModel):
    """Camper data for map display."""
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
    """Input model for manually adding a camper."""
    first_name: str
    last_name: str
    address: str
    town: str
    zip_code: str
    am_bus_number: Optional[str] = "NONE"
    pm_bus_number: Optional[str] = None
    session: Optional[str] = ""
