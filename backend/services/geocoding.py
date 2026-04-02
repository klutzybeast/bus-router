"""Geocoding service with caching and multiple providers."""

import logging
import requests
from typing import Optional
from models.schemas import GeoLocation
from services.database import db, gmaps, POSITIONSTACK_API_KEY

logger = logging.getLogger(__name__)

# In-memory cache for current session
_geocode_memory_cache = {}


def normalize_address(address: str, town: str = "", zip_code: str = "") -> str:
    """Normalize address for consistent cache keys"""
    full = f"{address}, {town}, {zip_code}" if town else address
    normalized = ' '.join(full.lower().split())
    return normalized


async def get_cached_geocode(address_key: str) -> Optional[dict]:
    """Check MongoDB cache for geocoded address"""
    try:
        if address_key in _geocode_memory_cache:
            return _geocode_memory_cache[address_key]

        cached = await db.geocode_cache.find_one({"address_key": address_key})
        if cached and cached.get('latitude') and cached.get('longitude'):
            _geocode_memory_cache[address_key] = {
                'latitude': cached['latitude'],
                'longitude': cached['longitude'],
                'formatted_address': cached.get('formatted_address', '')
            }
            return _geocode_memory_cache[address_key]
        return None
    except Exception as e:
        logging.error(f"Cache lookup error: {e}")
        return None


async def save_geocode_cache(address_key: str, latitude: float, longitude: float, formatted_address: str, source: str):
    """Save geocoded result to MongoDB cache"""
    from datetime import datetime, timezone
    try:
        await db.geocode_cache.update_one(
            {"address_key": address_key},
            {
                "$set": {
                    "address_key": address_key,
                    "latitude": latitude,
                    "longitude": longitude,
                    "formatted_address": formatted_address,
                    "source": source,
                    "cached_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
        _geocode_memory_cache[address_key] = {
            'latitude': latitude,
            'longitude': longitude,
            'formatted_address': formatted_address
        }
        logging.info(f"Cached geocode for: {address_key[:50]}... (source: {source})")
    except Exception as e:
        logging.error(f"Cache save error: {e}")


def geocode_with_google(full_address: str) -> Optional[dict]:
    """Geocode using Google Maps API"""
    if not gmaps:
        return None
    try:
        result = gmaps.geocode(full_address)
        if result and len(result) > 0:
            location = result[0]['geometry']['location']
            return {
                'latitude': location['lat'],
                'longitude': location['lng'],
                'formatted_address': result[0]['formatted_address']
            }
    except Exception as e:
        logging.error(f"Google geocoding error for {full_address}: {str(e)}")
    return None


def geocode_with_positionstack(full_address: str) -> Optional[dict]:
    """Geocode using PositionStack API (free backup)"""
    if not POSITIONSTACK_API_KEY:
        return None
    try:
        response = requests.get(
            "http://api.positionstack.com/v1/forward",
            params={
                "access_key": POSITIONSTACK_API_KEY,
                "query": full_address,
                "limit": 1
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                result = data['data'][0]
                return {
                    'latitude': result['latitude'],
                    'longitude': result['longitude'],
                    'formatted_address': result.get('label', full_address)
                }
    except Exception as e:
        logging.error(f"PositionStack geocoding error for {full_address}: {str(e)}")
    return None


def geocode_address(address: str, town: str = "", zip_code: str = "") -> Optional[GeoLocation]:
    """Synchronous geocode function (for backward compatibility)."""
    full_address = f"{address}, {town}, {zip_code}" if town else address
    if not full_address.strip():
        return None

    result = geocode_with_google(full_address)
    if result:
        return GeoLocation(
            latitude=result['latitude'],
            longitude=result['longitude'],
            address=result['formatted_address']
        )

    result = geocode_with_positionstack(full_address)
    if result:
        return GeoLocation(
            latitude=result['latitude'],
            longitude=result['longitude'],
            address=result['formatted_address']
        )

    return None


async def geocode_address_cached(address: str, town: str = "", zip_code: str = "") -> Optional[GeoLocation]:
    """Geocode address with caching - ALWAYS use this for batch operations."""
    full_address = f"{address}, {town}, {zip_code}" if town else address
    if not full_address.strip():
        return None

    address_key = normalize_address(address, town, zip_code)

    cached = await get_cached_geocode(address_key)
    if cached:
        logging.debug(f"Cache HIT for: {address_key[:50]}...")
        return GeoLocation(
            latitude=cached['latitude'],
            longitude=cached['longitude'],
            address=cached.get('formatted_address', full_address)
        )

    logging.info(f"Cache MISS - geocoding: {address_key[:50]}...")

    result = geocode_with_google(full_address)
    if result:
        await save_geocode_cache(address_key, result['latitude'], result['longitude'], result['formatted_address'], 'google')
        return GeoLocation(
            latitude=result['latitude'],
            longitude=result['longitude'],
            address=result['formatted_address']
        )

    result = geocode_with_positionstack(full_address)
    if result:
        await save_geocode_cache(address_key, result['latitude'], result['longitude'], result['formatted_address'], 'positionstack')
        return GeoLocation(
            latitude=result['latitude'],
            longitude=result['longitude'],
            address=result['formatted_address']
        )

    logging.warning(f"All geocoding failed for: {full_address}")
    return None


def get_geocode_memory_cache_size() -> int:
    """Return the size of the in-memory geocode cache."""
    return len(_geocode_memory_cache)
