# AGENTS.md — Recruiter Dashboard Guide for AI Agents

> ⚠️ **STOP! Read the parent documentation first:**
> - `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/AGENTS.md`
> - `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/CODEBASE_LOCATIONS.md`
>
> This is a **spoke** of the Colorado CareAssist Portal. It's a nested git repository inside the main portal.

---

## 1. Quick Reference

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment` |
| **GitHub** | `https://github.com/shulmeister/recruiter-dashboard` |
| **Mac Mini App** | `caregiver-lead-tracker` |
| **Live URL** | `https://portal.coloradocareassist.com/recruiting` |
| **Tech Stack** | Flask, SQLAlchemy, PostgreSQL |

---

## 2. Deployment

```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git add -A && git commit -m "Description" && git push origin main && git push origin main
```

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application |
| `models.py` | SQLAlchemy ORM models |
| `fetch_facebook_leads.py` | Script to pull leads from Facebook Lead Ads |
| `templates/` | Jinja2 HTML templates |
| `portal_auth_middleware.py` | Portal SSO authentication |

---

## 4. Features

- **Candidate Pipeline**: Track caregiver applicants through hiring stages
- **Facebook Lead Ads Sync**: Pull leads from Meta Lead Ads campaigns
- **Duplicate Protection**: Prevents duplicate leads via `facebook_lead_id`
- **Portal Integration**: SSO authentication from main portal

---

## 5. Facebook Lead Ads Integration

### Environment Variables
```
FACEBOOK_APP_ID
FACEBOOK_APP_SECRET
FACEBOOK_ACCESS_TOKEN
FACEBOOK_AD_ACCOUNT_ID
```

### Manual Pull
Click "Pull Leads" button in the Facebook Campaign Management card.

### Scheduled Pull
```bash
python fetch_facebook_leads.py
```
Add to Mac Mini Scheduler for automatic daily sync.

---

## 6. Common Commands

```bash
# Check logs
mac-mini logs -n 100 -a caregiver-lead-tracker

# Restart
mac-mini restart -a caregiver-lead-tracker

# Run locally
flask run --port 5000
```

---

## 7. Important Notes

- This is a **nested git repo** - it has its own `.git` folder
- Always push to BOTH `origin` (GitHub) AND `mac-mini`
- Uses Flask (not FastAPI like other dashboards)
- Portal embeds this via iframe at `/recruitment` route

---

*Parent project: Colorado CareAssist Portal*
*Last Updated: December 29, 2025*

