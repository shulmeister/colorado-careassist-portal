# WellSky DocumentReference POST — Debug Status

**Date:** 2026-02-23
**Status:** BLOCKED — Server Crash (500) on Valid Payload
**Priority:** High (Requires Vendor Support)

---

## Executive Summary

We have exhaustively tested the `POST /v1/documentReferences/` endpoint. The server implementation appears to be broken or misconfigured for this agency.

1.  **Format Requirement:** The server **REQUIRES** `content` to be a single **Object**, not an Array (contradicting standard FHIR and some documentation). Sending an Array causes an immediate 500 crash.
2.  **Validation Works:** When using the Object format, the server correctly validates missing fields, returning 422 for missing `type.text`, `context`, `data`, `title`, etc.
3.  **Crash on Success:** When a payload passes all validations (is perfectly formed), the server **Crashes with 500 Internal Server Error**.

This indicates the issue is **Server-Side**, likely a permission error during file storage or a bug in the backend code handling the file data.

---

## The Findings

### 1. Array vs Object Format
| Format | Payload | Result | Meaning |
|--------|---------|--------|---------|
| **Array** | `content: [{"attachment": ...}]` | **500 Internal Server Error** | Server cannot parse/handle array. |
| **Object** | `content: {"attachment": ...}` | **422 Unprocessable Entity** | Server accepts format, validates fields. |

### 2. Validation Checks (Object Format)
The server correctly identifies missing fields when using the Object format:

| Missing Field | Response (422) |
|---------------|----------------|
| `type.text` | `'text' in 'type' is required.` |
| `context` | `'context' is required.` |
| `content.attachment.data` | `'data', 'title' and 'contentType' are mandatory.` |
| `meta.tag.agencyId` | `'agencyId' is required.` |

### 3. The Crash
When all required fields are present and valid, the server crashes:

```json
{
  "resourceType": "DocumentReference",
  "type": {
    "text": "Clinical Note",
    "coding": [{"code": "clinical-note", "display": "clinical-note"}]
  },
  "content": {
    "attachment": {
      "contentType": "text/plain",
      "data": "VGVzdCBjb250ZW50",
      "title": "test.txt"
    }
  },
  "context": {
    "related": [{"ref": "Patient/8718473"}]
  },
  "meta": {
    "tag": [{"code": "agencyId", "display": "4505"}]
  }
}
```
**Result:** `500 Internal Server Error` (HTML Body)

---

## Action Plan: Contact WellSky Support

**Open a ticket with the following details:**

**Subject:** API 500 Error on POST /v1/documentReferences/ for Agency 4505

**Message:**
> We are encountering a persistent 500 Internal Server Error when creating DocumentReferences via the API.
>
> **Endpoint:** `POST https://connect.clearcareonline.com/v1/documentReferences/`
> **Agency ID:** 4505
> **Auth:** OAuth2 Client Credentials (Token generation works)
>
> **Symptoms:**
> 1. The API validates the request structure correctly (returns 422 if fields are missing).
> 2. When a valid payload is sent (satisfying all 422 checks), the server returns **500 Internal Server Error**.
>
> **Reproduction Payload (Python/Requests):**
> ```python
> import requests, base64
> 
> url = "https://connect.clearcareonline.com/v1/documentReferences/"
> headers = {"Authorization": "Bearer <TOKEN>", "Content-Type": "application/json"}
> payload = {
>   "resourceType": "DocumentReference",
>   "type": {
>     "text": "Clinical Note", 
>     "coding": [{"code": "clinical-note", "display": "clinical-note"}]
>   },
>   "content": {
>     "attachment": {
>       "contentType": "text/plain",
>       "data": "VGVzdCBjb250ZW50", 
>       "title": "test.txt"
>     }
>   },
>   "context": {
>     "related": [{"ref": "Patient/8718473"}]
>   },
>   "meta": {
>     "tag": [{"code": "agencyId", "display": "4505"}]
>   }
> }
> response = requests.post(url, json=payload, headers=headers)
> # Returns 500
> ```
>
> **Question:**
> Does the `client_credentials` grant type have permission to **write documents** for this agency?
> Is there a specific configuration required to enable DocumentReference uploads for our API client?

---

## Current Workaround

We are continuing to use **Google Drive Uploads** (working) until this API issue is resolved.
The code in `services/fax_service.py` is configured to attempt WellSky upload and fail gracefully (logging the error) while succeeding on Google Drive.
