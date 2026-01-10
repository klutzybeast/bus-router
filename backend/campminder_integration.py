import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class CampMinderAPI:
    def __init__(self, api_key: str, subscription_key: str, api_url: str):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.api_url = api_url.rstrip('/')
        self.jwt_token = None
        self.token_expiry = None
        self.client_ids = None
    
    async def get_jwt_token(self) -> str:
        """Get JWT token from CampMinder using API key and subscription key"""
        # If token exists and not expiring soon, return it
        if self.jwt_token and self.token_expiry and datetime.now() < self.token_expiry - timedelta(minutes=5):
            return self.jwt_token
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_url}/auth/apikey",
                    headers={
                        "Ocp-Apim-Subscription-Key": self.subscription_key,
                        "Authorization": self.api_key,  # No "Bearer " prefix for this endpoint
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.jwt_token = data.get('Token')
                    self.client_ids = data.get('ClientIDs', '')
                    # JWT expires in 1 hour
                    self.token_expiry = datetime.now() + timedelta(hours=1)
                    logger.info(f"✓ JWT token obtained. ClientIDs: {self.client_ids}")
                    return self.jwt_token
                else:
                    logger.error(f"Failed to get JWT: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error getting JWT: {str(e)}")
            return None
    
    async def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with JWT token"""
        token = await self.get_jwt_token()
        
        if not token:
            raise Exception("Failed to obtain JWT token from CampMinder")
        
        return {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Authorization": f"Bearer {token}",
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
                params['modifiedSince'] = since.isoformat()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_url}/persons",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    logger.info(f"✓ Fetched campers from CampMinder")
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