"""
Bus Staff Configuration API Tests
Tests CRUD operations for bus staff configuration endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBusStaffAPI:
    """Bus Staff CRUD endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_bus = "Bus #99"  # Use high number to avoid conflicts
        self.test_staff_data = {
            "bus_number": self.test_bus,
            "driver_name": "TEST_Driver_Name",
            "counselor_name": "TEST_Counselor_Name",
            "home_address": "123 Test St, Test City, NY 12345",
            "capacity": 25,
            "location_name": "Test Location"
        }
        yield
        # Cleanup - delete test data
        try:
            import urllib.parse
            encoded_bus = urllib.parse.quote(self.test_bus)
            requests.delete(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        except:
            pass
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Bus Routing API"
    
    def test_get_all_bus_staff(self):
        """Test GET /api/bus-staff - Returns all configured staff"""
        response = requests.get(f"{BASE_URL}/api/bus-staff")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "staff" in data
        assert "count" in data
        assert isinstance(data["staff"], dict)
    
    def test_create_bus_staff(self):
        """Test POST /api/bus-staff - Creates new staff configuration"""
        response = requests.post(
            f"{BASE_URL}/api/bus-staff",
            json=self.test_staff_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["bus_number"] == self.test_bus
        assert data["driver_name"] == "TEST_Driver_Name"
        assert data["counselor_name"] == "TEST_Counselor_Name"
        assert data["was_update"] == False
    
    def test_create_and_verify_persistence(self):
        """Test Create → GET verification pattern"""
        # CREATE
        create_response = requests.post(
            f"{BASE_URL}/api/bus-staff",
            json=self.test_staff_data
        )
        assert create_response.status_code == 200
        
        # GET to verify persistence
        import urllib.parse
        encoded_bus = urllib.parse.quote(self.test_bus)
        get_response = requests.get(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["status"] == "success"
        assert data["bus_number"] == self.test_bus
        assert data["driver_name"] == "TEST_Driver_Name"
        assert data["counselor_name"] == "TEST_Counselor_Name"
        assert data["home_address"] == "123 Test St, Test City, NY 12345"
    
    def test_update_bus_staff(self):
        """Test POST /api/bus-staff - Updates existing staff configuration"""
        # First create
        requests.post(f"{BASE_URL}/api/bus-staff", json=self.test_staff_data)
        
        # Update with new data
        updated_data = {
            "bus_number": self.test_bus,
            "driver_name": "TEST_Updated_Driver",
            "counselor_name": "TEST_Updated_Counselor",
            "home_address": "456 Updated St, NY",
            "capacity": 30,
            "location_name": "Updated Location"
        }
        
        update_response = requests.post(
            f"{BASE_URL}/api/bus-staff",
            json=updated_data
        )
        assert update_response.status_code == 200
        
        data = update_response.json()
        assert data["status"] == "success"
        assert data["driver_name"] == "TEST_Updated_Driver"
        assert data["was_update"] == True
        
        # Verify update persisted
        import urllib.parse
        encoded_bus = urllib.parse.quote(self.test_bus)
        get_response = requests.get(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        get_data = get_response.json()
        assert get_data["driver_name"] == "TEST_Updated_Driver"
        assert get_data["counselor_name"] == "TEST_Updated_Counselor"
    
    def test_get_single_bus_staff(self):
        """Test GET /api/bus-staff/{bus_number} - Returns single bus staff config"""
        # First create
        requests.post(f"{BASE_URL}/api/bus-staff", json=self.test_staff_data)
        
        import urllib.parse
        encoded_bus = urllib.parse.quote(self.test_bus)
        response = requests.get(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["bus_number"] == self.test_bus
        assert "driver_name" in data
        assert "counselor_name" in data
        assert "home_address" in data
    
    def test_get_nonexistent_bus_staff(self):
        """Test GET /api/bus-staff/{bus_number} - Returns 404 for nonexistent bus"""
        import urllib.parse
        encoded_bus = urllib.parse.quote("Bus #98")  # Non-existent bus
        response = requests.get(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert response.status_code == 404
    
    def test_delete_bus_staff(self):
        """Test DELETE /api/bus-staff/{bus_number} - Deletes staff configuration"""
        # First create
        requests.post(f"{BASE_URL}/api/bus-staff", json=self.test_staff_data)
        
        import urllib.parse
        encoded_bus = urllib.parse.quote(self.test_bus)
        
        # Delete
        delete_response = requests.delete(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert delete_response.status_code == 200
        
        data = delete_response.json()
        assert data["status"] == "success"
        assert "Deleted" in data["message"]
        
        # Verify deletion - should return 404
        get_response = requests.get(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_bus_staff(self):
        """Test DELETE /api/bus-staff/{bus_number} - Returns 404 for nonexistent bus"""
        import urllib.parse
        encoded_bus = urllib.parse.quote("Bus #97")  # Non-existent bus
        response = requests.delete(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert response.status_code == 404


class TestExistingBusStaff:
    """Tests for pre-configured Bus #01 staff"""
    
    def test_bus_01_staff_exists(self):
        """Verify Bus #01 has John Smith/Jane Doe configured"""
        import urllib.parse
        encoded_bus = urllib.parse.quote("Bus #01")
        response = requests.get(f"{BASE_URL}/api/bus-staff/{encoded_bus}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["bus_number"] == "Bus #01"
        assert data["driver_name"] == "John Smith"
        assert data["counselor_name"] == "Jane Doe"


class TestDownloadEndpoints:
    """Tests for download endpoints"""
    
    def test_download_seat_availability(self):
        """Test GET /api/download/seat-availability - Downloads CSV file"""
        response = requests.get(f"{BASE_URL}/api/download/seat-availability")
        assert response.status_code == 200
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/octet-stream' in content_type or 'text/csv' in content_type
        
        # Check content disposition header
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert 'seat_availability' in content_disposition
        
        # Verify CSV content
        content = response.text
        assert '2026 Seats Available' in content
        assert 'Bus #' in content
        assert 'Driver' in content
        assert 'Counselor' in content
    
    def test_download_bus_assignments(self):
        """Test GET /api/download/bus-assignments - Downloads CSV file"""
        response = requests.get(f"{BASE_URL}/api/download/bus-assignments")
        assert response.status_code == 200
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/octet-stream' in content_type or 'text/csv' in content_type
        
        # Verify CSV content
        content = response.text
        assert 'Last Name' in content
        assert 'First Name' in content
        assert 'Bus Assignment' in content
    
    def test_seat_availability_includes_staff_info(self):
        """Verify seat availability CSV includes configured staff names"""
        response = requests.get(f"{BASE_URL}/api/download/seat-availability")
        assert response.status_code == 200
        
        content = response.text
        # Bus #01 should show John Smith and Jane Doe
        lines = content.split('\n')
        bus_01_line = [l for l in lines if l.startswith('Bus #01,')]
        assert len(bus_01_line) > 0
        assert 'John Smith' in bus_01_line[0]
        assert 'Jane Doe' in bus_01_line[0]


class TestCampersAPI:
    """Tests for campers endpoints"""
    
    def test_get_campers(self):
        """Test GET /api/campers - Returns all campers"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            camper = data[0]
            assert "first_name" in camper
            assert "last_name" in camper
            assert "location" in camper
            assert "am_bus_number" in camper or "pm_bus_number" in camper


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
