# WellSky Home Connect API - Complete Reference

**Version:** February 2026
**Base URL:** `https://connect.clearcareonline.com/v1/`
**Authentication:** OAuth 2.0 Bearer Token
**Rate Limit:** 100 requests per second

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Appointment API](#appointment-api)
4. [Practitioner API](#practitioner-api)
5. [Patient API](#patient-api)
6. [Encounter API](#encounter-api)
7. [ClockIn/ClockOut API](#clockin-clockout-api)
8. [Task API](#task-api)
9. [DocumentReference API](#documentreference-api)
10. [Subscription API](#subscription-api)
11. [ProfileTags API](#profiletags-api)
12. [RelatedPerson API](#relatedperson-api)
13. [Additional Resources](#additional-resources)

---

## Getting Started

### Overview

WellSky Personal Care Home Connect API is an enterprise-class API system that enables home care agencies to integrate with insurance companies, hospitals, and other healthcare systems.

### Key Features

- **FHIR-based standards** - Built on HL7 FHIR specifications
- **Real-time operations** - Designed for CRUD operations on individual records
- **Webhook subscriptions** - Real-time event notifications
- **Comprehensive resources** - Patient, Practitioner, Appointment, Encounter, and more

### Implementation Rules

1. **Trailing Slash Required:** All GET commands must end with `/`
   - ✅ `GET v1/practitioners/`
   - ❌ `GET v1/practitioners`
   - **Exception:** Specific ID lookups: `GET v1/practitioners/123/?agencyId=456`

2. **Base URL:** Always use `https://connect.clearcareonline.com/v1/`

3. **Phone Numbers:** Must be exactly 10 digits (no country code, first digit not 0 or 1)
   - Work phones support optional extension: `x` followed by 1-6 digits

4. **Date Formats:**
   - Date: `YYYY-MM-DD` (e.g., `2026-01-29`)
   - DateTime: `YYYY-MM-DDTHH:MM:SS` (e.g., `2026-01-29T14:30:00`)
   - Search dates: `YYYYMMDD` (e.g., `20260129`)

5. **Character Validation:**
   - UTF-8 characters supported including: `! @ # $ % ^ & * ( ) [ ] - + = < > ? . / | '`
   - Escaped whitespace: `\b \f \n \r \t`
   - No Unicode below character point 32 (except tab, CR, LF)

---

## Authentication

### OAuth 2.0 Access Token

**Endpoint:** `POST /oauth/accesstoken`

**Usage:**
```http
Authorization: Bearer {access_token}
```
*(Note: Do not use `BearerToken` - use standard `Bearer`)*

---

## Endpoint Standards

1.  **Plurality:**
    *   `v1/practitioners/` (Plural)
    *   `v1/patients/` (Plural)
    *   `v1/appointment/` (**Singular**)

2.  **Trailing Slashes:**
    *   REQUIRED for lists: `v1/patients/`
    *   REQUIRED for details: `v1/patients/123/`

---

## Appointment API

Appointments represent scheduled shifts/visits between caregivers and clients.

### Get Appointment by ID

**Endpoint:** `GET /v1/appointment/{id}/`

**Response:**
```json
{
  "caregiver": {
    "id": "3306118"
  },
  "client": {
    "id": "2870130"
  },
  "start": "2020-06-03T14:00:00+00:00",
  "end": "2020-06-04T04:00:00+00:00",
  "id": "109131818",
  "position": {
    "latitude": 43.0124964,
    "longitude": -82.4606573
  },
  "resourceType": "Appointment",
  "scheduledItems": [
    {
      "id": "12345",
      "name": "Meal Preparation"
    }
  ],
  "status": "SCHEDULED",
  "tasks": [
    {
      "id": "67890",
      "description": "Assist with breakfast",
      "status": "NOT_COMPLETE"
    }
  ]
}
```

### Search Appointments

**Endpoint:** `GET /v1/appointment/` or `POST /v1/appointment/_search/`

**Query Parameters (GET):**
- `startDate` - Format: YYYYMMDD (e.g., `20260129`)
- `additionalDays` - Number of days after start (1-6)
- `weekNo` - Week of year: YYYYWW (e.g., `202605`)
- `monthNo` - Month of year: YYYYMM (e.g., `202601`)
- `caregiverId` - Caregiver/practitioner ID
- `clientId` - Client/patient ID
- `_count` - Records per page (1-100, default: 20)
- `_page` - Page number (default: 0)

**Required:** Either `caregiverId` OR `clientId` AND one of `startDate`, `weekNo`, or `monthNo`

**Examples:**

```http
# Get all shifts for client on specific date
GET /v1/appointment/?clientId=92169&startDate=20260129

# Get caregiver's shifts for next 3 days
GET /v1/appointment/?caregiverId=948043&startDate=20260129&additionalDays=3

# Get all shifts for a week
GET /v1/appointment/?clientId=92169&weekNo=202605

# Get all shifts for a month
GET /v1/appointment/?clientId=92169&monthNo=202601
```

**POST Body (Search):**
```json
{
  "startDate": "20260129",
  "additionalDays": "2",
  "caregiverId": "3306118"
}
```

**Response:**
```json
{
  "resourceType": "Bundle",
  "id": "searchParams",
  "type": "searchset",
  "totalRecords": 15,
  "entry": [
    {
      "caregiver": {"id": "3306118"},
      "client": {"id": "2870130"},
      "start": "2026-01-29T14:00:00+00:00",
      "end": "2026-01-29T18:00:00+00:00",
      "status": "SCHEDULED"
    }
  ]
}
```

### Create Appointment

**Endpoint:** `POST /v1/appointment/`

**Request:**
```json
{
  "resourceType": "Appointment",
  "client": {"id": "2870130"},
  "caregiver": {"id": "3456789"},
  "start": "2026-02-05T08:00:00",
  "end": "2026-02-05T12:00:00",
  "status": "SCHEDULED",
  "scheduledItems": [
    {"id": "123", "name": "Meal Preparation"}
  ],
  "position": {
    "latitude": 39.7392,
    "longitude": -104.9903
  }
}
```

**Response:**
```json
{
  "resourceType": "Appointment",
  "id": "109131900"
}
```

**Status Values:**
- `SCHEDULED` - Upcoming shift
- `COMPLETED` - Finished shift
- `CANCELLED` - Cancelled shift

### Update Appointment

**Endpoint:** `PUT /v1/appointment/{id}/`

**Request:** Same structure as Create (full resource replacement).

### Delete Appointment

**Endpoint:** `DELETE /v1/appointment/{id}/`

Permanently removes the scheduled shift. Use with caution.

**Notes:**
- All dates returned in UTC timezone
- Recurring shifts share the same ID as the original shift
- "Nearest" occurrence is selected for recurring shifts

---

## Practitioner API

Practitioners are caregivers (hired) or applicants (not hired).

### Create Practitioner

**Endpoint:** `POST /v1/practitioners/`

**Request:**
```json
{
  "resourceType": "Practitioner",
  "active": true,
  "name": [
    {
      "use": "official",
      "family": "Lopez",
      "given": ["Maria", "Elena"]
    }
  ],
  "telecom": [
    {
      "system": "phone",
      "value": "3035551234",
      "use": "mobile"
    },
    {
      "system": "email",
      "value": "maria.lopez@example.com"
    }
  ],
  "address": [
    {
      "use": "home",
      "line": ["123 Main St"],
      "city": "Denver",
      "state": "CO",
      "postalCode": "80202"
    }
  ],
  "gender": "female",
  "birthDate": "1990-01-05",
  "ssn": "123-45-6789",
  "communication": [
    {
      "coding": [
        {
          "code": "en-us",
          "display": "English"
        }
      ]
    }
  ],
  "meta": {
    "tag": [
      {
        "code": "isHired",
        "display": "true"
      },
      {
        "code": "agencyId",
        "display": "1669"
      },
      {
        "code": "status",
        "display": "100"
      },
      {
        "code": "locationId",
        "display": "123"
      },
      {
        "code": "profileTags",
        "display": "45,67,89"
      }
    ]
  }
}
```

**Response:**
```json
{
  "resourceType": "Practitioner",
  "id": "3456789"
}
```

### Search Practitioners

**Endpoint:** `GET /v1/practitioners/` or `POST /v1/practitioners/_search/`

**Search Parameters:**
- `first_name` / `last_name` / `family` - Name search
- `address`, `city`, `state`, `country` - Location
- `gender` - Gender
- `active` - Active status (true/false)
- `agency_id` - Agency ID
- `home_phone`, `mobile_phone`, `work_phone`, `fax_phone` - Contact
- `is_hired` - Hired status (true/false)
- `external_id` - External/payroll ID
- `tags` - Profile tag IDs (comma-separated: "1,2,3")
- `created` / `updated` - Timestamps (supports lt, gt, le, ge, eq)

**Examples:**

```http
# Find active hired caregivers in Denver
GET /v1/practitioners/?active=true&is_hired=true&city=Denver

# Find caregivers with specific skills
GET /v1/practitioners/?tags=45,67&is_hired=true

# Find by name
GET /v1/practitioners/?first_name=Maria&last_name=Lopez
```

**POST Search:**
```json
{
  "active": "true",
  "is_hired": "true",
  "city": "Denver",
  "tags": "45,67,89"
}
```

**Response:**
```json
{
  "resourceType": "Bundle",
  "id": "searchParams",
  "type": "searchset",
  "totalRecords": 23,
  "entry": [
    {
      "resourceType": "Practitioner",
      "id": "3456789",
      "active": true,
      "name": [{"family": "Lopez", "given": ["Maria"]}],
      "telecom": [...],
      "address": [...],
      "meta": {
        "tag": [
          {"code": "isHired", "display": "true"},
          {"code": "profileTags", "display": "45,67,89"}
        ]
      }
    }
  ]
}
```

### Get Practitioner by ID

**Endpoint:** `GET /v1/practitioners/{id}/`

### Update Practitioner

**Endpoint:** `PUT /v1/practitioners/{id}/`

**Request:** Same structure as Create

### Delete Practitioner

**Endpoint:** `DELETE /v1/practitioners/{id}/`

### Practitioner Status Codes

| Status | ID | Description |
|--------|----|-----------|
| New Applicant | 10 | Initial application |
| Passed Phone Screen | 15 | Phone interview complete |
| Interview Scheduled | 18 | In-person interview scheduled |
| Interview Completed | 20 | Interview done |
| Conditional Offer Given | 25 | Conditional offer extended |
| Passed Skills Screening | 30 | Skills test passed |
| Passed Background Check | 40 | Background check clear |
| Passed Reference Check | 50 | References verified |
| Offer of Hiring Given | 60 | Final offer extended |
| Paperwork Received | 70 | Employment paperwork complete |
| Completed Orientation | 80 | Training/orientation done |
| Not Hired | 90 | Application rejected |
| **Hired** | **100** | **Active caregiver** |
| Application Completed | 110 | Application submitted |

### Deactivation Reasons

- Leave of Absence
- Suspension
- Terminated - Quit
- Terminated - Insufficient Work Available
- Terminated - for Cause
- Inactive
- Other - See Activity Log
- Disability or Worker's Comp

---

## Patient API

Patients represent clients, prospects, referral sources, or client contacts.

### Create Patient

**Endpoint:** `POST /v1/patients/`

**Request:**
```json
{
  "resourceType": "Patient",
  "active": true,
  "name": [
    {
      "use": "official",
      "family": "Johnson",
      "given": ["Margaret", "Ann"]
    }
  ],
  "telecom": [
    {
      "system": "phone",
      "value": "3035559876",
      "use": "home"
    },
    {
      "system": "phone",
      "value": "3035554321",
      "use": "mobile"
    }
  ],
  "address": [
    {
      "use": "home",
      "line": ["456 Oak Ave"],
      "city": "Colorado Springs",
      "state": "CO",
      "postalCode": "80903"
    }
  ],
  "gender": "female",
  "birthDate": "1945-03-15",
  "maritalStatus": [
    {
      "coding": [
        {
          "code": "W",
          "display": "Widowed"
        }
      ]
    }
  ],
  "communication": [
    {
      "coding": [
        {
          "code": "en-us",
          "display": "English"
        }
      ]
    }
  ],
  "meta": {
    "tag": [
      {
        "code": "isClient",
        "display": "true"
      },
      {
        "code": "agencyId",
        "display": "1669"
      },
      {
        "code": "status",
        "display": "80"
      },
      {
        "code": "locationId",
        "display": "123"
      }
    ]
  }
}
```

**Response:**
```json
{
  "resourceType": "Patient",
  "id": "2870130"
}
```

### Search Patients

**Endpoint:** `GET /v1/patients/` or `POST /v1/patients/_search/`

**Search Parameters:**
- `first_name` / `last_name` / `family` - Name
- `address`, `city`, `state`, `country` - Location
- `gender` - Gender
- `active` - Active status
- `agency_id` - Agency ID
- `home_phone`, `mobile_phone`, `work_phone` - Contact
- `external_id` - External ID
- `community_id` / `community_name` - Community
- `tags` - Profile tags (comma-separated)
- `created` / `updated` - Timestamps

**Examples:**

```http
# Find client by phone number
GET /v1/patients/?mobile_phone=3035551234

# Find clients in community
GET /v1/patients/?community_id=456

# Find by name
POST /v1/patients/_search/
{
  "family": "Johnson",
  "given": "Margaret"
}
```

### Get Patient by ID

**Endpoint:** `GET /v1/patients/{id}/`

Returns full FHIR Patient resource including name, contact, address, and meta tags.

### Update Patient

**Endpoint:** `PUT /v1/patients/{id}/`

**Request:** Same FHIR Patient structure as Create. All fields are optional -- only provided fields are updated.

```json
{
  "resourceType": "Patient",
  "name": [{"use": "official", "family": "Johnson", "given": ["Margaret"]}],
  "telecom": [{"system": "phone", "value": "3035559999", "use": "mobile"}],
  "address": [{"use": "home", "city": "Boulder", "state": "CO"}],
  "meta": {
    "tag": [
      {"code": "agencyId", "display": "1669"},
      {"code": "status", "display": "80"}
    ]
  }
}
```

### Delete Patient

**Endpoint:** `DELETE /v1/patients/{id}/`

Permanently removes the patient record from WellSky. Use with caution.

### Client Status Codes

| Status | ID | Description |
|--------|----|-----------|
| New Lead | 1 | Initial inquiry |
| Initial Phone Call | 10 | First contact made |
| Assessment Scheduled | 20 | Assessment appointment set |
| Assessment Performed | 30 | Assessment completed |
| Wants to Meet Candidates | 40 | Ready for caregiver intro |
| Needs Contract | 50 | Contract preparation |
| Expecting Client Signature | 60 | Awaiting signed contract |
| Ready to Schedule Care | 70 | Contract signed, ready to start |
| **Care Started** | **80** | **Active client** |
| Closed - Lost | 90 | Did not proceed |
| Closed - Won | 100 | Successfully onboarded |

### Marital Status Codes

| Value | Code | Display |
|-------|------|---------|
| Married | M | Married |
| Single | S | Never Married |
| Widowed | W | Widowed |
| Separated | L | Legally Separated |
| Domestic Partnership | T | Domestic Partner |
| Divorced | D | Divorced |
| Cohabitating | U | Unmarried |
| Unknown | UNK | Unknown |

---

## Encounter API

Encounters represent completed care visits (care logs).

### Create Encounter

**Endpoint:** `POST /v1/encounter/`

**Request:**
```json
{
  "resourceType": "Encounter",
  "agencyId": "1669",
  "status": "COMPLETE",
  "patientId": "2870130",
  "practitionerId": "3456789",
  "startDateTime": "2026-01-29T14:00:00",
  "endDateTime": "2026-01-29T18:00:00",
  "billRateMethod": "Hourly",
  "billRateId": "12345",
  "payRateMethod": "Hourly",
  "payRateId": "67890"
}
```

**Rate Methods:**
- `Hourly` - Standard hourly rate
- `notBillable` / `notPayable` - No charge/payment
- `perVisit` - Flat visit rate
- `liveIn` - Live-in care rate

**Response:**
```json
{
  "resourceType": "Encounter",
  "id": "128777063"
}
```

### Search Encounters

**Endpoint:** `POST /v1/encounter/_search/`

**Request:**
```json
{
  "startDate": "20260101",
  "endDate": "20260131",
  "clientId": "2870130",
  "caregiverId": "3456789"
}
```

**Query Parameters:**
- `_count` - Records per page (default: 30)
- `_page` - Page number (default: 1)
- `_sort` - Sort by startDate or endDate (prefix `-` for descending)

### Get Encounter by ID

**Endpoint:** `GET /v1/encounter/{id}/`

**Response:**
```json
{
  "resourceType": "Encounter",
  "id": "128777063",
  "status": "COMPLETE",
  "subject": {
    "reference": "Patient/2870130",
    "display": "Margaret Johnson"
  },
  "participant": {
    "Individual": [
      {
        "reference": "Practitioner/3456789",
        "display": "Maria Lopez"
      }
    ]
  },
  "appointment": {
    "reference": "Appointment/44172786"
  },
  "period": {
    "start": "2026-01-29T14:00:00",
    "end": "2026-01-29T18:00:00"
  },
  "rates": {
    "payRate": [
      {
        "id": "67890",
        "amount": 18.50,
        "method": "Hourly"
      }
    ],
    "billRate": [
      {
        "id": "12345",
        "amount": 28.00,
        "method": "Hourly"
      }
    ]
  }
}
```

### Update Encounter

**Endpoint:** `PUT /v1/encounter/{id}/`

**Request:** Same structure as Create

### Delete Encounter

**Endpoint:** `DELETE /v1/encounter/{id}/`

---

## ClockIn ClockOut API

### Clock In

**Endpoint:** `POST /v1/encounter/{appointment_id}/clockin/`

**Request:**
```json
{
  "resourceType": "Encounter",
  "period": {
    "start": "2026-01-29T14:05:00"
  },
  "position": {
    "latitude": 38.8951,
    "longitude": -77.0364
  }
}
```

**Response:**
```json
{
  "clockedOut": false,
  "id": 128777063,
  "period": {
    "start": "2026-01-29T14:05:00",
    "end": null
  },
  "resourceType": "Encounter",
  "status": "IN_PROGRESS",
  "success": true
}
```

**Notes:**
- Idempotent - returns existing encounter if already clocked in
- Uses `appointment_id` to create encounter
- Returns `encounter_id` (carelog ID)

### Clock Out

**Endpoint:** `PUT /v1/encounter/{carelog_id}/clockout/`

**Request:**
```json
{
  "resourceType": "Encounter",
  "period": {
    "end": "2026-01-29T18:02:00"
  },
  "position": {
    "latitude": 38.8951,
    "longitude": -77.0364
  },
  "generalComment": "Client doing well today. Enjoyed lunch.",
  "mileage": 12.5,
  "mileageDescription": "Round trip to client home"
}
```

**Response:**
```json
{
  "success": true
}
```

**Notes:**
- Idempotent - no update if already clocked out
- Uses `carelog_id` (encounter ID from clock-in)
- Optional: comments, mileage

---

## Task API

### Get Task Logs for Encounter

**Endpoint:** `GET /v1/encounter/{encounter_id}/tasklog/`

**Response:**
```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 3,
  "entry": [
    {
      "id": "12345",
      "title": "Meal Preparation",
      "description": "Prepare breakfast and lunch",
      "status": "COMPLETE",
      "comment": "Client enjoyed scrambled eggs",
      "recorded": "2026-01-29T15:30:00"
    },
    {
      "id": "12346",
      "title": "Light Housekeeping",
      "description": "Vacuum living room",
      "status": "NOT_COMPLETE",
      "comment": "Client requested skip today",
      "recorded": "2026-01-29T16:00:00"
    }
  ]
}
```

### Update Shift Task

**Endpoint:** `PUT /v1/encounter/{encounter_id}/task/{task_id}/`

**Request:**
```json
{
  "resourceType": "Task",
  "status": "COMPLETE",
  "comment": "Task completed successfully"
}
```

**Status Values:**
- `COMPLETE` - Task done
- `NOT_COMPLETE` - Task not done (comment required)

**Response:**
```json
{
  "success": true
}
```

### Create Task Log

**Endpoint:** `POST /v1/encounter/{encounter_id}/tasklog/`

**Request:**
```json
{
  "resourceType": "TaskLog",
  "title": "Medication Reminder",
  "description": "Reminded client to take afternoon medication",
  "status": "COMPLETE",
  "comment": "Client took medication at 2pm",
  "message_for_next_caregiver": true,
  "show_in_family_room": false,
  "recorded": "2026-01-29T14:00:00"
}
```

**Response:**
```json
{
  "success": true,
  "taskLogId": 12118
}
```

### Update Task Log

**Endpoint:** `PUT /v1/encounter/{encounter_id}/tasklog/{tasklog_id}/`

**Request:** Same structure as Create (all fields optional)

---

## DocumentReference API

Manage documents attached to patient/client profiles (care plans, assessments, clinical notes, images, etc.).

### Create DocumentReference

**Endpoint:** `POST /v1/documentreference/`

**Request:**
```json
{
  "resourceType": "DocumentReference",
  "subject": {"reference": "Patient/2870130"},
  "type": {
    "coding": [{"code": "clinical-note", "display": "clinical-note"}]
  },
  "description": "Weekly care assessment notes",
  "date": "2026-02-04T12:00:00Z",
  "content": [
    {
      "attachment": {
        "contentType": "application/pdf",
        "data": "<base64-encoded-content>"
      }
    }
  ]
}
```

**Response:**
```json
{
  "resourceType": "DocumentReference",
  "id": "98765"
}
```

### Get DocumentReference by ID

**Endpoint:** `GET /v1/documentreference/{id}/`

Returns document metadata and base64-encoded content.

### Search DocumentReferences

**Endpoint:** `POST /v1/documentreference/_search/`

**Request:**
```json
{
  "subject": "Patient/2870130",
  "type": "clinical-note",
  "date": "ge2026-01-01"
}
```

**Query Parameters:**
- `_count` - Records per page (default: 30)
- `_page` - Page number (default: 1)

### Update DocumentReference

**Endpoint:** `PUT /v1/documentreference/{id}/`

**Request:** Same structure as Create (all fields optional)

### Delete DocumentReference

**Endpoint:** `DELETE /v1/documentreference/{id}/`

---

## Subscription API

Subscribe to real-time webhook notifications for events.

### Create Subscription

**Endpoint:** `POST /v1/subscriptions/`

**Request:**
```json
{
  "resourceType": "Subscription",
  "status": "active",
  "criteria": "encounter.clockout.changed",
  "reason": "Monitor shift completions for Gigi AI",
  "channel": {
    "type": "rest-hook",
    "endpoint": "https://gigi.coloradocareassist.com/webhooks/wellsky",
    "payload": "application/fhir+json",
    "header": [
      "Authorization: Bearer your_webhook_secret"
    ]
  },
  "meta": {
    "tag": [
      {
        "code": "agencyId",
        "display": "1669"
      }
    ]
  }
}
```

**Response:**
```json
{
  "resourceType": "Subscription",
  "id": 789
}
```

### Available Subscription Criteria

| Resource Type | Criteria | Description |
|---------------|----------|-------------|
| AdminTask | `admintask.created` | New task created |
| AdminTask | `admintask.changed` | Task updated |
| AdminTask | `admintask.status.changed` | Task status changed |
| AdminTask | `admintask.status.complete` | Task completed |
| AgencyAdmin | `agency_admin.created` | New administrator |
| AgencyAdmin | `agency_admin.deactivated.changed` | Admin deactivated/reactivated |
| Encounter | `encounter.clockout.changed` | Shift clocked out |
| Patient | `patient.created` | New patient/client |
| Patient | `patient.name.changed` | Name updated |
| Patient | `patient.address.changed` | Address updated |
| Patient | `patient.telecom.changed` | Contact info updated |
| Patient | `patient.deactivated.changed` | Patient deactivated/reactivated |
| Patient | `patient.dateofdeath.changed` | Date of death updated |
| Patient | `prospect.status.changed` | Lead status changed |
| Practitioner | `practitioner.created` | New caregiver/applicant |
| Practitioner | `practitioner.name.changed` | Name updated |
| Practitioner | `practitioner.address.changed` | Address updated |
| Practitioner | `practitioner.telecom.changed` | Contact updated |
| Practitioner | `practitioner.deactivated.changed` | Deactivated/reactivated |
| Practitioner | `applicant.status.changed` | Hiring status changed |
| ReferralSource | `referralsources.created` | New referral source |
| ReferralSource | `referralsources.changed` | Referral source updated |

### Webhook Payload

When an event occurs, WellSky sends:

```json
{
  "resourceType": "Patient",
  "id": 2870130
}
```

Your webhook endpoint should:
1. Return `200 OK` immediately
2. Use the ID to fetch full resource details via GET

### Search Subscriptions

**Endpoint:** `GET /v1/subscriptions/`

**Query Parameters:**
- `status` - Filter by status
- `criteria` - Filter by event type
- `contact_email` - Filter by subscriber email

### Get Subscription by ID

**Endpoint:** `GET /v1/subscriptions/{id}/`

### Update Subscription

**Endpoint:** `PUT /v1/subscriptions/{id}/`

### Delete Subscription

**Endpoint:** `DELETE /v1/subscriptions/{id}/`

---

## ProfileTags API

Manage skill/certification tags that can be assigned to practitioners. Tags are referenced by comma-separated IDs in the `profileTags` meta tag on Practitioner resources.

### Create Profile Tag

**Endpoint:** `POST /v1/profileTags/`

**Request:**
```json
{
  "name": "CNA",
  "description": "Certified Nursing Assistant",
  "type": "certification"
}
```

**Response:**
```json
{
  "id": "45",
  "name": "CNA"
}
```

**Tag Types:** `skill`, `certification`, `language`, or custom values.

### Get Profile Tag by ID

**Endpoint:** `GET /v1/profileTags/{id}/`

### Search Profile Tags

**Endpoint:** `GET /v1/profileTags/`

**Query Parameters:**
- `name` - Filter by tag name
- `type` - Filter by tag type
- `_count` - Records per page (default: 100)
- `_page` - Page number (default: 1)

**Examples:**
```http
# List all tags
GET /v1/profileTags/

# Find by name
GET /v1/profileTags/?name=CNA

# Find by type
GET /v1/profileTags/?type=certification
```

### Update Profile Tag

**Endpoint:** `PUT /v1/profileTags/{id}/`

**Request:** All fields optional -- only provided fields are updated.
```json
{
  "name": "CNA - Certified Nursing Assistant",
  "description": "Updated description"
}
```

### Delete Profile Tag

**Endpoint:** `DELETE /v1/profileTags/{id}/`

---

## RelatedPerson API

Family members, emergency contacts, and other related persons for patients.

### Get Related Persons for Patient

**Endpoint:** `GET /v1/relatedperson/{patient_id}/`

Returns FHIR Bundle with all related persons for the patient.

**Response:**
```json
{
  "entry": [
    {
      "resource": {
        "resourceType": "RelatedPerson",
        "id": "12345",
        "name": [{"given": ["John"], "family": "Smith"}],
        "relationship": {"coding": [{"code": "SON", "display": "Son"}]},
        "telecom": [
          {"system": "phone", "value": "7195551234", "use": "mobile"},
          {"system": "email", "value": "john@example.com"}
        ],
        "address": [{"city": "Colorado Springs", "state": "CO"}],
        "emergencyContact": true,
        "primaryContact": true,
        "payer": false,
        "poa": false
      }
    }
  ]
}
```

### Create Related Person

**Endpoint:** `POST /v1/relatedperson/`

**Request:**
```json
{
  "resourceType": "RelatedPerson",
  "patient": {"reference": "Patient/2870130"},
  "name": [{"given": ["John"], "family": "Smith"}],
  "relationship": {"coding": [{"code": "SON"}]},
  "telecom": [
    {"system": "phone", "value": "7195551234", "use": "mobile"}
  ],
  "emergencyContact": true,
  "primaryContact": true,
  "payer": false,
  "poa": false
}
```

### Search Related Persons

**Endpoint:** `POST /v1/relatedperson/_search/`

Search across all patients. Supports `patient`, `name`, `phone` filters.

### Update Related Person

**Endpoint:** `PUT /v1/relatedperson/{contact_id}/`

Same structure as Create (all fields optional).

### Delete Related Person

**Endpoint:** `DELETE /v1/relatedperson/{patient_id}/contacts/{contact_id}/`

### Relationship Codes

- `FTH` - Father
- `MTH` - Mother
- `SPS` - Spouse
- `BRO` / `SIS` - Sibling
- `SON` / `DAU` - Child
- `DOCTOR` - Physician
- `SOCIAL_WORKER` - Social Worker
- `NURSE` - Nurse
- `FRND` - Friend
- `NBOR` - Neighbor
- And more...

---

## Additional Resources

### Location API

**Endpoint:** `GET /v1/locations/` or `POST /v1/locations/_search/`

Search office locations by name, address, phone, etc.

### Organization API

**Endpoint:** `GET /v1/organizations/` or `POST /v1/organizations/_search/`

Search agencies by name, subdomain, address, etc.

### ReferralSource API

**Endpoint:** `POST /v1/referralsource/`

Create marketing referral sources.

**Get:** `GET /v1/referralsource/{id}/`
**Update:** `PUT /v1/referralsource/{id}/`

**Standard Referral Types:**
- Hospital (ID: 14)
- Physician (ID: 18)
- Assisted Living (ID: 5)
- Home Healthcare (ID: 12)
- Word of Mouth (ID: 22)
- Internet (ID: 16)
- And more...

---

## Common Patterns

### Error Handling

**400 Bad Request:**
```json
{
  "error": "Invalid phone number format. Must be 10 digits."
}
```

**403 Forbidden:**
```json
{
  "error": "Access denied. Invalid agencyId."
}
```

**404 Not Found:**
```json
{
  "error": "Resource not found"
}
```

**422 Unprocessable Entity:**
```json
{
  "error": "Validation failed: birthDate is required"
}
```

### Pagination

All search endpoints support pagination:

```http
GET /v1/practitioners/?_count=50&_page=2
```

Response includes:
```json
{
  "totalRecords": 235,
  "entry": [...]
}
```

### Sorting

Use `_sort` parameter:

```http
# Ascending
GET /v1/patients/?_sort=last_name

# Descending (prefix with -)
GET /v1/patients/?_sort=-created

# Multiple fields
GET /v1/practitioners/?_sort=last_name,-created
```

### Date Searches

Supports comparison operators:

```http
# Greater than
GET /v1/practitioners/?created=gt2026-01-01

# Less than or equal
GET /v1/patients/?updated=le2026-01-29T14:00:00

# Equal to
GET /v1/practitioners/?created=eq2026-01-15
```

**Operators:**
- `lt` - Less than
- `gt` - Greater than
- `le` - Less than or equal
- `ge` - Greater than or equal
- `eq` - Equal to

### Timezone Handling

- All datetimes stored in UTC
- Input accepts timezone offset: `2026-01-29T14:00:00-07:00`
- Without timezone, assumed UTC: `2026-01-29T14:00:00`
- Agency timezone used for display in WellSky UI

---

## Rate Limits

- **100 requests per second** maximum
- No limit on concurrent requests
- Designed for real-time operations, NOT batch processing

**Best Practices:**
- Cache frequently accessed data (organizations, locations)
- Use webhooks instead of polling
- Store resource IDs to minimize search calls
- Batch-friendly: Use search with pagination instead of individual GETs

---

## Support

**WellSky Personal Care Support:**
- Email: personalcaresupport@wellsky.com
- Documentation: https://www.clearcareonline.com/fhir/

**API Status:**
- Production Base: `https://connect.clearcareonline.com/v1/`
- Current Version: January 2026

---

## Changelog Highlights

**January 14, 2026:**
- Fixed Condition endpoint boolean fields
- Fixed DocumentReference pagination errors
- Fixed GraphQL shift ID errors

**November 6, 2025:**
- Added `agency_admin.created` subscription
- Fixed Condition field types

**August 28, 2025:**
- Fixed Encounter rate display
- Improved Practitioner contact validation

**May 9, 2025:**
- Added Condition POST/PUT for assessment fields

**April 15, 2025:**
- Launched ProfileTags endpoint

---

## Quick Reference

### Most Common Endpoints for Gigi

```bash
# Authentication
POST /oauth/accesstoken

# Find caregiver by name
POST /v1/practitioners/_search/
{"first_name": "Maria", "last_name": "Lopez"}

# Get caregiver's shifts today
GET /v1/appointment/?caregiverId=123&startDate=20260129

# Create a new shift
POST /v1/appointment/
{"client": {"id": "456"}, "caregiver": {"id": "123"}, "start": "...", "end": "..."}

# Find available caregivers
POST /v1/practitioners/_search/
{"active": "true", "is_hired": "true", "city": "Denver"}

# Find client by phone
POST /v1/patients/_search/
{"mobile_phone": "3035551234"}

# Update client info
PUT /v1/patients/{id}/
{"resourceType": "Patient", "telecom": [...]}

# Get shift history
POST /v1/encounter/_search/
{"clientId": "456", "startDate": "20260101", "endDate": "20260131"}

# Subscribe to events
POST /v1/subscriptions/
{"criteria": "encounter.clockout.changed", ...}

# Manage skill tags
POST /v1/profileTags/
{"name": "CNA", "type": "certification"}

# Get client's emergency contacts
GET /v1/relatedperson/{patient_id}/
```

---

**End of WellSky Home Connect API Reference**
