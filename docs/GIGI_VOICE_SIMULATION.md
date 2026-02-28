# Gigi Voice Simulation Framework

**Last Updated:** February 27, 2026

## Overview

Automated end-to-end testing for Gigi's voice brain. Simulates realistic phone calls via WebSocket, captures tool usage in real-time, and scores conversations using LLM-as-judge evaluation.

## Architecture

```
run_gigi_simulations.py          simulation_service.py            voice_brain.py
┌──────────────────┐    launch   ┌─────────────────────┐   WS    ┌──────────────┐
│ 22 Scenario Defs │───────────▶│ SimulationRunner     │────────▶│ Voice Brain  │
│ expected_tools   │            │ - Anthropic caller   │◀────────│ (LLM + tools)│
│ expected_behavior│            │ - WebSocket protocol │         └──────────────┘
└──────────────────┘            │ - Tool capture       │
                                └────────┬────────────┘
                                         │ results
                                         ▼
                                ┌─────────────────────┐
                                │ simulation_evaluator │
                                │ - Tool score (40%)   │
                                │ - Behavior score(60%)│
                                │ - Overall composite  │
                                └────────┬────────────┘
                                         │
                                         ▼
                                ┌─────────────────────┐
                                │ gigi_simulations DB  │
                                │ (PostgreSQL)         │
                                └─────────────────────┘
```

### Key Files

| File                              | Purpose                                       |
| --------------------------------- | --------------------------------------------- |
| `scripts/run_gigi_simulations.py` | Scenario definitions + CLI runner             |
| `gigi/simulation_service.py`      | WebSocket simulation runner + DB persistence  |
| `gigi/simulation_evaluator.py`    | Scoring engine (tool matching + Claude judge) |

### How It Works

1. **Launch:** `run_gigi_simulations.py` calls `launch_simulation()` for each scenario
2. **Connect:** `SimulationRunner` opens WebSocket to voice brain (`ws://localhost:{port}/llm-websocket/sim_{uuid}`)
3. **Retell Protocol:** Sends `call_details` event, receives greeting, then conversation loop
4. **Caller LLM:** Anthropic Claude Sonnet generates realistic caller responses based on scenario personality
5. **Tool Capture:** WebSocket `tool_call_invocation` / `tool_call_result` events captured in real-time
6. **Completion:** After max 10 turns or natural ending, evaluator scores the run
7. **Storage:** Results saved to `gigi_simulations` table with transcript, tools, scores

## Scoring

### Overall Score = Tool (40%) + Behavior (60%)

**Tool Score (0-100):**

- Compares expected_tools vs actual tools used
- Partial credit (50%) for related tools (e.g., `get_wellsky_caregivers` when `get_wellsky_clients` was expected)
- No penalty for proactive lookup tools when none expected
- 50% penalty for action tools used when none expected

**Behavior Score (0-100):**

- LLM-as-judge evaluation using Claude Sonnet
- Evaluates against scenario's `expected_behavior` criteria
- Accounts for real vs simulated data differences
- Floor of 50 when tool score >= 90 (prevents harsh evaluator outliers)

### Thresholds

| Score Range   | Status | Meaning                |
| ------------- | ------ | ---------------------- |
| >= 70         | PASS   | Acceptable performance |
| 50-69         | WARN   | Needs attention        |
| < 50          | FAIL   | Broken behavior        |
| Runtime error | CRASH  | WebSocket/API failure  |

**Suite target: 85% pass rate**

## Scenarios (22 Total)

### Inbound Call Scenarios (14)

| ID                              | Name                              | Expected Tools                                     | Tests                             |
| ------------------------------- | --------------------------------- | -------------------------------------------------- | --------------------------------- |
| `wrong_number`                  | Wrong Number / Not In System      | (none)                                             | Service explanation, info capture |
| `rambling_family_loop`          | Rambling Family Member            | `get_wellsky_clients`                              | Loop control, client lookup       |
| `dementia_repeat_loop`          | Repeating Dementia Client         | `get_wellsky_clients`, `get_client_current_status` | Patience, consistency             |
| `angry_neglect_accusation`      | Angry Neglect Accusation          | `get_wellsky_clients`, `transfer_call`             | De-escalation, transfer           |
| `same_day_prospect`             | Same-Day Start Prospect           | (none)                                             | Intake, no over-promising         |
| `medical_advice_boundary`       | Medical Advice Boundary           | `transfer_call`                                    | Scope boundaries, 911 redirect    |
| `payroll_dispute_after_hours`   | Caregiver Payroll Dispute         | `get_wellsky_caregivers`                           | After-hours handling              |
| `caregiver_late_not_callout`    | Caregiver Late But Coming         | `get_wellsky_caregivers`                           | Distinguish late vs call-out      |
| `client_threatening_cancel`     | Client Threatening to Cancel      | `get_wellsky_clients`, `transfer_call`             | Retention, escalation             |
| `price_shopper`                 | Price Shopper                     | (none)                                             | Concise pricing, no loops         |
| `buyer_after_hours`             | Home Care Buyer (After Hours)     | (none)                                             | Education, intake capture         |
| `caregiver_callout_frantic`     | Caregiver Call-Out (Frantic)      | `get_wellsky_caregivers`, `report_call_out`        | Call-out logging                  |
| `client_no_show_anxious`        | Client No-Show (Anxious)          | `get_wellsky_clients`, `get_client_current_status` | Reassurance, status check         |
| `family_member_confused_client` | Family Member for Confused Client | `get_wellsky_clients`, `get_client_current_status` | Schedule lookup, follow-up        |

### Jason Owner Scenarios (8)

These test Gigi as Jason's personal chief of staff — proactive tool usage and concise responses.

| ID                         | Name                           | Expected Tools                     | Tests                                 |
| -------------------------- | ------------------------------ | ---------------------------------- | ------------------------------------- |
| `jason_dinner_reservation` | Dinner Reservation             | `web_search`, `book_table_request` | Restaurant search, detail collection  |
| `jason_claude_code_task`   | Claude Code Task               | `create_claude_task`               | Task dispatch, confirmation           |
| `jason_flight_search`      | Flight Search                  | `search_flights`                   | Airfare lookup with dates             |
| `jason_trading_query`      | Elite Trading / Stock Analysis | `get_stock_price`                  | Real price data, disclaimer           |
| `jason_billing_hours`      | Billing Hours Comparison       | `get_wellsky_shifts`               | Week-over-week comparison             |
| `jason_weather_trading`    | Weather Trading Bot Status     | `get_weather_arb_status`           | P&L, Kalshi vs Polymarket             |
| `jason_concert_search`     | Concert Search                 | `search_events`                    | Real search results, no hallucination |
| `jason_calendar_check`     | Calendar and Email Check       | `get_calendar_events`              | Schedule summary, highlights          |

## Running Simulations

### CLI (Full Suite)

```bash
# Against staging (default, port 8768)
cd ~/mac-mini-apps/careassist-staging
python3 scripts/run_gigi_simulations.py

# Against production (port 8767)
PORT=8767 python3 scripts/run_gigi_simulations.py
```

### Portal UI

Portal → Gigi → Simulations tab → Run individual or full suite.

### Prerequisites

- `ANTHROPIC_API_KEY` — Required for behavior evaluation (Claude Sonnet judge)
- `GEMINI_API_KEY` — Loaded from `~/.gigi-env` (legacy, now uses Anthropic for caller too)
- Voice brain service running on target port

## Adding a New Scenario

1. Add scenario dict to `GIGI_TEST_SCENARIOS` in `scripts/run_gigi_simulations.py`:

```python
{
    "id": "unique_scenario_id",
    "name": "Human-Readable Name",
    "description": "What this scenario tests",
    "identity": "Caller name, age, relationship",
    "goal": "What the caller wants to accomplish",
    "personality": "How the caller behaves",
    "expected_tools": ["tool_name_1", "tool_name_2"],
    "expected_behavior": [
        "Behavior expectation 1",
        "Behavior expectation 2",
    ],
}
```

2. Use **canonical tool names** from `gigi/tool_registry.py` (e.g., `search_events` not `search_concerts`)
3. Run on staging first to validate
4. Promote to production when passing

## Common Issues

### WebSocket Keepalive Timeouts (CRASH)

Running 22 simulations concurrently causes Anthropic API contention. The 5-second WebSocket ping timeout fires when LLM calls take too long. **Not a code bug** — re-run the suite; subsequent runs typically pass.

### Tool Score = 0 Despite Correct Behavior

Usually means `expected_tools` in the scenario definition uses the wrong tool name. Check canonical names in `tool_registry.py`. Common mistakes:

- `search_concerts` → should be `search_events`
- `web_search` for flights → should be `search_flights`

### LLM Non-Determinism

Same scenario can score 15/100 or 95/100 across runs depending on LLM tool selection. If a scenario intermittently fails, check:

1. Voice brain system prompt has explicit tool guidance rule for that scenario type
2. The tool is listed by name in the Capabilities section of the prompt

### Behavior Score Floor

If tool_score >= 90 but behavior_score < 50, the evaluator floors behavior at 50. This prevents harsh LLM-judge outliers from failing scenarios that used the right tools.

## Database Schema

```sql
CREATE TABLE gigi_simulations (
    id SERIAL PRIMARY KEY,
    scenario_id TEXT,
    scenario_name TEXT,
    call_id TEXT,
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    expected_tools JSONB,
    launched_by TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    transcript TEXT,
    transcript_json JSONB,
    turn_count INTEGER,
    tool_calls_json JSONB,
    tools_used JSONB,
    tool_score INTEGER,
    behavior_score INTEGER,
    overall_score INTEGER,
    evaluation_details JSONB,
    error_message TEXT
);
```
