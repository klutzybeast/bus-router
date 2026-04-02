"""
Backend API Tests for Refactored Camp Bus Routing Application
Tests all major endpoints after server.py refactoring from 7391 to 629 lines.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndConfig:
    """Health check and configuration endpoints"""
    
    def test_api_health(self):
        """GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("PASS: /api/health returns healthy status")
    
    def test_config_check(self):
        """GET /api/config-check returns configuration status"""
        response = requests.get(f"{BASE_URL}/api/config-check")
        assert response.status_code == 200
        data = response.json()
        assert "webhook_configured" in data
        assert "positionstack_configured" in data
        assert "google_maps_configured" in data
        print(f"PASS: /api/config-check - webhook: {data['webhook_configured']}, positionstack: {data['positionstack_configured']}, google_maps: {data['google_maps_configured']}")
    
    def test_geocode_cache_stats(self):
        """GET /api/geocode-cache-stats returns cache statistics"""
        response = requests.get(f"{BASE_URL}/api/geocode-cache-stats")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "total_cached_addresses" in data
        assert "memory_cache_size" in data
        print(f"PASS: /api/geocode-cache-stats - {data['total_cached_addresses']} cached addresses")


class TestSeasons:
    """Season management endpoints"""
    
    def test_get_active_season(self):
        """GET /api/seasons/active returns active season with camper_count"""
        response = requests.get(f"{BASE_URL}/api/seasons/active")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "season" in data
        season = data["season"]
        assert "id" in season
        assert "name" in season
        assert "camper_count" in season
        assert season["is_active"] == True
        print(f"PASS: /api/seasons/active - {season['name']} with {season['camper_count']} campers")


class TestCampers:
    """Camper CRUD endpoints"""
    
    def test_get_campers(self):
        """GET /api/campers returns list of campers"""
        response = requests.get(f"{BASE_URL}/api/campers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify camper structure
        camper = data[0]
        assert "_id" in camper
        assert "first_name" in camper
        assert "last_name" in camper
        assert "am_bus_number" in camper
        print(f"PASS: /api/campers returns {len(data)} campers")


class TestBuses:
    """Bus information endpoints"""
    
    def test_get_buses(self):
        """GET /api/buses returns list of 34 buses"""
        response = requests.get(f"{BASE_URL}/api/buses")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "buses" in data
        buses = data["buses"]
        assert len(buses) == 34
        # Verify bus structure
        bus = buses[0]
        assert "bus_number" in bus
        assert "capacity" in bus
        assert "am_camper_count" in bus
        assert "pm_camper_count" in bus
        print(f"PASS: /api/buses returns {len(buses)} buses")


class TestBusZones:
    """Bus zone endpoints"""
    
    def test_get_bus_zones(self):
        """GET /api/bus-zones returns zones data"""
        response = requests.get(f"{BASE_URL}/api/bus-zones")
        assert response.status_code == 200
        data = response.json()
        assert "zones" in data
        print(f"PASS: /api/bus-zones returns {len(data['zones'])} zones")


class TestShadows:
    """Shadow staff endpoints"""
    
    def test_get_shadows(self):
        """GET /api/shadows returns shadows data"""
        response = requests.get(f"{BASE_URL}/api/shadows")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "shadows" in data
        print(f"PASS: /api/shadows returns {data['count']} shadows")


class TestBusStaff:
    """Bus staff endpoints"""
    
    def test_get_bus_staff(self):
        """GET /api/bus-staff returns staff data"""
        response = requests.get(f"{BASE_URL}/api/bus-staff")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "staff" in data
        print(f"PASS: /api/bus-staff returns {data['count']} staff configurations")


class TestBusTracking:
    """GPS tracking, attendance, and history endpoints"""
    
    def test_bus_tracking_login(self):
        """POST /api/bus-tracking/login with pin '1' returns Bus #01 with campers"""
        response = requests.post(
            f"{BASE_URL}/api/bus-tracking/login",
            json={"pin": "1"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["bus_number"] == "Bus #01"
        assert "campers" in data
        assert "attendance" in data
        assert len(data["campers"]) > 0
        print(f"PASS: /api/bus-tracking/login - Bus #01 with {len(data['campers'])} campers")
    
    def test_bus_tracking_login_invalid(self):
        """POST /api/bus-tracking/login with invalid pin returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/bus-tracking/login",
            json={"pin": "99"}
        )
        # Bus #99 doesn't exist, should return 401
        assert response.status_code == 401
        print("PASS: /api/bus-tracking/login with invalid pin returns 401")
    
    def test_bus_tracking_history(self):
        """GET /api/bus-tracking/history/Bus%20%2301 returns history data"""
        response = requests.get(f"{BASE_URL}/api/bus-tracking/history/Bus%20%2301")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["bus_number"] == "Bus #01"
        assert "points" in data
        assert "stops" in data
        print(f"PASS: /api/bus-tracking/history - {data['point_count']} points, {data['stop_count']} stops")
    
    def test_attendance_report_json(self):
        """GET /api/bus-tracking/attendance-report/json returns report data"""
        response = requests.get(f"{BASE_URL}/api/bus-tracking/attendance-report/json")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "date" in data
        assert "buses" in data
        assert "totals" in data
        print(f"PASS: /api/bus-tracking/attendance-report/json - {data['totals']['buses_reporting']} buses reporting")


class TestAutoSync:
    """Auto-sync status endpoints"""
    
    def test_auto_sync_status(self):
        """GET /api/auto-sync-status returns sync status"""
        response = requests.get(f"{BASE_URL}/api/auto-sync-status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "interval_minutes" in data
        print(f"PASS: /api/auto-sync-status - enabled: {data['enabled']}, interval: {data['interval_minutes']} min")


class TestRouteSheet:
    """Route sheet endpoints"""
    
    def test_route_sheet(self):
        """GET /api/route-sheet/Bus%20%2301 returns route sheet with AM and PM stops"""
        response = requests.get(f"{BASE_URL}/api/route-sheet/Bus%20%2301")
        assert response.status_code == 200
        data = response.json()
        assert data["bus_number"] == "Bus #01"
        assert "am_stops" in data
        assert "pm_stops" in data
        assert len(data["am_stops"]) > 0
        assert len(data["pm_stops"]) > 0
        print(f"PASS: /api/route-sheet - {data['total_am_stops']} AM stops, {data['total_pm_stops']} PM stops")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
