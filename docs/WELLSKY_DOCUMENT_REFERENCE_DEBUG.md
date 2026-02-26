# WellSky DocumentReference POST — Debug Status

**Last Updated:** 2026-02-26
**Status:** PARTIALLY RESOLVED — Structure fixed, WellSky-side 500 persists
**Priority:** Vendor Ticket Open

---

## Summary

WellSky support confirmed (Feb 26) that the following fields **do not exist** in their DocumentReference API:
- `description` (top-level)
- `date` (top-level)
- `type.coding`
- `status`
- `subject`

All code has been updated to remove these invalid fields. The correct structure is documented below.

The WellSky-side 500 Internal Server Error persists after the structure fix. This is a vendor-side issue (likely `client_credentials` lacking write permission for DocumentReferences). A ticket has been sent to WellSky support.

---

## Correct DocumentReference Structure (Confirmed by WellSky)

```json
{
  "resourceType": "DocumentReference",
  "type": {
    "text": "General"
  },
  "content": {
    "attachment": {
      "contentType": "application/pdf",
      "data": "<base64-encoded-content>",
      "title": "filename.pdf"
    }
  },
  "context": {
    "related": [
      {"ref": "Patient/647616"}
    ]
  },
  "meta": {
    "tag": [
      {"code": "agencyId", "display": "4505"}
    ]
  }
}
```

**Key rules:**
- `type` must only have `text` field — no `coding`, no other fields
- `content` must be an **Object** (NOT an Array — array causes immediate 500)
- `context.related` uses `Patient/{id}` for clients, `Practitioner/{id}` for caregivers
- `title` is **required** in attachment
- `agencyId` tag is **required** in meta

---

## API Validation Behavior (Object Format)

When using the correct Object format, WellSky validates fields and returns 422 for missing ones:

| Missing Field | Response |
|---|---|
| `type.text` | `'text' in 'type' is required.` |
| `context` | `'context' is required.` |
| `content.attachment.data` | `'data', 'title' and 'contentType' are mandatory.` |
| `meta.tag.agencyId` | `'agencyId' is required.` |

**Note:** Getting 422 is GOOD — it means the request is reaching WellSky's validation layer. The 500 occurs after validation passes.

---

## URL Casing

| URL | Result |
|-----|--------|
| `/v1/documentReferences/` (camelCase) | 500 (reaches WellSky processing, server-side error) |
| `/v1/documentreferences/` (lowercase) | 403 (auth rejected — wrong route) |

**Always use camelCase: `/v1/documentReferences/`**

---

## Code Locations (All Fixed as of Feb 26)

| File | Fix Applied |
|------|-------------|
| `careassist-unified/services/wellsky_service.py` | Removed `description`, `date`, `coding` from `create_document_reference()` |
| `careassist-unified/services/fax_service.py` | Removed `description=` from all calls |
| `careassist-unified/portal/portal_app.py` | Removed `description=` from assessment upload |
| `client-portal/backend/services/wellsky_client_adapter.py` | Removed `status`, `subject`, `description`, `coding`; fixed URL to camelCase |
| `employee-portal/backend/services/wellsky_adapter.py` | Removed `description`, `coding` from type |

---

## What Each Flow Uploads

| Flow | Trigger | Document Type | Patient/Practitioner | Status |
|------|---------|---------------|---------------------|--------|
| **Client Portal** (6 signed docs) | Packet complete → `sync_client_to_wellsky()` | C01–C06 PDFs | `Patient/{ws_id}` | 500 (WellSky) |
| **Employee Portal** (onboarding docs) | Hired → `upload_documents_to_wellsky()` | Signed onboarding PDFs | `Practitioner/{ws_id}` | 500 (WellSky) |
| **Fax Service** | Inbound fax filed to patient | Facesheet / Referral / Authorization | `Patient/{ws_id}` | 500 (WellSky) |
| **Assessment Upload** | Portal assessment sync | Client Assessment PDF | `Patient/{ws_id}` | 500 (WellSky) |
| **Clinical Notes** (Gigi) | SMS doc, call notes | text/plain notes | `Patient/{ws_id}` | 500 (WellSky) |

---

## Flows That Do NOT Use DocumentReference (By Design)

| Flow | What WellSky Gets |
|------|-------------------|
| **Monitoring Visits** | Care Alert (TaskLog) + Google Drive PDF |
| **Incident Reports** | Care Alert (TaskLog) + Admin Task + Google Drive PDF |

These flows deliberately avoid DocumentReference and use Care Alerts instead, which work reliably.

---

## Current Workaround

All document-generating flows fail gracefully:
- Log a warning (not an error that crashes the flow)
- Continue with the rest of the operation (Care Alert, DB update, etc.)
- **Google Drive** is always the primary storage for PDFs — always succeeds

---

## WellSky Support Ticket

**Subject:** API 500 Error on POST /v1/documentReferences/ for Agency 4505

**Status:** Open (sent Feb 26, 2026)

**Key question asked:** Does the `client_credentials` grant type have write permission for DocumentReference uploads for Agency 4505?

**Reproduction payload (all fields valid, still 500):**
```python
import requests, base64
url = "https://connect.clearcareonline.com/v1/documentReferences/"
headers = {"Authorization": "Bearer <TOKEN>", "Content-Type": "application/fhir+json"}
payload = {
  "resourceType": "DocumentReference",
  "type": {"text": "General"},
  "content": {
    "attachment": {
      "contentType": "application/pdf",
      "data": "<base64-pdf>",
      "title": "test.pdf"
    }
  },
  "context": {"related": [{"ref": "Patient/647616"}]},
  "meta": {"tag": [{"code": "agencyId", "display": "4505"}]}
}
response = requests.post(url, json=payload, headers=headers)
# Returns: 500 Internal Server Error (HTML body)
```
