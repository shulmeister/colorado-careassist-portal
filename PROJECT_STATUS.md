# Colorado Care Assist Portal - Project Status

**Last Updated:** February 6, 2026
**Status:** 🟡 PARTIALLY FUNCTIONAL - Major issues with voice AI and data sync

---

## EXECUTIVE SUMMARY

The portal is a unified platform running on a Mac Mini (M2, macOS 15.2) hosting:
- Main web dashboard (portal)
- Gigi AI assistant (voice, SMS, Telegram)
- Sales CRM
- Recruiting dashboard
- Marketing sites

**Critical Issues:**
1. ❌ Gigi voice calls experience random disconnects and silent failures
2. ❌ WellSky appointments/shifts API returns 0 records despite valid requests
3. ⚠️ Client count mismatch (cache: 71, expected: 51)
4. ⚠️ Voice calls timeout on any query taking >5 seconds (partially mitigated)

---

## ARCHITECTURE OVERVIEW

### Infrastructure
- **Host:** Mac Mini M2, macOS 15.2, Tailscale IP: 100.124.88.105
- **Database:** PostgreSQL 17 (local, port 5432)
- **Tunnel:** Cloudflare tunnel for public access
- **Domains:**
  - portal.coloradocareassist.com (production, port 8765)
  - staging.coloradocareassist.com (staging, port 8766)

### Repository Structure
```
~/mac-mini-apps/
├── careassist-unified/     # Production (main branch, port 8765)
└── careassist-staging/     # Staging (staging branch, port 8766)
```

### Key Services (LaunchAgents)
| Service | Port | LaunchAgent | Status |
|---------|------|-------------|---------|
| Production Portal | 8765 | com.coloradocareassist.gigi-unified | ✅ Running |
| Staging Portal | 8766 | com.coloradocareassist.staging | ✅ Running |
| Telegram Bot | - | com.coloradocareassist.telegram-bot | ✅ Running |
| WellSky Sync | - | com.coloradocareassist.wellsky-sync | ✅ Every 2 hours |
| Cloudflare Tunnel | - | com.cloudflare.cloudflared | ✅ Running |
| PostgreSQL 17 | 5432 | homebrew.mxcl.postgresql@17 | ✅ Running |

---

## GIGI AI ASSISTANT

### Overview
Gigi is a Claude-powered AI assistant operating across multiple channels:
- **Voice:** Retell AI (phone: 307-459-8220 → 720-817-6600)
- **SMS:** RingCentral + Gemini (307-459-8220)
- **Telegram:** @Shulmeisterbot
- **Team Chat:** RingCentral Glip monitoring

### Voice System Architecture

#### Components
1. **Retell AI** - Voice interface provider
   - Agent ID: `agent_5b425f858369d8df61c363d47f`
   - Type: `custom-llm` (WebSocket-based)
   - Voice: Susan
   - Phone: +1-720-817-6600 (Retell number)
   - Forward: +1-307-459-8220 (RingCentral, forwards to Retell)

2. **Voice Brain** - Custom LLM backend
   - File: `gigi/voice_brain.py`
   - Endpoint: `wss://portal.coloradocareassist.com/llm-websocket/{call_id}`
   - WebSocket handler in `unified_app.py` line 349
   - Uses Claude Sonnet 4.5 (`claude-sonnet-4-20250514`)

3. **Tool Execution**
   - Synchronous tool calls during conversation
   - No streaming or multi-turn support
   - Tools must complete in <5 seconds to avoid Retell timeout

#### Current Configuration
```python
# Retell Agent Settings (as of Feb 6, 2026)
- ambient_sound: "call-center" (0.3 volume)
- enable_backchannel: true
- backchannel_frequency: 0.8
- backchannel_words: ["mhm", "uh-huh", "I see", "mm-hmm"]
- agent_version: 2
- WebSocket URL: wss://portal.coloradocareassist.com/llm-websocket
  (Note: No {call_id} placeholder - was causing URL encoding issues)
```

### Available Tools

| Tool | Purpose | Data Source | Response Time |
|------|---------|-------------|---------------|
| `lookup_caller` | Identify caller by phone | cached_patients, cached_practitioners | <100ms ✅ |
| `get_wellsky_clients` | Search clients | cached_patients (PostgreSQL) | <100ms ✅ |
| `get_wellsky_caregivers` | Search caregivers | cached_practitioners (PostgreSQL) | <100ms ✅ |
| `get_wellsky_shifts` | Get appointments | cached_appointments (PostgreSQL) | <100ms but returns 0 ❌ |
| `web_search` | Web queries | Brave Search API → DDG fallback | <1s ✅ |
| `get_crypto_price` | Crypto prices | CoinGecko API | ~1s ✅ |
| `get_stock_price` | Stock prices | Yahoo Finance API | ~1s ✅ |
| `send_sms` | Send text message | RingCentral API | ~1s ✅ |
| `transfer_call` | Transfer to human | Retell transfer | Instant ✅ |
| `search_google_drive` | Search Drive files | Google Drive API | 3-10s ⚠️ |

---

## WELLSKY INTEGRATION

### API Details
- **Provider:** WellSky Personal Care Connect (formerly ClearCare)
- **Protocol:** FHIR-compliant REST API
- **Base URL:** `https://connect.clearcareonline.com/v1`
- **Auth:** OAuth2 client credentials
- **Agency ID:** 4505

### Credentials (in ~/.gigi-env)
```bash
WELLSKY_CLIENT_ID=<configured>
WELLSKY_CLIENT_SECRET=<configured>
WELLSKY_AGENCY_ID=4505
WELLSKY_ENVIRONMENT=production
```

### Available Endpoints

| Resource | Endpoint | Method | Works? | Notes |
|----------|----------|--------|--------|-------|
| Patients (Clients) | `/v1/patients/` | GET | ✅ Yes | Requires query params |
| Patients Search | `/v1/patients/_search/` | POST | ✅ Yes | Active filter buggy, use GET |
| Practitioners (Caregivers) | `/v1/practitioners/_search/` | POST | ✅ Yes | Works with active=true |
| Appointments (Shifts) | `/v1/appointment/_search/` | POST | ❌ RETURNS 0 | See issue #1 |
| Related Persons (Family) | `/v1/relatedperson/{patient_id}/` | GET | ✅ Yes | Per-patient query |

### FHIR Resource Mapping
```
WellSky Term     → FHIR Resource    → Our Cache Table
─────────────────────────────────────────────────────────
Clients          → Patient          → cached_patients
Caregivers       → Practitioner     → cached_practitioners
Family Contacts  → RelatedPerson    → cached_related_persons
Shifts/Visits    → Appointment      → cached_appointments
```

---

## WELLSKY POSTGRESQL CACHE

### Purpose
Cache WellSky data locally to avoid 30+ second API delays during voice calls.

### Sync Schedule
- **Frequency:** Every 2 hours (7200 seconds)
- **LaunchAgent:** `com.coloradocareassist.wellsky-sync`
- **Script:** `~/mac-mini-apps/careassist-unified/scripts/sync_wellsky_clients.py`
- **Logs:** `~/logs/wellsky-sync.log`

### Cache Tables

#### 1. cached_patients (Clients)
```sql
Columns: id, first_name, last_name, full_name, phone, home_phone, work_phone,
         email, address, city, state, zip_code, status, is_active,
         start_date, emergency_contact_name, emergency_contact_phone,
         referral_source, notes, wellsky_data, synced_at, updated_at

Current Count: 71 active clients
Expected Count: 51 (per user's Excel export with Deactivated=False)
Discrepancy: 20 extra clients (❌ ISSUE #3)

Indexes:
- PRIMARY KEY (id)
- idx_cached_patients_full_name ON (full_name)
- idx_cached_patients_phone ON (phone, home_phone, work_phone)
```

#### 2. cached_practitioners (Caregivers)
```sql
Columns: id, first_name, last_name, full_name, phone, home_phone, work_phone,
         email, address, city, state, zip_code, status, is_hired, is_active,
         hire_date, preferred_language, languages, skills, certifications,
         notes, external_id, wellsky_data, synced_at, updated_at

Current Count: 56 active hired caregivers
Status: ✅ Working correctly

Indexes:
- PRIMARY KEY (id)
- idx_cached_practitioners_full_name ON (full_name)
- idx_cached_practitioners_phone ON (phone)
```

#### 3. cached_related_persons (Family Contacts)
```sql
Columns: id, patient_id, first_name, last_name, full_name, relationship,
         phone, home_phone, work_phone, email, city, state,
         is_emergency_contact, is_primary_contact, is_payer, is_poa,
         is_active, wellsky_data, synced_at, updated_at

Current Count: 93 family contacts
Status: ✅ Working correctly

Indexes:
- PRIMARY KEY (id)
- idx_cached_related_persons_patient ON (patient_id)
```

#### 4. cached_appointments (Shifts) ❌ BROKEN
```sql
Columns: id, patient_id, practitioner_id, scheduled_start, scheduled_end,
         actual_start, actual_end, status, service_type, location_address,
         notes, wellsky_data, synced_at, updated_at

Current Count: 0 (❌ ALWAYS ZERO)
Expected: Hundreds of shifts for current + next month

Indexes:
- PRIMARY KEY (id)
- idx_cached_appt_patient ON (patient_id)
- idx_cached_appt_practitioner ON (practitioner_id)
- idx_cached_appt_scheduled ON (scheduled_start, scheduled_end)
- idx_cached_appt_status ON (status)
```

### Sync Process Flow

#### 1. Client Sync (✅ Working)
```python
# Method: GET /v1/patients/?last_name:contains=XX
# Searches all 676 two-letter combinations (Aa, Ab, Ac, ... Zz)
# Filters: active=true from response data
# Time: ~6 minutes for full sync
# Result: 71 clients cached
```

#### 2. Caregiver Sync (✅ Working)
```python
# Method: POST /v1/practitioners/_search/
# Payload: {"active": "true", "is_hired": "true"}
# Time: ~1 second
# Result: 55-56 caregivers cached
```

#### 3. Family Contacts Sync (✅ Working)
```python
# Method: GET /v1/relatedperson/{patient_id}/ for each client
# Loops through all 71 active clients
# Time: ~1 minute
# Result: 93 family contacts cached
```

#### 4. Appointments Sync (❌ BROKEN)
```python
# Attempted Methods:
# 1. GET /v1/appointments/?date=ge2026-01-30&date=le2026-02-20
#    Result: 403 Forbidden
#
# 2. POST /v1/appointment/_search/
#    Payload: {"clientId": "8379744", "monthNo": "202602"}
#    Result: 200 OK but 0 entries in response
#
# 3. Tested with multiple client IDs, all return 0 appointments
#
# Current Implementation:
# - Loops through all 71 active clients
# - Queries current month + next month for each client
# - Time: ~1-2 minutes
# - Result: ALWAYS 0 appointments synced
```

### Sync Logs (Latest Run - Feb 6, 2026 16:29)
```
2026-02-06 16:22:09,305 - INFO - --- Syncing active clients ---
2026-02-06 16:28:30,639 - INFO - Found 71 active clients
2026-02-06 16:28:30,701 - INFO - --- Syncing active caregivers ---
2026-02-06 16:28:31,477 - INFO - Found 55 active hired caregivers
2026-02-06 16:28:31,506 - INFO - --- Syncing family contacts for 71 clients ---
2026-02-06 16:29:26,587 - INFO - Synced 93 family contacts
2026-02-06 16:29:26,590 - INFO - --- Syncing appointments/shifts ---
2026-02-06 16:29:26,743 - ERROR - Appointment fetch failed: 403  ← OLD CODE
2026-02-06 16:29:26,745 - INFO - Synced 0 appointments            ← BROKEN
2026-02-06 16:29:26,751 - INFO - Sync complete: 71 clients, 56 caregivers, 93 family contacts, 0 appointments
```

---

## KNOWN ISSUES

### 🔴 CRITICAL - Issue #1: WellSky Appointments API Returns 0 Records

**Symptom:**
The WellSky `/v1/appointment/_search/` endpoint returns 200 OK with an empty result set, regardless of client_id or date range.

**Impact:**
- Gigi cannot look up shift schedules
- Voice queries like "Who's working with [client] today?" return no data
- Shift sync always shows 0 appointments in cache

**Tested Scenarios:**
```python
# Test 1: Using month number
wellsky.search_appointments(client_id="8379744", month_no="202602", limit=100)
→ Result: [] (empty list, no error)

# Test 2: Using specific date range
wellsky.search_appointments(client_id="8379744", start_date=date(2026,2,1), additional_days=6)
→ Result: [] (empty list, no error)

# Test 3: Different client IDs
# Tested with multiple clients from cached_patients
→ Result: All return 0 appointments

# Test 4: Raw API call
GET /v1/appointments/?date=ge2026-01-30
→ Result: 403 Forbidden (requires client_id or caregiver_id)

POST /v1/appointment/_search/
{"clientId": "8379744", "monthNo": "202602"}
→ Result: {"resourceType": "Bundle", "entry": []}  ← Empty!
```

**Possible Causes:**
1. **API Permissions** - OAuth credentials lack appointment read access
2. **Empty Data** - WellSky system genuinely has no appointments scheduled
3. **Different Endpoint** - Shifts might be in a non-FHIR endpoint
4. **Query Format** - FHIR query parameters incorrect
5. **Agency Configuration** - Appointments feature not enabled for Agency 4505

**Investigation Needed:**
- [ ] Contact WellSky support to verify API permissions
- [ ] Check WellSky web portal - do appointments exist there?
- [ ] Review API documentation for alternative appointment endpoints
- [ ] Test with WellSky sandbox environment
- [ ] Check if agency has "Scheduling" module enabled

**Workaround:**
None. Shift queries are non-functional until this is resolved.

---

### 🔴 CRITICAL - Issue #2: Gigi Voice Calls Experience Silent Failures

**Symptom:**
During voice calls, Gigi sometimes "disappears" - doesn't hang up, but stops responding. User hears silence/hold music, then eventually the call disconnects.

**Reproduction:**
1. Call 307-459-8220 (forwards to 720-817-6600)
2. Gigi answers and greets caller
3. Ask a question requiring WellSky lookup (e.g., "Tell me about Preston Hill")
4. Gigi says nothing, ambient sound continues
5. After 30-60 seconds, call disconnects

**Observed Behavior:**
- ✅ Bitcoin/stock price queries work fine (Brave Search, <1s)
- ✅ Simple conversation works fine
- ❌ WellSky client lookups cause silence (even though cached and fast)
- ❌ Google Drive searches cause silence (3-10 seconds)

**Technical Details:**
```python
# voice_brain.py - Tool execution is synchronous
response = claude.messages.create(...)
while response.stop_reason == "tool_use":
    for block in response.content:
        if block.type == "tool_use":
            result = await execute_tool(tool_name, tool_input)  ← Blocks here
            # If tool takes >5 seconds, Retell may timeout
```

**Retell Timeout Behavior:**
- Retell expects WebSocket responses within ~5 seconds
- If no response, it may disconnect or play hold music
- No partial response / streaming support in custom-llm mode
- Can't send "Let me check on that..." mid-execution

**Potential Causes:**
1. **Database Connection Delays** - psycopg2 connections blocking
2. **Claude API Latency** - Second API call (with tool results) times out
3. **Retell WebSocket Timeout** - Expecting faster responses
4. **Network Issues** - Cloudflare tunnel latency
5. **Python Event Loop Blocking** - Sync code blocking async websocket

**Investigation Needed:**
- [ ] Add detailed timing logs to voice_brain.py
- [ ] Monitor WebSocket connection during failed calls
- [ ] Test with simpler queries to isolate issue
- [ ] Review Retell custom-llm timeout settings
- [ ] Check if database queries are actually fast in production

**Attempted Fixes:**
- ✅ Cached WellSky data (clients/caregivers now <100ms)
- ✅ Added Brave Search (web queries now <1s)
- ❌ Still experiencing silent failures on some queries

---

### 🟡 MEDIUM - Issue #3: Client Count Mismatch (71 vs 51)

**Symptom:**
PostgreSQL cache shows 71 active clients, but user's Excel export from WellSky shows only 51 active clients (filtered by Deactivated=False).

**Current State:**
```sql
-- Our cache
SELECT COUNT(*) FROM cached_patients WHERE is_active = true;
→ 71

-- User's data (from WellSky web export)
-- 51 clients with Deactivated = False
```

**Discrepancy:** 20 extra clients in our cache

**Possible Causes:**
1. **Different Active Fields** - WellSky has multiple status fields:
   - `active` (boolean) - FHIR field we use
   - `Deactivated` (boolean) - WellSky-specific field
   - `status` (enum) - FHIR status code
   - These may not be synchronized

2. **API vs Web Portal Mismatch** - API and web UI use different filters

3. **Sync Logic Bug** - Our sync marks too many clients as active

4. **Timing** - User's export is older/newer than our last sync

**Investigation Needed:**
- [ ] Export full client list from WellSky web portal
- [ ] Compare with our cached_patients table
- [ ] Identify which 20 clients are extra
- [ ] Check their status in WellSky API response
- [ ] Determine correct filtering logic

**Impact:**
Low - Extra clients don't break functionality, but may return incorrect results for "active clients" count.

---

### 🟡 MEDIUM - Issue #4: Production Portal Crashed (Feb 6, 16:34)

**Symptom:**
Production portal (port 8765) received TERM signal and shut down unexpectedly.

**Timeline:**
```
2026-02-06 16:34:00 - [76266] [INFO] Handling signal: term
2026-02-06 16:34:03 - [76268] [INFO] Shutting down
2026-02-06 16:34:03 - [76268] [INFO] Application shutdown complete.
```

**Possible Causes:**
1. Health monitor script detected failure and restarted service
2. macOS LaunchAgent watchdog timeout
3. Manual restart during staging promotion
4. System resource limits (memory/CPU)

**Resolution:**
Service was manually restarted and is now stable.

**Prevention:**
- [ ] Review health monitor logs for false positives
- [ ] Add crash detection to Telegram alerts
- [ ] Increase LaunchAgent timeout if needed

---

## PERFORMANCE METRICS

### Voice Call Response Times (Post-Caching)

| Query Type | Tool Used | Response Time | Status |
|------------|-----------|---------------|--------|
| "What's the price of Bitcoin?" | web_search (Brave) | <1s | ✅ Works |
| "Tell me about [client name]" | get_wellsky_clients (cache) | <100ms | ⚠️ Silent failure |
| "Who is [caregiver name]?" | get_wellsky_caregivers (cache) | <100ms | ⚠️ Silent failure |
| "What shifts today?" | get_wellsky_shifts (cache) | <100ms | ❌ Returns 0 |
| "Search Google Drive for X" | search_google_drive (API) | 3-10s | ⚠️ May timeout |

### Database Performance
```sql
-- Client lookup by name (cached)
SELECT * FROM cached_patients WHERE LOWER(full_name) LIKE '%peter%';
→ 5-10ms ✅

-- Caregiver lookup (cached)
SELECT * FROM cached_practitioners WHERE LOWER(full_name) LIKE '%maria%';
→ 5-10ms ✅

-- Appointment lookup (cached but empty)
SELECT * FROM cached_appointments WHERE patient_id = '8379744';
→ <1ms but 0 results ❌
```

### Sync Performance
```
Full WellSky Sync Duration: ~7 minutes
├── Clients (71):        ~6 min (676 API calls for 2-letter combos)
├── Caregivers (56):     ~1 sec (single API call)
├── Family (93):         ~1 min (71 API calls, one per client)
└── Appointments (0):    ~1 min (71 API calls, all return 0) ❌
```

---

## RECENT CHANGES (Feb 6, 2026)

### ✅ Implemented
1. **WellSky Caching System**
   - Created cached_appointments table
   - Updated sync_wellsky_clients.py to sync appointments
   - Updated voice_brain.py to query cache instead of live API
   - Changed LaunchAgent from daily to every 2 hours

2. **Brave Search Integration**
   - Added BRAVE_API_KEY to ~/.gigi-env
   - Updated web_search tool to try Brave first (instant)
   - Falls back to DuckDuckGo if Brave fails
   - Reduces web query time from 5-10s to <1s

3. **Voice Brain Improvements**
   - Added .strip() to prevent Claude API whitespace errors
   - Added exc_info=True to error logging
   - Fixed WebSocket URL (removed {call_id} placeholder)

4. **Retell Agent Updates**
   - Added ambient sound (call-center at 0.3 volume)
   - Enabled backchannel (frequency 0.8)
   - Updated phone to use agent version 2

### ❌ Still Broken
- Appointments API returns 0 records (Issue #1)
- Voice calls experience silent failures (Issue #2)
- Client count mismatch (Issue #3)

---

## ENVIRONMENT & CREDENTIALS

### Required Environment Variables (in ~/.gigi-env)
```bash
# Core
DATABASE_URL=postgresql://careassist:careassist2026@localhost:5432/careassist

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-...

# WellSky
WELLSKY_CLIENT_ID=<oauth_client_id>
WELLSKY_CLIENT_SECRET=<oauth_client_secret>
WELLSKY_AGENCY_ID=4505
WELLSKY_ENVIRONMENT=production

# RingCentral
RINGCENTRAL_CLIENT_ID=<client_id>
RINGCENTRAL_CLIENT_SECRET=<client_secret>
RINGCENTRAL_JWT_TOKEN=<jwt_token>

# Retell AI
RETELL_API_KEY=<api_key>

# Google (OAuth for portal)
GOOGLE_CLIENT_ID=<client_id>
GOOGLE_CLIENT_SECRET=<client_secret>

# Google (Work - for calendar/email)
GOOGLE_WORK_CLIENT_ID=<client_id>
GOOGLE_WORK_CLIENT_SECRET=<client_secret>
GOOGLE_WORK_REFRESH_TOKEN=<refresh_token>

# Gemini (for SMS)
GEMINI_API_KEY=<api_key>

# Brave Search (added Feb 6, 2026)
BRAVE_API_KEY=BSA_RPPBTdia3vopHH2ibpJCMgzwwXT

# Telegram
TELEGRAM_BOT_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>

# Brevo (email marketing)
BREVO_API_KEY=<api_key>

# Cloudflare
CF_API_TOKEN=<api_token>
CF_ZONE_ID=<zone_id>
```

### LaunchAgent Files Location
```
~/Library/LaunchAgents/
├── com.coloradocareassist.gigi-unified.plist      # Production portal
├── com.coloradocareassist.staging.plist           # Staging portal
├── com.coloradocareassist.telegram-bot.plist      # Telegram bot
├── com.coloradocareassist.wellsky-sync.plist      # WellSky sync (every 2 hours)
└── com.cloudflare.cloudflared.plist               # Cloudflare tunnel
```

---

## DEVELOPMENT WORKFLOW

### Golden Rule
**NEVER edit production directly.** All changes go through staging → production.

### Standard Process
```bash
# 1. Make changes in staging
cd ~/mac-mini-apps/careassist-staging
# ... edit files ...

# 2. Test in staging
~/scripts/restart-staging.sh
# Test at https://staging.coloradocareassist.com

# 3. Commit changes
git add <files>
git commit -m "feat(component): description"

# 4. Promote to production (when ready)
~/scripts/promote-to-production.sh
```

### Emergency Production Fix
```bash
# If production is broken and needs immediate fix:
cd ~/mac-mini-apps/careassist-unified

# Option A: Cherry-pick from staging
git cherry-pick <commit-hash>

# Option B: Direct edit (NOT RECOMMENDED)
# ... edit files ...
git add -A && git commit -m "hotfix: description"

# Restart production
launchctl bootout gui/501/com.coloradocareassist.gigi-unified
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist
```

---

## DEBUGGING TOOLS

### Logs Locations
```bash
~/logs/
├── gigi-unified.log              # Production portal stdout
├── gigi-unified-error.log        # Production portal stderr
├── staging.log                   # Staging portal stdout
├── staging-error.log             # Staging portal stderr
├── telegram-bot.log              # Telegram bot
├── wellsky-sync.log              # WellSky sync script
├── health-status.json            # Current health status
└── health-alerts.log             # Health monitor alerts
```

### Check Service Status
```bash
# List all services
launchctl list | grep -E "coloradocareassist|cloudflare|postgres"

# Check specific service
launchctl list com.coloradocareassist.gigi-unified

# View recent logs
tail -50 ~/logs/gigi-unified-error.log
```

### Database Access
```bash
# Connect to PostgreSQL
/opt/homebrew/opt/postgresql@17/bin/psql -d careassist

# Check cache status
psql -d careassist -c "
  SELECT
    (SELECT COUNT(*) FROM cached_patients WHERE is_active=true) as clients,
    (SELECT COUNT(*) FROM cached_practitioners WHERE is_active=true) as caregivers,
    (SELECT COUNT(*) FROM cached_appointments) as appointments,
    (SELECT COUNT(*) FROM cached_related_persons) as family_contacts;
"
```

### Test WellSky API
```bash
cd ~/mac-mini-apps/careassist-unified
python3 -c "
from services.wellsky_service import WellSkyService
ws = WellSkyService()

# Test client search
clients = ws.search_patients(last_name='Smith', limit=5)
print(f'Found {len(clients)} clients')

# Test appointment search
from datetime import datetime
shifts = ws.search_appointments(
    client_id='8379744',
    month_no=datetime.now().strftime('%Y%m')
)
print(f'Found {len(shifts)} appointments')
"
```

### Test Voice Brain Locally
```bash
# Start staging and connect with WebSocket test tool
# Production: wss://portal.coloradocareassist.com/llm-websocket
# Staging: wss://staging.coloradocareassist.com/llm-websocket

# Test with wscat (if installed)
wscat -c "wss://staging.coloradocareassist.com/llm-websocket/test_call_123"
```

---

## NEXT STEPS / TODO

### 🔴 Critical (Blocking Production Use)
1. **Investigate WellSky Appointments API** (Issue #1)
   - Contact WellSky support
   - Verify API permissions include appointment read access
   - Test with sandbox environment
   - Check agency configuration

2. **Fix Voice Call Silent Failures** (Issue #2)
   - Add detailed timing logs to voice_brain.py
   - Monitor WebSocket during failed calls
   - Test database connection pooling
   - Consider implementing acknowledgment before slow tools

### 🟡 High Priority
3. **Resolve Client Count Mismatch** (Issue #3)
   - Compare WellSky export with cached_patients
   - Identify the 20 extra clients
   - Determine correct active filter logic

4. **Improve Error Handling**
   - Add retry logic for API failures
   - Better error messages to user during voice calls
   - Automatic fallback when tools fail

### 🟢 Nice to Have
5. **Monitoring Improvements**
   - Add Retell call quality metrics
   - Track tool execution times
   - Alert on abnormal behavior

6. **Performance Optimization**
   - Database connection pooling
   - Cache query result sets
   - Reduce Claude API latency

7. **Testing**
   - Automated voice call testing
   - WellSky API integration tests
   - End-to-end conversation tests

---

## TECHNICAL DEBT

1. **Mixed Sync Scripts** - Two different sync implementations:
   - `scripts/sync_wellsky_clients.py` (currently used)
   - `services/sync_wellsky_cache.py` (older, unused)
   - Should consolidate to one

2. **Hardcoded Timeouts** - Many arbitrary timeout values throughout code

3. **No Database Migrations** - Schema changes done manually via SQL

4. **LaunchAgent Environment** - Credentials duplicated in plists and ~/.gigi-env

5. **No Staging Database** - Staging uses production database

6. **Git Workflow** - Staging and production in separate directories, prone to drift

---

## CONTACT / SUPPORT

- **Primary User:** Jason Shulmeister
- **Telegram Alerts:** Health monitor sends alerts to Jason's Telegram
- **Repository:** Private GitHub (shulmeister/colorado-careassist-portal)
- **WellSky Support:** support@wellsky.com
- **Retell Support:** support@retellai.com

---

## GLOSSARY

| Term | Definition |
|------|------------|
| **FHIR** | Fast Healthcare Interoperability Resources - HL7 standard for healthcare data exchange |
| **Custom-llm** | Retell's mode for bringing your own LLM via WebSocket |
| **Voice Brain** | Our custom LLM backend that processes voice calls via Claude |
| **Tool Call** | Claude's function calling feature to execute actions |
| **LaunchAgent** | macOS service that auto-starts and monitors processes |
| **Cloudflare Tunnel** | Secure tunnel to expose local services to internet |

---

**End of Project Status Document**
