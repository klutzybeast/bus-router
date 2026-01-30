"""
Test Suite for Camper Card & Roster Enhancements
Tests:
1. Pickup/Dropoff status dropdown - save and clear status
2. Full bus roster print endpoint
3. Roster shows camper info with AM/PM rider type and pickup_dropoff status
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test camper from the review request
TEST_CAMPER_ID = "Accarino_Jolie_11561"
TEST_BUS = "Bus #14"


class TestPickupDropoffEndpoint:
    """Tests for POST /api/campers/{camper_id}/pickup-dropoff endpoint"""
    
    def test_set_early_pickup_status(self):
        """Test setting Early Pickup status"""
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "Early Pickup"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "success"
        assert "Early Pickup" in data.get("message", "")
        print(f"✓ Set Early Pickup status: {data}")
    
    def test_verify_status_in_campers_list(self):
        """Verify pickup_dropoff field is returned in GET /api/campers"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        
        campers = response.json()
        test_camper = next((c for c in campers if c.get("_id") == TEST_CAMPER_ID), None)
        
        assert test_camper is not None, f"Test camper {TEST_CAMPER_ID} not found"
        assert "pickup_dropoff" in test_camper, "pickup_dropoff field missing from camper data"
        assert test_camper.get("pickup_dropoff") == "Early Pickup", f"Expected 'Early Pickup', got '{test_camper.get('pickup_dropoff')}'"
        print(f"✓ Verified pickup_dropoff in campers list: {test_camper.get('pickup_dropoff')}")
    
    def test_set_late_dropoff_status(self):
        """Test setting Late Drop Off status"""
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "Late Drop Off"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "success"
        print(f"✓ Set Late Drop Off status: {data}")
    
    def test_set_both_status(self):
        """Test setting Early Pickup and Late Drop Off status"""
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "Early Pickup and Late Drop Off"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "success"
        print(f"✓ Set Early Pickup and Late Drop Off status: {data}")
    
    def test_clear_status(self):
        """Test clearing status with CLEAR value"""
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "CLEAR"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "success"
        assert "cleared" in data.get("message", "").lower()
        print(f"✓ Cleared status: {data}")
    
    def test_verify_status_cleared(self):
        """Verify status is cleared in campers list"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        
        campers = response.json()
        test_camper = next((c for c in campers if c.get("_id") == TEST_CAMPER_ID), None)
        
        assert test_camper is not None
        # After CLEAR, pickup_dropoff should be empty string or not present
        status = test_camper.get("pickup_dropoff", "")
        assert status == "" or status is None, f"Expected empty status after CLEAR, got '{status}'"
        print(f"✓ Verified status cleared: pickup_dropoff='{status}'")
    
    def test_invalid_status_rejected(self):
        """Test that invalid status values are rejected"""
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "Invalid Status"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid status, got {response.status_code}"
        print(f"✓ Invalid status correctly rejected with 400")
    
    def test_nonexistent_camper(self):
        """Test updating non-existent camper returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/campers/NONEXISTENT_CAMPER_12345/pickup-dropoff",
            json={"pickup_dropoff": "Early Pickup"}
        )
        assert response.status_code == 404, f"Expected 404 for non-existent camper, got {response.status_code}"
        print(f"✓ Non-existent camper correctly returns 404")


class TestFullRosterPrintEndpoint:
    """Tests for GET /api/full-roster/print endpoint"""
    
    def test_roster_all_buses(self):
        """Test generating roster for all buses"""
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Should return HTML
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML response, got {content_type}"
        
        html = response.text
        assert "Full Bus Roster" in html, "Expected 'Full Bus Roster' in HTML"
        assert "Bus #" in html, "Expected bus numbers in HTML"
        print(f"✓ Generated roster for all buses (HTML length: {len(html)})")
    
    def test_roster_specific_bus(self):
        """Test generating roster for specific bus (Bus #14)"""
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=Bus%20%2314")
        assert response.status_code == 200
        
        html = response.text
        assert "Bus #14" in html, "Expected Bus #14 in roster"
        # Should contain our test camper
        assert "Accarino" in html or "Jolie" in html, "Expected test camper in Bus #14 roster"
        print(f"✓ Generated roster for Bus #14")
    
    def test_roster_contains_rider_type(self):
        """Test that roster shows AM/PM rider type"""
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=all")
        assert response.status_code == 200
        
        html = response.text
        # Check for rider type indicators
        assert "AM" in html, "Expected AM rider type in roster"
        assert "PM" in html, "Expected PM rider type in roster"
        print(f"✓ Roster contains AM/PM rider type indicators")
    
    def test_roster_contains_address(self):
        """Test that roster shows camper address"""
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=Bus%20%2314")
        assert response.status_code == 200
        
        html = response.text
        # Check for address-related content
        assert "Address" in html or "address" in html or "Long Beach" in html, "Expected address info in roster"
        print(f"✓ Roster contains address information")
    
    def test_roster_with_pickup_dropoff_status(self):
        """Test that roster shows pickup/dropoff status when set"""
        # First set a status
        requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "Early Pickup"}
        )
        
        # Get roster
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=Bus%20%2314")
        assert response.status_code == 200
        
        html = response.text
        # The status should appear in the roster
        assert "Early Pickup" in html, "Expected 'Early Pickup' status in roster"
        print(f"✓ Roster shows pickup/dropoff status")
        
        # Clean up - clear the status
        requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "CLEAR"}
        )
    
    def test_roster_nonexistent_bus(self):
        """Test roster for non-existent bus returns appropriate response"""
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=Bus%20%23999")
        # Should return 404 or empty roster
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
        if response.status_code == 200:
            html = response.text
            # Should indicate no campers found or be empty
            assert "No campers" in html or len(html) < 500, "Expected empty or 'no campers' message"
        print(f"✓ Non-existent bus handled correctly (status: {response.status_code})")


class TestCamperDataIntegrity:
    """Tests for camper data integrity with pickup_dropoff field"""
    
    def test_campers_endpoint_returns_pickup_dropoff_field(self):
        """Verify GET /api/campers returns pickup_dropoff field for all campers"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        
        campers = response.json()
        assert len(campers) > 0, "Expected at least one camper"
        
        # Check first few campers have pickup_dropoff field
        for camper in campers[:5]:
            assert "pickup_dropoff" in camper, f"pickup_dropoff field missing from camper {camper.get('_id')}"
        
        print(f"✓ All campers have pickup_dropoff field (checked {min(5, len(campers))} campers)")
    
    def test_camper_has_required_fields(self):
        """Verify camper data has all required fields for roster"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        
        campers = response.json()
        test_camper = next((c for c in campers if c.get("_id") == TEST_CAMPER_ID), None)
        
        assert test_camper is not None
        
        required_fields = ["first_name", "last_name", "am_bus_number", "pm_bus_number", "pickup_dropoff", "town"]
        for field in required_fields:
            assert field in test_camper, f"Required field '{field}' missing from camper data"
        
        print(f"✓ Camper has all required fields: {required_fields}")


class TestEndToEndFlow:
    """End-to-end test of the complete pickup/dropoff flow"""
    
    def test_complete_flow(self):
        """Test complete flow: set status -> verify in list -> verify in roster -> clear"""
        # Step 1: Set status
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "Late Drop Off"}
        )
        assert response.status_code == 200
        print("Step 1: Set 'Late Drop Off' status ✓")
        
        # Step 2: Verify in campers list
        response = requests.get(f"{BASE_URL}/api/campers")
        campers = response.json()
        test_camper = next((c for c in campers if c.get("_id") == TEST_CAMPER_ID), None)
        assert test_camper.get("pickup_dropoff") == "Late Drop Off"
        print("Step 2: Verified status in campers list ✓")
        
        # Step 3: Verify in roster
        response = requests.get(f"{BASE_URL}/api/full-roster/print?bus=Bus%20%2314")
        assert "Late Drop Off" in response.text
        print("Step 3: Verified status appears in roster ✓")
        
        # Step 4: Clear status
        response = requests.post(
            f"{BASE_URL}/api/campers/{TEST_CAMPER_ID}/pickup-dropoff",
            json={"pickup_dropoff": "CLEAR"}
        )
        assert response.status_code == 200
        print("Step 4: Cleared status ✓")
        
        # Step 5: Verify cleared
        response = requests.get(f"{BASE_URL}/api/campers")
        campers = response.json()
        test_camper = next((c for c in campers if c.get("_id") == TEST_CAMPER_ID), None)
        assert test_camper.get("pickup_dropoff", "") == ""
        print("Step 5: Verified status cleared ✓")
        
        print("\n✓ Complete end-to-end flow passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
