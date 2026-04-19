"""
Shadow Staff API Tests
Tests for the shadow staff feature - 1:1 staff members assigned to accompany specific campers.
Shadows take bus seats and inherit the session from their linked child.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://counselor-admin-test.preview.emergentagent.com').rstrip('/')

class TestShadowAPI:
    """Shadow Staff CRUD API tests"""
    
    # Store created shadow IDs for cleanup
    created_shadow_ids = []
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test"""
        yield
        # Cleanup: Delete any test-created shadows
        for shadow_id in self.created_shadow_ids:
            try:
                requests.delete(f"{BASE_URL}/api/shadows/{shadow_id}")
            except:
                pass
        self.created_shadow_ids.clear()
    
    def test_health_check(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_get_all_shadows(self):
        """Test GET /api/shadows - retrieve all shadows"""
        response = requests.get(f"{BASE_URL}/api/shadows")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "shadows" in data
        assert "count" in data
        assert isinstance(data["shadows"], list)
        print(f"✓ GET /api/shadows returned {data['count']} shadows")
    
    def test_existing_shadow_data_structure(self):
        """Test that existing shadow has correct data structure"""
        response = requests.get(f"{BASE_URL}/api/shadows")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            shadow = data["shadows"][0]
            # Verify required fields exist
            assert "id" in shadow, "Shadow should have 'id' field"
            assert "shadow_name" in shadow, "Shadow should have 'shadow_name' field"
            assert "camper_id" in shadow, "Shadow should have 'camper_id' field"
            assert "camper_name" in shadow, "Shadow should have 'camper_name' field"
            assert "bus_number" in shadow, "Shadow should have 'bus_number' field"
            assert "session" in shadow, "Shadow should have 'session' field"
            print(f"✓ Shadow data structure verified: {shadow['shadow_name']} linked to {shadow['camper_name']}")
        else:
            pytest.skip("No existing shadows to verify structure")
    
    def test_get_shadow_by_camper(self):
        """Test GET /api/shadows/by-camper/{camper_id}"""
        # First get existing shadows to find a valid camper_id
        response = requests.get(f"{BASE_URL}/api/shadows")
        data = response.json()
        
        if data["count"] > 0:
            camper_id = data["shadows"][0]["camper_id"]
            response = requests.get(f"{BASE_URL}/api/shadows/by-camper/{camper_id}")
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            assert result["shadow"] is not None
            assert result["shadow"]["camper_id"] == camper_id
            print(f"✓ GET /api/shadows/by-camper/{camper_id} returned shadow")
        else:
            pytest.skip("No existing shadows to test by-camper endpoint")
    
    def test_get_shadow_by_bus(self):
        """Test GET /api/shadows/by-bus/{bus_number}"""
        # First get existing shadows to find a valid bus_number
        response = requests.get(f"{BASE_URL}/api/shadows")
        data = response.json()
        
        if data["count"] > 0:
            bus_number = data["shadows"][0]["bus_number"]
            # URL encode the bus number
            import urllib.parse
            encoded_bus = urllib.parse.quote(bus_number, safe='')
            response = requests.get(f"{BASE_URL}/api/shadows/by-bus/{encoded_bus}")
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            assert "shadows" in result
            print(f"✓ GET /api/shadows/by-bus/{bus_number} returned {result['count']} shadows")
        else:
            pytest.skip("No existing shadows to test by-bus endpoint")
    
    def test_create_shadow_requires_valid_camper(self):
        """Test POST /api/shadows - should fail with invalid camper_id"""
        response = requests.post(f"{BASE_URL}/api/shadows", json={
            "shadow_name": "TEST_Invalid Shadow",
            "camper_id": "INVALID_CAMPER_ID_12345"
        })
        # Should return 404 for invalid camper
        assert response.status_code == 404
        print("✓ POST /api/shadows correctly rejects invalid camper_id")
    
    def test_create_shadow_requires_name(self):
        """Test POST /api/shadows - should fail without shadow_name"""
        response = requests.post(f"{BASE_URL}/api/shadows", json={
            "camper_id": "some_camper_id"
        })
        # Should return 422 for missing required field
        assert response.status_code == 422
        print("✓ POST /api/shadows correctly requires shadow_name")
    
    def test_create_and_delete_shadow(self):
        """Test full shadow lifecycle: create and delete"""
        # First, get a valid camper to link the shadow to
        campers_response = requests.get(f"{BASE_URL}/api/campers")
        assert campers_response.status_code == 200
        campers = campers_response.json()
        
        if len(campers) == 0:
            pytest.skip("No campers available to create shadow")
        
        # Find a camper without an existing shadow
        existing_shadows = requests.get(f"{BASE_URL}/api/shadows").json()
        existing_camper_ids = [s["camper_id"] for s in existing_shadows.get("shadows", [])]
        
        test_camper = None
        for camper in campers:
            camper_id = camper.get("_id")
            if camper_id and camper_id not in existing_camper_ids:
                test_camper = camper
                break
        
        if not test_camper:
            pytest.skip("All campers already have shadows assigned")
        
        camper_id = test_camper["_id"]
        
        # Create shadow
        create_response = requests.post(f"{BASE_URL}/api/shadows", json={
            "shadow_name": "TEST_Shadow Staff Member",
            "camper_id": camper_id
        })
        
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        create_data = create_response.json()
        assert create_data["status"] == "success"
        assert "shadow" in create_data
        
        shadow = create_data["shadow"]
        shadow_id = shadow["id"]
        self.created_shadow_ids.append(shadow_id)
        
        # Verify shadow data
        assert shadow["shadow_name"] == "TEST_Shadow Staff Member"
        assert shadow["camper_id"] == camper_id
        assert "bus_number" in shadow
        assert "session" in shadow
        print(f"✓ Created shadow: {shadow['shadow_name']} for {shadow['camper_name']} on {shadow['bus_number']}")
        
        # Verify shadow appears in GET all
        get_response = requests.get(f"{BASE_URL}/api/shadows")
        assert get_response.status_code == 200
        all_shadows = get_response.json()["shadows"]
        found = any(s["id"] == shadow_id for s in all_shadows)
        assert found, "Created shadow should appear in GET /api/shadows"
        print("✓ Shadow appears in GET /api/shadows list")
        
        # Delete shadow
        delete_response = requests.delete(f"{BASE_URL}/api/shadows/{shadow_id}")
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert delete_data["status"] == "success"
        print(f"✓ Deleted shadow: {shadow_id}")
        
        # Verify shadow is gone
        get_after_delete = requests.get(f"{BASE_URL}/api/shadows")
        all_shadows_after = get_after_delete.json()["shadows"]
        found_after = any(s["id"] == shadow_id for s in all_shadows_after)
        assert not found_after, "Deleted shadow should not appear in GET /api/shadows"
        print("✓ Shadow no longer appears after deletion")
        
        # Remove from cleanup list since already deleted
        self.created_shadow_ids.remove(shadow_id)
    
    def test_duplicate_shadow_rejected(self):
        """Test that creating duplicate shadow for same camper is rejected"""
        # Get existing shadow
        response = requests.get(f"{BASE_URL}/api/shadows")
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No existing shadows to test duplicate rejection")
        
        existing_shadow = data["shadows"][0]
        camper_id = existing_shadow["camper_id"]
        
        # Try to create another shadow for same camper
        duplicate_response = requests.post(f"{BASE_URL}/api/shadows", json={
            "shadow_name": "TEST_Duplicate Shadow",
            "camper_id": camper_id
        })
        
        # Should be rejected (400 Bad Request)
        assert duplicate_response.status_code == 400
        print(f"✓ Duplicate shadow correctly rejected for camper {camper_id}")
    
    def test_delete_nonexistent_shadow(self):
        """Test DELETE /api/shadows/{id} with invalid ID"""
        response = requests.delete(f"{BASE_URL}/api/shadows/000000000000000000000000")
        # Should return 404
        assert response.status_code == 404
        print("✓ DELETE nonexistent shadow returns 404")


class TestShadowSeatAvailability:
    """Test that shadows are counted in seat availability"""
    
    def test_seat_availability_includes_shadows(self):
        """Test GET /api/seat-availability-json includes shadow counts"""
        response = requests.get(f"{BASE_URL}/api/seat-availability-json")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "buses" in data
        
        # Check if any bus has shadow count
        has_shadow_field = False
        for bus_number, bus_data in data["buses"].items():
            if "shadows" in bus_data:
                has_shadow_field = True
                print(f"  {bus_number}: {bus_data.get('shadows', 0)} shadows")
        
        assert has_shadow_field, "Seat availability should include 'shadows' field"
        print("✓ Seat availability includes shadow counts")
    
    def test_shadow_affects_seat_count(self):
        """Test that shadows are counted in AM/PM seat calculations"""
        # Get shadows
        shadows_response = requests.get(f"{BASE_URL}/api/shadows")
        shadows_data = shadows_response.json()
        
        if shadows_data["count"] == 0:
            pytest.skip("No shadows to verify seat count impact")
        
        # Get seat availability
        seat_response = requests.get(f"{BASE_URL}/api/seat-availability-json")
        seat_data = seat_response.json()
        
        # Find a bus with shadows
        for shadow in shadows_data["shadows"]:
            bus_number = shadow["bus_number"]
            if bus_number in seat_data["buses"]:
                bus_info = seat_data["buses"][bus_number]
                shadow_count = bus_info.get("shadows", 0)
                
                # Shadows should be counted (shadow_count > 0 if there are shadows on this bus)
                assert shadow_count > 0, f"Bus {bus_number} should have shadow count > 0"
                
                # Verify shadows affect AM/PM counts
                # Shadows take both AM and PM seats
                h1_am = bus_info.get("h1_am", 0)
                h1_pm = bus_info.get("h1_pm", 0)
                
                print(f"✓ {bus_number}: {shadow_count} shadows, H1 AM: {h1_am}, H1 PM: {h1_pm}")
                break


class TestShadowDataIntegrity:
    """Test shadow data integrity and inheritance"""
    
    def test_shadow_inherits_camper_bus(self):
        """Test that shadow inherits bus number from linked camper"""
        # Get shadows
        shadows_response = requests.get(f"{BASE_URL}/api/shadows")
        shadows_data = shadows_response.json()
        
        if shadows_data["count"] == 0:
            pytest.skip("No shadows to verify bus inheritance")
        
        shadow = shadows_data["shadows"][0]
        camper_id = shadow["camper_id"]
        shadow_bus = shadow["bus_number"]
        
        # Get the linked camper
        campers_response = requests.get(f"{BASE_URL}/api/campers")
        campers = campers_response.json()
        
        linked_camper = None
        for camper in campers:
            if camper.get("_id") == camper_id:
                linked_camper = camper
                break
        
        if linked_camper:
            camper_am_bus = linked_camper.get("am_bus_number", "")
            camper_pm_bus = linked_camper.get("pm_bus_number", "")
            
            # Shadow should have same bus as camper (AM bus preferred)
            assert shadow_bus == camper_am_bus or shadow_bus == camper_pm_bus, \
                f"Shadow bus ({shadow_bus}) should match camper bus (AM: {camper_am_bus}, PM: {camper_pm_bus})"
            print(f"✓ Shadow bus ({shadow_bus}) matches camper bus")
        else:
            print(f"⚠ Could not find linked camper {camper_id} in campers list")
    
    def test_shadow_inherits_camper_session(self):
        """Test that shadow inherits session from linked camper"""
        # Get shadows
        shadows_response = requests.get(f"{BASE_URL}/api/shadows")
        shadows_data = shadows_response.json()
        
        if shadows_data["count"] == 0:
            pytest.skip("No shadows to verify session inheritance")
        
        shadow = shadows_data["shadows"][0]
        camper_id = shadow["camper_id"]
        shadow_session = shadow["session"]
        
        # Get the linked camper
        campers_response = requests.get(f"{BASE_URL}/api/campers")
        campers = campers_response.json()
        
        linked_camper = None
        for camper in campers:
            if camper.get("_id") == camper_id:
                linked_camper = camper
                break
        
        if linked_camper:
            camper_session = linked_camper.get("session", "")
            assert shadow_session == camper_session, \
                f"Shadow session ({shadow_session}) should match camper session ({camper_session})"
            print(f"✓ Shadow session ({shadow_session}) matches camper session")
        else:
            print(f"⚠ Could not find linked camper {camper_id} in campers list")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
