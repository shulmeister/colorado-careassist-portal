# Elite Teams - Systematic Management Framework

**Your three elite teams with Gigi as Chief of Staff orchestrating accountability and performance.**

---

## Teams Overview

| Team | Lead | KPIs | Daily Standup |
|------|------|------|---------------|
| **💰 Finance** | CFO | Cash runway, DSO, gross margin, burn rate | `finance-daily-pulse.py` |
| **🛠️ Tech** | Head of Engineering | Build success, code review time, test coverage, uptime | Manual GitHub/Mac Mini check |
| **📈 Marketing** | Marketing VP | ROAS, organic traffic, email rates, lead conversion | Manual GA4/Ads check |

---

## Quick Start

### Daily Finance Pulse
```bash
python3 /Users/shulmeister/mac-mini-apps/clawd/elite-teams/finance-daily-pulse.py
```

### Team Commands
See command protocols:
- `gigi-finance-commands.md` - Finance team management commands
- `gigi-tech-commands.md` - Tech team protocols and standards
- `gigi-marketing-commands.md` - Marketing team automation

### Optimization Plans
Detailed KPIs and strategies:
- `finance-team-optimization-plan.md` - Finance KPIs, DSO targets, cash flow management
- `tech-team-optimization-plan.md` - Build success, code review, technical debt
- `marketing-optimization-plan.md` - ROAS targets, skill module compliance

---

## Integration with Heartbeat

Gigi runs automated daily checks via `HEARTBEAT.md`:

**Weekday mornings (8-9am MT):**
1. Finance pulse check → Alert on red items only
2. Tech build/PR status → Alert on failures only
3. Marketing performance → Alert on ROAS/traffic issues only
4. Routine metrics → Logged to memory, not surfaced

**Result:** Jason only sees urgent issues, everything else is tracked automatically.

---

## Tools & APIs

### Finance Team
- **QuickBooks CLI:** `/Users/shulmeister/mac-mini-apps/clawd/tools/quickbooks/qb.py`
- **Credentials:** 1Password (`QuickBooks Online`)
- **Daily automation:** `finance-daily-pulse.py`

### Tech Team
- **GitHub:** github.com/shulmeister/clawd
- **Mac Mini:** careassist-unified (production)
- **Monitoring:** GitHub Actions, Mac Mini metrics

### Marketing Team
- **Google Ads:** Credentials in 1Password
- **GA4:** Via `ga4-analytics` skill
- **Brevo CRM:** Credentials in 1Password
- **23 Marketing Skills:** Systematic usage required

### Operations
- **WellSky API:** ✅ Active (see `wellsky-api-setup.md`)

---

## Accountability Framework

### Daily Standups
Each team reports:
1. **Yesterday:** What was accomplished?
2. **Today:** What's the plan?
3. **Blockers:** What's preventing progress?
4. **KPIs:** Quick snapshot (red/yellow/green)
5. **Actions:** Specific deliverables with owners

### Escalation to Jason
**Immediate alert:**
- 🔴 Red KPIs (cash <3mo, build broken, ROAS <1:1)
- 🔴 Production issues
- 🔴 Major blockers (>24hr impact)

**Weekly summary only:**
- ⚠️ Yellow KPIs
- ⚠️ Minor blockers
- ✅ Green metrics (routine updates)

---

## File Structure

```
elite-teams/
├── README.md (this file)
├── TEAMS.md (team activation triggers)
│
├── Finance Team
│   ├── finance-team.md
│   ├── finance-team-optimization-plan.md
│   ├── gigi-finance-commands.md
│   └── finance-daily-pulse.py ⭐
│
├── Tech Team
│   ├── tech-team.md
│   ├── tech-team-optimization-plan.md
│   └── gigi-tech-commands.md
│
├── Marketing Team
│   ├── marketing-team.md
│   ├── marketing-optimization-plan.md
│   └── gigi-marketing-commands.md
│
├── Operations Team
│   ├── operations-team.md
│   └── wellsky-api-setup.md ⭐
```

---

## Example Workflows

### Morning Routine (Automated via Heartbeat)
```bash
# 8am MT - Gigi runs automatically
python3 /Users/shulmeister/mac-mini-apps/clawd/elite-teams/finance-daily-pulse.py
# Checks GitHub Actions for tech team
# Checks GA4 for marketing team
# Surfaces urgent items only to Jason
```

### Manual Deep Dive
```bash
# Finance deep dive
python3 /Users/shulmeister/mac-mini-apps/clawd/tools/quickbooks/qb.py pnl ThisMonth
python3 /Users/shulmeister/mac-mini-apps/clawd/tools/quickbooks/qb.py balance
python3 /Users/shulmeister/mac-mini-apps/clawd/tools/quickbooks/qb.py customers

# Marketing deep dive
"Gigi, run full marketing audit using skill modules"
"Gigi, analyze organic traffic trends for past 30 days"

# Tech deep dive
"Gigi, check GitHub PR queue and code review times"
"Gigi, analyze Mac Mini resource usage and costs"
```

### Emergency Response
```bash
# Finance emergency
"Gigi, activate cash crisis protocol - DSO hit 65 days"

# Tech emergency
"Gigi, production is down - coordinate incident response"

# Marketing emergency
"Gigi, Google Ads ROAS dropped to 0.8 - pause underperforming campaigns"
```

---

## Success Metrics

### Q1 2026 Targets
- **Finance:** DSO <40 days, 6+ months cash runway, 99% forecast accuracy
- **Tech:** 95% build success, <24hr code review, 80%+ test coverage
- **Marketing:** 3:1 ROAS average, 100% skill module compliance, 15% organic growth

### Measurement
- **Daily:** Automated pulse checks via heartbeat
- **Weekly:** Monday team reviews (summary to Jason)
- **Monthly:** Full KPI dashboard (first Monday of month)

---

**Gigi runs the operations. Jason approves the strategy. Elite teams execute.**

Last updated: February 4, 2026
