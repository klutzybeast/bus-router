"""Service for syncing CampMinder person IDs and pushing attendance to CamperSnapshot.

Flow:
1. sync_person_ids(): Pulls persons from CampMinder API → matches by name → stores person_id on camper records
2. push_attendance_to_snapshot(): Called when counselor marks attendance → pushes to CamperSnapshot via person_id
"""

import os
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.database import db, campminder_api

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")
CAMPERSNAPSHOT_URL = os.environ.get("CAMPERSNAPSHOT_URL", "https://campersnapshot.com")


async def sync_person_ids() -> dict:
    """Pull persons from CampMinder new Persons API, match to our campers by name, store person_id."""
    try:
        # Get JWT with retry for rate limits
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
        page_size = 1000

        async with httpx.AsyncClient(timeout=90.0) as client:
            while True:
                response = None
                for attempt in range(3):
                    try:
                        response = await client.get(
                            "https://api.campminder.com/persons/",
                            headers=headers,
                            params={
                                "clientid": client_id,
                                "pagenumber": page,
                                "pagesize": page_size,
                                "includecamperdetails": "false",
                            },
                        )
                    except Exception as req_err:
                        logger.warning(f"Request error page {page}: {req_err}")
                        await asyncio.sleep(5)
                        continue

                    if response.status_code == 429:
                        wait = 10 * (attempt + 1)
                        logger.warning(f"Rate limited on page {page}, waiting {wait}s...")
                        await asyncio.sleep(wait)
                        headers = await campminder_api.get_auth_headers()
                        continue
                    break

                if not response or response.status_code != 200:
                    status = response.status_code if response else "no response"
                    logger.error(f"CampMinder Persons API error on page {page}: {status}")
                    break

                data = response.json()
                if not data:
                    break

                results = data.get("Results", [])
                all_persons.extend(results)

                total = data.get("TotalCount", 0)
                logger.info(f"Fetched page {page}: {len(results)} persons (total so far: {len(all_persons)}/{total})")

                if len(all_persons) >= total or not results:
                    break
                page += 1
                await asyncio.sleep(1)  # Rate limit courtesy delay

        logger.info(f"Total CampMinder persons fetched: {len(all_persons)}")

        # Build name→person_id lookup (lowercase for case-insensitive matching)
        cm_lookup = {}
        for person in all_persons:
            name_obj = person.get("Name") or {}
            first = (name_obj.get("First") or "").strip().lower()
            last = (name_obj.get("Last") or "").strip().lower()
            pid = person.get("ID")
            if first and last and pid:
                key = f"{first}|{last}"
                cm_lookup[key] = pid

        logger.info(f"CampMinder name lookup built: {len(cm_lookup)} entries")

        # Match to our campers and update person_id
        campers_cursor = db.campers.find({}, {"_id": 1, "first_name": 1, "last_name": 1})
        matched = 0
        unmatched = []

        async for camper in campers_cursor:
            cid = camper["_id"]
            # Skip _PM records
            if str(cid).endswith("_PM"):
                continue

            first = (camper.get("first_name") or "").strip().lower()
            last = (camper.get("last_name") or "").strip().lower()
            key = f"{first}|{last}"

            pid = cm_lookup.get(key)
            if pid:
                await db.campers.update_one({"_id": cid}, {"$set": {"person_id": str(pid)}})
                matched += 1
            else:
                unmatched.append(f"{camper.get('first_name')} {camper.get('last_name')}")

        result = {
            "success": True,
            "campminder_persons": len(all_persons),
            "matched": matched,
            "unmatched": len(unmatched),
            "unmatched_names": unmatched[:20],
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Person ID sync complete: {matched} matched, {len(unmatched)} unmatched")
        return result

    except Exception as e:
        import traceback
        logger.error(f"Person ID sync error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}


async def push_attendance_to_snapshot(camper_id: str, status: str, date: str):
    """Push a single attendance mark to CamperSnapshot using the camper's person_id.
    Fire-and-forget — errors are logged but don't block the counselor app.
    """
    try:
        camper = await db.campers.find_one({"_id": camper_id}, {"person_id": 1})
        if not camper or not camper.get("person_id"):
            return

        person_id = camper["person_id"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{CAMPERSNAPSHOT_URL}/api/bus-roster/mark",
                json={
                    "camper_id": person_id,
                    "status": status,
                    "date": date,
                },
            )
            if response.status_code == 200:
                logger.info(f"Snapshot push OK: {camper_id} (pid={person_id}) -> {status}")
            else:
                logger.warning(f"Snapshot push failed: {response.status_code} - {response.text[:200]}")

    except Exception as e:
        logger.warning(f"CamperSnapshot push error for {camper_id}: {str(e)}")
