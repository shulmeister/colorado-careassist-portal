# GIGI State Documentation

## Current Status: ✅ RUNNING ON MAC MINI

**Date:** February 2, 2026
**Location:** Mac Mini (jasons-mac-mini)
**Service:** com.coloradocareassist.gigi-unified
**Port:** 8765
**URL:** https://portal.coloradocareassist.com

---

## Infrastructure

- **No Heroku** - All Heroku apps deleted
- **No DigitalOcean** - Droplet decommissioned
- **Database:** Local PostgreSQL 17 on Mac Mini
- **Access:** Cloudflare Tunnel (secure, no open ports)
- **Remote:** Tailscale at 100.124.88.105

---

## Capabilities

1. **SMS (307-459-8220):** Replies using Gemini AI. Recognizes Owner ("Hi Jason"). No duplicates.
2. **Voice (307-459-8220 → 720-817-6600):** Recognizes callers via WellSky lookup ("Hi [Name]").
3. **Telegram (@Shulmeisterbot):** Personal AI assistant running on Mac Mini.
4. **Logging:** Logs ALL interactions to WellSky (Client Notes or Admin Tasks).
5. **Portal:** Full web portal with 26 tiles for various tools

---

## Service Management

```bash
# Check status
launchctl list | grep gigi-unified
curl http://localhost:8765/health

# View logs
tail -f ~/logs/gigi-unified.log
tail -f ~/logs/gigi-unified-error.log

# Restart
launchctl unload ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist
launchctl load ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist
```

---

## RingCentral Bot Status

- **Status:** ✅ ENABLED AND RUNNING
- **Monitoring:** "New Scheduling" chat and Direct SMS
- **Loop:** Every 60 seconds
- **Bot Class:** `gigi/ringcentral_bot.py` → `GigiRingCentralBot`

The bot is started automatically via `unified_app.py` startup event.

To disable: Set `GIGI_RC_BOT_ENABLED=false` in LaunchAgent plist.

---

## Code Location

- **Main App:** `/Users/shulmeister/heroku-apps/careassist-unified/`
- **Gigi Code:** `/Users/shulmeister/heroku-apps/careassist-unified/gigi/`
- **LaunchAgent:** `~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist`
- **Logs:** `~/logs/gigi-unified.log` and `~/logs/gigi-unified-error.log`

---

## Database

- **Host:** localhost:5432
- **Database:** careassist
- **User:** careassist
- **Password:** careassist2026
- **Connection:** `postgresql://careassist:careassist2026@localhost:5432/careassist`

---

## Backups

Daily at 3AM to Google Drive (`gdrive:MacMini-Backups`)
Manual: `~/scripts/backup-to-gdrive.sh`

---

## Recent Fixes

- **Feb 2, 2026:** Fixed services module import issue - sales dashboard failure was preventing services modules from being restored to Python's module cache, breaking RingCentral bot imports. Fixed with proper try/finally pattern.
