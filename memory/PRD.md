# Camp Bus Routing System - Product Requirements Document

## Overview
A web application that displays camper bus routes on a Google Map, using Google Sheets as the primary data source. The system manages AM and PM bus assignments for campers attending camp with **multi-season support** for year-over-year data management.

## Primary Data Source
- **Google Sheet**: `https://docs.google.com/spreadsheets/d/1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k/edit`
- **Webhook for Updates**: `https://script.google.com/macros/s/AKfycbybQKEZ4G0bBTMuLK7dOju864j_0rZyJ8pKpsP_hLnBNZGb3JN_n3xDgJd9AlpWyG4I/exec`

## CampMinder API Status
- **Status**: WORKING - Full parent contact integration completed
- Family relationship API working via GetFamilyPersons with 'since' parameter
- Parent phone numbers fetched from person records (PhoneNumbers field)
- 24-hour caching in MongoDB to reduce API calls
- Field IDs identified: AM Bus (20852), PM Bus (20853)

---

## What's Been Implemented

### Phase 19: Codebase Refactoring (April 2026)
- **Backend Refactoring (P1 - COMPLETE)**:
  - `server.py` reduced from **7,391 lines to 629 lines** (91% reduction)
  - 12 modular router files created under `/backend/routers/`
  - Shared services extracted to `/backend/services/` (database, geocoding, helpers, bus_utils)
  - Pydantic models consolidated in `/backend/models/schemas.py`
  - 88 API routes verified working after refactoring
  - Auto-sync and lifecycle functions remain in server.py
- **Router Modules**:
  - `config.py` - Health, status, config endpoints
  - `seasons.py` - Season management CRUD
  - `campers.py` - Camper management
  - `tracking.py` - GPS tracking, attendance, history
  - `shadows.py` - Shadow staff management
  - `zones.py` - Bus zone management
  - `buses.py` - Bus info endpoints
  - `audit.py` - Audit endpoints
  - `staff.py` - Bus staff, assigned staff, staff addresses
  - `sheets.py` - Google Sheets integration
  - `roster.py` - Route sheets and roster printing
  - `sync.py` - CampMinder sync operations
- **Frontend Refactoring**:
  - `BusRoutingMap.jsx` reduced from **3,789 lines to 3,398 lines** (~390 lines extracted)
  - `TrackingDialog.jsx` extracted (203 lines) - Live GPS tracking popup with map, stop detection, camper bubbles
  - `HistoryDialog.jsx` extracted (276 lines) - Self-contained tracking history viewer with date picker, route map, stops table
  - Added `WebkitOverflowScrolling: 'touch'` for iOS momentum scrolling
  - Added `overscrollBehavior: 'contain'` to prevent pull-to-refresh interference
  - Added `position: 'static'` to prevent scroll lock from any parent elements

### Phase 18: GPS Bus Tracking & Counselor App (March 2026)
- **Counselor Mobile Web App** (`/counselor`):
  - Login with bus number as PIN
  - View list of campers assigned to bus
  - Mark attendance (Present/Absent) for each camper
  - Real-time GPS tracking sends location every 30 seconds
  - Wake Lock API for background tracking
- **Admin Live Tracking**:
  - Green "Track" button on each bus card
  - Live bus location on map with auto-refresh
  - Stop detection with camper pickup bubbles (100m radius)
  - Tracking history viewer with date picker
  - Stop duration logging
- **Attendance Reports**: HTML and JSON endpoints

### Phase 17: Camper Card & Roster Enhancements (January 2026)
- Pickup/Dropoff Status dropdown
- Roster updated to show only primary parents (IsPrincipal=True)
- Guardian phone number display on route sheets

### Earlier Phases (Complete)
- Multi-season support with data copy
- CampMinder API integration with guardian contacts
- Google Maps routing with turn-by-turn directions
- Bus zone management with polygon drawing
- Shadow staff tracking
- Staff address CSV upload
- Seat availability tracking
- Auto-sync from Google Sheets (15-min interval)
- Geocoding with caching (Google Maps + PositionStack fallback)
- Editable route sheets
- PWA manifest for counselor "Add to Home Screen"

---

## Code Architecture

```
/app/backend/
  server.py                    # 629 lines - App setup, lifecycle, auto-sync
  routers/
    config.py                  # Health, status, config
    seasons.py                 # Season CRUD
    campers.py                 # Camper management
    tracking.py                # GPS tracking, attendance, history
    shadows.py                 # Shadow staff
    zones.py                   # Bus zones
    buses.py                   # Bus info
    audit.py                   # Audit endpoints
    staff.py                   # Staff management
    sheets.py                  # Google Sheets integration
    roster.py                  # Route sheets, roster printing
    sync.py                    # CampMinder sync
  services/
    database.py                # MongoDB connection, shared instances
    geocoding.py               # Geocoding with caching
    helpers.py                 # Shared helpers (get_active_season_id, etc.)
    bus_utils.py               # Bus colors, utilities
  models/
    schemas.py                 # All Pydantic models

/app/frontend/src/
  App.js                       # Routes: /, /staff-lookup, /counselor
  App.css                      # Global styles (no overflow restrictions)
  pages/
    CounselorApp.jsx           # Counselor PWA with GPS + attendance
    StaffZoneLookupPage.jsx    # Staff zone lookup
  components/
    BusRoutingMap.jsx           # 3398 lines - Main admin dashboard (partially refactored)
    TrackingDialog.jsx          # 203 lines - Live GPS tracking popup (extracted)
    HistoryDialog.jsx           # 276 lines - Tracking history viewer (extracted)
```

---

## Key API Endpoints
- `POST /api/bus-tracking/login` - Counselor login
- `POST /api/bus-tracking/location` - GPS update
- `GET /api/bus-tracking/location/{bus_number}` - Live bus location
- `GET /api/bus-tracking/history/{bus_number}` - Route history
- `GET /api/bus-tracking/attendance-report` - HTML attendance report
- `GET /api/seasons/active` - Active season
- `GET /api/campers` - All campers
- `GET /api/buses` - All buses
- `GET /api/route-sheet/{bus_number}` - Route sheet with directions

---

## Database Collections
- `campers` - Camper records with bus assignments
- `seasons` - Season management
- `bus_locations` - Current GPS coordinates per bus
- `bus_location_history` - GPS tracking history
- `bus_stops_log` - Stop duration records
- `bus_attendance` - Daily attendance records
- `bus_staff` - Bus staff configurations
- `bus_assigned_staff` - Staff bus assignments
- `bus_zones` - Bus zone polygons
- `shadows` - Shadow staff records
- `geocode_cache` - Cached geocoding results
- `sync_status` - Auto-sync status
- `campminder_relatives_cache` - Guardian contact cache

---

## Prioritized Backlog

### P1 (Next)
- **Continue Frontend Refactoring**: Further split `BusRoutingMap.jsx` (3,398 lines)
  - Extract `StaffConfigDialog.jsx` - Staff configuration modal
  - Extract `ShadowDialog.jsx` - Shadow management modal
  - Extract `AddCamperDialog.jsx` - Camper add form
  - Extract `BusSidebar.jsx` - Bus filter sidebar panel
  - Extract custom hooks (`useSeasons`, `useBusData`, `useTracking`)

### P2
- **Parent Bus Tracking**: Let parents track their child's bus
- **PM Attendance Tracking**: Expand AM-only tracking to include PM
- **Parent Notifications**: Notifications when children board/exit

### P3
- **Multi-Tenant SaaS Version**: Support multiple camps
- **Deprecate Google Sheet Sync**: Move entirely to CampMinder API

---

## Known Limitations
- **iOS Background Tracking**: Wake Lock API added but iOS Safari suspends JS after ~15s in background. Counselors must keep app visible.
- **BusRoutingMap.jsx**: Still 3,398 lines - further frontend refactoring ongoing (P1)

## 3rd Party Integrations
- CampMinder API (User API Key)
- Google Maps API (User API Key)
- PositionStack API (User API Key)
- Google Sheets API (User API Key)
