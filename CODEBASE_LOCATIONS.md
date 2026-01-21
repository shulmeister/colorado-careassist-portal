# Codebase Locations - Quick Reference

Canonical path (source of truth):

```
/Users/shulmeister/Documents/GitHub/colorado-careassist-portal
```

Key structure:

```
colorado-careassist-portal/
├── portal_app.py
├── gigi/
├── services/
├── templates/
└── dashboards/
    ├── sales/            # nested git repo
    ├── recruitment/      # nested git repo
    └── activity-tracker/ # nested git repo
```

Repo references:
- Portal: https://github.com/shulmeister/colorado-careassist-portal
- Sales: https://github.com/shulmeister/sales-dashboard
- Recruiter: https://github.com/shulmeister/recruiter-dashboard
- Activity Tracker: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker

Deployment (always):

```bash
git add -A
git commit -m "message"
git push origin main
```

For full details, see `docs/PROJECT_GUIDE.md`.
