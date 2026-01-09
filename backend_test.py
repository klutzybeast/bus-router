import requests
import sys
import json

class BusRoutingAPITester:
    def __init__(self, base_url="https://camp-busmap.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, validate_response=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n{'='*60}")
        print(f"🔍 Test {self.tests_run}: {name}")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"Method: {method}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=120)
            
            print(f"Status Code: {response.status_code}")
            
            # Check status code
            status_match = response.status_code == expected_status
            
            if not status_match:
                self.tests_failed += 1
                self.failed_tests.append({
                    'name': name,
                    'reason': f'Expected status {expected_status}, got {response.status_code}',
                    'response': response.text[:500]
                })
                print(f"❌ FAILED - Expected status {expected_status}, got {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False, {}
            
            # Try to parse JSON response
            try:
                response_data = response.json()
                print(f"Response Data: {json.dumps(response_data, indent=2)[:500]}")
            except:
                response_data = {}
                print(f"Response Text: {response.text[:200]}")
            
            # Additional validation if provided
            if validate_response and response_data:
                validation_result = validate_response(response_data)
                if not validation_result['success']:
                    self.tests_failed += 1
                    self.failed_tests.append({
                        'name': name,
                        'reason': validation_result['message'],
                        'response': str(response_data)[:500]
                    })
                    print(f"❌ FAILED - {validation_result['message']}")
                    return False, response_data
            
            self.tests_passed += 1
            print(f"✅ PASSED")
            return True, response_data

        except requests.exceptions.Timeout:
            self.tests_failed += 1
            self.failed_tests.append({
                'name': name,
                'reason': 'Request timeout (>30s)',
                'response': 'N/A'
            })
            print(f"❌ FAILED - Request timeout")
            return False, {}
        except Exception as e:
            self.tests_failed += 1
            self.failed_tests.append({
                'name': name,
                'reason': f'Exception: {str(e)}',
                'response': 'N/A'
            })
            print(f"❌ FAILED - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test GET /api/ endpoint"""
        def validate(data):
            if 'message' not in data:
                return {'success': False, 'message': 'Missing "message" field in response'}
            if data['message'] != 'Bus Routing API':
                return {'success': False, 'message': f'Expected message "Bus Routing API", got "{data["message"]}"'}
            return {'success': True, 'message': 'Valid response'}
        
        return self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200,
            validate_response=validate
        )

    def test_get_campers_initial(self):
        """Test GET /api/campers - should return list (empty or with data)"""
        def validate(data):
            if not isinstance(data, list):
                return {'success': False, 'message': f'Expected list, got {type(data).__name__}'}
            return {'success': True, 'message': f'Valid list with {len(data)} items'}
        
        success, data = self.run_test(
            "Get Campers (Initial)",
            "GET",
            "campers",
            200,
            validate_response=validate
        )
        return success, data

    def test_sync_campers(self, csv_content):
        """Test POST /api/sync-campers with CSV data"""
        def validate(data):
            if 'status' not in data:
                return {'success': False, 'message': 'Missing "status" field in response'}
            if data['status'] != 'success':
                return {'success': False, 'message': f'Expected status "success", got "{data["status"]}"'}
            if 'count' not in data:
                return {'success': False, 'message': 'Missing "count" field in response'}
            if not isinstance(data['count'], int):
                return {'success': False, 'message': f'Count should be integer, got {type(data["count"]).__name__}'}
            if data['count'] <= 0:
                return {'success': False, 'message': f'Expected positive count, got {data["count"]}'}
            return {'success': True, 'message': f'Successfully synced {data["count"]} campers'}
        
        return self.run_test(
            "Sync Campers with CSV",
            "POST",
            "sync-campers",
            200,
            data={'csv_content': csv_content},
            validate_response=validate
        )

    def test_get_campers_after_sync(self):
        """Test GET /api/campers after sync - should have data"""
        def validate(data):
            if not isinstance(data, list):
                return {'success': False, 'message': f'Expected list, got {type(data).__name__}'}
            if len(data) == 0:
                return {'success': False, 'message': 'Expected campers after sync, got empty list'}
            
            # Validate first camper structure
            camper = data[0]
            required_fields = ['first_name', 'last_name', 'location', 'bus_number', 'bus_color', 'session', 'pickup_type']
            missing_fields = [field for field in required_fields if field not in camper]
            if missing_fields:
                return {'success': False, 'message': f'Missing fields in camper: {missing_fields}'}
            
            # Validate location structure
            if 'latitude' not in camper['location'] or 'longitude' not in camper['location']:
                return {'success': False, 'message': 'Location missing latitude or longitude'}
            
            # Check if only AM Bus campers are included
            am_bus_count = sum(1 for c in data if 'AM' in c.get('pickup_type', ''))
            
            return {'success': True, 'message': f'Valid list with {len(data)} campers, {am_bus_count} AM pickups'}
        
        success, data = self.run_test(
            "Get Campers (After Sync)",
            "GET",
            "campers",
            200,
            validate_response=validate
        )
        return success, data

    def validate_bus_colors(self, campers):
        """Validate that bus colors are consistent"""
        print(f"\n{'='*60}")
        print(f"🔍 Additional Validation: Bus Color Consistency")
        print(f"{'='*60}")
        
        self.tests_run += 1
        
        bus_colors = {}
        for camper in campers:
            bus_num = camper['bus_number']
            bus_color = camper['bus_color']
            
            if bus_num in bus_colors:
                if bus_colors[bus_num] != bus_color:
                    self.tests_failed += 1
                    self.failed_tests.append({
                        'name': 'Bus Color Consistency',
                        'reason': f'Bus {bus_num} has inconsistent colors: {bus_colors[bus_num]} vs {bus_color}',
                        'response': 'N/A'
                    })
                    print(f"❌ FAILED - Bus {bus_num} has inconsistent colors")
                    return False
            else:
                bus_colors[bus_num] = bus_color
        
        unique_buses = len(bus_colors)
        print(f"Found {unique_buses} unique buses with consistent colors")
        
        if unique_buses > 33:
            print(f"⚠️  WARNING: Found {unique_buses} buses, expected max 33")
        
        self.tests_passed += 1
        print(f"✅ PASSED - All bus colors are consistent")
        return True

    def validate_am_bus_filter(self, csv_content, campers):
        """Validate that only AM Bus campers are included"""
        print(f"\n{'='*60}")
        print(f"🔍 Additional Validation: AM Bus Filter")
        print(f"{'='*60}")
        
        self.tests_run += 1
        
        # Count AM Bus entries in CSV
        import csv
        from io import StringIO
        
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        am_bus_count = 0
        non_am_bus_count = 0
        
        for row in reader:
            am_method = row.get('Trans-AMDropOffMethod', '')
            if 'AM Bus' in am_method:
                am_bus_count += 1
            else:
                non_am_bus_count += 1
        
        print(f"CSV Analysis:")
        print(f"  - Campers with 'AM Bus': {am_bus_count}")
        print(f"  - Campers without 'AM Bus': {non_am_bus_count}")
        print(f"  - Total campers in API: {len(campers)}")
        
        # Check if any non-AM Bus campers are in the results
        for camper in campers:
            if 'AM' not in camper.get('pickup_type', ''):
                self.tests_failed += 1
                self.failed_tests.append({
                    'name': 'AM Bus Filter',
                    'reason': f'Found non-AM camper: {camper["first_name"]} {camper["last_name"]}',
                    'response': str(camper)
                })
                print(f"❌ FAILED - Found non-AM Bus camper in results")
                return False
        
        self.tests_passed += 1
        print(f"✅ PASSED - All campers have AM Bus transport")
        return True

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*60}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print(f"\n{'='*60}")
            print(f"❌ FAILED TESTS DETAILS:")
            print(f"{'='*60}")
            for i, test in enumerate(self.failed_tests, 1):
                print(f"\n{i}. {test['name']}")
                print(f"   Reason: {test['reason']}")
                if test['response'] != 'N/A':
                    print(f"   Response: {test['response'][:200]}")
        
        return self.tests_failed == 0


def main():
    print("="*60)
    print("🚌 Camp Bus Routing API Test Suite")
    print("="*60)
    
    # Initialize tester
    tester = BusRoutingAPITester()
    
    # Test 1: Root endpoint
    tester.test_root_endpoint()
    
    # Test 2: Get campers initially
    tester.test_get_campers_initial()
    
    # Test 3: Load CSV file
    print(f"\n{'='*60}")
    print(f"📄 Loading CSV file...")
    print(f"{'='*60}")
    try:
        with open('/app/test_campers.csv', 'r', encoding='utf-8-sig') as f:
            csv_content = f.read()
        print(f"✅ CSV file loaded successfully ({len(csv_content)} bytes)")
    except Exception as e:
        print(f"❌ Failed to load CSV file: {str(e)}")
        return 1
    
    # Test 4: Sync campers
    success, sync_response = tester.test_sync_campers(csv_content)
    
    if not success:
        print("\n⚠️  Sync failed, skipping remaining tests")
        tester.print_summary()
        return 1
    
    # Test 5: Get campers after sync
    success, campers = tester.test_get_campers_after_sync()
    
    if success and campers:
        # Additional validations
        tester.validate_bus_colors(campers)
        tester.validate_am_bus_filter(csv_content, campers)
    
    # Print summary
    all_passed = tester.print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
