# WellSky API Compatibility Matrix (Agency 4505)

**Last Updated:** January 31, 2026
**Status:** ✅ Write operations NOW WORKING via Encounter/TaskLog pattern

---

## 🟢 WHAT WORKS (100% RELIABLE)

| Action | Host | Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| **Auth** | `connect.clearcareonline.com` | `/oauth/accesstoken` | Use `client_credentials`. Returns `BearerToken`. |
| **Search Caregivers** | `connect.clearcareonline.com` | `/v1/Practitioner` | Use FHIR params. Filters like `active=true` work. |
| **Search Clients** | `connect.clearcareonline.com` | `/v1/Patient` | Use FHIR params. |
| **Get Schedules** | `connect.clearcareonline.com` | `/v1/Appointment` | Requires `practitioner` or `patient` ID. |
| **Clock In** | `connect.clearcareonline.com` | `POST /v1/encounter/{appointment_id}/clockin/` | ✅ Creates encounter, returns `encounter_id` |
| **Clock Out** | `connect.clearcareonline.com` | `PUT /v1/encounter/{encounter_id}/clockout/` | ✅ Uses encounter_id from clock-in |
| **Add Shift Notes** | `connect.clearcareonline.com` | `POST /v1/encounter/{encounter_id}/tasklog/` | ✅ **THIS IS HOW TO DOCUMENT!** |

---

## ✅ THE WORKING DOCUMENTATION PATTERN

**Key Discovery:** TaskLog works on ENCOUNTER ID (not appointment ID). This is how Zingage adds "Shift Notes".

### Step 1: Get Appointment ID
```bash
GET /v1/appointment/?agencyId=4505&caregiverId={id}&startDate=YYYYMMDD
# Returns: appointment_id (e.g., "275350728")
```

### Step 2: Clock In (creates Encounter)
```bash
POST /v1/encounter/{appointment_id}/clockin/?agencyId=4505
{
  "resourceType": "Encounter",
  "period": { "start": "2026-01-31T18:00:00" },
  "position": { "latitude": 39.7392, "longitude": -104.9903 }
}
# Returns: encounter_id (e.g., "798693975")
```

### Step 3: Add Documentation (TaskLog)
```bash
POST /v1/encounter/{encounter_id}/tasklog/?agencyId=4505
{
  "resourceType": "TaskLog",
  "title": "Gigi AI - SMS Confirmation",
  "description": "Caregiver confirmed arrival via SMS. Documented by Gigi AI.",
  "status": "COMPLETE",
  "recorded": "2026-01-31T18:05:00Z",
  "show_in_family_room": false,
  "message_for_next_caregiver": false
}
# Returns: { "success": true, "taskLogId": "4124449533" }
```

**Result:** Shows up as "Shift Notes" in WellSky mobile app and dashboard!

---

## 🔴 WHAT IS BROKEN / 404 (DO NOT USE)

| Action | Host | Endpoint | Result |
| :--- | :--- | :--- | :--- |
| **Legacy Auth** | `api.clearcareonline.com` | `/connect/token` | **404 Page Not Found** |
| **Legacy Token** | `api.clearcareonline.com` | `/api/v1/token` | **404 Page Not Found** |
| **Legacy Notes** | `api.clearcareonline.com` | `/api/v1/agencies/{id}/prospects/{id}/notes/` | **404 Page Not Found** |
| **Legacy Tasks** | `api.clearcareonline.com` | `/api/v1/agencies/{id}/tasks/` | **404 Page Not Found** |

---

## ⚠️ STILL FINICKY (Use Workarounds)

| Action | Endpoint | Error | Workaround |
| :--- | :--- | :--- | :--- |
| **Prospect Notes** | `/v1/prospects/{id}/notes` | `403 Forbidden` | Use TaskLog on encounter instead |
| **Admin Tasks** | `/v1/adminTasks/` | `422 Unprocessable` | Use TaskLog or local DB + RingCentral chat |

---

## 🛠️ GIGI DOCUMENTATION STRATEGY

**For shift-related interactions (clock in/out, arrival confirmation):**
1. Use the Encounter/TaskLog pattern above ✅
2. This shows in WellSky as "Shift Notes"

**For non-shift interactions (general notes):**
1. Log to local database (`portal.db` → `gigi_documentation_log` table)
2. Post urgent items to RingCentral Team Chat
3. Sync to WellSky when encounter is available

**Local Database Backup:**
All documentation is ALWAYS logged locally first, ensuring 24/7/365 compliance trail even if WellSky API has issues.
