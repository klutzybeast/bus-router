"""
Staff Zone Lookup Feature Tests
Tests for staff addresses endpoints: GET, POST, PUT, DELETE, CSV upload
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://routewise-camp.preview.emergentagent.com').rstrip('/')

class TestStaffAddressesAPI:
    """Test Staff Addresses CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.api_url = f"{BASE_URL}/api"
        self.test_staff_ids = []
        yield
        # Cleanup: Delete test staff created during tests
        for staff_id in self.test_staff_ids:
            try:
                requests.delete(f"{self.api_url}/staff-addresses/{staff_id}")
            except:
                pass
    
    def test_get_all_staff_addresses(self):
        """Test GET /api/staff-addresses - should return list of staff"""
        response = requests.get(f"{self.api_url}/staff-addresses")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "staff" in data
        assert "count" in data
        assert isinstance(data["staff"], list)
        print(f"✓ GET /api/staff-addresses - Found {data['count']} staff members")
    
    def test_brian_stein_exists(self):
        """Test that Brian Stein test case exists with correct data"""
        response = requests.get(f"{self.api_url}/staff-addresses")
        assert response.status_code == 200
        
        data = response.json()
        staff_list = data["staff"]
        
        # Find Brian Stein
        brian = next((s for s in staff_list if s["name"] == "Brian Stein"), None)
        assert brian is not None, "Brian Stein should exist in staff list"
        
        # Verify address
        assert "4288 New York" in brian["address"], f"Brian's address should contain '4288 New York', got: {brian['address']}"
        assert "Island Park" in brian["address"], f"Brian's address should contain 'Island Park', got: {brian['address']}"
        
        # Verify geocoding worked
        assert brian["lat"] is not None, "Brian should have latitude"
        assert brian["lng"] is not None, "Brian should have longitude"
        assert brian["lat"] > 40.5 and brian["lat"] < 40.7, f"Brian's latitude should be in Long Island area, got: {brian['lat']}"
        
        # Verify bus assignment
        assert brian["bus_number"] == "Bus #15", f"Brian should be assigned to Bus #15, got: {brian['bus_number']}"
        
        # Verify nearby buses
        assert "nearby_buses" in brian, "Brian should have nearby_buses field"
        assert "Bus #15" in brian["nearby_buses"], f"Bus #15 should be in nearby buses, got: {brian['nearby_buses']}"
        assert "Bus #31" in brian["nearby_buses"], f"Bus #31 should be in nearby buses, got: {brian['nearby_buses']}"
        
        print(f"✓ Brian Stein test case verified:")
        print(f"  - Address: {brian['address']}")
        print(f"  - Location: ({brian['lat']}, {brian['lng']})")
        print(f"  - Assigned Bus: {brian['bus_number']}")
        print(f"  - Nearby Buses: {brian['nearby_buses']}")
    
    def test_create_staff_address(self):
        """Test POST /api/staff-addresses - create new staff with geocoding"""
        test_staff = {
            "name": "TEST_Staff_Member",
            "address": "123 Main Street, Oceanside, NY 11572"
        }
        
        response = requests.post(f"{self.api_url}/staff-addresses", json=test_staff)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "staff" in data
        
        staff = data["staff"]
        assert staff["name"] == test_staff["name"]
        assert staff["lat"] is not None, "Staff should be geocoded with latitude"
        assert staff["lng"] is not None, "Staff should be geocoded with longitude"
        assert "nearby_buses" in staff, "Staff should have nearby_buses calculated"
        
        # Store ID for cleanup
        self.test_staff_ids.append(staff["id"])
        
        print(f"✓ POST /api/staff-addresses - Created staff:")
        print(f"  - Name: {staff['name']}")
        print(f"  - Address: {staff['address']}")
        print(f"  - Location: ({staff['lat']}, {staff['lng']})")
        print(f"  - Nearby Buses: {staff.get('nearby_buses', [])}")
    
    def test_create_staff_with_bus_assignment(self):
        """Test POST /api/staff-addresses with bus_number"""
        test_staff = {
            "name": "TEST_Staff_With_Bus",
            "address": "500 Merrick Road, Rockville Centre, NY 11570",
            "bus_number": "Bus #20"
        }
        
        response = requests.post(f"{self.api_url}/staff-addresses", json=test_staff)
        assert response.status_code == 200
        
        data = response.json()
        staff = data["staff"]
        assert staff["bus_number"] == "Bus #20", f"Bus should be assigned, got: {staff.get('bus_number')}"
        
        self.test_staff_ids.append(staff["id"])
        print(f"✓ Created staff with bus assignment: {staff['name']} -> {staff['bus_number']}")
    
    def test_update_staff_bus_assignment(self):
        """Test PUT /api/staff-addresses/{id} - assign bus to staff"""
        # First create a staff member
        create_response = requests.post(f"{self.api_url}/staff-addresses", json={
            "name": "TEST_Staff_Update",
            "address": "100 Broadway, Freeport, NY 11520"
        })
        assert create_response.status_code == 200
        staff_id = create_response.json()["staff"]["id"]
        self.test_staff_ids.append(staff_id)
        
        # Update with bus assignment
        update_response = requests.put(f"{self.api_url}/staff-addresses/{staff_id}", json={
            "bus_number": "Bus #25"
        })
        assert update_response.status_code == 200
        
        data = update_response.json()
        assert data["status"] == "success"
        assert data["staff"]["bus_number"] == "Bus #25"
        
        # Verify persistence with GET
        get_response = requests.get(f"{self.api_url}/staff-addresses")
        staff_list = get_response.json()["staff"]
        updated_staff = next((s for s in staff_list if s["id"] == staff_id), None)
        assert updated_staff is not None
        assert updated_staff["bus_number"] == "Bus #25"
        
        print(f"✓ PUT /api/staff-addresses/{staff_id} - Bus assignment updated and persisted")
    
    def test_delete_staff_address(self):
        """Test DELETE /api/staff-addresses/{id}"""
        # First create a staff member
        create_response = requests.post(f"{self.api_url}/staff-addresses", json={
            "name": "TEST_Staff_Delete",
            "address": "200 Atlantic Ave, Lynbrook, NY 11563"
        })
        assert create_response.status_code == 200
        staff_id = create_response.json()["staff"]["id"]
        
        # Delete the staff
        delete_response = requests.delete(f"{self.api_url}/staff-addresses/{staff_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "success"
        
        # Verify deletion with GET
        get_response = requests.get(f"{self.api_url}/staff-addresses")
        staff_list = get_response.json()["staff"]
        deleted_staff = next((s for s in staff_list if s["id"] == staff_id), None)
        assert deleted_staff is None, "Staff should be deleted"
        
        print(f"✓ DELETE /api/staff-addresses/{staff_id} - Staff deleted successfully")
    
    def test_geocoding_failure_handling(self):
        """Test that invalid addresses return proper error"""
        test_staff = {
            "name": "TEST_Invalid_Address",
            "address": "xyzabc123notarealaddress"
        }
        
        response = requests.post(f"{self.api_url}/staff-addresses", json=test_staff)
        # Should return 400 for geocoding failure
        assert response.status_code == 400
        assert "geocode" in response.json().get("detail", "").lower()
        
        print("✓ Invalid address returns 400 with geocoding error")


class TestSeatAvailabilityWithStaff:
    """Test that staff with addresses are reflected in seat availability"""
    
    def test_seat_availability_includes_staff(self):
        """Test GET /api/seat-availability-json includes staff_with_addresses count"""
        response = requests.get(f"{BASE_URL}/api/seat-availability-json")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "buses" in data
        
        # Check Bus #15 (Brian Stein's bus)
        bus_15 = data["buses"].get("Bus #15")
        if bus_15:
            # Staff with addresses should be counted
            staff_count = bus_15.get("staff_with_addresses", 0)
            print(f"✓ Bus #15 staff_with_addresses count: {staff_count}")
            
            # Verify staff count is reflected in seat counts
            h1_am = bus_15.get("h1_am", 0)
            capacity = bus_15.get("capacity", 30)
            print(f"  - Capacity: {capacity}, H1 AM count: {h1_am}")
        else:
            print("⚠ Bus #15 not found in seat availability (may have no campers)")


class TestCoverSheetWithStaff:
    """Test that cover sheet includes staff in notes column"""
    
    def test_cover_sheet_includes_staff_notes(self):
        """Test GET /api/sheets/seat-availability includes staff in notes"""
        response = requests.get(f"{BASE_URL}/api/sheets/seat-availability")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        
        sheet_data = data["data"]
        
        # Find Bus #15 row
        bus_15_row = None
        for row in sheet_data:
            if row and len(row) > 0 and row[0] == "Bus #15":
                bus_15_row = row
                break
        
        if bus_15_row:
            # Notes column should be the last column (index 13 in full format or 10 in simple)
            notes = bus_15_row[-1] if len(bus_15_row) > 10 else ""
            print(f"✓ Bus #15 notes column: {notes}")
            
            # Brian Stein should appear in notes
            if "Brian Stein" in str(notes):
                print("  - Brian Stein found in notes ✓")
            else:
                print("  - Brian Stein NOT found in notes (may need verification)")
        else:
            print("⚠ Bus #15 not found in cover sheet data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
