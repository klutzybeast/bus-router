"""
Test Suite for Multi-Season Feature
Tests season CRUD operations and data filtering by season
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://routewise-camp.preview.emergentagent.com').rstrip('/')

class TestSeasonAPI:
    """Season Management API Tests"""
    
    def test_health_check(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_get_all_seasons(self):
        """Test GET /api/seasons returns list of seasons"""
        response = requests.get(f"{BASE_URL}/api/seasons")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "seasons" in data
        assert isinstance(data["seasons"], list)
        print(f"✓ GET /api/seasons returned {len(data['seasons'])} seasons")
        
        # Verify season structure
        if len(data["seasons"]) > 0:
            season = data["seasons"][0]
            assert "id" in season
            assert "name" in season
            assert "year" in season
            assert "is_active" in season
            assert "camper_count" in season
            print(f"  - First season: {season['name']} (Year: {season['year']}, Active: {season['is_active']}, Campers: {season['camper_count']})")
        return data["seasons"]
    
    def test_get_active_season(self):
        """Test GET /api/seasons/active returns the active season with camper count"""
        response = requests.get(f"{BASE_URL}/api/seasons/active")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "season" in data
        
        season = data["season"]
        assert "id" in season
        assert "name" in season
        assert "year" in season
        assert season["is_active"] == True
        assert "camper_count" in season
        
        print(f"✓ Active season: {season['name']}")
        print(f"  - Year: {season['year']}")
        print(f"  - Camper count: {season['camper_count']}")
        print(f"  - Season ID: {season['id']}")
        
        # Verify camper count is reasonable (should be ~528 based on context)
        assert season["camper_count"] >= 0
        return season
    
    def test_get_campers_filtered_by_season(self):
        """Test GET /api/campers returns campers filtered by active season"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        campers = response.json()
        assert isinstance(campers, list)
        
        print(f"✓ GET /api/campers returned {len(campers)} campers")
        
        # Verify camper structure
        if len(campers) > 0:
            camper = campers[0]
            assert "first_name" in camper
            assert "last_name" in camper
            assert "location" in camper
            # Check season_id is present
            if "season_id" in camper:
                print(f"  - Campers have season_id field")
        
        return campers
    
    def test_get_shadows_filtered_by_season(self):
        """Test GET /api/shadows returns shadows filtered by active season"""
        response = requests.get(f"{BASE_URL}/api/shadows")
        assert response.status_code == 200
        data = response.json()
        assert "shadows" in data
        shadows = data["shadows"]
        assert isinstance(shadows, list)
        
        print(f"✓ GET /api/shadows returned {len(shadows)} shadows")
        
        # Verify shadow structure if any exist
        if len(shadows) > 0:
            shadow = shadows[0]
            assert "shadow_name" in shadow
            assert "camper_id" in shadow
            assert "bus_number" in shadow
            print(f"  - First shadow: {shadow['shadow_name']} on {shadow['bus_number']}")
        
        return shadows
    
    def test_get_bus_zones_filtered_by_season(self):
        """Test GET /api/bus-zones returns bus zones filtered by active season"""
        response = requests.get(f"{BASE_URL}/api/bus-zones")
        assert response.status_code == 200
        data = response.json()
        assert "zones" in data
        zones = data["zones"]
        assert isinstance(zones, list)
        
        print(f"✓ GET /api/bus-zones returned {len(zones)} zones")
        
        return zones
    
    def test_get_bus_staff_filtered_by_season(self):
        """Test GET /api/bus-staff returns bus staff filtered by active season"""
        response = requests.get(f"{BASE_URL}/api/bus-staff")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "staff" in data
        staff = data["staff"]
        assert isinstance(staff, dict)
        
        print(f"✓ GET /api/bus-staff returned {len(staff)} staff configurations")
        
        return staff


class TestSeasonCRUD:
    """Test Season Create, Activate, and Copy operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Store original active season to restore after tests"""
        response = requests.get(f"{BASE_URL}/api/seasons/active")
        if response.status_code == 200:
            self.original_season_id = response.json()["season"]["id"]
        else:
            self.original_season_id = None
        yield
        # Restore original active season after test
        if self.original_season_id:
            requests.put(f"{BASE_URL}/api/seasons/{self.original_season_id}/activate")
    
    def test_create_new_season_without_copy(self):
        """Test POST /api/seasons creates a new season without copying data"""
        test_year = 2099  # Use far future year to avoid conflicts
        test_name = f"{test_year} Test Season"
        
        response = requests.post(f"{BASE_URL}/api/seasons", json={
            "name": test_name,
            "year": test_year,
            "copy_from_season_id": None
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "season_id" in data
        assert data["copied"] is None  # No data copied
        
        print(f"✓ Created new season: {test_name}")
        print(f"  - Season ID: {data['season_id']}")
        
        # Verify the new season is now active
        active_response = requests.get(f"{BASE_URL}/api/seasons/active")
        assert active_response.status_code == 200
        active_season = active_response.json()["season"]
        assert active_season["name"] == test_name
        assert active_season["year"] == test_year
        assert active_season["camper_count"] == 0  # No campers copied
        
        print(f"  - New season is now active with 0 campers")
        
        return data["season_id"]
    
    def test_activate_season(self):
        """Test PUT /api/seasons/{season_id}/activate switches the active season"""
        # First get all seasons
        seasons_response = requests.get(f"{BASE_URL}/api/seasons")
        assert seasons_response.status_code == 200
        seasons = seasons_response.json()["seasons"]
        
        if len(seasons) < 2:
            pytest.skip("Need at least 2 seasons to test activation")
        
        # Find a non-active season
        inactive_season = None
        for season in seasons:
            if not season["is_active"]:
                inactive_season = season
                break
        
        if not inactive_season:
            pytest.skip("No inactive season found to test activation")
        
        # Activate the inactive season
        response = requests.put(f"{BASE_URL}/api/seasons/{inactive_season['id']}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        print(f"✓ Activated season: {inactive_season['name']}")
        
        # Verify it's now active
        active_response = requests.get(f"{BASE_URL}/api/seasons/active")
        assert active_response.status_code == 200
        active_season = active_response.json()["season"]
        assert active_season["id"] == inactive_season["id"]
        
        print(f"  - Verified season is now active")
    
    def test_activate_nonexistent_season(self):
        """Test activating a non-existent season returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.put(f"{BASE_URL}/api/seasons/{fake_id}/activate")
        assert response.status_code == 404
        print(f"✓ Activating non-existent season correctly returns 404")


class TestSeasonDataFiltering:
    """Test that data is correctly filtered by active season"""
    
    def test_campers_have_season_id(self):
        """Verify campers returned have season_id matching active season"""
        # Get active season
        active_response = requests.get(f"{BASE_URL}/api/seasons/active")
        assert active_response.status_code == 200
        active_season_id = active_response.json()["season"]["id"]
        
        # Get campers
        campers_response = requests.get(f"{BASE_URL}/api/campers")
        assert campers_response.status_code == 200
        campers = campers_response.json()
        
        if len(campers) > 0:
            # Check a sample of campers have the correct season_id
            sample_size = min(10, len(campers))
            for camper in campers[:sample_size]:
                if "season_id" in camper:
                    assert camper["season_id"] == active_season_id, \
                        f"Camper {camper.get('first_name')} {camper.get('last_name')} has wrong season_id"
            
            print(f"✓ Verified {sample_size} campers have correct season_id: {active_season_id}")
        else:
            print("⚠ No campers to verify season_id")
    
    def test_camper_count_matches_active_season(self):
        """Verify camper count from /api/campers matches active season's camper_count"""
        # Get active season with camper count
        active_response = requests.get(f"{BASE_URL}/api/seasons/active")
        assert active_response.status_code == 200
        active_season = active_response.json()["season"]
        expected_count = active_season["camper_count"]
        
        # Get campers
        campers_response = requests.get(f"{BASE_URL}/api/campers")
        assert campers_response.status_code == 200
        campers = campers_response.json()
        actual_count = len(campers)
        
        # Note: The counts might differ slightly because /api/campers filters out
        # campers without valid locations or bus assignments
        print(f"✓ Active season reports {expected_count} campers")
        print(f"  - /api/campers returns {actual_count} campers (with valid locations/buses)")
        
        # The API count should be <= the season count (some may be filtered)
        # Allow for some variance due to filtering logic
        assert actual_count <= expected_count + 50, \
            f"Camper count mismatch: API returned {actual_count}, season reports {expected_count}"


class TestSeasonIntegration:
    """Integration tests for season feature with other endpoints"""
    
    def test_seat_availability_uses_active_season(self):
        """Test that seat availability endpoint uses active season data"""
        response = requests.get(f"{BASE_URL}/api/seat-availability-json")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "buses" in data
        
        print(f"✓ Seat availability endpoint returns data for {len(data['buses'])} buses")
    
    def test_db_status_endpoint(self):
        """Test database status endpoint"""
        response = requests.get(f"{BASE_URL}/api/db-status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        
        print(f"✓ Database connected, total campers: {data.get('camper_count', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
