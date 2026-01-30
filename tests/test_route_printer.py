#!/usr/bin/env python3
"""
Test suite for route printer functionality
Tests the /api/route-sheet endpoints
"""

import requests
import sys
from datetime import datetime

class RoutePrinterTester:
    def __init__(self, base_url="https://bus-roster-pro-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0

    def run_test(self, name, test_func):
        """Run a single test"""
        self.tests_run += 1
        print(f"\n{'='*60}")
        print(f"🔍 Test {self.tests_run}: {name}")
        print('='*60)
        
        try:
            result = test_func()
            if result:
                self.tests_passed += 1
                print(f"✅ PASSED")
            else:
                self.tests_failed += 1
                print(f"❌ FAILED")
            return result
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ FAILED - Exception: {str(e)}")
            return False

    def test_route_sheet_json(self):
        """Test JSON route sheet endpoint"""
        url = f"{self.base_url}/api/route-sheet/Bus%20%2301"
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Expected 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check required fields
        required_fields = ['bus_number', 'capacity', 'driver', 'counselor', 
                          'total_stops', 'date', 'am_stops', 'pm_stops',
                          'am_directions', 'pm_directions']
        
        for field in required_fields:
            if field not in data:
                print(f"Missing required field: {field}")
                return False
        
        print(f"Bus Number: {data['bus_number']}")
        print(f"Total Stops: {data['total_stops']}")
        print(f"AM Stops: {len(data['am_stops'])}")
        print(f"PM Stops: {len(data['pm_stops'])}")
        
        return True

    def test_route_sheet_html(self):
        """Test HTML printable route sheet endpoint"""
        url = f"{self.base_url}/api/route-sheet/Bus%20%2301/print"
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Expected 200, got {response.status_code}")
            return False
        
        html = response.text
        
        # Check for required HTML elements
        required_elements = [
            '<!DOCTYPE html>',
            '<title>Route Sheet - Bus #01</title>',
            'AM ROUTE',
            'PM ROUTE',
            'Morning Pickups',
            'Afternoon Drop-offs',
            'REVERSE'
        ]
        
        for element in required_elements:
            if element not in html:
                print(f"Missing required HTML element: {element}")
                return False
        
        print(f"HTML Length: {len(html)} characters")
        print(f"Contains AM ROUTE: {'AM ROUTE' in html}")
        print(f"Contains PM ROUTE: {'PM ROUTE' in html}")
        
        return True

    def test_am_pm_sections_present(self):
        """Test that both AM and PM sections are present in HTML"""
        url = f"{self.base_url}/api/route-sheet/Bus%20%2301/print"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to get route sheet: {response.status_code}")
            return False
        
        html = response.text
        
        # Count occurrences
        am_count = html.count('AM ROUTE')
        pm_count = html.count('PM ROUTE')
        
        print(f"AM ROUTE sections: {am_count}")
        print(f"PM ROUTE sections: {pm_count}")
        
        # Should have at least 1 of each (might have 2 due to comments)
        if am_count < 1:
            print("Missing AM ROUTE section")
            return False
        
        if pm_count < 1:
            print("Missing PM ROUTE section")
            return False
        
        return True

    def test_pm_route_reversed(self):
        """Test that PM route is in reverse order of AM route"""
        url = f"{self.base_url}/api/route-sheet/Bus%20%2301"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to get route sheet: {response.status_code}")
            return False
        
        data = response.json()
        
        am_stops = data['am_stops']
        pm_stops = data['pm_stops']
        
        if len(am_stops) != len(pm_stops):
            print(f"AM and PM stops count mismatch: {len(am_stops)} vs {len(pm_stops)}")
            return False
        
        if len(am_stops) == 0:
            print("No stops found")
            return False
        
        # Check if PM is reverse of AM
        first_am = am_stops[0]['camper_name']
        last_am = am_stops[-1]['camper_name']
        first_pm = pm_stops[0]['camper_name']
        last_pm = pm_stops[-1]['camper_name']
        
        print(f"First AM stop: {first_am}")
        print(f"Last AM stop: {last_am}")
        print(f"First PM stop: {first_pm}")
        print(f"Last PM stop: {last_pm}")
        
        # First PM should be last AM
        if first_pm != last_am:
            print(f"PM route not reversed: First PM ({first_pm}) != Last AM ({last_am})")
            return False
        
        # Last PM should be first AM
        if last_pm != first_am:
            print(f"PM route not reversed: Last PM ({last_pm}) != First AM ({first_am})")
            return False
        
        print("✓ PM route is correctly reversed")
        return True

    def test_multiple_buses(self):
        """Test route sheets for multiple buses"""
        buses = ['Bus #01', 'Bus #02', 'Bus #03']
        success_count = 0
        
        for bus in buses:
            url = f"{self.base_url}/api/route-sheet/{requests.utils.quote(bus)}/print"
            response = requests.get(url, timeout=10)
            
            print(f"{bus}: {response.status_code}")
            
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 404:
                print(f"  (No campers assigned to {bus})")
        
        print(f"\nSuccessfully generated route sheets for {success_count}/{len(buses)} buses")
        return success_count > 0

    def test_html_structure(self):
        """Test HTML structure is valid"""
        url = f"{self.base_url}/api/route-sheet/Bus%20%2301/print"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to get route sheet: {response.status_code}")
            return False
        
        html = response.text
        
        # Check for proper HTML structure
        checks = {
            'Has DOCTYPE': '<!DOCTYPE html>' in html,
            'Has opening html tag': '<html>' in html,
            'Has closing html tag': '</html>' in html,
            'Has head section': '<head>' in html and '</head>' in html,
            'Has body section': '<body>' in html and '</body>' in html,
            'Has CSS styles': '<style>' in html and '</style>' in html,
            'Has tables': '<table>' in html and '</table>' in html,
            'Has print button': 'window.print()' in html,
        }
        
        all_passed = True
        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"{status} {check}")
            if not result:
                all_passed = False
        
        return all_passed

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        print("="*60)
        
        return self.tests_failed == 0

def main():
    print("="*60)
    print("🚌 ROUTE PRINTER TEST SUITE")
    print("="*60)
    print(f"Testing: https://bus-roster-pro-1.preview.emergentagent.com")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    tester = RoutePrinterTester()
    
    # Run all tests
    tester.run_test("Route Sheet JSON Endpoint", tester.test_route_sheet_json)
    tester.run_test("Route Sheet HTML Endpoint", tester.test_route_sheet_html)
    tester.run_test("AM and PM Sections Present", tester.test_am_pm_sections_present)
    tester.run_test("PM Route is Reversed", tester.test_pm_route_reversed)
    tester.run_test("Multiple Buses", tester.test_multiple_buses)
    tester.run_test("HTML Structure Valid", tester.test_html_structure)
    
    # Print summary
    success = tester.print_summary()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
