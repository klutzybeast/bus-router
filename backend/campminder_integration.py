from typing import List, Dict, Optional
import httpx
import logging
import asyncio
from datetime import datetime, timedelta

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
        """Get JWT token from CampMinder"""
        if self.jwt_token and self.token_expiry and datetime.now() < self.token_expiry - timedelta(minutes=5):
            return self.jwt_token
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_url}/auth/apikey",
                    headers={
                        "Ocp-Apim-Subscription-Key": self.subscription_key,
                        "Authorization": self.api_key,
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.jwt_token = data.get('Token')
                    self.client_ids = data.get('ClientIDs', '')
                    self.token_expiry = datetime.now() + timedelta(hours=1)
                    logger.info(f"✓ JWT obtained. ClientIDs: {self.client_ids}")
                    return self.jwt_token
                else:
                    logger.error(f"Failed to get JWT: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error getting JWT: {str(e)}")
            return None
    
    async def get_auth_headers(self) -> Dict[str, str]:
        """Get auth headers with JWT token"""
        token = await self.get_jwt_token()
        if not token:
            raise Exception("Failed to obtain JWT token")
        
        return {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def get_all_persons(self, season_id: int = 2026) -> List[Dict]:
        """Fetch all persons with pagination"""
        all_persons = []
        page = 1
        
        try:
            headers = await self.get_auth_headers()
            
            while True:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(
                        f"{self.api_url}/persons",
                        headers=headers,
                        params={
                            'clientid': self.client_ids or '241',
                            'pagenumber': page,
                            'pagesize': 1000,
                            'includecamperdetails': 'true',
                            'includehouseholddetails': 'true',
                            'seasonid': season_id
                        }
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Error fetching persons page {page}: {response.status_code}")
                        break
                    
                    data = response.json()
                    results = data.get('Results', [])
                    all_persons.extend(results)
                    
                    logger.info(f"Fetched page {page}: {len(results)} persons (total: {len(all_persons)})")
                    
                    if not data.get('Next') or len(results) < 1000:
                        break
                    
                    page += 1
                    await asyncio.sleep(0.5)  # Rate limiting
            
            logger.info(f"✓ Fetched total of {len(all_persons)} persons")
            return all_persons
        
        except Exception as e:
            logger.error(f"Error fetching persons: {str(e)}")
            return all_persons
    
    async def get_person_custom_fields(self, person_id: int, season_id: int = 2026) -> List[Dict]:
        """Get custom fields for a specific person"""
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_url}/persons/{person_id}/custom-fields",
                    headers=headers,
                    params={
                        'clientid': self.client_ids or '241',
                        'pagenumber': 1,
                        'pagesize': 100,
                        'seasonid': season_id
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('Results', [])
                else:
                    return []
        except Exception as e:
            logger.error(f"Error getting custom fields for person {person_id}: {str(e)}")
            return []
    
    async def get_campers_with_transportation(self, season_id: int = 2026) -> List[Dict]:
        """Get all campers with their transportation custom fields"""
        # First get all persons
        all_persons = await self.get_all_persons(season_id)
        
        # Filter for campers only (Age < 18)
        campers = [p for p in all_persons if p.get('CamperDetails') and p.get('Age', 100) < 18]
        
        logger.info(f"Found {len(campers)} campers out of {len(all_persons)} persons")
        
        # For efficiency, only get custom fields for first 100 campers in testing
        # In production, you'd batch this
        campers_with_fields = []
        
        for i, camper in enumerate(campers[:100]):
            custom_fields = await self.get_person_custom_fields(camper['ID'], season_id)
            
            # Map custom fields to dictionary
            fields_dict = {}
            for field in custom_fields:
                fields_dict[field['Id']] = field['Value']
            
            camper['CustomFields'] = fields_dict
            campers_with_fields.append(camper)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Fetched custom fields for {i + 1}/{len(campers[:100])} campers")
                await asyncio.sleep(0.5)
        
        return campers_with_fields
    
    async def update_camper_bus_assignment(self, camper_id: str, bus_number: int) -> bool:
        """Update bus assignment in CampMinder - placeholder for now"""
        logger.info(f"Would update camper {camper_id} to Bus #{bus_number}")
        return True
    
    async def bulk_update_bus_assignments(self, assignments: List[Dict[str, int]]) -> Dict[str, bool]:
        """Bulk update bus assignments - placeholder"""
        return {a['camper_id']: True for a in assignments}
