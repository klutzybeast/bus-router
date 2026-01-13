from typing import List, Dict, Any
from collections import defaultdict
from bus_config import get_bus_capacity, get_bus_driver, get_bus_counselor, get_bus_location

class CoverSheetGenerator:
    """Generate EXACT format matching the Excel Cover Sheet - compact summary table"""
    
    def parse_session_to_halves(self, session: str) -> Dict[str, bool]:
        """Parse session string to determine which halves"""
        session_lower = session.lower()
        
        result = {
            'half1_am': False,
            'half1_pm': False,
            'half2_am': False,
            'half2_pm': False
        }
        
        if 'full season' in session_lower:
            result = {k: True for k in result}
        elif 'half season 1' in session_lower or 'half 1' in session_lower or 'half season 1' in session_lower:
            result['half1_am'] = True
            result['half1_pm'] = True
        elif 'half season 2' in session_lower or 'half 2' in session_lower or 'half season 2' in session_lower:
            result['half2_am'] = True
            result['half2_pm'] = True
        elif '6 week' in session_lower or 'flex' in session_lower:
            result = {k: True for k in result}
        
        return result
    
    def generate_cover_sheet(self, campers: List[Dict[str, Any]], staff_dict: Dict[str, Dict] = None) -> List[List[Any]]:
        """
        Generate cover sheet data showing bus-by-bus seat availability
        
        Args:
            campers: List of camper documents from database
            staff_dict: Optional dict of bus_number -> staff config from database
        
        Returns list of rows (each row is a list of values)
        """
        if staff_dict is None:
            staff_dict = {}
        
        # Group campers by bus
        bus_groups = defaultdict(list)
        for camper in campers:
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            
            # Add to AM bus group
            if am_bus and am_bus != 'NONE' and 'NONE' not in am_bus.upper():
                bus_groups[am_bus].append(camper)
            
            # Also add to PM bus group if different
            if pm_bus and pm_bus != am_bus and pm_bus != 'NONE' and 'NONE' not in pm_bus.upper():
                if camper not in bus_groups[pm_bus]:
                    bus_groups[pm_bus].append(camper)
        
        sorted_buses = sorted(bus_groups.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        # Start building sheet
        sheet_data = []
        
        # Title
        sheet_data.append(['2026 Seats Available'])
        sheet_data.append(['Rolling River Day Camp'])
        sheet_data.append([])
        
        # Column headers - EXACT format from Excel
        sheet_data.append([
            'Bus #',
            'Location',
            'Driver',
            'Counselor',
            'Seats',
            'Half 1 AM',
            'Half 1 PM',
            'Half 2 AM',
            'Half 2 PM',
            'Available'
        ])
        
        # Calculate totals across all buses
        total_half1_am = 0
        total_half1_pm = 0
        total_half2_am = 0
        total_half2_pm = 0
        total_capacity = 0
        total_available = 0
        
        # Data rows for each bus
        for bus_number in sorted_buses:
            bus_campers = bus_groups[bus_number]
            
            # Get staff info from database if available, else use defaults
            if bus_number in staff_dict:
                staff = staff_dict[bus_number]
                driver = staff.get('driver_name', get_bus_driver(bus_number))
                counselor = staff.get('counselor_name', get_bus_counselor(bus_number))
                capacity = staff.get('capacity', get_bus_capacity(bus_number))
                location = staff.get('location_name', get_bus_location(bus_number))
            else:
                capacity = get_bus_capacity(bus_number)
                driver = get_bus_driver(bus_number)
                counselor = get_bus_counselor(bus_number)
                location = get_bus_location(bus_number)
            
            # Fallback location to first camper's town
            if not location and bus_campers:
                location = bus_campers[0].get('town', '')
            
            # Count campers per half session
            half1_am_count = 0
            half1_pm_count = 0
            half2_am_count = 0
            half2_pm_count = 0
            
            for camper in bus_campers:
                session = camper.get('session', '')
                halves = self.parse_session_to_halves(session)
                
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            available = capacity - len(bus_campers)
            
            # Add totals
            total_capacity += capacity
            total_available += available
            total_half1_am += half1_am_count
            total_half1_pm += half1_pm_count
            total_half2_am += half2_am_count
            total_half2_pm += half2_pm_count
            
            sheet_data.append([
                bus_number,
                location,
                driver,
                counselor,
                capacity,
                half1_am_count,
                half1_pm_count,
                half2_am_count,
                half2_pm_count,
                available
            ])
        
        # Summary totals row
        sheet_data.append([])
        sheet_data.append([
            'TOTALS',
            f'{len(sorted_buses)} Buses',
            '',
            '',
            total_capacity,
            total_half1_am,
            total_half1_pm,
            total_half2_am,
            total_half2_pm,
            total_available
        ])
        
        # Available seats summary
        sheet_data.append([])
        sheet_data.append(['AVAILABLE SEATS BY HALF SESSION:'])
        sheet_data.append(['Half 1 AM Available:', total_capacity - total_half1_am])
        sheet_data.append(['Half 1 PM Available:', total_capacity - total_half1_pm])
        sheet_data.append(['Half 2 AM Available:', total_capacity - total_half2_am])
        sheet_data.append(['Half 2 PM Available:', total_capacity - total_half2_pm])
        
        return sheet_data
