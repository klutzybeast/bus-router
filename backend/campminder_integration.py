import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class CampMinderAPI:
    def __init__(self, api_key: str, subscription_key: str, api_url: str):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.api_url = api_url.rstrip('/')
        self.token = None
        self.token_expiry = None
    
    async def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with subscription key"""
        return {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def update_camper_bus_assignment(self, camper_id: str, bus_number: int) -> bool:
        """Update bus assignment in CampMinder"""
        try:
            headers = await self.get_auth_headers()
            
            # CampMinder API endpoint for updating camper transportation
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.api_url}/api/entity/person/camper/{camper_id}",
                    headers=headers,
                    json={
                        "2026Transportation M AM Bus": f"Bus #{bus_number:02d}",
                        "2026Transportation M PM Bus": f"Bus #{bus_number:02d}"
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully updated bus assignment for camper {camper_id} to Bus #{bus_number}")
                    return True
                else:
                    logger.error(f"Failed to update camper {camper_id}: {response.status_code} - {response.text}")
                    return False
        
        except Exception as e:
            logger.error(f"Error updating camper {camper_id} in CampMinder: {str(e)}")
            return False
    
    async def get_new_campers(self, since: Optional[datetime] = None) -> List[Dict]:
        """Fetch new campers from CampMinder"""
        try:
            headers = await self.get_auth_headers()
            
            params = {}
            if since:
                params['since'] = since.isoformat()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_url}/api/entity/person/camper/GetCampers",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to fetch campers: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching campers from CampMinder: {str(e)}")
            return []
    
    async def bulk_update_bus_assignments(self, assignments: List[Dict[str, int]]) -> Dict[str, bool]:
        """Bulk update multiple camper bus assignments"""
        results = {}
        
        for assignment in assignments:
            camper_id = assignment['camper_id']
            bus_number = assignment['bus_number']
            
            success = await self.update_camper_bus_assignment(camper_id, bus_number)
            results[camper_id] = success
            
            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        return results