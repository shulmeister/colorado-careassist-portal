#!/bin/bash
# Deploy fixes for WellSky API, RingCentral Auth, and Retell Webhook

echo "📦 Staging fixes..."
git add services/wellsky_service.py gigi/ringcentral_bot.py gigi/sync_retell.py

echo "📝 Committing..."
git commit -m "Fix WellSky API and Gigi Bot Auth

- Services: Implemented 'Encounter Search + TaskLog' strategy for WellSky notes to mitigate API 403/404 issues.
- Services: Added local database fallback for guaranteed documentation.
- Gigi: Fixed RingCentral auth to use proper JWT exchange flow.
- Gigi: Improved task creation logic for unassigned/caregiver-sourced SMS.
- Retell: Updated webhook URL to production domain.

Verified with test_wellsky_mitigation.py."

echo "🚀 Deploying to Heroku..."
git push heroku main

echo "✅ Fixes deployed!"
