"""Route sheet and roster printing endpoints."""

import os
import logging
import urllib.parse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.database import db, route_printer
from services.helpers import get_active_season_id, get_guardian_contacts_cached
from services.bus_utils import get_bus_color
from bus_config import (
    get_bus_driver, get_bus_counselor, get_bus_home_location, get_bus_capacity
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Roster"])

@router.get("/route-sheet/{bus_number}")
async def get_route_sheet(bus_number: str):
    """Get printable route sheet with turn-by-turn directions for a specific bus"""
    try:
        # Get campers for this bus (check both AM and PM bus fields)
        campers = await db.campers.find({
            "$or": [
                {"am_bus_number": bus_number},
                {"pm_bus_number": bus_number}
            ]
        }).to_list(None)
        
        if not campers:
            raise HTTPException(status_code=404, detail=f"No campers found for {bus_number}")
        
        # Generate route sheet with directions
        route_sheet = route_printer.generate_route_sheet(bus_number, campers)
        
        return route_sheet
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating route sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/route-sheet/{bus_number}/print")
async def get_printable_route_sheet(bus_number: str, edit: bool = False):
    """Get printable HTML route sheet with optional edit mode for drag-and-drop reordering"""
    try:
        import urllib.parse
        decoded_bus = urllib.parse.unquote(bus_number)
        
        # Get campers for this bus
        campers = await db.campers.find({
            "$or": [
                {"am_bus_number": decoded_bus},
                {"pm_bus_number": decoded_bus}
            ]
        }).to_list(None)
        
        if not campers:
            return HTMLResponse(content=f"<h1>No campers found for {decoded_bus}</h1>", status_code=404)
        
        # Check for custom route order
        season_id = await get_active_season_id()
        route_order = None
        if season_id:
            route_order = await db.route_orders.find_one({
                "bus_number": decoded_bus,
                "season_id": season_id
            })
        
        # Generate route sheet
        route_sheet = route_printer.generate_route_sheet(decoded_bus, campers)
        
        # Apply custom order if exists
        if route_order:
            am_order = route_order.get("am_order", [])
            pm_order = route_order.get("pm_order", [])
            
            if am_order and route_sheet.get("am_stops"):
                route_sheet["am_stops"] = reorder_stops(route_sheet["am_stops"], am_order)
                route_sheet["custom_am_order"] = True
            
            if pm_order and route_sheet.get("pm_stops"):
                route_sheet["pm_stops"] = reorder_stops(route_sheet["pm_stops"], pm_order)
                route_sheet["custom_pm_order"] = True
        
        # Generate HTML (with edit mode if requested)
        if edit:
            html = generate_editable_route_html(route_sheet, decoded_bus)
        else:
            html = route_printer.generate_printable_html(route_sheet)
        
        # Return with no-cache headers to ensure fresh data after reset
        response = HTMLResponse(content=html)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        logging.error(f"Error generating printable route: {str(e)}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

def reorder_stops(stops: List[Dict], order: List[str]) -> List[Dict]:
    """Reorder stops based on custom order list"""
    if not order or not stops:
        return stops
    
    # Create lookup by address (since order contains addresses)
    stop_lookup = {}
    for stop in stops:
        addr = stop.get("address", "").strip().lower()
        stop_lookup[addr] = stop
    
    # Reorder based on custom order
    reordered = []
    used_addresses = set()
    
    for addr in order:
        addr_lower = addr.strip().lower()
        if addr_lower in stop_lookup and addr_lower not in used_addresses:
            stop = stop_lookup[addr_lower].copy()
            stop["stop_number"] = len(reordered) + 1
            reordered.append(stop)
            used_addresses.add(addr_lower)
    
    # Add any remaining stops not in the custom order
    for stop in stops:
        addr = stop.get("address", "").strip().lower()
        if addr not in used_addresses:
            stop_copy = stop.copy()
            stop_copy["stop_number"] = len(reordered) + 1
            reordered.append(stop_copy)
    
    return reordered

def generate_editable_route_html(route_sheet: Dict[str, Any], bus_number: str) -> str:
    """Generate editable HTML route sheet with drag-and-drop (mobile + desktop compatible)"""
    
    home_label = route_sheet.get('home_label', 'Home')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit Route - {route_sheet['bus_number']}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
            body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 10px; }}
            .header {{ background: #1e40af; color: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; }}
            .header h1 {{ margin: 0; font-size: 1.3em; }}
            .header p {{ margin: 5px 0 0 0; font-size: 0.9em; opacity: 0.9; }}
            .edit-notice {{ background: #fef3c7; border: 2px solid #f59e0b; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9em; }}
            .routes-container {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
            @media (min-width: 768px) {{ .routes-container {{ grid-template-columns: 1fr 1fr; }} }}
            .route-section {{ background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; }}
            .route-section h2 {{ color: #1e40af; margin-top: 0; font-size: 1.1em; }}
            .route-section p {{ font-size: 0.85em; color: #666; }}
            .stop-list {{ min-height: 100px; }}
            .stop-item {{ 
                background: white; 
                border: 2px solid #d1d5db; 
                padding: 12px; 
                margin: 8px 0; 
                border-radius: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
                transition: all 0.15s;
                touch-action: none;
                user-select: none;
                -webkit-user-select: none;
            }}
            .stop-item:active {{ background: #dbeafe; border-color: #3b82f6; }}
            .stop-item.dragging {{ 
                opacity: 0.9; 
                transform: scale(1.02); 
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                z-index: 1000;
                background: #eff6ff;
                border-color: #3b82f6;
            }}
            .stop-item.drag-over {{ 
                border: 2px dashed #3b82f6; 
                background: #dbeafe;
                transform: scale(0.98);
            }}
            .stop-number {{ 
                background: #3b82f6; 
                color: white; 
                min-width: 32px; 
                height: 32px; 
                border-radius: 50%; 
                display: flex; 
                align-items: center; 
                justify-content: center;
                font-weight: bold;
                font-size: 14px;
                flex-shrink: 0;
            }}
            .drag-handle {{ 
                cursor: grab; 
                color: #6b7280; 
                font-size: 24px; 
                padding: 5px;
                touch-action: none;
            }}
            .stop-info {{ flex-grow: 1; min-width: 0; }}
            .stop-name {{ font-weight: bold; color: #1f2937; font-size: 0.95em; }}
            .stop-address {{ color: #6b7280; font-size: 0.8em; margin-top: 2px; word-break: break-word; }}
            .buttons {{ 
                display: flex; 
                flex-wrap: wrap;
                gap: 8px; 
                margin: 15px 0; 
                justify-content: center; 
                position: sticky;
                top: 0;
                background: white;
                padding: 10px 0;
                z-index: 100;
                border-bottom: 1px solid #e5e7eb;
            }}
            .btn {{ 
                padding: 12px 16px; 
                border: none; 
                border-radius: 8px; 
                font-size: 14px; 
                cursor: pointer; 
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .btn-primary {{ background: #2563eb; color: white; }}
            .btn-primary:active {{ background: #1d4ed8; }}
            .btn-success {{ background: #16a34a; color: white; }}
            .btn-success:active {{ background: #15803d; }}
            .btn-secondary {{ background: #6b7280; color: white; }}
            .btn-secondary:active {{ background: #4b5563; }}
            .btn-danger {{ background: #dc2626; color: white; }}
            .btn-danger:active {{ background: #b91c1c; }}
            .save-status {{ 
                text-align: center; 
                padding: 12px; 
                margin: 10px 0; 
                border-radius: 8px; 
                display: none; 
                font-weight: 600;
            }}
            .save-status.success {{ display: block; background: #d1fae5; color: #065f46; }}
            .save-status.error {{ display: block; background: #fee2e2; color: #991b1b; }}
            .save-status.loading {{ display: block; background: #dbeafe; color: #1e40af; }}
            .placeholder {{ 
                border: 2px dashed #3b82f6; 
                background: #dbeafe; 
                border-radius: 8px;
                min-height: 60px;
                margin: 8px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>✏️ Edit Route - {route_sheet['bus_number']}</h1>
            <p>Drag stops to reorder (works on mobile & desktop)</p>
        </div>
        
        <div class="buttons">
            <button class="btn btn-success" onclick="saveOrder()">💾 Save</button>
            <button class="btn btn-primary" onclick="printRoute()">🖨️ Print</button>
            <button class="btn btn-danger" onclick="resetOrder()">🔄 Reset</button>
            <button class="btn btn-secondary" onclick="window.close()">✕ Close</button>
        </div>
        
        <div id="saveStatus" class="save-status"></div>
        
        <div class="edit-notice">
            <strong>📱 Tip:</strong> Touch and hold a stop, then drag it to a new position. Release to drop.
        </div>
        
        <div class="routes-container">
            <div class="route-section">
                <h2>🌅 AM Pickups</h2>
                <p>{home_label} → Camp</p>
                <div class="stop-list" id="amStops">
    """
    
    for stop in route_sheet.get("am_stops", []):
        camper_names = stop.get("camper_name", "Unknown")
        address = stop.get("address", "")
        html += f"""
                    <div class="stop-item" data-address="{address}">
                        <span class="drag-handle">☰</span>
                        <span class="stop-number">{stop['stop_number']}</span>
                        <div class="stop-info">
                            <div class="stop-name">{camper_names}</div>
                            <div class="stop-address">{address}</div>
                        </div>
                    </div>
        """
    
    html += f"""
                </div>
            </div>
            
            <div class="route-section">
                <h2>🌆 PM Drop-offs</h2>
                <p>Camp → {home_label}</p>
                <div class="stop-list" id="pmStops">
    """
    
    for stop in route_sheet.get("pm_stops", []):
        camper_names = stop.get("camper_name", "Unknown")
        address = stop.get("address", "")
        html += f"""
                    <div class="stop-item" data-address="{address}">
                        <span class="drag-handle">☰</span>
                        <span class="stop-number">{stop['stop_number']}</span>
                        <div class="stop-info">
                            <div class="stop-name">{camper_names}</div>
                            <div class="stop-address">{address}</div>
                        </div>
                    </div>
        """
    
    html += f"""
                </div>
            </div>
        </div>
        
        <script>
            const API_URL = window.location.origin + '/api';
            const BUS_NUMBER = '{bus_number}';
            
            // Universal drag and drop (touch + mouse)
            class DragDropList {{
                constructor(containerId) {{
                    this.container = document.getElementById(containerId);
                    this.draggedItem = null;
                    this.placeholder = null;
                    this.touchStartY = 0;
                    this.touchStartX = 0;
                    this.initialTop = 0;
                    this.initialLeft = 0;
                    
                    this.init();
                }}
                
                init() {{
                    this.container.querySelectorAll('.stop-item').forEach(item => {{
                        // Mouse events
                        item.addEventListener('mousedown', (e) => this.onDragStart(e, item));
                        
                        // Touch events
                        item.addEventListener('touchstart', (e) => this.onTouchStart(e, item), {{ passive: false }});
                        item.addEventListener('touchmove', (e) => this.onTouchMove(e), {{ passive: false }});
                        item.addEventListener('touchend', (e) => this.onTouchEnd(e));
                    }});
                    
                    // Mouse move/up on document
                    document.addEventListener('mousemove', (e) => this.onMouseMove(e));
                    document.addEventListener('mouseup', (e) => this.onDragEnd(e));
                }}
                
                onDragStart(e, item) {{
                    if (e.button !== 0) return;
                    e.preventDefault();
                    this.startDrag(item, e.clientX, e.clientY);
                }}
                
                onTouchStart(e, item) {{
                    if (e.touches.length !== 1) return;
                    const touch = e.touches[0];
                    this.touchStartX = touch.clientX;
                    this.touchStartY = touch.clientY;
                    
                    // Start drag after a short delay to distinguish from scroll
                    this.touchTimer = setTimeout(() => {{
                        e.preventDefault();
                        this.startDrag(item, touch.clientX, touch.clientY);
                        if (navigator.vibrate) navigator.vibrate(50);
                    }}, 150);
                }}
                
                startDrag(item, x, y) {{
                    this.draggedItem = item;
                    const rect = item.getBoundingClientRect();
                    
                    // Store original position
                    this.initialTop = rect.top;
                    this.initialLeft = rect.left;
                    this.offsetX = x - rect.left;
                    this.offsetY = y - rect.top;
                    
                    // Create placeholder
                    this.placeholder = document.createElement('div');
                    this.placeholder.className = 'placeholder';
                    this.placeholder.style.height = rect.height + 'px';
                    item.parentNode.insertBefore(this.placeholder, item);
                    
                    // Style dragged item
                    item.classList.add('dragging');
                    item.style.position = 'fixed';
                    item.style.width = rect.width + 'px';
                    item.style.top = rect.top + 'px';
                    item.style.left = rect.left + 'px';
                    item.style.zIndex = '1000';
                }}
                
                onMouseMove(e) {{
                    if (!this.draggedItem) return;
                    e.preventDefault();
                    this.moveDrag(e.clientX, e.clientY);
                }}
                
                onTouchMove(e) {{
                    if (this.touchTimer) {{
                        const touch = e.touches[0];
                        const dx = Math.abs(touch.clientX - this.touchStartX);
                        const dy = Math.abs(touch.clientY - this.touchStartY);
                        if (dx > 10 || dy > 10) {{
                            clearTimeout(this.touchTimer);
                            this.touchTimer = null;
                        }}
                    }}
                    
                    if (!this.draggedItem) return;
                    e.preventDefault();
                    const touch = e.touches[0];
                    this.moveDrag(touch.clientX, touch.clientY);
                }}
                
                moveDrag(x, y) {{
                    if (!this.draggedItem) return;
                    
                    // Move dragged item
                    this.draggedItem.style.top = (y - this.offsetY) + 'px';
                    this.draggedItem.style.left = (x - this.offsetX) + 'px';
                    
                    // Find drop target
                    const items = [...this.container.querySelectorAll('.stop-item:not(.dragging)')];
                    let closestItem = null;
                    let closestDistance = Infinity;
                    
                    items.forEach(item => {{
                        const rect = item.getBoundingClientRect();
                        const itemCenterY = rect.top + rect.height / 2;
                        const distance = Math.abs(y - itemCenterY);
                        
                        if (distance < closestDistance) {{
                            closestDistance = distance;
                            closestItem = item;
                        }}
                        
                        item.classList.remove('drag-over');
                    }});
                    
                    if (closestItem && closestDistance < 80) {{
                        const rect = closestItem.getBoundingClientRect();
                        const insertBefore = y < rect.top + rect.height / 2;
                        
                        if (insertBefore) {{
                            this.container.insertBefore(this.placeholder, closestItem);
                        }} else {{
                            this.container.insertBefore(this.placeholder, closestItem.nextSibling);
                        }}
                    }}
                }}
                
                onTouchEnd(e) {{
                    if (this.touchTimer) {{
                        clearTimeout(this.touchTimer);
                        this.touchTimer = null;
                    }}
                    this.onDragEnd(e);
                }}
                
                onDragEnd(e) {{
                    if (!this.draggedItem) return;
                    
                    // Insert at placeholder position
                    if (this.placeholder && this.placeholder.parentNode) {{
                        this.placeholder.parentNode.insertBefore(this.draggedItem, this.placeholder);
                        this.placeholder.remove();
                    }}
                    
                    // Reset styles
                    this.draggedItem.classList.remove('dragging');
                    this.draggedItem.style.position = '';
                    this.draggedItem.style.width = '';
                    this.draggedItem.style.top = '';
                    this.draggedItem.style.left = '';
                    this.draggedItem.style.zIndex = '';
                    
                    this.draggedItem = null;
                    this.placeholder = null;
                    
                    // Update numbers
                    this.updateNumbers();
                }}
                
                updateNumbers() {{
                    this.container.querySelectorAll('.stop-item').forEach((item, index) => {{
                        item.querySelector('.stop-number').textContent = index + 1;
                    }});
                }}
            }}
            
            function getStopOrder(containerId) {{
                const container = document.getElementById(containerId);
                return [...container.querySelectorAll('.stop-item')].map(item => item.dataset.address);
            }}
            
            function showStatus(message, type) {{
                const status = document.getElementById('saveStatus');
                status.textContent = message;
                status.className = 'save-status ' + type;
                if (type === 'success' || type === 'error') {{
                    setTimeout(() => status.className = 'save-status', 3000);
                }}
            }}
            
            async function saveOrder() {{
                showStatus('💾 Saving...', 'loading');
                
                try {{
                    const amOrder = getStopOrder('amStops');
                    await fetch(API_URL + '/route-order', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ bus_number: BUS_NUMBER, route_type: 'am', stop_order: amOrder }})
                    }});
                    
                    const pmOrder = getStopOrder('pmStops');
                    await fetch(API_URL + '/route-order', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ bus_number: BUS_NUMBER, route_type: 'pm', stop_order: pmOrder }})
                    }});
                    
                    showStatus('✅ Route order saved!', 'success');
                    if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
                }} catch (error) {{
                    showStatus('❌ Error: ' + error.message, 'error');
                }}
            }}
            
            async function resetOrder() {{
                if (!confirm('Reset to auto-generated order?')) return;
                showStatus('🔄 Resetting...', 'loading');
                
                try {{
                    const response = await fetch(API_URL + '/route-order/' + encodeURIComponent(BUS_NUMBER), {{ 
                        method: 'DELETE',
                        headers: {{ 'Content-Type': 'application/json' }}
                    }});
                    const data = await response.json();
                    
                    if (response.ok && data.status === 'success') {{
                        showStatus('✅ Reset complete. Reloading...', 'success');
                        // Force reload without cache
                        setTimeout(() => {{
                            window.location.href = window.location.pathname + '?edit=true&t=' + Date.now();
                        }}, 800);
                    }} else {{
                        showStatus('❌ Error: ' + (data.message || 'Unknown error'), 'error');
                    }}
                }} catch (error) {{
                    console.error('Reset error:', error);
                    showStatus('❌ Error: ' + error.message, 'error');
                }}
            }}
            
            function printRoute() {{
                window.open(API_URL + '/route-sheet/' + encodeURIComponent(BUS_NUMBER) + '/print', '_blank');
            }}
            
            // Initialize
            new DragDropList('amStops');
            new DragDropList('pmStops');
        </script>
    </body>
    </html>
    """
    
    return html


@router.get("/full-roster/print")
async def get_full_roster_print(bus: str = "all"):
    """
    Generate a printable full bus roster with:
    - Bus info header (number, driver, counselor)
    - Camper name, full address, parent phone numbers
    - AM/PM rider status
    - Pickup/Dropoff status
    - Staff and shadows at the bottom
    
    Query params:
    - bus: "all" for all buses, or specific bus number like "Bus #15"
    """
    try:
        season_id = await get_active_season_id()
        
        # Build query based on bus filter
        query = {"season_id": season_id} if season_id else {}
        
        if bus != "all":
            # Filter by specific bus (check both AM and PM)
            query["$or"] = [
                {"am_bus_number": bus},
                {"pm_bus_number": bus}
            ]
        
        # Get campers from database
        campers_cursor = db.campers.find(query)
        campers = await campers_cursor.to_list(length=None)
        
        if not campers:
            return HTMLResponse(content="<h1>No campers found</h1>", status_code=404)
        
        # Get bus staff info for all buses
        bus_staff_cursor = db.bus_staff.find({})
        bus_staff_list = await bus_staff_cursor.to_list(length=None)
        bus_staff_map = {staff.get('bus_number'): staff for staff in bus_staff_list}
        
        # Get shadows
        shadows_cursor = db.shadows.find({"season_id": season_id} if season_id else {})
        shadows_list = await shadows_cursor.to_list(length=None)
        
        # Get staff with addresses
        staff_addresses_cursor = db.staff_addresses.find({"season_id": season_id} if season_id else {})
        staff_addresses_list = await staff_addresses_cursor.to_list(length=None)
        
        # Get guardian contacts using the CampMinder family relationship API
        guardian_contacts = await get_guardian_contacts_cached(campers)
        logging.info(f"Loaded guardian contacts for {sum(1 for v in guardian_contacts.values() if v)} campers")
        
        # First, group camper records by name to handle AM/PM address differences
        # Some campers have separate records for AM pickup address and PM dropoff address
        camper_records = {}  # name_key -> {'am_record': ..., 'pm_record': ..., 'default_record': ...}
        
        for camper in campers:
            first_name = (camper.get('first_name') or '').strip()
            last_name = (camper.get('last_name') or '').strip()
            camper_key = f"{first_name}_{last_name}".lower()
            
            if camper_key not in camper_records:
                camper_records[camper_key] = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'am_bus': camper.get('am_bus_number', ''),
                    'pm_bus': camper.get('pm_bus_number', ''),
                    'am_record': None,  # Record with AM address
                    'pm_record': None,  # Record with PM-only address
                    'default_record': camper,  # Fallback
                    'pickup_dropoff': camper.get('pickup_dropoff', '')
                }
            
            pickup_type = (camper.get('pickup_type') or '').lower()
            
            # Categorize this record based on pickup_type
            if 'pm' in pickup_type and 'am' not in pickup_type:
                # This is a PM-only dropoff address (e.g., "PM Drop-off Only")
                camper_records[camper_key]['pm_record'] = camper
            elif 'am' in pickup_type:
                # This is an AM address (e.g., "AM & PM" or "AM Pick-up Only")
                camper_records[camper_key]['am_record'] = camper
            else:
                # Default/unknown - use as fallback
                if not camper_records[camper_key]['am_record']:
                    camper_records[camper_key]['am_record'] = camper
            
            # Update pickup_dropoff if set
            if camper.get('pickup_dropoff'):
                camper_records[camper_key]['pickup_dropoff'] = camper.get('pickup_dropoff')
        
        # Now build buses_data using the correct address for each route
        buses_data = {}
        
        for camper_key, camper_info in camper_records.items():
            am_bus = camper_info['am_bus']
            pm_bus = camper_info['pm_bus']
            first_name = camper_info['first_name']
            last_name = camper_info['last_name']
            
            # Get guardian contacts
            name_key = f"{first_name}_{last_name}".lower()
            guardians = guardian_contacts.get(name_key, [])
            
            # Format phone numbers - get up to 2 parents
            phone_list = []
            for guardian in guardians[:2]:
                guardian_name = guardian.get('name', 'Parent')
                for phone in guardian.get('phones', [])[:1]:
                    phone_num = phone.get('number', '')
                    if phone_num:
                        phone_list.append({'name': guardian_name, 'phone': phone_num})
            
            # Helper function to get address from a record
            def get_address_from_record(record):
                if not record:
                    return ''
                location = record.get('location', {})
                addr = location.get('address', '') if isinstance(location, dict) else ''
                if not addr:
                    parts = [
                        record.get('address', ''),
                        record.get('town', ''),
                        record.get('state', ''),
                        record.get('zip_code', '')
                    ]
                    addr = ', '.join(filter(None, parts))
                return addr
            
            # Determine which buses to add this camper to
            buses_to_add = []
            
            if bus != "all":
                # Filtering by specific bus
                if am_bus == bus and pm_bus == bus:
                    buses_to_add.append((bus, "AM & PM", camper_info['am_record'] or camper_info['default_record']))
                elif am_bus == bus:
                    buses_to_add.append((bus, "AM only", camper_info['am_record'] or camper_info['default_record']))
                elif pm_bus == bus:
                    buses_to_add.append((bus, "PM only", camper_info['pm_record'] or camper_info['am_record'] or camper_info['default_record']))
            else:
                # All buses
                if am_bus and am_bus.startswith('Bus'):
                    if am_bus == pm_bus:
                        # Same bus for AM and PM - use AM address
                        buses_to_add.append((am_bus, "AM & PM", camper_info['am_record'] or camper_info['default_record']))
                    else:
                        # Different buses - AM bus gets AM address
                        buses_to_add.append((am_bus, "AM only", camper_info['am_record'] or camper_info['default_record']))
                
                if pm_bus and pm_bus.startswith('Bus') and pm_bus != am_bus:
                    # PM bus gets PM address (or AM address if no separate PM address)
                    buses_to_add.append((pm_bus, "PM only", camper_info['pm_record'] or camper_info['am_record'] or camper_info['default_record']))
            
            for bus_num, rider_type, address_record in buses_to_add:
                if bus_num not in buses_data:
                    buses_data[bus_num] = {
                        'campers': [],
                        'shadows': [],
                        'staff': [],
                        'bus_info': bus_staff_map.get(bus_num, {})
                    }
                
                full_address = get_address_from_record(address_record)
                
                buses_data[bus_num]['campers'].append({
                    'name': f"{first_name} {last_name}",
                    'full_address': full_address,
                    'rider_type': rider_type,
                    'pickup_dropoff': camper_info['pickup_dropoff'],
                    'phones': phone_list,
                    'camper_id': str(address_record.get('_id', '')) if address_record else ''
                })
        
        # Add shadows to their buses
        for shadow in shadows_list:
            shadow_bus = shadow.get('bus_number', '')
            if shadow_bus in buses_data:
                buses_data[shadow_bus]['shadows'].append({
                    'name': shadow.get('shadow_name', 'Unknown Shadow'),
                    'camper_name': shadow.get('camper_name', ''),
                    'session': shadow.get('session', '')
                })
        
        # Add staff to their buses
        for staff in staff_addresses_list:
            staff_bus = staff.get('bus_number', '')
            if staff_bus in buses_data:
                buses_data[staff_bus]['staff'].append({
                    'name': staff.get('name', 'Unknown Staff'),
                    'address': staff.get('address', '')
                })
        
        # Sort buses numerically
        sorted_buses = sorted(buses_data.keys(), key=lambda x: int(x.replace('Bus #', '').replace('Bus', '').strip() or '0'))
        
        # Generate HTML
        html = generate_roster_html(sorted_buses, buses_data, bus)
        
        response = HTMLResponse(content=html)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
        
    except Exception as e:
        logging.error(f"Error generating full roster: {str(e)}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


def generate_roster_html(sorted_buses: list, buses_data: dict, bus_filter: str) -> str:
    """Generate printable HTML for the full bus roster with bus info, campers, staff, and shadows"""
    
    title = "Full Bus Roster - All Buses" if bus_filter == "all" else f"Bus Roster - {bus_filter}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ 
                font-family: Arial, sans-serif; 
                max-width: 1000px; 
                margin: 0 auto; 
                padding: 20px;
                font-size: 11px;
            }}
            .page-header {{ 
                background: #1e40af; 
                color: white; 
                padding: 12px 20px; 
                margin-bottom: 20px; 
                border-radius: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .page-header h1 {{ margin: 0; font-size: 1.4em; }}
            .page-header .date {{ font-size: 0.85em; opacity: 0.9; }}
            .print-btn {{
                background: white;
                color: #1e40af;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
                font-size: 12px;
            }}
            .print-btn:hover {{ background: #e0e7ff; }}
            
            .bus-section {{ 
                page-break-after: always;
                margin-bottom: 30px; 
                border: 2px solid #1e40af;
                border-radius: 8px;
                overflow: hidden;
            }}
            .bus-section:last-child {{ page-break-after: auto; }}
            
            .bus-info-header {{ 
                background: #1e40af; 
                color: white;
                padding: 15px 20px; 
            }}
            .bus-info-header h2 {{ margin: 0 0 10px 0; font-size: 1.5em; }}
            .bus-info-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 15px;
                font-size: 12px;
            }}
            .bus-info-item {{
                background: rgba(255,255,255,0.15);
                padding: 8px 12px;
                border-radius: 4px;
            }}
            .bus-info-label {{ font-weight: bold; opacity: 0.9; }}
            .bus-info-value {{ font-size: 1.1em; }}
            
            .campers-section {{ padding: 0; }}
            .section-title {{
                background: #f1f5f9;
                padding: 10px 15px;
                font-weight: bold;
                font-size: 12px;
                border-bottom: 1px solid #e2e8f0;
                color: #1e40af;
            }}
            
            table {{ 
                width: 100%; 
                border-collapse: collapse;
            }}
            th {{ 
                background: #f8fafc; 
                padding: 8px 6px; 
                text-align: left; 
                font-weight: 600;
                border-bottom: 2px solid #e2e8f0;
                font-size: 10px;
            }}
            td {{ 
                padding: 6px; 
                border-bottom: 1px solid #e2e8f0;
                vertical-align: top;
                font-size: 11px;
            }}
            tr:nth-child(even) {{ background: #f8fafc; }}
            .name-cell {{ font-weight: 500; }}
            
            .rider-type {{ 
                display: inline-block;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 600;
            }}
            .rider-am-pm {{ background: #dcfce7; color: #166534; }}
            .rider-am {{ background: #fef3c7; color: #92400e; }}
            .rider-pm {{ background: #dbeafe; color: #1e40af; }}
            
            .status {{ 
                display: inline-block;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9px;
                background: #fce7f3;
                color: #9d174d;
                font-weight: 500;
            }}
            
            .phone-cell {{ font-size: 10px; }}
            .phone-item {{ margin-bottom: 2px; }}
            .phone-name {{ font-weight: 500; color: #374151; }}
            .phone-number {{ color: #1e40af; }}
            .no-phone {{ color: #94a3b8; font-style: italic; font-size: 10px; }}
            
            .staff-shadows-section {{
                background: #fef3c7;
                border-top: 2px solid #f59e0b;
            }}
            .staff-shadows-section .section-title {{
                background: #fef3c7;
                color: #92400e;
            }}
            .staff-item {{
                padding: 8px 15px;
                border-bottom: 1px solid #fcd34d;
                display: flex;
                justify-content: space-between;
            }}
            .staff-item:last-child {{ border-bottom: none; }}
            .staff-name {{ font-weight: 500; }}
            .staff-role {{ 
                font-size: 10px; 
                background: #92400e; 
                color: white; 
                padding: 2px 8px; 
                border-radius: 10px;
            }}
            
            .no-staff {{ 
                padding: 10px 15px; 
                color: #92400e; 
                font-style: italic;
                font-size: 11px;
            }}
            
            .legend {{
                display: flex;
                gap: 15px;
                margin-bottom: 15px;
                flex-wrap: wrap;
                font-size: 10px;
            }}
            .legend-item {{
                display: flex;
                align-items: center;
                gap: 5px;
            }}
            
            @media print {{
                .print-btn {{ display: none; }}
                .page-header {{ background: #1e40af !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                .bus-info-header {{ background: #1e40af !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                .bus-section {{ page-break-after: always; page-break-inside: avoid; }}
                body {{ font-size: 10px; padding: 10px; }}
                .staff-shadows-section {{ background: #fef3c7 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            }}
        </style>
    </head>
    <body>
        <div class="page-header">
            <div>
                <h1>{title}</h1>
                <div class="date">Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
            </div>
            <button class="print-btn" onclick="window.print()">🖨️ Print Roster</button>
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <span class="rider-type rider-am-pm">AM & PM</span> Both routes
            </div>
            <div class="legend-item">
                <span class="rider-type rider-am">AM only</span> Morning only
            </div>
            <div class="legend-item">
                <span class="rider-type rider-pm">PM only</span> Afternoon only
            </div>
            <div class="legend-item">
                <span class="status">Status</span> Special arrangements
            </div>
        </div>
    """
    
    for bus_num in sorted_buses:
        bus_data = buses_data[bus_num]
        campers = bus_data['campers']
        shadows = bus_data.get('shadows', [])
        staff = bus_data.get('staff', [])
        bus_info = bus_data.get('bus_info', {})
        
        # Sort campers by last name
        campers.sort(key=lambda x: x['name'].split()[-1] if x['name'] else '')
        
        driver_name = bus_info.get('driver_name', 'TBD')
        counselor_name = bus_info.get('counselor_name', 'TBD')
        capacity = bus_info.get('capacity', 'N/A')
        
        html += f"""
        <div class="bus-section">
            <div class="bus-info-header">
                <h2>{bus_num}</h2>
                <div class="bus-info-grid">
                    <div class="bus-info-item">
                        <div class="bus-info-label">🚌 Driver</div>
                        <div class="bus-info-value">{driver_name}</div>
                    </div>
                    <div class="bus-info-item">
                        <div class="bus-info-label">👤 Counselor</div>
                        <div class="bus-info-value">{counselor_name}</div>
                    </div>
                    <div class="bus-info-item">
                        <div class="bus-info-label">👥 Campers</div>
                        <div class="bus-info-value">{len(campers)} / {capacity}</div>
                    </div>
                </div>
            </div>
            
            <div class="campers-section">
                <div class="section-title">📋 CAMPER ROSTER</div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 4%">#</th>
                            <th style="width: 16%">Camper Name</th>
                            <th style="width: 28%">Address</th>
                            <th style="width: 8%">Route</th>
                            <th style="width: 12%">Status</th>
                            <th style="width: 32%">Parent Phone Numbers</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for idx, camper in enumerate(campers, 1):
            rider_class = 'rider-am-pm' if 'AM & PM' in camper['rider_type'] else ('rider-am' if 'AM' in camper['rider_type'] else 'rider-pm')
            status_html = f'<span class="status">{camper["pickup_dropoff"]}</span>' if camper['pickup_dropoff'] else '-'
            
            # Format phone numbers
            phones_html = ''
            if camper['phones']:
                phones_html = '<div class="phone-cell">'
                for phone_info in camper['phones']:
                    phones_html += f'<div class="phone-item"><span class="phone-name">{phone_info["name"]}:</span> <span class="phone-number">{phone_info["phone"]}</span></div>'
                phones_html += '</div>'
            else:
                phones_html = '<span class="no-phone">No contacts on file</span>'
            
            html += f"""
                        <tr>
                            <td>{idx}</td>
                            <td class="name-cell">{camper['name']}</td>
                            <td>{camper['full_address']}</td>
                            <td><span class="rider-type {rider_class}">{camper['rider_type']}</span></td>
                            <td>{status_html}</td>
                            <td>{phones_html}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        """
        
        # Add staff and shadows section
        has_staff_or_shadows = len(shadows) > 0 or len(staff) > 0
        
        html += """
            <div class="staff-shadows-section">
                <div class="section-title">👥 STAFF & SHADOWS ON THIS BUS</div>
        """
        
        if has_staff_or_shadows:
            for shadow in shadows:
                html += f"""
                <div class="staff-item">
                    <span class="staff-name">{shadow['name']} (Shadow for {shadow.get('camper_name', 'camper')})</span>
                    <span class="staff-role">Shadow</span>
                </div>
                """
            
            for staff_member in staff:
                html += f"""
                <div class="staff-item">
                    <span class="staff-name">{staff_member['name']}</span>
                    <span class="staff-role">Staff</span>
                </div>
                """
        else:
            html += """
                <div class="no-staff">No additional staff or shadows assigned to this bus</div>
            """
        
        html += """
            </div>
        </div>
        """
    
    html += """
    </body>
    </html>
    """
    
    return html



