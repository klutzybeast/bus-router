"""Audit endpoints for verifying bus assignments."""

import os
import csv
import logging
from io import StringIO
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

from services.database import db, CAMPMINDER_SHEET_ID

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Audit"])

@router.get("/audit/campers")
async def audit_all_campers():
    """
    Comprehensive audit of ALL campers to verify bus assignments are correct.
    Compares database values against Google Sheet source data.
    
    Distinguishes between:
    - TRUE ERRORS: Database has different bus than Sheet (Sheet has valid bus)
    - AUTO-ASSIGNMENTS: Database has bus, Sheet has NONE (system auto-assigned)
    """
    import httpx
    import csv
    from io import StringIO
    
    logger.info("=== STARTING COMPREHENSIVE CAMPER AUDIT ===")
    
    results = {
        "status": "success",
        "total_checked": 0,
        "true_errors": [],         # DB differs from valid sheet bus
        "auto_assignments": [],     # DB has bus, sheet has NONE
        "summary": {}
    }
    
    try:
        # Step 1: Load all campers from database
        db_campers = await db.campers.find({}).to_list(None)
        logger.info(f"Loaded {len(db_campers)} campers from database")
        
        # Step 2: Load Google Sheet data for comparison
        sheet_id = CAMPMINDER_SHEET_ID
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(csv_url)
            csv_content = response.text
        
        # Parse Google Sheet data
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]
        
        reader = csv.DictReader(StringIO(csv_content))
        sheet_data = {}
        
        for row in reader:
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            am_bus = row.get('2026Transportation M AM Bus', '').strip()
            pm_bus = row.get('2026Transportation M PM Bus', '').strip()
            
            if first_name and last_name:
                key = f"{last_name}_{first_name}".lower()
                sheet_data[key] = {
                    'name': f"{first_name} {last_name}",
                    'sheet_am_bus': am_bus,
                    'sheet_pm_bus': pm_bus
                }
        
        logger.info(f"Loaded {len(sheet_data)} campers from Google Sheet")
        
        # Step 3: Audit each camper
        seen_campers = set()
        
        for camper in db_campers:
            first_name = camper.get('first_name', '')
            last_name = camper.get('last_name', '')
            camper_id = camper.get('_id', '')
            db_am_bus = camper.get('am_bus_number', '')
            db_pm_bus = camper.get('pm_bus_number', '')
            
            # Skip PM-specific entries
            if camper_id.endswith('_PM'):
                continue
            
            # Skip if already checked
            full_name = f"{first_name} {last_name}"
            if full_name in seen_campers:
                continue
            seen_campers.add(full_name)
            
            results["total_checked"] += 1
            
            # Find in sheet data
            key = f"{last_name}_{first_name}".lower()
            sheet_camper = sheet_data.get(key)
            
            if not sheet_camper:
                continue
            
            sheet_am = sheet_camper['sheet_am_bus']
            sheet_pm = sheet_camper['sheet_pm_bus']
            
            # Determine if sheet value is valid bus
            def is_valid_sheet_bus(val):
                if not val:
                    return False
                val_upper = val.upper()
                if val_upper == 'NONE' or val_upper == '':
                    return False
                if any(x in val_upper for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM']):
                    return False
                return val.startswith('Bus')
            
            # Check AM
            if db_am_bus and db_am_bus != 'NONE' and db_am_bus.startswith('Bus'):
                if is_valid_sheet_bus(sheet_am):
                    # Both have valid buses - check if they match
                    db_norm = db_am_bus.replace(' ', '')
                    sheet_norm = sheet_am.replace(' ', '')
                    if db_norm != sheet_norm:
                        results["true_errors"].append({
                            "camper": full_name,
                            "type": "AM",
                            "database_value": db_am_bus,
                            "sheet_value": sheet_am,
                            "issue": "TRUE ERROR: AM bus mismatch"
                        })
                else:
                    # DB has bus, sheet has NONE - auto-assignment
                    results["auto_assignments"].append({
                        "camper": full_name,
                        "type": "AM",
                        "auto_assigned_bus": db_am_bus,
                        "sheet_value": sheet_am or "NONE"
                    })
            
            # Check PM
            if db_pm_bus and db_pm_bus != 'NONE' and db_pm_bus.startswith('Bus'):
                if is_valid_sheet_bus(sheet_pm):
                    # Both have valid buses - check if they match
                    db_norm = db_pm_bus.replace(' ', '')
                    sheet_norm = sheet_pm.replace(' ', '')
                    if db_norm != sheet_norm:
                        results["true_errors"].append({
                            "camper": full_name,
                            "type": "PM",
                            "database_value": db_pm_bus,
                            "sheet_value": sheet_pm,
                            "issue": "TRUE ERROR: PM bus mismatch"
                        })
                else:
                    # DB has bus, sheet has NONE - auto-assignment
                    results["auto_assignments"].append({
                        "camper": full_name,
                        "type": "PM",
                        "auto_assigned_bus": db_pm_bus,
                        "sheet_value": sheet_pm or "NONE"
                    })
        
        # Step 4: Generate summary
        results["summary"] = {
            "total_campers_checked": results["total_checked"],
            "true_errors_count": len(results["true_errors"]),
            "auto_assignments_count": len(results["auto_assignments"]),
            "validation_passed": len(results["true_errors"]) == 0,
            "message": "✓✓✓ ALL BUS LABELS MATCH GOOGLE SHEET" if len(results["true_errors"]) == 0 else f"❌ Found {len(results['true_errors'])} bus mismatches"
        }
        
        if len(results["true_errors"]) > 0:
            results["status"] = "errors_found"
            logger.error(f"AUDIT FOUND {len(results['true_errors'])} TRUE ERRORS")
        else:
            logger.info(f"AUDIT PASSED - {len(results['auto_assignments'])} auto-assignments detected (expected)")
        
        return results
        
    except Exception as e:
        logger.error(f"Error during audit: {str(e)}")
        results["status"] = "error"
        results["message"] = str(e)
        return results


@router.get("/audit/bus/{bus_number}")
async def audit_single_bus(bus_number: str):
    """Audit all campers on a specific bus"""
    
    # Get all campers assigned to this bus
    campers = await db.campers.find({
        "$or": [
            {"am_bus_number": bus_number},
            {"pm_bus_number": bus_number}
        ]
    }).to_list(None)
    
    results = {
        "bus_number": bus_number,
        "am_campers": [],
        "pm_campers": [],
        "am_count": 0,
        "pm_count": 0
    }
    
    seen_am = set()
    seen_pm = set()
    
    for camper in campers:
        name = f"{camper['first_name']} {camper['last_name']}"
        camper_id = camper.get('_id', '')
        
        # Check AM assignment
        if camper.get('am_bus_number') == bus_number and name not in seen_am:
            if not camper_id.endswith('_PM'):
                results["am_campers"].append({
                    "name": name,
                    "address": camper.get('location', {}).get('address', ''),
                    "am_bus": camper.get('am_bus_number', ''),
                    "pm_bus": camper.get('pm_bus_number', '')
                })
                seen_am.add(name)
        
        # Check PM assignment
        if camper.get('pm_bus_number') == bus_number and name not in seen_pm:
            results["pm_campers"].append({
                "name": name,
                "address": camper.get('location', {}).get('address', ''),
                "am_bus": camper.get('am_bus_number', ''),
                "pm_bus": camper.get('pm_bus_number', '')
            })
            seen_pm.add(name)
    
    results["am_count"] = len(results["am_campers"])
    results["pm_count"] = len(results["pm_campers"])
    
    return results
