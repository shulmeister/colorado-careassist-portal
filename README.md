# Colorado CareAssist Portal

This repo is the **hub** for the Colorado CareAssist Portal and contains the **Gigi** after-hours agent plus nested dashboard repos under `dashboards/`.

Start here: `docs/PROJECT_GUIDE.md`.

## Quick Map (Hub + Spokes)

- Hub repo: https://github.com/shulmeister/colorado-careassist-portal
- Hub app: https://careassist-unified-0a11ddb45ac0.herokuapp.com
- Gigi: https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/
- Sales: https://github.com/shulmeister/sales-dashboard → https://careassist-tracker-0fcf2cecdb22.herokuapp.com
- Recruiter: https://github.com/shulmeister/recruiter-dashboard → https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com
- Activity Tracker: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker → https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com

## Deployment (Always)

GitHub `main` is the source of truth. Heroku auto-deploys from GitHub. Do not push directly to Heroku.

```bash
git add -A
git commit -m "Description"
git push origin main
```

## Where to Read More

- Consolidated guide: `docs/PROJECT_GUIDE.md`
- Agent rules: `AGENTS.md`
- Canonical path: `CODEBASE_LOCATIONS.md`
- Archive of historical notes: `docs/archive/README.md`
