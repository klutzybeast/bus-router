import requests
import time

base_url = "https://camperbuses.preview.emergentagent.com/api"

print("="*60)
print("AUTO-SYNC DETAILED TEST")
print("="*60)

# First, check current database state
print("\n1. Current database state:")
response = requests.get(f"{base_url}/campers", timeout=30)
if response.status_code == 200:
    campers_before = response.json()
    print(f"   Campers with valid locations: {len(campers_before)}")

# Trigger auto-sync
print("\n2. Triggering auto-sync...")
response = requests.post(f"{base_url}/trigger-sync", json={}, timeout=120)
print(f"   Response: {response.status_code}")
if response.status_code == 200:
    print(f"   {response.json()}")

# Wait a moment for sync to complete
time.sleep(2)

# Check database state after sync
print("\n3. Database state after auto-sync:")
response = requests.get(f"{base_url}/campers", timeout=30)
if response.status_code == 200:
    campers_after = response.json()
    print(f"   Campers with valid locations: {len(campers_after)}")
    print(f"   Difference: {len(campers_after) - len(campers_before)}")

# Check sync status
print("\n4. Auto-sync status:")
response = requests.get(f"{base_url}/auto-sync-status", timeout=30)
if response.status_code == 200:
    status = response.json()
    print(f"   Last sync: {status.get('last_sync')}")
    sync_info = status.get('sync_info', {})
    if sync_info:
        print(f"   New campers: {sync_info.get('new_campers', 0)}")
        print(f"   Updated campers: {sync_info.get('updated_campers', 0)}")
        print(f"   Deleted campers: {sync_info.get('deleted_campers', 0)}")
        print(f"   Status: {sync_info.get('status')}")

print("\n" + "="*60)
print("CONCLUSION")
print("="*60)
print(f"Auto-sync is DELETING campers!")
print(f"This happens because:")
print(f"1. Geocoding failures cause campers to not be added to sheet_camper_ids")
print(f"2. Then they get deleted from database (line 854 in server.py)")
print(f"3. The sync logic should add ALL campers, even if geocoding fails")
