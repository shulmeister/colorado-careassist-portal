# Colorado CareAssist — Proprietary Technology Platform

**Confidential — Prepared for Strategic Investment Discussion**

---

## Executive Summary

Colorado CareAssist has built a vertically integrated, AI-native technology platform purpose-built for non-medical home care operations. The platform was designed from the ground up to eliminate the patchwork of 15–20 SaaS tools that most home care agencies rely on, replacing them with a single, unified system running on proprietary infrastructure.

The result: **a turnkey technology stack that can be deployed across acquired agencies in days, not months** — driving immediate margin expansion, operational consistency, and competitive differentiation in an industry still running on paper, fax machines, and spreadsheets.

**Development replacement value:** $375,000 – $635,000
**Annual SaaS replacement value:** $23,000 – $59,000 per agency
**Monthly infrastructure cost:** <$50/mo (self-hosted, no cloud dependency)

---

## Why This Matters for a Roll-Up

The U.S. non-medical home care market is $120B+ and highly fragmented — 30,000+ agencies, most owner-operated with fewer than 50 caregivers. The typical acquisition target runs on:

- Paper intake forms and fax machines
- GoFormz or PDF packets for onboarding
- No CRM — referrals tracked in email or a notebook
- Manual scheduling via phone calls and whiteboards
- No AI, no automation, no analytics

**This platform eliminates all of that on Day 1 post-acquisition.** Every tool below is production-tested, integrated with WellSky (the industry-standard EHR), and operational today.

---

## Platform Architecture

```
                    ┌──────────────────────────────────────────┐
                    │         UNIFIED OPERATIONS PORTAL         │
                    │     portal.coloradocareassist.com         │
                    │         38 integrated tools               │
                    │        156 database tables                │
                    └─────────────────┬────────────────────────┘
                                      │
          ┌───────────────────────────┼────────────────────────────┐
          │                           │                            │
    ┌─────┴──────┐           ┌────────┴────────┐          ┌───────┴───────┐
    │  GIGI AI   │           │   OPERATIONS    │          │   BUSINESS    │
    │ Chief of   │           │   AUTOMATION    │          │  INTELLIGENCE │
    │  Staff     │           │                 │          │               │
    │            │           │ • WellSky Sync  │          │ • Sales CRM   │
    │ 6 Channels │           │ • Client Intake │          │ • Marketing   │
    │ 34 Tools   │           │ • Onboarding    │          │ • Recruiting  │
    │ 24/7 AI    │           │ • Fax           │          │ • Analytics   │
    │            │           │ • Scheduling    │          │ • QBO KPIs    │
    └────────────┘           └─────────────────┘          └───────────────┘
          │                           │                            │
          └───────────────────────────┼────────────────────────────┘
                                      │
                    ┌─────────────────┴────────────────────────┐
                    │          INFRASTRUCTURE LAYER             │
                    │   Self-hosted · Cloudflare · PostgreSQL   │
                    │   Zero cloud dependency · $50/mo total    │
                    └──────────────────────────────────────────┘
```

---

## I. Gigi — AI Chief of Staff

**Gigi is the centerpiece of the platform.** A multi-channel AI assistant purpose-built for home care operations, Gigi handles voice calls, SMS, fax, internal messaging, and Telegram — all through a single unified intelligence with persistent memory and 34 integrated tool capabilities.

### Channels

| Channel | Technology | Use Case |
|---------|-----------|----------|
| **Voice (inbound calls)** | Retell AI + Custom LLM + ElevenLabs | Clients and caregivers call the main business line and speak directly with Gigi. She looks up schedules, logs call-outs, transfers emergencies to humans. |
| **SMS** | RingCentral polling | Caregivers text in sick calls, clock in/out, and shift questions. Gigi responds with operational data from WellSky. |
| **Direct Messages** | RingCentral Glip | Owner/manager gets full Gigi capability — web search, email, calendar, AI research — via internal chat. |
| **Telegram** | Telegram Bot API | Primary mobile interface for management. Full tool access including deep research, browser automation, and Claude Code integration. |
| **Fax** | RingCentral Fax API | Inbound/outbound fax with automatic PDF processing, Telegram and email alerts on receipt. |
| **API / Siri / Shortcuts** | REST API | Voice-activated queries via Apple Shortcuts: "Hey Siri, ask Gigi who's working today." |

### AI Capabilities

- **34 integrated tools** — WellSky patient lookup, shift search, caregiver availability, email/calendar, web search, stock/crypto prices, concert tickets, AR reports, and more
- **Persistent memory** — PostgreSQL-backed memory system with save/recall/forget. Gigi remembers preferences, corrections, and patterns across sessions
- **Self-learning** — Shadow mode captures Gigi's draft SMS responses, compares to staff actual replies, and creates correction memories automatically
- **Failure handling** — 10 failure protocols with meltdown detection (3 failures in 5 minutes triggers escalation)
- **Constitutional AI** — 10 non-negotiable operating laws governing when to transfer to humans, never make medical decisions, and always escalate emergencies

### What This Replaces

| Legacy Approach | Cost | Gigi Replacement |
|----------------|------|-----------------|
| After-hours answering service | $300 – $600/mo | 24/7 AI voice with full system access |
| Part-time admin for scheduling calls | $2,000 – $3,000/mo | Automated shift lookup and caregiver matching |
| Manual fax monitoring | Staff time | Auto-download, alert, and file |
| SMS back-and-forth for call-outs | Staff time | Automated logging + replacement finder |

---

## II. Operations Suite

### Client Portal — `client.coloradocareassist.com`
Digital client intake replacing paper packets and GoFormz. Families complete assessment forms, service agreements, and consent documents online. Data syncs directly to WellSky as a new patient record with demographics, insurance, and care preferences.

**Replaces:** GoFormz client packets ($100 – $200/mo), manual data entry into WellSky

### Employee Onboarding Portal — `employee.coloradocareassist.com`
End-to-end caregiver onboarding with candidate tracking, compliance document collection, OpenSign e-signatures, background check integration, and automatic WellSky practitioner record creation on hire.

**Replaces:** GoFormz employee packets + BambooHR ($150 – $300/mo), manual WellSky data entry

### Fax — Built into Portal
Full send/receive fax with Inbox/Sent/Outbox tabs, multi-file upload, drag-and-drop page reorder, cover page with company letterhead, and inline PDF preview. Inbound faxes trigger automatic Telegram and email alerts. Two company numbers supported.

**Replaces:** Fax.Plus ($120/yr), eFax ($200/yr)

### VA Plan of Care Generator
Converts VA Form 10-7080 data into formatted Plans of Care with automatic PDF naming. Purpose-built for VA Community Care referrals — a growing segment as the VA shifts to community-based care.

**No commercial equivalent exists.**

### VA RFS Converter
Converts referral face sheets into VA Form 10-10172 Request for Services. AI-powered document parsing pre-fills form fields from uploaded PDFs.

**No commercial equivalent exists.**

### WellSky Payroll Converter
Transforms WellSky timesheet exports into the format required by Adams Keegan payroll processing. Eliminates hours of manual spreadsheet manipulation every pay period.

**No commercial equivalent exists.**

---

## III. Business Intelligence

### Sales Dashboard & CRM
Full sales pipeline with deal stages, contact management, activity tracking, and bidirectional Brevo sync. AI-powered face sheet scanner on deal creation parses uploaded referral documents to pre-fill contact fields.

**WellSky lifecycle integration:** Deals automatically create WellSky prospect records. Stage changes (Qualified → Assessment → Closed Won) sync in real-time. "Closed Won" converts prospects to active patients.

**Replaces:** HubSpot or Salesforce ($100 – $300/mo)

### Recruiter Dashboard
Applicant tracking for caregiver recruiting with pipeline stages, source tracking, and interview scheduling.

**Replaces:** JazzHR or Workable ($50 – $150/mo)

### Marketing Dashboard
Campaign performance analytics aggregating Google Ads, Meta Ads, and organic channels.

**Replaces:** Databox or AgencyAnalytics ($50 – $75/mo)

### QBO Dashboard — `qbo.coloradocareassist.com`
Real-time financial KPIs pulled from QuickBooks Online: revenue, expenses, cash flow, AR aging, and margin trends.

**Replaces:** Custom BI tools or Fathom ($40 – $100/mo)

---

## IV. Infrastructure

### Self-Hosted Architecture

The entire platform runs on a single Apple Mac Mini with:
- **PostgreSQL 17** — 156 tables, full relational data model
- **Cloudflare Tunnel** — zero-trust ingress, no open ports, DDoS protection
- **Tailscale** — secure remote management
- **Automated backups** — daily PostgreSQL dumps + config archives to Google Drive
- **Health monitoring** — 5-minute service checks with auto-restart and Telegram alerts
- **Staging environment** — full staging replica for risk-free development and testing

### Deployed Applications

| Application | URL | Purpose |
|-------------|-----|---------|
| Operations Portal | portal.coloradocareassist.com | Unified command center (38 tools) |
| Marketing Website | coloradocareassist.com | Consumer-facing (Next.js, SEO-optimized) |
| Employee Portal | employee.coloradocareassist.com | Caregiver onboarding + e-signatures |
| Client Portal | client.coloradocareassist.com | Client intake + WellSky sync |
| Status Dashboard | status.coloradocareassist.com | Infrastructure health monitoring |
| QBO Dashboard | qbo.coloradocareassist.com | Financial KPIs from QuickBooks |
| PowderPulse | powderpulse.coloradocareassist.com | Ski conditions (demonstrates platform flexibility) |
| Elite Trading | elitetrading.coloradocareassist.com | Quantitative trading tools |
| Trading Dashboard | trading.coloradocareassist.com | Algorithmic trading P&L |

### Monthly Operating Cost

| Item | Cost |
|------|------|
| Hardware (Mac Mini, amortized) | ~$50/mo |
| Anthropic API (Claude Haiku) | ~$20 – $40/mo |
| RingCentral (already in use) | $0 incremental |
| Cloudflare (free tier) | $0 |
| Domains | ~$3/mo |
| **Total** | **<$100/mo** |

---

## V. Roll-Up Deployment Model

### The Playbook: Acquire → Deploy → Optimize

**Week 1 — Immediate Wins**
- Deploy portal with sales CRM, marketing dashboard, and recruiting tools
- Stand up Client Portal for digital intake (replaces paper)
- Stand up Employee Portal for caregiver onboarding (replaces GoFormz)
- Activate Gigi on the agency's phone system (24/7 AI coverage)

**Week 2–4 — Integration**
- Connect WellSky (or migrate to WellSky)
- Configure VA form tools (if applicable)
- Migrate payroll data flow
- Train staff on portal tools

**Ongoing — Compounding Value**
- Gigi's memory system learns agency-specific patterns
- Self-learning pipeline improves SMS response quality over time
- Sales CRM captures referral sources and conversion data
- Analytics surface operational inefficiencies across the portfolio

### Unit Economics Impact Per Acquired Agency

| Lever | Annual Savings |
|-------|---------------|
| SaaS tool consolidation | $23,000 – $59,000 |
| Admin labor reduction (AI handling calls/SMS) | $24,000 – $36,000 |
| Faster onboarding (digital vs. paper) | $5,000 – $10,000 |
| Reduced missed shifts (AI call-out handling) | $10,000 – $20,000 |
| **Total estimated savings per agency** | **$62,000 – $125,000/yr** |

At 20 acquired agencies: **$1.24M – $2.5M in annual technology-driven savings.**

---

## VI. Competitive Moat

1. **Vertical integration** — Not a collection of APIs. A single unified platform where every tool shares the same database, the same AI, and the same user interface.

2. **WellSky-native** — Deep bidirectional integration with the dominant home care EHR. Prospects become patients. Shifts become timesheets. No CSV exports, no manual entry.

3. **AI-first, not AI-bolted-on** — Gigi isn't a chatbot added to an existing system. She is the system. Every operational workflow passes through her intelligence.

4. **Zero marginal cost to deploy** — The platform runs on commodity hardware. No per-seat SaaS fees. No cloud compute bills that scale with headcount. Adding an agency costs near zero.

5. **Proprietary tools with no commercial equivalent** — The VA form generators, payroll converters, and AI shift-filling engine solve problems that no vendor addresses because the market is too fragmented for them to care.

6. **Self-improving** — The shadow mode learning pipeline means Gigi gets better at every agency she operates in. The more agencies in the portfolio, the smarter the AI becomes across all of them.

---

## VII. Technology Summary

| Metric | Value |
|--------|-------|
| Portal tools | 38 |
| Database tables | 156 |
| AI channels | 6 (voice, SMS, fax, DM, Telegram, API) |
| AI tools per channel | Up to 34 |
| Deployed web applications | 9 |
| WellSky FHIR endpoints integrated | 10+ (Patients, Practitioners, Appointments, etc.) |
| Development replacement value | $375,000 – $635,000 |
| Annual SaaS replacement value | $23,000 – $59,000 per agency |
| Monthly infrastructure cost | <$100 |
| Time to deploy at acquired agency | 1 – 4 weeks |

---

*Built by Jason Schulmeister · Colorado CareAssist · February 2026*
*All systems production-tested and operational.*
