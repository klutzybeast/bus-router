# Camp Bus Routing - CSV Sync Bug Report

## Test Date: 2026-01-11
## Tester: T1 (Testing Agent)

---

## EXECUTIVE SUMMARY

**CRITICAL DATA LOSS BUG IDENTIFIED**

The auto-sync functionality is deleting 143 campers (25% data loss) due to geocoding failures. Manual CSV sync is missing 11 campers. Root cause: When Google Maps geocoding fails, campers are completely skipped instead of being added with placeholder coordinates.

---

## TEST RESULTS

### Expected Data (from Google Sheet)
- Total rows: 695
- Campers with "AM Bus" method: 638
- **Campers with valid bus assignments (not NONE): 583** ✓
- Campers with addresses: 562
- Campers without addresses: 21
- Campers with different PM addresses: 11

### Manual CSV Sync (`/api/sync-campers`)
- **Reported synced: 593 campers**
- **Actual in database: 593 campers** (verified via MongoDB)
  - With valid locations (lat ≠ 0): 572
  - Without locations (lat = 0): 21
- **Visible via API: 572 campers** (11 missing from API response)
- **Missing: 11 campers** (583 expected - 572 visible)

### Auto-Sync (`/api/trigger-sync`)
- **CRITICAL BUG: Massive data deletion**
- Deleted: 593 campers (100% of existing data)
- Added: 456 new campers
- **Final count: 440 campers** (143 missing!)
- **Missing: 143 campers** (583 expected - 440 actual)

---

## ROOT CAUSE ANALYSIS

### Bug #1: Geocoding Failures Cause Data Loss (CRITICAL)

**Location:** `server.py` lines 180-194 (manual sync) and 773-798 (auto-sync)

**Issue:** When geocoding fails for a camper with an address, they are completely skipped.

```python
# Current buggy code (line 180-194)
if am_address.strip():
    location = geocode_address(am_address, am_town, am_zip)
    if location:  # ← BUG: If geocoding fails, camper is skipped!
        pins.append(CamperPin(...))
else:
    # Only adds if NO address at all
    pins.append(CamperPin(..., latitude=0.0, longitude=0.0))
```

**Impact:**
- Manual sync: ~11 campers skipped (geocoding failures)
- Auto-sync: ~143 campers skipped (geocoding failures + deletions)

**Fix Required:**
```python
if am_address.strip():
    location = geocode_address(am_address, am_town, am_zip)
    if not location:
        # If geocoding fails, add with placeholder coordinates
        location = GeoLocation(latitude=0.0, longitude=0.0, address="GEOCODING FAILED")
    pins.append(CamperPin(...))
```

### Bug #2: Auto-Sync Deletes Campers Not in sheet_camper_ids (CRITICAL)

**Location:** `server.py` lines 851-857

**Issue:** If a camper's geocoding fails, they're not added to `sheet_camper_ids`, then they get deleted.

```python
# Line 773-798: Only adds to sheet_camper_ids if geocoding succeeds
if am_address.strip():
    location = geocode_address(...)
    if location:  # ← If this fails, camper_id NOT added to sheet_camper_ids
        sheet_camper_ids.add(camper_id)
        # ... add to database

# Line 854: Deletes campers not in sheet_camper_ids
if db_camper['_id'] not in sheet_camper_ids:
    await db.campers.delete_one({"_id": db_camper['_id']})  # ← DELETES CAMPER!
```

**Impact:** 143 campers deleted during auto-sync

**Fix Required:** Add camper_id to sheet_camper_ids BEFORE geocoding attempt

### Bug #3: /api/campers Filters Out Campers Without Locations

**Location:** `server.py` line 116

**Issue:** Endpoint filters out campers with lat=0, making them invisible to the API.

```python
# Line 114-116
existing_campers = await db.campers.find({
    "am_bus_number": {"$exists": True, "$nin": ["NONE", ""]},
    "location.latitude": {"$ne": 0.0}  # ← Filters out campers without addresses
}, {"_id": 0}).to_list(None)
```

**Impact:** 21 campers without addresses are in database but invisible via API

**Fix Required:** Remove the latitude filter or add a query parameter to include them

### Bug #4: Missing Addresses Report Uses Wrong Field Name

**Location:** `server.py` line 532

**Issue:** Report looks for `bus_number` field, but database uses `am_bus_number`.

```python
# Line 530-533
missing = await db.campers.find({
    "location.latitude": 0.0,
    "bus_number": {"$exists": True, "$ne": "NONE"}  # ← Wrong field name!
}).to_list(None)
```

**Impact:** Report shows 0 campers missing addresses when there are actually 21

**Fix Required:** Change `bus_number` to `am_bus_number`

---

## DETAILED MISSING CAMPERS

### Campers Without Addresses (21 total)
These are in the database with lat=0 but filtered out by `/api/campers`:

1. Sophia Aiello (Bus #25)
2. Zoe Aiello (Bus #25)
3. Moses Chandler (Bus #01)
4. Oliver DiGioia (Bus #15)
5. John Dillon (Bus #11)
6. Emma Genova (Bus #07)
7. Ava Librizzi (Bus #23)
8. Landon Librizzi (Bus #23)
9. Antonella Mendez (Bus #01)
10. Matthew Mendez (Bus #01)
11. Olivia Mulligan (Bus #16)
12. Sianna Reisman (Bus #01)
13. Gemma Renzo (Bus #02)
14. Siena Schmier (Bus #02)
15. Vincent Schmier (Bus #02)
16. Brooke Sparberg (Bus #19)
17. Sianna Reisman (Bus #01) [duplicate]
18. Gemma Renzo (Bus #02) [duplicate]
19. Siena Schmier (Bus #02) [duplicate]
20. Vincent Schmier (Bus #02) [duplicate]
21. Brooke Sparberg (Bus #19) [duplicate]

### Campers With Geocoding Failures (~11 for manual sync, ~143 for auto-sync)
These have addresses but geocoding failed, so they were skipped entirely.

Sample:
- Brayden Berghorn (Bus #32, Address: "on Jons Bus")

---

## MONGODB VERIFICATION

```bash
# Total campers in database
db.campers.countDocuments({})
# Result: 593 (after manual sync)

# Campers with valid locations
db.campers.countDocuments({"location.latitude": {$ne: 0.0}})
# Result: 572

# Campers without locations
db.campers.countDocuments({"location.latitude": 0.0})
# Result: 21

# Sample camper without address
db.campers.findOne({"location.latitude": 0.0})
# Result: {
#   first_name: 'Sophia',
#   last_name: 'Aiello',
#   location: { latitude: 0, longitude: 0, address: 'ADDRESS NEEDED' },
#   am_bus_number: 'Bus #25',
#   pm_bus_number: 'Bus #25',
#   pickup_type: 'NO ADDRESS'
# }
```

---

## RECOMMENDATIONS

### Priority 1: Fix Geocoding Failure Handling (CRITICAL)
1. Modify `sync-campers` endpoint (lines 180-194)
2. Modify `auto_sync_campminder` function (lines 773-798)
3. Add campers with lat/lng=0 if geocoding fails
4. Add camper_id to sheet_camper_ids BEFORE geocoding attempt

### Priority 2: Fix API Filtering
1. Remove latitude filter from `/api/campers` endpoint (line 116)
2. Or add query parameter to optionally include campers with lat=0

### Priority 3: Fix Missing Addresses Report
1. Change `bus_number` to `am_bus_number` in query (line 532)

### Priority 4: Add Geocoding Error Logging
1. Log which addresses fail geocoding
2. Add retry logic for geocoding failures
3. Consider batch geocoding with error handling

---

## TEST ARTIFACTS

All test scripts available:
- `/app/backend_test.py` - Comprehensive API testing
- `/app/detailed_sync_test.py` - Missing campers analysis
- `/app/auto_sync_test.py` - Auto-sync behavior verification

---

## CONCLUSION

The CSV sync functionality has critical bugs causing data loss:
1. **Manual sync**: 11 campers missing (geocoding failures)
2. **Auto-sync**: 143 campers missing (geocoding failures + deletions)
3. **Root cause**: Geocoding failures cause campers to be skipped entirely
4. **Fix**: Add campers with placeholder coordinates when geocoding fails

**All 583 campers should be imported, with lat/lng=0 for those without addresses or geocoding failures.**
