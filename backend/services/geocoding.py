"""Geocoding service using Google Maps API."""

import logging
from typing import Optional
from models.schemas import GeoLocation
from services.database import gmaps

logger = logging.getLogger(__name__)


def geocode_address(address: str, town: str = "", zip_code: str = "") -> Optional[GeoLocation]:
    """
    Geocode an address using Google Maps API.
    
    Args:
        address: Street address
        town: Town/city name
        zip_code: ZIP code
        
    Returns:
        GeoLocation object or None if geocoding fails
    """
    try:
        full_address = f"{address}, {town}, {zip_code}" if town else address
        if not full_address.strip():
            return None
        
        result = gmaps.geocode(full_address)
        if result and len(result) > 0:
            location = result[0]['geometry']['location']
            return GeoLocation(
                latitude=location['lat'],
                longitude=location['lng'],
                address=result[0]['formatted_address']
            )
        return None
    except Exception as e:
        logger.error(f"Geocoding error for {full_address}: {str(e)}")
        return None
