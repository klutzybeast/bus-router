"""Shared helper functions used across routers."""

import logging
from typing import Optional, List, Dict
from datetime import datetime
from services.database import db, campminder_api

logger = logging.getLogger(__name__)


async def get_active_season_id() -> Optional[str]:
    """Helper function to get the active season ID"""
    try:
        season = await db.seasons.find_one({"is_active": True})
        if season:
            return str(season["_id"])
        return None
    except Exception as e:
        logging.error(f"Error getting active season ID: {e}")
        return None


async def get_guardian_contacts_cached(campers: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Get guardian contacts using the CampMinder family relationship API.
    Results are cached in MongoDB - but empty results are NOT cached to allow retry.
    IMPORTANT: Only returns actual parents/guardians (PersonType=2), NOT siblings.
    """
    try:
        old_cache_count = await db.campminder_relatives_cache.count_documents({})
        if old_cache_count > 0:
            sample = await db.campminder_relatives_cache.find_one({})
            if sample:
                guardians = sample.get('guardians', [])
                if guardians and 'person_type' not in guardians[0]:
                    logging.info(f"Clearing {old_cache_count} stale cache entries (pre-PersonType fix)")
                    await db.campminder_relatives_cache.delete_many({})

        await db.campminder_relatives_cache.delete_many({"guardians": []})

        result = {}
        unique_keys = set()
        camper_list = []

        for camper in campers:
            first = (camper.get('first_name') or '').strip().lower()
            last = (camper.get('last_name') or '').strip().lower()

            if first and last:
                key = f"{first}_{last}"
                if key not in unique_keys:
                    unique_keys.add(key)
                    camper_list.append({
                        'first_name': camper.get('first_name', '').strip(),
                        'last_name': camper.get('last_name', '').strip(),
                        'key': key
                    })

        if not unique_keys:
            return {}

        cache_cursor = db.campminder_relatives_cache.find({
            "_id": {"$in": list(unique_keys)},
            "guardians.0": {"$exists": True}
        })
        cache_data = await cache_cursor.to_list(length=None)

        cached_keys = set()
        for item in cache_data:
            guardians = item.get('guardians', [])
            if guardians:
                result[item['_id']] = guardians
                cached_keys.add(item['_id'])

        missing_keys = unique_keys - cached_keys

        if missing_keys:
            missing_campers = [c for c in camper_list if c['key'] in missing_keys]
            api_result = await campminder_api.get_parent_contacts_for_campers(missing_campers)

            for key, guardians in api_result.items():
                result[key] = guardians
                if guardians:
                    await db.campminder_relatives_cache.update_one(
                        {"_id": key},
                        {"$set": {
                            "guardians": guardians,
                            "updated_at": datetime.now().isoformat()
                        }},
                        upsert=True
                    )

            for key in missing_keys:
                if key not in result:
                    result[key] = []

        return result

    except Exception as e:
        logging.error(f"Error in guardian lookup: {e}")
        return {}


def point_in_polygon(lat: float, lng: float, polygon: List[Dict]) -> bool:
    """Check if a point is inside a polygon using ray casting algorithm"""
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1

    for i in range(n):
        xi = polygon[i].get("lat", 0)
        yi = polygon[i].get("lng", 0)
        xj = polygon[j].get("lat", 0)
        yj = polygon[j].get("lng", 0)

        if ((yi > lng) != (yj > lng)) and (lat < (xj - xi) * (lng - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside
