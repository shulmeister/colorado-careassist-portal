# GIGI State Documentation

## Current Issue: Inbound SMS Not Detected for Group Numbers

**Date:** February 1, 2026
**Status:** 🔴 PARTIALLY BROKEN
**Last Confirmed Working:** January 31, 2026 at 1:25am MT (Dina and Anissa messages)

### The Problem

Gigi bot receives **0 inbound SMS** when polling RingCentral for texts sent to:
- ❌ 719-428-3999 (group/auto-receptionist number)
- ❌ 303-757-1777 (group/auto-receptionist number)
- ✅ 307-459-8220 (direct extension number - WORKING)

**Confirmed Working Messages (Jan 31, 2026 1:25am MT):**
- Dina text message - Gigi replied successfully
- Anissa text message - Gigi replied successfully

### Technical Root Cause

RingCentral phone number query (`GET /restapi/v1.0/account/~/phone-number`) reveals:

| Phone Number | Extension ID | Type | Status |
|--------------|--------------|------|--------|
| +13074598220 | 63570456008 | Direct extension | ✅ Visible to bot |
| +17194283999 | **NO EXTENSION ID** | Group/Auto-receptionist | ❌ Not visible to bot |
| +13037571777 | **NO EXTENSION ID** | Group/Auto-receptionist | ❌ Not visible to bot |

**Key Finding:** Group/auto-receptionist numbers have no `extension.id` field in RingCentral API.

### RingCentral API Limitations Discovered

All RingCentral API methods for SMS detection require an extension ID:

1. **Message-Store Polling (Current Method)**
   - Endpoint: `GET /restapi/v1.0/account/~/extension/~/message-store`
   - Uses Extension 111 JWT token
   - **Result:** Only sees messages for +13074598220 (the extension that owns the token)
   - **Cannot see:** 719 or 303 numbers (no extension assignment)

2. **Account-Level Polling (Attempted)**
   - Endpoint: `GET /restapi/v1.0/account/~/message-store`
   - **Result:** 404 error (insufficient admin permissions)
   - Tested with both Extension 111 and Extension 101 (Jason's admin) JWT tokens

3. **Webhook Subscriptions (Attempted)**
   - Event filter format: `/restapi/v1.0/account/~/extension/{id}/message-store/instant?type=SMS`
   - **Result:** Requires extension ID - same limitation as polling
   - Scripts created: `setup_sms_webhook.py`, `setup_webhook_admin.py`
   - Both successful but only trigger for numbers assigned to that extension

4. **Wildcard Subscriptions (Attempted)**
   - Tried: `/restapi/v1.0/account/~/extension/+/message-store/instant?type=SMS`
   - **Result:** RingCentral rejects or expands back to specific extension ID

### Code Changes Made (February 1, 2026)

#### gigi/ringcentral_bot.py

- **Reverted** multi-extension polling (polling '0' returned 404).
- **Kept** polling `account/~/extension/~/message-store`.
- **Note Added:** Bot requires a JWT with permissions to view group numbers (like x101 Admin) to see 719/303 messages.

#### gigi/main.py (lines 6096-6178)

- Webhook endpoint `/gigi/webhook/ringcentral-sms` handles both:
  - Simple format (from Workflow Builder): `{"from": "+1234", "to": "+5678", "message": "text"}`
  - Complex format (from native webhook): `{"event": "...", "body": {...}}`

#### New Files Created

- `gigi/test_sms_polling.py` - **SUCCESSFUL** test script proving Admin credentials can see all messages.
- `gigi/setup_sms_webhook.py` - Programmatic webhook setup using Extension 111 JWT
- `gigi/setup_webhook_admin.py` - Webhook setup using Extension 101 (Jason's admin) JWT
- `gigi/find_phone_extensions.py` - Discovery script to map phone numbers to extensions
- `gigi/check_webhook_status.py` - View active webhook subscriptions

### Deployment Environment

- **Heroku App:** careassist-unified (NOT gigi-backend-cca)
- **Auto-deploy:** Git push to main branch triggers deployment
- **Bot Process:** Running on Heroku (60-second polling interval)
- **Current Code:** All changes deployed and active

### Credentials Available

| Extension | User | JWT Token Location | Permissions | Notes |
|-----------|------|-------------------|-------------|-------|
| 111 | Extension 111 | Environment vars | User | Current bot token (Limited visibility) |
| 101 | Jason Shulman | `/Users/shulmeister/Desktop/rc-credentials webhook.json` | User (admin) | **TESTED & WORKING** |

### Tests Performed (February 1, 2026)

1. ✅ Message-store API with Extension 111 JWT → sees 307 number only
2. ✅ **Message-store API with Extension 101 (Admin) JWT** → **SEES ALL NUMBERS (303, 719, 307)**
   - Confirmed via `gigi/test_sms_polling.py`
3. ❌ Message-store API for extension `0` → 404 error
4. ❌ Account-level message-store endpoint → 404 error
5. ✅ Webhook subscription created successfully → only triggers for extension's numbers

### Conclusion & Fix
The issue is **permissions**. Gigi's current JWT (x111) cannot see the company lines. Using the Admin JWT (x101) successfully retrieves messages for all lines.

**Next Step:** Update Heroku environment variable `RINGCENTRAL_JWT_TOKEN` to use the Admin JWT.

2. **Infinite Loop Prevention Added** (lines 109-136)
   - **Bug:** Bot sent 224+ spam messages replying to itself
   - **Fix:** Bot now tracks own extension ID and skips messages where `creatorId` matches
   - **Double Safety:** Also skips messages matching bot reply text patterns

#### gigi/main.py (lines 6096-6178)

- Webhook endpoint `/gigi/webhook/ringcentral-sms` handles both:
  - Simple format (from Workflow Builder): `{"from": "+1234", "to": "+5678", "message": "text"}`
  - Complex format (from native webhook): `{"event": "...", "body": {...}}`

#### New Files Created

- `gigi/setup_sms_webhook.py` - Programmatic webhook setup using Extension 111 JWT
- `gigi/setup_webhook_admin.py` - Webhook setup using Extension 101 (Jason's admin) JWT
- `gigi/find_phone_extensions.py` - Discovery script to map phone numbers to extensions
- `gigi/check_webhook_status.py` - View active webhook subscriptions

### Deployment Environment

- **Heroku App:** careassist-unified (NOT gigi-backend-cca)
- **Auto-deploy:** Git push to main branch triggers deployment
- **Bot Process:** Running on Heroku (60-second polling interval)
- **Current Code:** All changes deployed and active

### Credentials Available

| Extension | User | JWT Token Location | Permissions | Notes |
|-----------|------|-------------------|-------------|-------|
| 111 | Extension 111 | Environment vars | User | Current bot token |
| 101 | Jason Shulman | `/Users/shulmeister/Desktop/rc-credentials webhook.json` | User (admin) | Same API limitations |

### Tests Performed (February 1, 2026)

1. ✅ Message-store API with Extension 111 JWT → sees 307 number only
2. ❌ Message-store API with Extension 101 admin JWT → same limitations
3. ❌ Account-level message-store endpoint → 404 error
4. ✅ Webhook subscription created successfully → only triggers for extension's numbers
5. ❌ Wildcard webhook subscription → rejected by RingCentral
6. ✅ Phone number query → confirmed 719 and 303 have no extension IDs

### Critical Unanswered Question

**Timeline:**
- ✅ January 31, 2026 1:25am MT - Dina and Anissa messages worked (Gigi replied)
- ❌ February 1, 2026 - Same phone numbers not visible to bot

**Question:** What changed between Jan 31 1:25am MT and Feb 1, 2026?

Possibilities:
- RingCentral account configuration changed (extension assignments for 719/303 numbers)
- Code deployment changed bot behavior (check git commits between Jan 31-Feb 1)
- Temporary API permissions that expired
- Different API method was being used before (check git history)

### Business Requirements

- **Phone Numbers:** 719-428-3999, 303-757-1777, 307-459-8220
- **Hours:** After-hours only (not M-F 8am-5pm MT)
- **Response Time:** 60-second polling interval
- **Current Functionality:** Only 307-459-8220 working
