# Gigi Tool Architecture

**Last Updated:** February 27, 2026

## Overview

Gigi operates across 6 channels (Voice, SMS, Telegram, DM/Team Chat, iMessage, Ask-Gigi API). All channels share a **single tool registry** and a **single execution engine**, with per-channel filtering.

## Architecture

```
tool_registry.py                     tool_executor.py
┌───────────────────────┐            ┌──────────────────────┐
│ CANONICAL_TOOLS (90)  │            │ execute(name, input)  │
│ SMS_EXCLUDE set       │            │ - 90 tool impls       │
│ VOICE_EXCLUDE set     │            │ - DB pool (psycopg2)  │
│ get_tools(channel)    │            │ - set_google_service() │
└───────┬───────────────┘            └──────────┬───────────┘
        │ imported by                           │ called by
        ▼                                       ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  ┌────────────────┐
│telegram_bot │  │ringcentral  │  │  voice_brain     │  │  ask_gigi      │
│ 90 tools    │  │_bot.py      │  │  90-4+6 = 92     │  │ 90 tools       │
│ (all canon) │  │ SMS: ~50    │  │  (canon-excl+    │  │ (via telegram) │
│             │  │ DM:  90     │  │   voice-only)    │  │                │
└─────────────┘  └─────────────┘  └──────────────────┘  └────────────────┘
```

## Key Files

| File                      | Role                                                         | Lines |
| ------------------------- | ------------------------------------------------------------ | ----- |
| `gigi/tool_registry.py`   | Tool schemas (Anthropic format), exclude sets, `get_tools()` | ~182  |
| `gigi/tool_executor.py`   | All 90 shared tool implementations                           | ~2400 |
| `gigi/voice_brain.py`     | 6 voice-only tools + delegates to executor                   | ~1176 |
| `gigi/telegram_bot.py`    | `execute_tool()` delegates to executor                       | ~740  |
| `gigi/ringcentral_bot.py` | SMS/DM local tools + delegates to executor                   | ~3075 |
| `gigi/ask_gigi.py`        | Reuses telegram_bot's execute_tool (no duplication)          | ~401  |

## Tool Registry (`tool_registry.py`)

### CANONICAL_TOOLS (90 tools)

All tool schemas in Anthropic format. Organized by category:

| Category                       | Tools  | Examples                                                              |
| ------------------------------ | ------ | --------------------------------------------------------------------- |
| Chief-of-Staff / Entertainment | ~8     | `search_events`, `book_table_request`, `search_flights`               |
| WellSky                        | ~8     | `get_wellsky_clients`, `get_wellsky_caregivers`, `get_wellsky_shifts` |
| Financial                      | ~6     | `get_ar_report`, `get_pnl_report`, `get_cash_position`                |
| Communication                  | ~4     | `get_calendar_events`, `search_emails`                                |
| Memory                         | ~4     | `save_memory`, `recall_memories`, `forget_memory`                     |
| Browser                        | ~3     | `browse_webpage`, `take_screenshot`, `browse_with_claude`             |
| Trading                        | ~3     | `get_stock_price`, `get_crypto_price`, `get_weather_arb_status`       |
| Knowledge Graph                | ~2     | `update_knowledge_graph`, `query_knowledge_graph`                     |
| Terminal / Thinking            | ~3     | `run_terminal`, `sequential_thinking`, `get_thinking_summary`         |
| Maps                           | ~3     | `get_directions`, `geocode_address`, `search_nearby_places`           |
| Other                          | varies | `web_search`, `deep_research`, `create_claude_task`, etc.             |

### Channel Exclude Sets

**SMS_EXCLUDE** (~30 tools): Removed for caregiver SMS — no browser, terminal, thinking, knowledge graph, financial dashboards, maps, or complex booking schemas (break Gemini).

**VOICE_EXCLUDE** (4 tools): `browse_webpage`, `take_screenshot`, `browse_with_claude`, `get_polybot_status` — not useful during phone calls.

### `get_tools(channel)`

```python
def get_tools(channel: str) -> list:
    if channel in ("telegram", "dm"):
        return list(CANONICAL_TOOLS)          # All 90
    elif channel == "sms":
        return [t for t in CANONICAL_TOOLS if t["name"] not in SMS_EXCLUDE]
    elif channel == "voice":
        return [t for t in CANONICAL_TOOLS if t["name"] not in VOICE_EXCLUDE]
    return list(CANONICAL_TOOLS)
```

## Voice-Only Tools

6 tools defined in `voice_brain.py` (NOT in the registry — voice-exclusive):

| Tool                | Purpose                                           |
| ------------------- | ------------------------------------------------- |
| `transfer_call`     | Transfer live call to human (Jason, on-call, 911) |
| `lookup_caller`     | Identify caller by phone number                   |
| `report_call_out`   | Log caregiver call-out (Care Alert + Admin Task)  |
| `send_sms`          | Send SMS during voice call                        |
| `send_email`        | Send email during voice call                      |
| `send_team_message` | Send RingCentral team message during voice call   |

These are appended after the filtered canonical tools:

```python
ANTHROPIC_TOOLS = get_tools("voice") + _VOICE_ONLY_TOOLS  # 86 + 6 = 92
```

## Tool Executor (`tool_executor.py`)

### Pattern

Single `async def execute(tool_name, tool_input) -> str` with elif chain for all 90 canonical tools. Returns `json.dumps({...})` always (Gemini requires JSON — plain strings cause empty responses).

### Shared Resources

- **DB pool**: `psycopg2.pool.ThreadedConnectionPool` (2-10 connections), lazy-initialized
- **Google service**: Injected via `set_google_service(svc)` by telegram_bot on init
- **Chief-of-staff tools**: `gigi/chief_of_staff_tools.py` for entertainment/travel
- **WellSky service**: `services/wellsky_service.py` for client/caregiver data
- **Browser**: `gigi/browser_automation.py` for Playwright

### Return Format

Every tool MUST return `json.dumps({...})`. This is critical:

- Gemini returns empty text when tool results are plain strings
- All channels expect JSON-parseable results
- Error format: `json.dumps({"error": "message"})`

## Channel Handler Patterns

### Telegram (`telegram_bot.py`)

```python
from gigi.tool_registry import CANONICAL_TOOLS as ANTHROPIC_TOOLS
import gigi.tool_executor as _tex

class GigiTelegramBot:
    def __init__(self):
        _tex.set_google_service(self.google)

    async def execute_tool(self, name, input):
        return await _tex.execute(name, input)
```

### Voice Brain (`voice_brain.py`)

```python
from gigi.tool_registry import get_tools as _get_voice_tools
ANTHROPIC_TOOLS = _get_voice_tools("voice") + _VOICE_ONLY_TOOLS

async def execute_tool(name, input):
    if name in ("transfer_call", "send_sms", ...):
        # Handle 6 voice-only tools locally
    else:
        return await tool_executor.execute(name, input)
```

### RingCentral Bot (`ringcentral_bot.py`)

```python
from gigi.tool_registry import SMS_EXCLUDE as _SMS_EXCLUDE

# SMS: 3 local tools + delegate rest to executor
# DM: 5 local tools + delegate rest to executor
```

### Ask-Gigi (`ask_gigi.py`)

Reuses `GigiTelegramBot.execute_tool()` — zero duplication.

## Adding a New Tool

### Step 1: Add Schema to Registry

In `gigi/tool_registry.py`, add to `CANONICAL_TOOLS`:

```python
{
    "name": "my_new_tool",
    "description": "What the tool does. Be specific for LLM tool selection.",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"],
    },
},
```

### Step 2: Add Implementation to Executor

In `gigi/tool_executor.py`, add an `elif` branch in `execute()`:

```python
elif tool_name == "my_new_tool":
    result = do_something(tool_input.get("param1", ""))
    return json.dumps({"result": result})
```

### Step 3: Done

All channels automatically inherit the tool via `get_tools()`. No changes needed in telegram_bot.py, voice_brain.py, or ringcentral_bot.py.

### Step 4 (Optional): Exclude from Channels

If the tool shouldn't be available on certain channels:

- **Exclude from SMS**: Add to `SMS_EXCLUDE` in `tool_registry.py`
- **Exclude from Voice**: Add to `VOICE_EXCLUDE` in `tool_registry.py`
- **Voice-only tool**: Add to `_VOICE_ONLY_TOOLS` in `voice_brain.py` instead

### Step 5: Voice Brain Prompt (if needed)

If the tool needs explicit guidance in voice calls, update the system prompt in `voice_brain.py`:

1. Add to **Capabilities** section (list the tool by exact name)
2. Add to **Rules** section if there's an "ALWAYS use X when..." directive
3. Add to **Proactive Behavior** section if Gigi should use it without being asked

## Common Pitfalls

| Pitfall                            | Fix                                                              |
| ---------------------------------- | ---------------------------------------------------------------- |
| Tool returns plain string          | Always `json.dumps({...})` — Gemini breaks on plain strings      |
| Wrong tool name in voice prompt    | Use canonical name from `tool_registry.py`, not aliases          |
| Tool works in Telegram but not SMS | Check `SMS_EXCLUDE` — may be filtered out                        |
| New tool not appearing in voice    | Check `VOICE_EXCLUDE` — may be filtered out                      |
| Google API tool fails              | Ensure `set_google_service()` called before first use            |
| DB connection leak                 | Always use `try/finally` with `_put_conn(conn)`                  |
| Voice sim scores 0 on tool         | Expected tool name in scenario must match canonical name exactly |
