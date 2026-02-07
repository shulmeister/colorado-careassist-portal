#!/usr/bin/env python3
"""
WellSky Full Sync Script — Clients, Caregivers, and Family Contacts

Syncs active clients, caregivers, and family contacts from WellSky
to local PostgreSQL cache for fast caller ID lookup.

Run daily at 3am via launchd (com.coloradocareassist.wellsky-sync).

API approach (per WellSky Connect API docs):
- Clients: GET /patients/?last_name:contains=XX with 2-letter combos
  (bulk GET /patients/?active=true returns 0 due to API bug)
- Caregivers: POST /practitioners/_search/ with active=true, is_hired=true
- Family: GET /relatedperson/{patient_id}/ for each active client
"""

import os
import sys
import json
import string
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import Json
import requests

# Logging
log_dir = Path.home() / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / 'wellsky-sync.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment
env_file = Path.home() / '.gigi-env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value.strip('"').strip("'")

# Config
BASE_URL = "https://connect.clearcareonline.com/v1"
TOKEN_URL = "https://connect.clearcareonline.com/oauth/accesstoken"
CLIENT_ID = os.environ.get('WELLSKY_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('WELLSKY_CLIENT_SECRET', '')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://careassist@localhost:5432/careassist')


def get_token():
    """Get OAuth2 access token."""
    try:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        })
        if r.status_code == 200:
            return r.json().get("access_token")
        logger.error(f"Token error: {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Token exception: {e}")
    return None


def parse_telecom(telecom_list):
    """Extract phone numbers and email from FHIR telecom array."""
    phone = home_phone = work_phone = email = ""
    for t in (telecom_list or []):
        if t.get("system") == "phone":
            val = t.get("value", "")
            use = t.get("use", "")
            if use == "mobile":
                phone = val
            elif use == "home":
                home_phone = val
            elif use == "work":
                work_phone = val
            elif not phone:
                phone = val
        elif t.get("system") == "email":
            email = t.get("value", "")
    return phone, home_phone, work_phone, email


def parse_address(address_list):
    """Extract address fields from FHIR address array."""
    if not address_list:
        return "", "", "", ""
    a = address_list[0]
    return (
        ", ".join(a.get("line", [])),
        a.get("city", ""),
        a.get("state", ""),
        a.get("postalCode", "")
    )


def sync_patients(token, db):
    """Sync active clients using GET /patients/?last_name:contains=XX."""
    logger.info("--- Syncing active clients ---")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    all_active = {}

    # Search all 2-letter last name combinations (676 total)
    combos = [f"{a}{b}" for a in string.ascii_uppercase for b in string.ascii_lowercase]
    for combo in combos:
        try:
            r = requests.get(f"{BASE_URL}/patients/", headers=headers,
                             params={"last_name:contains": combo, "_count": 100})
            if r.status_code != 200:
                continue
            for entry in r.json().get("entry", []):
                res = entry.get("resource", entry)
                if res.get("active") != True or res.get("id") in all_active:
                    continue
                nd = res.get("name", [{}])[0]
                fn = (nd.get("given", [""])[0] if nd.get("given") else "")
                ln = nd.get("family", "")
                phone, hphone, wphone, email = parse_telecom(res.get("telecom"))
                addr, city, state, zipcode = parse_address(res.get("address"))
                all_active[res["id"]] = {
                    "fn": fn, "ln": ln, "full": f"{fn} {ln}".strip(),
                    "phone": phone, "hphone": hphone, "wphone": wphone, "email": email,
                    "addr": addr, "city": city, "state": state, "zip": zipcode,
                    "data": res
                }
        except Exception as e:
            logger.error(f"Patient search error ({combo}): {e}")

    logger.info(f"Found {len(all_active)} active clients")

    # Write to database
    cur = db.cursor()
    cur.execute("UPDATE cached_patients SET is_active = false, status = 'INACTIVE', synced_at = NOW()")
    for pid, d in all_active.items():
        cur.execute("""
            INSERT INTO cached_patients (id,first_name,last_name,full_name,phone,home_phone,work_phone,
                email,address,city,state,zip_code,status,is_active,wellsky_data,synced_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',true,%s,NOW(),NOW())
            ON CONFLICT (id) DO UPDATE SET
                first_name=EXCLUDED.first_name,last_name=EXCLUDED.last_name,full_name=EXCLUDED.full_name,
                phone=EXCLUDED.phone,home_phone=EXCLUDED.home_phone,work_phone=EXCLUDED.work_phone,
                email=EXCLUDED.email,address=EXCLUDED.address,city=EXCLUDED.city,state=EXCLUDED.state,
                zip_code=EXCLUDED.zip_code,status='ACTIVE',is_active=true,wellsky_data=EXCLUDED.wellsky_data,
                synced_at=NOW(),updated_at=NOW()
        """, (pid, d["fn"], d["ln"], d["full"], d["phone"], d["hphone"], d["wphone"],
              d["email"], d["addr"], d["city"], d["state"], d["zip"], Json(d["data"])))
    db.commit()
    return list(all_active.keys())


def sync_practitioners(token, db):
    """Sync active hired caregivers using POST /practitioners/_search/."""
    logger.info("--- Syncing active caregivers ---")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    r = requests.post(f"{BASE_URL}/practitioners/_search/", headers=headers,
                      params={"_count": 100},
                      json={"active": "true", "is_hired": "true"})
    if r.status_code != 200:
        logger.error(f"Practitioner search failed: {r.status_code}")
        return

    entries = r.json().get("entry", [])
    logger.info(f"Found {len(entries)} active hired caregivers")

    cur = db.cursor()
    for entry in entries:
        res = entry.get("resource", entry)
        nd = res.get("name", [{}])[0]
        fn = (nd.get("given", [""])[0] if nd.get("given") else "")
        ln = nd.get("family", "")
        phone, hphone, wphone, email = parse_telecom(res.get("telecom"))
        addr, city, state, zipcode = parse_address(res.get("address"))

        # Extract language from FHIR communication[] array
        # WellSky format: communication[].coding[].display (not nested under .language)
        languages = []
        preferred_language = "English"
        for comm in res.get("communication", []):
            # Try WellSky format first: coding at top level of comm entry
            coding = comm.get("coding", [])
            if not coding:
                # Fallback: standard FHIR format with nested language.coding
                lang = comm.get("language", {})
                coding = lang.get("coding", [])
            display = coding[0].get("display", "") if coding else ""
            if display:
                languages.append(display)
            if comm.get("preferred", False) and display:
                preferred_language = display
        if not languages:
            languages = ["English"]
        languages_json = json.dumps(languages)

        cur.execute("""
            INSERT INTO cached_practitioners (id,first_name,last_name,full_name,phone,home_phone,work_phone,
                email,address,city,state,zip_code,status,is_hired,is_active,
                preferred_language,languages,wellsky_data,synced_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'HIRED',true,true,%s,%s,%s,NOW(),NOW())
            ON CONFLICT (id) DO UPDATE SET
                first_name=EXCLUDED.first_name,last_name=EXCLUDED.last_name,full_name=EXCLUDED.full_name,
                phone=EXCLUDED.phone,home_phone=EXCLUDED.home_phone,work_phone=EXCLUDED.work_phone,
                email=EXCLUDED.email,address=EXCLUDED.address,city=EXCLUDED.city,state=EXCLUDED.state,
                zip_code=EXCLUDED.zip_code,is_hired=true,is_active=true,
                preferred_language=EXCLUDED.preferred_language,languages=EXCLUDED.languages,
                wellsky_data=EXCLUDED.wellsky_data,
                synced_at=NOW(),updated_at=NOW()
        """, (res.get("id"), fn, ln, f"{fn} {ln}".strip(), phone, hphone, wphone,
              email, addr, city, state, zipcode,
              preferred_language, languages_json, Json(res)))
    db.commit()


def sync_related_persons(token, db, patient_ids):
    """Sync family/emergency contacts for each active client."""
    logger.info(f"--- Syncing family contacts for {len(patient_ids)} clients ---")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    total = 0

    cur = db.cursor()
    for pid in patient_ids:
        try:
            r = requests.get(f"{BASE_URL}/relatedperson/{pid}/", headers=headers)
            if r.status_code != 200:
                continue
            for entry in r.json().get("entry", []):
                res = entry.get("resource", entry)
                cid = res.get("id")
                if not cid:
                    continue
                nd = (res.get("name", [{}])[0] if res.get("name") else {})
                fn = (nd.get("given", [""])[0] if nd.get("given") else "")
                ln = nd.get("family", "")
                rel = ""
                if res.get("relationship", {}).get("coding"):
                    rel = res["relationship"]["coding"][0].get("display",
                          res["relationship"]["coding"][0].get("code", ""))
                phone, hphone, wphone, email = parse_telecom(res.get("telecom"))
                city = state = ""
                if res.get("address"):
                    city = res["address"][0].get("city", "")
                    state = res["address"][0].get("state", "")

                cur.execute("""
                    INSERT INTO cached_related_persons (id,patient_id,first_name,last_name,full_name,
                        relationship,phone,home_phone,work_phone,email,city,state,
                        is_emergency_contact,is_primary_contact,is_payer,is_poa,is_active,
                        wellsky_data,synced_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,NOW(),NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        patient_id=EXCLUDED.patient_id,first_name=EXCLUDED.first_name,
                        last_name=EXCLUDED.last_name,full_name=EXCLUDED.full_name,
                        relationship=EXCLUDED.relationship,phone=EXCLUDED.phone,
                        home_phone=EXCLUDED.home_phone,work_phone=EXCLUDED.work_phone,
                        email=EXCLUDED.email,city=EXCLUDED.city,state=EXCLUDED.state,
                        is_emergency_contact=EXCLUDED.is_emergency_contact,
                        is_primary_contact=EXCLUDED.is_primary_contact,
                        is_payer=EXCLUDED.is_payer,is_poa=EXCLUDED.is_poa,
                        wellsky_data=EXCLUDED.wellsky_data,synced_at=NOW(),updated_at=NOW()
                """, (cid, pid, fn, ln, f"{fn} {ln}".strip(), rel, phone, hphone, wphone,
                      email, city, state,
                      res.get("emergencyContact", False),
                      res.get("primaryContact", False),
                      res.get("payer", False),
                      res.get("poa", False),
                      Json(res)))
                total += 1
        except Exception as e:
            logger.error(f"RelatedPerson error for patient {pid}: {e}")

    db.commit()
    logger.info(f"Synced {total} family contacts")


def sync_appointments(token, db):
    """Sync appointments using WellSky API (requires use of WellSkyService)."""
    logger.info("--- Syncing appointments/shifts ---")

    # Import WellSky service for proper API access
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.wellsky_service import WellSkyService
    from datetime import datetime, timedelta

    wellsky = WellSkyService()
    all_appointments = []

    # Fetch appointments for previous, current, and next month
    today = datetime.now().date()
    prev_month = (today - timedelta(days=today.day)).strftime("%Y%m")
    current_month = today.strftime("%Y%m")
    next_month = (today + timedelta(days=32)).strftime("%Y%m")

    # Get all active clients (no LIMIT)
    cur = db.cursor()
    cur.execute("SELECT id FROM cached_patients WHERE is_active = true")
    client_ids = [row[0] for row in cur.fetchall()]
    logger.info(f"Syncing appointments for {len(client_ids)} active clients")

    for month_no in [prev_month, current_month, next_month]:
        logger.info(f"Fetching appointments for month {month_no}...")

        # Fetch appointments for each client
        for client_id in client_ids:
            try:
                shifts = wellsky.search_appointments(
                    client_id=client_id,
                    month_no=month_no,
                    limit=100
                )
                all_appointments.extend(shifts)
            except Exception as e:
                logger.debug(f"No appointments for client {client_id} in {month_no}: {e}")
                continue

    logger.info(f"Found {len(all_appointments)} total appointments")

    # Write to database
    cur = db.cursor()
    cur.execute("DELETE FROM cached_appointments")  # Clear old data

    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    utc = ZoneInfo("UTC")
    mt = ZoneInfo("America/Denver")

    inserted = 0
    failed = 0
    for shift in all_appointments:
        patient_id = shift.client_id
        practitioner_id = shift.caregiver_id
        status = shift.status.value if hasattr(shift.status, 'value') else str(shift.status)

        # Compute proper start/end datetimes, handling overnight shifts and UTC→Mountain conversion
        sched_start = None
        sched_end = None
        if shift.date and shift.start_time:
            start_time = _dt.strptime(shift.start_time, "%H:%M").time()
            sched_start_utc = _dt.combine(shift.date, start_time)
            try:
                sched_start = sched_start_utc.replace(tzinfo=utc).astimezone(mt).replace(tzinfo=None)
            except:
                sched_start = sched_start_utc - timedelta(hours=7)

        if shift.date and shift.end_time:
            end_time = _dt.strptime(shift.end_time, "%H:%M").time()
            end_date = shift.date
            if shift.start_time and end_time <= start_time:
                end_date = shift.date + timedelta(days=1)
            sched_end_utc = _dt.combine(end_date, end_time)
            try:
                sched_end = sched_end_utc.replace(tzinfo=utc).astimezone(mt).replace(tzinfo=None)
            except:
                sched_end = sched_end_utc - timedelta(hours=7)

        # Use composite ID: {wellsky_id}_{date} — recurring shifts share the same
        # WellSky appointment ID across months, so we need the date to keep each
        # occurrence unique (otherwise March overwrites February via ON CONFLICT)
        date_str = str(shift.date) if shift.date else "nodate"
        appt_id = f"{shift.id}_{date_str}"

        try:
            cur.execute("""
                INSERT INTO cached_appointments
                    (id, patient_id, practitioner_id, scheduled_start, scheduled_end,
                     status, service_type, wellsky_data, synced_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    patient_id = EXCLUDED.patient_id,
                    practitioner_id = EXCLUDED.practitioner_id,
                    scheduled_start = EXCLUDED.scheduled_start,
                    scheduled_end = EXCLUDED.scheduled_end,
                    status = EXCLUDED.status,
                    service_type = EXCLUDED.service_type,
                    wellsky_data = EXCLUDED.wellsky_data,
                    synced_at = NOW(),
                    updated_at = NOW()
            """, (appt_id, patient_id, practitioner_id, sched_start, sched_end,
                  status, "", Json(shift.to_dict() if hasattr(shift, 'to_dict') else {})))
            inserted += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to insert appointment {appt_id} (client={patient_id}): {e}")
            db.rollback()

    db.commit()
    logger.info(f"Synced {inserted} appointments ({failed} failed, {len(all_appointments)} fetched)")
    return inserted


def log_sync(db, sync_type, count, status):
    """Log sync operation."""
    try:
        cur = db.cursor()
        cur.execute("""INSERT INTO wellsky_sync_log
            (sync_type,started_at,completed_at,records_synced,records_added,records_updated,status)
            VALUES (%s,NOW(),NOW(),%s,%s,0,%s)""", (sync_type, count, count, status))
        db.commit()
    except Exception as e:
        logger.error(f"Log error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("WellSky Full Sync Starting")
    logger.info("=" * 60)

    token = get_token()
    if not token:
        logger.error("Failed to get API token")
        sys.exit(1)

    try:
        db = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)

    try:
        # 1. Sync active clients
        patient_ids = sync_patients(token, db)
        log_sync(db, "patients", len(patient_ids), "completed")

        # 2. Sync active caregivers
        sync_practitioners(token, db)
        log_sync(db, "practitioners", 0, "completed")

        # 3. Sync family contacts for active clients
        sync_related_persons(token, db, patient_ids)
        log_sync(db, "related_persons", 0, "completed")

        # 4. Sync appointments/shifts (last 7 days + next 14 days)
        appt_count = sync_appointments(token, db)
        log_sync(db, "appointments", appt_count, "completed")

        # Summary
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM cached_patients WHERE is_active=true")
        clients = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cached_practitioners WHERE is_active=true")
        caregivers = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cached_related_persons WHERE is_active=true")
        contacts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cached_appointments")
        appointments = cur.fetchone()[0]

        logger.info("=" * 60)
        logger.info(f"Sync complete: {clients} clients, {caregivers} caregivers, {contacts} family contacts, {appointments} appointments")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        log_sync(db, "full", 0, "failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
