# Colorado CareAssist Sales Dashboard & CRM

A comprehensive full-stack sales CRM and activity tracking application for Colorado CareAssist. Built with React Admin frontend and FastAPI backend.

**Live URL**: https://careassist-tracker-0fcf2cecdb22.herokuapp.com/

## Features

### 📊 CRM Dashboard
- **Hot Contacts**: Quick view of high-priority contacts
- **Pipeline View**: Visual deal pipeline with drag-and-drop stages
- **Activity KPIs**: Real-time metrics for visits, contacts, companies, deals
- **Forecasting**: Revenue projections based on deal stages and probability

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

### 📇 AI-Powered Document Scanning (Gemini)
- **MyWay PDFs**: AI extracts visits, addresses, cities, mileage, dates
- **Receipts**: AI extracts vendor, amount, date, category, items
- **Business Cards**: AI extracts contact info (name, company, email, phone)
- Upload from device or paste Google Drive links
- Bulk import folders from Google Drive
- Automatic duplicate detection for contacts, companies, and visits
- **No more OCR garbage** — Pure AI extraction via Gemini REST API

### 📈 Activity Tracking
- **Visits**: Log and track sales visits with MyWay PDF import (AI-parsed)
- **Expense Tracking**: Mileage reimbursement and expense management (AI-parsed)
- **Pay Period Navigator**: View expenses by payroll period
- **Activity Logs**: Full audit trail of all CRM actions
- **Duplicate Prevention**: MyWay visits checked for duplicates before saving

### 🔗 Integrations
- **Brevo** (formerly Sendinblue): Sync contacts for email marketing + webhook integration for automatic activity logging (delivered, opened, clicked events)
- **Google Drive**: Import files and folders directly
- **Gmail API**: Track emails sent (KPI)
- **RingCentral**: Track phone calls (webhook integration for automatic call logging)

## Tech Stack

### Backend
- **Python 3.11+** with FastAPI
- **PostgreSQL** (SQLAlchemy ORM)
- **AI Document Parsing**: Google Gemini 2.0 Flash via REST API (primary)
- **Image Processing**: Pillow, pillow-heif (HEIC support)
- **PDF/Receipt/Card Parsing**: Gemini AI (replaced OCR/Tesseract)

### Frontend
- **React 19** with TypeScript
- **React Admin** for CRM UI
- **Tailwind CSS** + shadcn/ui components
- **Vite** for building

### Infrastructure
- **Heroku** for hosting
- **PostgreSQL** on Heroku
- **Google Cloud** for Drive/Gmail APIs

## API Endpoints

### Contacts
```
GET    /admin/contacts              # List (with ?q=search&status=hot)
GET    /admin/contacts/{id}         # Get one
POST   /admin/contacts              # Create
PUT    /admin/contacts/{id}         # Update
DELETE /admin/contacts/{id}         # Delete (cascades tasks)
POST   /api/contacts/merge          # Merge duplicates
```

### Contact Tasks
```
GET    /admin/contact-tasks?contact_id=123  # List tasks for contact
POST   /admin/contact-tasks                 # Create task
PUT    /admin/contact-tasks/{id}            # Update task
DELETE /admin/contact-tasks/{id}            # Delete task
```

### Companies
```
GET    /admin/companies             # List
GET    /admin/companies/{id}        # Get one
POST   /admin/companies             # Create
PUT    /admin/companies/{id}        # Update
DELETE /admin/companies/{id}        # Delete
```

### Deals
```
GET    /admin/deals                 # List
GET    /admin/deals/{id}            # Get one
POST   /admin/deals                 # Create
PUT    /admin/deals/{id}            # Update
DELETE /admin/deals/{id}            # Delete
```

### Dashboard & Analytics
```
GET    /api/dashboard/summary       # All KPIs
GET    /api/visits                  # Visit list
GET    /api/activity-logs           # Activity log
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
2. Create a new webhook with URL: `https://careassist-tracker-0fcf2cecdb22.herokuapp.com/webhooks/brevo`
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
- Heroku CLI (for deployment)

### 1. Clone and Install

```bash
git clone https://github.com/shulmeister/sales-dashboard.git
cd sales-dashboard

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run build
cd ..
```

### 2. Environment Variables

Create `.env` file (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Security
APP_SECRET_KEY=your-random-secret-key

# AI (for business card scanning)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Google (for Drive import)
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account",...}

# Brevo (email marketing - free unlimited contacts!)
BREVO_API_KEY=xkeysib-...

# QuickBooks (customer sync to Brevo)
QUICKBOOKS_CLIENT_ID=...
QUICKBOOKS_CLIENT_SECRET=...
QUICKBOOKS_REALM_ID=...
QUICKBOOKS_ACCESS_TOKEN=...
QUICKBOOKS_REFRESH_TOKEN=...

# Optional integrations
RINGCENTRAL_CLIENT_ID=...
GMAIL_CREDENTIALS=...
```

### 3. Run Locally

```bash
# Start backend
uvicorn app:app --reload --port 8000

# In another terminal, start frontend dev server
cd frontend
npm run dev
```

### 4. Deploy to Heroku

```bash
# Login and create app
heroku login
heroku create your-app-name

# Add buildpacks
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-apt
heroku buildpacks:add heroku/python

# Set config vars
heroku config:set DATABASE_URL=...
heroku config:set APP_SECRET_KEY=...
heroku config:set OPENAI_API_KEY=...
# etc.

# Deploy
git push heroku main
```

## Project Structure

```
sales-dashboard/
├── app.py                 # Main FastAPI application
├── models.py              # SQLAlchemy models (with DealContact, DealStageHistory)
├── analytics.py           # Dashboard KPI calculations
├── ai_document_parser.py  # AI document parsing (Gemini)
├── brevo_service.py       # Brevo email marketing integration
├── google_drive_service.py # Google Drive integration
├── business_card_scanner.py # Legacy OCR (deprecated)
├── requirements.txt       # Python dependencies
├── Procfile              # Heroku process file
├── Aptfile               # System dependencies
│
├── services/             # Business logic services
│   ├── activity_service.py    # Unified timeline & stage tracking
│   ├── ai_enrichment_service.py # AI enrichment, deduplication, summaries
│   └── auth_service.py        # Google OAuth authentication
│
├── scripts/              # Utility scripts
│   └── migrate_attio_enhancements.py  # Database migration for new features
│
├── frontend/             # React Admin CRM
│   ├── src/
│   │   ├── components/
│   │   │   └── atomic-crm/   # CRM components
│   │   │       ├── contacts/
│   │   │       ├── companies/
│   │   │       ├── deals/
│   │   │       └── activity/
│   │   └── activity-tracker/ # Legacy activity pages
│   ├── dist/             # Built frontend (served by FastAPI)
│   └── package.json
│
└── README.md             # This file
```

## Team Assignees

Tasks and activities can be assigned to:
- jacob@coloradocareassist.com
- cynthia@coloradocareassist.com
- jason@coloradocareassist.com

## Current Stats (as of Jan 2026)

- **1,091+ Contacts** in database
- **87+ Companies** tracked
- **Active Deals** in pipeline
- **744+ Total Visits** logged
- **Brevo**: Unlimited contacts on free plan

### New in Jan 2026 (Attio-Inspired Enhancements)
- Relationship Graph: Multi-contact deals with roles
- Time-in-Stage Tracking: Stale deal detection
- Unified Activity Timeline: All interactions in one view
- AI Enrichment: Company data, deduplication, interaction summaries

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test locally
3. Build frontend: `cd frontend && npm run build`
4. Commit: `git commit -am "Add your feature"`
5. Push to all remotes:
   ```bash
   git push origin main
   git push heroku main
   ```

## License

Proprietary - Colorado CareAssist © 2025-2026
