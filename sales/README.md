# Colorado CareAssist Sales Dashboard & CRM

A comprehensive full-stack sales CRM and activity tracking application for Colorado CareAssist. Built with React Admin frontend and FastAPI backend.

**Live URLs**:
- Portal: https://portal.coloradocareassist.com/sales/
- Mac Mini: https://portal.coloradocareassist.com/sales/

**GitHub**: https://github.com/shulmeister/colorado-careassist-portal (sales dashboard is in `/sales` directory)

## Architecture

This sales dashboard is part of the **Colorado CareAssist Unified Portal**. The portal uses `unified_app.py` to mount multiple applications:

- `/` → Portal hub (main landing page)
- `/sales` → Sales Dashboard (this app)
- `/gigi` → Gigi AI voice assistant
- `/recruiting` → Recruiter dashboard
- `/marketing` → Marketing dashboard

Everything deploys together to the `careassist-unified` Mac Mini app.

## Features

### 📊 CRM Dashboard
- **Hot Contacts**: Quick view of high-priority contacts
- **Pipeline View**: Visual deal pipeline with drag-and-drop stages
- **Activity KPIs**: Real-time metrics for visits, contacts, companies, deals
- **Forecasting**: Revenue projections based on deal stages and probability
- **Latest Activity**: Real-time feed of all CRM activities including business card scans

### 👥 Contact Management
- Full CRUD for contacts with first/last name, email, phone, company
- **Status Tracking**: Hot (🔴), Warm (🟡), Cold (🔵) with color-coded badges
- **Search**: Full-text search across name, email, company, phone, address
- **Merge Duplicates**: Select multiple contacts and merge into one
- **Tags & Types**: Categorize contacts with custom tags and contact types
- **Tasks**: Create follow-up tasks assigned to team members with due dates

### 🏢 Company Management
- Track referral sources and partner companies
- Multi-location support (e.g., "PAM Health - Westminster")
- Associate contacts with companies
- View deals and activity per company
- Company-specific tasks

### 💰 Deal Pipeline
- Customizable deal stages (Lead → Qualified → Proposal → Negotiation → Won/Lost)
- Track deal amounts and probability
- Associate deals with contacts and companies
- Activity logging per deal
- **Relationship Graph**: Multi-contact deals with roles (Decision Maker, Champion, Blocker, etc.)
- **Time-in-Stage Tracking**: Automatic tracking of days in each stage with stale deal alerts (>30 days)
- **Stage History**: Full audit trail of all stage transitions with duration metrics

### 🤖 AI Enrichment (Gemini-Powered)
- **Company Enrichment**: Auto-populate industry, employee count, facility type
- **Contact Deduplication**: Detect duplicates by email, phone, or name+company
- **Smart Merge**: Merge contacts while preserving all relationships and activities
- **Interaction Summary**: AI-generated summaries of relationship history with sentiment analysis

### 📇 AI-Powered Business Card Scanning (Gemini)

**Auto-Scanner Workflow:**
The system automatically monitors Google Drive folders and imports business cards in real-time:

1. **Upload**: Drop business card photos (JPG, PNG, HEIC) into designated Google Drive folders:
   - `Business Cards/Jen Jeffers/` → Cards assigned to jen@coloradocareassist.com
   - `Business Cards/Jacob Stewart/` → Cards assigned to jacob@coloradocareassist.com
   - `Business Cards/Colorado Springs/` → Cards assigned to cosprings@coloradocareassist.com

2. **Auto-Processing**: Script runs every 5 minutes via cron job:
   ```bash
   */5 * * * * cd /path/to/sales && /path/to/venv/bin/python scripts/auto_scan_drive.py
   ```

3. **AI Extraction**: Gemini AI extracts:
   - Name, company, title
   - Email, phone
   - Address
   - LinkedIn profile

4. **Duplicate Prevention**:
   - Checks for existing contacts by email or phone
   - Updates existing contacts instead of creating duplicates
   - Logs all scans in activity timeline

5. **Dashboard Updates**:
   - New contacts appear immediately in dashboard
   - Shows in "Latest Activity" widget with scan timestamp
   - Contacts are filterable by account manager

**Manual Upload Options:**
- Upload from device camera/photos
- Paste Google Drive links
- Bulk import entire folders

**Features:**
- **No more OCR garbage** — Pure AI extraction via Gemini REST API
- Automatic duplicate detection for contacts and companies
- Activity logging for all scans (visible in Latest Activity feed)
- Support for HEIC, JPG, PNG formats

**Run Manual Scan:**
```bash
python scripts/auto_scan_drive.py
```

### 📄 AI Document Parsing (Gemini)
- **MyWay PDFs**: AI extracts visits, addresses, cities, mileage, dates
- **Receipts**: AI extracts vendor, amount, date, category, items
- Automatic duplicate prevention for contacts, companies, and visits

### 📈 Activity Tracking
- **Visits**: Log and track sales visits with MyWay PDF import (AI-parsed)
- **Expense Tracking**: Mileage reimbursement and expense management (AI-parsed)
- **Pay Period Navigator**: View expenses by payroll period
- **Activity Logs**: Full audit trail of all CRM actions including business card scans, calls, emails, visits
- **Duplicate Prevention**: MyWay visits checked for duplicates before saving

### 🔗 Integrations
- **Brevo** (formerly Sendinblue): Sync contacts for email marketing + webhook integration for automatic activity logging (delivered, opened, clicked events)
- **Google Drive**: Import files and folders directly + auto-monitoring of business card folders
- **Gmail API**: Track emails sent (KPI)
- **RingCentral**: Track phone calls (webhook integration for automatic call logging)

## Tech Stack

### Backend
- **Python 3.11+** with FastAPI
- **PostgreSQL** (SQLAlchemy ORM)
- **AI Document Parsing**: Google Gemini 2.0 Flash via REST API
- **Image Processing**: Pillow, pillow-heif (HEIC support)
- **PDF/Receipt/Card Parsing**: Gemini AI

### Frontend
- **React 19** with TypeScript
- **React Admin** for CRM UI
- **Tailwind CSS** + shadcn/ui components
- **Vite** for building

### Infrastructure
- **Mac Mini** for hosting (unified portal app)
- **PostgreSQL** on Mac Mini
- **Google Cloud** for Drive/Gmail APIs
- **Cron** for auto-scanning business card uploads

## API Endpoints

### Contacts
```
GET    /api/contacts              # List (with ?q=search&status=hot)
GET    /api/contacts/{id}         # Get one
POST   /api/contacts              # Create
PUT    /api/contacts/{id}         # Update
DELETE /api/contacts/{id}         # Delete (cascades tasks)
POST   /api/contacts/merge        # Merge duplicates
```

### Contact Tasks
```
GET    /api/contact-tasks?contact_id=123  # List tasks for contact
POST   /api/contact-tasks                 # Create task
PUT    /api/contact-tasks/{id}            # Update task
DELETE /api/contact-tasks/{id}            # Delete task
```

### Companies
```
GET    /api/companies             # List
GET    /api/companies/{id}        # Get one
POST   /api/companies             # Create
PUT    /api/companies/{id}        # Update
DELETE /api/companies/{id}        # Delete
```

### Deals
```
GET    /api/deals                 # List
GET    /api/deals/{id}            # Get one
POST   /api/deals                 # Create
PUT    /api/deals/{id}            # Update
DELETE /api/deals/{id}            # Delete
```

### Dashboard & Analytics
```
GET    /api/dashboard/summary       # All KPIs
GET    /api/visits                  # Visit list
GET    /api/activity-logs           # Activity log (includes business card scans, calls, emails, visits)
GET    /api/deals/stale             # Deals stuck in stage >30 days
GET    /api/analytics/stage-duration # Average time per stage
```

### Unified Timeline
```
GET    /api/timeline?contact_id=123       # Timeline for contact/company/deal
POST   /api/timeline/note                  # Quick note creation
```

### Relationship Graph
```
GET    /api/deals/{id}/contacts           # Get contacts for deal with roles
POST   /api/deals/{id}/contacts           # Add contact to deal
DELETE /api/deals/{id}/contacts/{cid}     # Remove contact from deal
GET    /api/contacts/{id}/deals           # Get all deals for a contact
GET    /api/contacts/{id}/relationships   # Full relationship graph
GET    /api/companies/{id}/relationships  # Company relationship graph
```

### Stage Tracking
```
GET    /api/deals/{id}/stage-history      # Full stage transition history
PUT    /api/deals/{id}/stage              # Update stage (logs history)
```

### AI Enrichment
```
POST   /api/companies/{id}/enrich         # Enrich company with AI
GET    /api/contacts/{id}/duplicates      # Find duplicate contacts
GET    /api/contacts/duplicates/scan      # Scan all contacts for duplicates
POST   /api/contacts/merge                # Merge duplicate contacts
GET    /api/contacts/{id}/interaction-summary  # AI summary of interactions
GET    /api/companies/{id}/interaction-summary # AI summary for company
```

### Business Card Scanning
```
POST   /upload-url                  # Single file from Google Drive
POST   /bulk-business-cards         # Folder from Google Drive
POST   /scan-business-card          # Local file upload
```

### Brevo Integration
```
GET    /api/brevo/test              # Test Brevo connection
POST   /api/sync-brevo-contacts     # Pull contacts from Brevo to Dashboard
POST   /webhooks/brevo              # Webhook endpoint for Brevo email events (delivered, opened, clicked, etc.)
```

## Webhooks

### Brevo Webhook
The Sales Dashboard automatically logs email activities from Brevo marketing campaigns via webhooks.

**Setup:**
1. In Brevo, go to **SMTP & API** → **Webhooks**
2. Create a new webhook with URL: `https://portal.coloradocareassist.com/sales/webhooks/brevo`
3. Select events to track:
   - `delivered` - Email delivered (logged as activity)
   - `opened` - Email opened (logged as activity)
   - `click` - Link clicked (logged as activity)
   - Optional: `hard_bounce`, `soft_bounce`, `spam`, `unsubscribe`

**How it works:**
- Each webhook event is automatically matched to contacts by email address
- Activities are logged in the contact's activity timeline
- Activities are linked to related deals when contacts are found
- Duplicate events are automatically prevented

**Example:** When you send a newsletter to 546 contacts, each "delivered" event creates an activity log for that contact, so you can see who received the newsletter.

### RingCentral Webhook
Automatically logs phone calls as activities. Configure in RingCentral dashboard.

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Mac Mini CLI (for deployment)
- Google Cloud Project with Drive API enabled

### 1. Clone Repository

```bash
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal/sales
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Environment Variables

Create `.env` file in the `sales/` directory:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Security
APP_SECRET_KEY=your-random-secret-key

# AI (for business card scanning)
GEMINI_API_KEY=your-gemini-api-key

# Google Drive (for business card auto-scanner)
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account",...}
GOOGLE_DRIVE_BUSINESS_CARDS_FOLDER_ID=your-folder-id

# Brevo (email marketing - free unlimited contacts!)
BREVO_API_KEY=xkeysib-...

# Optional integrations
RINGCENTRAL_CLIENT_ID=...
GMAIL_CREDENTIALS=...
```

### 5. Google Drive Setup for Business Card Auto-Scanner

1. **Create Google Cloud Project**:
   - Go to https://console.cloud.google.com
   - Create new project
   - Enable Google Drive API

2. **Create Service Account**:
   - IAM & Admin → Service Accounts → Create Service Account
   - Download JSON key
   - Copy JSON contents to `GOOGLE_SERVICE_ACCOUNT_KEY` env var

3. **Share Drive Folder**:
   - Create "Business Cards" folder in Google Drive
   - Create subfolders: `Jen Jeffers`, `Jacob Stewart`, `Colorado Springs`
   - Share folder with service account email (viewer access)
   - Copy folder ID from URL to `GOOGLE_DRIVE_BUSINESS_CARDS_FOLDER_ID`

4. **Set Up Cron Job** (for auto-scanning):
   ```bash
   # Edit crontab
   crontab -e

   # Add line to run every 5 minutes:
   */5 * * * * cd /path/to/colorado-careassist-portal/sales && /path/to/venv/bin/python scripts/auto_scan_drive.py >> /tmp/business-card-scanner.log 2>&1
   ```

### 6. Run Locally

```bash
# From sales/ directory
uvicorn app:app --reload --port 8000

# In another terminal, start frontend dev server (optional)
cd frontend
npm run dev
```

Visit: http://localhost:8000

### 7. Deploy to Mac Mini

The sales dashboard is part of the unified portal and deploys together:

```bash
# From repository root (colorado-careassist-portal/)
cd ..

# Deploy unified app (includes portal + sales + gigi)
git push origin main
```

The sales dashboard will be available at:
- https://portal.coloradocareassist.com/sales/
- https://portal.coloradocareassist.com/sales/ (if custom domain configured)

**Important**: The Procfile at the repository root uses `unified_app.py` which mounts the sales app at `/sales`.

## Project Structure

```
colorado-careassist-portal/
├── unified_app.py         # Main entry point (mounts all apps)
├── portal/                # Portal hub app
├── gigi/                  # Gigi AI voice assistant
└── sales/                 # Sales Dashboard (this directory)
    ├── app.py             # FastAPI application
    ├── models.py          # SQLAlchemy models
    ├── analytics.py       # Dashboard KPI calculations
    ├── ai_document_parser.py  # AI document parsing (Gemini)
    ├── activity_logger.py     # Activity logging service
    ├── brevo_service.py       # Brevo email marketing integration
    ├── google_drive_service.py # Google Drive integration
    ├── business_card_scanner.py # Business card AI parsing
    ├── requirements.txt       # Python dependencies
    ├── Procfile              # Mac Mini process file
    ├── Aptfile               # System dependencies
    │
    ├── services/         # Business logic services
    │   ├── activity_service.py    # Unified timeline & stage tracking
    │   ├── ai_enrichment_service.py # AI enrichment, deduplication, summaries
    │   └── auth_service.py        # Google OAuth authentication
    │
    ├── scripts/          # Utility scripts
    │   ├── auto_scan_drive.py         # Auto-scan Google Drive for business cards (runs via cron)
    │   └── fix_scanned_contacts.py    # Fix NULL last_activity for scanned contacts
    │
    ├── frontend/         # React Admin CRM
    │   ├── src/
    │   │   ├── components/
    │   │   │   └── atomic-crm/   # CRM components
    │   │   │       ├── contacts/
    │   │   │       ├── companies/
    │   │   │       ├── deals/
    │   │   │       ├── activity/
    │   │   │       └── dashboard/
    │   │   │           └── DashboardActivityLog.tsx  # Latest Activity widget
    │   │   └── activity-tracker/ # Legacy activity pages
    │   ├── dist/         # Built frontend (served by FastAPI)
    │   └── package.json
    │
    └── README.md         # This file
```

## Team Assignees

Tasks and activities can be assigned to:
- jacob@coloradocareassist.com (Jacob Stewart - Colorado Springs)
- jen@coloradocareassist.com (Jen Jeffers - Denver)
- jason@coloradocareassist.com (Jason Shulman - Owner)
- cosprings@coloradocareassist.com (Colorado Springs Office)

## Current Stats (as of Jan 2026)

- **1,091+ Contacts** in database
- **87+ Companies** tracked
- **Active Deals** in pipeline
- **744+ Total Visits** logged
- **Brevo**: Unlimited contacts on free plan
- **Business Card Scans**: Auto-processed from Google Drive every 5 minutes

### Recent Updates (Jan 2026)

**Attio-Inspired Enhancements:**
- Relationship Graph: Multi-contact deals with roles
- Time-in-Stage Tracking: Stale deal detection
- Unified Activity Timeline: All interactions in one view
- AI Enrichment: Company data, deduplication, interaction summaries

**Business Card Auto-Scanner:**
- Google Drive folder monitoring (Jen Jeffers, Jacob Stewart, Colorado Springs)
- Automatic AI extraction via Gemini
- Duplicate prevention by email/phone
- Real-time dashboard updates
- Activity logging for all scans (visible in Latest Activity widget)

**Latest Activity Widget Fix (v556):**
- Fixed display of business card scans (was showing "Activity" placeholder)
- Now shows proper descriptions: "Scanned business card for {name} from {filename}"
- Queries activity_logs database table for all activity types

## Development Workflow

1. Make changes in `sales/` directory
2. Test locally: `uvicorn app:app --reload`
3. Build frontend: `cd frontend && npm run build`
4. Commit changes: `git commit -am "Your message"`
5. Deploy unified app: `git push origin main` (from repository root)

## Troubleshooting

### Business Card Scanner Not Running
```bash
# Check cron job is set up
crontab -l | grep auto_scan_drive

# Run manually to test
cd /path/to/sales
source venv/bin/activate
python scripts/auto_scan_drive.py
```

### Latest Activity Widget Empty
- Check `/api/activity-logs` endpoint returns data
- Verify ActivityLog records exist in database
- Check frontend is calling correct endpoint path

### Contacts Not Appearing in Dashboard
- Verify `last_activity` field is set (required for dashboard filters)
- Run fix script: `python scripts/fix_scanned_contacts.py`

## License

Proprietary - Colorado CareAssist © 2025-2026
