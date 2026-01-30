# Mac Mini Self-Hosted Setup

**For:** Colorado Care Assist Portal + Gigi AI
**Go-Live:** Monday
**Critical:** Fast caller ID recognition (<5ms)

---

## 1. PostgreSQL Setup

### Install PostgreSQL (if not already installed)

```bash
brew install postgresql@15
brew services start postgresql@15
```

### Create Database

```bash
# Create main database (if not exists)
createdb colorado_careassist_portal

# Or connect to existing database
psql colorado_careassist_portal
```

### Create Cache Tables

```bash
cd ~/colorado-careassist-portal
psql colorado_careassist_portal < services/wellsky_cache.sql
```

**Verify tables created:**

```bash
psql colorado_careassist_portal -c "\dt cached_*"
```

Expected output:
```
 cached_patients        | table
 cached_practitioners   | table
 wellsky_sync_log       | table
```

---

## 2. WellSky API Credentials

### Set Environment Variables

Add to `~/.zshrc` or `~/.bash_profile`:

```bash
# WellSky API (Production)
export WELLSKY_CLIENT_ID="bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS"
export WELLSKY_CLIENT_SECRET="Do06wgoZuV7ni4zO"
export WELLSKY_AGENCY_ID="4505"
export WELLSKY_ENVIRONMENT="production"

# Database
export DATABASE_URL="postgresql://localhost/colorado_careassist_portal"

# Gigi Operations
export GIGI_OPERATIONS_SMS_ENABLED=true
```

**Reload shell:**

```bash
source ~/.zshrc
```

---

## 3. Initial Data Sync

### Run First Sync (populate cache)

```bash
cd ~/colorado-careassist-portal
python3 services/sync_wellsky_cache.py
```

**Expected output:**

```
INFO - Starting practitioner sync...
INFO - Fetching practitioners page 1...
INFO - Fetched 100 practitioners (total: 100)
INFO - Fetching practitioners page 2...
INFO - Fetched 47 practitioners (total: 147)
INFO - ✅ Practitioner sync complete: 147 total, 147 added, 0 updated

INFO - Starting patient sync...
INFO - Fetching patients page 1...
INFO - Fetched 100 patients (total: 100)
INFO - Fetching patients page 2...
INFO - Fetched 83 patients (total: 183)
INFO - ✅ Patient sync complete: 183 total, 183 added, 0 updated

INFO - ✅ All sync jobs complete
```

### Verify Data

```bash
psql colorado_careassist_portal -c "SELECT COUNT(*) FROM cached_practitioners WHERE is_hired = true;"
psql colorado_careassist_portal -c "SELECT COUNT(*) FROM cached_patients WHERE is_active = true;"

# Test fast caller ID lookup
psql colorado_careassist_portal -c "SELECT * FROM identify_caller('7195551234');"
```

---

## 4. Daily Auto-Sync (Cron Job)

### Create Cron Job

```bash
crontab -e
```

**Add this line (syncs daily at 3am):**

```cron
# WellSky cache sync - every day at 3am
0 3 * * * cd /Users/shulmeister/colorado-careassist-portal && /usr/local/bin/python3 services/sync_wellsky_cache.py >> /Users/shulmeister/logs/wellsky_sync.log 2>&1
```

**Or use launchd (more Mac-native):**

Create `/Users/shulmeister/Library/LaunchAgents/com.coloradocareassist.wellsky-sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.coloradocareassist.wellsky-sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/shulmeister/colorado-careassist-portal/services/sync_wellsky_cache.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/shulmeister/colorado-careassist-portal</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/shulmeister/logs/wellsky_sync.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/shulmeister/logs/wellsky_sync.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL</key>
        <string>postgresql://localhost/colorado_careassist_portal</string>
        <key>WELLSKY_CLIENT_ID</key>
        <string>bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS</string>
        <key>WELLSKY_CLIENT_SECRET</key>
        <string>Do06wgoZuV7ni4zO</string>
        <key>WELLSKY_AGENCY_ID</key>
        <string>4505</string>
        <key>WELLSKY_ENVIRONMENT</key>
        <string>production</string>
    </dict>
</dict>
</plist>
```

**Load launchd job:**

```bash
mkdir -p ~/logs
launchctl load ~/Library/LaunchAgents/com.coloradocareassist.wellsky-sync.plist
launchctl start com.coloradocareassist.wellsky-sync  # Test it now
```

**Check if it worked:**

```bash
tail -f ~/logs/wellsky_sync.log
```

---

## 5. Gigi Integration

### Use Fast Lookup in Gigi

**Update `gigi/main.py`:**

```python
from services.wellsky_fast_lookup import identify_caller, get_caregiver_shifts

@app.post("/gigi/incoming-call")
async def incoming_call(caller_number: str):
    """Handle incoming call to Gigi"""

    # INSTANT caller recognition (< 5ms from PostgreSQL cache)
    caller = identify_caller(caller_number)

    if not caller:
        return {"message": "I'm sorry, I don't recognize your number. Can you tell me your name?"}

    # Greet caller by name
    greeting = f"Hi {caller['first_name']}, how can I help you today?"

    if caller['type'] == 'practitioner':
        # Get real-time shifts from WellSky API
        shifts = get_caregiver_shifts(caller['id'], days=2)

        if shifts:
            today_shifts = [s for s in shifts if s['date'] == date.today()]
            if today_shifts:
                greeting += f" I see you have a shift today at {today_shifts[0]['start_time']}."

    return {"greeting": greeting, "caller": caller, "shifts": shifts if 'shifts' in locals() else []}
```

---

## 6. Monitoring & Maintenance

### Check Sync Status

```bash
# View recent syncs
psql colorado_careassist_portal -c "
SELECT
    sync_type,
    started_at,
    records_synced,
    records_added,
    records_updated,
    status
FROM wellsky_sync_log
ORDER BY started_at DESC
LIMIT 10;
"
```

### Check Data Freshness

```bash
# Find stale data (> 25 hours old)
psql colorado_careassist_portal -c "
SELECT
    'practitioners' as table,
    COUNT(*) as stale_records
FROM cached_practitioners
WHERE synced_at < NOW() - INTERVAL '25 hours'
UNION ALL
SELECT
    'patients',
    COUNT(*)
FROM cached_patients
WHERE synced_at < NOW() - INTERVAL '25 hours';
"
```

### Manual Sync (if needed)

```bash
# Sync just practitioners
python3 services/sync_wellsky_cache.py --practitioners

# Sync just patients
python3 services/sync_wellsky_cache.py --patients

# Sync both (default)
python3 services/sync_wellsky_cache.py
```

---

## 7. Performance Testing

### Test Caller ID Speed

```bash
# Time the lookup (should be < 5ms)
time psql colorado_careassist_portal -c "SELECT * FROM identify_caller('7195551234');"
```

**Expected:**
```
real    0m0.003s  ← Less than 5ms!
```

### Compare to API Speed

```bash
# Time WellSky API call (200-500ms)
time python3 -c "
from services.wellsky_service import WellSkyService
ws = WellSkyService()
cgs = ws.search_practitioners(phone='7195551234')
print(cgs[0].full_name if cgs else 'Not found')
"
```

**Expected:**
```
real    0m0.347s  ← Much slower (300ms+)
```

---

## 8. Go-Live Checklist

**Before Monday:**

- [ ] PostgreSQL running on Mac Mini
- [ ] Cache tables created (`wellsky_cache.sql`)
- [ ] Environment variables set
- [ ] Initial sync completed successfully
- [ ] Cron/launchd job configured and tested
- [ ] Gigi updated to use `wellsky_fast_lookup`
- [ ] Performance tested (caller ID < 5ms)
- [ ] Sync logs monitored

**On Monday:**

- [ ] Verify cache is fresh (synced today)
- [ ] Test incoming call with real caregiver number
- [ ] Monitor sync logs throughout the day
- [ ] Check database disk usage

---

## 9. Troubleshooting

### Sync Job Not Running

```bash
# Check if launchd job is loaded
launchctl list | grep wellsky

# View job status
launchctl print user/$(id -u)/com.coloradocareassist.wellsky-sync

# Check logs
tail -50 ~/logs/wellsky_sync.log
tail -50 ~/logs/wellsky_sync.error.log
```

### Caller Not Found in Cache

```bash
# Check if phone number exists
psql colorado_careassist_portal -c "
SELECT * FROM cached_practitioners WHERE phone LIKE '%5551234%';
"

# Force immediate sync
python3 services/sync_wellsky_cache.py
```

### Database Connection Issues

```bash
# Test database connection
psql colorado_careassist_portal -c "SELECT NOW();"

# Check PostgreSQL is running
brew services list | grep postgresql
```

---

## Performance Summary

**Caller ID Recognition:**
- ✅ Cache hit: < 5ms (99% of calls)
- ⚠️ Cache miss: 300-500ms (API fallback, rare)

**Shift Lookup:**
- Always real-time API: 200-300ms (acceptable, not on critical path)

**Data Freshness:**
- Synced daily at 3am
- 24-hour cache TTL
- Manual sync if urgent updates needed

---

**Questions? Check logs first:**
- Sync logs: `~/logs/wellsky_sync.log`
- Error logs: `~/logs/wellsky_sync.error.log`
- Database: `psql colorado_careassist_portal`
