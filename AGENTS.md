# AGENTS.md — Colorado CareAssist Portal Guide for AI Agents

Read `docs/PROJECT_GUIDE.md` first for the consolidated source-of-truth.

## Critical Rules

1) **Hub-and-spoke with nested repos**
- Each folder in `dashboards/` is its own independent git repository (not submodules).
- Always confirm which repo you are in with `git remote -v` before committing.

2) **Canonical path**
```
/Users/shulmeister/Documents/GitHub/colorado-careassist-portal
```

3) **Deployment flow (always)**
- GitHub `main` is the source of truth; Heroku auto-deploys from GitHub.
- Do not push directly to Heroku.

```bash
git add -A
git commit -m "Description"
git push origin main
```

## Gigi Summary
- Gigi is an after-hours voice + SMS agent under `gigi/`.
- Voice via Retell AI, SMS via RingCentral, optional WellSky actions.
- Details: `gigi/README.md` and `gigi/knowledge_base.md`.

## User Preferences

### The User Wants
- All changes synced to local + GitHub + Heroku (via GitHub auto-deploy)
- Clear documentation
- Problems fixed completely, not just identified
- Minimal back-and-forth
- Gigi to take action, not just log messages
- Gemini AI as default provider

### The User Hates
- Broken deployments
- Duplicate/confusing folder structures
- Re-explaining the project
- Half-finished work
- Supabase (removed)
- AI that only logs messages

## References

- Consolidated guide: `docs/PROJECT_GUIDE.md`
- Canonical paths: `CODEBASE_LOCATIONS.md`
- Archive: `docs/archive/README.md`
