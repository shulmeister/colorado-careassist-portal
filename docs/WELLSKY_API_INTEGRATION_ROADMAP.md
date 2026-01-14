# WellSky/ClearCare Connect API Integration Roadmap
## Colorado Care Assist - Product & Technology Strategy
### Version 1.0 | January 14, 2026

---

## Executive Summary

### Why WellSky Integration Matters

Colorado Care Assist operates on two parallel technology stacks that currently do not communicate:

1. **WellSky Personal Care** - The operational backbone handling scheduling, EVV, billing, caregiver management, and client care plans
2. **CareAssist Unified Portal** - Our custom-built hub for sales CRM, recruiting, marketing analytics, and business development

**The Problem:** Staff manually re-enter data between systems. Sales closes a deal in the CRM, then someone creates the client in WellSky. Recruiters approve a caregiver hire, then someone onboards them in WellSky. Operations schedules care, but marketing has no visibility into capacity or client status.

**The Solution:** The WellSky Connect API provides read/write access to client, caregiver, schedule, and billing data. By building strategic integrations, we can:

- **Eliminate 15+ hours/week of duplicate data entry**
- **Provide real-time operational visibility to sales and marketing**
- **Enable automated workflows that reduce human error**
- **Create competitive advantages through data-driven marketing**

### Strategic Business Impact

| Metric | Current State | Post-Integration Target | Business Value |
|--------|---------------|------------------------|----------------|
| Client onboarding time | 2-3 hours manual entry | 15 minutes automated | Faster revenue realization |
| Caregiver onboarding | 4+ hours across systems | 45 minutes | Reduced time-to-productivity |
| Data accuracy | Manual sync errors weekly | 99%+ automated sync | Reduced compliance risk |
| Marketing response time | Days to get client status | Real-time | Improved lead nurturing |
| Sales visibility | Limited to CRM data | Full operational picture | Better forecasting |

### Investment Recommendation

**Phase 1 (Foundation):** 40-60 development hours, $8,000-12,000 estimated cost
**Phase 2 (Operational Intelligence):** 80-120 development hours, $15,000-25,000
**Phase 3 (Advanced Automation):** 100-150 development hours, $20,000-35,000

**Total Estimated Investment:** $43,000-72,000 over 6-9 months
**Estimated Annual Savings:** $35,000+ (staff time) + revenue acceleration from improved operations

---

## Integration Opportunities Matrix

### Data Flow Analysis: WellSky to Colorado Care Assist Systems

```
                    +-------------------+
                    |   WellSky API     |
                    | Connect Platform  |
                    +--------+----------+
                             |
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
+-------+-------+    +-------+-------+    +-------+-------+
| Sales CRM     |    | Recruiting    |    | Marketing     |
| Dashboard     |    | Dashboard     |    | Dashboard     |
+---------------+    +---------------+    +---------------+
| - Deals       |    | - Leads       |    | - Analytics   |
| - Contacts    |    | - Candidates  |    | - Campaigns   |
| - Companies   |    | - Hires       |    | - Metrics     |
| - Activities  |    | - Onboarding  |    | - Reports     |
+---------------+    +---------------+    +---------------+
```

### Detailed Data Flow Mapping

#### FROM WellSky --> TO Portal Systems

| WellSky Data | Destination System | Use Case | Priority |
|--------------|-------------------|----------|----------|
| **Client Profiles** | Sales CRM (Deals) | Auto-update deal status when client onboarded | Critical |
| **Client Status** (active/on-hold/discharged) | Sales CRM, Marketing | Track client lifecycle, trigger win-back campaigns | High |
| **Schedule/Shifts** | Sales CRM | Show capacity for pipeline deals | High |
| **Caregiver Profiles** | Recruiting Dashboard | Sync hired candidates to WellSky employees | Critical |
| **Caregiver Availability** | Recruiting Dashboard | Show scheduling capacity for recruiting priorities | Medium |
| **Billing/Invoices** | Sales CRM (Financial) | Track revenue by referral source | Medium |
| **Care Plan Data** | Portal (CarePlanStatus) | Sync care plan updates to quality tracking | Medium |
| **EVV Clock-ins** | Marketing Dashboard | Calculate hours delivered for testimonials/stats | Low |
| **Family Room Activity** | Marketing Dashboard | Track family engagement for satisfaction metrics | Low |

#### FROM Portal Systems --> TO WellSky

| Portal Data | WellSky Destination | Use Case | Priority |
|-------------|---------------------|----------|----------|
| **Closed Deal (client info)** | New Client Profile | Auto-create client when deal closes | Critical |
| **Hired Candidate** | New Caregiver Profile | Auto-onboard caregiver when hire approved | Critical |
| **Referral Source Info** | Client Referral Source | Link client to referring organization | High |
| **Lead Contact Details** | Client Emergency Contacts | Push family/POA info from CRM | Medium |
| **Quality Visit Results** | Care Documentation | Sync QA visit notes to client record | Low |
| **Survey Responses** | Client Notes | Log satisfaction data in WellSky | Low |

---

## PRIORITY ADDITIONS: Critical Workflow Integrations

Based on real operational pain points, these integrations address the highest-impact daily workflows.

### GoFormz → WellSky Automation

**Pain Point:** Staff complete employee/client packets in GoFormz, then manually re-enter all data into WellSky.

#### Employee Packet Completion → WellSky Caregiver Creation

**Trigger:** Employee packet marked "Complete" in GoFormz
**Action:** Auto-create caregiver profile in WellSky with all packet data

```
GoFormz Employee Packet Fields → WellSky Caregiver Profile
─────────────────────────────────────────────────────────────
First Name, Last Name         → firstName, lastName
SSN (last 4)                  → taxId (partial)
Address, City, State, Zip     → address
Phone, Email                  → phone, email
Emergency Contact             → emergencyContact
Available Days/Times          → availability
Certifications                → certifications
Transportation Type           → transportation
Service Areas                 → serviceAreas
Direct Deposit Info           → payrollInfo
─────────────────────────────────────────────────────────────
```

**Business Value:** Eliminates 45-60 min of manual data entry per new hire

#### Client Packet Completion → WellSky Client Creation

**Trigger:** Client packet marked "Complete" in GoFormz
**Action:** Auto-create client profile in WellSky with all intake data

```
GoFormz Client Packet Fields → WellSky Client Profile
─────────────────────────────────────────────────────────────
Client Name                   → firstName, lastName
Address                       → address
Phone, Email                  → phone, email
Emergency Contact/POA         → emergencyContacts
Physician Info                → physician
Diagnosis/Conditions          → medicalConditions
Care Preferences              → carePreferences
Authorized Services           → authorizedServices
Payer Information             → payerSource
Start Date                    → startDate
─────────────────────────────────────────────────────────────
```

**Business Value:** Eliminates 30-45 min of manual data entry per new client

---

### Sales Dashboard → WellSky Prospect/Client Pipeline

**Pain Point:** Deals in CRM exist independently from WellSky prospects, causing duplicate tracking.

#### Deal Creation → WellSky Prospect (Optional)

**Trigger:** User clicks "Create as WellSky Prospect" on deal
**Action:** Creates prospect record in WellSky sales pipeline

```
Sales Dashboard Deal → WellSky Prospect
─────────────────────────────────────────────────────────────
Deal Name                     → prospectName
Contact Name                  → primaryContact
Contact Phone/Email           → contactInfo
Referral Source               → referralSource
Estimated Hours               → estimatedHours
Expected Close Date           → followUpDate
Notes                         → notes
Deal Stage                    → prospectStatus
─────────────────────────────────────────────────────────────
```

**Business Value:** Single source of truth for sales pipeline across both systems

#### Deal Won → WellSky Client (Automatic)

**Trigger:** Deal stage changes to "Closed/Won"
**Action:** Auto-convert prospect to client OR create new client in WellSky

---

### Recruiting Dashboard → WellSky Applicant List

**Pain Point:** Recruiting tracks leads in dashboard but WellSky has separate applicant tracking.

#### Push Lead to WellSky Applicants (On Request)

**Trigger:** User clicks "Send to WellSky Applicants" on recruiting lead
**Action:** Creates applicant record in WellSky ATS

```
Recruiting Lead → WellSky Applicant
─────────────────────────────────────────────────────────────
Name                          → applicantName
Phone, Email                  → contactInfo
Source (Indeed, FB, etc.)     → applicationSource
Applied Date                  → applicationDate
Notes/Interview Notes         → notes
Status                        → applicantStatus
Resume (if attached)          → documents
─────────────────────────────────────────────────────────────
```

**Sync Back:** WellSky applicant status changes sync back to recruiting dashboard

**Business Value:** Unified applicant tracking, no duplicate entry

---

## CRITICAL: AI-Powered Open Shift Filling (End the No-Call No-Show Crisis)

**This is the #1 daily pain point.** The no-call no-show is what one industry advisor called "the nuclear event in home care" - it can "blow up a client relationship in one fell swoop."

When caregivers call off (or worse, don't show up at all), coordinators scramble to find replacements through manual phone calls and texts. This takes 30-60 minutes per incident and often fails.

**Reference:** This solution mirrors what [Careswitch built](https://www.careswitch.com/blog/the-end-of-the-no-call-no-show) - but we'll build it in-house, integrated with YOUR existing stack.

### The Problem

```
Current "Fire Drill" Workflow:
─────────────────────────────────────────────────────────────
1. Caregiver texts/calls: "I can't make my 2pm shift"
2. Coordinator checks WellSky for shift details
3. Coordinator manually searches for available caregivers
4. Coordinator calls/texts each one individually
5. Most don't answer or aren't available
6. Repeat steps 3-4 until someone accepts
7. Update WellSky with new assignment
8. Notify client of caregiver change

Time: 30-60 minutes (often during already busy periods)
Success Rate: ~70% (some shifts go unfilled)
Staff Stress: EXTREME
─────────────────────────────────────────────────────────────
```

### The Solution: Automated Shift Filling Engine

Build an AI-powered system that integrates:
- **WellSky API** - Get open shifts, caregiver availability, skills, location
- **RingCentral** - Automated SMS/calls to caregivers
- **BeeTexting** - High-volume SMS campaigns with responses
- **AI Logic** - Smart matching, preference learning, escalation

```
Automated Shift Filling Workflow:
─────────────────────────────────────────────────────────────
1. DETECT: Caregiver texts "can't make shift" → AI interprets intent
2. IDENTIFY: System pulls shift details from WellSky API
3. MATCH: AI queries WellSky for qualified available caregivers:
   - Has required skills/certifications
   - Available during shift time
   - Within reasonable distance
   - No overtime conflicts
   - Client compatibility (past assignments)
   - Caregiver preferences (prefers this client)
4. OUTREACH: Parallel SMS blast via RingCentral/BeeTexting:
   "Hi [Name], can you cover a 2-6pm shift in Aurora today?
    Client: [First Name]. Reply YES to accept or NO to decline."
5. ACCEPT: First YES response triggers:
   - Auto-update WellSky schedule
   - Confirm to accepting caregiver
   - Notify client of change
   - Close outreach to others ("Shift filled, thanks!")
6. ESCALATE: If no response in 15 min, escalate to coordinator
7. LOG: All activity logged for reporting

Time: 2-5 minutes (fully automated)
Success Rate: 85-90%
Staff Stress: MINIMAL
─────────────────────────────────────────────────────────────
```

### Technical Architecture

```
+------------------------------------------------------------------+
|                    SHIFT FILLING ENGINE                            |
+------------------------------------------------------------------+
|                                                                    |
|  INCOMING CHANNELS                    AI PROCESSING                |
|  ─────────────────                    ──────────────               |
|  [RingCentral SMS] ────┐                                          |
|  [RingCentral Call] ───┼──► [Intent Detection] ──► [Shift Lookup] |
|  [BeeTexting SMS] ─────┤         │                      │         |
|  [WellSky Alert] ──────┘         │                      │         |
|                                  ▼                      ▼         |
|                          [Call-Off Detected]    [WellSky API]     |
|                                  │              Get shift details  |
|                                  │                      │         |
|                                  ▼                      ▼         |
|                          [Caregiver Matcher]◄──────────────       |
|                                  │                                |
|                    ┌─────────────┼─────────────┐                  |
|                    ▼             ▼             ▼                  |
|              [Tier 1]       [Tier 2]      [Tier 3]                |
|              Best match     Good match    Any qualified           |
|              Same client    Same area     Available               |
|              before         Similar hrs   Will pay OT             |
|                    │             │             │                  |
|                    └─────────────┼─────────────┘                  |
|                                  ▼                                |
|  OUTREACH                 [SMS Blast via                          |
|  ────────                  RingCentral/BeeTexting]                |
|                                  │                                |
|                    ┌─────────────┼─────────────┐                  |
|                    ▼             ▼             ▼                  |
|              [Response]    [Response]    [Response]               |
|               "YES"         "NO"         [timeout]                |
|                    │             │             │                  |
|                    ▼             │             │                  |
|              [ACCEPT]            │             │                  |
|              Update WellSky      │             │                  |
|              Notify client       │             │                  |
|              Confirm CG          │             │                  |
|              Close others        │             │                  |
|                                  │             │                  |
|                    No acceptance after 15 min?                    |
|                                  │                                |
|                                  ▼                                |
|                          [ESCALATE]                               |
|                          Alert coordinator                        |
|                          Provide summary                          |
|                                                                    |
+------------------------------------------------------------------+
```

### Caregiver Matching Algorithm

```python
def find_replacement_caregivers(shift, wellsky_service):
    """
    Find and rank caregivers who can cover an open shift.
    Returns tiered list for outreach priority.
    """

    # Get shift requirements from WellSky
    shift_details = wellsky_service.get_shift(shift.id)
    client = wellsky_service.get_client(shift_details.client_id)

    # Get all potentially available caregivers
    all_caregivers = wellsky_service.get_caregivers(
        status='active',
        available_on=shift_details.date
    )

    candidates = []

    for cg in all_caregivers:
        # FILTER: Must meet basic requirements
        if not meets_requirements(cg, shift_details):
            continue

        # SCORE: Rank by fit
        score = calculate_match_score(cg, shift_details, client)

        candidates.append({
            'caregiver': cg,
            'score': score,
            'tier': get_tier(score)
        })

    # Sort by score, return tiered
    return sorted(candidates, key=lambda x: x['score'], reverse=True)


def calculate_match_score(caregiver, shift, client):
    """
    Score 0-100 for caregiver-shift fit.
    Higher = better match, contact first.
    """
    score = 0

    # Has worked with this client before (+30)
    if has_prior_assignment(caregiver, client):
        score += 30

    # Client specifically requested this CG (+20)
    if client.preferred_caregivers and caregiver.id in client.preferred_caregivers:
        score += 20

    # Lives nearby - within 15 min drive (+15)
    distance = calculate_distance(caregiver.address, client.address)
    if distance < 10:
        score += 15
    elif distance < 20:
        score += 10
    elif distance < 30:
        score += 5

    # Available and not near overtime (+10)
    weekly_hours = get_weekly_hours(caregiver)
    if weekly_hours < 32:
        score += 10
    elif weekly_hours < 38:
        score += 5
    # Over 40 = no bonus, may need OT approval

    # High performer - above avg client ratings (+10)
    if caregiver.avg_rating and caregiver.avg_rating > 4.5:
        score += 10
    elif caregiver.avg_rating and caregiver.avg_rating > 4.0:
        score += 5

    # Caregiver prefers this shift type (+5)
    if shift.type in caregiver.preferred_shift_types:
        score += 5

    # Recently accepted similar offers (+5)
    if recently_accepted_offers(caregiver):
        score += 5

    return min(score, 100)
```

### SMS Templates

```
INITIAL OUTREACH:
"Hi [FirstName]! Can you cover a shift today?
📍 [City] (15 min from you)
⏰ [StartTime]-[EndTime]
💰 [Hours] hrs
Reply YES to accept or NO to pass."

ACCEPTANCE CONFIRMATION:
"You're confirmed for [ClientFirstName]'s shift!
📍 [Address]
⏰ [StartTime]-[EndTime]
📝 Care notes in WellSky app
Questions? Call office: [Number]"

SHIFT FILLED (to others):
"Thanks! This shift has been filled.
We appreciate your quick response! 🙏"

NO RESPONSE ESCALATION (to coordinator):
"⚠️ OPEN SHIFT ALERT
[ClientName] - [Date] [Time]
Location: [City]
Contacted [X] caregivers, no acceptance.
Top candidates who didn't respond:
- [Name1] - [Phone]
- [Name2] - [Phone]
Requires manual follow-up."
```

### Implementation Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Intent Detection** | GPT-4/Claude API | Parse incoming messages for call-off intent |
| **Shift Lookup** | WellSky API | Get shift details, client info |
| **Caregiver Query** | WellSky API | Get available, qualified caregivers |
| **Distance Calc** | Google Maps API | Calculate drive times |
| **SMS Outreach** | RingCentral/BeeTexting | Parallel text blast |
| **Response Handler** | Webhook listeners | Process YES/NO responses |
| **Schedule Update** | WellSky API | Reassign shift |
| **Notification** | RingCentral/Brevo | Confirm to all parties |
| **Escalation** | Portal alerts | Notify coordinators |
| **Logging** | PostgreSQL | Audit trail, analytics |

### Business Impact

| Metric | Before | After | Impact |
|--------|--------|-------|--------|
| Time to fill open shift | 30-60 min | 2-5 min | **90% reduction** |
| Shift fill rate | ~70% | ~90% | **20% improvement** |
| Coordinator stress | High | Low | **Quality of life** |
| Missed visits | 2-4/week | <1/week | **Client satisfaction** |
| After-hours escalations | Frequent | Rare | **Work-life balance** |

---

### ADVANCED: Predictive No-Show Prevention

Beyond reactive shift filling, the next level is **predicting which shifts are at risk BEFORE the no-show happens**.

Careswitch reports their prediction algorithms achieve "freaky-high level of accuracy" by combining factors that "don't all have to do with the shift at all, or even caregiver characteristics you'd expect."

#### Risk Prediction Factors

```python
def calculate_shift_risk_score(shift, caregiver, wellsky_data, historical_data):
    """
    Predict likelihood of no-show/call-off for upcoming shift.
    Score 0-100, higher = more risk.
    """
    risk_score = 0

    # CAREGIVER HISTORY FACTORS
    # ──────────────────────────────────────────────

    # Call-off rate (last 90 days)
    calloff_rate = caregiver.calloffs_90d / caregiver.scheduled_shifts_90d
    if calloff_rate > 0.15:
        risk_score += 25
    elif calloff_rate > 0.10:
        risk_score += 15
    elif calloff_rate > 0.05:
        risk_score += 5

    # Recent pattern - called off recently?
    if caregiver.last_calloff_days < 7:
        risk_score += 15
    elif caregiver.last_calloff_days < 14:
        risk_score += 8

    # Tenure - newer caregivers more likely to no-show
    if caregiver.tenure_days < 30:
        risk_score += 15
    elif caregiver.tenure_days < 90:
        risk_score += 8

    # SHIFT CHARACTERISTIC FACTORS
    # ──────────────────────────────────────────────

    # Early morning shifts higher risk
    if shift.start_time.hour < 7:
        risk_score += 10

    # Weekend shifts higher risk
    if shift.date.weekday() >= 5:
        risk_score += 8

    # Long shifts (8+ hours) higher risk
    if shift.duration_hours >= 8:
        risk_score += 5

    # CLIENT RELATIONSHIP FACTORS
    # ──────────────────────────────────────────────

    # First time with this client?
    if not has_prior_assignment(caregiver, shift.client):
        risk_score += 10

    # Difficult client history?
    if shift.client.difficulty_score and shift.client.difficulty_score > 3:
        risk_score += 10

    # EXTERNAL FACTORS
    # ──────────────────────────────────────────────

    # Weather forecast (snow, extreme cold)
    if get_weather_risk(shift.date, shift.location):
        risk_score += 15

    # Holiday proximity
    if is_near_holiday(shift.date):
        risk_score += 10

    # Payday timing (day after payday = higher risk historically)
    if is_day_after_payday(shift.date):
        risk_score += 5

    # ENGAGEMENT SIGNALS
    # ──────────────────────────────────────────────

    # Hasn't confirmed shift (if confirmation system exists)
    if not shift.confirmed and shift.hours_until < 24:
        risk_score += 20

    # Low engagement score (TeamEngage/app activity)
    if caregiver.engagement_score and caregiver.engagement_score < 50:
        risk_score += 10

    return min(risk_score, 100)
```

#### Proactive Intervention Workflow

```
For shifts scoring > 60 risk (24+ hours out):
─────────────────────────────────────────────────────────────
1. FLAG: Shift appears on "At-Risk Shifts" dashboard
2. CONFIRM: Auto-send confirmation request to caregiver
   "Hi [Name], confirming your shift tomorrow at [Time].
    Reply YES to confirm or call us if there's an issue."
3. BACKUP: Pre-identify 2-3 backup caregivers
4. ALERT: Notify coordinator of high-risk shift
5. PREPARE: Have replacement outreach ready to trigger

If no confirmation received:
─────────────────────────────────────────────────────────────
6. ESCALATE: Call caregiver directly
7. ACTIVATE: Begin backup outreach if no response
8. FILL: Complete replacement before shift time
─────────────────────────────────────────────────────────────
```

#### At-Risk Shift Dashboard Widget

```
+------------------------------------------------------------------+
|  AT-RISK SHIFTS (Next 48 Hours)                    [Auto-Refresh] |
+------------------------------------------------------------------+
| Risk | Caregiver      | Client      | Date/Time    | Status      |
|------|----------------|-------------|--------------|-------------|
| 🔴 82| Maria G.       | Johnson, R. | Tomorrow 7AM | Unconfirmed |
| 🟠 68| Tyler M.       | Smith, B.   | Tomorrow 2PM | Confirmed   |
| 🟡 55| Ashley K.      | Davis, L.   | Wed 9AM      | Confirmed   |
+------------------------------------------------------------------+
| [Request Confirmations] [Pre-Stage Backups] [View All Shifts]    |
+------------------------------------------------------------------+
```

#### Business Value of Prediction

| Metric | Reactive Only | With Prediction | Impact |
|--------|---------------|-----------------|--------|
| No-shows caught | After the fact | 4-24 hrs ahead | **Proactive** |
| Client disruption | Common | Rare | **Satisfaction** |
| Emergency scrambles | Daily | Weekly | **90% reduction** |
| Coordinator planning | Impossible | Data-driven | **Predictable** |

### Competitive Advantage

Companies like [Zingage](https://www.zingage.com), [Alden Health](https://www.alden.health/), and [AxisCare](https://axiscare.com/) are building similar AI scheduling tools. By building this in-house integrated with YOUR existing tech stack (WellSky + RingCentral + BeeTexting + Portal), Colorado Care Assist can:

1. **Own the technology** - No monthly SaaS fees ($500-2000/month)
2. **Customize completely** - Fit your exact workflows
3. **Integrate deeply** - Connect to your CRM, recruiting, marketing
4. **Build competitive moat** - Operational excellence competitors can't match

### Priority: P0 (Highest)

This should be the FIRST major integration built after foundation authentication.

---

## Advanced Operational Features (Inspired by Industry Leaders)

Based on analysis of [Phoebe](https://www.phoebe.work/), [Zingage](https://www.zingage.com), [Alden](https://www.alden.health/), and other AI scheduling leaders, here are operational features that address real day-to-day pain points:

### Clock-In/Clock-Out Monitoring & Reminders

**The Problem:** Caregivers forget to clock in/out, causing EVV compliance issues and payroll headaches.

**The Solution:**

```
Clock-In Reminder Flow:
─────────────────────────────────────────────────────────────
Shift starts at 9:00 AM
│
├─ 8:45 AM: "Good morning [Name]! Reminder: Your shift with
│            [Client] starts at 9:00 AM. Don't forget to
│            clock in when you arrive! 📍"
│
├─ 9:05 AM: (No clock-in detected)
│           "Hi [Name], we noticed you haven't clocked in yet
│            for your shift at [Client]'s. Please clock in now
│            or reply if there's an issue."
│
├─ 9:15 AM: (Still no clock-in)
│           ESCALATE → Alert coordinator
│           "⚠️ [Caregiver] hasn't clocked in for [Client]
│            shift (started 9:00 AM). Last contact: [time]"
│
└─ If caregiver responds "running late" or "car trouble":
   → AI acknowledges, asks for ETA, notifies client
─────────────────────────────────────────────────────────────

Clock-Out Reminder Flow:
─────────────────────────────────────────────────────────────
Shift ends at 1:00 PM
│
├─ 1:00 PM: (No clock-out detected after 5 min)
│           "Hi [Name], your shift was scheduled to end at
│            1:00 PM. Please clock out when you leave! ⏰"
│
├─ 1:15 PM: (Still no clock-out)
│           ESCALATE → Alert coordinator
│           "⚠️ [Caregiver] hasn't clocked out from [Client]
│            shift (ended 1:00 PM). Verify status."
─────────────────────────────────────────────────────────────
```

**WellSky Integration:**
- Pull scheduled shifts and expected clock-in/out times
- Monitor EVV clock events in real-time
- Update shift status when caregiver responds

**Business Value:**
- Improved EVV compliance (critical for Medicaid/VA)
- Reduced payroll errors
- Early detection of no-shows
- Automatic documentation of issues

---

### Proactive Caregiver Availability Management

**The Problem:** Coordinators don't know current caregiver availability until they need to fill a shift, then spend hours calling around.

**The Solution:** Proactive weekly/bi-weekly availability check-ins

```
Weekly Availability Check-In (Sunday evening):
─────────────────────────────────────────────────────────────
"Hi [Name]! Quick check-in for the week ahead.

Your current scheduled hours: 24 hrs
Open shifts available in your area: 12 hrs

Are you looking for more hours this week?
Reply: YES for more, NO I'm good, or LESS if you need time off"

Response Handling:
─────────────────────────────────────────────────────────────
YES → "Great! What days/times work best for you this week?"
      → Update availability in WellSky
      → Flag as "seeking hours" for shift offers

NO  → "Perfect, you're all set! Let us know if anything changes."

LESS → "No problem. Which days do you need off?"
       → Create time-off request in WellSky
       → Alert coordinator if affects scheduled shifts
─────────────────────────────────────────────────────────────
```

**Ongoing Availability Updates:**
```
After shift completion:
─────────────────────────────────────────────────────────────
"Thanks for today's shift with [Client]!

Quick question: Are you available for a similar shift
tomorrow (Tue) 2-6pm in [Area]?
Reply YES or NO"

→ Build real-time availability database
→ Know who to contact BEFORE shifts open
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Always-current availability data
- Faster shift filling (know who wants hours)
- Better caregiver satisfaction (proactive, not reactive)
- Reduced turnover (engaged caregivers stay)

---

### Multi-Language Support

**The Problem:** Diverse caregiver workforce speaks multiple languages. English-only communication excludes or confuses some staff.

**The Solution:**

```
Language Detection & Switching:
─────────────────────────────────────────────────────────────
1. Pull preferred language from WellSky caregiver profile
2. Send initial outreach in preferred language
3. If caregiver responds in different language, detect and switch
4. All future communication in detected language

Supported Languages (via AI translation):
- English (default)
- Spanish
- Tagalog
- Vietnamese
- Haitian Creole
- Mandarin/Cantonese
- Russian
- Others as needed
─────────────────────────────────────────────────────────────

Example - Spanish Outreach:
"¡Hola [Nombre]! ¿Puedes cubrir un turno hoy?
📍 Aurora (15 min de ti)
⏰ 2:00 PM - 6:00 PM
Responde SÍ para aceptar o NO para pasar."
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Better response rates from non-English speakers
- Inclusive workplace culture
- Access to larger caregiver pool
- Reduced miscommunication

---

### Recurring Shift Management

**The Problem:** Many clients have recurring weekly schedules. Managing ongoing availability for recurring shifts is tedious.

**The Solution:**

```
Recurring Shift Confirmation Flow:
─────────────────────────────────────────────────────────────
Every [Sunday] for weekly recurring shifts:

"Hi [Name], confirming your recurring shifts this week:

📅 Mon 9am-1pm - [Client A]
📅 Wed 9am-1pm - [Client A]
📅 Fri 2pm-6pm - [Client B]

Reply ALL GOOD to confirm all, or tell us which
shifts you can't make."

Responses:
─────────────────────────────────────────────────────────────
"ALL GOOD" → Mark all confirmed
"Can't do Friday" → Trigger replacement search for Friday
"Need to switch Wed" → Ask for details, find coverage
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Early warning on recurring shift gaps
- Reduced last-minute scrambles
- Better client continuity
- Caregiver schedule visibility

---

### Multi-Shift Outreach

**The Problem:** When offering shifts, you contact caregivers one shift at a time. Inefficient for caregivers who want multiple shifts.

**The Solution:**

```
Bundled Shift Offer:
─────────────────────────────────────────────────────────────
Instead of 3 separate messages for 3 open shifts:

"Hi [Name]! We have multiple open shifts in your area:

1️⃣ Mon 2-6pm - [Client A] - Aurora
2️⃣ Tue 9am-1pm - [Client B] - Denver
3️⃣ Thu 2-6pm - [Client C] - Aurora

Reply with the numbers you want (e.g., '1 and 3')
or 'ALL' to take all three!"

Response Handling:
─────────────────────────────────────────────────────────────
"1 and 3" → Assign shifts 1 and 3, continue outreach for 2
"ALL"     → Assign all three, close outreach
"Just 2"  → Assign shift 2, continue outreach for 1 and 3
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Faster shift filling
- Better caregiver experience (one text vs. many)
- Caregivers can plan their week
- Reduced message fatigue

---

### Care Coordinator Workflow Optimization

**The Problem:** All alerts go to all coordinators. Noise overwhelms the signal.

**The Solution:**

```
Coordinator Assignment Sync from WellSky:
─────────────────────────────────────────────────────────────
Coordinator A → Clients 1-25 (Denver area)
Coordinator B → Clients 26-50 (Aurora area)
Coordinator C → Clients 51-75 (South suburbs)

Alert Routing:
─────────────────────────────────────────────────────────────
Client 12 shift issue → Alert Coordinator A only
Client 40 no-show    → Alert Coordinator B only
Client 60 complaint  → Alert Coordinator C only

Escalation (if primary coordinator unavailable):
→ Route to backup coordinator
→ Then to supervisor
─────────────────────────────────────────────────────────────
```

**Dashboard Filtering:**
```
Coordinator A sees:
┌──────────────────────────────────────────────────────────┐
│ MY SHIFTS (Coordinator A - Denver)          [Filter: My] │
├──────────────────────────────────────────────────────────┤
│ ✅ 8 Confirmed  │ ⚠️ 2 At-Risk  │ 🔴 1 Open             │
│                                                          │
│ [View All Agency Shifts]                                 │
└──────────────────────────────────────────────────────────┘
```

**Business Value:**
- Reduced alert fatigue
- Clear accountability
- Faster response (right person sees right issues)
- Scalable as agency grows

---

### Organizational Memory (Knowledge Retention)

**The Problem:** When coordinators leave, all their knowledge about caregiver preferences, client quirks, and "who to call first" walks out the door.

**The Solution:**

```
Automatic Knowledge Capture:
─────────────────────────────────────────────────────────────
Every shift fill, the system learns:
- Which caregivers respond fastest
- Which caregivers prefer certain clients
- Which caregivers decline certain shift times
- Which caregiver-client pairings get good feedback
- Which caregivers are reliable (accept and show up)
- Which caregivers flake (accept but cancel)

This becomes "Caregiver DNA":
─────────────────────────────────────────────────────────────
Caregiver: Maria G.
├─ Response Rate: 78% (responds to 78% of offers)
├─ Acceptance Rate: 45% (accepts 45% of offers)
├─ Reliability: 94% (shows up 94% of accepted shifts)
├─ Preferred Times: Mornings, Weekdays
├─ Preferred Areas: Aurora, Centennial
├─ Preferred Clients: Johnson R., Smith B. (worked 10+ times)
├─ Avoids: Overnight shifts, Downtown Denver
├─ Languages: English, Spanish
└─ Rating: 4.7/5.0 (client feedback)
─────────────────────────────────────────────────────────────
```

**Business Value:**
- New coordinators instantly effective
- No "starting from scratch" when staff turns over
- Data-driven caregiver matching
- Continuous improvement over time

---

### Off-Hours Automation

**The Problem:** Caregivers text at all hours. Coordinators either ignore (bad experience) or respond (burnout).

**The Solution:**

```
After-Hours Response Handling:
─────────────────────────────────────────────────────────────
Business Hours: 8am - 6pm M-F

Outside Business Hours:
─────────────────────────────────────────────────────────────
Caregiver texts: "I can't make my shift tomorrow"

Auto-Response:
"Thanks for letting us know! Our office is closed right now,
but I've logged your message. A coordinator will follow up
first thing in the morning.

If this is URGENT (you can't make a shift in the next 4 hours),
reply URGENT and I'll start looking for coverage now."

If "URGENT" → Trigger automated shift filling
If no reply → Queue for morning coordinator review
─────────────────────────────────────────────────────────────

Caregiver texts: "Do I work tomorrow?"

Auto-Response:
"Let me check... Yes! You're scheduled for:
📅 Tomorrow (Tue) 9am-1pm with [Client]
📍 [Address]

Reply CONFIRM to confirm or let me know if there's an issue."
─────────────────────────────────────────────────────────────
```

**Business Value:**
- 24/7 caregiver support without 24/7 staff
- Reduced coordinator burnout
- Better caregiver experience
- Urgent issues still handled

---

### Voice Call Capabilities (Advanced)

**The Problem:** Some caregivers don't respond to texts. Voice calls are more effective but time-consuming.

**The Solution:**

```
Parallel Voice Outreach:
─────────────────────────────────────────────────────────────
When SMS doesn't get response (or for urgent shifts):

1. System calls up to 50+ caregivers simultaneously
2. AI voice delivers the offer:
   "Hi, this is Colorado Care Assist calling about an
    open shift. We have a 2 to 6 PM shift available today
    in Aurora. Press 1 to accept, Press 2 to decline,
    or Press 3 to speak with a coordinator."

3. First "1" press wins, others get:
   "Thank you, this shift has been filled. We appreciate
    your quick response and will keep you in mind for
    future opportunities!"
─────────────────────────────────────────────────────────────

Deferred Voice Calls:
─────────────────────────────────────────────────────────────
If caregiver is currently on shift (per WellSky schedule):
→ Wait until 10 minutes after shift ends
→ Then initiate voice call
→ Don't interrupt caregivers while with clients
─────────────────────────────────────────────────────────────

Voice Call Preview:
─────────────────────────────────────────────────────────────
Before mass outreach, coordinator can:
→ Preview call to their own phone
→ Verify script sounds correct
→ Then approve for full deployment
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Reach caregivers who ignore texts
- Massive parallel outreach (vs. one-by-one calling)
- Professional, consistent messaging
- Respect for on-duty caregivers

---

### Emoji & Informal Response Handling

**The Problem:** Caregivers respond with thumbs up 👍, "k", "yep", or other informal responses. Systems that require exact "YES" miss these.

**The Solution:**

```
Flexible Response Interpretation:
─────────────────────────────────────────────────────────────
Positive (Accept):
- YES, yes, Yes, y, Y
- 👍, 👍🏻, 👍🏽, ✅, 🙋, 🙋‍♀️
- "yep", "yeah", "sure", "ok", "k", "I'll take it"
- "I can do it", "count me in", "I'm in"

Negative (Decline):
- NO, no, No, n, N
- 👎, ❌, 🙅, 🙅‍♀️
- "nope", "can't", "sorry", "pass"
- "I'm busy", "not available", "working"

Ambiguous (Need Clarification):
- "maybe", "let me check", "what time?"
- "how long?", "where?", "which client?"
- → AI asks clarifying question
- → Or routes to coordinator
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Higher response capture rate
- Natural communication style
- Reduced back-and-forth
- Better caregiver experience

---

### Follow-Up Messaging (Shift Filled Notifications)

**The Problem:** Caregivers respond to shift offers, but never hear back. Did they get it? Was it filled? Frustrating experience.

**The Solution:**

```
When Shift Filled:
─────────────────────────────────────────────────────────────
To WINNER:
"You're confirmed for [Client]'s shift!
📅 Today 2-6pm
📍 [Address]
📝 Care notes available in your WellSky app

See you there! Reply with any questions."

To ALL OTHERS who responded:
"Thanks for your quick response! This shift has been filled,
but we really appreciate you. We'll keep you in mind for
the next one! 🙏"

To ALL OTHERS who didn't respond:
(No message - don't spam non-responders)
─────────────────────────────────────────────────────────────
```

**Business Value:**
- Professional communication
- Caregivers feel valued
- Builds goodwill for future requests
- Clear confirmation reduces confusion

---

## Paradigm VA Billing Integration

**Context:** Colorado Care Assist uses [Paradigm](https://www.careswitch.com/blog/paradigm-partnership) for VA Community Care billing, authorization management, and collections.

### Current Pain Point

VA billing data exists in Paradigm, operational data exists in WellSky, and sales/referral tracking exists in the Portal. No unified view of VA client performance.

### Integration Opportunities

#### WellSky → Paradigm Sync

```
When VA client starts service in WellSky:
─────────────────────────────────────────────────────────────
1. New VA client created in WellSky (payer = VA)
2. Trigger sync to Paradigm for enrollment/auth setup
3. Authorization details flow back to WellSky
4. Billing-ready status confirmed
─────────────────────────────────────────────────────────────
```

#### Paradigm → Portal Analytics

```
VA Revenue Tracking Dashboard:
─────────────────────────────────────────────────────────────
| VA Metric               | Source      | Value     |
|-------------------------|-------------|-----------|
| Active VA Clients       | WellSky     | 18        |
| Hours Authorized/Week   | Paradigm    | 320       |
| Hours Delivered/Week    | WellSky     | 285       |
| Utilization Rate        | Calculated  | 89%       |
| Revenue MTD             | Paradigm    | $24,500   |
| Outstanding Claims      | Paradigm    | $8,200    |
| Avg Days to Payment     | Paradigm    | 28 days   |
─────────────────────────────────────────────────────────────
```

#### Referral Source ROI for VA

Connect VFW posts, VA social workers, and other veteran referral sources tracked in Sales Dashboard to actual VA revenue in Paradigm:

```
VA Referral Source Performance:
─────────────────────────────────────────────────────────────
| Source              | Referrals | Clients | Revenue/Year |
|---------------------|-----------|---------|--------------|
| VA Social Worker    | 12        | 8       | $96,000      |
| VFW Post 1 (Denver) | 6         | 5       | $62,000      |
| VFW Post 2 (Aurora) | 4         | 3       | $38,000      |
| DAV Chapter         | 3         | 2       | $28,000      |
| Word of Mouth       | 8         | 4       | $44,000      |
─────────────────────────────────────────────────────────────
```

### Technical Approach

Paradigm may have API access or export capabilities. If direct API isn't available:
1. Scheduled data exports from Paradigm
2. Parse and import into Portal database
3. Join with WellSky client data for unified reporting

**Priority:** P2 (Phase 2 - after core WellSky integrations)

---

## Phase 1: Foundation (Critical/Must-Have)

**Timeline:** Weeks 1-6
**Development Effort:** 40-60 hours
**Business Impact:** Eliminates core duplicate data entry

### 1.1 Authentication & Connection Infrastructure

**What It Does:**
Establishes secure OAuth 2.0 connection to WellSky Connect API with token management, refresh handling, and error recovery.

**Technical Implementation:**

```python
# New file: /sales/wellsky_service.py
class WellSkyService:
    """
    WellSky Connect API integration service.
    Handles authentication, token refresh, and API calls.
    """

    BASE_URL = "https://api.clearcareonline.com/v1"

    def __init__(self):
        self.api_key = os.getenv('WELLSKY_API_KEY')
        self.api_secret = os.getenv('WELLSKY_API_SECRET')
        self.access_token = None
        self.token_expires_at = None

    def authenticate(self):
        """Get or refresh access token"""
        # Implementation details...

    def get_clients(self, status=None, modified_since=None):
        """Retrieve client list with optional filters"""
        # Implementation details...

    def create_client(self, client_data):
        """Create new client in WellSky"""
        # Implementation details...
```

**Data Model Changes:**

Add to `/portal/portal_models.py`:
```python
class WellSkySync(Base):
    """Track sync status between Portal and WellSky"""
    __tablename__ = "wellsky_sync"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)  # client, caregiver, schedule
    portal_id = Column(Integer, nullable=False)
    wellsky_id = Column(String(100), nullable=True)
    sync_status = Column(String(50), default="pending")  # pending, synced, error
    last_synced = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

**Environment Variables Required:**
```
WELLSKY_API_KEY=your_api_key
WELLSKY_API_SECRET=your_api_secret
WELLSKY_AGENCY_ID=your_agency_id
WELLSKY_ENVIRONMENT=production  # or sandbox
```

**Business Value:**
- Foundational infrastructure for all integrations
- Secure credential management
- Error handling and retry logic

**Priority:** P0 (Must complete first)

---

### 1.2 Deal-to-Client Sync (Sales CRM --> WellSky)

**What It Does:**
When a deal reaches "Closed/Won" stage in the Sales CRM, automatically creates the client profile in WellSky Personal Care.

**Current Process (Manual):**
1. Sales rep marks deal as Closed/Won in CRM
2. Sales rep emails operations with client details
3. Operations manually creates client in WellSky (15-20 fields)
4. Operations emails back with confirmation
5. Sales rep updates CRM with WellSky client ID

**New Process (Automated):**
1. Sales rep marks deal as Closed/Won in CRM
2. System automatically creates client in WellSky
3. WellSky client ID synced back to CRM deal
4. Operations receives notification with client ready for scheduling

**Data Mapping:**

| CRM Deal Field | WellSky Client Field | Notes |
|----------------|---------------------|-------|
| `name` | `firstName`, `lastName` | Split on space |
| `contact_name` | `primaryContact.name` | POA/family contact |
| `email` | `email` | Primary email |
| `phone` | `phone` | Primary phone |
| `address` | `address.street`, `city`, `state`, `zip` | Parse full address |
| `referral_source_id` | `referralSource` | Lookup referral source |
| `payor_source` | `paymentType` | Map to WellSky payer types |
| `expected_revenue` | `authorizedHoursPerWeek` | Calculate from revenue |
| `notes` | `notes` | Include deal notes |

**Trigger Points:**
- Deal stage changes to "Closed/Won"
- Manual "Sync to WellSky" button on deal page

**Error Handling:**
- Validation errors displayed to user
- Retry queue for API failures
- Email notification on persistent failures

**Business Value:**
- **Time Saved:** 20-30 minutes per client onboarding
- **Error Reduction:** Eliminates typos from manual re-entry
- **Speed:** Clients ready for scheduling within minutes of close

**Priority:** P0

---

### 1.3 Hired Caregiver Sync (Recruiting --> WellSky)

**What It Does:**
When a recruiting lead is marked as "Hired" in the Recruiter Dashboard, automatically creates the caregiver profile in WellSky Personal Care.

**Current Process (Manual):**
1. Recruiter marks candidate as "Hired"
2. Recruiter emails HR/Operations with candidate info
3. HR manually creates caregiver in WellSky (25+ fields)
4. HR enters certifications, availability, skills
5. HR emails back with confirmation
6. Caregiver can now be scheduled

**New Process (Automated):**
1. Recruiter marks candidate as "Hired" and confirms key details
2. System creates caregiver profile in WellSky
3. Basic availability and skills pre-populated
4. HR reviews and enhances profile (certifications, documents)
5. Caregiver ready for scheduling faster

**Data Mapping:**

| Recruiting Lead Field | WellSky Caregiver Field | Notes |
|----------------------|------------------------|-------|
| `name` | `firstName`, `lastName` | Split on space |
| `email` | `email` | Primary email |
| `phone` | `phone` | Primary phone |
| `notes` | `notes` | Include interview notes |
| (new) `availability` | `availability` | Capture during hire process |
| (new) `skills` | `skills` | Capture certifications |
| (new) `preferred_location` | `serviceArea` | Geographic preferences |

**New Recruiting Dashboard Fields:**
Add "Hire Confirmation" form with additional fields needed for WellSky:
- Availability (days/times)
- Transportation (car/bus/walk)
- Preferred service areas
- Certifications held
- Emergency contact

**Business Value:**
- **Time Saved:** 45-60 minutes per caregiver onboarding
- **Faster to Schedule:** New hires available for shifts sooner
- **Better Data:** Structured capture of availability/skills

**Priority:** P0

---

### 1.4 Client Status Sync (WellSky --> Sales CRM)

**What It Does:**
Keeps the Sales CRM deal status synchronized with the actual client status in WellSky operations.

**Sync Scenarios:**

| WellSky Status Change | CRM Action | Notification |
|----------------------|------------|--------------|
| Client becomes Active | Update deal to "Active Client" | Email to sales rep |
| Client goes On-Hold | Update deal, flag for follow-up | Alert to assigned rep |
| Client Discharged | Move deal to "Churned", log reason | Win-back campaign trigger |
| Client Reactivated | Update deal to "Active" | Notification to sales |

**Technical Implementation:**
- Scheduled sync job every 15 minutes
- Webhook listener for real-time updates (if WellSky supports)
- Delta sync to minimize API calls

**New CRM Fields:**
```python
# Add to Deal model
wellsky_client_id = Column(String(100), nullable=True, index=True)
wellsky_status = Column(String(50), nullable=True)  # active, on_hold, discharged
wellsky_last_sync = Column(DateTime, nullable=True)
discharge_reason = Column(String(255), nullable=True)
discharge_date = Column(Date, nullable=True)
```

**Business Value:**
- **Real-time visibility:** Sales knows when clients churn
- **Proactive retention:** On-hold alerts enable intervention
- **Accurate reporting:** Pipeline reflects actual client status
- **Win-back opportunities:** Discharged clients trigger re-engagement

**Priority:** P1

---

## Phase 2: Operational Intelligence (High Value)

**Timeline:** Weeks 7-14
**Development Effort:** 80-120 hours
**Business Impact:** Real-time visibility, automated workflows

### 2.1 Capacity & Scheduling Visibility

**What It Does:**
Provides real-time visibility into caregiver capacity and scheduling status to inform sales pipeline management and recruiting priorities.

**Dashboard Widgets:**

**Sales Dashboard - Capacity Indicator:**
```
+------------------------------------------+
|  Current Operational Capacity            |
|  ----------------------------------------|
|  Active Caregivers: 45                   |
|  Available Hours/Week: 1,200             |
|  Scheduled Hours/Week: 980 (82%)         |
|  Open Capacity: 220 hours                |
|  ----------------------------------------|
|  Can Accept New Clients: YES             |
|  Estimated New Client Slots: 4-6         |
+------------------------------------------+
```

**Recruiting Dashboard - Demand Indicator:**
```
+------------------------------------------+
|  Staffing Demand Analysis                |
|  ----------------------------------------|
|  Pending Client Deals: 8                 |
|  Estimated Hours Needed: 160/week        |
|  Current Open Capacity: 220 hours        |
|  ----------------------------------------|
|  Urgency Level: MODERATE                 |
|  Hiring Priority: 2-3 caregivers         |
|  Focus Areas: Denver South, Aurora       |
+------------------------------------------+
```

**Data Points from WellSky:**
- Total active caregivers
- Aggregate scheduled hours by week
- Aggregate available hours by week
- Open shifts needing coverage
- Geographic distribution of clients/caregivers

**Business Value:**
- **Informed Sales:** Know when to accelerate or slow pipeline
- **Proactive Recruiting:** Hire ahead of demand
- **Resource Planning:** Balance capacity with growth
- **Geographic Strategy:** Identify underserved areas

**Priority:** P1

---

### 2.2 Referral Source Performance Tracking

**What It Does:**
Connects referral source data from CRM to actual client outcomes in WellSky, enabling ROI analysis by referral partner.

**Metrics Tracked:**

| Metric | Source | Calculation |
|--------|--------|-------------|
| Leads by Source | CRM | Count of deals by referral_source_id |
| Conversion Rate | CRM | Closed/Won deals / Total deals |
| Revenue per Source | WellSky | Sum of billings by referral source |
| Client Tenure | WellSky | Average months from start to discharge |
| Hours Delivered | WellSky | Total hours billed by referral source |
| Retention Rate | WellSky | Active clients / Total clients from source |

**Dashboard View:**

```
+----------------------------------------------------------------+
|  Referral Source Performance (Last 12 Months)                   |
+----------------------------------------------------------------+
| Source              | Leads | Conv% | Revenue  | Tenure | ROI  |
|---------------------|-------|-------|----------|--------|------|
| Good Sam Hospital   |    24 | 42%   | $128,000 | 8.2 mo | 4.2x |
| Visiting Nurse Svc  |    18 | 56%   | $96,000  | 12.1mo | 5.8x |
| Dr. Martinez Office |    12 | 33%   | $42,000  | 6.4 mo | 2.1x |
| Website (Organic)   |    45 | 18%   | $38,000  | 4.2 mo | 1.2x |
| VFW Posts           |     8 | 62%   | $52,000  | 14.8mo | 6.2x |
+----------------------------------------------------------------+
```

**Marketing Applications:**
- Identify highest-value referral relationships
- Quantify ROI of healthcare partner development
- Guide territory planning and visit priorities
- Support bonus/commission calculations for sales

**Business Value:**
- **Attribution:** Know true value of each referral source
- **Focus:** Invest time in highest-ROI relationships
- **Accountability:** Data-driven sales performance tracking

**Priority:** P1

---

### 2.3 Client Lifecycle Automation

**What It Does:**
Triggers automated workflows based on client lifecycle events in WellSky.

**Workflow Triggers:**

**New Client Started:**
```
Trigger: Client status changes to "Active" in WellSky
Actions:
  1. Send welcome email to client/family (via Brevo)
  2. Create satisfaction survey task (30 days)
  3. Create quality visit task (60 days)
  4. Log activity in CRM
  5. Update referral source statistics
```

**Client On-Hold:**
```
Trigger: Client status changes to "On Hold" in WellSky
Actions:
  1. Alert assigned sales rep
  2. Create follow-up task (7 days)
  3. Flag in CRM for retention outreach
  4. Pause any marketing communications
```

**Client Discharged:**
```
Trigger: Client status changes to "Discharged" in WellSky
Actions:
  1. Log discharge reason from WellSky
  2. Send satisfaction survey (if appropriate)
  3. Add to win-back campaign (90-day delay)
  4. Update referral source statistics
  5. Calculate final LTV for reporting
```

**Client Anniversary:**
```
Trigger: Client reaches 6-month or 1-year milestone
Actions:
  1. Send appreciation card/gift (automated via service)
  2. Request testimonial/review
  3. Log milestone in CRM
  4. Trigger referral request email
```

**Technical Implementation:**
- Event listener for WellSky status changes
- Workflow engine with configurable actions
- Integration with Brevo for email automation
- Task creation in CRM

**Business Value:**
- **Consistency:** Every client gets proper lifecycle attention
- **Retention:** Proactive intervention on at-risk clients
- **Testimonials:** Automated collection at optimal moments
- **Referrals:** Systematic ask at satisfaction peaks

**Priority:** P2

---

### 2.4 Hours & Revenue Dashboard

**What It Does:**
Provides real-time visibility into operational metrics that matter for business decisions.

**Executive Dashboard Widgets:**

```
+------------------------------------------+
|  Weekly Snapshot (Jan 6-12, 2026)        |
|  ----------------------------------------|
|  Hours Delivered:     1,247              |
|  vs. Last Week:       +8.2%              |
|  vs. Same Week LY:    +34.1%             |
|  ----------------------------------------|
|  Revenue (Projected): $48,633            |
|  Billed:              $42,180            |
|  Outstanding:         $6,453             |
|  ----------------------------------------|
|  Active Clients:      52                 |
|  New This Week:       2                  |
|  Churned This Week:   1                  |
|  ----------------------------------------|
|  Active Caregivers:   45                 |
|  Utilization Rate:    76%                |
+------------------------------------------+
```

**Trend Charts:**
- Hours delivered (weekly, 52-week trend)
- Revenue (monthly, YoY comparison)
- Client count (monthly)
- Average hours per client

**Data from WellSky:**
- Actual hours from EVV/timekeeping
- Billing/invoice data
- Client count by status
- Caregiver hours worked

**Business Value:**
- **Executive Visibility:** Real-time business health
- **Trend Analysis:** Spot growth or decline early
- **Forecasting:** Project revenue based on scheduled hours
- **Marketing ROI:** Correlate marketing spend with growth

**Priority:** P2

---

## Phase 3: Advanced Automation (Competitive Advantage)

**Timeline:** Weeks 15-24
**Development Effort:** 100-150 hours
**Business Impact:** AI-powered insights, predictive analytics

### 3.1 Predictive Lead Scoring Enhancement

**What It Does:**
Enhances CRM lead scoring with operational data from WellSky to predict deal quality.

**Current Lead Scoring (CRM-only):**
- Referral source quality
- Contact engagement
- Budget indicators
- Timeline urgency

**Enhanced Lead Scoring (with WellSky data):**
- **Similar Client Analysis:** Compare new lead to successful past clients
  - Similar payor source performance
  - Similar hours/service level outcomes
  - Similar geographic success rates
- **Caregiver Match Confidence:** Do we have caregivers available in their area?
- **Capacity Alignment:** Current capacity vs. requested hours
- **Seasonal Patterns:** Historical demand for their service type

**Model Inputs from WellSky:**
```python
def calculate_enhanced_lead_score(lead, wellsky_service):
    base_score = lead.current_score  # 0-100

    # Similar client success rate
    similar_clients = wellsky_service.get_similar_clients(
        payor_source=lead.payor_source,
        hours_estimate=lead.estimated_hours,
        location=lead.city
    )
    success_rate = calculate_retention_rate(similar_clients)

    # Caregiver availability
    available_caregivers = wellsky_service.get_caregivers_by_area(lead.city)
    availability_score = min(len(available_caregivers) * 10, 30)

    # Capacity alignment
    capacity_pct = wellsky_service.get_current_capacity_percent()
    capacity_score = 20 if capacity_pct < 80 else 10 if capacity_pct < 90 else 0

    return base_score * 0.5 + success_rate * 0.3 + availability_score + capacity_score
```

**Business Value:**
- **Better Prioritization:** Focus on leads most likely to succeed
- **Realistic Forecasting:** Account for operational constraints
- **Resource Alignment:** Sell where we can deliver

**Priority:** P2

---

### 3.2 Automated Marketing Content Personalization

**What It Does:**
Uses WellSky operational data to personalize marketing communications with real, current statistics.

**Dynamic Content Examples:**

**Email Template Variables:**
```html
<!-- Pulled from WellSky in real-time -->
<p>Colorado Care Assist currently serves <strong>{{active_client_count}}</strong>
families across the Front Range, delivering over <strong>{{weekly_hours}}</strong>
hours of care each week.</p>

<p>Our team of <strong>{{active_caregiver_count}}</strong> professional caregivers
maintains a <strong>{{avg_tenure_months}}</strong>-month average tenure -
well above the industry standard.</p>
```

**Website Dynamic Stats:**
```javascript
// Stats widget on homepage
{
  clients_served_total: 187,      // Lifetime from WellSky
  hours_delivered_total: 245000,  // Lifetime hours
  years_experience: 8,            // Company age
  avg_caregiver_tenure: 2.3,      // From WellSky
  satisfaction_rate: 4.8          // From surveys
}
```

**Social Media Automation:**
```
Weekly Stats Post (Auto-generated):
"This week, our amazing team of caregivers delivered 1,247 hours of
compassionate care to families across Colorado. Thank you to our
dedicated team! #HomeCareThatCares #ColoradoCareAssist"
```

**Business Value:**
- **Authenticity:** Real numbers, not marketing fluff
- **Freshness:** Stats always current
- **Efficiency:** No manual stat updates
- **Trust Building:** Transparency with prospects

**Priority:** P3

---

### 3.3 Caregiver Performance Marketing Insights

**What It Does:**
Connects recruiting effectiveness to operational outcomes, creating a feedback loop for recruiting optimization.

**Metrics Tracked:**

| Recruiting Source | Hires | 90-Day Retention | Avg Performance | Client Rating |
|-------------------|-------|------------------|-----------------|---------------|
| Indeed | 24 | 58% | 3.8/5.0 | 4.2/5.0 |
| Facebook Ads | 18 | 72% | 4.1/5.0 | 4.5/5.0 |
| Referral Bonus | 12 | 89% | 4.4/5.0 | 4.7/5.0 |
| ZipRecruiter | 8 | 45% | 3.4/5.0 | 3.9/5.0 |

**Insights Generated:**
- Which recruiting sources produce best-performing caregivers
- Correlation between hire attributes and client satisfaction
- Optimal caregiver profile for different service types
- Geographic performance patterns

**Marketing Applications:**
- Reallocate recruiting budget to highest-performing sources
- Refine job descriptions based on successful hire profiles
- Target recruiting ads to demographics of best performers
- Calculate true cost-per-quality-hire by source

**Business Value:**
- **Recruiting ROI:** Spend where we get best caregivers
- **Quality Focus:** Hire for client satisfaction, not just fill seats
- **Retention:** Identify what makes caregivers stay

**Priority:** P3

---

### 3.4 Predictive Churn Prevention

**What It Does:**
Uses WellSky operational data to predict clients at risk of churning before they leave.

**Risk Indicators from WellSky:**
- Declining hours scheduled
- Increased caregiver changes
- Missed visits or late arrivals
- Decreasing family portal engagement
- Payment delays
- Care plan not updated recently

**Risk Scoring Model:**
```python
def calculate_churn_risk(client, wellsky_data):
    risk_factors = {
        'declining_hours': detect_declining_hours(wellsky_data),      # 0-25
        'caregiver_turnover': count_recent_changes(wellsky_data),      # 0-20
        'missed_visits': count_missed_visits(wellsky_data, days=30),   # 0-20
        'portal_inactive': days_since_portal_login(wellsky_data),      # 0-15
        'payment_issues': has_overdue_invoices(wellsky_data),          # 0-10
        'stale_care_plan': days_since_care_plan_update(wellsky_data),  # 0-10
    }

    risk_score = sum(risk_factors.values())  # 0-100

    if risk_score >= 60:
        trigger_retention_alert(client, risk_factors)

    return risk_score
```

**Automated Interventions:**
- High-risk clients flagged for care coordinator outreach
- Quality visit automatically scheduled
- Sales/relationship manager notified
- Satisfaction survey triggered

**Business Value:**
- **Retention:** Intervene before clients leave
- **Revenue Protection:** Each saved client = ~$42K annually
- **Proactive Service:** Demonstrate care before complaints

**Priority:** P3

---

## Technical Architecture

### System Integration Diagram

```
+------------------------------------------------------------------+
|                     COLORADO CARE ASSIST                          |
|                     UNIFIED DATA PLATFORM                         |
+------------------------------------------------------------------+
|                                                                    |
|  +----------------+     +------------------+     +--------------+  |
|  | SALES CRM      |     | RECRUITING       |     | MARKETING    |  |
|  | (FastAPI)      |     | (Flask)          |     | (Portal)     |  |
|  +-------+--------+     +--------+---------+     +------+-------+  |
|          |                       |                      |          |
|          +----------+------------+----------+-----------+          |
|                     |                       |                      |
|              +------v-------+        +------v-------+              |
|              | wellsky_     |        | wellsky_     |              |
|              | service.py   |        | webhooks.py  |              |
|              +------+-------+        +------+-------+              |
|                     |                       ^                      |
+---------------------|                       |----------------------+
                      |                       |
                      v                       |
              +-------+-------+       +-------+-------+
              | WellSky       |       | WellSky       |
              | Connect API   |<----->| Webhook       |
              | (REST)        |       | Events        |
              +---------------+       +---------------+
                      |
              +-------v-------+
              | WELLSKY       |
              | PERSONAL CARE |
              | (Operations)  |
              +---------------+
```

### Data Flow Patterns

**Pattern 1: Outbound Sync (Portal --> WellSky)**
```
1. User action in Portal (e.g., close deal)
2. Event triggers wellsky_service.create_client()
3. API call to WellSky with transformed data
4. WellSky returns new entity ID
5. Portal stores wellsky_id for reference
6. Sync status logged for audit
```

**Pattern 2: Inbound Sync (WellSky --> Portal)**
```
Option A: Polling (simpler)
1. Scheduled job runs every 15 minutes
2. Call wellsky_service.get_clients(modified_since=last_sync)
3. Process each changed record
4. Update corresponding Portal records
5. Log sync completion

Option B: Webhooks (real-time, if supported)
1. WellSky sends webhook on entity change
2. /api/wellsky/webhook endpoint receives event
3. Validate webhook signature
4. Process event based on type
5. Update corresponding Portal records
```

**Pattern 3: Bi-directional Sync**
```
1. Maintain sync_version on both sides
2. Compare versions before update
3. Use conflict resolution rules:
   - WellSky wins for operational fields (schedule, hours)
   - Portal wins for sales/marketing fields (notes, tags)
   - Latest timestamp wins for shared fields (contact info)
```

### Database Schema Additions

```sql
-- Core sync tracking table
CREATE TABLE wellsky_sync (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- client, caregiver, schedule
    portal_table VARCHAR(100) NOT NULL,
    portal_id INTEGER NOT NULL,
    wellsky_id VARCHAR(100),
    sync_status VARCHAR(50) DEFAULT 'pending',
    sync_direction VARCHAR(20),  -- outbound, inbound, bidirectional
    last_synced TIMESTAMP,
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(entity_type, portal_id)
);

-- Index for efficient lookups
CREATE INDEX idx_wellsky_sync_wellsky_id ON wellsky_sync(wellsky_id);
CREATE INDEX idx_wellsky_sync_status ON wellsky_sync(sync_status);
CREATE INDEX idx_wellsky_sync_entity ON wellsky_sync(entity_type, portal_table);

-- Sync log for auditing
CREATE TABLE wellsky_sync_log (
    id SERIAL PRIMARY KEY,
    sync_id INTEGER REFERENCES wellsky_sync(id),
    action VARCHAR(50) NOT NULL,  -- create, update, delete, error
    request_data JSONB,
    response_data JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoint Structure

```
/api/wellsky/
    GET    /status              # Connection status and sync health
    POST   /sync/clients        # Trigger client sync
    POST   /sync/caregivers     # Trigger caregiver sync
    GET    /clients             # List synced clients
    GET    /clients/{id}        # Get specific client with WellSky data
    POST   /clients             # Create client in WellSky
    GET    /caregivers          # List synced caregivers
    POST   /caregivers          # Create caregiver in WellSky
    GET    /capacity            # Get current capacity metrics
    GET    /hours               # Get hours/revenue data
    POST   /webhook             # Receive WellSky webhooks
```

### Security Considerations

1. **API Credentials:** Store in environment variables, never in code
2. **Token Refresh:** Implement automatic token refresh before expiry
3. **Webhook Validation:** Verify webhook signatures/source IPs
4. **Data Minimization:** Only sync fields that are needed
5. **Audit Logging:** Log all API calls for compliance
6. **Error Handling:** Never expose API errors to end users
7. **Rate Limiting:** Respect WellSky API limits, implement backoff

---

## Success Metrics

### Phase 1 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Client onboarding time | < 20 minutes | Time from deal close to WellSky active |
| Caregiver onboarding time | < 1 hour | Time from hire to WellSky profile |
| Sync reliability | > 99% | Successful syncs / Total attempts |
| Data accuracy | > 99% | Matching records after sync |
| Staff time saved | > 10 hours/week | Before/after time study |

### Phase 2 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dashboard load time | < 3 seconds | Time to display WellSky data |
| Data freshness | < 15 minutes | Time from WellSky change to Portal update |
| Capacity visibility accuracy | > 95% | Compare to manual check |
| Referral source ROI calculated | 100% of sources | Sources with complete attribution |
| Lifecycle automation rate | > 90% | Automated workflows vs. manual |

### Phase 3 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Lead score accuracy | > 80% | Predicted vs. actual outcomes |
| Churn prediction accuracy | > 70% | Predicted at-risk vs. actual churn |
| Content personalization | 100% | Dynamic stats updated daily |
| Recruiting source ROI visibility | Complete | All sources tracked to outcomes |

### Business Outcome Metrics

| Outcome | Baseline | 6-Month Target | 12-Month Target |
|---------|----------|----------------|-----------------|
| New client onboarding/month | 4-6 | 6-8 | 8-12 |
| Client retention rate | ~78% | 82% | 85% |
| Sales rep productivity | 3 closes/month | 4 closes/month | 5 closes/month |
| Time-to-schedule new hire | 5-7 days | 2-3 days | 1-2 days |
| Data entry errors | Weekly | Monthly | Rare |

---

## Implementation Timeline

### Phase 1: Foundation (6 weeks)

| Week | Milestone | Deliverables |
|------|-----------|--------------|
| 1 | API Setup | Authentication working, basic API calls |
| 2 | Data Models | Sync tables created, entity mapping defined |
| 3 | Client Sync (Outbound) | Deal-to-client sync working |
| 4 | Caregiver Sync (Outbound) | Hire-to-caregiver sync working |
| 5 | Status Sync (Inbound) | Client status syncing to CRM |
| 6 | Testing & Deployment | Production deployment, monitoring |

### Phase 2: Operational Intelligence (8 weeks)

| Week | Milestone | Deliverables |
|------|-----------|--------------|
| 7-8 | Capacity Dashboard | Real-time capacity metrics |
| 9-10 | Referral Source Tracking | Full attribution pipeline |
| 11-12 | Lifecycle Automation | Event-triggered workflows |
| 13-14 | Hours/Revenue Dashboard | Executive visibility metrics |

### Phase 3: Advanced Automation (10 weeks)

| Week | Milestone | Deliverables |
|------|-----------|--------------|
| 15-17 | Enhanced Lead Scoring | Predictive model integration |
| 18-20 | Content Personalization | Dynamic marketing content |
| 21-22 | Recruiting Analytics | Source-to-outcome tracking |
| 23-24 | Churn Prevention | Predictive alerting system |

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting | Medium | Medium | Implement caching, batch operations |
| API downtime | Low | High | Graceful degradation, retry queues |
| Data format changes | Medium | Medium | Version API calls, monitor for changes |
| Webhook delivery issues | Medium | Low | Fallback to polling for critical data |
| Authentication token issues | Low | High | Robust token refresh, alerting |

### Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| WellSky API access delayed | Low | High | Begin onboarding process early |
| Staff resistance to new workflows | Medium | Medium | Training, change management |
| Over-automation causing errors | Low | High | Gradual rollout, human review points |
| Compliance concerns | Low | High | Legal review, data governance |

### Mitigation Strategies

1. **Start Simple:** Phase 1 uses proven patterns (CRUD sync)
2. **Fallback Modes:** Manual entry still possible if sync fails
3. **Monitoring:** Alerts for sync failures, data discrepancies
4. **Rollback:** All changes reversible, no destructive operations
5. **Incremental Rollout:** Test with subset before full deployment

---

## Appendix A: WellSky Connect API Reference

Based on available documentation, the Connect API provides:

### API Capabilities

**Read Access:**
- Client profiles and contact information
- Caregiver profiles and certifications
- Schedule and shift data
- Billing and invoice information
- Care plan documentation
- Referral source data
- Point-of-care documentation

**Write Access:**
- Create/update client profiles
- Create/update caregiver profiles
- Create/update schedules
- Update care documentation

### Authentication
- OAuth 2.0 with API key/secret
- Access tokens with refresh capability
- Agency-level permissions

### Rate Limits
- Specific limits to be confirmed during onboarding
- Recommend implementing exponential backoff

### Documentation
- Official docs: [apidocs.clearcareonline.com](https://apidocs.clearcareonline.com/)
- Terms: [wellsky.com/clearcare-connect-api-terms](https://wellsky.com/clearcare-connect-api-terms/)

---

## Appendix B: Current Data Models Reference

### Sales CRM Models (Relevant for Integration)

```python
# /sales/models.py - Key models for WellSky sync

class Deal:
    id: int
    name: str              # Client name --> WellSky firstName + lastName
    company_id: int        # Referral source --> WellSky referralSource
    stage: str             # Pipeline stage --> Trigger sync on "closed/won"
    expected_revenue: float
    # NEW FIELDS:
    wellsky_client_id: str
    wellsky_status: str
    wellsky_last_sync: datetime

class Lead:
    id: int
    name: str
    referral_source_id: int
    # Fields for WellSky client creation

class ReferralSource:
    id: int
    name: str              # --> WellSky referral source name
    organization: str
    source_type: str
```

### Recruiting Models (Relevant for Integration)

```python
# /recruiting/app.py - Key models for WellSky sync

class Lead:
    id: int
    name: str              # --> WellSky caregiver name
    email: str
    phone: str
    status: str            # "hired" triggers sync
    # NEW FIELDS:
    wellsky_caregiver_id: str
    wellsky_sync_status: str
```

### Portal Models (Quality Tracking)

```python
# /portal/portal_models.py - Already have WellSky-ready fields

class ClientSurveyResponse:
    client_id: str         # WellSky client ID ready

class ClientComplaint:
    client_id: str         # WellSky client ID ready
    source: str            # Can be "wellsky"

class CarePlanStatus:
    client_id: str         # WellSky client ID ready
```

---

## Appendix C: Approval Requirements

All integration launches require stakeholder approval:

### Phase 1 Approval Required:
- [ ] Technical review of API implementation
- [ ] Data mapping review with operations
- [ ] Security review of credential management
- [ ] Testing sign-off from QA
- [ ] User training plan approved

### Phase 2 Approval Required:
- [ ] Dashboard design review
- [ ] Workflow automation review with operations
- [ ] Privacy review for data visibility
- [ ] User acceptance testing complete

### Phase 3 Approval Required:
- [ ] Predictive model accuracy validation
- [ ] Marketing content automation review
- [ ] Compliance review for automated communications

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 14, 2026 | Elite Marketing Director + Tech Team | Initial roadmap creation |

---

*This document is a strategic planning artifact for Colorado Care Assist technology integration. Implementation specifics may vary based on WellSky API access and technical discovery.*

*For questions: Contact the Tech Team or Elite Marketing Director*
