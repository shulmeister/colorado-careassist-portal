# Test WellSky Logging - Quick Guide

## Test 1: SMS with Alert Keyword

**Send this SMS to 307-459-8220:**
```
I'm sick and can't come in today
```

**Expected Result:**
- ✅ RingCentral bot detects "sick" keyword (callout)
- ✅ Identifies you as Jason (owner) via 603-997-1495
- ✅ Creates admin task in WellSky

**To Check:**
```bash
# Watch the logs live
tail -f ~/logs/gigi-unified.log | grep -i "documented\|task\|wellsky"
```

## Test 2: SMS with Client Name

**Send this SMS to 307-459-8220:**
```
Need to call out for George Furdon
```

**Expected Result:**
- ✅ Detects "call out" keyword
- ✅ Identifies client "George Furdon" from WellSky
- ✅ Creates note on George's client record
- ✅ Creates urgent admin task linked to George

## Test 3: Team Chat Message

**Post in "New Scheduling" RingCentral chat:**
```
Anyone available for a last-minute shift?
```

**Expected Result:**
- ✅ Detects "available" and "shift" keywords (scheduling)
- ✅ Creates admin task (scheduling priority)

---

## How to Monitor in Real-Time

**Option 1: Watch Logs**
```bash
tail -f ~/logs/gigi-unified.log
```

**Option 2: Filter for WellSky Activity**
```bash
tail -f ~/logs/gigi-unified.log | grep -E "Documented|Created.*task|WellSky"
```

**Option 3: Check Last 50 Lines**
```bash
tail -50 ~/logs/gigi-unified.log | grep -i wellsky
```

---

## What You'll See in Logs

**When it works:**
```
✅ Documented sms activity for George Furdon in WellSky
✅ Created callout task for caregiver Elaine Kozloski in WellSky
✅ Created UNASSIGNED callout task in WellSky
```

**If there's an issue:**
```
❌ Failed to document to WellSky: [error message]
```

---

## Simple Test Now

1. **Open Terminal and run:**
   ```bash
   tail -f ~/logs/gigi-unified.log
   ```

2. **Send SMS to 307-459-8220:**
   ```
   Test: I'm sick
   ```

3. **Watch the log** - you should see activity within 60 seconds (bot checks every 60s)

4. **Check WellSky** - Look in Admin Tasks for new task from gigi_manager

---

## Quick Status Check

**Is the bot running?**
```bash
launchctl list | grep gigi-unified
# Should show: 6970  0  com.coloradocareassist.gigi-unified
```

**When was it last active?**
```bash
tail -20 ~/logs/gigi-unified.log
```

**Force immediate check (restart bot):**
```bash
launchctl unload ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist
launchctl load ~/Library/LaunchAgents/com.coloradocareassist.gigi-unified.plist
```

After restart, the bot checks SMS within 15 seconds.
