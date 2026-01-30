# Colorado CareAssist - Recruiting Dashboard

A complete caregiver recruitment pipeline with Facebook Lead Ads integration, application tracking, and candidate management.

**Live URL**: https://portal.coloradocareassist.com/recruiting/
**Part of**: Colorado CareAssist Unified Portal (mounted at `/recruiting`)

---

## Features

### 👥 Candidate Pipeline
- Track caregiver applicants through recruitment stages
- Application status management (New → Screening → Interview → Hired/Rejected)
- Candidate notes and communication history
- Assignment to recruiting team members

### 📱 Facebook Lead Ads Integration
- **Auto-sync** from Facebook Lead Gen campaigns every 24 hours
- **Manual pull** via "Pull Leads" button in UI
- **Duplicate protection** via native Facebook Lead IDs
- Automatic backfill of existing manual leads with Facebook IDs

### 📊 Dashboard Analytics
- Total applicants by status
- Conversion rates (applicants → hired)
- Source tracking (Facebook, referral, website, walk-in)
- Time-to-hire metrics

---

## Architecture

**Tech Stack**:
- **Backend**: Flask (Python)
- **Frontend**: Jinja2 templates, Vanilla JavaScript
- **Database**: PostgreSQL (separate database from main portal)
- **Deployment**: Mounted at `/recruiting` in unified portal via `unified_app.py`

**Deployment**: Part of the unified portal app (`careassist-unified` on Heroku)

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- PostgreSQL
- Facebook Business account with Lead Ads campaigns
- Meta Developer account

### 1. Clone Repository

```bash
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal/recruiting
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 3. Set Up Database

```bash
# Create database
createdb colorado_careassist_recruiting

# Set database URL
export DATABASE_URL=postgresql://username:password@localhost:5432/colorado_careassist_recruiting

# Run migrations (creates tables)
python app.py  # Tables auto-create on first run
```

### 4. Environment Variables

Create `.env` file in `recruiting/` directory:

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/colorado_careassist_recruiting

# Facebook Lead Ads Integration
# Get from: https://developers.facebook.com/apps/
FACEBOOK_APP_ID=your-facebook-app-id
FACEBOOK_APP_SECRET=your-facebook-app-secret
FACEBOOK_ACCESS_TOKEN=your-long-lived-page-access-token
FACEBOOK_AD_ACCOUNT_ID=your-ad-account-id  # No "act_" prefix
FACEBOOK_PAGE_ID=your-facebook-page-id

# Flask Secret Key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-super-secret-key-change-this
```

### 5. Run Locally

```bash
# From recruiting/ directory
python app.py

# Visit: http://localhost:5000
```

---

## Facebook Lead Ads Setup

### Step 1: Create Meta App

1. Go to https://developers.facebook.com/apps/
2. Create new app → Select "Business" type
3. Add **Lead Ads** product
4. Request `leads_retrieval` permission (requires business verification)

### Step 2: Generate Long-Lived Access Token

```bash
# Get short-lived token from Graph API Explorer
# https://developers.facebook.com/tools/explorer/

# Exchange for long-lived token (60 days)
curl -G "https://graph.facebook.com/v18.0/oauth/access_token" \
  -d "grant_type=fb_exchange_token" \
  -d "client_id=YOUR_APP_ID" \
  -d "client_secret=YOUR_APP_SECRET" \
  -d "fb_exchange_token=SHORT_LIVED_TOKEN"
```

**Result**: Long-lived token (valid 60 days)

**Note**: Long-lived tokens expire after 60 days. You'll need to regenerate them. Consider setting up automatic refresh.

### Step 3: Get Page ID and Ad Account ID

```bash
# Get your Page ID
curl -G "https://graph.facebook.com/v18.0/me/accounts" \
  -d "access_token=YOUR_ACCESS_TOKEN"

# Get your Ad Account ID
curl -G "https://graph.facebook.com/v18.0/me/adaccounts" \
  -d "access_token=YOUR_ACCESS_TOKEN"
```

### Step 4: Test Connection

```bash
# Test API access
curl -G "https://graph.facebook.com/v18.0/YOUR_AD_ACCOUNT_ID/leadgen_forms" \
  -d "access_token=YOUR_ACCESS_TOKEN" \
  -d "fields=id,name,status,leads_count"
```

### Step 5: Configure Environment Variables

Set the variables from steps above in your `.env` file or Heroku config.

---

## Facebook Lead Sync

### Manual Sync (via UI)

1. Go to recruiting dashboard
2. Click **Facebook Campaign Management** card
3. Click **Pull Leads** button
4. Status text shows: "Last pull: X minutes ago. Ingested Y leads."

### Automated Sync (Heroku Scheduler)

**Recommended**: Set up daily automated sync

```bash
# Add Heroku Scheduler (if not already added)
heroku addons:create scheduler:standard -a careassist-unified

# Open scheduler dashboard
heroku addons:open scheduler -a careassist-unified
```

**Add job**:
- **Command**: `cd recruiting && python fetch_facebook_leads.py`
- **Frequency**: Daily at 9:00 AM
- **Dyno**: worker (or web if no worker dyno)

### Manual Sync (Command Line)

```bash
# From recruiting/ directory
python fetch_facebook_leads.py
```

**Output**:
```
✓ Fetched 15 leads from Facebook
✓ Inserted 12 new leads
✓ Skipped 3 duplicates (already in database)
```

---

## Duplicate Prevention

The dashboard uses **Facebook native Lead IDs** to prevent duplicates:

1. **New leads from Facebook**: Stored with `facebook_lead_id` field
2. **Duplicate check**: Skips any lead with same `facebook_lead_id`
3. **Backfill**: Existing manual leads matched by email/phone get Facebook ID added
4. **Manual entries**: Can be created without Facebook ID (for walk-ins, referrals)

**Database schema**:
```sql
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    facebook_lead_id VARCHAR(255) UNIQUE,  -- Prevents duplicates
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    source VARCHAR(50) DEFAULT 'facebook',
    status VARCHAR(50) DEFAULT 'new',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## API Endpoints

### Leads Management

```
GET    /api/leads                  # List all leads
GET    /api/leads/{id}             # Get single lead
POST   /api/leads                  # Create lead manually
PUT    /api/leads/{id}             # Update lead (status, notes, etc.)
DELETE /api/leads/{id}             # Delete lead
```

### Facebook Integration

```
GET    /api/facebook/status        # Check Facebook API connection
POST   /api/facebook/fetch-leads   # Pull leads from Facebook
GET    /api/facebook/campaigns     # List active lead gen campaigns
```

### Dashboard

```
GET    /                           # Main dashboard
GET    /dashboard/analytics        # Analytics view
GET    /dashboard/pipeline         # Pipeline view
```

---

## Deployment to Heroku

The recruiting dashboard is part of the **unified portal** and deploys together.

### Environment Variables (Heroku)

```bash
# Set recruiting database URL
heroku config:set RECRUITING_DATABASE_URL=postgresql://... -a careassist-unified

# Set Facebook credentials
heroku config:set FACEBOOK_APP_ID=your-app-id -a careassist-unified
heroku config:set FACEBOOK_APP_SECRET=your-app-secret -a careassist-unified
heroku config:set FACEBOOK_ACCESS_TOKEN=your-long-lived-token -a careassist-unified
heroku config:set FACEBOOK_AD_ACCOUNT_ID=your-account-id -a careassist-unified
heroku config:set FACEBOOK_PAGE_ID=your-page-id -a careassist-unified

# Verify
heroku config -a careassist-unified | grep FACEBOOK
```

### Deploy

```bash
# From repository root
git push heroku main
```

The recruiting dashboard will be available at:
- https://careassist-unified-0a11ddb45ac0.herokuapp.com/recruiting/
- https://portal.coloradocareassist.com/recruiting/ (if custom domain configured)

---

## Database Schema

### Leads Table

```sql
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    facebook_lead_id VARCHAR(255) UNIQUE,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    source VARCHAR(50) DEFAULT 'facebook',
    status VARCHAR(50) DEFAULT 'new',
    assigned_to VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_source ON leads(source);
CREATE INDEX idx_leads_facebook_id ON leads(facebook_lead_id);
```

### Lead Status Values

| Status | Description |
|--------|-------------|
| `new` | New applicant (not contacted yet) |
| `contacted` | Initial contact made |
| `screening` | Phone screening in progress |
| `interview_scheduled` | In-person interview scheduled |
| `background_check` | Background check in progress |
| `onboarding` | Hired, onboarding in progress |
| `active` | Active caregiver |
| `rejected` | Not a good fit |
| `withdrew` | Applicant withdrew |

---

## Troubleshooting

### Facebook Access Token Expired

**Error**: "Invalid OAuth access token"

**Fix**:
1. Generate new long-lived token (see Facebook Setup)
2. Update environment variable:
   ```bash
   heroku config:set FACEBOOK_ACCESS_TOKEN=new-token -a careassist-unified
   ```

### No Leads Being Pulled

**Check**:
1. Facebook campaigns are active and have leads
2. Access token has `leads_retrieval` permission
3. Ad account ID is correct (no "act_" prefix)

**Debug**:
```bash
# Test API manually
curl -G "https://graph.facebook.com/v18.0/YOUR_AD_ACCOUNT_ID/leadgen_forms" \
  -d "access_token=YOUR_TOKEN" \
  -d "fields=id,name,status,leads_count"
```

### Duplicate Leads Appearing

**Check**:
1. `facebook_lead_id` column exists in database
2. UNIQUE constraint on `facebook_lead_id` is active
3. Sync script is using latest version

**Fix**:
```bash
# Remove duplicates manually
heroku run python -a careassist-unified
>>> from app import db, Lead
>>> # Find duplicates
>>> duplicates = db.session.query(Lead.email, func.count(Lead.id)).group_by(Lead.email).having(func.count(Lead.id) > 1).all()
>>> # Keep only most recent
```

### Database Connection Errors

**Error**: "Could not connect to database"

**Fix**:
```bash
# Verify database URL
heroku config:get RECRUITING_DATABASE_URL -a careassist-unified

# Check database status
heroku pg:info -a careassist-unified

# Verify tables exist
heroku run python -a careassist-unified
>>> from app import db
>>> db.create_all()
```

---

## Development

### Local Development

```bash
# Set up local database
createdb colorado_careassist_recruiting

# Set environment variables
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
pip install -r requirements.txt

# Run app
python app.py

# Visit: http://localhost:5000
```

### Testing Facebook Integration

```bash
# Test API connection
python fetch_facebook_leads.py --dry-run

# Pull leads manually
python fetch_facebook_leads.py
```

### Database Migrations

Currently uses SQLAlchemy automatic table creation. For production, consider adding Alembic:

```bash
# Install Alembic
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

---

## Project Structure

```
recruiting/
├── app.py                      # Main Flask application
├── models.py                   # SQLAlchemy models
├── fetch_facebook_leads.py     # Facebook sync script
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
│
├── templates/                  # Jinja2 templates
│   ├── dashboard.html          # Main dashboard
│   ├── leads.html              # Leads list view
│   ├── lead_detail.html        # Single lead view
│   └── analytics.html          # Analytics dashboard
│
├── static/                     # CSS, JS, images
│   ├── css/
│   ├── js/
│   └── images/
│
└── README.md                   # This file
```

---

## Team

**Recruiting Team**:
- Primary recruiter assignments
- Lead follow-up and screening
- Interview coordination

**Development**:
- Jason Shulman (jason@coloradocareassist.com)

---

## License

Proprietary - Colorado CareAssist © 2025-2026

---

## Support

**Technical Issues**:
- Email: jason@coloradocareassist.com
- Check Heroku logs: `heroku logs --tail -a careassist-unified | grep recruiting`

**Facebook API Issues**:
- Meta Developer Support: https://developers.facebook.com/support/
- Check API status: https://developers.facebook.com/status/

---

## Recent Updates (Jan 2026)

- ✅ Facebook Lead Ads integration live
- ✅ Automated daily sync via Heroku Scheduler
- ✅ Duplicate protection via native Lead IDs
- ✅ Manual lead entry support
- ✅ Mounted at `/recruiting` in unified portal

---

**Ready to deploy?** See main [README.md](../README.md) and [DEPLOYMENT.md](../DEPLOYMENT.md) for complete setup instructions.
