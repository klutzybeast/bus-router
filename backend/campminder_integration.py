"""
CampMinder API Integration for Bus Route Management

This module provides integration with CampMinder's WebAPI to retrieve camper
and bus assignment data. The integration supports:

1. Authentication via api.campminder.com/auth/apikey
2. Camper data retrieval via webapi.campminder.com
3. Custom field data for AM/PM bus assignments
4. Family address data for geocoding

Note: Some API endpoints may require specific subscription levels.
The Day Travel API requires separate enablement.

Known Field IDs:
- AM Bus: 20852 (Bus#AM Bus)  
- PM Bus: 20853 (Bus#PM Bus)
"""

from typing import List, Dict, Optional, Any
import httpx
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Bus field IDs discovered from API
AM_BUS_FIELD_ID = 20852  # Bus#AM Bus
PM_BUS_FIELD_ID = 20853  # Bus#PM Bus


class CampMinderAPI:
    """
    CampMinder API Integration for Bus Route Management
    
    Uses the correct API endpoints:
    - Auth: https://api.campminder.com/auth/apikey
    - Data: https://webapi.campminder.com/api/...
    """
    
    def __init__(self, api_key: str, subscription_key: str, api_url: str = None):
        self.api_key = api_key
        self.subscription_key = subscription_key
        # Auth endpoint is on api.campminder.com
        self.auth_url = "https://api.campminder.com"
        # Data endpoints are on webapi.campminder.com
        self.data_url = "https://webapi.campminder.com"
        self.jwt_token = None
        self.token_expiry = None
        self.client_ids = None
        
        # Cache for field definitions
        self.am_bus_field_id = AM_BUS_FIELD_ID
        self.pm_bus_field_id = PM_BUS_FIELD_ID
        self.field_definitions = {}
    
    async def get_jwt_token(self) -> Optional[str]:
        """
        Authenticate with CampMinder API and get JWT token
        Endpoint: GET https://api.campminder.com/auth/apikey
        """
        if self.jwt_token and self.token_expiry and datetime.now() < self.token_expiry - timedelta(minutes=5):
            return self.jwt_token
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.auth_url}/auth/apikey",
                    headers={
                        "Ocp-Apim-Subscription-Key": self.subscription_key,
                        "Authorization": self.api_key,
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.jwt_token = data.get('Token')
                    self.client_ids = data.get('ClientIDs', '241')
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
        Retrieve Custom Field Definitions
        Endpoint: GET /api/entity/customfield/GetFieldDefs
        
        Returns all custom field definitions and identifies AM/PM bus field IDs
        """
        if self.field_definitions:
            return self.field_definitions
        
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/customfield/GetFieldDefs",
                    headers=headers,
                    params={'clientid': self.client_ids or '241'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('Success'):
                        fields = data.get('Result', [])
                        if isinstance(fields, dict):
                            fields = list(fields.values())
                        
                        for field in fields:
                            field_name = field.get('Name', '').lower()
                            field_id = field.get('ID') or field.get('FieldID')
                            
                            # Look for AM Bus field
                            if 'am' in field_name and 'bus' in field_name:
                                self.am_bus_field_id = field_id
                                logger.info(f"✓ Found AM Bus field: ID={field_id}, Name={field.get('Name')}")
                            
                            # Look for PM Bus field
                            if 'pm' in field_name and 'bus' in field_name:
                                self.pm_bus_field_id = field_id
                                logger.info(f"✓ Found PM Bus field: ID={field_id}, Name={field.get('Name')}")
                            
                            # Store all field definitions
                            if field_id:
                                self.field_definitions[field_id] = field
                        
                        logger.info(f"✓ Retrieved {len(fields)} field definitions")
                        return self.field_definitions
                    else:
                        logger.error(f"GetFieldDefs failed: {data.get('ErrorText')}")
                        return {}
                else:
                    logger.error(f"Failed to get field definitions: {response.status_code} - {response.text}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting field definitions: {str(e)}")
            return {}
    
    async def get_active_camper_ids(self, season_id: str = "2026") -> List[int]:
        """
        Get active camper person IDs for a season
        Endpoint: GET /api/entity/person/camper/GetActiveCamper
        """
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/person/camper/GetActiveCamper",
                    headers=headers,
                    params={
                        'clientid': self.client_ids or '241',
                        'seasonID': season_id
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('Success') or data.get('Result'):
                        person_ids = data.get('Result', [])
                        logger.info(f"✓ Retrieved {len(person_ids)} active campers for season {season_id}")
                        return person_ids
                    else:
                        logger.error(f"GetActiveCamper failed: {data.get('ErrorText')}")
                        return []
                else:
                    logger.error(f"Failed to get active campers: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error getting active campers: {str(e)}")
            return []
    
    async def get_persons(self, person_ids: List[int] = None, since: str = None) -> Dict[int, Dict]:
        """
        Get person data (names, etc.)
        Endpoint: GET /api/entity/person/GetPersons
        
        Returns dict mapping person_id -> person data
        """
        try:
            headers = await self.get_auth_headers()
            
            params = {'clientid': self.client_ids or '241'}
            if person_ids:
                params['personIDs'] = ','.join(map(str, person_ids))
            if since:
                params['since'] = since
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/person/GetPersons",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('Result', {})
                    
                    # Result could be dict or list
                    if isinstance(result, dict):
                        persons_list = list(result.values())
                    else:
                        persons_list = result
                    
                    # Convert to dict keyed by person ID
                    persons_dict = {}
                    for person in persons_list:
                        pid = person.get('ID')
                        if pid:
                            persons_dict[pid] = person
                    
                    logger.info(f"✓ Retrieved {len(persons_dict)} persons")
                    return persons_dict
                else:
                    logger.error(f"Failed to get persons: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting persons: {str(e)}")
            return {}
    
    async def get_family_addresses(self, since: str = None) -> Dict[int, List[Dict]]:
        """
        Get family addresses
        Endpoint: GET /api/entity/family/GetFamilyAddresses
        
        Returns dict mapping family_id -> list of addresses
        """
        try:
            headers = await self.get_auth_headers()
            
            params = {'clientid': self.client_ids or '241'}
            if since:
                params['since'] = since
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/family/GetFamilyAddresses",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('Result', {})
                    
                    # Result is dict where values are lists of addresses
                    if isinstance(result, dict):
                        logger.info(f"✓ Retrieved addresses for {len(result)} families")
                        return result
                    else:
                        logger.warning("Unexpected address format")
                        return {}
                else:
                    logger.error(f"Failed to get addresses: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting addresses: {str(e)}")
            return {}
    
    async def get_family_persons(self, person_ids: List[int]) -> Dict[int, int]:
        """
        Get family IDs for persons
        Endpoint: GET /api/entity/family/GetFamilyPersons
        
        Returns dict mapping person_id -> family_id
        """
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/family/GetFamilyPersons",
                    headers=headers,
                    params={
                        'clientid': self.client_ids or '241',
                        'personIDs': ','.join(map(str, person_ids))
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('Success'):
                        result = data.get('Result', [])
                        # Convert to dict
                        family_map = {}
                        if isinstance(result, list):
                            for item in result:
                                pid = item.get('PersonID')
                                fid = item.get('FamilyID')
                                if pid and fid:
                                    family_map[pid] = fid
                        logger.info(f"✓ Retrieved family info for {len(family_map)} persons")
                        return family_map
                    else:
                        logger.warning(f"GetFamilyPersons returned: {data.get('ErrorText')}")
                        return {}
                else:
                    logger.error(f"Failed to get family persons: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting family persons: {str(e)}")
            return {}
    
    async def get_custom_field_data(self, person_ids: List[int] = None, 
                                     field_ids: List[int] = None,
                                     since: str = None) -> Dict[int, Dict]:
        """
        Get custom field data (including bus assignments)
        Endpoint: GET /api/entity/customfield/GetCustomFieldData
        
        Returns dict mapping person_id -> {field_id: value}
        
        Note: This endpoint may return empty if the API subscription
        doesn't include custom field access.
        """
        try:
            headers = await self.get_auth_headers()
            
            params = {'clientid': self.client_ids or '241'}
            if person_ids:
                params['personIDs'] = ','.join(map(str, person_ids))
            if field_ids:
                params['fieldIDs'] = ','.join(map(str, field_ids))
            if since:
                params['since'] = since
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/customfield/GetCustomFieldData",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('Result', {})
                    
                    if isinstance(result, dict):
                        cf_list = list(result.values())
                    else:
                        cf_list = result if result else []
                    
                    # Convert to person_id -> field values dict
                    cf_dict = {}
                    for container in cf_list:
                        pid = container.get('ObjectID')
                        if pid:
                            fields = container.get('Fields', [])
                            field_values = {}
                            for f in fields:
                                fid = f.get('FieldID')
                                value = f.get('Value')
                                if fid and value:
                                    field_values[fid] = value
                            if field_values:
                                cf_dict[pid] = field_values
                    
                    logger.info(f"✓ Retrieved custom field data for {len(cf_dict)} persons")
                    return cf_dict
                else:
                    logger.error(f"Failed to get custom fields: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting custom fields: {str(e)}")
            return {}
    
    async def get_camper_season_data(self, season_id: str = "2026") -> List[Dict]:
        """
        Get camper season-specific data
        Endpoint: GET /api/entity/person/camper/GetCampers
        
        Uses 'since' parameter which returns more complete data
        """
        try:
            headers = await self.get_auth_headers()
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/entity/person/camper/GetCampers",
                    headers=headers,
                    params={
                        'clientid': self.client_ids or '241',
                        'since': '2020-01-01T00:00:00Z'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('Success'):
                        result = data.get('Result', [])
                        # Filter to requested season
                        if isinstance(result, list):
                            season_campers = [c for c in result 
                                            if c.get('SeasonID') == int(season_id)]
                            logger.info(f"✓ Retrieved {len(season_campers)} campers for season {season_id}")
                            return season_campers
                    return []
                else:
                    logger.error(f"Failed to get camper data: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error getting camper data: {str(e)}")
            return []
    
    def parse_session_type(self, session_type: str, enrolled_sessions: List = None) -> Dict[str, bool]:
        """
        Parse session types to determine AM/PM eligibility
        """
        session_lower = (session_type or '').lower()
        
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
            return {'has_am': True, 'has_pm': True}
    
    async def get_all_campers_with_bus_data(self, season_id: str = "2026") -> List[Dict]:
        """
        Main integration function - combines all API calls
        
        Returns campers with properly formatted bus data following display rules:
        - Only show AM bus if camper has AM session
        - Only show PM bus if camper has PM session
        - Never show "None" - leave blank instead
        
        Note: Bus assignment data may be unavailable if the API subscription
        doesn't include custom field access. In that case, campers are
        returned without bus assignments (to be filled from Google Sheet).
        """
        logger.info(f"Starting CampMinder API sync for season {season_id}")
        
        # Step 1: Authenticate
        token = await self.get_jwt_token()
        if not token:
            logger.error("Failed to authenticate with CampMinder API")
            return []
        
        # Step 2: Get field definitions (to verify bus field IDs)
        await self.get_field_definitions()
        
        # Step 3: Get active camper IDs
        active_ids = await self.get_active_camper_ids(season_id)
        if not active_ids:
            logger.warning("No active campers found for season")
            return []
        
        logger.info(f"Found {len(active_ids)} active campers")
        
        # Step 4: Get person data (names)
        active_ids_set = set(active_ids)
        all_persons = await self.get_persons(since='2020-01-01T00:00:00Z')
        
        # Filter to active campers
        camper_persons = {pid: data for pid, data in all_persons.items() 
                         if pid in active_ids_set}
        logger.info(f"Got person data for {len(camper_persons)} campers")
        
        # Step 5: Get camper season data
        season_data = await self.get_camper_season_data(season_id)
        season_lookup = {c.get('PersonID'): c for c in season_data}
        
        # Step 6: Try to get custom field data (bus assignments)
        # Note: This may return empty if API access is limited
        bus_data = await self.get_custom_field_data(
            person_ids=list(active_ids_set)[:500],  # Batch limit
            field_ids=[self.am_bus_field_id, self.pm_bus_field_id]
        )
        logger.info(f"Got bus assignment data for {len(bus_data)} campers")
        
        # Step 7: Get family addresses
        all_addresses = await self.get_family_addresses(since='2020-01-01T00:00:00Z')
        
        # Also get person-to-family mapping
        family_map = await self.get_family_persons(list(active_ids_set)[:200])
        
        # Step 8: Build result list
        result_campers = []
        
        for person_id in active_ids_set:
            person = camper_persons.get(person_id, {})
            if not person:
                continue
            
            name = person.get('Name', {})
            first_name = name.get('FirstName', '') or name.get('NickName', '')
            last_name = name.get('LastName', '')
            
            if not first_name or not last_name:
                continue
            
            # Get bus assignments
            person_bus = bus_data.get(person_id, {})
            raw_am_bus = person_bus.get(self.am_bus_field_id, '')
            raw_pm_bus = person_bus.get(self.pm_bus_field_id, '')
            
            # Clean bus values
            am_bus = ''
            pm_bus = ''
            
            if raw_am_bus and str(raw_am_bus).lower() not in ['none', 'null', 'n/a', '', 'nt']:
                # Format as "Bus #XX"
                bus_num = str(raw_am_bus).zfill(2) if raw_am_bus.isdigit() else raw_am_bus
                am_bus = f"Bus #{bus_num}" if not bus_num.startswith('Bus') else bus_num
            
            if raw_pm_bus and str(raw_pm_bus).lower() not in ['none', 'null', 'n/a', '', 'nt']:
                bus_num = str(raw_pm_bus).zfill(2) if raw_pm_bus.isdigit() else raw_pm_bus
                pm_bus = f"Bus #{bus_num}" if not bus_num.startswith('Bus') else bus_num
            
            # Get address from family
            address = ''
            city = ''
            state = ''
            zip_code = ''
            
            family_id = family_map.get(person_id)
            if family_id and family_id in all_addresses:
                family_addrs = all_addresses[family_id]
                if isinstance(family_addrs, list) and family_addrs:
                    # Get primary address (LocationFlagID 513 = primary home)
                    for addr_item in family_addrs:
                        addr = addr_item.get('Address', {})
                        if addr and addr.get('AddressLine1'):
                            address = addr.get('AddressLine1', '')
                            city = addr.get('City', '')
                            state = addr.get('StateProvince', '')
                            zip_code = addr.get('PostalCode', '')
                            break
            
            # Get session info
            season_info = season_lookup.get(person_id, {})
            session_type = season_info.get('SessionType', '')
            
            # Parse session for AM/PM eligibility
            session_info = self.parse_session_type(session_type)
            
            # Build full address
            full_address = ', '.join(filter(None, [address, city, state, zip_code]))
            
            result_campers.append({
                'personID': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'address': full_address,
                'town': city,
                'state': state,
                'zip_code': zip_code,
                'session_type': session_type,
                'has_am_session': session_info['has_am'],
                'has_pm_session': session_info['has_pm'],
                'am_bus_number': am_bus,
                'pm_bus_number': pm_bus
            })
        
        logger.info(f"✓ Processed {len(result_campers)} campers with data")
        return result_campers
    
    async def test_api_connectivity(self) -> Dict[str, Any]:
        """
        Test API connectivity and return diagnostic information
        """
        results = {
            "auth": {"status": "pending", "message": ""},
            "field_defs": {"status": "pending", "message": ""},
            "active_campers": {"status": "pending", "message": ""},
            "persons": {"status": "pending", "message": ""},
            "addresses": {"status": "pending", "message": ""},
            "custom_fields": {"status": "pending", "message": ""},
            "day_travel": {"status": "pending", "message": ""},
        }
        
        try:
            # Test 1: Authentication
            token = await self.get_jwt_token()
            if token:
                results["auth"] = {
                    "status": "success",
                    "message": f"Authenticated. ClientIDs: {self.client_ids}"
                }
            else:
                results["auth"] = {"status": "error", "message": "Authentication failed"}
                return {"status": "error", "results": results}
            
            # Test 2: Field definitions
            fields = await self.get_field_definitions()
            if fields:
                results["field_defs"] = {
                    "status": "success",
                    "message": f"Retrieved {len(fields)} fields. AM Bus ID: {self.am_bus_field_id}, PM Bus ID: {self.pm_bus_field_id}"
                }
            else:
                results["field_defs"] = {"status": "warning", "message": "No field definitions returned"}
            
            # Test 3: Active campers
            active = await self.get_active_camper_ids("2026")
            if active:
                results["active_campers"] = {
                    "status": "success",
                    "message": f"Found {len(active)} active campers for 2026"
                }
            else:
                results["active_campers"] = {"status": "warning", "message": "No active campers found"}
            
            # Test 4: Person data
            persons = await self.get_persons(since='2020-01-01T00:00:00Z')
            if persons:
                results["persons"] = {
                    "status": "success", 
                    "message": f"Retrieved {len(persons)} person records"
                }
            else:
                results["persons"] = {"status": "warning", "message": "No person data returned"}
            
            # Test 5: Addresses
            addresses = await self.get_family_addresses(since='2020-01-01T00:00:00Z')
            if addresses:
                results["addresses"] = {
                    "status": "success",
                    "message": f"Retrieved addresses for {len(addresses)} families"
                }
            else:
                results["addresses"] = {"status": "warning", "message": "No address data returned"}
            
            # Test 6: Custom fields
            if active:
                cf_data = await self.get_custom_field_data(
                    person_ids=active[:50],
                    field_ids=[self.am_bus_field_id, self.pm_bus_field_id]
                )
                if cf_data:
                    results["custom_fields"] = {
                        "status": "success",
                        "message": f"Retrieved custom field data for {len(cf_data)} campers"
                    }
                else:
                    results["custom_fields"] = {
                        "status": "warning",
                        "message": "Custom field data empty - may require higher API access level"
                    }
            
            # Test 7: Day Travel API
            headers = await self.get_auth_headers()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.data_url}/api/travel/day/traveldate/season/2026",
                    headers=headers,
                    params={'clientid': self.client_ids}
                )
                if response.status_code == 200:
                    results["day_travel"] = {"status": "success", "message": "Day Travel API accessible"}
                elif response.status_code == 403:
                    results["day_travel"] = {
                        "status": "disabled",
                        "message": "Day Travel API not enabled for this subscription"
                    }
                else:
                    results["day_travel"] = {
                        "status": "error",
                        "message": f"Day Travel API returned {response.status_code}"
                    }
            
            # Determine overall status
            statuses = [r["status"] for r in results.values()]
            if all(s == "success" for s in statuses):
                overall = "success"
            elif results["auth"]["status"] == "success" and any(s == "success" for s in statuses):
                overall = "partial"
            else:
                overall = "error"
            
            return {
                "status": overall,
                "results": results,
                "recommendation": "Use Google Sheet sync as fallback for bus assignments" if results["custom_fields"]["status"] != "success" else "CampMinder API fully operational"
            }
            
        except Exception as e:
            logger.error(f"Error testing API: {str(e)}")
            return {"status": "error", "message": str(e), "results": results}
    
    async def update_camper_bus_assignment(self, camper_id: str, bus_number: str, bus_type: str = 'am') -> bool:
        """Update bus assignment in CampMinder (placeholder - write API may not be available)"""
        logger.info(f"Would update camper {camper_id} {bus_type.upper()} to {bus_number}")
        # TODO: Implement actual API call when endpoint is available
        return True
    
    async def bulk_update_bus_assignments(self, assignments: List[Dict]) -> Dict[str, bool]:
        """Bulk update bus assignments (placeholder)"""
        return {a['camper_id']: True for a in assignments}
