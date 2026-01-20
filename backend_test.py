import requests
import sys
from datetime import datetime
import csv
from io import StringIO

class CampBusRoutingTester:
    def __init__(self, base_url="https://campmap-routes.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.csv_content = None

    def log(self, message, level="INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, json_data=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if json_data:
                    response = requests.post(url, json=json_data, headers=headers, timeout=120)
                else:
                    response = requests.post(url, data=data, headers=headers, timeout=120)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}", "PASS")
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                if response.text:
                    self.log(f"Response: {response.text[:200]}", "ERROR")

            return success, response.json() if response.text and success else {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}", "FAIL")
            return False, {}

    def load_csv_from_google_sheets(self):
        """Download CSV from Google Sheets"""
        self.log("Downloading CSV from Google Sheets...")
        try:
            csv_url = "https://docs.google.com/spreadsheets/d/1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k/export?format=csv"
            response = requests.get(csv_url, timeout=30)
            
            if response.status_code == 200:
                self.csv_content = response.text
                self.log(f"✅ Downloaded CSV ({len(self.csv_content)} chars)", "PASS")
                return True
            else:
                self.log(f"❌ Failed to download CSV: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Error downloading CSV: {str(e)}", "FAIL")
            return False

    def analyze_csv_data(self):
        """Analyze CSV to understand expected counts"""
        self.log("\n" + "="*60)
        self.log("CSV DATA ANALYSIS")
        self.log("="*60)
        
        if not self.csv_content:
            self.log("❌ No CSV content to analyze", "FAIL")
            return
        
        # Remove BOM if present
        csv_content = self.csv_content
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        total_rows = 0
        am_bus_method = 0
        valid_bus_assignment = 0
        no_address = 0
        with_address = 0
        geocoding_needed = 0
        different_pm_address = 0
        filtered_pm_buses = 0
        
        campers_with_address = []
        campers_without_address = []
        
        for row in reader:
            total_rows += 1
            am_method = row.get('Trans-AMDropOffMethod', '')
            
            if 'AM Bus' in am_method:
                am_bus_method += 1
                
                am_bus = row.get('2026Transportation M AM Bus', '')
                pm_bus = row.get('2026Transportation M PM Bus', '')
                
                if am_bus and 'NONE' not in am_bus.upper():
                    valid_bus_assignment += 1
                    
                    am_address = row.get('Trans-PickUpAddress', '')
                    pm_address = row.get('Trans-DropOffAddress', '')
                    
                    if am_address.strip():
                        with_address += 1
                        geocoding_needed += 1
                        campers_with_address.append({
                            'name': f"{row.get('First Name', '')} {row.get('Last Name', '')}",
                            'address': am_address,
                            'town': row.get('Trans-PickUpTown', ''),
                            'zip': row.get('Trans-PickUpZip', ''),
                            'am_bus': am_bus
                        })
                    else:
                        no_address += 1
                        campers_without_address.append({
                            'name': f"{row.get('First Name', '')} {row.get('Last Name', '')}",
                            'am_bus': am_bus
                        })
                    
                    # Check if PM address is different
                    if pm_address.strip() and pm_address != am_address:
                        different_pm_address += 1
                    
                    # Check if PM bus would be filtered
                    if pm_bus and any(x in pm_bus.upper() for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM', 'NONE']):
                        filtered_pm_buses += 1
        
        self.log(f"Total rows in CSV: {total_rows}")
        self.log(f"Campers with 'AM Bus' method: {am_bus_method}")
        self.log(f"Campers with valid bus assignment (not NONE): {valid_bus_assignment}")
        self.log(f"  - With addresses (need geocoding): {with_address}")
        self.log(f"  - Without addresses (lat/lng=0): {no_address}")
        self.log(f"Campers with different PM address: {different_pm_address}")
        self.log(f"PM buses filtered (MAIN TENT/HOCKEY RINK/AUDITORIUM): {filtered_pm_buses}")
        
        self.log(f"\n📊 EXPECTED DATABASE COUNT:")
        self.log(f"  Minimum: {valid_bus_assignment} (one entry per camper)")
        self.log(f"  Maximum: {valid_bus_assignment + different_pm_address} (if PM addresses create separate entries)")
        
        # Show sample campers without addresses
        if campers_without_address:
            self.log(f"\n📋 Sample campers WITHOUT addresses (first 5):")
            for camper in campers_without_address[:5]:
                self.log(f"  - {camper['name']} (Bus: {camper['am_bus']})")
        
        return {
            'total_rows': total_rows,
            'am_bus_method': am_bus_method,
            'valid_bus_assignment': valid_bus_assignment,
            'with_address': with_address,
            'no_address': no_address,
            'different_pm_address': different_pm_address,
            'expected_min': valid_bus_assignment,
            'expected_max': valid_bus_assignment + different_pm_address
        }

    def test_manual_csv_sync(self):
        """Test manual CSV upload via /api/sync-campers"""
        self.log("\n" + "="*60)
        self.log("TEST 1: MANUAL CSV SYNC")
        self.log("="*60)
        
        if not self.csv_content:
            self.log("❌ No CSV content loaded", "FAIL")
            return False
        
        success, response = self.run_test(
            "Manual CSV Sync",
            "POST",
            "sync-campers",
            200,
            json_data={"csv_content": self.csv_content}
        )
        
        if success:
            count = response.get('count', 0)
            self.log(f"📊 Synced {count} campers")
            return count
        
        return 0

    def test_auto_sync(self):
        """Test auto-sync via /api/trigger-sync"""
        self.log("\n" + "="*60)
        self.log("TEST 2: AUTO-SYNC FROM GOOGLE SHEETS")
        self.log("="*60)
        
        success, response = self.run_test(
            "Auto-Sync Trigger",
            "POST",
            "trigger-sync",
            200,
            json_data={}
        )
        
        if success:
            self.log(f"✅ Auto-sync completed successfully")
            return True
        
        return False

    def verify_database_count(self):
        """Verify database count via /api/campers"""
        self.log("\n" + "="*60)
        self.log("DATABASE VERIFICATION")
        self.log("="*60)
        
        success, response = self.run_test(
            "Get All Campers",
            "GET",
            "campers",
            200
        )
        
        if success:
            campers = response if isinstance(response, list) else []
            count = len(campers)
            self.log(f"📊 Database contains {count} campers")
            
            # Count campers with/without addresses
            with_location = sum(1 for c in campers if c.get('location', {}).get('latitude', 0) != 0)
            without_location = count - with_location
            
            self.log(f"  - With valid locations: {with_location}")
            self.log(f"  - Without locations (lat=0): {without_location}")
            
            return count, with_location, without_location
        
        return 0, 0, 0

    def check_missing_addresses_report(self):
        """Check the missing addresses report"""
        self.log("\n" + "="*60)
        self.log("MISSING ADDRESSES REPORT")
        self.log("="*60)
        
        success, response = self.run_test(
            "Missing Addresses Report",
            "GET",
            "reports/missing-addresses",
            200
        )
        
        if success:
            count = response.get('count', 0)
            campers = response.get('campers', [])
            self.log(f"📊 {count} campers missing addresses")
            
            if campers:
                self.log(f"\nSample campers missing addresses (first 10):")
                for camper in campers[:10]:
                    self.log(f"  - {camper.get('first_name')} {camper.get('last_name')} (Bus: {camper.get('bus_number', 'N/A')})")
            
            return count
        
        return 0

def main():
    """Main test execution"""
    print("\n" + "="*60)
    print("CAMP BUS ROUTING - CSV SYNC TESTING")
    print("="*60 + "\n")
    
    tester = CampBusRoutingTester()
    
    # Step 1: Download and analyze CSV
    if not tester.load_csv_from_google_sheets():
        print("\n❌ Failed to download CSV. Exiting.")
        return 1
    
    csv_analysis = tester.analyze_csv_data()
    
    # Step 2: Test manual CSV sync
    manual_count = tester.test_manual_csv_sync()
    
    # Step 3: Verify database
    db_count, with_location, without_location = tester.verify_database_count()
    
    # Step 4: Check missing addresses
    missing_count = tester.check_missing_addresses_report()
    
    # Step 5: Test auto-sync
    tester.test_auto_sync()
    
    # Step 6: Verify database again after auto-sync
    db_count_after, with_location_after, without_location_after = tester.verify_database_count()
    
    # Final Analysis
    print("\n" + "="*60)
    print("FINAL ANALYSIS")
    print("="*60)
    
    if csv_analysis:
        expected_min = csv_analysis['expected_min']
        expected_max = csv_analysis['expected_max']
        
        print(f"\n📊 Expected campers: {expected_min} - {expected_max}")
        print(f"📊 Actual in database: {db_count_after}")
        print(f"📊 Missing: {expected_min - db_count_after}")
        
        if db_count_after >= expected_min:
            print(f"\n✅ SUCCESS: All expected campers imported!")
        else:
            print(f"\n❌ FAILURE: Missing {expected_min - db_count_after} campers")
            print(f"\n🔍 POTENTIAL ISSUES:")
            print(f"  1. Geocoding failures: {csv_analysis['with_address']} addresses need geocoding")
            print(f"     If geocoding fails, campers may be skipped entirely")
            print(f"  2. Check backend logs for geocoding errors")
            print(f"  3. Campers without addresses should still be imported with lat/lng=0")
    
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
