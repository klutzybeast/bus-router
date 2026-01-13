# Camp Bus Routing System - PRD

## Original Problem Statement
The user wants a web application to display camper bus routes on a Google Map. The system should pull camper data (including name, address, and bus assignment) from a Google Sheet and display color-coded pins for each camper based on their assigned bus number. The system must handle campers with different AM and PM bus assignments, auto-sync from Google Sheet every 15 minutes, and write changes back to the sheet when bus assignments are updated in the UI.

## Core Requirements
- Display campers on a Google Map with color-coded pins by bus number
- Automatically sync camper data from Google Sheet (every 15 minutes)
- Handle separate AM and PM bus assignments
- Generate printable route sheets for drivers with turn-by-turn directions
- Manage and assign buses to campers
- Generate seat availability reports
- Bidirectional sync with Google Sheet (read and write)

## Technical Stack
- **Backend**: FastAPI (Python) with Motor (async MongoDB driver)
- **Frontend**: React with @react-google-maps/api
- **Database**: MongoDB
- **Integrations**: Google Maps API (Geocoding, Directions, Maps JavaScript), Google Sheets (via CSV export and Apps Script webhook), CampMinder API (partial)

## CampMinder API Integration Status (Updated: Jan 2026)

### Working Endpoints:
| Endpoint | Status | Description |
|----------|--------|-------------|
| `/auth/apikey` | ✅ | Authentication - JWT token obtained |
| `/api/entity/customfield/GetFieldDefs` | ✅ | Retrieved 602 field definitions |
| `/api/entity/person/camper/GetActiveCamper` | ✅ | Retrieved 736 active campers |
| `/api/entity/person/GetPersons` | ✅ | Retrieved 14,921 person records |
| `/api/entity/family/GetFamilyAddresses` | ✅ | Retrieved addresses for 12,896 families |

### Not Working (Subscription Level):
| Endpoint | Status | Issue |
|----------|--------|-------|
| `/api/entity/customfield/GetCustomFieldData` | ⚠️ | Returns empty - requires higher API access |
| `/api/entity/customfield/GetEntityFieldContainers` | ⚠️ | Returns empty - requires higher API access |
| `/api/travel/day/*` | ❌ | "Day travel API is not enabled" |

### Bus Field IDs:
- AM Bus: Field ID **20852** (Name: "Bus#AM Bus")
- PM Bus: Field ID **20853** (Name: "Bus#PM Bus")

### Recommendation:
Continue using Google Sheets as primary data source for bus assignments until CampMinder API subscription is upgraded to include custom field access.

## Data Source
- **Primary**: Google Sheet at `https://docs.google.com/spreadsheets/d/1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k/edit`
- **Seat Availability Sheet**: `https://docs.google.com/spreadsheets/d/1ZK58gjF4BO0HF_2y6oovrjzRH3qV5zAs8H-7CeKOSGE/edit`
- **Webhook URL**: `https://script.google.com/macros/s/AKfycbybQKEZ4G0bBTMuLK7dOju864j_0rZyJ8pKpsP_hLnBNZGb3JN_n3xDgJd9AlpWyG4I/exec`

## What's Been Implemented

### Phase 1: Core Map Display ✅
- Google Map with camper pins
- Color-coded pins by bus number (33 unique colors)
- Search functionality
- Click on pin to see camper details

### Phase 2: Data Sync ✅
- Auto-sync from Google Sheet every 15 minutes
- Manual refresh button
- Instant write-back to Google Sheet when bus changed in UI

### Phase 3: Route Management ✅
- Separate AM and PM bus assignments
- Different AM/PM addresses for campers who need them
- Campers correctly appear ONLY on their assigned bus routes
- PM-only campers (AM bus = NONE) supported

### Phase 4: Route Sheets ✅
- Printable HTML route sheets
- Turn-by-turn directions via Google Directions API
- Separate AM and PM routes with correct campers
- Distance and time estimates

### Phase 5: UI Features ✅
- Add Camper Manually button/dialog
- "Needs Address" section showing 15 campers without addresses
- Filter by session type
- Download bus assignments CSV

## Current Stats (as of Jan 13, 2026)
- **481 campers** on map
- **15 campers** need addresses (have bus but no address in sheet)
- **33 active buses**
- **12 campers** with different AM/PM bus assignments

## Key Files
- `/app/backend/server.py` - Main FastAPI app
- `/app/backend/route_printer.py` - Route sheet generation
- `/app/backend/sibling_offset.py` - Pin offset for siblings at same address
- `/app/frontend/src/components/BusRoutingMap.jsx` - Main React component

## Known Limitations
- CampMinder API integration partially working (custom field access requires subscription upgrade)
- Campers without addresses cannot be shown on map
- Google Sheets data entry inconsistencies (some PM buses in wrong column)

## Future Enhancements (Backlog)
- P1: Refactor server.py into smaller modules
- P2: Clean up abandoned CampMinder code
- P3: Add admin dashboard for bus capacity management
