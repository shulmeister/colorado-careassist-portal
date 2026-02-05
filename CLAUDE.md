# CLAUDE.md — Colorado Care Assist Infrastructure

**Last Updated:** February 4, 2026
**Status:** ✅ FULLY SELF-HOSTED ON MAC MINI

---

## PROJECT OVERVIEW

This is the **unified platform** for Colorado Care Assist, containing:

| Component | Description | Location |
|-----------|-------------|----------|
| **Portal** | Main web dashboard with 26+ tiles | `/portal/` |
| **Gigi AI** | Chief of Staff AI (voice, SMS, Telegram, scheduling) | `/gigi/` |
| **Sales Dashboard** | CRM for sales tracking | `/sales/` |
| **Recruiting** | Caregiver recruiting dashboard | `/recruiting/` |
| **PowderPulse** | Ski weather app (Vue.js) | `/powderpulse/` |

### Related Repositories

| Repo | Port | URL | Description |
|------|------|-----|-------------|
| `careassist-unified` | 8765 | portal.coloradocareassist.com | This repo - unified platform |
| `coloradocareassist` | 3000 | coloradocareassist.com | Marketing website (Next.js) |
| `hesedhomecare` | 3001 | hesedhomecare.org | Hesed website (Next.js) |
| `clawd` | - | - | Gigi config, elite teams, knowledge base |

---

## GIGI - THE AI CHIEF OF STAFF

**Gigi is ONE unified AI** operating across multiple channels:

| Channel | Technology | Purpose |
|---------|------------|---------|
| **Telegram** (@Shulmeisterbot) | `telegram_bot.py` | Personal assistant for Jason |
| **Voice** (307-459-8220) | Retell AI | Phone calls, caller ID, transfers |
| **SMS** (307-459-8220) | RingCentral + Gemini | Text message replies |
| **Team Chat** | RingCentral Glip | Monitors "New Scheduling" chat |
| **Portal** | Web UI | Dashboard, tools, analytics |

### Gigi's Core Capabilities
- **WellSky Integration**: Full CRUD on Patients, Practitioners, Appointments, Encounters, DocumentReferences, Subscriptions, ProfileTags, and RelatedPersons. Clock in/out, task logs, shift search, and webhook event subscriptions. See `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` for complete endpoint reference.
- **RingCentral**: SMS, voice, team messaging
- **Google Workspace**: Calendar, email (read/write)
- **Auto-Documentation**: Syncs RC messages → WellSky client notes
- **After-Hours Coverage**: Autonomous SMS/voice handling

### Gigi's Constitution (Laws)
See `gigi/CONSTITUTION.md` for the 10 non-negotiable operating principles.

---

## INFRASTRUCTURE

### Services Running on Mac Mini

| Service | Port | LaunchAgent |
|---------|------|-------------|
| Portal (gigi-unified) | 8765 | com.coloradocareassist.gigi-unified |
| Main Website | 3000 | com.coloradocareassist.website |
| Hesed Home Care | 3001 | com.coloradocareassist.hesedhomecare |
| Elite Trading | 3002 | com.coloradocareassist.elite-trading |
| PowderPulse | 3003 | com.coloradocareassist.powderpulse |
| Telegram Bot | - | com.coloradocareassist.telegram-bot |
| Health Monitor | - | com.coloradocareassist.health-monitor |
| Cloudflare Tunnel | - | com.cloudflare.cloudflared |
| PostgreSQL 17 | 5432 | homebrew.mxcl.postgresql@17 |

### Database
- **Connection:** `postgresql://careassist:careassist2026@localhost:5432/careassist`
- **82 tables** for portal, sales, recruiting, WellSky cache

### Remote Access
- **Tailscale:** `100.124.88.105` (jasons-mac-mini)
- **SSH:** `ssh shulmeister@100.124.88.105`

### Health Monitoring
- **Script:** `scripts/health-monitor.sh` (runs every 5 minutes)
- **Status:** `~/logs/health-status.json`
- **Alerts:** Telegram notifications for failures
- **Auto-Restart:** Failed services are automatically restarted

---

## API CREDENTIALS

All credentials are in `~/.gigi-env` and duplicated in LaunchAgent plists.

| API | Env Vars | Purpose |
|-----|----------|---------|
| **Anthropic** | `ANTHROPIC_API_KEY` | Claude AI for Gigi |
| **RingCentral** | `RINGCENTRAL_CLIENT_ID`, `_SECRET`, `_JWT_TOKEN` | SMS, voice, team chat |
| **WellSky** | `WELLSKY_CLIENT_ID`, `_SECRET`, `_AGENCY_ID` | Client/caregiver data |
| **Google (Portal)** | `GOOGLE_CLIENT_ID`, `_SECRET` | OAuth login |
| **Google (Work)** | `GOOGLE_WORK_CLIENT_ID`, `_SECRET`, `_REFRESH_TOKEN` | Calendar/email |
| **Retell** | `RETELL_API_KEY` | Voice AI |
| **Gemini** | `GEMINI_API_KEY` | SMS responses |
| **Brevo** | `BREVO_API_KEY` | Email marketing |

**IMPORTANT:** Never hardcode credentials. Always use `os.getenv()`.

---

## FILE STRUCTURE

```
careassist-unified/
├── CLAUDE.md              # This file - main reference
├── unified_app.py         # Entry point - mounts all sub-apps
├── portal/                # Portal web app (FastAPI)
│   └── portal_app.py      # Main portal routes
├── gigi/                  # Gigi AI assistant
│   ├── telegram_bot.py    # Telegram interface
│   ├── ringcentral_bot.py # RC chat/SMS monitoring
│   ├── main.py            # Retell voice webhooks
│   └── CONSTITUTION.md    # Gigi's operating laws
├── sales/                 # Sales CRM dashboard
├── recruiting/            # Recruiting dashboard (Flask)
├── services/              # Shared services
│   ├── wellsky_service.py # WellSky API integration
│   └── ringcentral_messaging_service.py
├── scripts/
│   ├── health-monitor.sh  # Service health monitoring
│   └── security-audit.sh  # Security checks
└── docs/                  # Additional documentation
```

---

## COMMON COMMANDS

```bash
# Check all services
launchctl list | grep -E "coloradocareassist|cloudflare|postgres"

# Check health status
cat ~/logs/health-status.json

# Restart a service
launchctl bootout gui/501/com.coloradocareassist.<service>
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.<service>.plist

# View logs
tail -f ~/logs/gigi-unified.log
tail -f ~/logs/telegram-bot.log

# Database access
/opt/homebrew/opt/postgresql@17/bin/psql -d careassist

# Test health endpoints
curl -s http://localhost:8765/health
curl -s https://portal.coloradocareassist.com/health
```

---

## ELITE AGENT TEAMS

Activate teams by saying "@team-name" or "team-name team":

| Team | Focus | Trigger |
|------|-------|---------|
| **Tech** | TypeScript, Python, infrastructure | `@tech-team` |
| **Marketing** | SEO, ads, email, analytics | `@marketing-team` |
| **Finance** | Billing, payroll, cash flow | `@finance-team` |
| **Ops** | Scheduling, compliance, HR | `@ops-team` |

---

## IF SOMETHING BREAKS

1. **Check health status:** `cat ~/logs/health-status.json`
2. **Check service status:** `launchctl list | grep coloradocareassist`
3. **Check logs:** `tail -50 ~/logs/<service>-error.log`
4. **Restart service:** Use launchctl bootout/bootstrap
5. **Check alerts:** `tail ~/logs/health-alerts.log`

---

## DEVELOPMENT WORKFLOW

### Before Making Changes
```bash
git pull origin main
curl -s http://localhost:8765/health
```

### After Making Changes
```bash
git add <specific-files>
git commit -m "fix(component): description"
git push origin main
```

### Restart Services After Code Changes
```bash
launchctl bootout gui/501/com.coloradocareassist.gigi-unified
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist
```

---

## HISTORY

- **Feb 4, 2026:** Consolidated API credentials, created health monitoring system, Claude Code integration for Gigi
- **Feb 2, 2026:** Completed Mac Mini self-hosted setup with local PostgreSQL, Cloudflare tunnel, Tailscale
