# CLAUDE.md — Colorado Care Assist Infrastructure

**Last Updated:** February 8, 2026
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
| `elite-trading-mcp` | 3002 | elitetrading.coloradocareassist.com | Trading MCP server |
| `gigi-menubar` | - | - | macOS menu bar app (SwiftUI) |
| `gigi-backend-cca` | - | - | Legacy backend reference |
| `clawd` | - | - | Gigi config, elite teams, knowledge base |

---

## GIGI - THE AI CHIEF OF STAFF

**Gigi is ONE unified AI** operating across 6 channels:

### Communication Channels

**RingCentral (307-459-8220) — Gigi's primary number**

| Channel | Technology | Handler | Tools | Status |
|---------|------------|---------|-------|--------|
| **Voice** | Retell AI Custom LLM | `voice_brain.py` | 21 tools | Working |
| **SMS** | RC message-store polling | `ringcentral_bot.py` | 15 tools | In Progress |
| **Direct Messages** | RC Glip API polling | `ringcentral_bot.py` | 15 tools | In Progress |
| **Team Chat** | RC Glip API polling | `ringcentral_bot.py` | 15 tools | In Progress |

**Other Channels**

| Channel | Technology | Handler | Tools | Status |
|---------|------------|---------|-------|--------|
| **Telegram** | Telegram Bot API | `telegram_bot.py` | 21 tools | Working |
| **Ask-Gigi API** | REST `/api/ask-gigi` | `ask_gigi.py` | 19 tools | Working |
| **Apple Shortcuts / Siri** | Shortcuts → ask-gigi API | `ask_gigi.py` | 19 tools | Working |
| **iMessage** | BlueBubbles webhook | `main.py` → `ask_gigi.py` | 19 tools | Code Done (needs BB GUI setup) |
| **Menu Bar** | SwiftUI → ask-gigi API | `ask_gigi.py` | 19 tools | Working |

### Ask-Gigi API (Feb 8 — Foundation for Apple integrations)
- **Endpoint:** `POST /api/ask-gigi` (mounted at `/gigi/api/ask-gigi` via unified_app)
- **Auth:** Bearer token via `GIGI_API_TOKEN` env var
- **Module:** `gigi/ask_gigi.py` — reuses GigiTelegramBot.execute_tool (no duplication)
- **All channels that use ask_gigi.py** get the same 19 tools (all Telegram tools)
- **Cross-channel context:** API messages visible from Telegram/SMS and vice versa

### Tool Sets
**Shared tools (15):** `get_client_current_status`, `get_wellsky_clients`, `get_wellsky_caregivers`, `get_wellsky_shifts`, `log_call_out`, `identify_caller`, `get_weather`, `web_search`, `get_stock_price`, `get_crypto_price`, `search_concerts`, `get_calendar_events`, `search_emails`, `check_recent_sms`, `send_sms`

**Telegram/API extras (+6):** `save_memory`, `recall_memories`, `forget_memory`, `search_memory_logs`, `browse_webpage`, `take_screenshot`

**Voice-only extras (+6):** `send_sms`, `send_team_message`, `send_email`, `lookup_caller`, `report_call_out`, `transfer_call`

### Gigi's Core Capabilities
- **WellSky Integration**: Full CRUD on Patients, Practitioners, Appointments, Encounters, DocumentReferences, Subscriptions, ProfileTags, and RelatedPersons. Clock in/out, task logs, shift search, and webhook event subscriptions. See `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` for complete endpoint reference.
- **RingCentral**: SMS, voice, team messaging, DMs, inbound SMS monitoring
- **Google Workspace**: Calendar, email (read/write)
- **Auto-Documentation**: Syncs RC messages → WellSky client notes
- **After-Hours Coverage**: Autonomous SMS/voice handling
- **Morning Briefing**: Daily 7 AM Telegram message with weather, calendar, shifts, emails, alerts

### Gigi Multi-LLM Provider (Feb 7)
All 3 handlers (`telegram_bot.py`, `voice_brain.py`, `ringcentral_bot.py`) + `ask_gigi.py` support 3 providers.
- **Config:** `GIGI_LLM_PROVIDER=gemini` + `GIGI_LLM_MODEL=gemini-2.5-flash`
- **Current production:** Gemini 2.5 Flash — best tool calling + speed + NO API FEES
- **Default models:** Gemini=`gemini-2.5-flash`, Anthropic=`claude-sonnet-4-20250514`, OpenAI=`gpt-5.1`
- Gemini API: use `Part(text=...)` NOT `Part.from_text(...)` (API changed)

### Gigi Subsystems (Feb 8 — All Active)
- **Memory System** (`gigi/memory_system.py`): PostgreSQL `gigi_memories` + `gigi_memory_audit_log`. Tools: save_memory, recall_memories, forget_memory.
- **Mode Detector** (`gigi/mode_detector.py`): 8 modes (focus/execution/decision/travel/off_grid/crisis/thinking/review). Time-based auto-detection.
- **Failure Handler** (`gigi/failure_handler.py`): 10 protocols, meltdown detection (3 in 5 min). Wraps tool failures.
- **Conversation Store** (`gigi/conversation_store.py`): PostgreSQL `gigi_conversations`. Replaces in-memory dicts and JSON files.
- **Pattern Detector** (`gigi/pattern_detector.py`): Detects tool failure patterns, open shift trends, memory conflicts.
- **Self-Monitor** (`gigi/self_monitor.py`): Weekly audit of failures, memory stats, shift coverage.
- **Memory Logger** (`gigi/memory_logger.py`): Daily markdown journal at `~/.gigi-memory/YYYY-MM-DD.md`.
- **Constitutional Preamble**: 10 Operating Laws injected into ALL system prompts.
- **Dynamic System Prompts**: `_build_*_system_prompt()` builders inject memories + mode + date/time per-call.

### Browser Automation (Feb 8)
- **Module:** `gigi/browser_automation.py` — Playwright + headless Chromium
- **Tools:** `browse_webpage` (extract page text), `take_screenshot` (save PNG to `~/logs/screenshots/`)
- Available in Telegram + all ask-gigi API channels

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
| Gigi Menu Bar | - | com.coloradocareassist.gigi-menubar | - |
| Memory Decay Cron | - | com.coloradocareassist.gigi-memory-decay | - (3:15 AM daily) |
| Memory Logger | - | com.coloradocareassist.gigi-memory-logger | - (11:59 PM daily) |
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
| **Ask-Gigi API** | `GIGI_API_TOKEN` | Bearer token for /api/ask-gigi |
| **BlueBubbles** | `BLUEBUBBLES_URL`, `BLUEBUBBLES_PASSWORD` | iMessage bridge |

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
│   ├── telegram_bot.py    # Telegram interface (multi-provider, 21 tools)
│   ├── ringcentral_bot.py # RC polling, SMS, clock reminders, daily confirmations, morning briefing
│   ├── main.py            # Retell webhooks + /api/ask-gigi + /webhook/imessage
│   ├── ask_gigi.py        # Generic ask-gigi function (reuses telegram tools, no duplication)
│   ├── browser_automation.py  # Playwright headless Chromium (browse + screenshot)
│   ├── conversation_store.py  # PostgreSQL conversation persistence (all channels)
│   ├── memory_system.py   # Gigi's memory (save/recall/forget via PostgreSQL)
│   ├── mode_detector.py   # 8-mode auto-detection (focus, crisis, travel, etc.)
│   ├── failure_handler.py # 10 failure protocols + meltdown detection
│   ├── pattern_detector.py # Repeated failure + trend detection
│   ├── self_monitor.py    # Weekly self-audit (Monday morning briefing)
│   ├── memory_logger.py   # Daily markdown journal at ~/.gigi-memory/
│   ├── morning_briefing_service.py  # 7 AM daily briefing via Telegram
│   ├── google_service.py  # Google Calendar + Gmail API (OAuth2)
│   ├── chief_of_staff_tools.py  # Shared tool implementations
│   └── CONSTITUTION.md    # Gigi's 10 operating laws
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
| `~/scripts/gigi-memory-decay.py` | Memory decay cron (3:15 AM daily) |
| `~/scripts/create_gigi_shortcuts.py` | Apple Shortcuts generator for Siri integration |

### Cron Jobs (Automatic)
```bash
*/5 * * * * /Users/shulmeister/scripts/deep-health-check.sh
*/2 * * * * /Users/shulmeister/scripts/watchdog.sh
```

---

## BACKUP & DISASTER RECOVERY

- **Daily backup** at 3 AM via `~/scripts/backup-to-gdrive.sh` (LaunchAgent)
- **What's backed up:** PostgreSQL dump, `~/.gigi-env`, `~/.cloudflared/`, all LaunchAgent plists, all scripts (sh + py), Claude memory files, gigi-menubar source
- **Destination:** Google Drive via rclone (`gdrive:MacMini-Backups`)
- **Retention:** 7 days local, unlimited on Google Drive
- **GitHub repos:** All 8 apps pushed to private repos on github.com/shulmeister

### Restore Procedure
1. Clone all repos from GitHub
2. Install PostgreSQL 17, restore: `pg_restore -d careassist ~/backups/careassist-YYYY-MM-DD.dump`
3. Extract configs: `tar -xzf configs-YYYY-MM-DD.tar.gz -C /`
4. Install Cloudflare Tunnel, Tailscale
5. Bootstrap LaunchAgents: `launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.*.plist`

---

## HISTORY

- **Feb 8, 2026:** Gigi Phases 1-4 activated: Memory System (PostgreSQL-backed save/recall/forget), Mode Detector (8 modes), Failure Handler (10 protocols), Conversation Store (cross-channel PostgreSQL persistence replacing JSON files), Pattern Detector, Self-Monitor (weekly Monday audit), Memory Logger (daily journal). Constitutional preamble + dynamic system prompts for all handlers. Caregiver preference extractor. Memory decay cron (3:15 AM) + memory logger cron (11:59 PM).
- **Feb 8, 2026:** Apple Integration Phases 1-5: (1) Generic `/api/ask-gigi` REST endpoint with Bearer auth — reuses telegram tools with no code duplication. (2) 3 Apple Shortcuts for Siri ("Ask Gigi", "Morning Briefing", "Who's Working"). (3) iMessage channel via BlueBubbles webhook (code complete, needs BB GUI setup). (4) macOS Menu Bar app (SwiftUI, auto-start via LaunchAgent). (5) Browser automation with Playwright headless Chromium (browse_webpage + take_screenshot tools). All 8 repos pushed to GitHub. gigi-menubar repo created. Backup script updated.
- **Feb 7, 2026 (evening):** Voice brain fully validated through Retell infrastructure. Fixed WebSocket ping/pong (was blocking → disconnect), added stale response cancellation, send lock, tool_call_invocation/result events. Multi-LLM provider support (Gemini/Anthropic/OpenAI) for voice and Telegram. Fixed Retell webhook signature (SDK verify, not custom HMAC). Fixed Gemini Part.from_text → Part(text=...). All 6 core tools tested: concerts, weather, ski, flights, shifts, caregiver lookup. Added morning briefing service (7 AM daily via Telegram).
- **Feb 7, 2026 (overnight):** Autonomous 5-agent audit: fixed SQL injection in simulation_service, undefined capture_memory, 14 connection leaks (6 files), missing imports (json/hmac/hashlib), 3 duplicate routes → /api/internal/wellsky/*, SQLAlchemy 2.0 fix, Sales CRM task model aliases, CompanyTasksList useState→useEffect, voice_brain open_only parity. WellSky sync confirmed 1,074 appointments (24 of 71 clients have zero appointments — WellSky-side gap).
- **Feb 7, 2026:** Fixed 11 CRM bugs (duplicate route, FK, contact/company ID collision, relative URLs, task types). Created 3 QA/security agents (security-auditor, performance-engineer, chaos-engineer). Pushed all 7 repos to GitHub. Fixed backup script to include .py files and Claude memory.
- **Feb 6, 2026:** Created 6 custom Claude Code subagents. Fixed 27 voice brain bugs (11 tools wrapped in run_sync, connection leaks, SQL injection). Added Claude Code task bridge. Upgraded web search to DuckDuckGo. Fixed WellSky composite IDs. Fixed Retell signature bypass. Created 3 missing portal templates. Fixed concierge page text contrast. Fixed PowderPulse portal routing. Fixed BTC rainbow chart stretching.
- **Feb 5, 2026:** Added staging environment (staging.coloradocareassist.com), deep health checks, promote-to-production workflow. NEVER edit production directly anymore.
- **Feb 5, 2026:** Unified Gigi voice brain (Claude-powered via Retell custom-llm WebSocket)
- **Feb 4, 2026:** Consolidated API credentials, created health monitoring system, Claude Code integration for Gigi
- **Feb 2, 2026:** Completed Mac Mini self-hosted setup with local PostgreSQL, Cloudflare tunnel, Tailscale
