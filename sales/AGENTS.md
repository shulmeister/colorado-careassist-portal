# AGENTS.md — Sales Dashboard Guide for AI Agents

> ⚠️ **STOP! Read the parent documentation first:**
> - `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/AGENTS.md`
> - `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/CODEBASE_LOCATIONS.md`
>
> This is a **spoke** of the Colorado CareAssist Portal. It's a nested git repository inside the main portal.

---

## 1. Quick Reference

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/sales` |
| **GitHub** | `https://github.com/shulmeister/sales-dashboard` |
| **Heroku App** | `careassist-tracker` |
| **Staging App** | `careassist-tracker-staging` |
| **Live URL** | `https://careassist-tracker-0fcf2cecdb22.herokuapp.com` |
| **Tech Stack** | FastAPI, React-Admin, PostgreSQL, Python 3.11 |

---

## 2. Deployment

```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git add -A && git commit -m "Description" && git push origin main && git push heroku main
```

**Staging deployment:**
```bash
git push heroku-staging main
```

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main FastAPI application (~4000+ lines) |
| `models.py` | SQLAlchemy ORM models (Contact, Company, Deal, Visit, Expense, etc.) |
| `ai_document_parser.py` | Gemini-based document parsing for PDFs, receipts, business cards |
| `analytics.py` | Dashboard KPI calculations |
| `brevo_service.py` | Brevo email marketing integration |
| `frontend/` | React-Admin frontend application |
| `frontend/src/App.tsx` | Main React app with routing |
| `frontend/src/activity-tracker/` | Activity tracking UI components |

---

## 4. Features

- **CRM**: Contacts, Companies, Deals with full CRUD
- **Activity Tracking**: Visits, mileage, expenses, email activities (via Brevo webhooks)
- **Document Scanning**: MyWay PDFs, receipts, business cards via AI
- **Email Marketing**: Brevo integration (contact sync + webhook activity logging)
- **Dashboard**: Real-time analytics

---

## 5. Environment Variables

```
DATABASE_URL
GEMINI_API_KEY
OPENAI_API_KEY
GOOGLE_SERVICE_ACCOUNT_KEY
BREVO_API_KEY
SECRET_KEY
```

---

## 6. Common Commands

```bash
# Check logs
heroku logs -n 100 -a careassist-tracker

# Restart
heroku restart -a careassist-tracker

# Build frontend
cd frontend && npm run build && cd ..

# Run locally
uvicorn app:app --reload --port 8000
```

---

## 7. Important Notes

- This is a **nested git repo** - it has its own `.git` folder
- Always push to BOTH `origin` (GitHub) AND `heroku`
- The iCloud folder at `~/Library/Mobile Documents/.../sales-dashboard` is a duplicate - use this path instead
- Frontend changes require `npm run build` before deploying

---

*Parent project: Colorado CareAssist Portal*
*Last Updated: December 29, 2025*

