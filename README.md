# Colorado CareAssist Portal

> **Complete unified business portal** with CRM, recruiting, marketing analytics, AI voice assistant, and operations dashboards - all in one deployable application.

**Host**: Mac Mini - Jasons-Mac-mini
**Live URL**: https://portal.coloradocareassist.com
**GitHub (source of truth)**: https://github.com/shulmeister/colorado-careassist-portal
**Status**: **Migration to Mac Mini Complete (Feb 3, 2026)**

---

## 🚀 Recent Upgrades: Gigi Elite Chief of Staff

Gigi has been upgraded from a business scheduler to a **Full Chief of Staff**:

- **Secure Autonomous Purchasing**: Uses a **2FA handshake** via Telegram/SMS before buying tickets or booking tables.
- **Unified Google Intelligence**: Unified search across multiple Gmail accounts and ALL accessible Google Calendars.
- **Business Automation**: Scans RingCentral chats and auto-documents tasks/complaints into WellSky.
- **1Password Integration**: Uses a Service Account for secure, headless credential retrieval on the Mac Mini.

See [GIGI_ELITE_CHIEF_OF_STAFF.md](GIGI_ELITE_CHIEF_OF_STAFF.md) for full details.

---

## 🏗️ Architecture Overview

This is a **unified FastAPI application** running locally on macOS:

```
colorado-careassist-portal/
├── unified_app.py          # Main entry point (mounts everything)
├── portal/                 # Portal hub (FastAPI)
├── sales/                  # Sales Dashboard (FastAPI + React Admin)
├── recruiting/             # Recruiter Dashboard (Flask)
├── gigi/                   # Gigi AI Voice Assistant (FastAPI)
├── powderpulse/            # PowderPulse ski weather (Vue.js SPA)
├── services/               # Shared services (WellSky, marketing APIs)
└── templates/              # Jinja2 templates for portal pages
```

**Deployment**: Services are managed via macOS `launchd` using the `com.coloradocareassist.gigi-unified.plist` LaunchAgent.

---

## 🤖 Gigi - AI Voice Assistant

**Gigi** is Jason's Elite Chief of Staff who handles CCA business operations and personal assistant requests.

**Capabilities**:
| Feature | Status |
|---------|--------|
| Voice calls (Retell AI) | ✅ LIVE |
| SMS / Team Chat Monitoring | ✅ LIVE |
| 2FA Ticket Purchasing | 🔐 ACTIVE |
| Unified Calendar/Email | ✅ LIVE |
| WellSky Auto-Documentation | ✅ LIVE |

**Technical**:
- **Host**: Mac Mini
- **APIs**: Retell AI, RingCentral, WellSky (Connect), Gmail, Calendar, 1Password CLI
- **Documentation**: See [gigi/README.md](gigi/README.md) and [GIGI_ELITE_CHIEF_OF_STAFF.md](GIGI_ELITE_CHIEF_OF_STAFF.md)

---

## 🔧 Development

### Local Setup (Mac Mini)

```bash
# 1. Load environment
source ~/.gigi-env

# 2. Start services (managed by launchctl)
sh deploy_local.sh
```

---

## 📝 License

Proprietary - Colorado CareAssist © 2025-2026