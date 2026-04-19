"""
Tests for Admin Clear Attendance feature:
- POST /api/bus-tracking/clear-attendance with list body and optional bus_number query param
- E2E: create attendance via POST /api/bus-tracking/attendance → verify → clear → verify deleted
- Regular counselor login with PIN '1' still works
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://counselor-admin-test.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def bus1_camper_id(session):
    r = session.post(f"{API}/bus-tracking/login", json={"pin": "1"}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("bus_number") in ("Bus #01", "Bus#01", "01", "1") or "bus_number" in data
    campers = data.get("campers") or []
    assert len(campers) > 0, "no campers returned for bus pin=1"
    # Prefer id field
    cid = campers[0].get("id") or campers[0].get("camper_id") or campers[0].get("_id")
    assert cid, f"camper id field missing in {campers[0]}"
    return {"bus_number": data["bus_number"], "camper_id": cid}


# ---------- Counselor login still works ----------
class TestCounselorLogin:
    def test_login_pin_1_returns_bus01(self, session):
        r = session.post(f"{API}/bus-tracking/login", json={"pin": "1"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "bus_number" in data
        assert "campers" in data
        assert isinstance(data["campers"], list)
        assert len(data["campers"]) > 0

    def test_login_admin_pin_not_valid_bus(self, session):
        # 'admin' should NOT be a valid bus-login; admin is purely client-side gate
        r = session.post(f"{API}/bus-tracking/login", json={"pin": "admin"}, timeout=30)
        assert r.status_code in (400, 401, 404, 422), f"expected rejection, got {r.status_code}: {r.text}"


# ---------- Clear-Attendance API ----------
class TestClearAttendanceAPI:
    TEST_DATE = "2026-07-15"  # A camp day (not Sunday)

    def _mark(self, session, bus, camper_id, date, status="present"):
        url = f"{API}/bus-tracking/attendance?bus_number={requests.utils.quote(bus)}&date={date}"
        return session.post(url, json={"camper_id": camper_id, "status": status}, timeout=30)

    def test_clear_with_empty_dates(self, session):
        r = session.post(f"{API}/bus-tracking/clear-attendance", json=[], timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["deleted"] == 0

    def test_e2e_create_verify_clear_verify_deletion(self, session, bus1_camper_id):
        bus = bus1_camper_id["bus_number"]
        camper = bus1_camper_id["camper_id"]
        date = self.TEST_DATE

        # CREATE attendance
        r = self._mark(session, bus, camper, date, "present")
        assert r.status_code == 200, f"mark failed: {r.status_code} {r.text}"

        # VERIFY attendance exists via GET /bus-tracking/attendance/{bus_number}?date=...
        g = session.get(f"{API}/bus-tracking/attendance/{requests.utils.quote(bus)}?date={date}", timeout=30)
        assert g.status_code == 200, f"GET attendance failed: {g.status_code} {g.text}"
        existing = g.json()
        # response has records list with camper_id field
        attendance_records = existing.get("records", []) if isinstance(existing, dict) else existing
        found = any(rec.get("camper_id") == camper for rec in attendance_records)
        assert found, f"attendance (camper={camper}) not found before clear: {existing}"

        # CLEAR via admin endpoint with bus filter
        c = session.post(
            f"{API}/bus-tracking/clear-attendance?bus_number={requests.utils.quote(bus)}",
            json=[date],
            timeout=30,
        )
        assert c.status_code == 200, f"clear failed: {c.status_code} {c.text}"
        cdata = c.json()
        assert cdata["success"] is True
        assert cdata["deleted"] >= 1, f"expected >=1 deleted, got {cdata}"
        assert cdata["bus_number"] == bus

        # VERIFY deletion
        g2 = session.get(f"{API}/bus-tracking/attendance/{requests.utils.quote(bus)}?date={date}", timeout=30)
        assert g2.status_code == 200
        after = g2.json()
        attendance_records = after.get("records", []) if isinstance(after, dict) else after
        assert not any(rec.get("camper_id") == camper for rec in attendance_records), f"record still present: {after}"

    def test_clear_all_buses_for_date(self, session, bus1_camper_id):
        bus = bus1_camper_id["bus_number"]
        camper = bus1_camper_id["camper_id"]
        date = "2026-07-16"

        # Create
        r = self._mark(session, bus, camper, date, "absent")
        assert r.status_code == 200

        # Clear without bus_number (ALL)
        c = session.post(f"{API}/bus-tracking/clear-attendance", json=[date], timeout=30)
        assert c.status_code == 200
        cdata = c.json()
        assert cdata["success"] is True
        assert cdata["bus_number"] == "ALL"
        assert cdata["deleted"] >= 1

    def test_clear_with_wrong_bus_does_not_delete(self, session, bus1_camper_id):
        bus = bus1_camper_id["bus_number"]
        camper = bus1_camper_id["camper_id"]
        date = "2026-07-17"

        r = self._mark(session, bus, camper, date, "present")
        assert r.status_code == 200

        # Try clear with bus that doesn't match
        c = session.post(
            f"{API}/bus-tracking/clear-attendance?bus_number=Bus%20%2399",
            json=[date],
            timeout=30,
        )
        assert c.status_code == 200
        cdata = c.json()
        assert cdata["deleted"] == 0

        # Cleanup: clear correct bus
        session.post(
            f"{API}/bus-tracking/clear-attendance?bus_number={requests.utils.quote(bus)}",
            json=[date],
            timeout=30,
        )
