# Complete Contacts Tab Integration Task

## Context
The sales dashboard (FastAPI backend + React Admin frontend) needs to show ALL prospects, referral sources, and clients in a unified "Contacts" tab, sorted by date with proper tags. Currently, contacts are stored in separate tables (leads, referral_sources) and the frontend uses Supabase. We need to migrate to a FastAPI REST endpoint and sync all data into the contacts table.

## Current State (What's Already Done)
1. ✅ Database schema extended: `models.py` Contact model now has:
   - `status` (String, nullable)
   - `contact_type` (String, nullable) - "prospect", "referral", "client"
   - `tags` (Text, nullable) - JSON-encoded list
   - `last_activity` (DateTime, nullable)
   - `account_manager` (String, nullable)
   - `source` (String, nullable)
2. ✅ Auto-migration helper: `app.py` has `ensure_contact_schema()` that adds missing columns on startup
3. ✅ Basic API exists: `/api/contacts` GET endpoint returns contacts
4. ✅ Data import script: `add_december_2025_leads.py` has all leads/referrals defined but doesn't sync to contacts table yet

## What Needs to Be Completed

### Task 1: Extend Contacts API (Backend)
**File**: `sales-dashboard/app.py`

Update the `/api/contacts` endpoint (around line 911) to:
- Return contacts sorted by `created_at DESC` (newest first) by default
- Include all new fields: `status`, `tags` (as array), `contact_type`, `last_activity`, `account_manager`, `source`
- Support filtering by `tags`, `status`, `contact_type` via query params
- Support sorting by `last_activity`, `created_at`, `name`

Add/update these endpoints:
- `GET /api/contacts` - List with filters/sorting
- `GET /api/contacts/{id}` - Get single contact
- `POST /api/contacts` - Create contact
- `PUT /api/contacts/{id}` - Update contact (include new fields)
- `DELETE /api/contacts/{id}` - Delete contact

**Important**: The `Contact.to_dict()` method in `models.py` already handles tags JSON parsing. Make sure the API uses it.

### Task 2: Sync Leads/Referrals to Contacts Table
**File**: `sales-dashboard/add_december_2025_leads.py`

Add a function that:
1. After creating/updating each Lead, also create/update a Contact entry with:
   - `name` = lead.contact_name or lead.name
   - `email` = lead.email
   - `phone` = lead.phone
   - `address` = lead.address or lead.city
   - `notes` = lead.notes
   - `contact_type` = "prospect"
   - `tags` = JSON array: `["Prospect"]`
   - `status` = "warm" (or derive from lead.priority: "high" -> "hot", "medium" -> "warm", "low" -> "cold")
   - `source` = lead.source
   - `last_activity` = lead.updated_at or lead.created_at
   - `created_at` = lead.created_at

2. After creating/updating each ReferralSource, also create/update a Contact entry with:
   - `name` = referral_source.name
   - `company` = referral_source.organization
   - `email` = referral_source.email
   - `phone` = referral_source.phone
   - `address` = referral_source.address
   - `notes` = referral_source.notes
   - `contact_type` = "referral"
   - `tags` = JSON array: `["Referral Source"]`
   - `status` = "warm" (or map from referral_source.status: "incoming" -> "cold", "ongoing" -> "warm", "active" -> "hot")
   - `source` = referral_source.source_type
   - `last_activity` = referral_source.updated_at or referral_source.created_at
   - `created_at` = referral_source.created_at

3. Use idempotent logic: check if contact exists by email+name, update if exists, create if not.

**Import the Contact model**: Add `Contact` to the imports at the top of `add_december_2025_leads.py`.

### Task 3: Update Frontend to Use FastAPI REST Instead of Supabase
**Files to modify**:
- `sales-dashboard/frontend/src/components/atomic-crm/providers/supabase/dataProvider.ts` OR create new REST provider
- `sales-dashboard/frontend/src/components/atomic-crm/root/CRM.tsx`

**Option A (Recommended)**: Create a simple REST data provider for contacts only
- Create `sales-dashboard/frontend/src/components/atomic-crm/providers/rest/contactsDataProvider.ts`
- Implement React Admin data provider interface:
  - `getList`: GET `/api/contacts?filter={...}&sort={...}&range=[0,24]`
  - `getOne`: GET `/api/contacts/{id}`
  - `create`: POST `/api/contacts`
  - `update`: PUT `/api/contacts/{id}`
  - `delete`: DELETE `/api/contacts/{id}`
- In `CRM.tsx`, conditionally use this provider for contacts resource only, keep Supabase for others

**Option B**: Extend existing Supabase provider to fallback to REST for contacts
- Modify `dataProvider.ts` to check resource name, if "contacts" use REST API, else use Supabase

**React Admin expects**:
- `getList` returns `{ data: Contact[], total: number }`
- Filter format: `{ tags: ["Prospect"], status: "warm" }` -> query string `?tags=Prospect&status=warm`
- Sort format: `{ field: "last_activity", order: "DESC" }` -> query string `?sort=last_activity&order=DESC`
- Range format: `[0, 24]` -> query string `?range=0,24` or headers `Range: contacts=0-24`

### Task 4: Update ContactList Component
**File**: `sales-dashboard/frontend/src/components/atomic-crm/contacts/ContactList.tsx`

Ensure it:
- Sorts by `last_activity` or `created_at` DESC by default (line 32 already has `sort={{ field: "last_seen", order: "DESC" }}` - may need to change to `last_activity`)
- Filter component supports tags (Prospect, Referral Source, Client), status (Cold/Warm/Hot), contact_type
- Displays tags, status, last_activity in the list view

## File Locations
- Backend API: `sales-dashboard/app.py` (lines ~911-920 for contacts endpoint)
- Models: `sales-dashboard/models.py` (Contact class starts at line 60)
- Import script: `sales-dashboard/add_december_2025_leads.py`
- Frontend data provider: `sales-dashboard/frontend/src/components/atomic-crm/providers/supabase/dataProvider.ts`
- Frontend CRM root: `sales-dashboard/frontend/src/components/atomic-crm/root/CRM.tsx`
- Frontend contacts list: `sales-dashboard/frontend/src/components/atomic-crm/contacts/ContactList.tsx`
- Frontend contacts resource: `sales-dashboard/frontend/src/components/atomic-crm/contacts/index.tsx`

## Expected Outcome
1. All leads from `add_december_2025_leads.py` appear in Contacts tab as "Prospect" tagged contacts
2. All referral sources appear in Contacts tab as "Referral Source" tagged contacts
3. Contacts tab shows: name, company, email, phone, tags, status, last_activity
4. Contacts sorted by date (newest first) by default
5. Filters work: can filter by tag (Prospect/Referral Source/Client), status, contact_type
6. No Supabase dependency for contacts (or graceful fallback)

## Testing Checklist
- [ ] Run `python add_december_2025_leads.py` - verify contacts created in DB
- [ ] Test `GET /api/contacts` - verify all fields returned
- [ ] Test `GET /api/contacts?tags=Prospect` - verify filtering works
- [ ] Test frontend Contacts tab - verify all contacts visible
- [ ] Test filters in frontend - verify tag/status filters work
- [ ] Verify sorting by date works
- [ ] Deploy to Heroku and test in production

## Deployment
After completing:
1. Commit all changes
2. Push to GitHub: `git push origin main`
3. Deploy to Heroku: `git push heroku main` (or auto-deploy if enabled)

## Notes
- The `Contact.to_dict()` method already handles tags as JSON. Make sure API responses use it.
- Keep idempotency: running the import script multiple times shouldn't create duplicates.
- The frontend uses React Admin v5 (`ra-core`). Data provider interface is standard.
- Database is PostgreSQL on Heroku, SQLite locally. Schema migration helper handles both.



