# Colorado CareAssist Portal

Unified business platform: portal, Gigi AI, sales CRM, recruiting.

**URL**: https://portal.coloradocareassist.com
**Port**: 8765 | **Branch**: main | **GitHub**: shulmeister/colorado-careassist-portal

## Quick Reference

- **Full documentation**: `CLAUDE.md` (this is the authoritative reference)
- **Change log**: `CHANGELOG.md`
- **Gigi details**: `gigi/README.md`
- **WellSky API**: `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md`

## Architecture

```
unified_app.py          # Entry point (mounts portal, gigi, sales, recruiting)
├── portal/             # Web dashboard (FastAPI + Jinja2)
├── gigi/               # AI Chief of Staff (voice, SMS, Telegram, DM)
├── sales/              # CRM (FastAPI + React Admin)
├── recruiting/         # Recruiting dashboard (Flask)
├── services/           # Shared services (WellSky, RingCentral)
└── scripts/            # Cron jobs, health checks, backups
```

## Services

| Service | Port | LaunchAgent |
|---------|------|-------------|
| Portal | 8765 | `com.coloradocareassist.gigi-unified` |
| RC Bot | - | `com.coloradocareassist.gigi-rc-bot` |
| Telegram Bot | - | `com.coloradocareassist.telegram-bot` |

## Common Commands

```bash
# Load env
set -a && source ~/.gigi-env && set +a

# Check services
launchctl list | grep coloradocareassist

# Restart portal
launchctl bootout gui/501/com.coloradocareassist.gigi-unified
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist

# Logs
tail -f ~/logs/gigi-unified.log
```

## License

Proprietary - Colorado CareAssist 2025-2026
