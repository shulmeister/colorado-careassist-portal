# Gigi - AI Chief of Staff

Gigi operates across 6+ channels with 15-33 tools per channel, backed by PostgreSQL memory and self-monitoring subsystems.

> **Full reference:** See `CLAUDE.md` at the repo root.

## Channels

| Channel | Handler | Tools | Status |
|---------|---------|-------|--------|
| **Voice** (307-459-8220) | `voice_brain.py` | 33 | Working |
| **SMS** (307-459-8220) | `ringcentral_bot.py` | 15 | Working |
| **DM / Team Chat** | `ringcentral_bot.py` | 31 | Working |
| **Telegram** | `telegram_bot.py` | 32 | Working |
| **Ask-Gigi API** | `ask_gigi.py` | 32 | Working |
| **Apple Shortcuts / Siri** | `ask_gigi.py` | 32 | Working |
| **iMessage** | `main.py` + `ask_gigi.py` | 32 | Code Done |
| **Menu Bar** | `ask_gigi.py` | 32 | Working |

**Note:** SMS tools are intentionally limited to operational tools only. Only Jason gets full Gigi capability via DM/Telegram/voice.

## LLM Provider

- **Production:** `anthropic` / `claude-haiku-4-5-20251001`
- All handlers support Gemini, Anthropic, and OpenAI via `GIGI_LLM_PROVIDER` + `GIGI_LLM_MODEL`

## Key Files

| File | Purpose |
|------|---------|
| `voice_brain.py` | Retell Custom LLM WebSocket handler |
| `telegram_bot.py` | Telegram bot (canonical tool definitions) |
| `ringcentral_bot.py` | SMS/DM/Team Chat polling, scheduled messages |
| `main.py` | Retell webhooks, ask-gigi API, iMessage webhook |
| `ask_gigi.py` | Generic ask-gigi (reuses telegram tools) |
| `learning_pipeline.py` | Shadow mode learning (pairs drafts with staff replies) |
| `memory_system.py` | Long-term memory (save/recall/forget) |
| `conversation_store.py` | PostgreSQL conversation persistence |
| `CONSTITUTION.md` | 10 non-negotiable operating laws |

---

*See `CLAUDE.md` for full architecture, credentials, and procedures.*
