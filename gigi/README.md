# Gigi - AI Voice Assistant

Gigi is a real team member at Colorado Care Assist - an AI-powered voice assistant who answers calls when the office is closed or when staff cannot answer. She handles caregiver and client communications with calm, capable professionalism.

## Capabilities

### Voice Calls (Retell AI)
- Answers calls on 719-428-3999 and 303-757-1777
- Identifies callers (caregiver vs client) by phone number lookup
- Handles call-outs, schedule questions, clock issues
- Logs interactions for office follow-up

### SMS Auto-Reply (RingCentral)
- Automatically replies to all inbound text messages
- Detects intent: clock in/out, call-out, schedule, payroll, general
- Takes action when possible (with WellSky integration)
- Generates context-aware responses using Gemini AI

### WellSky Integration (Scheduling)
- Looks up caregiver shift data by phone number
- Clocks caregivers in/out of shifts
- Reports call-outs and triggers coverage finding
- Provides schedule information

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INBOUND                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phone Call ──► Retell AI ──► /gigi/retell-webhook              │
│                                      │                           │
│                                      ▼                           │
│                              Tool Functions                      │
│                              - verify_caller                     │
│                              - get_shift_details                 │
│                              - report_call_out                   │
│                              - log_client_issue                  │
│                                                                  │
│  SMS ──► RingCentral Webhook ──► /gigi/webhook/ringcentral-sms  │
│                                          │                       │
│                                          ▼                       │
│                                 Intent Detection                 │
│                                 (clock_out, callout, etc.)       │
│                                          │                       │
│                                          ▼                       │
│                                 WellSky Lookup                   │
│                                 (shift data, caregiver info)     │
│                                          │                       │
│                                          ▼                       │
│                                 Take Action                      │
│                                 (clock out, report callout)      │
│                                          │                       │
│                                          ▼                       │
│                                 Gemini AI Response               │
│                                          │                       │
│                                          ▼                       │
│                                 RingCentral SMS Reply            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/gigi/` | GET | Health check |
| `/gigi/retell-webhook` | POST | Retell AI voice call events |
| `/gigi/webhook/ringcentral-sms` | POST | RingCentral SMS notifications |
| `/gigi/webhook/beetexting` | POST | Beetexting SMS (backup) |
| `/gigi/webhook/inbound-sms` | POST | Generic inbound SMS handler |
| `/gigi/test/sms-reply` | POST | Test SMS response generation |

## Retell AI Voice Tools

Gigi's voice agent (Retell AI) uses these tool functions:

| Tool | Description | When to Use |
|------|-------------|-------------|
| `verify_caller(phone)` | Identifies caller as caregiver/client/unknown | ALWAYS call first |
| `get_active_shifts(person_id)` | Returns next 24 hours of shifts | After identifying caregiver |
| `get_shift_details(person_id)` | Gets next shift with full details | To confirm shift info |
| `execute_caregiver_call_out(caregiver_id, shift_id, reason)` | **AUTONOMOUS**: Updates WellSky → Logs to Portal → Triggers Replacement Blast | When caregiver calls out |
| `log_client_issue(client_id, note, issue_type, priority)` | Logs client concerns for follow-up | When client has an issue |

### Autonomous Call-Out Flow

When a caregiver calls out sick, `execute_caregiver_call_out` performs three actions automatically:

1. **STEP A - WellSky Update**: `PUT /api/wellsky/shifts/{shift_id}` → Status = 'Open', unassign caregiver
2. **STEP B - Portal Log**: `POST /api/operations/call-outs` → Creates call-out record
3. **STEP C - Replacement Blast**: `POST /api/operations/replacement-blast` → SMS to available caregivers

After all three steps, Gigi says: *"I've updated the system and we are already looking for a replacement. Feel better."*

### Retell Tool Schema

The tool definitions are in `gigi/retell_tools_schema.json`. Upload this to your Retell AI agent configuration.

## Intent Detection (SMS)

Gigi detects these intents from SMS messages:

| Intent | Trigger Phrases | Action |
|--------|-----------------|--------|
| `clock_out` | "can't clock out", "forgot to clock out" | Clock out via WellSky |
| `clock_in` | "can't clock in", "forgot to clock in" | Clock in via WellSky |
| `callout` | "calling out", "can't make it", "sick" | Report call-out, notify team |
| `schedule` | "my schedule", "what shifts" | List upcoming shifts |
| `payroll` | "pay stub", "paycheck" | Direct to adamskeegan.com |
| `general` | (anything else) | AI-generated response |

## WellSky Functions

When WellSky API is configured, Gigi can:

```python
# Look up caregiver by phone
caregiver = wellsky.get_caregiver_by_phone("+17205551234")

# Get their current shift (the one they're working now)
shift = wellsky.get_caregiver_current_shift("+17205551234")
# Returns: client name, shift time, status, clock-in time

# Clock them out
success, message = wellsky.clock_out_shift(shift.id, notes="via Gigi SMS")
# Returns: (True, "Clocked out at 4:15 PM")

# Report a call-out
success, message, shift = wellsky.report_callout(
    phone="+17205551234",
    reason="Sick, can't make morning shift"
)
# Returns: (True, "Got it. I've logged your call-out...", affected_shift)

# Get upcoming schedule
shifts = wellsky.get_caregiver_upcoming_shifts("+17205551234", days=7)
```

## Environment Variables

```bash
# Required
RETELL_API_KEY=key_xxxxx                    # Retell AI voice agent
GEMINI_API_KEY=AIzaSyxxxxx                  # Response generation

# RingCentral SMS
RINGCENTRAL_CLIENT_ID=cqaJllTcFyndtgsussicsd
RINGCENTRAL_CLIENT_SECRET=xxxxx
RINGCENTRAL_JWT_TOKEN=eyJxxxxx

# WellSky (when available)
WELLSKY_API_KEY=xxxxx
WELLSKY_API_SECRET=xxxxx
WELLSKY_AGENCY_ID=xxxxx
```

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~1400 | FastAPI app, all endpoints, tool functions |
| `knowledge_base.md` | ~300 | Information for Retell AI voice agent |
| `system_prompt.txt` | ~90 | Voice agent personality and instructions |

## Example Flows

### Caregiver Can't Clock Out

**Before WellSky API:**
```
Caregiver: "My app won't let me clock out"
Gigi: "No worries! What was the client name and your actual clock-out time?"
```

**After WellSky API:**
```
Caregiver: "My app won't let me clock out"
[Gigi looks up: Phone → Caregiver → Current Shift → Client: Janna Segal]
[Gigi clocks them out at current time]
Gigi: "Done! I clocked you out of your shift with Janna Segal at 4:15pm."
```

### Caregiver Call-Out

```
Caregiver: "Hey I'm sick and can't make my shift tomorrow"
[Gigi looks up: Phone → Caregiver → Next Shift → Tomorrow 9am with Mary Johnson]
[Gigi reports call-out, marks shift as open for coverage]
Gigi: "I'm sorry to hear that. I've logged your call-out for tomorrow's 9am shift
       with Mary Johnson. The care team is being notified to find coverage. Feel better!"
```

## Deployment

Gigi is part of the main Portal deployment:

```bash
cd /Users/shulmeister/Documents/GitHub/careassist-unified-portal
git add -A && git commit -m "Gigi changes" && git push origin main && git push heroku main
```

Heroku app: `careassist-unified`

## RingCentral Webhook Setup

The RingCentral webhook subscription was created via API:

```python
# Subscription details
{
    "id": "4a7f8a49-196f-4d75-b62a-c7a6ba13f446",
    "status": "Active",
    "eventFilters": ["/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS"],
    "deliveryMode": {
        "address": "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/ringcentral-sms",
        "transportType": "WebHook"
    },
    "expiresIn": 604800  # 7 days - needs renewal
}
```

## Testing

```bash
# Test SMS response (no actual SMS sent)
curl -X POST "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/test/sms-reply" \
  -d "from_number=+17205551234" \
  -d "message=I cant clock out of my shift"

# Simulate full webhook (sends actual SMS reply)
curl -X POST "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/ringcentral-sms" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS",
    "body": {
      "direction": "Inbound",
      "from": {"phoneNumber": "+17205551234"},
      "to": [{"phoneNumber": "+17194283999"}],
      "subject": "I cant clock out of my shift"
    }
  }'
```

---

*Last Updated: January 21, 2026*
