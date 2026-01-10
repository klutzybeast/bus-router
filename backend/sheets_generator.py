from typing import List, Dict, Any
from collections import defaultdict

class SheetsDataGenerator:
    def __init__(self, max_capacity_per_bus: int = 50):
        self.max_capacity_per_bus = max_capacity_per_bus
    
    def generate_seat_availability_data(self, campers: List[Dict]) -> List[List[Any]]:
        """Generate formatted data for Google Sheets seat availability"""
        
        # Group campers by bus
        bus_groups = defaultdict(list)
        for camper in campers:
            bus_number = camper.get('bus_number', '')
            if bus_number:
                bus_groups[bus_number].append(camper)
        
        # Sort buses numerically
        sorted_buses = sorted(bus_groups.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        # Generate sheet data
        sheet_data = []
        
        # Title row
        sheet_data.append(['2026 Bus Seat Availability Report'])
        sheet_data.append([f'Last Updated: {campers[0].get("created_at", "N/A") if campers else "N/A"}'])
        sheet_data.append([])  # Empty row
        
        # Headers
        sheet_data.append(['Bus Number', 'Location', 'Total Capacity', 'Campers Assigned', 'Available Seats', 'Utilization %'])
        
        # Summary data for each bus
        for bus_number in sorted_buses:
            bus_campers = bus_groups[bus_number]
            total_campers = len(bus_campers)
            available_seats = self.max_capacity_per_bus - total_campers
            utilization = (total_campers / self.max_capacity_per_bus) * 100
            
            # Get primary location from first camper's town
            location = bus_campers[0].get('town', 'N/A') if bus_campers else 'N/A'
            
            sheet_data.append([
                bus_number,
                location,
                self.max_capacity_per_bus,
                total_campers,
                available_seats,
                f'{utilization:.1f}%'
            ])
        
        # Add spacing
        sheet_data.append([])
        sheet_data.append([])
        
        # Detailed breakdown by bus
        sheet_data.append(['DETAILED BREAKDOWN BY BUS'])
        sheet_data.append([])
        
        for bus_number in sorted_buses:
            bus_campers = bus_groups[bus_number]
            
            # Bus header
            sheet_data.append([f'{bus_number} - {bus_campers[0].get("town", "N/A") if bus_campers else "N/A"}'])
            sheet_data.append(['Capacity:', self.max_capacity_per_bus, 'Assigned:', len(bus_campers), 'Available:', self.max_capacity_per_bus - len(bus_campers)])
            sheet_data.append([])
            
            # Camper list headers
            sheet_data.append(['Last Name', 'First Name', 'Session', 'Pickup Type', 'Address', 'Town', 'Zip'])
            
            # Camper details
            for camper in bus_campers:
                sheet_data.append([
                    camper.get('last_name', ''),
                    camper.get('first_name', ''),
                    camper.get('session', ''),
                    camper.get('pickup_type', ''),
                    camper.get('location', {}).get('address', ''),
                    camper.get('town', ''),
                    camper.get('zip_code', '')
                ])
            
            # Add spacing between buses
            sheet_data.append([])
            sheet_data.append([])
        
        # Summary footer
        sheet_data.append(['SUMMARY'])
        sheet_data.append(['Total Buses:', len(sorted_buses)])
        sheet_data.append(['Total Campers:', len(campers)])
        sheet_data.append(['Total Capacity:', len(sorted_buses) * self.max_capacity_per_bus])
        sheet_data.append(['Total Available:', (len(sorted_buses) * self.max_capacity_per_bus) - len(campers)])
        
        return sheet_data
    
    def generate_compact_availability(self, campers: List[Dict]) -> List[List[Any]]:
        """Generate compact seat availability summary"""
        
        bus_groups = defaultdict(list)
        for camper in campers:
            bus_number = camper.get('bus_number', '')
            if bus_number:
                bus_groups[bus_number].append(camper)
        
        sorted_buses = sorted(bus_groups.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
        
        data = []
        data.append(['Bus #', 'Capacity', 'Assigned', 'Available', 'Status'])
        
        for bus_number in sorted_buses:
            total_campers = len(bus_groups[bus_number])
            available = self.max_capacity_per_bus - total_campers
            
            if available <= 0:
                status = '🔴 FULL'
            elif available <= 5:
                status = '🟡 LOW'
            else:
                status = '🟢 OPEN'
            
            data.append([
                bus_number,
                self.max_capacity_per_bus,
                total_campers,
                available,
                status
            ])
        
        return data
