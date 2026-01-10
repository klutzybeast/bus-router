from typing import List, Dict, Any
from collections import defaultdict
from bus_config import get_bus_capacity, get_bus_driver, get_bus_counselor

class SheetsDataGenerator:
    def __init__(self):
        pass
    
    def parse_session_to_halves(self, session: str) -> Dict[str, bool]:
        """Parse session string to determine which halves the camper attends"""
        session_lower = session.lower()
        
        result = {
            'half1_am': False,
            'half1_pm': False,
            'half2_am': False,
            'half2_pm': False
        }
        
        if 'full season' in session_lower:
            # Full season attends all halves
            result['half1_am'] = True
            result['half1_pm'] = True
            result['half2_am'] = True
            result['half2_pm'] = True
        elif 'half season 1' in session_lower or 'half 1' in session_lower:
            # Half season 1 only
            result['half1_am'] = True
            result['half1_pm'] = True
        elif 'half season 2' in session_lower or 'half 2' in session_lower:
            # Half season 2 only
            result['half2_am'] = True
            result['half2_pm'] = True
        elif '6 week' in session_lower:
            # 6 week typically spans both halves
            result['half1_am'] = True
            result['half1_pm'] = True
            result['half2_am'] = True
            result['half2_pm'] = True
        elif 'flex' in session_lower:
            # Flex can be either, mark as full for safety
            result['half1_am'] = True
            result['half1_pm'] = True
            result['half2_am'] = True
            result['half2_pm'] = True
        
        return result
    
    def generate_seat_availability_data(self, campers: List[Dict]) -> List[List[Any]]:
        """Generate exact format matching the Excel cover sheet"""
        
        # Group campers by bus, excluding NONE
        bus_groups = defaultdict(list)
        for camper in campers:
            bus_number = camper.get('bus_number', '')
            if bus_number and bus_number != 'NONE' and 'NONE' not in bus_number.upper():
                bus_groups[bus_number].append(camper)
        
        # Sort buses numerically
        sorted_buses = sorted(bus_groups.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        # Generate sheet data
        sheet_data = []
        
        # Main title
        sheet_data.append(['2026 Bus Seat Availability'])
        sheet_data.append(['Rolling River Day Camp'])
        sheet_data.append([])
        
        # Process each bus
        for bus_number in sorted_buses:
            bus_campers = bus_groups[bus_number]
            capacity = get_bus_capacity(bus_number)
            driver = get_bus_driver(bus_number)
            counselor = get_bus_counselor(bus_number)
            location = bus_campers[0].get('town', 'N/A') if bus_campers else 'N/A'
            
            # Bus header section
            sheet_data.append([f'Rolling River Bus Number: {bus_number}'])
            sheet_data.append([f'Location: {location}'])
            sheet_data.append([f'Bus Driver Name: {driver}'])
            sheet_data.append([f'Bus Counselor Name: {counselor}'])
            sheet_data.append([f'Seats: {capacity}'])
            sheet_data.append([])
            
            # Camper table headers
            sheet_data.append(['Last Name', 'First Name', 'Season', 'Half 1 AM', 'Half 1 PM', 'Half 2 AM', 'Half 2 PM'])
            
            # Count attendance by half
            half1_am_count = 0
            half1_pm_count = 0
            half2_am_count = 0
            half2_pm_count = 0
            
            # Camper rows
            for camper in bus_campers:
                last_name = camper.get('last_name', '')
                first_name = camper.get('first_name', '')
                session = camper.get('session', '')
                
                # Parse session to halves
                halves = self.parse_session_to_halves(session)
                
                # Count for totals
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
                
                # Add row with X marks for attended sessions
                sheet_data.append([
                    last_name,
                    first_name,
                    session,
                    'X' if halves['half1_am'] else '',
                    'X' if halves['half1_pm'] else '',
                    'X' if halves['half2_am'] else '',
                    'X' if halves['half2_pm'] else ''
                ])
            
            sheet_data.append([])
            
            # Seat totals section with warning if over 19 for small buses
            warning = ' ⚠️ OVER 19!' if capacity <= 19 and len(bus_campers) > 19 else ''
            sheet_data.append([f'Seat Totals (Do Not Pass 19 for small buses){warning}'])
            sheet_data.append([f'Available Seats: {capacity - len(bus_campers)}'])
            sheet_data.append([f'Total Campers Assigned: {len(bus_campers)}'])
            sheet_data.append([f'Half 1 AM: {half1_am_count}', f'Half 1 PM: {half1_pm_count}', f'Half 2 AM: {half2_am_count}', f'Half 2 PM: {half2_pm_count}'])
            
            # Separator
            sheet_data.append([])
            sheet_data.append(['=' * 50])
            sheet_data.append([])
        
        return sheet_data
    
    def generate_compact_availability(self, campers: List[Dict]) -> List[List[Any]]:
        """Generate compact seat availability summary"""
        
        bus_groups = defaultdict(list)
        for camper in campers:
            bus_number = camper.get('bus_number', '')
            if bus_number and bus_number != 'NONE' and 'NONE' not in bus_number.upper():
                bus_groups[bus_number].append(camper)
        
        sorted_buses = sorted(bus_groups.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        data = []
        data.append(['Bus #', 'Capacity', 'Assigned', 'Available', 'Status'])
        
        for bus_number in sorted_buses:
            capacity = get_bus_capacity(bus_number)
            total_campers = len(bus_groups[bus_number])
            available = capacity - total_campers
            
            if available <= 0:
                status = '🔴 FULL'
            elif available <= 5:
                status = '🟡 LOW'
            else:
                status = '🟢 OPEN'
            
            # Add warning for small buses over 19
            if capacity <= 19 and total_campers > 19:
                status += ' ⚠️'
            
            data.append([
                bus_number,
                capacity,
                total_campers,
                available,
                status
            ])
        
        return data