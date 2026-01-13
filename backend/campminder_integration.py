from typing import List, Dict, Optional, Any
import httpx
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CampMinderAPI:
    """
    CampMinder API Integration for Bus Route Management
    
    Integrates with:
    - Custom Field API for AM/PM bus assignments
    - Day Travel API for transportation assignments
    - Camper Data API for camper information
    """
    
    def __init__(self, api_key: str, subscription_key: str, api_url: str):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.api_url = api_url.rstrip('/')
        self.jwt_token = None
        self.token_expiry = None
        self.client_ids = None
        
        # Cache for field definitions
        self.am_bus_field_id = None
        self.pm_bus_field_id = None
        self.field_definitions = {}
    
    async def get_jwt_token(self) -> Optional[str]:
        """
        Authenticate with CampMinder API and get JWT token
        Endpoint: /api/security/ section
        """
        if self.jwt_token and self.token_expiry and datetime.now() < self.token_expiry - timedelta(minutes=5):
            return self.jwt_token
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try the auth/apikey endpoint first
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
        """Get authentication headers with JWT token"""
        token = await self.get_jwt_token()
        if not token:
            raise Exception("Failed to obtain JWT token")
        
        return {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def get_field_definitions(self) -> Dict[str, Any]:
        """
        Step 2: Retrieve Custom Field Definitions
        Tries multiple endpoint variations for compatibility
        
        Identifies:
        - AM Bus custom field ID
        - PM Bus custom field ID
        """
        if self.field_definitions:
            return self.field_definitions
        
        try:
            headers = await self.get_auth_headers()
            
            # Try multiple endpoint variations
            endpoint_variations = [
                "/entity/customfield/GetFieldDefs",
                "/customfield/GetFieldDefs",
                "/api/entity/customfield/GetFieldDefs",
                "/customfield",
            ]
            
            response = None
            async with httpx.AsyncClient(timeout=30.0) as client:
                for endpoint in endpoint_variations:
                    try:
                        response = await client.get(
                            f"{self.api_url}{endpoint}",
                            headers=headers,
                            params={
                                'clientid': self.client_ids or '241'
                            }
                        )
                        if response.status_code == 200:
                            logger.info(f"✓ Found working endpoint: {endpoint}")
                            break
                    except Exception:
                        continue
                
                if response is None:
                    # Fallback - try the original
                    response = await client.get(
                        f"{self.api_url}/entity/customfield/GetFieldDefs",
                        headers=headers,
                        params={
                            'clientid': self.client_ids or '241'
                        }
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    fields = data if isinstance(data, list) else data.get('Results', [])
                    
                    for field in fields:
                        field_name = field.get('Name', '').lower()
                        field_id = field.get('Id') or field.get('FieldID')
                        
                        # Look for AM Bus field
                        if 'am' in field_name and 'bus' in field_name:
                            self.am_bus_field_id = field_id
                            logger.info(f"✓ Found AM Bus field: ID={field_id}, Name={field.get('Name')}")
                        
                        # Look for PM Bus field
                        if 'pm' in field_name and 'bus' in field_name:
                            self.pm_bus_field_id = field_id
                            logger.info(f"✓ Found PM Bus field: ID={field_id}, Name={field.get('Name')}")
                        
                        # Store all field definitions
                        self.field_definitions[field_id] = field
                    
                    logger.info(f"✓ Retrieved {len(fields)} field definitions")
                    return self.field_definitions
                else:
                    logger.error(f"Failed to get field definitions: {response.status_code} - {response.text}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting field definitions: {str(e)}")
            return {}
    
    async def get_campers(self, season_id: str = "2026") -> List[Dict]:
        """
        Step 3: Get Camper Data
        Endpoint: GET /api/entity/person/camper/GetCampers
        
        Parameters:
        - seasonID: Season year (e.g., '2026')
        
        Extracts: personID, name, address, session_type for each camper
        """
        all_campers = []
        
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.api_url}/api/entity/person/camper/GetCampers",
                    headers=headers,
                    params={
                        'clientid': self.client_ids or '241',
                        'seasonID': season_id,
                        'includeLeads': 'false'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    campers = data if isinstance(data, list) else data.get('Results', data.get('Campers', []))
                    
                    for camper in campers:
                        camper_data = {
                            'personID': camper.get('PersonID') or camper.get('ID') or camper.get('personID'),
                            'first_name': camper.get('FirstName') or camper.get('firstName', ''),
                            'last_name': camper.get('LastName') or camper.get('lastName', ''),
                            'address': camper.get('Address') or camper.get('StreetAddress', ''),
                            'city': camper.get('City', ''),
                            'state': camper.get('State', ''),
                            'zip': camper.get('Zip') or camper.get('ZipCode', ''),
                            'session_type': camper.get('SessionType') or camper.get('Session', ''),
                            'enrolled_sessions': camper.get('EnrolledSessions', [])
                        }
                        all_campers.append(camper_data)
                    
                    logger.info(f"✓ Retrieved {len(all_campers)} campers")
                    return all_campers
                else:
                    logger.error(f"Failed to get campers: {response.status_code} - {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error getting campers: {str(e)}")
            return []
    
    async def get_custom_transportation_fields(self, person_ids: List[str], season_id: str = "2026") -> Dict[str, Dict]:
        """
        Step 4: Get Custom Transportation Fields
        Endpoint: GET /api/entity/customfield/GetEntityFieldContainers
        
        Parameters:
        - Keys: Comma-delimited list of "objectID" (personID) and "objectTypeFlag"
        - fieldIDs: Optional - comma-delimited list of field IDs (AM Bus, PM Bus)
        
        Returns: Dict mapping personID to their AM/PM bus values
        """
        # First get field definitions if not cached
        await self.get_field_definitions()
        
        transportation_data = {}
        
        try:
            headers = await self.get_auth_headers()
            
            # Build keys parameter - format: "personID|objectTypeFlag"
            # objectTypeFlag for campers is typically 1
            keys = ",".join([f"{pid}|1" for pid in person_ids[:100]])  # Batch limit
            
            # Build fieldIDs parameter if we have them
            field_ids = []
            if self.am_bus_field_id:
                field_ids.append(str(self.am_bus_field_id))
            if self.pm_bus_field_id:
                field_ids.append(str(self.pm_bus_field_id))
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    'clientid': self.client_ids or '241',
                    'Keys': keys
                }
                
                if field_ids:
                    params['fieldIDs'] = ",".join(field_ids)
                
                response = await client.get(
                    f"{self.api_url}/api/entity/customfield/GetEntityFieldContainers",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    containers = data if isinstance(data, list) else data.get('Results', [])
                    
                    for container in containers:
                        person_id = str(container.get('ObjectID') or container.get('PersonID', ''))
                        fields = container.get('Fields', container.get('CustomFields', []))
                        
                        am_bus = ''
                        pm_bus = ''
                        
                        for field in fields:
                            field_id = field.get('FieldID') or field.get('Id')
                            value = field.get('Value', '')
                            
                            # Check if this is AM or PM bus field
                            if field_id == self.am_bus_field_id:
                                am_bus = value if value and value.lower() != 'none' else ''
                            elif field_id == self.pm_bus_field_id:
                                pm_bus = value if value and value.lower() != 'none' else ''
                            else:
                                # Try to identify by field name
                                field_name = (field.get('Name') or field.get('FieldName', '')).lower()
                                if 'am' in field_name and 'bus' in field_name:
                                    am_bus = value if value and value.lower() != 'none' else ''
                                elif 'pm' in field_name and 'bus' in field_name:
                                    pm_bus = value if value and value.lower() != 'none' else ''
                        
                        transportation_data[person_id] = {
                            'am_bus': am_bus,
                            'pm_bus': pm_bus
                        }
                    
                    logger.info(f"✓ Retrieved transportation fields for {len(transportation_data)} campers")
                    return transportation_data
                else:
                    logger.error(f"Failed to get custom fields: {response.status_code} - {response.text}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting custom fields: {str(e)}")
            return {}
    
    async def get_transportation_assignments(self, season_id: str = "2026") -> List[Dict]:
        """
        Step 5: Get Transportation Assignments
        Endpoint: GET /api/travel/day/transportationassignment/season/{seasonId}
        
        Parameters:
        - seasonId: The camp season ID
        
        Returns: List of transportation assignments
        """
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.api_url}/api/travel/day/transportationassignment/season/{season_id}",
                    headers=headers,
                    params={
                        'clientid': self.client_ids or '241'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assignments = data if isinstance(data, list) else data.get('Results', data.get('Assignments', []))
                    logger.info(f"✓ Retrieved {len(assignments)} transportation assignments")
                    return assignments
                else:
                    logger.error(f"Failed to get transportation assignments: {response.status_code} - {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error getting transportation assignments: {str(e)}")
            return []
    
    def parse_session_type(self, session_type: str, enrolled_sessions: List = None) -> Dict[str, bool]:
        """
        Step 6: Parse Session Types to determine AM/PM eligibility
        
        Returns:
        - has_am: True if camper has AM session
        - has_pm: True if camper has PM session
        """
        session_lower = (session_type or '').lower()
        
        # Check enrolled sessions list if available
        if enrolled_sessions:
            sessions_str = ' '.join([str(s).lower() for s in enrolled_sessions])
            session_lower = f"{session_lower} {sessions_str}"
        
        # Full day sessions (both AM and PM)
        full_day_keywords = ['full season', 'full day', 'half season', 'flex', '5 days', '5-day', 'full time']
        is_full_day = any(kw in session_lower for kw in full_day_keywords)
        
        # AM-only sessions
        am_only_keywords = ['am only', 'am session', 'morning only', 'am-only']
        is_am_only = any(kw in session_lower for kw in am_only_keywords) and not is_full_day
        
        # PM-only sessions
        pm_only_keywords = ['pm only', 'pm session', 'afternoon only', 'pm-only']
        is_pm_only = any(kw in session_lower for kw in pm_only_keywords) and not is_full_day
        
        if is_am_only:
            return {'has_am': True, 'has_pm': False}
        elif is_pm_only:
            return {'has_am': False, 'has_pm': True}
        else:
            # Default to full day (both AM and PM)
            return {'has_am': True, 'has_pm': True}
    
    async def get_all_campers_with_bus_data(self, season_id: str = "2026") -> List[Dict]:
        """
        Main integration function - combines all API calls
        
        Returns campers with properly formatted bus data following display rules:
        - Only show AM bus if camper has AM session
        - Only show PM bus if camper has PM session
        - Never show "None" - leave blank instead
        """
        logger.info(f"Starting CampMinder API sync for season {season_id}")
        
        # Step 1: Get JWT token (done in each request)
        token = await self.get_jwt_token()
        if not token:
            logger.error("Failed to authenticate with CampMinder API")
            return []
        
        # Step 2: Get field definitions
        await self.get_field_definitions()
        
        # Step 3: Get all campers
        campers = await self.get_campers(season_id)
        if not campers:
            logger.warning("No campers returned from API")
            return []
        
        # Step 4: Get custom transportation fields in batches
        person_ids = [c['personID'] for c in campers if c['personID']]
        transportation_data = {}
        
        # Process in batches of 100
        for i in range(0, len(person_ids), 100):
            batch = person_ids[i:i+100]
            batch_data = await self.get_custom_transportation_fields(batch, season_id)
            transportation_data.update(batch_data)
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Step 5: Get transportation assignments (supplementary)
        transport_assignments = await self.get_transportation_assignments(season_id)
        
        # Build assignment lookup
        assignment_lookup = {}
        for assignment in transport_assignments:
            pid = str(assignment.get('PersonID') or assignment.get('CamperID', ''))
            if pid:
                assignment_lookup[pid] = assignment
        
        # Step 6 & 7: Combine data with session logic
        result_campers = []
        
        for camper in campers:
            person_id = str(camper['personID'])
            
            # Get transportation data from custom fields
            trans_data = transportation_data.get(person_id, {})
            raw_am_bus = trans_data.get('am_bus', '')
            raw_pm_bus = trans_data.get('pm_bus', '')
            
            # Also check transport assignments
            if not raw_am_bus or not raw_pm_bus:
                assignment = assignment_lookup.get(person_id, {})
                if not raw_am_bus:
                    raw_am_bus = assignment.get('AMBus') or assignment.get('AMBusNumber', '')
                if not raw_pm_bus:
                    raw_pm_bus = assignment.get('PMBus') or assignment.get('PMBusNumber', '')
            
            # Parse session type
            session_info = self.parse_session_type(
                camper['session_type'],
                camper.get('enrolled_sessions', [])
            )
            
            # Apply display logic rules
            # Rule: Only show bus if camper has that session AND bus value exists
            am_bus = ''
            pm_bus = ''
            
            # Clean bus values - remove "None", null, etc.
            if raw_am_bus and str(raw_am_bus).lower() not in ['none', 'null', 'n/a', '']:
                if session_info['has_am']:
                    am_bus = raw_am_bus
            
            if raw_pm_bus and str(raw_pm_bus).lower() not in ['none', 'null', 'n/a', '']:
                if session_info['has_pm']:
                    pm_bus = raw_pm_bus
            
            # Build full address
            address_parts = [
                camper['address'],
                camper['city'],
                camper['state'],
                camper['zip']
            ]
            full_address = ', '.join([p for p in address_parts if p])
            
            result_campers.append({
                'personID': person_id,
                'first_name': camper['first_name'],
                'last_name': camper['last_name'],
                'address': full_address,
                'town': camper['city'],
                'zip_code': camper['zip'],
                'session_type': camper['session_type'],
                'has_am_session': session_info['has_am'],
                'has_pm_session': session_info['has_pm'],
                'am_bus_number': am_bus,  # Empty string if no bus or no AM session
                'pm_bus_number': pm_bus   # Empty string if no bus or no PM session
            })
        
        logger.info(f"✓ Processed {len(result_campers)} campers with bus data")
        return result_campers
    
    async def update_camper_bus_assignment(self, camper_id: str, bus_number: str, bus_type: str = 'am') -> bool:
        """Update bus assignment in CampMinder"""
        logger.info(f"Would update camper {camper_id} {bus_type.upper()} to {bus_number}")
        # TODO: Implement actual API call when endpoint is available
        return True
    
    async def bulk_update_bus_assignments(self, assignments: List[Dict]) -> Dict[str, bool]:
        """Bulk update bus assignments"""
        return {a['camper_id']: True for a in assignments}
