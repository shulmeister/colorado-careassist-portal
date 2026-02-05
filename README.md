# Colorado CareAssist Portal

> **Complete unified business portal** with CRM, recruiting, marketing analytics, AI voice assistant, autonomous shift filling, and operations dashboards - all in one self-hosted application.

**Host**: Mac Mini (Jason's Mac Mini via Tailscale)
**Live URL**: https://portal.coloradocareassist.com
**GitHub**: https://github.com/shulmeister/colorado-careassist-portal
**Last Updated**: February 4, 2026

---

## Architecture

This is a **unified FastAPI application** running on macOS, managed by `launchd`:

```
careassist-unified/
├── unified_app.py              # Main entry point (mounts everything)
├── portal/                     # Portal hub (FastAPI) — port 8765
│   ├── portal_app.py           # Routes: auth, health, CRM, webhooks
│   └── templates/              # Jinja2 templates
├── sales/                      # Sales Dashboard (FastAPI + React Admin)
│   ├── shift_filling/          # Autonomous shift filling engine
│   │   ├── engine.py           # Calloff → fill pipeline
│   │   ├── matcher.py          # Caregiver scoring + matching
│   │   ├── sms_service.py      # Multi-language SMS outreach
│   │   ├── voice_service.py    # Retell outbound voice calls
│   │   └── models.py           # Data models
│   └── frontend/               # React admin UI
├── gigi/                       # Gigi AI Assistant
│   ├── ringcentral_bot.py      # SMS + Team Chat bot (separate LaunchAgent)
│   ├── caregiver_preference_extractor.py  # Claude-powered memory
│   ├── clock_reminder_service.py          # Clock in/out reminders
│   ├── daily_confirmation_service.py      # Daily shift texts
│   ├── memory_system.py        # Long-term memory (gigi_memories table)
│   └── telegram_bridge.py      # Telegram bot
├── services/                   # Shared services
│   ├── wellsky_service.py      # WellSky Connect API client
│   ├── wellsky_fast_lookup.py  # Cache-based caller ID
│   └── wellsky_cache.sql       # Cache table schemas
├── scripts/
│   ├── sync_wellsky_clients.py # Daily WellSky → PostgreSQL sync
│   └── health-monitor.sh       # Health check script
└── docs/                       # API reference docs
```

---

## Services & Ports

| Service | Port | LaunchAgent | Process |
|---------|------|-------------|---------|
| Portal (unified_app) | 8765 | `com.coloradocareassist.gigi-unified` | `unified_app.py` |
| RC Bot | — | `com.coloradocareassist.gigi-rc-bot` | `gigi/ringcentral_bot.py` |
| WellSky Sync | — | `com.coloradocareassist.wellsky-sync` | `scripts/sync_wellsky_clients.py` (3am) |

---

## Gigi AI Assistant

Gigi operates across multiple channels:

| Channel | Technology | What It Does |
|---------|-----------|--------------|
| **Voice** (307-459-8220) | Retell AI | Answers calls, caller ID, transfers, creates WellSky prospects |
| **SMS** (307-459-8220) | RingCentral | Reads/responds to texts, shift filling outreach |
| **Team Chat** | RingCentral Glip | Monitors "New Scheduling" for calloffs, complaints, tasks |
| **Telegram** | Claude API | Jason's personal command channel |
| **Portal** | Web UI | Dashboards, CRM, marketing analytics |

### Key Capabilities
- **Caller ID**: Identifies callers from 4 cached tables (clients, caregivers, family, staff)
- **Smart Transfers**: Routes to Israt (scheduling) or Jacob (sales) based on intent
- **Auto-Documentation**: Logs scheduling events, complaints, task updates to WellSky
- **Shift Filling**: Autonomous calloff → find replacements → SMS outreach → assign winner
- **WellSky CRUD**: Reads shifts, updates tasks, creates prospects, manages task logs

### Feature Flags (all OFF by default, enable in `~/.gigi-env`)
| Flag | Feature |
|------|---------|
| `CAREGIVER_MEMORY_ENABLED` | Extracts schedule/location preferences from conversations |
| `MULTILANG_SMS_ENABLED` | Translates shift offers to caregiver's preferred language |
| `VOICE_OUTREACH_ENABLED` | Retell outbound calls after SMS non-response (5 min delay) |
| `CLOCK_REMINDER_ENABLED` | SMS alerts for missed clock-in/out (5+ min late) |
| `DAILY_CONFIRMATION_ENABLED` | "You have shifts tomorrow" texts at 2pm Mountain |
| `GIGI_SHIFT_MONITOR_ENABLED` | Autonomous shift gap detection |

---

## Database

**PostgreSQL 17** on localhost:5432

Key tables:
- `cached_patients` — Active clients (~70), synced daily from WellSky
- `cached_practitioners` — Active caregivers (~55), with language preferences
- `cached_related_persons` — Family/emergency contacts (~93)
- `cached_staff` — Office staff (Jason, Israt, Jacob, Cynthia)
- `gigi_memories` — Long-term AI memory (preferences, patterns, facts)
- `wellsky_sync_log` — Sync operation history
- `identify_caller(phone)` — SQL function for instant caller ID lookup

---

## Environment

All env vars stored in `~/.gigi-env` and duplicated in each LaunchAgent plist.

Key variables:
- `DATABASE_URL` — PostgreSQL connection
- `ANTHROPIC_API_KEY` — Claude API (for AI features)
- `RINGCENTRAL_*` — Phone/SMS (Client ID, Secret, JWT)
- `WELLSKY_*` — WellSky Connect API (Agency 4505)
- `GOOGLE_WORK_*` — Calendar/Email access
- `RETELL_API_KEY` — Voice calls
- `BREVO_API_KEY` — Email campaigns
- `GEMINI_API_KEY` — Google AI
- Feature flags (see above)

---

## Development

### Prerequisites
- Python 3.11+ (`/opt/homebrew/bin/python3.11`)
- PostgreSQL 17
- Node.js 18+ (for React admin frontend)

### Running Locally
```bash
# Load environment
export $(grep -v '^#' ~/.gigi-env | grep '=' | xargs)

# Start portal
python3 unified_app.py

# Start RC bot (separate terminal)
python3 gigi/ringcentral_bot.py

# Run WellSky sync manually
python3 scripts/sync_wellsky_clients.py
```

### Managed Services (Production)
All services run via `launchd`. See `GIGI_STATE.md` for full LaunchAgent list.

```bash
# Check service status
launchctl list | grep coloradocareassist

# Restart portal
launchctl bootout gui/501/com.coloradocareassist.gigi-unified
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist

# View logs
tail -f ~/logs/gigi-unified.log
tail -f ~/logs/gigi-rc-bot.log
```

---

## Key Documentation

| File | Description |
|------|-------------|
| `GIGI_STATE.md` | Current operational status, all features, troubleshooting |
| `CLAUDE.md` | Infrastructure overview, file locations, common commands |
| `GIGI_ELITE_CHIEF_OF_STAFF.md` | Gigi's full capabilities and architecture |
| `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` | WellSky API documentation |

---

## License

Proprietary - Colorado CareAssist 2025-2026
