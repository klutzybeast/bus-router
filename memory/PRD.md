# Camp Bus Routing System - Product Requirements Document

## Overview
A web application that displays camper bus routes on a Google Map, using Google Sheets as the primary data source. The system manages AM and PM bus assignments for campers attending camp.

## Primary Data Source
- **Google Sheet**: `https://docs.google.com/spreadsheets/d/1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k/edit`
- **Webhook for Updates**: `https://script.google.com/macros/s/AKfycbybQKEZ4G0bBTMuLK7dOju864j_0rZyJ8pKpsP_hLnBNZGb3JN_n3xDgJd9AlpWyG4I/exec`

## CampMinder API Status
- **Status**: BLOCKED
- Partial integration exists but custom field access (bus assignments) is blocked by the API provider
- User needs to contact CampMinder support to upgrade subscription for custom field access
- Field IDs identified: AM Bus (20852), PM Bus (20853)

---

## What's Been Implemented

### Phase 1: Core Map Display ✅
- Google Map with camper pins
- Color-coded pins by bus number (33 unique colors)
- Search functionality by name, address, town
- Click on pin to see camper details

### Phase 2: Data Sync ✅
- Auto-sync from Google Sheet every 15 minutes
- Manual refresh button
- Two-way sync: Changes in app write back to Google Sheet via webhook

### Phase 3: Route Management ✅
- Separate AM and PM bus assignments
- Different AM/PM addresses for campers who need them
- Campers correctly appear ONLY on their assigned bus routes
- PM-only campers (car drop-off AM) supported

### Phase 4: Route Sheets ✅
- Printable HTML route sheets
- Turn-by-turn directions via Google Directions API
- Separate AM and PM routes with correct campers
- Distance and time estimates
- Route logic:
  - AM Route: Driver Home → Camper Pickups → Camp
  - PM Route: Camp → Camper Drop-offs → Driver Home

### Phase 5: UI Features ✅
- Add Camper Manually dialog
- "Needs Address" section showing campers without addresses
- Filter by session type
- Download bus assignments CSV

### Phase 12: Geocoding Cache + PositionStack Backup ✅ (January 2025)
- **MongoDB geocoding cache** - addresses geocoded once, never re-geocoded
- **Eliminated $547/3-day billing issue** - cache prevents repeated API calls
- **PositionStack as backup** - free tier (100/month) for new addresses when Google fails
- **Cache stats endpoint**: `/api/geocode-cache-stats`
- **Current cache**: 367+ addresses stored
- **Memory + DB cache** - fast lookups with persistence
- Scrollable bus list in sidebar

### Phase 6: Change Detection System ✅ (December 2024)
- `/api/detect-changes` endpoint implemented
- Detects AM/PM bus additions, removals, and changes
- Automatically syncs detected changes to Google Sheet
- Categorizes changes by type (AM_ADDED, PM_ADDED, AM_CHANGED, PM_CHANGED, etc.)

### Phase 7: Bus Staff Configuration ✅ (January 2025)
- Full CRUD operations for bus staff (drivers, counselors)
- Backend endpoints: GET/POST/DELETE `/api/bus-staff`
- Configure driver name, counselor name, home address, location name, capacity per bus
- Staff info displayed in map InfoWindow pop-ups when clicking camper markers
- Staff info included in Seat Availability CSV downloads
- Geocoding of driver home addresses for route start/end points
- UI: "Configure Bus Staff" dialog with form and configured buses list

### Phase 8: Download Buttons Fix ✅ (January 2025)
- Fixed download buttons to work on both desktop AND mobile devices
- Uses direct link approach with `target="_blank"` for better mobile compatibility
- Backend endpoints return proper headers for CSV downloads:
  - `Content-Type: text/csv; charset=utf-8`
  - `Content-Disposition: attachment; filename="..."`
  - `Access-Control-Expose-Headers: Content-Disposition`
- Toast notifications show download status
- Fallback to opening in new tab if primary method fails

### Phase 10: Dynamic Bus Zones ✅ (January 2025)
- **USER-DEFINED ZONES** - replaced auto-calculated convex hull zones
- Users can now create custom polygon zones for each bus:
  - Click on map to place polygon vertices
  - Drag vertices to adjust zone shape
  - Right-click vertices to delete them
  - Zones saved to database and persist between sessions
- **Zone Management Panel**:
  - "+ Zone" button to create new zone for a bus
  - Edit button (✎) to modify existing zones
  - Delete button (×) to remove zones
  - Visual indicators showing which buses have zones
- One zone per bus (user-controlled, not auto-generated)
- Color-coded zones matching bus colors
- Toggle to show/hide all zones

### Phase 11: Seat Availability in Bus List ✅ (January 2025)
- Each bus in the sidebar now shows:
  - **H1** (Half Season 1) seats remaining
  - **H2** (Half Season 2) seats remaining
  - **Cap** (Capacity) of the bus
- Color-coded availability: green (available), orange (≤3 left), red (overbooked)
- Dynamically calculated based on camper session types
- Bus info fetched from `/api/buses` endpoint including capacity data

### Phase 13: Enhanced Seat Availability Excel Report ✅ (January 2025)
- Downloadable Excel report now includes **detailed availability columns**:
  - Half 1 AM, **H1 AM Avail**, Half 1 PM, **H1 PM Avail**
  - Half 2 AM, **H2 AM Avail**, Half 2 PM, **H2 PM Avail**
- **Conditional color formatting** on availability columns:
  - 🟢 Green: >10 seats available
  - 🟠 Orange: 5-10 seats available  
  - 🔴 Red: <5 seats available (includes overbooked buses)
- Summary section at bottom with totals by half session
- Professional formatting with headers, alternating row colors, frozen header row
- **Separate webhook** for Seat Availability Google Sheet updates (`SEAT_AVAILABILITY_WEBHOOK_URL`)

### Phase 14: Shadow Staff Feature ✅ (January 2025)
- **Shadow = 1:1 staff member** assigned to accompany a specific camper
- Shadows take a bus seat and are counted in seat availability
- Shadow inherits the bus number and session from their linked camper
- **UI**: "Add Shadow" button in camper InfoWindow popup
  - Click to expand input form for shadow name
  - Saved shadow shows in purple background with delete (X) button
- **Backend CRUD endpoints**:
  - `GET /api/shadows` - Get all shadows
  - `GET /api/shadows/by-bus/{bus_number}` - Get shadows on a specific bus
  - `GET /api/shadows/by-camper/{camper_id}` - Get shadow for a specific camper
  - `POST /api/shadows` - Create shadow (requires shadow_name and camper_id)
  - `DELETE /api/shadows/{shadow_id}` - Delete shadow
- Shadows stored in MongoDB `shadows` collection

### Phase 9: Code Refactoring (Foundation Ready)
- Created modular structure in `/app/backend/`:
  - `models/` - Pydantic schemas
  - `services/` - Database, geocoding, bus utilities
  - `routers/` - Route handlers for campers, sync, routes, audit
- Original `server.py` remains entry point for stability

---

## Current Stats (as of January 2025)
- **492 campers** on map
- **34 buses** configured
- **33 active buses** with campers
- **1 shadow staff** assigned

---

## Key Files
| File | Purpose |
|------|---------|
| `/app/backend/server.py` | Main FastAPI application (2596 lines) |
| `/app/backend/route_printer.py` | Route sheet generation |
| `/app/backend/bus_config.py` | Bus info and home locations |
| `/app/backend/sibling_offset.py` | Pin offset for siblings |
| `/app/frontend/src/components/BusRoutingMap.jsx` | Main React map component |
| `/app/frontend/src/components/EditableBusZone.jsx` | User-editable bus zone component |
| `/app/frontend/src/components/ZoneCreator.jsx` | Zone drawing/creation component |
| `/app/backend/models/schemas.py` | Pydantic models |
| `/app/backend/routers/*.py` | Modular route handlers |

---

## API Endpoints

### Core Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/campers` | GET | Get all campers with valid locations |
| `/api/campers/needs-address` | GET | Get campers needing addresses |
| `/api/campers/add` | POST | Manually add a camper |
| `/api/campers/{id}` | DELETE | Delete a camper |
| `/api/campers/{id}/change-bus` | POST | Change camper's bus assignment |

### Sync Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trigger-sync` | POST | Manual sync from Google Sheet |
| `/api/sync-to-google-sheet` | POST | Sync all assignments to sheet |
| `/api/detect-changes` | POST | Detect and sync bus assignment changes |

### Route Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/buses` | GET | Get all buses with info |
| `/api/buses/{number}` | GET | Get specific bus details |
| `/api/route-sheet/{bus}/print` | GET | Printable route sheet HTML |
| `/api/download/bus-assignments` | GET | Download CSV |
| `/api/download/seat-availability` | GET | Download seat availability CSV |

### Bus Staff Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/bus-staff` | GET | Get all configured bus staff |
| `/api/bus-staff` | POST | Create/update bus staff config |
| `/api/bus-staff/{bus_number}` | GET | Get staff for specific bus |
| `/api/bus-staff/{bus_number}` | DELETE | Delete staff configuration |

### Audit Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/audit/campers` | GET | Full camper audit vs Google Sheet |
| `/api/audit/bus/{number}` | GET | Audit single bus |

---

## Backlog

### P1 - High Priority
- [ ] Complete migration to modular routers (reduces `server.py` from 2596 lines)
- [ ] Refactor `BusRoutingMap.jsx` - extract UI panels into separate components
- [ ] Resolve CampMinder API access (requires user action with provider)

### P2 - Medium Priority  
- [ ] Bus capacity dashboard for admins
- [ ] Historical route tracking

### P3 - Low Priority
- [ ] Deprecate Google Sheet sync once CampMinder API works
- [ ] Mobile app version

---

## Known Limitations
1. CampMinder API custom field access blocked by subscription level
2. Campers without addresses cannot be shown on map
3. Google Sheets data entry inconsistencies require manual cleanup

---

## Environment Variables
```
# Backend (.env)
MONGO_URL=<mongodb connection>
DB_NAME=<database name>
GOOGLE_MAPS_API_KEY=<google maps key>
CAMPMINDER_SHEET_ID=1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k
GOOGLE_SHEETS_WEBHOOK_URL=<webhook url>
AUTO_SYNC_ENABLED=true
SYNC_INTERVAL_MINUTES=15

# Frontend (.env)
REACT_APP_BACKEND_URL=<backend url>
REACT_APP_GOOGLE_MAPS_API_KEY=<google maps key>
```

---

## Last Updated
January 2025 - Shadow Staff feature: 1:1 staff members assigned to accompany specific campers, with seat availability integration
