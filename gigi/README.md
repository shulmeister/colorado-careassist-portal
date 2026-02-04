# Gigi - AI Chief of Staff

Gigi is Colorado Care Assist's Elite AI assistant. She has evolved from a simple scheduler into a comprehensive **Chief of Staff** capable of managing business operations and Jason's personal requests with secure, real-world execution.

## 🚀 Capabilities

### Elite Chief of Staff (Personal Assistant)
- **Secure Purchases (2FA):** Automates ticket purchases (Ticketmaster) and restaurant bookings (OpenTable) using a secure **Double Confirmation flow**. She sends a 2FA text to Jason's phone and waits for verbal approval.
- **Unified Google Intelligence:** Direct access to multiple Gmail accounts and search across all accessible Google Calendars.
- **1Password Integration:** Securely retrieves credentials on the Mac Mini using a headless Service Account.

### CCA Business Operations (Manager Bot)
- **Team Chat Monitoring:** Scans RingCentral chats for client mentions and task completions.
- **Auto-Documentation:** Syncs tasks and complaints directly into **WellSky** as clinical notes or admin tasks.
- **After-Hours Coverage:** Automatically replies to SMS and handles caregiver call-outs when the office is closed.

---

## 🏗️ Architecture (Mac Mini Local)

Gigi has migrated from the cloud to Jason's **Mac Mini** for lower latency and enhanced security.

```
┌─────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE                           │
├─────────────────────────────────────────────────────────────────┤
│  Hardware: Mac Mini (Local)                                      │
│  Service Manager: macOS launchd (LaunchAgents)                   │
│  Database: Local PostgreSQL 17 + SQLite                          │
│  Security: 1Password CLI (Service Account Mode)                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🛠️ Integrated Tools

| Tool | Description | Status |
|------|-------------|--------|
| `verify_caller` | Identifies caregiver/client/owner | ✅ LIVE |
| `gmail_search` | Search emails for invoices or info | ✅ LIVE |
| `get_calendar_events` | Check schedule across all calendars | ✅ LIVE |
| `search_concerts` | Find upcoming shows for favorite artists | ✅ LIVE |
| `buy_tickets` | Buy tickets via Ticketmaster | 🔐 2FA ACTIVE |
| `book_table` | Book reservations via OpenTable | 🔐 2FA ACTIVE |
| `execute_call_out` | Autonomous WellSky shift unassignment | ✅ LIVE |

## 🔐 Security & 2FA Flow

Gigi uses a **"God View, Human Hand"** security model:
1. **Request:** Jason asks Gigi to buy tickets.
2. **Initiation:** Gigi identifies the tickets and sends a **Telegram confirmation** to Jason's phone.
3. **Verification:** Gigi stays on the call and asks: *"I've sent a text to your phone for security. May I proceed with the purchase?"*
4. **Execution:** Only after a verbal "Yes" does she use the 1Password Service Account to retrieve card details and complete the transaction.

---

## 🛠️ Maintenance & Deployment

All services are managed locally on the Mac Mini.

```bash
# Restart all Gigi services
sh deploy_local.sh

# Check logs
tail -f ~/logs/gigi-unified.log
```

---
*Gigi: Capable, Secure, Local.*