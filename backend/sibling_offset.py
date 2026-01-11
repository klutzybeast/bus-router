"""
Auto-apply sibling offset after sync
"""
from motor.motor_asyncio import AsyncIOMotorClient
import os
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

async def apply_sibling_offset(db):
    """Automatically apply offset to siblings at same address"""
    try:
        # Group by approximate location
        address_groups = defaultdict(list)
        
        campers = await db.campers.find({"location.latitude": {"$ne": 0}}).sort("_id", 1).to_list(None)
        
        # Group by location (rounded to 4 decimals)
        for camper in campers:
            lat_key = round(camper['location']['latitude'], 4)
            lng_key = round(camper['location']['longitude'], 4)
            location_key = f"{lat_key}_{lng_key}"
            address_groups[location_key].append(camper)
        
        # Apply offset to each group with multiple campers
        updated = 0
        for location_key, group in address_groups.items():
            if len(group) > 1:
                # Get original location from first camper
                original_lat = group[0]['location']['latitude']
                original_lng = group[0]['location']['longitude']
                
                for i, camper in enumerate(group):
                    offset = i * 0.00002  # 6 feet per sibling
                    
                    new_lat = original_lat + offset
                    new_lng = original_lng + offset
                    
                    await db.campers.update_one(
                        {"_id": camper['_id']},
                        {"$set": {
                            "location.latitude": new_lat,
                            "location.longitude": new_lng
                        }}
                    )
                    updated += 1
        
        logger.info(f"✓ Applied offset to {updated} siblings at {len([g for g in address_groups.values() if len(g) > 1])} addresses")
        return updated
        
    except Exception as e:
        logger.error(f"Error applying offset: {str(e)}")
        return 0
