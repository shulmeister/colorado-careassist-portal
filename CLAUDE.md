# CLAUDE.md — Colorado Care Assist Infrastructure

**Last Updated:** February 22, 2026
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

**Note:** PowderPulse was split out to a standalone service on port 3003 (Feb 14, 2026). Source still lives in `/powderpulse/` but runs independently via `powderpulse/server.py`. Portal `/powderpulse` redirects to `powderpulse.coloradocareassist.com`.

### Related Repositories & Standalone Services

| Repo | Port | URL | Description |
|------|------|-----|-------------|
| `careassist-unified` | 8765 | portal.coloradocareassist.com | This repo - unified platform |
| `coloradocareassist` | 3000 | coloradocareassist.com | Marketing website (Next.js) |
| `hesedhomecare` | 3001 | hesedhomecare.org | Hesed website (Next.js) |
| `elite-trading-mcp` | 3002 | elitetrading.coloradocareassist.com | Trading MCP server |
| **PowderPulse** | 3003 | powderpulse.coloradocareassist.com | Ski weather app (FastAPI + Vue.js SPA) |
| `weather-arb` | 3010 | - (localhost) | Weather Sniper Bot (Polymarket, PAPER TRADING) |
| `kalshi-weather` | 3011 | - (localhost) | Weather Sniper Bot (Kalshi, LIVE) |
| `kalshi-poly-arb` | 3013 | - (localhost) | Kalshi-Polymarket arb scanner |
| `status-dashboard` | 3012 | status.coloradocareassist.com | Infrastructure status dashboard |
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
| **Voice** | Retell AI Custom LLM | `voice_brain.py` | 33 tools | Working |
| **SMS** | RC message-store polling | `ringcentral_bot.py` | 15 tools | Working |
| **Direct Messages** | RC Glip API polling | `ringcentral_bot.py` | 31 tools | Working |
| **Team Chat** | RC Glip API polling | `ringcentral_bot.py` | 31 tools | Working |

**Other Channels**

| Channel | Technology | Handler | Tools | Status |
|---------|------------|---------|-------|--------|
| **Telegram** | Telegram Bot API | `telegram_bot.py` | 32 tools | Working |
| **Ask-Gigi API** | REST `/api/ask-gigi` | `ask_gigi.py` | 32 tools | Working |
| **Apple Shortcuts / Siri** | Shortcuts → ask-gigi API | `ask_gigi.py` | 32 tools | Working |
| **iMessage** | BlueBubbles webhook | `main.py` → `ask_gigi.py` | 32 tools | Code Done (needs BB GUI setup) |
| **Menu Bar** | SwiftUI → ask-gigi API | `ask_gigi.py` | 32 tools | Working |

### Ask-Gigi API (Feb 8 — Foundation for Apple integrations)
- **Endpoint:** `POST /gigi/api/ask-gigi` (served by gigi_app.py on port 8767)
- **Auth:** Bearer token via `GIGI_API_TOKEN` env var
- **Module:** `gigi/ask_gigi.py` — reuses GigiTelegramBot.execute_tool (no duplication)
- **All channels that use ask_gigi.py** get the same 32 tools (all Telegram tools)
- **Cross-channel context:** API messages visible from Telegram/SMS and vice versa

### Tool Sets
**Telegram tools (32):** `search_concerts`, `buy_tickets_request`, `book_table_request`, `get_client_current_status`, `get_calendar_events`, `search_emails`, `get_weather`, `get_wellsky_clients`, `get_wellsky_caregivers`, `get_wellsky_shifts`, `web_search`, `get_stock_price`, `get_crypto_price`, `create_claude_task`, `check_claude_task`, `save_memory`, `recall_memories`, `forget_memory`, `search_memory_logs`, `browse_webpage`, `take_screenshot`, `get_morning_briefing`, `get_ar_report`, `get_polybot_status`, `get_weather_arb_status`, `deep_research`, `watch_tickets`, `list_ticket_watches`, `remove_ticket_watch`, `clock_in_shift`, `clock_out_shift`, `find_replacement_caregiver`

**Voice tools (33):** All Telegram tools minus browser/morning_briefing/get_polybot_status, plus: `send_sms`, `send_team_message`, `send_email`, `lookup_caller`, `report_call_out`, `transfer_call`

**RC SMS tools (15):** `get_client_current_status`, `identify_caller`, `get_wellsky_shifts`, `get_wellsky_clients`, `get_wellsky_caregivers`, `log_call_out`, `save_memory`, `recall_memories`, `forget_memory`, `search_memory_logs`, `get_morning_briefing`, `get_ar_report`, `clock_in_shift`, `clock_out_shift`, `find_replacement_caregiver`

**RC DM/Team Chat tools (31):** Full Telegram-like set including browser tools + `check_recent_sms`, `send_sms`, `log_call_out`, `identify_caller`, `get_weather_arb_status`, `deep_research`, `watch_tickets`, `list_ticket_watches`, `remove_ticket_watch`, `clock_in_shift`, `clock_out_shift`, `find_replacement_caregiver`

### Gigi's Core Capabilities
- **WellSky Integration**: Full CRUD on Patients, Practitioners, Appointments, Encounters, DocumentReferences, Subscriptions, ProfileTags, and RelatedPersons. Clock in/out, task logs, shift search, and webhook event subscriptions. See `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` for complete endpoint reference.
- **RingCentral**: SMS, voice, team messaging, DMs, inbound SMS monitoring, fax send/receive
- **Google Workspace**: Calendar, email (read/write)
- **Fax**: Send/receive via RingCentral API (free with RingEX). Portal page with Inbox/Sent/Outbox tabs, multi-file upload, cover page/note, drag-and-drop page reorder, inline PDF preview. Gigi tools: `send_fax`, `check_fax_status`, `list_faxes`. Telegram + email alerts on inbound fax. Numbers: 719-428-3999, 303-757-1777.
- **Auto-Documentation**: Syncs RC messages → WellSky Care Alerts (TaskLog) + escalation Tasks (AdminTask)
- **After-Hours Coverage**: Autonomous SMS/voice handling
- **Morning Briefing**: Daily 7 AM Telegram message with weather, calendar, shifts, emails, alerts

### Gigi Multi-LLM Provider (Feb 7)
All 3 handlers (`telegram_bot.py`, `voice_brain.py`, `ringcentral_bot.py`) + `ask_gigi.py` support 3 providers.
- **Config:** `GIGI_LLM_PROVIDER=anthropic` + `GIGI_LLM_MODEL=claude-haiku-4-5-20251001`
- **Current production:** Anthropic Haiku 4.5 — all Gigi channels
- **Default models:** Gemini=`gemini-3-flash-preview`, Anthropic=`claude-haiku-4-5-20251001`, OpenAI=`gpt-5.1`
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

### Enterprise Readiness (Feb 19)
Five features built for production readiness with clients and employees:
1. **Clock In/Out Tools** — `clock_in_shift`, `clock_out_shift` across all channels (voice, SMS, Telegram, DM). Caregivers can clock in/out by talking to Gigi or texting.
2. **Transfer Call Rules** — Voice brain system prompt includes "When to Transfer Calls (CRITICAL)" section. Gigi transfers to a human for: emergencies, complaints, legal/HIPAA, billing, repeated failures (3+), explicit requests.
3. **Shift Filling Engine** — `find_replacement_caregiver` tool wired across all channels. Queries WellSky for available caregivers matching skills/availability, ranks by proximity and past performance.
4. **SMS Semantic Loop Detection** — `_detect_semantic_loop()` in RC bot. Detects when Gigi is repeating herself in SMS conversations (cosine similarity > 0.85 on last 3 messages). Breaks loop with escalation.
5. **Simulation Testing** — End-to-end voice simulation via portal Simulations tab. WebSocket-based tool capture (cross-process safe). Evaluator scores tool usage (40%) + conversation behavior (60%). Best score: 85/100 on weather/concert scenario.

### Ticket Watch System (Feb 16)
- **Purpose:** Monitors Ticketmaster + Bandsintown for concert/event on-sale dates. Sends Telegram alerts.
- **Tools:** `watch_tickets`, `list_ticket_watches`, `remove_ticket_watch` (all channels)
- **Polling:** RC bot checks every ~15 min. Ticketmaster Discovery API (5000 calls/day) + Bandsintown (catches AXS events).
- **Alerts:** New event found, 24h before on-sale, 15min before on-sale ("GET IN QUEUE NOW")
- **DB:** `gigi_ticket_watches` table with `notified_events` JSONB for deduplication

### Scheduled Outbound Messages
| Message | Time | Channel | Target | Env Flag |
|---------|------|---------|--------|----------|
| **Morning Briefing** | 7:00 AM MT | Telegram | Jason | `MORNING_BRIEFING_ENABLED` |
| **Clock In/Out Reminders** | Every 5 min (business hours) | SMS | Caregivers | `CLOCK_REMINDER_ENABLED` |
| **Shift Confirmations** | 2:00 PM MT | SMS | Caregivers | `DAILY_CONFIRMATION_ENABLED` |
| **Ticket Watch Alerts** | As needed (15 min polls) | Telegram | Jason | Always on (if watches exist) |
| **Task Completion Alerts** | As needed | Telegram | Jason | Always on |
| **Memory Decay** | 3:15 AM MT | Internal | DB only | Separate LaunchAgent |
| **Memory Logger** | 11:59 PM MT | Internal | Disk only | Separate LaunchAgent |

**Shadow Mode (current):** `CLOCK_REMINDER_ENABLED=false`, `DAILY_CONFIRMATION_ENABLED=false` — no outbound to caregivers.

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

## SALES DASHBOARD & WELLSKY LIFECYCLE

**Location:** `sales/` | **Port:** 8765 (portal) | **DB:** SQLite (`sales_tracker.db`) + portal PostgreSQL

### WellSky Prospect → Client Lifecycle

The Sales Dashboard is the source of truth for new leads. WellSky is the hub for operational data. They sync automatically:

| Sales Stage | WellSky Status | isClient | Trigger |
|---|---|---|---|
| Deal created (any stage) | New Lead (1) | false | `create_deal` route |
| Qualified | Initial Phone Call (10) | false | stage change |
| Assessment Scheduled | Assessment Scheduled (20) | false | stage change |
| Assessment Completed | Assessment Performed (30) | false | stage change |
| Proposal Sent | Expecting Signature (60) | false | stage change |
| Closed Won | Ready to Schedule (70) | true | stage change |
| Closed Lost | Lost | false | stage change |

**Implementation:**
- `services/sales_wellsky_sync.py` — `SalesWellSkySyncService` (singleton `sales_wellsky_sync`)
- `services/wellsky_service.py` — `WellSkyProspect`, `ProspectStatus` enum, `create_prospect()`, `update_prospect_status()`
- `sales/app.py` — `create_deal` fires `sync_deal_to_prospect()` in daemon thread; `update_deal` fires `sync_deal_stage_change()` in daemon thread on stage change
- Client Portal (`client-portal/backend/services/wellsky_client_adapter.py`) — `create_prospect()`, `update_prospect_status()`, `convert_prospect_to_client()` used when paperwork completes

**All sync is background (daemon threads)** — zero API latency impact. Errors logged as warnings, never surface to caller.

### Sales Dashboard Features (Feb 21, 2026)
- Face sheet scanner on Create Deal card (AI document parsing → pre-fill fields)
- Weekly/Monthly/YTD KPIs + Forecast Revenue on Summary dashboard
- Deal/Contact navigation buttons on Dashboard
- Stage history tracking (`stage_entered_at` timestamps)
- Brevo CRM bidirectional sync

---

## WEATHER SNIPER BOT (Polymarket — PAPER TRADING)

**Location:** `~/mac-mini-apps/weather-arb/` | **Port:** 3010 | **LaunchAgent:** `com.coloradocareassist.weather-arb`

### Strategy
Auto-snipes slam-dunk Polymarket temperature markets at daily market open:
1. NOAA forecasts pre-fetched for 6 US cities (T+2 date)
2. At 10:50 UTC, bot enters fast-poll mode (every 5s)
3. At 11:00 UTC, Polymarket releases new temperature events for T+2
4. Bot detects "X°F or higher" / "X°F or below" markets where NOAA forecast exceeds threshold by 5°F+
5. Places GTC limit buy at $0.22/share the instant each market starts accepting orders
6. Holds all positions to resolution (no auto-sell)
7. Telegram notifications for every snipe + hourly heartbeat

### Configuration (Feb 13, 2026)
- **Cities:** US only — nyc, chicago, seattle, atlanta, dallas, miami (NOAA reliable, 2-3°F RMSE)
- **Snipe price:** $0.22 | Max price: $0.35 | Budget: $25/market | Max total: $150
- **Margin required:** 5°F (forecast must beat threshold by this much)
- **Market timing:** Events created 11:00:00 UTC, accepting orders 3-17 min later (staggered by city)
- **Wallet:** `0x7c3d3D6557e5B00C9149739Ad1d4Fc088229238C` | Orders routed through `clob-proxy-ams.fly.dev`

### Key Files
| File | Purpose |
|------|---------|
| `sniper.py` | Core strategy: SlamDunk detection, margin check, order execution |
| `main.py` | FastAPI app + sniper_loop (continuous scan/execute cycle) |
| `config.py` | All config via WARB_* env vars |
| `trader.py` | CLOB order execution via Fly.io Amsterdam proxy |
| `weather.py` | NOAA (US) / Open-Meteo ECMWF (international) forecasts |
| `markets.py` | Gamma API market discovery, city matching, question parsing |
| `notifier.py` | Telegram alert delivery |

### API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Basic health check |
| GET | `/status` | Full sniper status (running, CLOB, config, orders, forecasts) |
| GET | `/forecasts` | Current forecasts for all cities on target date |
| GET | `/orders` | All sniper orders placed this session |
| GET | `/pnl` | Live P&L from Polymarket data API |
| POST | `/scan` | Trigger manual scan for slam dunks |
| POST | `/refresh-forecasts` | Force refresh all forecasts |

### Backtest Results (Feb 13-15, 2026)
- US cities (NOAA): 1 trade, +345% ROI — perfect accuracy
- International (ECMWF): 2 trades, -99% — Toronto forecast was 5°C+ off
- Decision: US cities only until ECMWF improves

---

## INFRASTRUCTURE

### Services Running on Mac Mini

| Service | Port | LaunchAgent | URL |
|---------|------|-------------|-----|
| **Production Portal** | 8765 | com.coloradocareassist.gigi-unified | portal.coloradocareassist.com |
| **Production Gigi** | 8767 | com.coloradocareassist.gigi-server | portal.coloradocareassist.com/gigi/* |
| **Staging Portal** | 8766 | com.coloradocareassist.staging | staging.coloradocareassist.com |
| **Staging Gigi** | 8768 | com.coloradocareassist.gigi-server-staging | staging.coloradocareassist.com/gigi/* |
| Main Website | 3000 | com.coloradocareassist.website | coloradocareassist.com |
| Hesed Home Care | 3001 | com.coloradocareassist.hesedhomecare | hesedhomecare.org |
| Elite Trading | 3002 | com.coloradocareassist.elite-trading | elitetrading.coloradocareassist.com |
| PowderPulse | 3003 | com.coloradocareassist.powderpulse | powderpulse.coloradocareassist.com (standalone FastAPI) |
| Weather Sniper Bot | 3010 | com.coloradocareassist.weather-arb | - (localhost only) |
| Kalshi Weather Bot | 3011 | com.coloradocareassist.kalshi-weather | - (localhost only) |
| Kalshi-Poly Arb | 3013 | com.coloradocareassist.kalshi-poly-arb | - (localhost only) |
| Status Dashboard | 3012 | com.coloradocareassist.status-dashboard | status.coloradocareassist.com |
| **Trading Dashboard** | 3014 | com.coloradocareassist.trading-dashboard | trading.coloradocareassist.com |
| **Gigi Doctor** | - | com.coloradocareassist.gigi-doctor | Proactive token refresh (every 6h) |
| Telegram Bot | - | com.coloradocareassist.telegram-bot | - |
| RingCentral Bot | - | com.coloradocareassist.gigi-rc-bot | - |
| Gigi Menu Bar | - | com.coloradocareassist.gigi-menubar | - |
| BlueBubbles | 1234 | com.bluebubbles.server | - (localhost only) |
| Clawd Gateway | 8080 | - | clawd.coloradocareassist.com |
| Memory Decay Cron | - | com.coloradocareassist.gigi-memory-decay | - (3:15 AM daily) |
| Memory Logger | - | com.coloradocareassist.gigi-memory-logger | - (11:59 PM daily) |
| Daily Backup | - | com.coloradocareassist.backup | - (3:00 AM daily) |
| Health Monitor | - | com.coloradocareassist.health-monitor | - (every 5 min) |
| WellSky Sync | - | com.coloradocareassist.wellsky-sync | - (every 2 hours) |
| Claude Task Worker | - | com.coloradocareassist.claude-task-worker | - |
| Cloudflare Tunnel | - | com.cloudflare.cloudflared | - |
| PostgreSQL 17 | 5432 | homebrew.mxcl.postgresql@17 | - |

### Staging vs Production

| Environment | Directory | Port | URL | Branch |
|-------------|-----------|------|-----|--------|
| **Production** | `~/mac-mini-apps/careassist-unified/` | 8765 | portal.coloradocareassist.com | `main` |
| **Staging** | `~/mac-mini-apps/careassist-staging/` | 8766 | staging.coloradocareassist.com | `staging` |

**CRITICAL: NEVER edit production directly. All development happens on staging first.**

### Database
- **Connection:** via `DATABASE_URL` env var (PostgreSQL 17, localhost:5432/careassist)
- **102 tables** for portal, sales, recruiting, WellSky cache, Gigi subsystems

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
├── unified_app.py         # Entry point - mounts portal, sales, recruiting
├── gigi_app.py            # Standalone Gigi service (port 8767/8768)
├── portal/                # Portal web app (FastAPI)
│   └── portal_app.py      # Main portal routes
├── gigi/                  # Gigi AI assistant
│   ├── voice_brain.py     # Retell Custom LLM WebSocket handler (multi-provider, 33 tools)
│   ├── telegram_bot.py    # Telegram interface (multi-provider, 32 tools)
│   ├── ringcentral_bot.py # RC polling, SMS (15 tools), DM/Team (31 tools), scheduled messages
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
│   ├── clock_reminder_service.py    # SMS clock in/out reminders to caregivers
│   ├── daily_confirmation_service.py # 2 PM shift confirmation SMS to caregivers
│   ├── ticket_monitor.py  # Ticketmaster + Bandsintown polling, Telegram alerts
│   ├── simulation_service.py  # Voice simulation runner (WebSocket-based)
│   ├── simulation_evaluator.py # Simulation scoring (tool 40% + behavior 60%)
│   ├── google_service.py  # Google Calendar + Gmail API (OAuth2)
│   ├── chief_of_staff_tools.py  # Shared tool implementations
│   └── CONSTITUTION.md    # Gigi's 10 operating laws
├── sales/                 # Sales CRM dashboard
├── recruiting/            # Recruiting dashboard (Flask)
├── powderpulse/           # Standalone ski weather app (NOT mounted in unified_app)
│   ├── server.py          # FastAPI standalone server (port 3003) + Liftie CORS proxy
│   ├── src/               # Vue.js source (NWS + ECMWF for US, met.no + ECMWF for intl)
│   └── dist/              # Built SPA (vite build)
├── services/              # Shared services
│   ├── wellsky_service.py # WellSky API integration (clients, caregivers, shifts, prospects)
│   ├── sales_wellsky_sync.py # Sales Dashboard → WellSky prospect lifecycle sync
│   ├── fax_service.py     # RingCentral fax send/receive/poll (replaces Fax.Plus)
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
tail -f ~/logs/gigi-server.log        # Gigi standalone service
tail -f ~/logs/gigi-server-error.log  # Gigi error log
tail -f ~/logs/telegram-bot.log

# Database access
/opt/homebrew/opt/postgresql@17/bin/psql -d careassist

# Test health endpoints
curl -s http://localhost:8765/health
curl -s https://portal.coloradocareassist.com/health
curl -s http://localhost:8767/gigi/health    # Gigi standalone health
```

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
5. Verify production is healthy (retries up to 60s for slow boots)

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

See `CHANGELOG.md` for detailed change history.
