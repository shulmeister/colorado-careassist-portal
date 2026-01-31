# Gigi RingCentral Manager Bot (Documentation)

**Role:** 24/7 QA Analyst & After-Hours Manager
**Status:** Live
**Location:** `gigi/ringcentral_bot.py`

## Architecture

Gigi now operates in two distinct modes simultaneously within the RingCentral ecosystem.

### 1. The Documenter (24/7/365 QA)
**Goal:** Ensure NO activity is lost, even if handled by humans or other bots.
**Triggers:** Every message in `New Scheduling` and key team chats.
**Actions:**
- **Analyzes** text for client names (e.g., "Mrs. Smith", "Client John").
- **Classifies** the event: Call-out, Complaint, Late, or Schedule Change.
- **Logs to WellSky:**
    - Adds a **Care Plan Note** to the Client's profile.
    - Creates an **Admin Task** for any item requiring follow-up (Call-outs, Complaints).
- **Why?** Zingage often solves tasks silently. Humans text but forget to log. Gigi ensures the "Audit Trail" is perfect.

### 2. The Replier (After-Hours Coverage)
**Goal:** Instant response when staff is off.
**Schedule:**
- **M-F 8am - 5pm:** SILENT (Israt/Office handles replies).
- **Nights/Weekends:** ACTIVE (Immediate reply).
**Actions:**
- Detects actionable requests (Call-outs, "I'm late").
- Replies immediately with confirmation: *"I hear you. I've logged this..."*
- **Why?** Zingage does not reply to texts. Caregivers need immediate confirmation 24/7.

## Deployment & Monitoring

- **Startup:** The bot starts automatically with the main FastAPI app (`gigi/main.py`).
- **Logs:** Check standard application logs for `gigi_rc_bot` entries.
- **Verification:** Look for "RC ACTIVITY" notes in WellSky client profiles.

## Configuration

- `GIGI_RC_BOT_ENABLED`: Set to `true` (default) or `false`.
- Timezone: America/Denver.
