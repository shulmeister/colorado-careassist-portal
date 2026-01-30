# Colorado CareAssist Portal

> **Complete unified business portal** with CRM, recruiting, marketing analytics, AI voice assistant, and operations dashboards - all in one deployable application.

**Live URL**: https://portal.coloradocareassist.com (or https://careassist-unified-0a11ddb45ac0.herokuapp.com)
**GitHub**: https://github.com/shulmeister/colorado-careassist-portal

---

## 🚀 Quick Start (Clone & Deploy from Scratch)

```bash
# 1. Clone the repository
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your API keys (see Environment Variables section below)

# 3. Install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Set up databases (PostgreSQL required)
createdb colorado_careassist_portal
createdb colorado_careassist_sales
createdb colorado_careassist_recruiting

# 5. Run migrations
alembic upgrade head

# 6. Build frontend (sales dashboard)
cd sales/frontend
npm install
npm run build
cd ../..

# 7. Run locally
uvicorn unified_app:app --reload --port 8000

# Visit: http://localhost:8000
```

For production deployment to Heroku, see [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 🏗️ Architecture Overview

This is a **unified FastAPI application** that mounts multiple sub-applications at different URL paths:

```
colorado-careassist-portal/
├── unified_app.py          # Main entry point (mounts everything)
├── portal/                 # Portal hub (FastAPI)
├── sales/                  # Sales Dashboard (FastAPI + React Admin)
├── recruiting/             # Recruiter Dashboard (Flask)
├── gigi/                   # Gigi AI Voice Assistant (FastAPI)
├── powderpulse/            # PowderPulse ski weather (Vue.js SPA)
├── va-plan-of-care/        # VA form converter
├── services/               # Shared services (WellSky, marketing APIs)
└── templates/              # Jinja2 templates for portal pages
```

**Deployment**: Everything deploys together to a single Heroku app (`careassist-unified`) via `unified_app.py`.

---

## 📱 Applications & Features

| App | URL Path | Tech Stack | Purpose |
|-----|----------|------------|---------|
| **Portal Hub** | `/` | FastAPI + Jinja2 | Main dashboard with tiles for all apps |
| **Gigi AI** | `/gigi` | FastAPI + Retell AI | Voice/SMS assistant for after-hours calls |
| **Sales Dashboard** | `/sales` | FastAPI + React Admin | Full CRM: contacts, companies, deals, visits |
| **Recruiting** | `/recruiting` | Flask | Caregiver recruitment pipeline |
| **Marketing** | `/marketing` | Jinja2 + Chart.js | Social media, Google Ads, GA4, GBP analytics |
| **Operations** | `/operations` | Jinja2 + Chart.js | WellSky EVV integration, client operations |
| **PowderPulse** | `/powderpulse` | Vue.js SPA | Colorado ski resort weather forecasts |
| **Payroll** | `/payroll` | Static HTML | WellSky payroll report converter |
| **VA Plan of Care** | `/va-plan-of-care` | TBD | Veteran Affairs form converter |

---

## 🤖 Gigi - AI Voice Assistant

**Gigi** is Colorado Care Assist's AI-powered voice assistant who answers calls when the office is closed or when staff cannot answer. She handles caregiver call-outs, client complaints, and prospect inquiries with calm, capable professionalism.

**Phone Numbers**:
- **Primary**: 719-428-3999 (Colorado Springs)
- **Secondary**: 303-757-1777 (Denver)

**Capabilities**:
| Feature | Status |
|---------|--------|
| Voice calls (Retell AI) | ✅ Live |
| SMS auto-responses (RingCentral) | ✅ Live |
| Caregiver call-out handling | ✅ Live |
| WellSky shift lookup | ⏳ Ready (needs API key) |
| Clock in/out via phone | ⏳ Ready (needs API key) |

**Technical**:
- **Tech**: FastAPI, Retell AI (voice), RingCentral (SMS), Google Gemini (AI), WellSky API
- **Key Files**: `gigi/main.py`, `gigi/knowledge_base.md`, `gigi/system_prompt.txt`
- **Documentation**: See [gigi/README.md](gigi/README.md)

---

## 💼 Sales Dashboard - Full CRM

**Location**: `/sales` (mounted from `/sales/` directory)
**Live URL**: https://portal.coloradocareassist.com/sales/

**Features**:
- **CRM**: Contacts, companies, deals with full pipeline management
- **AI Business Card Scanner**: Auto-processes cards uploaded to Google Drive
- **Activity Tracking**: Visits, calls, emails, notes with unified timeline
- **AI Enrichment**: Automatic company data lookup, duplicate detection, interaction summaries
- **Integrations**: Brevo (email marketing), QuickBooks (customer sync), RingCentral (call logging), Gmail API

**Business Card Auto-Scanner**:
1. Upload business cards (JPG, PNG, HEIC) to Google Drive folders:
   - `Business Cards/Jen Jeffers/` → jen@coloradocareassist.com
   - `Business Cards/Jacob Stewart/` → jacob@coloradocareassist.com
   - `Business Cards/Colorado Springs/` → cosprings@coloradocareassist.com
2. Cron job runs every 5 minutes: `python sales/scripts/auto_scan_drive.py`
3. Gemini AI extracts contact info (name, email, phone, company)
4. Contacts appear instantly in dashboard with proper account manager assignment

**Documentation**: See [sales/README.md](sales/README.md)

---

## 👥 Recruiting Dashboard

**Location**: `/recruiting` (mounted from `/recruiting/` directory)
**Live URL**: https://portal.coloradocareassist.com/recruiting/

**Features**:
- Caregiver recruitment pipeline
- Facebook Lead Ads integration (auto-sync every 24 hours)
- Duplicate detection via native Facebook lead IDs
- Application tracking and status management

**Documentation**: See [recruiting/README.md](recruiting/README.md)

---

## 📊 Marketing Dashboard

**Location**: `/marketing` (built into portal_app.py)
**Live URL**: https://portal.coloradocareassist.com/marketing/

**Data Sources**:
- **Social Media**: Facebook, Instagram, LinkedIn, Pinterest, TikTok
- **Advertising**: Google Ads, Facebook Ads
- **Analytics**: Google Analytics 4, Google Business Profile
- **Email**: Brevo (formerly Sendinblue)

**Key Metrics**: Impressions, clicks, CTR, conversions, ROAS, engagement rates

---

## 🏥 Operations Dashboard

**Location**: `/operations` (built into portal_app.py)
**Live URL**: https://portal.coloradocareassist.com/operations/

**Features**:
- Client operations KPIs
- Care plans due for review
- Open shifts and coverage
- At-risk client monitoring
- **WellSky EVV Integration** (ready for API key)

**WellSky Integration**:
- Currently in mock mode (uses `services/wellsky_service.py` with sample data)
- Ready to activate when `WELLSKY_API_KEY` is configured
- Features: shift lookup, clock in/out, call-out reporting

---

## ⛷️ PowderPulse - Ski Weather App

**Location**: `/powderpulse` (Vue.js SPA)
**Live URL**: https://portal.coloradocareassist.com/powderpulse/

**Features**:
- Real-time Colorado ski resort weather forecasts
- Snow conditions, lift status, trail counts
- Responsive design for mobile/desktop

---

## 🛠️ Environment Variables

**Required environment variables** (copy from `.env.example` and fill in):

### Core Portal
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/colorado_careassist_portal
APP_SECRET_KEY=your-super-secret-key
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://careassist-unified-0a11ddb45ac0.herokuapp.com/auth/callback
ALLOWED_DOMAINS=coloradocareassist.com
```

### Sales Dashboard
```bash
SALES_DATABASE_URL=postgresql://username:password@localhost:5432/colorado_careassist_sales
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account",...}
GOOGLE_DRIVE_BUSINESS_CARDS_FOLDER_ID=your-folder-id
BREVO_API_KEY=xkeysib-your-api-key
QUICKBOOKS_CLIENT_ID=your-client-id
QUICKBOOKS_CLIENT_SECRET=your-client-secret
GMAIL_SERVICE_ACCOUNT_EMAIL=your-service-account@project.iam.gserviceaccount.com
```

### Recruiting Dashboard
```bash
RECRUITING_DATABASE_URL=postgresql://username:password@localhost:5432/colorado_careassist_recruiting
FACEBOOK_ACCESS_TOKEN=your-long-lived-token
FACEBOOK_AD_ACCOUNT_ID=act_your-account-id
```

### Gigi AI Voice Assistant
```bash
RETELL_API_KEY=your-retell-api-key
GEMINI_API_KEY=your-gemini-api-key
RINGCENTRAL_CLIENT_ID=your-client-id
RINGCENTRAL_CLIENT_SECRET=your-client-secret
RINGCENTRAL_JWT_TOKEN=your-jwt-token
WELLSKY_API_KEY=your-wellsky-key  # Optional, enables WellSky features
```

### Marketing Dashboard
```bash
GA4_PROPERTY_ID=your-property-id
GBP_LOCATION_IDS=comma,separated,ids
GOOGLE_ADS_DEVELOPER_TOKEN=your-token
GOOGLE_ADS_CUSTOMER_ID=1234567890
LINKEDIN_ACCESS_TOKEN=your-token
TIKTOK_ACCESS_TOKEN=your-token
```

**Complete list**: See [.env.example](.env.example) for all variables with detailed comments.

---

## 📦 Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI, Flask |
| Frontend | React 19 (sales), Vue.js (PowderPulse), Jinja2 (portal) |
| Databases | PostgreSQL (3 separate databases) |
| AI/ML | Google Gemini 2.0 Flash, Retell AI |
| Voice/SMS | Retell AI, RingCentral |
| Email/Marketing | Brevo, QuickBooks, Facebook Ads |
| OCR/Documents | Gemini AI (business cards, receipts, PDFs) |
| Deployment | Heroku (unified app) |
| Build Tools | Vite (React), npm, pip |

---

## 🚢 Deployment

### Heroku (Production)

**App Name**: `careassist-unified`
**URL**: https://careassist-unified-0a11ddb45ac0.herokuapp.com
**Custom Domain**: https://portal.coloradocareassist.com

**Deploy process**:
```bash
# 1. Login to Heroku
heroku login

# 2. Add Heroku remote (if not already added)
git remote add heroku https://git.heroku.com/careassist-unified.git

# 3. Deploy
git push heroku main
```

**Auto-deploy**: GitHub integration is enabled - pushes to `main` branch automatically deploy to Heroku.

**Detailed deployment guide**: See [DEPLOYMENT.md](DEPLOYMENT.md) for complete instructions including:
- PostgreSQL add-on setup
- Environment variable configuration
- Buildpacks
- Heroku Scheduler jobs (business card scanner, Facebook leads sync)
- Custom domain configuration
- Monitoring and logging

---

## 🔧 Development

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 18 or higher
- **PostgreSQL**: 14 or higher
- **Git**: Latest version

### Local Setup

```bash
# 1. Clone repository
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal

# 2. Set up Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# 4. Create PostgreSQL databases
createdb colorado_careassist_portal
createdb colorado_careassist_sales
createdb colorado_careassist_recruiting

# 5. Run database migrations
alembic upgrade head

# 6. Build sales dashboard frontend
cd sales/frontend
npm install
npm run build
cd ../..

# 7. Start development server
uvicorn unified_app:app --reload --port 8000
```

### Running Individual Apps

**Portal only**:
```bash
cd portal
uvicorn portal_app:app --reload --port 8000
```

**Sales dashboard only**:
```bash
cd sales
uvicorn app:app --reload --port 8000
```

**Recruiting dashboard only**:
```bash
cd recruiting
python app.py
```

**Gigi AI only**:
```bash
cd gigi
uvicorn main:app --reload --port 8000
```

### Building Frontends

**Sales dashboard** (React):
```bash
cd sales/frontend
npm run dev  # Development mode with hot reload
npm run build  # Production build → sales/frontend/dist/
```

**PowderPulse** (Vue):
```bash
cd powderpulse
npm run dev  # Development mode
npm run build  # Production build → powderpulse/dist/
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | This file - overview and quick start |
| [.env.example](.env.example) | Complete environment variables template |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Complete Heroku deployment guide |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local development setup and workflows |
| [sales/README.md](sales/README.md) | Sales Dashboard documentation |
| [gigi/README.md](gigi/README.md) | Gigi AI Voice Assistant documentation |
| [recruiting/README.md](recruiting/README.md) | Recruiting Dashboard documentation |
| [CLAUDE.md](CLAUDE.md) | AI agent instructions (for Claude Code) |

---

## 🗂️ Project Structure

```
colorado-careassist-portal/
├── unified_app.py                  # Main entry point (mounts all apps)
├── requirements.txt                # Python dependencies
├── Procfile                        # Heroku process file
├── .env.example                    # Environment variables template
│
├── portal/                         # Portal Hub (FastAPI)
│   ├── portal_app.py               # Main portal application
│   ├── portal_auth.py              # Google OAuth authentication
│   ├── portal_models.py            # Database models
│   └── portal_setup.py             # Initial setup script
│
├── sales/                          # Sales Dashboard (FastAPI + React)
│   ├── app.py                      # Main FastAPI application
│   ├── models.py                   # SQLAlchemy ORM models
│   ├── analytics.py                # Dashboard KPIs and analytics
│   ├── business_card_scanner.py    # AI business card parsing
│   ├── brevo_service.py            # Brevo email integration
│   ├── google_drive_service.py     # Google Drive integration
│   ├── frontend/                   # React Admin CRM frontend
│   │   ├── src/                    # React source code
│   │   └── dist/                   # Built frontend (served by FastAPI)
│   ├── scripts/                    # Utility scripts
│   │   ├── auto_scan_drive.py      # Business card auto-scanner (cron job)
│   │   └── fix_scanned_contacts.py # Maintenance scripts
│   └── services/                   # Business logic services
│
├── recruiting/                     # Recruiting Dashboard (Flask)
│   ├── app.py                      # Main Flask application
│   ├── models.py                   # SQLAlchemy models
│   ├── templates/                  # Jinja2 templates
│   └── static/                     # CSS, JS, images
│
├── gigi/                           # Gigi AI Voice Assistant
│   ├── main.py                     # FastAPI application
│   ├── knowledge_base.md           # Retell AI knowledge base
│   ├── system_prompt.txt           # Voice personality prompt
│   ├── conversation_flow.py        # Call flow logic
│   └── conversation_flow_config.json # Retell config
│
├── powderpulse/                    # PowderPulse Ski Weather App
│   ├── index.html                  # Vue.js SPA entry point
│   ├── src/                        # Vue source code
│   └── dist/                       # Built app
│
├── va-plan-of-care/                # VA Form Converter
│   ├── app.py                      # FastAPI application
│   └── templates/                  # Form templates
│
├── services/                       # Shared Services
│   ├── wellsky_service.py          # WellSky EVV API client
│   ├── marketing/                  # Marketing API integrations
│   │   ├── brevo_client.py
│   │   ├── facebook_client.py
│   │   ├── google_ads_client.py
│   │   ├── ga4_client.py
│   │   └── gbp_client.py
│   └── auth_service.py             # Shared authentication
│
├── templates/                      # Portal Jinja2 Templates
│   ├── index.html                  # Portal hub page
│   ├── marketing.html              # Marketing dashboard
│   ├── operations.html             # Operations dashboard
│   └── payroll.html                # Payroll converter
│
├── static/                         # Static Assets
│   ├── css/
│   ├── js/
│   └── images/
│
└── docs/                           # Documentation
    ├── README.md                   # Documentation index
    ├── WELLSKY_API_TECHNICAL_SPECIFICATION.md
    ├── MARKETING_STRATEGY_JAN2026.md
    └── archive/                    # Archived setup guides
```

---

## 👥 Team & Contributors

**Colorado Care Assist Staff**:
- **Jason Shulman** - Owner (jason@coloradocareassist.com)
- **Cynthia Pointe** - Operations Manager (cynthia@coloradocareassist.com, ext 105)
- **Jen Jeffers** - Sales (Denver) (jen@coloradocareassist.com)
- **Jacob Stewart** - Sales (Colorado Springs) (jacob@coloradocareassist.com)
- **Gigi** - AI Voice Assistant (ext 999, phone: 719-428-3999)

**Development Team**:
- Primary development by Jason Shulman
- AI assistance via Claude (Anthropic)

---

## 📝 License

Proprietary - Colorado CareAssist © 2025-2026

---

## 🆘 Support

**Internal Team**:
- Email: jason@coloradocareassist.com
- Phone: 303-757-1777 (Denver), 719-428-3999 (Colorado Springs)

**Development Issues**:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- Review Heroku logs: `heroku logs --tail -a careassist-unified`
- Check application logs in respective directories

**Emergency Contacts**:
- **Cynthia Pointe**: RingCentral ext 105 (operations)
- **Jason Shulman**: RingCentral ext 101 (technical)

---

## 🎯 Key Features by Use Case

### For Sales Team
- 📇 Business card auto-scanning from Google Drive uploads
- 📊 Full CRM with contacts, companies, deals
- 📧 Email marketing via Brevo integration
- 📱 Call logging via RingCentral webhook
- 💰 QuickBooks customer sync
- 🤖 AI-powered company enrichment and duplicate detection

### For Recruiting Team
- 👥 Caregiver recruitment pipeline
- 📱 Facebook Lead Ads auto-sync (24-hour schedule)
- 🔍 Duplicate-proof lead tracking
- 📊 Application status management

### For Marketing Team
- 📈 Multi-platform social media analytics
- 💰 Google Ads and Facebook Ads performance
- 📊 Google Analytics 4 and Google Business Profile metrics
- 📧 Brevo email marketing campaign tracking
- 📱 LinkedIn, Pinterest, TikTok engagement metrics

### For Operations Team
- 🏥 Client operations KPIs
- 📋 Care plans due for review tracking
- 📅 Open shift and coverage monitoring
- ⚠️ At-risk client alerts
- ⏰ WellSky EVV integration (clock in/out, shift lookup)

### For Executive Team
- 📊 Unified dashboard hub with all key metrics
- 🤖 Gigi AI handling after-hours communications
- 💼 Complete visibility across sales, recruiting, marketing, operations
- 📱 Mobile-responsive access to all applications

---

## 🚀 Recent Updates (Jan 2026)

- ✅ Business card auto-scanner with Google Drive monitoring
- ✅ Latest Activity widget fix (shows business card scans)
- ✅ Unified app architecture (everything in one Heroku app)
- ✅ Gigi AI voice assistant live on 719-428-3999
- ✅ RingCentral SMS auto-responses
- ✅ QuickBooks customer sync to Brevo
- ✅ WellSky API integration ready (awaiting API key)

---

**Ready to deploy?** See [DEPLOYMENT.md](DEPLOYMENT.md) for complete Heroku setup instructions.
**Need help?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or email jason@coloradocareassist.com
