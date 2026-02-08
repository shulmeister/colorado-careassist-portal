# Gigi - AI Chief of Staff

Gigi is Colorado Care Assist's AI Chief of Staff. She operates across 6+ channels with 22-25 tools per channel, backed by PostgreSQL memory, cross-channel conversation persistence, and self-monitoring subsystems.

> **Primary reference:** See `CLAUDE.md` at the repo root for full architecture, tool lists, and operational details.

---

## Channels

| Channel | Handler | Tools | Status |
|---------|---------|-------|--------|
| **Voice** (307-459-8220) | `voice_brain.py` | 25 | Working |
| **SMS** (307-459-8220) | `ringcentral_bot.py` | 11 | Working |
| **DM / Team Chat** | `ringcentral_bot.py` | 22 | Working |
| **Telegram** | `telegram_bot.py` | 22 | Working |
| **Ask-Gigi API** | `ask_gigi.py` | 22 | Working |
| **Apple Shortcuts / Siri** | `ask_gigi.py` | 22 | Working |
| **iMessage** | `main.py` + `ask_gigi.py` | 22 | Code Done |
| **Menu Bar** | `ask_gigi.py` | 22 | Working |

## Key Files

| File | Purpose |
|------|---------|
| `voice_brain.py` | Retell Custom LLM WebSocket handler (multi-provider, 25 tools) |
| `telegram_bot.py` | Telegram bot (multi-provider, 22 tools) |
| `ringcentral_bot.py` | RC polling loop — SMS, DM, Team Chat, clock reminders, daily confirmations, morning briefing |
| `main.py` | Retell webhooks, `/api/ask-gigi`, `/webhook/imessage` |
| `ask_gigi.py` | Generic ask-gigi function (reuses telegram tools, no code duplication) |
| `browser_automation.py` | Playwright headless Chromium (browse + screenshot) |
| `conversation_store.py` | PostgreSQL conversation persistence (all channels) |
| `memory_system.py` | Long-term memory (save/recall/forget via PostgreSQL `gigi_memories`) |
| `mode_detector.py` | 8-mode auto-detection (focus, crisis, travel, etc.) |
| `failure_handler.py` | 10 failure protocols + DB-based meltdown detection |
| `pattern_detector.py` | Repeated failure + trend detection for morning briefing |
| `self_monitor.py` | Weekly self-audit (Monday morning briefing) |
| `memory_logger.py` | Daily markdown journal at `~/.gigi-memory/` |
| `morning_briefing_service.py` | 7 AM daily briefing via Telegram |
| `google_service.py` | Google Calendar + Gmail API (OAuth2) |
| `CONSTITUTION.md` | Gigi's 10 non-negotiable operating laws |

## Multi-LLM Provider

All handlers support Gemini, Anthropic, and OpenAI. Configured via:
- `GIGI_LLM_PROVIDER=gemini` (default)
- `GIGI_LLM_MODEL=gemini-3-flash-preview` (default)

## Subsystems

- **Memory System** — PostgreSQL `gigi_memories` + audit log, with confidence decay
- **Conversation Store** — PostgreSQL `gigi_conversations`, cross-channel context injection
- **Mode Detector** — 8 operating modes, injected into system prompts
- **Failure Handler** — 10 protocols, DB-based meltdown detection (3 failures in 5 min)
- **Pattern Detector** — Tool failure trends, open shifts, memory conflicts, drift
- **Self-Monitor** — Weekly audit (Monday briefing), failure stats, memory health
- **Memory Logger** — Daily markdown journal, searchable via `search_memory_logs` tool
- **Constitutional Preamble** — 10 Operating Laws injected into ALL system prompts

## Security

- All services bind `127.0.0.1`, exposed only via Cloudflare Tunnel
- iMessage webhook requires BlueBubbles password parameter
- Retell webhook uses SDK `verify()` (never custom HMAC)
- Voice brain blocks side-effect tools during test/simulation calls

---

*For full details, tool lists, API credentials, and operational procedures, see `CLAUDE.md`.*
