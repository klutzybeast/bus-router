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
    
    def generate_cover_sheet(self, campers: List[Dict[str, Any]], staff_dict: Dict[str, Dict] = None, 
                             shadows: List[Dict[str, Any]] = None, assigned_staff: List[Dict[str, Any]] = None,
                             staff_addresses: List[Dict[str, Any]] = None) -> List[List[Any]]:
        """
        Generate cover sheet data showing bus-by-bus seat availability
        
        Args:
            campers: List of camper documents from database
            staff_dict: Optional dict of bus_number -> staff config from database
            shadows: Optional list of shadow documents
            assigned_staff: Optional list of assigned staff documents
            staff_addresses: Optional list of staff with addresses documents
        
        Returns list of rows (each row is a list of values)
        """
        if staff_dict is None:
            staff_dict = {}
        if shadows is None:
            shadows = []
        if assigned_staff is None:
            assigned_staff = []
        if staff_addresses is None:
            staff_addresses = []
        
        # Build notes for each bus (shadows and assigned staff names)
        bus_notes = defaultdict(list)
        for shadow in shadows:
            bus_num = shadow.get('bus_number', '')
            if bus_num:
                shadow_name = shadow.get('shadow_name', '')
                camper_name = shadow.get('camper_name', '')
                bus_notes[bus_num].append(f"Shadow: {shadow_name} (for {camper_name})")
        
        for staff in assigned_staff:
            bus_num = staff.get('bus_number', '')
            if bus_num:
                staff_name = staff.get('staff_name', '')
                bus_notes[bus_num].append(f"Staff: {staff_name}")
        
        # Add staff with addresses to notes (only if they have a bus assigned)
        for staff in staff_addresses:
            bus_num = staff.get('bus_number', '')
            if bus_num and bus_num.startswith('Bus'):
                staff_name = staff.get('name', '')
                bus_notes[bus_num].append(f"Staff: {staff_name}")
        
        # Group campers by bus - track AM and PM separately
        bus_am_campers = defaultdict(set)
        bus_pm_campers = defaultdict(set)
        
        for camper in campers:
            camper_id = f"{camper.get('first_name', '')}_{camper.get('last_name', '')}_{camper.get('_id', '')}"
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            session = camper.get('session', '')
            halves = self.parse_session_to_halves(session)
            
            # Track AM bus assignments
            if am_bus and am_bus != 'NONE' and 'NONE' not in am_bus.upper():
                bus_am_campers[am_bus].add((camper_id, session, 'am'))
            
            # Track PM bus assignments
            if pm_bus and pm_bus != 'NONE' and 'NONE' not in pm_bus.upper():
                bus_pm_campers[pm_bus].add((camper_id, session, 'pm'))
        
        # Get all unique buses
        all_buses = set(bus_am_campers.keys()) | set(bus_pm_campers.keys()) | set(bus_notes.keys())
        sorted_buses = sorted(all_buses, key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        # Start building sheet
        sheet_data = []
        
        # Title
        sheet_data.append(['2026 Seats Available'])
        sheet_data.append(['Rolling River Day Camp'])
        sheet_data.append([])
        
        # Column headers - 14 columns with Notes column
        sheet_data.append([
            'Bus #',
            'Location',
            'Driver',
            'Counselor',
            'Seats',
            'Half 1 AM',
            'H1 AM Avail',
            'Half 1 PM',
            'H1 PM Avail',
            'Half 2 AM',
            'H2 AM Avail',
            'Half 2 PM',
            'H2 PM Avail',
            'Notes'
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
            
            # Count campers per half session - separate AM and PM tracking
            half1_am_count = 0
            half1_pm_count = 0
            half2_am_count = 0
            half2_pm_count = 0
            
            # Count AM bus campers
            for camper_id, session, bus_type in bus_am_campers.get(bus_number, set()):
                halves = self.parse_session_to_halves(session)
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
            
            # Count PM bus campers
            for camper_id, session, bus_type in bus_pm_campers.get(bus_number, set()):
                halves = self.parse_session_to_halves(session)
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            # Count shadows for this bus
            bus_shadows = [s for s in shadows if s.get('bus_number') == bus_number]
            for shadow in bus_shadows:
                session = shadow.get('session', '')
                halves = self.parse_session_to_halves(session)
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            # Count assigned staff for this bus
            bus_staff = [s for s in assigned_staff if s.get('bus_number') == bus_number]
            for staff_member in bus_staff:
                session = staff_member.get('session', '')
                halves = self.parse_session_to_halves(session)
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            # Calculate available seats for each session
            h1_am_avail = capacity - half1_am_count
            h1_pm_avail = capacity - half1_pm_count
            h2_am_avail = capacity - half2_am_count
            h2_pm_avail = capacity - half2_pm_count
            
            # Overall available = capacity - max usage
            max_usage = max(half1_am_count, half1_pm_count, half2_am_count, half2_pm_count)
            available = capacity - max_usage
            
            # Add totals
            total_capacity += capacity
            total_available += available
            total_half1_am += half1_am_count
            total_half1_pm += half1_pm_count
            total_half2_am += half2_am_count
            total_half2_pm += half2_pm_count
            
            # Fallback location to first camper's town if not set
            if not location:
                am_campers = list(bus_am_campers.get(bus_number, set()))
                if am_campers:
                    # Get the actual camper data
                    for c in campers:
                        if c.get('am_bus_number') == bus_number:
                            location = c.get('town', '')
                            break
            
            # Build notes string
            notes = "; ".join(bus_notes.get(bus_number, []))
            
            sheet_data.append([
                bus_number,
                location or '',
                driver,
                counselor,
                capacity,
                half1_am_count,
                h1_am_avail,
                half1_pm_count,
                h1_pm_avail,
                half2_am_count,
                h2_am_avail,
                half2_pm_count,
                h2_pm_avail,
                notes
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
            total_capacity - total_half1_am,
            total_half1_pm,
            total_capacity - total_half1_pm,
            total_half2_am,
            total_capacity - total_half2_am,
            total_half2_pm,
            total_capacity - total_half2_pm,
            ''
        ])
        
        # Available seats summary
        sheet_data.append([])
        sheet_data.append(['AVAILABLE SEATS BY HALF SESSION:'])
        sheet_data.append(['Half 1 AM Available:', total_capacity - total_half1_am])
        sheet_data.append(['Half 1 PM Available:', total_capacity - total_half1_pm])
        sheet_data.append(['Half 2 AM Available:', total_capacity - total_half2_am])
        sheet_data.append(['Half 2 PM Available:', total_capacity - total_half2_pm])
        
        return sheet_data
    
    def generate_cover_sheet_simple(self, campers: List[Dict[str, Any]], staff_dict: Dict[str, Dict] = None,
                                    shadows: List[Dict[str, Any]] = None, assigned_staff: List[Dict[str, Any]] = None,
                                    staff_addresses: List[Dict[str, Any]] = None) -> List[List[Any]]:
        """
        Generate simplified 11-column cover sheet data for Google Sheets.
        This matches the format expected by the Google Apps Script.
        
        Columns: Bus #, Location, Driver, Counselor, Seats, Half 1 AM, Half 1 PM, Half 2 AM, Half 2 PM, Available, Notes
        
        Args:
            campers: List of camper documents from database
            staff_dict: Optional dict of bus_number -> staff config from database
            shadows: Optional list of shadow documents
            assigned_staff: Optional list of assigned staff documents
            staff_addresses: Optional list of staff with addresses documents
        
        Returns list of rows (each row is a list of values)
        """
        if staff_dict is None:
            staff_dict = {}
        if shadows is None:
            shadows = []
        if assigned_staff is None:
            assigned_staff = []
        if staff_addresses is None:
            staff_addresses = []
        
        # Build notes for each bus (shadows and assigned staff names)
        bus_notes = defaultdict(list)
        for shadow in shadows:
            bus_num = shadow.get('bus_number', '')
            if bus_num:
                shadow_name = shadow.get('shadow_name', '')
                camper_name = shadow.get('camper_name', '')
                bus_notes[bus_num].append(f"Shadow: {shadow_name} (for {camper_name})")
        
        for staff in assigned_staff:
            bus_num = staff.get('bus_number', '')
            if bus_num:
                staff_name = staff.get('staff_name', '')
                bus_notes[bus_num].append(f"Staff: {staff_name}")
        
        # Add staff with addresses to notes (only if they have a bus assigned)
        for staff in staff_addresses:
            bus_num = staff.get('bus_number', '')
            if bus_num and bus_num.startswith('Bus'):
                staff_name = staff.get('name', '')
                bus_notes[bus_num].append(f"Staff: {staff_name}")
        
        # Group campers by bus - track AM and PM separately
        bus_am_campers = defaultdict(set)
        bus_pm_campers = defaultdict(set)
        
        for camper in campers:
            camper_id = f"{camper.get('first_name', '')}_{camper.get('last_name', '')}_{camper.get('_id', '')}"
            am_bus = camper.get('am_bus_number', '')
            pm_bus = camper.get('pm_bus_number', '')
            session = camper.get('session', '')
            
            # Track AM bus assignments
            if am_bus and am_bus != 'NONE' and 'NONE' not in am_bus.upper():
                bus_am_campers[am_bus].add((camper_id, session, 'am'))
            
            # Track PM bus assignments
            if pm_bus and pm_bus != 'NONE' and 'NONE' not in pm_bus.upper():
                bus_pm_campers[pm_bus].add((camper_id, session, 'pm'))
        
        # Get all unique buses
        all_buses = set(bus_am_campers.keys()) | set(bus_pm_campers.keys()) | set(bus_notes.keys())
        sorted_buses = sorted(all_buses, key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        # Start building sheet
        sheet_data = []
        
        # Title
        sheet_data.append(['2026 Seats Available'])
        sheet_data.append(['Rolling River Day Camp'])
        sheet_data.append([])
        
        # Column headers - 11 columns for Google Sheet with Notes
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
            'Available',
            'Notes'
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
            
            # Count campers per half session - separate AM and PM tracking
            half1_am_count = 0
            half1_pm_count = 0
            half2_am_count = 0
            half2_pm_count = 0
            
            # Count AM bus campers
            for camper_id, session, bus_type in bus_am_campers.get(bus_number, set()):
                halves = self.parse_session_to_halves(session)
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
            
            # Count PM bus campers
            for camper_id, session, bus_type in bus_pm_campers.get(bus_number, set()):
                halves = self.parse_session_to_halves(session)
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            # Count shadows for this bus
            bus_shadows = [s for s in shadows if s.get('bus_number') == bus_number]
            for shadow in bus_shadows:
                session = shadow.get('session', '')
                halves = self.parse_session_to_halves(session)
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            # Count assigned staff for this bus
            bus_staff_list = [s for s in assigned_staff if s.get('bus_number') == bus_number]
            for staff_member in bus_staff_list:
                session = staff_member.get('session', '')
                halves = self.parse_session_to_halves(session)
                if halves['half1_am']:
                    half1_am_count += 1
                if halves['half1_pm']:
                    half1_pm_count += 1
                if halves['half2_am']:
                    half2_am_count += 1
                if halves['half2_pm']:
                    half2_pm_count += 1
            
            # Overall available = capacity - max usage
            max_usage = max(half1_am_count, half1_pm_count, half2_am_count, half2_pm_count)
            available = capacity - max_usage
            
            # Add totals
            total_capacity += capacity
            total_available += available
            total_half1_am += half1_am_count
            total_half1_pm += half1_pm_count
            total_half2_am += half2_am_count
            total_half2_pm += half2_pm_count
            
            # Fallback location to first camper's town if not set
            if not location:
                am_campers = list(bus_am_campers.get(bus_number, set()))
                if am_campers:
                    for c in campers:
                        if c.get('am_bus_number') == bus_number:
                            location = c.get('town', '')
                            break
            
            # Build notes string
            notes = "; ".join(bus_notes.get(bus_number, []))
            
            # 11-column row: Bus #, Location, Driver, Counselor, Seats, H1 AM, H1 PM, H2 AM, H2 PM, Available, Notes
            sheet_data.append([
                bus_number,
                location or '',
                driver,
                counselor,
                capacity,
                half1_am_count,
                half1_pm_count,
                half2_am_count,
                half2_pm_count,
                available,
                notes
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
            total_available,
            ''
        ])
        
        # Available seats summary
        sheet_data.append([])
        sheet_data.append(['AVAILABLE SEATS BY HALF SESSION:'])
        sheet_data.append(['Half 1 AM Available:', total_capacity - total_half1_am])
        sheet_data.append(['Half 1 PM Available:', total_capacity - total_half1_pm])
        sheet_data.append(['Half 2 AM Available:', total_capacity - total_half2_am])
        sheet_data.append(['Half 2 PM Available:', total_capacity - total_half2_pm])
        
        return sheet_data
