# Recruiter Dashboard Authentication Fix

## Issue
The Recruiter Dashboard is showing Google OAuth login instead of accepting portal authentication.

## Root Cause
Both the Portal and Recruiter Dashboard must use the **SAME** `APP_SECRET_KEY` environment variable to validate portal tokens.

## Solution

### Step 1: Get Portal's APP_SECRET_KEY
```bash
heroku config:get APP_SECRET_KEY --app portal-coloradocareassist
```

### Step 2: Set Same Key in Recruiter Dashboard
```bash
heroku config:set APP_SECRET_KEY=<value-from-portal> --app caregiver-lead-tracker
```

### Step 3: Verify Both Apps Have Same Key
```bash
# Portal
heroku config:get APP_SECRET_KEY --app portal-coloradocareassist

# Recruiter Dashboard  
heroku config:get APP_SECRET_KEY --app caregiver-lead-tracker
```

Both should return the **exact same value**.

## How It Works

1. Portal creates session token using `APP_SECRET_KEY`
2. Portal passes token to Recruiter Dashboard via URL: `?portal_token=...&portal_user_email=...`
3. Recruiter Dashboard validates token using **same** `APP_SECRET_KEY`
4. If keys match → authentication succeeds
5. If keys don't match → token validation fails → redirects to Google OAuth

## Testing

After setting the same `APP_SECRET_KEY`:
1. Log into Portal
2. Click Recruiter Dashboard tile
3. Should load dashboard directly (no Google OAuth prompt)

## Logs

Check Recruiter Dashboard logs for authentication details:
```bash
heroku logs --tail --app caregiver-lead-tracker | grep -i "portal\|auth\|token"
```

Look for:
- `Portal token check: token present=True`
- `Portal token validated successfully for: <email>`
- `Portal authentication successful - rendering dashboard`

