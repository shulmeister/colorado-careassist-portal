# GIGI STATE — Current Operational Status

**Last Updated:** February 4, 2026
**Status:** ALL SYSTEMS OPERATIONAL

---

## QUICK STATUS

| Component | Status | Notes |
|-----------|--------|-------|
| **Portal** (8765) | Running | portal.coloradocareassist.com |
| **RingCentral Bot** (SMS/Chat) | Running | Separate process via LaunchAgent |
| **Telegram Bot** | Running | @Shulmeisterbot |
| **Voice (Retell)** | Active | 307-459-8220 |
| **WellSky Sync** | Active | Daily at 3am via LaunchAgent |
| **PostgreSQL** | Running | localhost:5432 |
| **Cloudflare Tunnel** | Running | All domains routed |
| **Health Monitor** | Running | Every 5 minutes |

---

## GIGI CHANNELS

| Channel | Number/Handle | Technology | Status |
|---------|---------------|------------|--------|
| **Phone (Voice)** | 307-459-8220 | Retell AI + WellSky | Live |
| **Phone (SMS)** | 307-459-8220 | RingCentral + Claude | Live |
| **Telegram** | @Shulmeisterbot | Claude API + Tools | Live |
| **Team Chat** | "New Scheduling" | RingCentral Glip | Monitored |
| **Portal** | portal.coloradocareassist.com | Web UI | Live |

---

## RINGCENTRAL BOT (Separate Service)

- **Extension:** #111 (Gigi AI)
- **LaunchAgent:** `com.coloradocareassist.gigi-rc-bot`
- **Script:** `gigi/ringcentral_bot.py`
- **Monitoring:** "New Scheduling" chat + SMS inbound
- **Poll Loop:** Every 30 seconds

### What the RC Bot Does
1. Monitors RingCentral team chat for scheduling messages
2. Monitors SMS inbound (caller ID + routing)
3. Auto-documents tasks/complaints into WellSky
4. Smart call transfers (scheduling → Israt, sales → Jacob)
5. Runs shift filling campaigns
6. Runs clock-in/out reminder checks (when enabled)
7. Runs daily shift confirmation texts (when enabled)

---

## WELLSKY INTEGRATION

- **Mode:** Production (Connect API)
- **Agency ID:** 4505
- **Capabilities:**
  - Client/caregiver lookup
  - Shift queries (by date, caregiver, client)
  - Auto-documentation (tasks, notes)
  - Task logs (clock in/out tracking)
  - Client notes
  - Family/emergency contact lookup

### WellSky Cache (PostgreSQL)
Synced daily at 3am via `scripts/sync_wellsky_clients.py`:

| Table | Records | Description |
|-------|---------|-------------|
| `cached_patients` | ~70 | Active clients |
| `cached_practitioners` | ~55 | Active hired caregivers (with language data) |
| `cached_related_persons` | ~93 | Family/emergency contacts |
| `cached_staff` | 4 | Office staff (Jason, Israt, Jacob, Cynthia) |

SQL function `identify_caller(phone)` checks all 4 tables for instant caller ID.

---

## SHIFT FILLING ENGINE

Autonomous calloff handling pipeline:

1. **Detect calloff** → caregiver reports sick via SMS/chat
2. **Find replacements** → matcher scores caregivers by skills, proximity, availability, preferences
3. **SMS outreach** → texts eligible caregivers with shift offer
4. **Track responses** → ACCEPTED / DECLINED / AMBIGUOUS
5. **Assign winner** → first acceptance wins, others notified
6. **Voice follow-up** → (when enabled) calls non-responders after 5 min delay

---

## FEATURE FLAGS

All new features are gated behind environment variables. Set in `~/.gigi-env` and LaunchAgent plists.

| Feature | Env Var | Status | Description |
|---------|---------|--------|-------------|
| **Caregiver Memory** | `CAREGIVER_MEMORY_ENABLED` | OFF | Extracts preferences from conversations ("can't work Thursdays") |
| **Multi-Language SMS** | `MULTILANG_SMS_ENABLED` | OFF | Translates shift offers to caregiver's preferred language |
| **Voice Outreach** | `VOICE_OUTREACH_ENABLED` | OFF | Retell outbound calls for shift filling (SMS → voice cascade) |
| **Clock Reminders** | `CLOCK_REMINDER_ENABLED` | OFF | SMS reminder if caregiver misses clock-in/out by 5+ min |
| **Daily Confirmations** | `DAILY_CONFIRMATION_ENABLED` | OFF | "You have shifts tomorrow" texts at 2pm daily |
| **Shift Monitor** | `GIGI_SHIFT_MONITOR_ENABLED` | OFF | Autonomous shift gap detection |

### To Enable a Feature
1. Edit `~/.gigi-env` → set variable to `true`
2. Edit LaunchAgent plist → set same variable to `true`
3. Restart the service: `launchctl bootout gui/501/com.coloradocareassist.gigi-rc-bot && launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.gigi-rc-bot.plist`

### Voice Outreach Additional Requirement
Before enabling `VOICE_OUTREACH_ENABLED`, create a "Gigi Shift Offer" agent in the Retell dashboard with a shift-offer prompt and set `RETELL_SHIFT_OFFER_AGENT_ID` to the new agent ID. Webhook: `https://portal.coloradocareassist.com/webhook/retell/shift-offer-complete`

---

## ZINGAGE PARITY FEATURES (Built Feb 4, 2026)

These features match/exceed Zingage (Phoebe) competitor capabilities:

| Feature | Files | Notes |
|---------|-------|-------|
| Smart call transfers | `gigi/ringcentral_bot.py` | Routes to Israt (scheduling) or Jacob (sales) |
| Autonomous shift coordination | `sales/shift_filling/engine.py` | Full calloff → fill pipeline |
| Task claiming (WellSky) | `services/wellsky_service.py` | `update_task()`, `update_task_log()` |
| Auto-prospect creation | `services/wellsky_service.py` | `create_prospect()` from voice calls |
| Voicemail detection | `gigi/ringcentral_bot.py` | Detects voicemail transcripts, skips auto-reply |
| Caregiver memory | `gigi/caregiver_preference_extractor.py` | Claude-powered preference mining |
| Multi-language SMS | `sales/shift_filling/sms_service.py` | Translation + intl response parsing |
| Voice outreach | `sales/shift_filling/voice_service.py` | Retell outbound calling |
| Clock reminders | `gigi/clock_reminder_service.py` | Missed clock-in/out SMS alerts |
| Daily confirmations | `gigi/daily_confirmation_service.py` | "Shifts tomorrow" texts at 2pm |

---

## LAUNCHAGENTS

| Service | Plist | Log |
|---------|-------|-----|
| Portal (unified_app) | `com.coloradocareassist.gigi-unified` | `~/logs/gigi-unified.log` |
| RC Bot (ringcentral_bot) | `com.coloradocareassist.gigi-rc-bot` | `~/logs/gigi-rc-bot.log` |
| Telegram Bot | `com.coloradocareassist.telegram-bot` | `~/logs/telegram-bot.log` |
| WellSky Sync (3am daily) | `com.coloradocareassist.wellsky-sync` | `~/logs/wellsky-sync.log` |
| Health Monitor (5min) | `com.coloradocareassist.health-monitor` | `~/logs/health-monitor.log` |
| Backup (3am daily) | `com.coloradocareassist.backup` | `~/logs/backup.log` |
| Website (port 3000) | `com.coloradocareassist.website` | `~/logs/website.log` |
| Hesed (port 3001) | `com.coloradocareassist.hesedhomecare` | `~/logs/hesedhomecare.log` |
| Elite Trading (port 3002) | `com.coloradocareassist.elite-trading` | `~/logs/elite-trading.log` |
| PowderPulse (port 3003) | `com.coloradocareassist.powderpulse` | `~/logs/powderpulse.log` |
| Cloudflare Tunnel | `com.cloudflare.cloudflared` | `~/logs/cloudflared.log` |

---

## STAFF

| Name | Role | Phone |
|------|------|-------|
| Jason Shulman | CEO | (Telegram + RC) |
| Israt Jahan | Scheduler | +1 (303) 879-4468 |
| Jacob McKay | Sales | +1 (227) 233-5188 |
| Cynthia Pointe | Caregiver + Office | (in WellSky) |

---

## TROUBLESHOOTING

### Service Down?
```bash
# Check all services
launchctl list | grep -E "coloradocareassist|cloudflare|postgres"

# Check ports
lsof -i :3000,3001,3002,3003,8765 -P | grep LISTEN

# Restart a service
launchctl bootout gui/501/com.coloradocareassist.<service>
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.<service>.plist
```

### API Errors?
1. Check `~/.gigi-env` for credentials
2. Verify LaunchAgent plist has matching env vars
3. Check logs: `tail -f ~/logs/<service>.log`

### Telegram Conflict?
Only ONE instance can poll. Kill duplicates:
```bash
pkill -f "telegram_bot.py"
# Then restart via LaunchAgent
```

### WellSky Cache Stale?
Run manual sync:
```bash
export $(grep -v '^#' ~/.gigi-env | grep '=' | xargs)
python3 ~/mac-mini-apps/careassist-unified/scripts/sync_wellsky_clients.py
```

---

## RECENT CHANGES

- **Feb 4, 2026:** Built 5 Phoebe-parity features (caregiver memory, multi-language, voice outreach, clock reminders, daily confirmations) — all feature-flagged OFF until tested
- **Feb 4, 2026:** Built 5 Zingage-parity features (smart transfers, autonomous shift coordination, task claiming, auto-prospect, voicemail detection)
- **Feb 4, 2026:** WellSky cache system (patients, practitioners, related persons, staff) with daily sync and `identify_caller()` function
- **Feb 4, 2026:** Consolidated all API credentials, created health monitoring system
- **Feb 2, 2026:** Migrated to Mac Mini, fixed services module caching issue
