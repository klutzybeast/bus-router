import requests
import csv
from io import StringIO
from collections import defaultdict

# Download CSV
csv_url = "https://docs.google.com/spreadsheets/d/1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k/export?format=csv"
response = requests.get(csv_url, timeout=30)
csv_content = response.text

# Remove BOM if present
if csv_content.startswith('\ufeff'):
    csv_content = csv_content[1:]

csv_file = StringIO(csv_content)
reader = csv.DictReader(csv_file)

# Analyze CSV
expected_campers = []
for row in reader:
    am_method = row.get('Trans-AMDropOffMethod', '')
    
    if 'AM Bus' not in am_method:
        continue
    
    am_bus = row.get('2026Transportation M AM Bus', '')
    
    if not am_bus or 'NONE' in am_bus.upper():
        continue
    
    first_name = row.get('First Name', '')
    last_name = row.get('Last Name', '')
    am_address = row.get('Trans-PickUpAddress', '')
    am_zip = row.get('Trans-PickUpZip', '')
    
    expected_campers.append({
        'name': f"{first_name} {last_name}",
        'first_name': first_name,
        'last_name': last_name,
        'am_bus': am_bus,
        'has_address': bool(am_address.strip()),
        'address': am_address,
        'zip': am_zip
    })

print(f"Expected campers from CSV: {len(expected_campers)}")
print(f"  - With addresses: {sum(1 for c in expected_campers if c['has_address'])}")
print(f"  - Without addresses: {sum(1 for c in expected_campers if not c['has_address'])}")

# Get actual campers from database (including those with lat=0)
# We need to query MongoDB directly or use a different endpoint
base_url = "https://busroutes-6.preview.emergentagent.com/api"

# Try to get all campers including those without locations
# The /api/campers endpoint filters out lat=0, so let's check the sync response
print("\n" + "="*60)
print("TESTING MANUAL SYNC")
print("="*60)

response = requests.post(
    f"{base_url}/sync-campers",
    json={"csv_content": csv_content},
    timeout=120
)

print(f"Sync response: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Synced count: {data.get('count', 0)}")

# Now check what's actually in the database
# Since /api/campers filters out lat=0, we need to check the missing addresses report
response = requests.get(f"{base_url}/reports/missing-addresses", timeout=30)
if response.status_code == 200:
    data = response.json()
    missing_addresses = data.get('campers', [])
    print(f"\nCampers with lat=0 (missing addresses): {len(missing_addresses)}")

# Get campers with valid locations
response = requests.get(f"{base_url}/campers", timeout=30)
if response.status_code == 200:
    actual_campers = response.json()
    print(f"Campers with valid locations: {len(actual_campers)}")
    
    # Create lookup
    actual_names = set()
    for camper in actual_campers:
        name = f"{camper.get('first_name', '')} {camper.get('last_name', '')}"
        actual_names.add(name)
    
    # Find missing campers
    missing = []
    for expected in expected_campers:
        if expected['name'] not in actual_names:
            missing.append(expected)
    
    print(f"\n" + "="*60)
    print(f"MISSING CAMPERS: {len(missing)}")
    print("="*60)
    
    # Group by has_address
    with_address = [c for c in missing if c['has_address']]
    without_address = [c for c in missing if not c['has_address']]
    
    print(f"\nMissing campers WITH addresses: {len(with_address)}")
    if with_address:
        print("Sample (first 10):")
        for camper in with_address[:10]:
            print(f"  - {camper['name']} (Bus: {camper['am_bus']}, Address: {camper['address'][:50]}...)")
    
    print(f"\nMissing campers WITHOUT addresses: {len(without_address)}")
    if without_address:
        print("All campers without addresses:")
        for camper in without_address:
            print(f"  - {camper['name']} (Bus: {camper['am_bus']})")
    
    # Analyze by bus number
    bus_distribution = defaultdict(int)
    for camper in missing:
        bus_distribution[camper['am_bus']] += 1
    
    print(f"\nMissing campers by bus:")
    for bus, count in sorted(bus_distribution.items()):
        print(f"  {bus}: {count} missing")

print("\n" + "="*60)
print("CONCLUSION")
print("="*60)
print(f"Expected: {len(expected_campers)}")
print(f"Actual: {len(actual_campers)}")
print(f"Missing: {len(missing)}")
print(f"\nThe issue is likely:")
print(f"1. Geocoding failures for {len(with_address)} campers with addresses")
print(f"2. Campers without addresses not being added: {len(without_address)}")
