# Next Agent Handoff (Dec 26, 2025) — Receipt & Expense Fixes

> **Important**: Also read `AGENTS.md` for the master project guide covering architecture, deployment, and user preferences.

---

## Latest Session (Dec 23-26, 2025) — Receipt Upload Fixes

### Problems Solved

1. **Starbucks receipt uploaded but not appearing in Expense Tracker**
   - Root cause: Receipts were using `datetime.utcnow()` instead of the AI-parsed date
   - Root cause: Receipts assigned to current user, not Jacob/Maryssa
   - Root cause: Google Drive images misclassified as business cards

2. **Local receipt uploads created broken links**
   - Clicking receipt redirected to dashboard instead of showing receipt
   - Root cause: `receipt_url` stored filename only, not full URL

3. **App crashes after deploy**
   - IndentationError in `mailchimp_service.py` line 221
   - Fixed bad indentation in exception handler

### Code Changes

#### `app.py`
- Added `_parse_receipt_date()` helper function to extract date from AI parser results
- Modified `/upload` endpoint to use `_parse_receipt_date()` for Expense.date
- Modified `/upload` endpoint to use `_choose_expense_owner()` for Expense.user_email
- Modified `/upload-url` endpoint to prioritize receipt parsing for all images
- Added logging for receipt parsing flow

#### `frontend/src/activity-tracker/ExpenseTracker.tsx`
- Only render clickable `<a>` tags for URLs starting with `http://` or `https://`
- Local file uploads display description text only (no broken link)

#### `mailchimp_service.py`
- Fixed IndentationError on line 221 in exception handler

### Verification
1. Upload a receipt image via Google Drive link
2. Assign to Jacob or Maryssa
3. Check Expense Tracker — receipt should appear with correct vendor, amount, date
4. Click receipt link — should open the Google Drive file

---

## Previous Session (Dec 20, 2025) — Full CRM Features Update

This note documents the fixes made in this repo to address:

- MyWay visits uploaded via **Google Drive link** parsing successfully but **not appearing** in Activity → Visits.
- Companies **left-nav filters** not working.
- Company tiles **missing logos**.

## 1) MyWay visits “success” but not saved (root cause + fix)

### Symptom
User uploads a MyWay route PDF via the Google Drive link uploader (`/upload-url`). UI shows success and preview visits, but Activity → Visits (which calls `GET /api/visits`) does not show the new date (e.g. Dec 10).

### Root cause
`ActivityLogger.log_activity()` in `activity_logger.py` was **managing transactions**:

- It called `db.commit()` on success
- On error, it called `db.rollback()`

When called from within the MyWay saving loop in `app.py`, any exception inside activity logging could rollback the **outer transaction** holding newly inserted `Visit` rows. This matches the “possible cause” listed in `CRITICAL_BUGS_FOUND.md`.

### Fix
Changes were made so activity logging can be called in a **non-blocking** way without impacting the parent transaction:

- `activity_logger.py`
  - `log_activity(..., commit: bool = True)` now supports `commit=False`
  - With `commit=False`, it uses `db.begin_nested()` (SAVEPOINT) + `db.flush()` so failures never rollback the outer transaction.
  - Wrapper methods (`log_visit`, `log_email`, etc.) now accept and forward `commit=...`.
- `app.py`
  - MyWay visit save paths now call:
    - `ActivityLogger.log_visit(..., commit=False)` in both `POST /upload` and `POST /upload-url`

### Verification
After deploy:

1. Upload a MyWay PDF via Google Drive link (Activity → Uploads → “Import from Google Drive”).
2. Confirm the request `POST /upload-url` returns `"type": "myway_route"` and `saved_count > 0`.
3. Refresh Activity → Visits. The list calls `GET /api/visits` and should show the new date at the top.

> Note: older uploads that “succeeded” but were rolled back will need to be re-uploaded.

## 2) Companies filters not working

### Frontend behavior
`frontend/src/components/atomic-crm/companies/CompanyListFilter.tsx` toggles filters like:

- `size: "<County>"` (Service Area / County)
- `sector: "<Referral Type>"`
- `sales_id: identity.id` (Account Manager)

The main Companies list uses the default data provider (`frontend/src/components/atomic-crm/providers/supabase/dataProvider.ts`) which calls:

- `GET /admin/companies?...` with a `Range` header for pagination

### Fix
`GET /admin/companies` in `app.py` was updated to be more tolerant of filter formats:

- Accept `size` and `sector` as `List[str]` (so repeated query params work)
- Also accept a JSON `filter=` param (some RA providers send that form)
- Keep existing `q` search behavior.
- Added a small **county heuristic map** so filters like **"El Paso"** match common city/zip substrings
  (e.g. `Colorado Springs`, `Fountain`, `809xx`) because addresses rarely contain the literal county name.

### Verification
1. Open Companies page.
2. Toggle a county and a referral type.
3. Confirm Network shows requests to `/admin/companies?...` and the list changes.

## 3) Company logos missing on tiles

### Likely cause
Third-party logo URLs (Clearbit, external avatar services) are frequently blocked by Brave/adblockers, causing `<img>` to fail and the UI to fall back to the first letter.

### Fix
Generate a same-origin SVG “logo”:

- Added endpoint: `GET /api/company-logos/{company_id}.svg`
  - Returns an SVG circle with deterministic background and company initials
  - Cached for 1 day via `Cache-Control`
- Updated `_to_company_dict()` to always set:
  - `logo.src = "/api/company-logos/{id}.svg"`

This makes logos render reliably regardless of adblockers.

### Verification
1. Open Companies page.
2. Confirm each tile avatar loads from `/api/company-logos/<id>.svg` in Network.

## Deployment notes

- Backend runs via `Procfile`: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- OCR dependencies via `Aptfile` (Tesseract + HEIC libs).

## Operational checklist

After merging/deploying:

- Re-upload the missing MyWay PDF(s) (e.g. Dec 10) once.
- Confirm `GET /api/visits` returns the new records.
- Confirm Companies filters and logo rendering in Brave.

## 4) Google Drive receipt uploads not appearing in Expense Tracker

### Symptom
Uploading a receipt image via Google Drive link (`POST /upload-url`) returns “success” but the expense doesn’t show up in
Activity → Expenses (Jacob/Maryssa pay period widget).

### Root cause
`/upload-url` originally tried **business card OCR first** for image-like downloads and returned early if it produced a
contact-like payload. Receipts can be misclassified as business cards by OCR, so the receipt handler never ran.

### Fix
In `app.py` within `upload_from_url`:
- Determine owner/uploader first
- For image-like bytes, attempt **receipt OCR first** using `_try_image_receipt_to_expense`
- Only if not a receipt, attempt business card OCR

Receipt detection is content-based (OCR text heuristics), not filename-based.

### Optional OpenAI parsing
If `OPENAI_API_KEY` is set, receipt OCR now attempts:
- An OpenAI extraction from OCR text
- If that fails, an **OpenAI Vision** extraction directly from the image bytes

This dramatically reduces the “receipt misclassified as business card” failure mode.

### Assigning Drive uploads (receipts + MyWay) to Jacob/Maryssa
The Drive upload UI allows choosing **Assign Drive imports to: Jacob/Maryssa**, which sends `assign_to` to `/upload-url`.
Backend uses this assignment for:
- `Expense.user_email` (so it shows in the Expense pay-period widget)
- `Visit.user_email` and the MyWay-created `FinancialEntry.user_email` (so mileage reimbursement shows for the right person)

## Dashboard KPI note (Total Visits)

The Activity → Visits page uses `GET /api/visits` and shows new uploads immediately.
The Dashboard KPI "Total Visits" originally preferred Google Sheet totals (cached) and could lag behind DB writes.
`analytics.py` was updated to **prefer DB `Visit.count()`** for `total_visits` while still keeping the sheet value
as `total_visits_sheet` for reference.

The Activity Summary UI (`frontend/src/activity-tracker/Summary.tsx`) labels KPI cards as **(DB)** and displays
`kpi_source` + `last_updated` so it's always clear the sheet is legacy and the database is the source of truth.

## 5) Company Enrichment Pipeline (county, facility_type, website, logo)

### New DB Columns
Four new columns were added to `referral_sources` (ReferralSource model):

- `county VARCHAR(100)` — Colorado county name (e.g., "Denver", "El Paso", "Douglas")
- `facility_type_normalized VARCHAR(100)` — Normalized facility type (e.g., "skilled_nursing", "rehab_hospital", "assisted_living")
- `website VARCHAR(255)` — Company website URL
- `logo_url TEXT` — Clearbit logo URL (e.g., `https://logo.clearbit.com/domain.com`)

### Auto-migration
`ensure_referral_source_schema()` in `app.py` automatically adds these columns at startup if missing.

### Enrichment Endpoints
- `POST /admin/companies/{id}/enrich` — Enrich a single company using OpenAI (GPT-4o-mini) with Gemini fallback
- `POST /admin/companies/enrich-all?force=false` — Background bulk enrichment of all companies

### CLI Script
`scripts/enrich_companies.py` can be run on Heroku for one-time bulk enrichment:
```bash
heroku run python scripts/enrich_companies.py
```

### Logo Rendering
`GET /api/company-logos/{id}.svg` now:
1. Checks in-memory cache (24hr TTL)
2. Uses `logo_url` from DB if available
3. Tries Google favicon service if website is known
4. Falls back to domain favicon
5. Renders SVG with initials if no logo found

### Filter Improvements
County filter (`size` param in UI) now:
1. **First** matches on the enriched `county` column (exact case-insensitive match)
2. **Then** falls back to heuristic address substring matching

This makes county filtering much more accurate after enrichment.

### Current State (Dec 13, 2025)
- 50/53 companies enriched with county + website + logo_url
- 3 companies (IDs 19, 38, 49) need enrichment (run `/admin/companies/{id}/enrich` or bulk enrich)
- Company tiles now display real logos via the SVG proxy endpoint

### Frontend Changes
- `Company` type updated with `county`, `facility_type_normalized`, `logo_url` fields
- `SERVICE_AREAS` now includes "Arapahoe" county

## 6) Company ↔ Contact Linking

### Problem
Company tiles showed "No Contacts" even though a contact person was listed directly on the company record.

### Root Cause
The frontend's `contacts_summary` view expects contacts in a separate `contacts` table with `company_id` foreign key. 
The original import put all data into `referral_sources` (companies), not into `contacts`.

### Solution
1. Added `first_name`, `last_name`, `company_id`, `last_seen` columns to `Contact` model
2. Created `GET /admin/contacts_summary` endpoint (emulates Supabase view for React Admin)
3. Created `POST /admin/companies/sync-contacts` endpoint to sync ReferralSource data → Contact records
4. Updated `_to_company_dict` to include `nb_contacts` count

### Current State (Dec 13, 2025)
- 53 Contact records created, each linked to their ReferralSource via `company_id`
- Company show page now displays "1 Contact" tab with proper contact list
- Clicking on a contact navigates to the contact detail page

### Data Model Fix (Dec 13, 2025)
Duplicate company records have been merged. Previously, each contact was stored as a separate company record
(e.g., 4 "Encompass" records for 4 different contacts). Now properly consolidated:
- **20 duplicate company records merged**
- All contacts re-linked to their canonical (oldest) company record
- Example: "Encompass Health Rehabilitation Hospital of Littleton" → 1 company with 6 contacts


## 7) Bulk Business Card Folder Processing

### Feature
Users can now paste a **Google Drive folder URL** containing business card images, and all cards are processed at once using AI vision (OpenAI GPT-4o-mini with Gemini fallback).

### How It Works
1. User pastes a folder URL (e.g., `https://drive.google.com/drive/folders/1aGO...`) in the Upload panel
2. Backend lists all image files in the folder via Drive API
3. Each image is downloaded and sent to OpenAI Vision for structured extraction
4. AI returns JSON with: first_name, last_name, company, email, phone, title, address, website, notes
5. For each card:
   - If company exists → link contact to existing company
   - If company not found → create new company
   - If contact email exists → update existing contact
   - If new contact → create new Contact record
   - Activity is logged for each card scan

### Endpoints
- `POST /bulk-business-cards` — Accepts `folder_url` and optional `assign_to`

### Frontend
- New purple-themed section in UploadPanel.tsx
- Shows progress, chips with summary (contacts created/updated, companies created/linked), and error details

### Google Drive Requirements
**IMPORTANT**: The Drive folder must be shared with the service account email:
- Find the service account email in `GOOGLE_SERVICE_ACCOUNT_KEY` (usually `..@...iam.gserviceaccount.com`)
- Share the folder with that email (Viewer access is sufficient)

### AI Providers
1. **OpenAI Vision** (primary) — Uses `gpt-4o-mini` with vision capability
2. **Gemini** (fallback) — Uses `gemini-2.0-flash` if OpenAI fails

### Rate Limiting
A 300ms delay is added between processing each card to avoid API rate limits.

### Example Usage
```
Folder: https://drive.google.com/drive/folders/1aGO6vxe50yA-1UcanPDEVlIFrXOMRYK4?usp=sharing
Result: Processed 50 of 50 business cards
- 48 Contacts Created
- 2 Contacts Updated  
- 35 Companies Created
- 15 Companies Linked
```


## 8) Duplicate Company Merge Script

### Problem
Original data import created one `ReferralSource` (company) record per contact person, resulting in duplicate 
company entries (e.g., 4 "Encompass" records for 4 different contacts).

### Solution
`scripts/merge_duplicate_companies.py` finds and merges duplicate companies:
1. Groups `ReferralSource` records by `organization` name
2. Keeps the oldest record as the "canonical" company
3. Extracts contact info from duplicates and creates/updates `Contact` records
4. Re-links any existing contacts to the canonical company
5. Deletes duplicate company records

### Usage
```bash
heroku run python3 scripts/merge_duplicate_companies.py --app careassist-tracker
```

### Results (Dec 13, 2025)
- 14 organizations had duplicates
- 20 duplicate company records merged
- 4 new contact records created
- All contacts properly linked to canonical companies

### Example
Before: 4 separate "Encompass Health Rehabilitation Hospital of Littleton" company tiles
After: 1 company with 6 linked contacts (Susan Perucchini, Valarie Bates, Melissa Jacobs, Irene Ntui, etc.)


## 9) Contact Tasks Feature (Dec 20, 2025)

### New Endpoints
```
GET    /admin/contact-tasks?contact_id=123  # List tasks for a contact
POST   /admin/contact-tasks                 # Create task
PUT    /admin/contact-tasks/{id}            # Update task
DELETE /admin/contact-tasks/{id}            # Delete task
```

### Model
`ContactTask` in `models.py`:
- `contact_id` — Foreign key to Contact
- `title` — Task description
- `due_date` — Optional due date
- `status` — "pending" or "done"
- `assigned_to` — Team member email
- `created_by` — Creator email

### Frontend
`ContactTasksList.tsx` component displays tasks in the Contact detail page Tasks tab.

### Cascade Delete
When a contact is deleted via `DELETE /admin/contacts/{id}`, all related `ContactTask` records are automatically deleted first.


## 10) Contact Detail Page Overhaul (Dec 20, 2025)

### New Tabs
Contact detail page now has 3 tabs (like Company page):
1. **Activity** — Activity log for this contact
2. **Deals** — Deals linked to this contact
3. **Tasks** — Tasks for this contact with add/complete functionality

### Files Changed
- `ContactShow.tsx` — Complete rewrite with tabs
- `ContactTasksList.tsx` — New component
- `ActivityLog.tsx` — Now accepts `contactId` parameter


## 11) Contact Merge Feature (Dec 20, 2025)

### Endpoint
```
POST /api/contacts/merge
Body: { "primary_id": 123, "duplicate_ids": [124, 125] }
```

### Behavior
1. Transfers all deals, tasks, activity logs from duplicates to primary
2. Enriches primary with missing data (email, phone, address) from duplicates
3. Deletes duplicate contact records

### Frontend
- `BulkMergeButton.tsx` — Shows when 2+ contacts selected in list
- Radio group to select which contact to keep as primary
- Displays contact details to help user decide


## 12) Contact Search (Dec 20, 2025)

### Backend
`GET /admin/contacts?q=searchterm` now searches across:
- `name`, `first_name`, `last_name`
- `email`, `phone`, `address`
- `company`, `title`

### Frontend
`ContactListFilter.tsx` has debounced search input that filters in real-time.


## 13) Contact Status Colors (Dec 20, 2025)

### Status Values
- `hot` — Red badge (🔴)
- `warm` — Yellow badge (🟡)
- `cold` — Blue badge (🔵)

### Display
Status badges with colors appear on:
- Contact list (via Status component dot)
- Contact detail page header
- Contact aside panel


## 14) Model Fixes (Dec 20, 2025)

### Contact.to_dict()
Now includes:
- `first_name`
- `last_name`
- `company_id`

### create_contact() / update_contact()
Both endpoints now:
- Accept `first_name`, `last_name`, `company_id`
- Auto-generate `name` from first/last if not provided
- Default status to "cold" for new contacts


## Current Database Stats (Dec 20, 2025)

| Entity | Count |
|--------|-------|
| Contacts | 543 |
| Companies | 86 |
| Deals | 13 |
| Visits | 858 |
| Contact Tasks | ~3 |


## Repository Sync Status

All three locations are synchronized:
- ✅ Local (macOS)
- ✅ GitHub (github.com/shulmeister/sales-dashboard)
- ✅ Heroku (careassist-tracker-0fcf2cecdb22.herokuapp.com)

Last deployment: Dec 20, 2025 — AI Document Parser (Gemini)


## Quick Start for New Developer

```bash
# Clone
git clone https://github.com/shulmeister/sales-dashboard.git
cd sales-dashboard

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && npm run build && cd ..

# Set environment variables (see .env.example)
export DATABASE_URL=...
export OPENAI_API_KEY=...
# etc.

# Run
uvicorn app:app --reload
```

Open http://localhost:8000 — Frontend is served from `frontend/dist/`


## 15) AI Document Parsing Revolution (Dec 20, 2025)

### The Problem
OCR (Tesseract, EasyOCR, RapidOCR) was producing garbage results for:
- MyWay route PDFs (0 visits parsed, misidentified as business cards)
- Receipts (wrong amounts, misclassified)
- Complex layouts

User feedback: "gemini absolutely nails a myway...just saying"

### The Solution
Created `ai_document_parser.py` — a new module that uses **Gemini REST API** for all document parsing:

```python
from ai_document_parser import ai_parser

# MyWay PDF
result = ai_parser.parse_myway_pdf(content, filename)
# Returns: visits[], mileage, date

# Receipt
result = ai_parser.parse_receipt(content, filename)
# Returns: vendor, amount, date, category, items[]

# Business Card  
result = ai_parser.parse_business_card(content, filename)
# Returns: first_name, last_name, company, email, phone, etc.
```

### API Format
Uses Gemini's REST API directly (like existing business card code):
```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
```

Supports models: `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`

### Code Changes
- `app.py` — `/upload` and `/upload-url` endpoints now route to `ai_parser` first
- Removed all OCR garbage fallbacks (no more `_force_ocr_any_bytes_to_contact`)
- Clean flow: PDF → AI parser, Image → AI parser, No fallbacks

### Test Results (Dec 20, 2025)
**MyWay PDF**: `myway_2025-12-11_route_9.pdf`
- ✅ 16 visits extracted
- ✅ 42.18 miles captured
- ✅ Date: 2025-12-11
- ✅ Cities: Denver, Arvada, Westminster, Federal Heights, Thornton
- ✅ Business names: "Thornton Care Center", "HCA North Denver Orthopedic Specialists"

**Receipt**: `FAMILY DOLLAR.pdf`
- ✅ Vendor: FAMILY DOLLAR
- ✅ Amount: $34.94
- ✅ Date: 2025-12-01
- ✅ Items: Kellogg's variety packs, Motts fruit snacks, Christmas treat bags

### Duplicate Prevention for MyWay Visits
Both `/upload` and `/upload-url` now check for existing visits before saving:
- Matches on date + stop number + normalized business name
- Skips duplicates and reports them in response
- Prevents re-uploading same PDF from creating duplicate entries


## 16) Code Cleanup (Dec 20, 2025)

Removed ~400 lines of dead OCR fallback code from `app.py`:
- Deleted `_try_image_ocr_to_contact` fallback path
- Deleted `_force_ocr_any_bytes_to_contact` function calls
- Deleted duplicate PDF/image handling blocks
- Deleted expense OCR fallbacks

New flow is clean:
1. Detect file type (PDF or image)
2. Route to appropriate AI parser method
3. Return result or error (no garbage fallbacks)


## 17) Brevo Integration (Dec 20, 2025)

### Why Brevo?
- **Unlimited contacts on free plan** — Mailchimp charges per contact (painful above 500)
- **Modern REST API** with Python support
- **Built-in CRM features** — Deals, Tasks, Companies (potential future integration)
- **Native Mailchimp migration** — Can import directly from Mailchimp with tags

### What Was Done
1. **Created `brevo_service.py`** — Full service class with:
   - `test_connection()` — Verify API key
   - `get_all_contacts()` — Pull contacts from Brevo
   - `add_contact()` — Push single contact
   - `bulk_import_contacts()` — Batch import
   - `create_list()` / `get_lists()` — List management
   - `create_attributes()` — Custom fields (CONTACT_TYPE, STATUS, SOURCE, etc.)

2. **Added API Endpoints**:
   - `GET /api/brevo/test` — Test connection
   - `POST /api/sync-brevo-contacts` — Pull contacts from Brevo to Dashboard

3. **Updated Dashboard UI** (`templates/dashboard.html`):
   - Button: "Sync from Mailchimp" → "Sync from Brevo" (green #0b996e)
   - Function: `syncMailchimpContacts()` → `syncBrevoContacts()`
   - All Mailchimp status messages updated to Brevo

4. **Environment Variable**:
   - `BREVO_API_KEY` — Set in Heroku config

### Brevo API Key
Stored in Heroku config var: `BREVO_API_KEY`

### Brevo Has CRM Features
Brevo includes Deals and Tasks — could potentially integrate:
- `/crm/deals` — Sync deals between Dashboard and Brevo
- `/crm/tasks` — Sync tasks
- `/crm/companies` — Sync companies

This is future work if the user wants a unified CRM experience.

### Migration Notes
- User should use **Brevo's native Mailchimp integration** (App Store → Mailchimp) to import contacts with tags intact
- Then click "Sync from Brevo" in Dashboard to pull them in
- Mailchimp can then be cancelled to save money


## Known Issues / Future Work

1. **Activity Logs** — Currently showing 0 entries; may need review of logging calls
2. **Phone Calls KPI** — Shows 0; RingCentral integration may need data population
3. **Google Sheets** — Integration disabled (Maryssa left); code still present but disabled
4. **Brevo CRM Sync** — Could sync Deals/Tasks/Companies with Brevo's CRM module


