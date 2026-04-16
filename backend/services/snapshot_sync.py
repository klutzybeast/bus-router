"""Service for syncing CampMinder person IDs and pushing attendance to CamperSnapshot.

Flow:
1. sync_person_ids(): Pulls persons from CampMinder API → caches name→pid mapping → stores person_id on camper records
2. assign_person_id(): Looks up a single new camper against the cached mapping
3. push_attendance_to_snapshot(): Called when counselor marks attendance → pushes to CamperSnapshot via person_id
"""

import os
import logging
import asyncio
import urllib.parse
import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.database import db, campminder_api

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")
CAMPERSNAPSHOT_URL = os.environ.get("CAMPERSNAPSHOT_URL", "https://campersnapshot.com")


async def sync_person_ids() -> dict:
    """Pull persons from CampMinder Persons API, cache mapping, match to campers, store person_id."""
    try:
        headers = None
        for auth_attempt in range(3):
            try:
                headers = await campminder_api.get_auth_headers()
                break
            except Exception:
                wait = 10 * (auth_attempt + 1)
                logger.warning(f"Auth attempt {auth_attempt + 1} failed, waiting {wait}s...")
                await asyncio.sleep(wait)

        if not headers:
            return {"success": False, "error": "Could not authenticate with CampMinder after retries"}

        client_id = campminder_api.client_ids or "241"
        all_persons = []
        page = 1

        async with httpx.AsyncClient(timeout=90.0) as client:
            while True:
                response = None
                for attempt in range(3):
                    try:
                        response = await client.get(
                            "https://api.campminder.com/persons/",
                            headers=headers,
                            params={"clientid": client_id, "pagenumber": page, "pagesize": 1000, "includecamperdetails": "false"},
                        )
                    except Exception as req_err:
                        logger.warning(f"Request error page {page}: {req_err}")
                        await asyncio.sleep(5)
                        continue
                    if response.status_code == 429:
                        await asyncio.sleep(10 * (attempt + 1))
                        headers = await campminder_api.get_auth_headers()
                        continue
                    break

                if not response or response.status_code != 200:
                    break

                data = response.json()
                if not data:
                    break
                results = data.get("Results", [])
                all_persons.extend(results)
                total = data.get("TotalCount", 0)
                logger.info(f"Fetched page {page}: {len(results)} persons ({len(all_persons)}/{total})")
                if len(all_persons) >= total or not results:
                    break
                page += 1
                await asyncio.sleep(1)

        logger.info(f"Total CampMinder persons fetched: {len(all_persons)}")

        # Build name→person_id lookup (deduplicated, last match wins)
        cm_lookup = {}
        for person in all_persons:
            name_obj = person.get("Name") or {}
            first = (name_obj.get("First") or "").strip().lower()
            last = (name_obj.get("Last") or "").strip().lower()
            pid = person.get("ID")
            if first and last and pid:
                cm_lookup[f"{first}|{last}"] = str(pid)

        # Store cache in MongoDB for future auto-assign (deduplicated)
        if cm_lookup:
            await db.person_id_cache.delete_many({})
            cache_docs = [{"_id": key, "person_id": pid, "first": key.split("|")[0], "last": key.split("|")[1]} for key, pid in cm_lookup.items()]
            await db.person_id_cache.insert_many(cache_docs)
            logger.info(f"Cached {len(cache_docs)} person_id mappings")

        # Match to campers and update person_id
        campers_cursor = db.campers.find({}, {"_id": 1, "first_name": 1, "last_name": 1})
        matched = 0
        unmatched = []
        async for camper in campers_cursor:
            cid = camper["_id"]
            if str(cid).endswith("_PM"):
                continue
            first = (camper.get("first_name") or "").strip().lower()
            last = (camper.get("last_name") or "").strip().lower()
            pid = cm_lookup.get(f"{first}|{last}")
            if pid:
                await db.campers.update_one({"_id": cid}, {"$set": {"person_id": pid}})
                matched += 1
            else:
                unmatched.append(f"{camper.get('first_name')} {camper.get('last_name')}")

        return {
            "success": True,
            "campminder_persons": len(all_persons),
            "cached_mappings": len(cm_lookup),
            "matched": matched,
            "unmatched": len(unmatched),
            "unmatched_names": unmatched[:20],
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        import traceback
        logger.error(f"Person ID sync error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}


async def assign_person_id(camper_id: str, first_name: str, last_name: str):
    """Auto-assign person_id to a single new camper using the cached mapping.
    Called after a new camper is inserted during sync.
    """
    try:
        key = f"{first_name.strip().lower()}|{last_name.strip().lower()}"
        cached = await db.person_id_cache.find_one({"_id": key})
        if cached:
            await db.campers.update_one({"_id": camper_id}, {"$set": {"person_id": cached["person_id"]}})
            logger.info(f"Auto-assigned person_id {cached['person_id']} to {camper_id}")
    except Exception as e:
        logger.warning(f"Auto-assign person_id failed for {camper_id}: {e}")


async def push_attendance_to_snapshot(camper_id: str, status: str, date: str):
    """Push attendance to CamperSnapshot using its UUID (not person_id).
    Looks up CamperSnapshot UUID by matching camper name from the roster.
    """
    try:
        camper = await db.campers.find_one(
            {"_id": camper_id},
            {"first_name": 1, "last_name": 1, "am_bus_number": 1, "snapshot_id": 1}
        )
        if not camper:
            return

        snapshot_id = camper.get("snapshot_id")

        # If no cached snapshot_id, look it up from CamperSnapshot roster
        if not snapshot_id:
            bus = camper.get("am_bus_number", "")
            name = f"{camper.get('first_name', '')} {camper.get('last_name', '')}".strip().lower()
            roster = await fetch_snapshot_roster(date=date, bus_number=bus)

            # Search in am_riders or campers
            riders = roster.get("am_riders", roster.get("campers", []))
            for r in riders:
                if r.get("name", "").strip().lower() == name:
                    snapshot_id = r.get("id")
                    break

            if snapshot_id:
                await db.campers.update_one({"_id": camper_id}, {"$set": {"snapshot_id": snapshot_id}})
            else:
                print(f"[SNAP] Could not find UUID for {camper_id} ({name}) on {bus}")
                return

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{CAMPERSNAPSHOT_URL}/api/bus-roster/mark",
                json={"camper_id": snapshot_id, "status": status, "date": date},
            )
            print(f"[SNAP] {camper_id} -> {snapshot_id} {status} {date}: {response.status_code}")

    except Exception as e:
        print(f"[SNAP] Error: {e}")


async def fetch_snapshot_roster(date: str = None, bus_number: str = None) -> dict:
    """Pull daily roster from CamperSnapshot (session-aware, bus riders only)."""
    try:
        if not date:
            date = datetime.now(EASTERN).strftime("%Y-%m-%d")

        if bus_number:
            encoded = urllib.parse.quote(bus_number, safe="")
            url = f"{CAMPERSNAPSHOT_URL}/api/bus-roster/{encoded}"
        else:
            url = f"{CAMPERSNAPSHOT_URL}/api/bus-roster"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params={"date": date})

        if response.status_code == 200:
            return response.json()
        else:
            print(f"[SNAP] Roster fetch failed: {response.status_code} {response.text[:200]}")
            return {"error": f"CamperSnapshot returned {response.status_code}", "fallback": True}

    except Exception as e:
        print(f"[SNAP] Roster fetch error: {e}")
        return {"error": str(e), "fallback": True}
