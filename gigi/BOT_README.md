# Gigi AI Bot - Operations Manual (v3.0 - The "Trojan Horse" Edition)

**Last Updated:** Feb 1, 2026
**Status:** ✅ FULLY OPERATIONAL

## 🚀 Quick Start (Deployment)

Gigi is now embedded directly into the main website process to ensure reliability.

### To Deploy (Heroku):
Simply push to the `main` branch.
```bash
git push origin main
```
That's it. The `unified_app` starts, and Gigi starts automatically in the background.

### To Run Locally (Mac Mini):
1. Ensure `.env` has the necessary database credentials.
2. Run the unified app:
```bash
uvicorn unified_app:app --reload
```
Gigi will start automatically.

---

## 🧠 System Architecture

### 1. The "Trojan Horse" Strategy
Previously, Gigi ran as a separate `worker` process on Heroku. This was unreliable (process often didn't start).
**Now:** Gigi is an async task (`gigi/async_bot.py`) launched by `unified_app.py` on startup.
- If the website is up, Gigi is up.
- Zero extra configuration needed.

### 2. Permissions & Credentials (CRITICAL)
Gigi (Extension 111) **cannot** see the company main lines (719/303).
To fix this, we hardcoded **Jason's Admin JWT (Extension 101)** into `gigi/async_bot.py`.
- **Why?** Only the Admin/Owner has permission to view/reply to the main company SMS numbers.
- **Where:** `gigi/async_bot.py` -> `ADMIN_JWT_TOKEN` variable.

### 3. Smart Reply & Spam Prevention
Gigi uses "Conversation Awareness" to prevent duplicate replies on restart:
1. She fetches the last 100 messages (Inbound & Outbound).
2. She groups them by phone number.
3. **Logic:**
   - If the *last* message in the thread is **Outbound** (from us) → She assumes it's handled. **Skipped.**
   - If the *last* message is **Inbound** (from them) → She replies.

This makes her "stateless" and robust. She won't spam you even if she restarts 50 times.

---

## 🔗 Integrations

### RingCentral (SMS)
- **Monitoring:** Polls `message-store` every 5 seconds.
- **Scope:** Last 12 hours (catch-up mode).
- **Numbers:** 303-757-1777, 719-428-3999, and direct lines.

### WellSky (Documentation)
- **File:** `services/wellsky_service.py`
- **Logic:**
  1. Incoming SMS received.
  2. Bot extracts Phone Number.
  3. Bot queries WellSky: "Get Caregiver/Client with this phone number".
  4. If found, logs a **Client Note** or **Admin Task** directly to their profile.
  5. **Voice Synergy:** Because the text is logged in WellSky, if you call the Gigi Voice Agent later, she "knows" about the text because she reads the WellSky notes.

---

## 🛠️ Troubleshooting

**Issue: Gigi isn't replying.**
1. Check if the website is up (`portal.coloradocareassist.com`).
2. Check `gigi/async_bot.py` to ensure `ADMIN_JWT_TOKEN` hasn't expired (it's valid until 2093).
3. Restart the server/dyno to force a fresh poll.

**Issue: Gigi replied multiple times.**
*Fixed by Smart Reply Logic.* If it happens again, check if the "Outbound" message failed to send (so she thinks she hasn't replied yet).

**Issue: WellSky logs missing.**
1. Ensure `WELLSKY_AVAILABLE` is True in logs.
2. Ensure the sender's phone number matches exactly one person in WellSky.

---

## 📂 Key Files
- `gigi/async_bot.py` → **The Brain.** (Loop, Logic, Reply, Logging).
- `unified_app.py` → **The Launcher.** (Starts bot on web boot).
- `services/wellsky_service.py` → **The Memory.** (API connection).