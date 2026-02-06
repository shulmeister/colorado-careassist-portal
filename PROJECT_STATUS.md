# Colorado Care Assist Portal - System Status

**Last Updated:** February 6, 2026 5:00 PM
**Status:** 🔴 UNSTABLE

---

## RELATED DOCUMENTATION

| Document | Location |
|----------|----------|
| `CLAUDE.md` | `~/mac-mini-apps/careassist-unified/CLAUDE.md` |
| `gigi/CONSTITUTION.md` | `~/mac-mini-apps/careassist-unified/gigi/CONSTITUTION.md` |
| `gigi/STATUS.md` | `~/mac-mini-apps/careassist-unified/gigi/STATUS.md` |
| `PHONE_NUMBER_STATUS.md` | `~/mac-mini-apps/careassist-unified/PHONE_NUMBER_STATUS.md` |
| `VOICE_AGENT_FIX_GUIDE.md` | `~/mac-mini-apps/careassist-unified/VOICE_AGENT_FIX_GUIDE.md` |
| `WELLSKY_LOGGING_UPDATE.md` | `~/mac-mini-apps/careassist-unified/WELLSKY_LOGGING_UPDATE.md` |

---

## PLATFORM OVERVIEW

**Host:** Mac Mini M2, macOS 15.2, Tailscale IP: 100.124.88.105
**Database:** PostgreSQL 17, port 5432
**Tunnel:** Cloudflare

**Services:**
- Portal (production: 8765, staging: 8766)
- Gigi AI (voice, SMS, Telegram)
- Sales CRM
- Recruiting dashboard

---

## CRITICAL ISSUES

### 1. Production Portal Crashes

**Frequency:** Multiple per day
**Last Crash:** Feb 6, 2026 16:34

**Log Pattern:**
```
[timestamp] [INFO] Handling signal: term
[timestamp] [INFO] Shutting down
[timestamp] [INFO] Error while closing socket [Errno 9] Bad file descriptor
[timestamp] [INFO] connection closed
[timestamp] [INFO] Application shutdown complete.
```

**Observations:**
- TERM signal received (source unknown)
- Clean shutdown
- Manual restart required via launchctl

**Logs:** `~/logs/gigi-unified.log`, `~/logs/gigi-unified-error.log`

---

### 2. Telegram Bot Crash Loop

**Frequency:** Every 10-60 minutes
**Error:**
```python
telegram.error.Conflict: Conflict: terminated by other getUpdates request;
make sure that only one bot instance is running
```

**Cycle:**
1. Bot starts
2. Operates 10-60 minutes
3. Conflict error
4. LaunchAgent restart
5. Repeat

**Mitigation Attempts (all temporary):**
- Process kill
- Webhook clear
- Pending updates clear

**Log:** `~/logs/telegram-bot.log`

---

### 3. Voice Call Silent Failures

**Symptom:** Call connects, Gigi greets, then silence mid-conversation

**Working:**
- Bitcoin/stock queries (<1s, Brave Search)
- Caller ID lookup
- Simple conversation

**Failing:**
- WellSky client queries (despite <100ms cache)
- Some web searches
- Multi-tool operations

**Code:** `gigi/voice_brain.py` - async/sync execution mismatch

---

### 4. Gigi Identity Confusion

**Current Configuration (Feb 6, 2026 4:45 PM):**

**Retell:**
- Agent: `agent_5b425f858369d8df61c363d47f` (Voice Brain Custom LLM) - **ONLY ONE**
- Phone: +1-720-817-6600

**RingCentral:**
- Phone: 307-459-8220 → forwards to 720-817-6600

**Telegram:** @Shulmeisterbot

**Deleted Agents (still referenced in docs):**
- `agent_d5c3f32bdf48fa4f7f24af7d36`
- `agent_e54167532428a1bc72c3375417`

**Example Confusion (Feb 6, 2026):**
```
User: "what's your phone number"
Gigi: "I don't have a phone number... I'm Gigi v2, text-based..."
```
Actual: Gigi answers 720-817-6600, handles 307 forwards

**System Prompt Locations:**
- Telegram: `gigi/telegram_bot.py` line 260-320 (updated Feb 6)
- Voice Brain: `gigi/voice_brain.py` line 165-290 (not updated)
- SMS: `gigi/ringcentral_bot.py` (uses Gemini)

---

### 5. WellSky Appointments API

**Status:** Returns 0 records consistently

**API Tests:**
```python
# Test 1: month_no
search_appointments(client_id="8379744", month_no="202602")
→ Response: 200 OK
→ Body: {"resourceType": "Bundle", "entry": []}

# Test 2: date range
search_appointments(client_id="8379744", start_date="2026-02-01", additional_days=6)
→ Response: 200 OK
→ Body: {"resourceType": "Bundle", "entry": []}

# Test 3: GET without filters
GET /v1/appointments/?date=ge2026-01-30
→ Response: 403 Forbidden

# Test 4: Multiple client IDs
Tested: 8379744, [5 other IDs]
→ All return empty Bundle
```

**Sync Attempts:**

| Date/Time | Change | Result |
|-----------|--------|--------|
| Feb 6 morning | Created cached_appointments table | 0 records |
| Feb 6 morning | Updated sync script | 0 records |
| Feb 6 afternoon | Changed to 2-hour sync | 0 records |
| Feb 6 afternoon | month_no query format | 0 records |
| Feb 6 afternoon | Multiple client ID tests | 0 records |

**Database State:**
```sql
SELECT COUNT(*) FROM cached_appointments;
→ 0
```

**API Endpoint:** `POST /v1/appointment/_search/`
**Credentials:** OAuth2, client_id/secret configured
**Agency ID:** 4505

---

### 6. Client Count Mismatch

**Cache:**
```sql
SELECT COUNT(*) FROM cached_patients WHERE is_active = true;
→ 71
```

**Expected (per WellSky export):** 51 (Deactivated = False)

**Discrepancy:** 20 clients

**Sync Method:**
- 676 API calls (2-letter last name combinations)
- Filters by `active=true` in FHIR response
- Last sync: Feb 6, 2026 16:29

---

### 7. Sales Dashboard Routing

**Recurring Issue:** API 404 errors, missing `/sales` prefix

**Timeline:**

| Date | Component | Error | Fix |
|------|-----------|-------|-----|
| Feb 5 | Task creation | 404 | Added /sales prefix |
| Feb 5 | Pagination | 404 | Fixed API routing |
| Feb 6 AM | Upcoming Tasks | 404 | Updated data provider |
| Feb 6 AM | Hot Contacts | 404 | Same fix |
| Feb 6 PM | Company tasks | Incorrect data | Reverted JOIN |

**URL Patterns in Codebase:**
- `/admin/...`
- `/sales/admin/...`
- `admin/...`
- Relative paths

**Current Status:** Working (Feb 6, 4:40 PM)

---

## RETELL CONFIGURATION

**Agent ID:** `agent_5b425f858369d8df61c363d47f`
**Type:** custom-llm
**Voice:** Susan
**WebSocket URL:** `wss://portal.coloradocareassist.com/llm-websocket`

**Settings:**
- ambient_sound: "call-center" (0.3 volume)
- enable_backchannel: true
- backchannel_frequency: 0.8

**Phone Association:**
- +1-720-817-6600 → agent_5b425f858369d8df61c363d47f

**Webhook Status:**
- Call started: Configured
- Call ended: Configured
- WebSocket: Active

---

## WELLSKY API STATUS

**Base URL:** `https://connect.clearcareonline.com/v1`
**Auth:** OAuth2 client credentials
**Agency:** 4505

**Endpoint Status:**

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/patients/` | GET | ✅ Working | Requires query params |
| `/patients/_search/` | POST | ⚠️ Active filter buggy | Use GET instead |
| `/practitioners/_search/` | POST | ✅ Working | active=true works |
| `/appointment/_search/` | POST | ❌ Returns 0 | All queries empty |
| `/relatedperson/{id}/` | GET | ✅ Working | Per-patient query |

**Last Successful Sync (Feb 6, 16:29):**
- Clients: 71
- Caregivers: 56
- Family contacts: 93
- Appointments: 0

**Sync Log:**
```
2026-02-06 16:28:30 - Found 71 active clients
2026-02-06 16:28:31 - Found 55 active hired caregivers
2026-02-06 16:29:26 - Synced 93 family contacts
2026-02-06 16:29:26 - Synced 0 appointments
```

---

## RINGCENTRAL STATUS

**Primary Number:** 307-459-8220
**Extension:** 111 (Gigi)

**Call Forwarding:**
- Destination: +1-720-817-6600 (Retell)
- Status: Active

**API Integration:**
- SMS: Active
- Team messaging: Active
- Voice: Forwarded (not using RC voice API)

**Credentials:** JWT token configured in `~/.gigi-env`

---

## TELEGRAM STATUS

**Bot:** @Shulmeisterbot
**Token:** Configured in `~/.gigi-env`

**Mode:** Polling (getUpdates)
**Webhook:** Cleared (not configured)
**Endpoint:** `/gigi/telegram-webhook` does not exist

**Conflict Error Status:** Ongoing
**LaunchAgent:** `com.coloradocareassist.telegram-bot`
**Restart Behavior:** Automatic on crash

---

## DATABASE CACHE STATUS

**Connection:** `postgresql://careassist:careassist2026@localhost:5432/careassist`

**WellSky Cache Tables:**

| Table | Records | Last Sync |
|-------|---------|-----------|
| cached_patients | 71 active | Feb 6, 16:28 |
| cached_practitioners | 56 active | Feb 6, 16:28 |
| cached_related_persons | 93 | Feb 6, 16:29 |
| cached_appointments | 0 | Feb 6, 16:29 |

**Sync Schedule:** Every 2 hours (LaunchAgent: `com.coloradocareassist.wellsky-sync`)
**Sync Script:** `~/mac-mini-apps/careassist-unified/scripts/sync_wellsky_clients.py`

---

## LAUNCHAGENT STATUS

**Running Services:**

| Service | LaunchAgent | Port | Status |
|---------|-------------|------|--------|
| Production Portal | com.coloradocareassist.gigi-unified | 8765 | Running (crashes periodically) |
| Staging Portal | com.coloradocareassist.staging | 8766 | Running |
| Telegram Bot | com.coloradocareassist.telegram-bot | - | Running (crash loop) |
| WellSky Sync | com.coloradocareassist.wellsky-sync | - | Every 2 hours |
| Cloudflare Tunnel | com.cloudflare.cloudflared | - | Running |
| PostgreSQL | homebrew.mxcl.postgresql@17 | 5432 | Running |

**Check Status:**
```bash
launchctl list | grep -E "coloradocareassist|cloudflare|postgres"
```

---

## LOG LOCATIONS

```
~/logs/
├── gigi-unified.log              # Production stdout
├── gigi-unified-error.log        # Production stderr
├── staging.log                   # Staging stdout
├── staging-error.log             # Staging stderr
├── telegram-bot.log              # Telegram bot
├── wellsky-sync.log              # WellSky sync
└── health-status.json            # Health monitor
```

---

## ENVIRONMENT VARIABLES

**Location:** `~/.gigi-env`

**Critical Keys:**
- `ANTHROPIC_API_KEY` - Claude API
- `RETELL_API_KEY` - Retell voice
- `WELLSKY_CLIENT_ID` / `WELLSKY_CLIENT_SECRET` - WellSky OAuth
- `RINGCENTRAL_JWT_TOKEN` - RingCentral
- `TELEGRAM_BOT_TOKEN` - Telegram
- `BRAVE_API_KEY` - Brave Search (added Feb 6)
- `GEMINI_API_KEY` - Gemini (SMS)
- `DATABASE_URL` - PostgreSQL

**Loading:** Scripts load via:
```bash
source ~/.gigi-env  # Some scripts
# or
with open('~/.gigi-env') as f: ...  # Python scripts
```

---

## GIT REPOSITORY STATE

**Production:** `~/mac-mini-apps/careassist-unified/` (main branch)
**Staging:** `~/mac-mini-apps/careassist-staging/` (staging branch)

**Recent Commits (main):**
```
3737fae docs: Add comprehensive project status documentation
c163bb8 feat(gigi): WellSky caching + Brave Search
e4776ac WIP: saving local changes before merge
e068df4 fix(sales): Link company tasks
```

**Uncommitted Changes:** None (as of Feb 6, 5:00 PM)

---

## VOICE BRAIN WEBSOCKET

**Endpoint:** `/llm-websocket/{call_id}`
**Handler:** `gigi/voice_brain.py` class `VoiceBrainHandler`
**Model:** Claude Sonnet 4.5 (`claude-sonnet-4-20250514`)

**Protocol:**
1. Retell sends call_details message
2. Voice Brain responds with greeting
3. Retell sends user speech transcripts
4. Voice Brain processes with Claude + tools
5. Returns response text
6. Retell converts to speech

**Tool Execution:** Synchronous in async context
**Timeout:** Unknown (suspected <5 seconds from Retell)

**Available Tools:**
- lookup_caller
- get_wellsky_clients (cached)
- get_wellsky_caregivers (cached)
- get_wellsky_shifts (cached, returns 0)
- web_search (Brave → DDG fallback)
- get_crypto_price
- get_stock_price
- send_sms
- transfer_call
- search_google_drive

---

## BRAVE SEARCH INTEGRATION

**Added:** Feb 6, 2026
**API Key:** Configured in `~/.gigi-env`
**Endpoint:** `https://api.search.brave.com/res/v1/web/search`

**Implementation:** `gigi/voice_brain.py` lines 464-491
**Fallback:** DuckDuckGo if Brave fails
**Timeout:** 3 seconds

**Status:** Working for web queries

---

## HEALTH MONITORING

**Scripts:**
- `~/scripts/deep-health-check.sh` - Every 5 minutes (cron)
- `~/scripts/watchdog.sh` - Every 2 minutes (cron)

**Status File:** `~/logs/health-status.json`
**Alerts:** Telegram notifications

**Monitored:**
- Portal health endpoints
- Service process status
- Database connectivity

**Recovery:** Automatic restart on failure (may contribute to crashes)

---

**END OF STATUS DOCUMENT**
