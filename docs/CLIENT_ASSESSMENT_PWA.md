# Client Assessment PWA

**Built:** February 23, 2026
**URL:** `https://portal.coloradocareassist.com/assessment`
**Purpose:** Offline-capable client intake form for field assessments on phone/iPad

---

## Overview

A Progressive Web App (PWA) that replaces paper client intake packets. Designed to be installed on a phone or iPad, used at client homes with or without internet, and auto-synced to the portal database when connectivity returns.

Single self-contained HTML file — zero dependencies, no build step.

## Documents (6 Tabs)

| Tab | Document | Contents |
|-----|----------|----------|
| 1: Assessment | C01 — Assessment Form | Contact info, client name, current situation, diagnosis, care goals, preferences, schedule, payment plan |
| 2: Client Info | C02 — Client Information | Demographics, emergency/care/payer contacts, payment method (ACH/card/check), signature |
| 3: Disclosure | C03 — Agency Disclosure | Responsibility tables (consumer/worker/agency), signatures |
| 4: Rights | C04 — Consumer Rights | 12 consumer rights, CDPHE complaint info, dual signatures |
| 5: Agreement | C05 — Service Agreement | Service terms, rates, HIPAA release, triple signatures |
| 6: Transport | C06 — Transportation Waiver | Transport authorization/decline, liability release, dual signatures |

## Key Features

### Signatures (Draw or Type)
- Each signature pad has a Draw/Type toggle
- Draw mode: finger/stylus drawing via Pointer Events API (works on all devices)
- Type mode: cursive text input, rendered onto canvas for storage as image
- 9 total signature pads across all documents

### Auto-Populate
Shared fields sync across documents to avoid re-entering data:
- Client name (C01) → C02, C03, C05, C06
- Client address (C01/C02) → C05
- Diagnosis (C01) → C02
- Referral (C01) → C02

### Auto-Save (Draft Recovery)
- Every keystroke saves the current form state to localStorage (debounced 500ms)
- If the app closes, crashes, or loses power, reopening restores exactly where you left off
- Draft key: `cca_draft` in localStorage
- Draft is cleared on explicit Save or Clear

### Auto-Sync
- On `online` event: syncs all pending assessments to the portal DB immediately
- After saving: auto-syncs if online
- Background: checks every 60 seconds for pending items
- On startup: syncs any pending items from previous sessions
- Manual sync also available via Saved tab

### PWA / Offline
- Installable as standalone app (Add to Home Screen)
- Service worker caches the form, manifest, and icons for full offline use
- Install banner auto-hides when already running as installed app
- Works completely offline — saves to localStorage, syncs when back online

## Files

| File | Purpose |
|------|---------|
| `static/offline-assessment.html` | The entire app (HTML + CSS + JS, self-contained) |
| `static/assessment-sw.js` | Service worker for offline caching |
| `static/assessment-manifest.json` | PWA manifest (standalone, dark theme) |
| `static/assessment-icon-192.svg` | App icon (192px) |
| `static/assessment-icon-512.svg` | App icon (512px) |

## Server-Side

### Route
```python
# portal/portal_app.py
@app.get("/assessment")
async def assessment_page():
    return FileResponse(os.path.join(_root_dir, "static", "offline-assessment.html"))
```

### Sync Endpoint
```
POST /api/client-assessments/sync
Content-Type: application/json
```
Receives assessment JSON from the app, upserts to PostgreSQL `client_assessments` table via `ON CONFLICT (local_id) DO UPDATE`.

### Database Table
```sql
CREATE TABLE client_assessments (
    id SERIAL PRIMARY KEY,
    local_id VARCHAR(100) NOT NULL UNIQUE,
    client_name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255),
    assessment_date DATE,
    taken_by VARCHAR(255),
    referral_source VARCHAR(255),
    form_data JSONB NOT NULL,
    signature_data TEXT,
    synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Data Safety

Data is protected at multiple layers:
1. **localStorage auto-save** — draft saved every 500ms, survives app close/crash
2. **localStorage assessments** — saved assessments persist in `cca_assessments_v2` until explicitly deleted
3. **PostgreSQL sync** — auto-synced to server DB the moment internet is available
4. **JSON export** — manual backup option from Saved tab
5. **Daily DB backup** — PostgreSQL dumped nightly to Google Drive
