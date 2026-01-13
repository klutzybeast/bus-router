"""
Route Printer - Generates printable route sheets for bus drivers

Route Logic:
- AM Route: Home Location → Camper Pickups (in order) → Camp
- PM Route: Camp → Camper Drop-offs (in order) → Home Location

Each bus has ONE home location that is used as:
- AM START point (green marker)
- PM END point (green marker)

Camp (477 Ocean Avenue) is always:
- AM END point (red marker)
- PM START point (red marker)
"""

from typing import List, Dict, Any
import googlemaps
from collections import defaultdict
from datetime import datetime
from bus_config import (
    get_bus_capacity, 
    get_bus_driver, 
    get_bus_counselor,
    get_bus_home_location,
    get_camp_address,
    is_home_at_camp,
    get_bus_info
)


class RoutePrinter:
    def __init__(self, gmaps_client):
        self.gmaps = gmaps_client
        self.camp_address = get_camp_address()
    
    def generate_route_sheet(self, bus_number: str, campers: List[Dict], camp_address: str = None) -> Dict[str, Any]:
        """
        Generate printable route sheet with turn-by-turn directions
        
        Route Logic:
        - AM: home_location → campers → camp
        - PM: camp → campers → home_location (SAME as AM start)
        """
        # Use configured camp address
        if camp_address is None:
            camp_address = self.camp_address
        
        if not campers:
            return {"error": "No campers assigned to this bus"}
        
        # Get bus info including home location
        bus_info = get_bus_info(bus_number)
        home_location = bus_info['home_location']
        home_label = bus_info['home_label']
        
        # Helper function to check if bus is valid (not NONE or empty)
        def is_valid_bus(bus):
            return bus and bus != 'NONE' and bus.startswith('Bus')
        
        # Separate AM and PM campers based on their ACTUAL bus assignment
        am_campers = self._get_am_campers(campers, bus_number, is_valid_bus)
        pm_campers = self._get_pm_campers(campers, bus_number, is_valid_bus)
        
        # Optimize AM route: home_location → campers → camp
        sorted_am = self.optimize_route_from_origin(am_campers, home_location) if am_campers else []
        
        # Optimize PM route: camp → campers → home_location
        # Note: PM stops are in forward order from camp, ending at home
        sorted_pm = self.optimize_route_from_origin(pm_campers, camp_address) if pm_campers else []
        
        # Get turn-by-turn directions for AM route
        # AM: home_location → campers → camp
        directions_am = self._get_am_directions(sorted_am, home_location, camp_address)
        
        # Get turn-by-turn directions for PM route
        # PM: camp → campers → home_location
        directions_pm = self._get_pm_directions(sorted_pm, camp_address, home_location)
        
        # Build route sheet
        route_sheet = {
            "bus_number": bus_number,
            "capacity": bus_info['capacity'],
            "driver": bus_info['driver'],
            "counselor": bus_info['counselor'],
            "home_location": home_location,
            "home_label": home_label,
            "home_is_camp": bus_info['home_is_camp'],
            "camp_address": camp_address,
            "total_stops": max(len(sorted_am), len(sorted_pm)),
            "total_am_stops": len(sorted_am),
            "total_pm_stops": len(sorted_pm),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "am_stops": [],
            "pm_stops": [],
            "am_directions": [],
            "pm_directions": [],
            "am_distance": "N/A",
            "am_time": "N/A",
            "pm_distance": "N/A",
            "pm_time": "N/A"
        }
        
        # Add AM stop information (morning pickups) - consolidated by address
        am_consolidated = self._consolidate_stops(sorted_am)
        for idx, stop in enumerate(am_consolidated, 1):
            route_sheet["am_stops"].append({
                "stop_number": idx,
                "camper_name": stop['camper_names'],
                "address": stop['address'],
                "town": stop['town'],
                "zip": stop['zip'],
                "session": stop['session'],
                "notes": ""
            })
        
        # Add PM stop information (afternoon drop-offs) - consolidated by address
        pm_consolidated = self._consolidate_stops(sorted_pm)
        for idx, stop in enumerate(pm_consolidated, 1):
            route_sheet["pm_stops"].append({
                "stop_number": idx,
                "camper_name": stop['camper_names'],
                "address": stop['address'],
                "town": stop['town'],
                "zip": stop['zip'],
                "session": stop['session'],
                "notes": ""
            })
        
        # Update stop counts to reflect consolidated stops
        route_sheet["total_am_stops"] = len(am_consolidated)
        route_sheet["total_pm_stops"] = len(pm_consolidated)
        route_sheet["total_stops"] = max(len(am_consolidated), len(pm_consolidated))
        
        # Process AM directions
        if directions_am and len(directions_am) > 0:
            self._process_directions(route_sheet, directions_am, 'am', home_label)
        
        # Process PM directions
        if directions_pm and len(directions_pm) > 0:
            self._process_directions(route_sheet, directions_pm, 'pm', 'Camp')
        
        return route_sheet
    
    def _get_am_campers(self, campers: List[Dict], bus_number: str, is_valid_bus) -> List[Dict]:
        """Get campers for AM route - those with this AM bus assignment"""
        am_campers = []
        for c in campers:
            am_bus = c.get('am_bus_number', '')
            if am_bus == bus_number and is_valid_bus(am_bus):
                camper_id = c.get('_id', '')
                # Skip PM-specific entries for AM route
                if camper_id.endswith('_PM'):
                    continue
                am_campers.append(c)
        return am_campers
    
    def _get_pm_campers(self, campers: List[Dict], bus_number: str, is_valid_bus) -> List[Dict]:
        """Get campers for PM route - those with this PM bus assignment"""
        pm_campers = []
        seen_names = set()
        
        # First pass: collect PM-specific entries (different address from AM)
        for c in campers:
            pm_bus = c.get('pm_bus_number', '')
            if pm_bus == bus_number and is_valid_bus(pm_bus):
                camper_id = c.get('_id', '')
                name = f"{c.get('first_name', '')}_{c.get('last_name', '')}"
                
                if camper_id.endswith('_PM') or c.get('pickup_type') == 'PM Drop-off Only':
                    pm_campers.append(c)
                    seen_names.add(name)
        
        # Second pass: add campers without PM-specific entries
        for c in campers:
            pm_bus = c.get('pm_bus_number', '')
            if pm_bus == bus_number and is_valid_bus(pm_bus):
                camper_id = c.get('_id', '')
                name = f"{c.get('first_name', '')}_{c.get('last_name', '')}"
                
                if not camper_id.endswith('_PM') and c.get('pickup_type') != 'PM Drop-off Only':
                    if name not in seen_names:
                        pm_campers.append(c)
                        seen_names.add(name)
        
        return pm_campers
    
    def _get_am_directions(self, campers: List[Dict], home_location: str, camp_address: str):
        """
        Get directions for AM route: home_location → campers → camp
        """
        if not campers:
            return None
        
        waypoints = [
            f"{c['location']['latitude']},{c['location']['longitude']}"
            for c in campers if c.get('location', {}).get('latitude')
        ]
        
        if len(waypoints) == 0 or len(waypoints) > 23:
            return None
        
        try:
            return self.gmaps.directions(
                origin=home_location,        # Start at home (green marker)
                destination=camp_address,    # End at camp (red marker)
                waypoints=waypoints,
                optimize_waypoints=False,
                mode="driving"
            )
        except Exception as e:
            print(f"Error getting AM directions: {e}")
            return None
    
    def _get_pm_directions(self, campers: List[Dict], camp_address: str, home_location: str):
        """
        Get directions for PM route: camp → campers → home_location
        """
        if not campers:
            return None
        
        waypoints = [
            f"{c['location']['latitude']},{c['location']['longitude']}"
            for c in campers if c.get('location', {}).get('latitude')
        ]
        
        if len(waypoints) == 0 or len(waypoints) > 23:
            return None
        
        try:
            return self.gmaps.directions(
                origin=camp_address,         # Start at camp (red marker)
                destination=home_location,   # End at home (green marker)
                waypoints=waypoints,
                optimize_waypoints=False,
                mode="driving"
            )
        except Exception as e:
            print(f"Error getting PM directions: {e}")
            return None
    
    def _process_directions(self, route_sheet: Dict, directions: List, route_type: str, start_label: str):
        """Process directions and add to route sheet"""
        route = directions[0]
        legs = route.get('legs', [])
        
        total_distance_meters = sum(leg['distance']['value'] for leg in legs)
        total_duration_seconds = sum(leg['duration']['value'] for leg in legs)
        
        route_sheet[f"{route_type}_distance"] = f"{total_distance_meters / 1609.34:.1f} miles"
        route_sheet[f"{route_type}_time"] = f"{total_duration_seconds // 60} minutes"
        
        for idx, leg in enumerate(legs, 1):
            step_directions = []
            for step in leg.get('steps', []):
                instruction = step.get('html_instructions', '')
                instruction = instruction.replace('<b>', '').replace('</b>', '')
                instruction = instruction.replace('<div>', ' ').replace('</div>', '')
                step_directions.append({
                    "instruction": instruction,
                    "distance": step['distance']['text'],
                    "duration": step['duration']['text']
                })
            
            # Determine from label
            if idx == 1:
                from_label = start_label
            else:
                from_label = legs[idx-2]['end_address']
            
            route_sheet[f"{route_type}_directions"].append({
                "leg_number": idx,
                "from": from_label,
                "to": leg['end_address'],
                "distance": leg['distance']['text'],
                "duration": leg['duration']['text'],
                "steps": step_directions
            })
    
    def optimize_route_from_origin(self, campers: List[Dict], start_location: str) -> List[Dict]:
        """
        Optimize the order of stops using nearest neighbor algorithm
        Starting from a specific origin point
        """
        if not campers:
            return []
        
        sorted_stops = []
        remaining = campers.copy()
        
        # Get starting coordinates
        try:
            start_result = self.gmaps.geocode(start_location)
            if start_result:
                current_lat = start_result[0]['geometry']['location']['lat']
                current_lng = start_result[0]['geometry']['location']['lng']
            else:
                # Default to first camper if start location not found
                sorted_stops.append(remaining.pop(0))
                current_lat = sorted_stops[0]['location']['latitude']
                current_lng = sorted_stops[0]['location']['longitude']
        except:
            return campers
        
        # Nearest neighbor algorithm
        while remaining:
            nearest_idx = 0
            min_distance = float('inf')
            
            for idx, camper in enumerate(remaining):
                lat = camper['location']['latitude']
                lng = camper['location']['longitude']
                
                # Simple Euclidean distance (good enough for nearby stops)
                distance = ((lat - current_lat) ** 2 + (lng - current_lng) ** 2) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx
            
            nearest = remaining.pop(nearest_idx)
            sorted_stops.append(nearest)
            current_lat = nearest['location']['latitude']
            current_lng = nearest['location']['longitude']
        
        return sorted_stops
    
    def optimize_stop_order(self, campers: List[Dict], start_location: str) -> List[Dict]:
        """Legacy method - calls optimize_route_from_origin"""
        return self.optimize_route_from_origin(campers, start_location)
    
    def generate_printable_html(self, route_sheet: Dict[str, Any]) -> str:
        """Generate printable HTML route sheet for drivers"""
        
        # Determine markers and labels
        home_label = route_sheet.get('home_label', 'Home')
        home_location = route_sheet.get('home_location', 'Unknown')
        camp_address = route_sheet.get('camp_address', self.camp_address)
        home_is_camp = route_sheet.get('home_is_camp', True)
        
        # AM route description
        if home_is_camp:
            am_route_desc = "Camp → Pickups → Camp"
        else:
            am_route_desc = f"{home_label} → Pickups → Camp"
        
        # PM route description  
        if home_is_camp:
            pm_route_desc = "Camp → Drop-offs → Camp"
        else:
            pm_route_desc = f"Camp → Drop-offs → {home_label}"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Route Sheet - {route_sheet['bus_number']}</title>
            <style>
                @media print {{
                    .no-print {{ display: none; }}
                    @page {{ margin: 0.5in; }}
                    .page-break {{ page-break-before: always; }}
                }}
                body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 20px auto; }}
                .header {{ background: #1e40af; color: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; }}
                .header h1 {{ margin: 0; }}
                .route-info {{ background: #f0f9ff; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #3b82f6; }}
                .route-info h3 {{ margin: 0 0 10px 0; color: #1e40af; }}
                .info-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 20px 0; }}
                .info-item {{ padding: 10px; background: #f3f4f6; border-radius: 5px; }}
                .info-label {{ font-weight: bold; color: #374151; font-size: 0.9em; }}
                .info-value {{ font-size: 1.1em; margin-top: 4px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #2563eb; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #e5e7eb; }}
                tr:nth-child(even) {{ background: #f9fafb; }}
                .directions {{ margin: 30px 0; }}
                .step {{ padding: 8px 12px; margin: 4px 0; background: #f0f9ff; border-left: 3px solid #3b82f6; font-size: 0.95em; }}
                .step-number {{ font-weight: bold; color: #1e40af; }}
                .signature {{ margin-top: 40px; border-top: 2px solid #000; padding-top: 10px; }}
                .marker {{ display: inline-block; width: 20px; height: 20px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }}
                .marker-green {{ background: #22c55e; }}
                .marker-red {{ background: #ef4444; }}
                .route-legend {{ display: flex; gap: 20px; margin: 10px 0; font-size: 0.9em; }}
                .legend-item {{ display: flex; align-items: center; }}
                h2 {{ color: #1e40af; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }}
                @media print {{ button {{ display: none; }} }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚌 {route_sheet['bus_number']} Route Sheet</h1>
                <p>Rolling River Day Camp - {route_sheet['date']}</p>
            </div>
            
            <div class="route-info">
                <h3>📍 Bus Home Location</h3>
                <p><strong>{home_label}:</strong> {home_location}</p>
                <p><strong>Camp:</strong> {camp_address}</p>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Driver</div>
                    <div class="info-value">{route_sheet['driver']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Counselor</div>
                    <div class="info-value">{route_sheet['counselor']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Bus Capacity</div>
                    <div class="info-value">{route_sheet['capacity']} seats</div>
                </div>
                <div class="info-item">
                    <div class="info-label">AM Stops / PM Stops</div>
                    <div class="info-value">{route_sheet['total_am_stops']} / {route_sheet['total_pm_stops']}</div>
                </div>
            </div>
            
            <!-- AM ROUTE -->
            <h2>🌅 AM ROUTE - Morning Pickups</h2>
            <div class="route-legend">
                <div class="legend-item"><span class="marker marker-green"></span> Start: {home_label}</div>
                <div class="legend-item">1️⃣ 2️⃣ 3️⃣ Numbered Stops (Pickups)</div>
                <div class="legend-item"><span class="marker marker-red"></span> End: Camp</div>
            </div>
            <p><strong>Route:</strong> {am_route_desc}</p>
            <p><strong>Distance:</strong> {route_sheet['am_distance']} | <strong>Time:</strong> {route_sheet['am_time']}</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Stop #</th>
                        <th>Camper Name</th>
                        <th>Address</th>
                        <th>Town</th>
                        <th>Session</th>
                        <th>✓</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for stop in route_sheet["am_stops"]:
            html += f"""
                    <tr>
                        <td><strong>{stop['stop_number']}</strong></td>
                        <td><strong>{stop['camper_name']}</strong></td>
                        <td>{stop['address']}</td>
                        <td>{stop['town']}</td>
                        <td>{stop['session']}</td>
                        <td>☐</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
        
        # Add AM turn-by-turn directions
        if route_sheet['am_directions']:
            html += """
            <div class="directions">
                <h3>📍 Turn-by-Turn Directions (AM)</h3>
            """
            
            for direction in route_sheet['am_directions']:
                html += f"""
                <div style="margin: 15px 0; padding: 10px; background: #fef3c7; border-radius: 5px;">
                    <h4>Leg {direction['leg_number']}: {direction['from']} → {direction['to']}</h4>
                    <p><strong>Distance:</strong> {direction['distance']} | <strong>Time:</strong> {direction['duration']}</p>
                """
                
                for idx, step in enumerate(direction['steps'], 1):
                    html += f"""
                    <div class="step">
                        <span class="step-number">{idx}.</span> {step['instruction']}
                        <span style="color: #6b7280; font-size: 0.9em;"> ({step['distance']}, {step['duration']})</span>
                    </div>
                    """
                
                html += "</div>"
            
            html += "</div>"
        
        html += f"""
            <div class="signature">
                <p><strong>Driver Signature (AM):</strong> _____________________ <strong>Time:</strong> _______</p>
            </div>
            
            <!-- PM ROUTE -->
            <div class="page-break"></div>
            <h2>🌆 PM ROUTE - Afternoon Drop-offs</h2>
            <div class="route-legend">
                <div class="legend-item"><span class="marker marker-red"></span> Start: Camp</div>
                <div class="legend-item">1️⃣ 2️⃣ 3️⃣ Numbered Stops (Drop-offs)</div>
                <div class="legend-item"><span class="marker marker-green"></span> End: {home_label}</div>
            </div>
            <p><strong>Route:</strong> {pm_route_desc}</p>
            <p><strong>Distance:</strong> {route_sheet['pm_distance']} | <strong>Time:</strong> {route_sheet['pm_time']}</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Stop #</th>
                        <th>Camper Name</th>
                        <th>Address</th>
                        <th>Town</th>
                        <th>Session</th>
                        <th>✓</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for stop in route_sheet["pm_stops"]:
            html += f"""
                    <tr>
                        <td><strong>{stop['stop_number']}</strong></td>
                        <td><strong>{stop['camper_name']}</strong></td>
                        <td>{stop['address']}</td>
                        <td>{stop['town']}</td>
                        <td>{stop['session']}</td>
                        <td>☐</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
        
        # Add PM turn-by-turn directions
        if route_sheet['pm_directions']:
            html += """
            <div class="directions">
                <h3>📍 Turn-by-Turn Directions (PM)</h3>
            """
            
            for direction in route_sheet['pm_directions']:
                html += f"""
                <div style="margin: 15px 0; padding: 10px; background: #fef3c7; border-radius: 5px;">
                    <h4>Leg {direction['leg_number']}: {direction['from']} → {direction['to']}</h4>
                    <p><strong>Distance:</strong> {direction['distance']} | <strong>Time:</strong> {direction['duration']}</p>
                """
                
                for idx, step in enumerate(direction['steps'], 1):
                    html += f"""
                    <div class="step">
                        <span class="step-number">{idx}.</span> {step['instruction']}
                        <span style="color: #6b7280; font-size: 0.9em;"> ({step['distance']}, {step['duration']})</span>
                    </div>
                    """
                
                html += "</div>"
            
            html += "</div>"
        
        html += f"""
            <div class="signature">
                <p><strong>Driver Signature (PM):</strong> _____________________ <strong>Time:</strong> _______</p>
            </div>
            
            <div class="no-print" style="text-align: center; margin: 30px 0;">
                <button onclick="window.print()" style="background: #2563eb; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer;">
                    🖨️ Print Route Sheet
                </button>
            </div>
        </body>
        </html>
        """
        
        return html
