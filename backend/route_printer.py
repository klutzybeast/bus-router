from typing import List, Dict, Any
import googlemaps
from collections import defaultdict
from datetime import datetime
from bus_config import get_bus_capacity, get_bus_driver, get_bus_counselor

class RoutePrinter:
    def __init__(self, gmaps_client):
        self.gmaps = gmaps_client
    
    def generate_route_sheet(self, bus_number: str, campers: List[Dict], camp_address: str = "Rolling River Day Camp, Wantagh, NY") -> Dict[str, Any]:
        """Generate printable route sheet with turn-by-turn directions"""
        
        if not campers:
            return {"error": "No campers assigned to this bus"}
        
        # Separate AM and PM campers
        am_campers = [c for c in campers if 'AM' in c.get('pickup_type', '')]
        pm_campers = [c for c in campers if 'PM' in c.get('pickup_type', '') or c.get('pickup_type') == 'AM & PM']
        
        # Sort AM campers by proximity for efficient route (morning pickups)
        sorted_am = self.optimize_stop_order(am_campers, camp_address) if am_campers else []
        
        # REVERSE for PM route (afternoon drop-offs)
        sorted_pm = list(reversed(sorted_am)) if sorted_am else []
        
        # Get turn-by-turn directions
        waypoints = [
            f"{c['location']['latitude']},{c['location']['longitude']}"
            for c in sorted_campers
        ]
        
        directions = None
        if len(waypoints) > 0:
            try:
                # Google Directions API supports max 25 waypoints
                if len(waypoints) > 23:
                    waypoints = waypoints[:23]
                
                directions = self.gmaps.directions(
                    origin=camp_address,
                    destination=camp_address,
                    waypoints=waypoints,
                    optimize_waypoints=True,
                    mode="driving"
                )
            except Exception as e:
                print(f"Error getting directions: {e}")
        
        route_sheet = {
            "bus_number": bus_number,
            "capacity": get_bus_capacity(bus_number),
            "driver": get_bus_driver(bus_number),
            "counselor": get_bus_counselor(bus_number),
            "total_stops": len(sorted_campers),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "stops": [],
            "directions": [],
            "total_distance": "N/A",
            "estimated_time": "N/A"
        }
        
        # Add stop information
        for idx, camper in enumerate(sorted_campers, 1):
            route_sheet["stops"].append({
                "stop_number": idx,
                "camper_name": f"{camper['first_name']} {camper['last_name']}",
                "address": camper['location'].get('address', ''),
                "town": camper.get('town', ''),
                "zip": camper.get('zip_code', ''),
                "pickup_type": camper.get('pickup_type', ''),
                "session": camper.get('session', ''),
                "notes": ""
            })
        
        # Add turn-by-turn directions if available
        if directions and len(directions) > 0:
            route = directions[0]
            legs = route.get('legs', [])
            
            total_distance_meters = sum(leg['distance']['value'] for leg in legs)
            total_duration_seconds = sum(leg['duration']['value'] for leg in legs)
            
            route_sheet["total_distance"] = f"{total_distance_meters / 1609.34:.1f} miles"
            route_sheet["estimated_time"] = f"{total_duration_seconds // 60} minutes"
            
            for idx, leg in enumerate(legs, 1):
                step_directions = []
                for step in leg.get('steps', []):
                    instruction = step.get('html_instructions', '').replace('<b>', '').replace('</b>', '').replace('<div>', ' ').replace('</div>', '')
                    step_directions.append({
                        "instruction": instruction,
                        "distance": step['distance']['text'],
                        "duration": step['duration']['text']
                    })
                
                route_sheet["directions"].append({
                    "leg_number": idx,
                    "from": legs[idx-1]['end_address'] if idx > 1 else "Camp",
                    "to": leg['end_address'],
                    "distance": leg['distance']['text'],
                    "duration": leg['duration']['text'],
                    "steps": step_directions
                })
        
        return route_sheet
    
    def optimize_stop_order(self, campers: List[Dict], start_location: str) -> List[Dict]:
        """Optimize the order of stops using nearest neighbor algorithm"""
        if not campers:
            return []
        
        # Simple nearest neighbor for now
        sorted_stops = []
        remaining = campers.copy()
        
        # Start from camp, find nearest stop
        try:
            camp_result = self.gmaps.geocode(start_location)
            if camp_result:
                current_lat = camp_result[0]['geometry']['location']['lat']
                current_lng = camp_result[0]['geometry']['location']['lng']
            else:
                # Default to first camper if camp location not found
                sorted_stops.append(remaining.pop(0))
                current_lat = sorted_stops[0]['location']['latitude']
                current_lng = sorted_stops[0]['location']['longitude']
        except:
            return campers
        
        while remaining:
            nearest_idx = 0
            min_distance = float('inf')
            
            for idx, camper in enumerate(remaining):
                lat = camper['location']['latitude']
                lng = camper['location']['longitude']
                
                # Simple distance calculation
                distance = ((lat - current_lat) ** 2 + (lng - current_lng) ** 2) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx
            
            nearest = remaining.pop(nearest_idx)
            sorted_stops.append(nearest)
            current_lat = nearest['location']['latitude']
            current_lng = nearest['location']['longitude']
        
        return sorted_stops
    
    def generate_printable_html(self, route_sheet: Dict[str, Any]) -> str:
        """Generate printable HTML route sheet for drivers"""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Route Sheet - {route_sheet['bus_number']}</title>
            <style>
                @media print {{
                    .no-print {{ display: none; }}
                    @page {{ margin: 0.5in; }}
                }}
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; }}
                .header {{ background: #1e40af; color: white; padding: 20px; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; }}
                .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0; }}
                .info-item {{ padding: 10px; background: #f3f4f6; border-radius: 5px; }}
                .info-label {{ font-weight: bold; color: #374151; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #2563eb; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #e5e7eb; }}
                tr:nth-child(even) {{ background: #f9fafb; }}
                .directions {{ margin: 30px 0; }}
                .step {{ padding: 10px; margin: 5px 0; background: #f0f9ff; border-left: 3px solid #3b82f6; }}
                .step-number {{ font-weight: bold; color: #1e40af; }}
                .signature {{ margin-top: 40px; border-top: 2px solid #000; padding-top: 10px; }}
                @media print {{ button {{ display: none; }} }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{route_sheet['bus_number']} Route Sheet</h1>
                <p>Rolling River Day Camp - {route_sheet['date']}</p>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Driver:</div>
                    <div>{route_sheet['driver']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Counselor:</div>
                    <div>{route_sheet['counselor']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Bus Capacity:</div>
                    <div>{route_sheet['capacity']} seats</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Total Stops:</div>
                    <div>{route_sheet['total_stops']} campers</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Total Distance:</div>
                    <div>{route_sheet['total_distance']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Estimated Time:</div>
                    <div>{route_sheet['estimated_time']}</div>
                </div>
            </div>
            
            <h2>Pickup/Drop-off Schedule</h2>
            <table>
                <thead>
                    <tr>
                        <th>Stop #</th>
                        <th>Camper Name</th>
                        <th>Address</th>
                        <th>Town</th>
                        <th>Type</th>
                        <th>Session</th>
                        <th>✓</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for stop in route_sheet['stops']:
            html += f"""
                    <tr>
                        <td>{stop['stop_number']}</td>
                        <td><strong>{stop['camper_name']}</strong></td>
                        <td>{stop['address']}</td>
                        <td>{stop['town']}</td>
                        <td>{stop['pickup_type']}</td>
                        <td>{stop['session']}</td>
                        <td>☐</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
        
        # Add turn-by-turn directions if available
        if route_sheet['directions']:
            html += """
            <div class="directions">
                <h2>Turn-by-Turn Directions</h2>
            """
            
            for direction in route_sheet['directions']:
                html += f"""
                <div style="margin: 20px 0; padding: 15px; background: #eff6ff; border-radius: 8px;">
                    <h3>Leg {direction['leg_number']}: {direction['from']} → {direction['to']}</h3>
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
        
        html += """
            <div class="signature">
                <p><strong>Driver Signature:</strong> _________________________ <strong>Date:</strong> _____________</p>
                <p><strong>Notes:</strong> _________________________________________________________________</p>
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
