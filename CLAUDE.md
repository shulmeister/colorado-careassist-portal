# CLAUDE.md — Colorado Care Assist Infrastructure

**Last Updated:** February 2, 2026
**Status:** ✅ FULLY SELF-HOSTED ON MAC MINI (No Heroku, No DigitalOcean)

---

## CRITICAL: Current Infrastructure

**EVERYTHING runs on Jason's Mac Mini.** No cloud hosting. No Heroku. No DigitalOcean.

### Services Running on Mac Mini

| Service | Port | URL | LaunchAgent |
|---------|------|-----|-------------|
| Portal (gigi-unified) | 8765 | portal.coloradocareassist.com | com.coloradocareassist.gigi-unified |
| Main Website | 3000 | coloradocareassist.com | com.coloradocareassist.website |
| Hesed Home Care | 3001 | hesedhomecare.org | com.coloradocareassist.hesedhomecare |
| Elite Trading | 3002 | elitetrading.coloradocareassist.com | com.coloradocareassist.elite-trading |
| PowderPulse | 3003 | powderpulse.coloradocareassist.com | com.coloradocareassist.powderpulse |
| Clawd Gateway | 8080 | clawd.coloradocareassist.com | com.coloradocareassist.gigi-gateway |
| Cloudflare Tunnel | - | - | com.cloudflare.cloudflared |
| PostgreSQL 17 | 5432 | localhost | homebrew.mxcl.postgresql@17 |

### Database

- **Local PostgreSQL 17** running on localhost:5432
- **Database:** `careassist`
- **User:** `careassist` / Password: `careassist2026`
- **Connection:** `postgresql://careassist:careassist2026@localhost:5432/careassist`
- **82 tables** migrated from Heroku

### Remote Access

- **Tailscale:** Mac Mini is `100.124.88.105` (jasons-mac-mini)
- **SSH:** `ssh shulmeister@100.124.88.105`
- From anywhere, access services via Tailscale IP

### Backups

- **Daily at 3:00 AM** → Google Drive (jason@coloradocareassist.com)
- **Location:** `gdrive:MacMini-Backups`
- **Script:** `/Users/shulmeister/scripts/backup-to-gdrive.sh`
- **LaunchAgent:** `com.coloradocareassist.backup`
- **Includes:** PostgreSQL dump, configs, LaunchAgents

### Cloudflare Tunnel

- **Tunnel ID:** `484767a1-bb21-4798-a576-e3834a55ba66`
- **Config:** `~/.cloudflared/config.yml`
- All domains route through this tunnel to localhost ports

---

## File Locations

```
~/heroku-apps/
├── careassist-unified/     # Portal + Gigi (Python/FastAPI) → port 8765
├── coloradocareassist/     # Main website (Next.js) → port 3000
├── hesedhomecare/          # Hesed website (Next.js) → port 3001
├── elite-trading-mcp/      # Elite Trading (Python/FastAPI) → port 3002
├── clawd/                  # Clawd gateway (Node.js) → port 8080
└── gigi-backend-cca/       # Legacy (not used)

~/Library/LaunchAgents/     # All service plists
~/logs/                     # Service logs
~/.gigi-env                 # Environment variables
~/.cloudflared/             # Cloudflare tunnel config
~/backups/                  # Local backup files
~/scripts/                  # Utility scripts
```

---

## Common Commands

```bash
# Check all services
launchctl list | grep -E "coloradocareassist|cloudflare|postgres"

# Check ports
lsof -i :3000,3001,3002,3003,8080,8765 -P | grep LISTEN

# Restart a service
launchctl unload ~/Library/LaunchAgents/com.coloradocareassist.<service>.plist
launchctl load ~/Library/LaunchAgents/com.coloradocareassist.<service>.plist

# View logs
tail -f ~/logs/gigi-unified.log
tail -f ~/logs/gigi-unified-error.log

# Database access
/opt/homebrew/opt/postgresql@17/bin/psql -d careassist

# Manual backup
/Users/shulmeister/scripts/backup-to-gdrive.sh

# Test sites
curl -s https://portal.coloradocareassist.com/health
curl -s https://coloradocareassist.com
curl -s https://elitetrading.coloradocareassist.com/health
```

---

## Environment Variables

All env vars are in `~/.gigi-env` and duplicated in each LaunchAgent plist.

Key variables:
- `DATABASE_URL` - Local PostgreSQL connection
- `GOOGLE_CLIENT_ID/SECRET` - OAuth for portal login
- `ANTHROPIC_API_KEY` - Claude API
- `GEMINI_API_KEY` - Google AI
- `RETELL_API_KEY` - Voice calls
- `RINGCENTRAL_*` - Phone/SMS

---

## Elite Agent Teams

**Quick triggers:**
- `@tech-team` — Engineering (TypeScript, Next.js, infra)
- `@marketing-team` — SEO, ads, email, analytics
- `@finance-team` — Billing, payroll, cash flow
- `@ops-team` — Scheduling, compliance, HR, client success

---

## If Something Breaks

1. **Service not responding:** Check `launchctl list | grep coloradocareassist`
2. **Database error:** Verify PostgreSQL: `/opt/homebrew/bin/brew services list | grep postgres`
3. **Sites not loading:** Check Cloudflare tunnel: `launchctl list | grep cloudflare`
4. **Need to restore:** Backups are in `gdrive:MacMini-Backups`

---

## Working Remotely with Claude

### GitHub Repository

- **Repo:** `shulmeister/colorado-careassist-portal` (private)
- **Branch:** `main`
- **Always pull before starting work:** `git pull origin main`

### Before Starting Any Session

```bash
# 1. Pull latest changes
git pull origin main

# 2. Check service status (if on Mac Mini via Tailscale)
curl -s http://100.124.88.105:8765/health
```

### After Making Changes

```bash
# 1. Stage specific files (never use git add -A)
git add <specific-files>

# 2. Commit with clear message
git commit -m "fix(component): description"

# 3. Push immediately to avoid conflicts
git push origin main
```

### Remote Access to Mac Mini

From any device with Tailscale:
- **SSH:** `ssh shulmeister@100.124.88.105`
- **Portal:** `http://100.124.88.105:8765`
- **Health:** `curl http://100.124.88.105:8765/health`

### Key Points for Claude

1. **This is a self-hosted setup** - Services run on Jason's Mac Mini, not cloud
2. **Database is local** - PostgreSQL on the Mac Mini (not accessible remotely without SSH tunnel)
3. **Git is the source of truth** - Always pull before changes, push after
4. **Check GIGI_STATE.md** for current bot/service status

---

## History

- **Feb 2, 2026:** Migrated everything from Heroku + DigitalOcean to Mac Mini
- All Heroku apps deleted
- DigitalOcean droplet (clawdbot) decommissioned
- Local PostgreSQL 17 with all data migrated
- Cloudflare tunnel for secure access
- Tailscale for remote management
- Daily backups to Google Drive
- **Feb 2, 2026:** Fixed RingCentral bot import issue (services module cache restoration)
