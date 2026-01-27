# CLAUDE.md — Colorado Care Assist Portal

## Elite Agent Teams

This project uses elite AI agent squads. See [.claude/agents/TEAMS.md](.claude/agents/TEAMS.md) for the full roster.

**Quick triggers:**
- `@tech-team` — Engineering (TypeScript, Next.js, infra)
- `@marketing-team` — SEO, ads, email, analytics
- `@finance-team` — Billing, payroll, cash flow
- `@ops-team` — Scheduling, compliance, HR, client success

---

## Project Overview

Colorado Care Assist portal — helping Colorado residents navigate healthcare assistance programs.

**Stack:** Next.js (Pages Router), TypeScript, CSS Modules, Jest

## Commands

```bash
npm run dev      # Development server
npm run build    # Production build
npm run test     # Run tests
npm run lint     # Linter
```

## Key Directories

```
/pages        # Next.js pages
/components   # React components
/lib          # Utility functions
/styles       # Global styles and CSS modules
/public       # Static assets
/.claude      # AI agent configurations
```

---

## CRITICAL INFRASTRUCTURE - DO NOT ASK FOR THIS INFO

### Core 4 Apps (MUST NEVER GO DOWN)

| App | Platform | URL | Notes |
|-----|----------|-----|-------|
| careassist-unified | Heroku (Basic) | portal.coloradocareassist.com | Main portal |
| coloradocareassist | Heroku (Basic) | coloradocareassist.com | Main website |
| hesedhomecare | Heroku (Basic) | hesedhomecare.org | Hesed Home Care |
| clawd | DigitalOcean Droplet | clawd.coloradocareassist.com | AI assistant |

### Clawd Droplet Details
- **IP:** 69.55.59.212
- **Access:** Cloudflare tunnel (not direct port access)
- **Service:** Runs on HOST (not Docker) on port 8080
- **If Docker container conflicts:** `docker stop clawdbot`
- **Check status:** `lsof -i :8080`

### SSH to Clawd
The droplet requires SSH key to be added via DigitalOcean Console.
