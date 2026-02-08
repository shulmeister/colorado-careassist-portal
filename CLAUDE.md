# CLAUDE.md — Colorado Care Assist Infrastructure

**Last Updated:** February 7, 2026
**Status:** ✅ FULLY SELF-HOSTED ON MAC MINI (with Staging Environment)

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

**Gigi is ONE unified AI** operating across two platforms:

### Communication Platforms

**Platform 1: RingCentral (307-459-8220) — Gigi's primary number**
The 307 number IS Gigi. All RingCentral channels share the same identity and should have the same capabilities.

| RC Channel | Technology | Handler | Tools | Status |
|------------|------------|---------|-------|--------|
| **Voice** | Retell AI Custom LLM | `voice_brain.py` | 21 tools | Working |
| **SMS** | RC message-store polling | `ringcentral_bot.py` | 15 tools | In Progress |
| **Direct Messages** | RC Glip API polling | `ringcentral_bot.py` | 15 tools | In Progress |
| **Team Chat** (New Scheduling) | RC Glip API polling | `ringcentral_bot.py` | 15 tools | In Progress |

**Platform 2: Telegram (@Shulmeisterbot) — Separate channel**

| Channel | Technology | Handler | Tools | Status |
|---------|------------|---------|-------|--------|
| **Telegram** | Telegram Bot API | `telegram_bot.py` | 15 tools | Working |

**Key Principle:** Telegram is the only separate channel. Everything else flows through RingCentral 307-459-8220 — call it, text it, DM her, @mention her in team chat — same Gigi.

### RC Text Channel Tools (15 — `ringcentral_bot.py`)
WellSky: `get_client_current_status`, `get_wellsky_clients`, `get_wellsky_caregivers`, `get_wellsky_shifts`, `log_call_out`, `identify_caller`
RingCentral: `check_recent_sms`, `send_sms`
General: `get_weather`, `web_search`, `get_stock_price`, `get_crypto_price`, `search_concerts`, `get_calendar_events`, `search_emails`

### Gigi's Core Capabilities
- **WellSky Integration**: Full CRUD on Patients, Practitioners, Appointments, Encounters, DocumentReferences, Subscriptions, ProfileTags, and RelatedPersons. Clock in/out, task logs, shift search, and webhook event subscriptions. See `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` for complete endpoint reference.
- **RingCentral**: SMS, voice, team messaging, DMs, inbound SMS monitoring
- **Google Workspace**: Calendar, email (read/write)
- **Auto-Documentation**: Syncs RC messages → WellSky client notes
- **After-Hours Coverage**: Autonomous SMS/voice handling
- **Morning Briefing**: Daily 7 AM Telegram message with weather, calendar, shifts, emails, alerts

### Gigi Multi-LLM Provider (Feb 7)
Both `telegram_bot.py` and `voice_brain.py` support 3 providers (Gemini, Anthropic, OpenAI).
- **Config:** `GIGI_LLM_PROVIDER=gemini` + `GIGI_LLM_MODEL=gemini-3-flash-preview`
- **Current production:** Gemini 3 Flash Preview — best tool calling + speed (~1.7s avg)
- Gemini API: use `Part(text=...)` NOT `Part.from_text(...)` (API changed)

### Retell Voice Brain (Feb 7 — VALIDATED)
- **Agent:** `agent_5b425f858369d8df61c363d47f` (Custom LLM, 11labs Susan)
- **Numbers:** +1-720-817-6600 (primary), +1-719-427-4641 (spare)
- **WebSocket:** `wss://portal.coloradocareassist.com/llm-websocket/{call_id}`
- **Critical rules:**
  - Ping/pong MUST be handled inline in receive loop (5s timeout → disconnect)
  - Cancel stale response tasks when new response_required arrives
  - Use asyncio.Lock on WebSocket sends
  - Send `tool_call_invocation`/`tool_call_result` for transcript visibility
  - Webhook signature: `from retell.lib.webhook_auth import verify` (NEVER custom HMAC)
- **Tested 6/6 tools:** concerts, weather, ski, flights, shifts, caregiver lookup — all passing
- **Retell batch test API does NOT support Custom LLM** — use dashboard simulation or phone call API

### Gigi's Constitution (Laws)
See `gigi/CONSTITUTION.md` for the 10 non-negotiable operating principles.

---

## INFRASTRUCTURE

### Services Running on Mac Mini

| Service | Port | LaunchAgent | URL |
|---------|------|-------------|-----|
| **Production Portal** | 8765 | com.coloradocareassist.gigi-unified | portal.coloradocareassist.com |
| **Staging Portal** | 8766 | com.coloradocareassist.staging | staging.coloradocareassist.com |
| Main Website | 3000 | com.coloradocareassist.website | coloradocareassist.com |
| Hesed Home Care | 3001 | com.coloradocareassist.hesedhomecare | hesedhomecare.org |
| Elite Trading | 3002 | com.coloradocareassist.elite-trading | elitetrading.coloradocareassist.com |
| PowderPulse | 3003 | com.coloradocareassist.powderpulse | powderpulse.coloradocareassist.com |
| Telegram Bot | - | com.coloradocareassist.telegram-bot | - |
| Cloudflare Tunnel | - | com.cloudflare.cloudflared | - |
| PostgreSQL 17 | 5432 | homebrew.mxcl.postgresql@17 | - |

### Staging vs Production

| Environment | Directory | Port | URL | Branch |
|-------------|-----------|------|-----|--------|
| **Production** | `~/mac-mini-apps/careassist-unified/` | 8765 | portal.coloradocareassist.com | `main` |
| **Staging** | `~/mac-mini-apps/careassist-staging/` | 8766 | staging.coloradocareassist.com | `staging` |

**CRITICAL: NEVER edit production directly. All development happens on staging first.**

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
| **Cloudflare** | `CF_API_TOKEN`, `CF_ZONE_ID` | DNS management |
| **Telegram** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Alerts & Gigi bot |

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
│   ├── voice_brain.py     # Retell Custom LLM WebSocket handler (multi-provider, 21 tools)
│   ├── telegram_bot.py    # Telegram interface (multi-provider, 15 tools)
│   ├── ringcentral_bot.py # RC polling, SMS, clock reminders, daily confirmations, morning briefing
│   ├── main.py            # Retell webhook handlers + signature verification
│   ├── morning_briefing_service.py  # 7 AM daily briefing via Telegram
│   ├── google_service.py  # Google Calendar + Gmail API (OAuth2)
│   ├── chief_of_staff_tools.py  # Shared tool implementations
│   └── CONSTITUTION.md    # Gigi's operating laws
├── sales/                 # Sales CRM dashboard
├── recruiting/            # Recruiting dashboard (Flask)
├── services/              # Shared services
│   ├── wellsky_service.py # WellSky API integration
│   └── ringcentral_messaging_service.py
├── scripts/
│   ├── health-monitor.sh  # Service health monitoring
│   ├── sync_wellsky_clients.py  # WellSky FHIR sync (every 2 hours)
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

## CLAUDE CODE SUBAGENTS

Custom subagents in `.claude/agents/`:

| Agent | Focus |
|-------|-------|
| **debugger** | Error analysis, log investigation, stack traces |
| **infra-ops** | Service health, LaunchAgents, ports, processes |
| **db-admin** | PostgreSQL schema, queries, migrations, integrity |
| **portal-dev** | FastAPI routes, templates, portal features |
| **gigi-dev** | Voice brain, Telegram, webhooks, tool calls |
| **reviewer** | Code review, staging/production diff |
| **security-auditor** | Vulnerability scanning, credential audit, network security |
| **performance-engineer** | Response times, DB queries, memory, CPU profiling |
| **chaos-engineer** | Resilience testing, failure scenarios, recovery verification |

### Elite Agent Teams (Legacy)

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

### The Golden Rule
**NEVER edit production directly.** All changes go through staging first.

### Step 1: Make Changes on Staging
```bash
cd ~/mac-mini-apps/careassist-staging
# Edit your code here...
```

### Step 2: Test on Staging
```bash
~/scripts/restart-staging.sh
# Then test at https://staging.coloradocareassist.com
```

### Step 3: Commit Changes
```bash
cd ~/mac-mini-apps/careassist-staging
git add <specific-files>
git commit -m "fix(component): description"
```

### Step 4: Promote to Production (only when ready!)
```bash
~/scripts/promote-to-production.sh
```

This script will:
1. Verify staging is healthy
2. Merge staging → main
3. Rebuild production
4. Restart production
5. Verify production is healthy

### Key Scripts

| Script | Purpose |
|--------|---------|
| `~/scripts/restart-staging.sh` | Rebuild and restart staging after code changes |
| `~/scripts/promote-to-production.sh` | Deploy tested staging code to production |
| `~/scripts/deep-health-check.sh` | Functional health checks (runs every 5 min via cron) |
| `~/scripts/watchdog.sh` | Backup monitor (runs every 2 min via cron) |
| `~/scripts/backup-to-gdrive.sh` | Daily DB dump + configs → Google Drive (3 AM) |
| `~/scripts/claude-task-worker.py` | Claude Code task bridge daemon |
| `~/scripts/sync_wellsky_clients.py` | WellSky FHIR sync (every 2 hours) |

### Cron Jobs (Automatic)
```bash
*/5 * * * * /Users/shulmeister/scripts/deep-health-check.sh
*/2 * * * * /Users/shulmeister/scripts/watchdog.sh
```

---

## BACKUP & DISASTER RECOVERY

- **Daily backup** at 3 AM via `~/scripts/backup-to-gdrive.sh` (LaunchAgent)
- **What's backed up:** PostgreSQL dump, `~/.gigi-env`, `~/.cloudflared/`, all LaunchAgent plists, all scripts (sh + py), Claude memory files
- **Destination:** Google Drive via rclone (`gdrive:MacMini-Backups`)
- **Retention:** 7 days local, unlimited on Google Drive
- **GitHub repos:** All 7 apps pushed to private repos on github.com/shulmeister

### Restore Procedure
1. Clone all repos from GitHub
2. Install PostgreSQL 17, restore: `pg_restore -d careassist ~/backups/careassist-YYYY-MM-DD.dump`
3. Extract configs: `tar -xzf configs-YYYY-MM-DD.tar.gz -C /`
4. Install Cloudflare Tunnel, Tailscale
5. Bootstrap LaunchAgents: `launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.*.plist`

---

## HISTORY

- **Feb 7, 2026 (evening):** Voice brain fully validated through Retell infrastructure. Fixed WebSocket ping/pong (was blocking → disconnect), added stale response cancellation, send lock, tool_call_invocation/result events. Multi-LLM provider support (Gemini/Anthropic/OpenAI) for voice and Telegram. Fixed Retell webhook signature (SDK verify, not custom HMAC). Fixed Gemini Part.from_text → Part(text=...). All 6 core tools tested: concerts, weather, ski, flights, shifts, caregiver lookup. Added morning briefing service (7 AM daily via Telegram).
- **Feb 7, 2026 (overnight):** Autonomous 5-agent audit: fixed SQL injection in simulation_service, undefined capture_memory, 14 connection leaks (6 files), missing imports (json/hmac/hashlib), 3 duplicate routes → /api/internal/wellsky/*, SQLAlchemy 2.0 fix, Sales CRM task model aliases, CompanyTasksList useState→useEffect, voice_brain open_only parity. WellSky sync confirmed 1,074 appointments (24 of 71 clients have zero appointments — WellSky-side gap).
- **Feb 7, 2026:** Fixed 11 CRM bugs (duplicate route, FK, contact/company ID collision, relative URLs, task types). Created 3 QA/security agents (security-auditor, performance-engineer, chaos-engineer). Pushed all 7 repos to GitHub. Fixed backup script to include .py files and Claude memory.
- **Feb 6, 2026:** Created 6 custom Claude Code subagents. Fixed 27 voice brain bugs (11 tools wrapped in run_sync, connection leaks, SQL injection). Added Claude Code task bridge. Upgraded web search to DuckDuckGo. Fixed WellSky composite IDs. Fixed Retell signature bypass. Created 3 missing portal templates. Fixed concierge page text contrast. Fixed PowderPulse portal routing. Fixed BTC rainbow chart stretching.
- **Feb 5, 2026:** Added staging environment (staging.coloradocareassist.com), deep health checks, promote-to-production workflow. NEVER edit production directly anymore.
- **Feb 5, 2026:** Unified Gigi voice brain (Claude-powered via Retell custom-llm WebSocket)
- **Feb 4, 2026:** Consolidated API credentials, created health monitoring system, Claude Code integration for Gigi
- **Feb 2, 2026:** Completed Mac Mini self-hosted setup with local PostgreSQL, Cloudflare tunnel, Tailscale
