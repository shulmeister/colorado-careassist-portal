# WellSky API Compatibility Matrix (Agency 4505)

**Last Updated:** January 31, 2026
**Status:** ⚠️ READ BEFORE CODING. Write operations are restricted.

---

## 🟢 WHAT WORKS (100% RELIABLE)

| Action | Host | Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| **Auth** | `connect.clearcareonline.com` | `/oauth/accesstoken` | Use `client_credentials`. Returns `BearerToken`. |
| **Search Caregivers** | `connect.clearcareonline.com` | `/v1/Practitioner` | Use FHIR params. Filters like `active=true` work. |
| **Search Clients** | `connect.clearcareonline.com` | `/v1/Patient` | Use FHIR params. |
| **Get Schedules** | `connect.clearcareonline.com` | `/v1/Appointment` | Requires `practitioner` or `patient` ID. |

---

## 🔴 WHAT IS BROKEN / 404 (DO NOT USE)

| Action | Host | Endpoint | Result |
| :--- | :--- | :--- | :--- |
| **Legacy Auth** | `api.clearcareonline.com` | `/connect/token` | **404 Page Not Found** |
| **Legacy Token** | `api.clearcareonline.com` | `/api/v1/token` | **404 Page Not Found** |
| **Legacy Notes** | `api.clearcareonline.com` | `/api/v1/agencies/{id}/prospects/{id}/notes/` | **404 Page Not Found** |
| **Legacy Tasks** | `api.clearcareonline.com` | `/api/v1/agencies/{id}/tasks/` | **404 Page Not Found** |

---

## ⚠️ THE "FINICKY" ZONE (WRITE OPERATIONS)

| Action | Endpoint | Error | Root Cause |
| :--- | :--- | :--- | :--- |
| **Add Note** | `/v1/prospects/{id}/notes` | `403 Forbidden` | Likely permission-scoped to human users only. |
| **Create Task** | `/v1/adminTasks/` | `422 Unprocessable` | Fails even with `theDate`. Backend expects strict GraphQL-style DateTime formats. |

---

## 🛠️ THE WORKAROUND STRATEGY

Since WellSky is currently rejecting **WRITE** operations (Notes/Tasks) via the Connect API for this key:

1. **Retain Data Locally:** All "Documentation" requests (like Israt/Cynthia's updates) must be logged to the **Portal Database (`portal.db`)** first.
2. **Read-Only from WellSky:** Use WellSky as the source of truth for IDs and Schedules, but do not rely on it for real-time documentation until the key scopes are elevated.
3. **Admin Tasks:** If an urgent task is needed, Gigi should post to the **RingCentral Team Chat** instead of attempting a WellSky API write that will likely fail.
