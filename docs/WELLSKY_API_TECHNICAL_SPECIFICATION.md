# WellSky Personal Care API - Technical Specification
**Colorado Care Assist**
**Document Version:** 1.0
**Last Updated:** January 29, 2026
**Contact:** Jason Shulman, jason@coloradocareassist.com

---

## Executive Summary

### Primary Strategic Goal: Replace Hybrid Human + AI Scheduling

Colorado Care Assist currently operates with a hybrid scheduling model:
1. **Gigi AI** ($1,000/month) - AI phone assistant for shift filling
2. **Offshore Scheduler** ($1,800/month, 40 hrs/week) - Human scheduler handling complex tasks

**Current Costs:** $2,800/month = $33,600/year

**Current Limitations:**
- Not 24/7/365 (offshore scheduler works limited hours)
- Scaling requires hiring Scheduler #2, #3, #4 (+$21,600/year each)
- Limited to business hours for phone/text responses

**The WellSky API is the key to building Gigi AI, which replaces both Gigi and enables 24/7/365 operations without additional human schedulers.**

**Why Build Gigi AI:**
1. **Massive Cost Savings** - Replace $33,600/year with ~$6,240/year (save $25K-27K/year)
2. **24/7/365 Availability** - Answer phones and texts at 3 AM on Christmas (human schedulers can't do this)
3. **Infinite Scaling** - Handle 50 clients or 500 clients with same cost (no need for Scheduler #2, #3, #4)
4. **Full Control** - Own the technology stack and customize for our exact workflows
5. **Deep Integration** - Connect to our CRM, recruiting, marketing automation, and portal
6. **Competitive Moat** - Build proprietary AI operational capabilities competitors can't match
7. **Data Ownership** - Keep all caregiver/client interaction data in our systems

**What We're Building (Gigi AI):**
Our in-house replacement for Gigi, integrated with:
- **WellSky API** - Real-time access to shifts, caregiver availability, client data
- **RingCentral** - Voice calls and SMS (same platform Gigi uses)
- **BeeTexting** - High-volume SMS campaigns for shift filling blasts
- **Our Portal** - Sales CRM, recruiting database, and operational dashboards

### Broader Integration Scope

Beyond AI scheduling, the WellSky API powers our unified operations portal across three core business systems:

**Integration Points:**
- **Sales CRM** ↔ WellSky Prospects & Clients
- **Recruiting Dashboard** ↔ WellSky Applicants & Caregivers
- **Gigi AI Voice Assistant** ← WellSky real-time data feeds (Gigi replacement)
- **Document Management (GoFormz)** → WellSky status conversions

**Business Impact:**
- **Replace $6K-24K/year AI scheduling SaaS** with in-house solution
- Automated prospect-to-client conversion workflow
- Real-time shift and availability management
- Predictive analytics for operational efficiency
- Reduced manual data entry across systems

---

## 1. System Architecture

### 1.1 Platform Overview

**Backend Framework:** FastAPI (Python 3.11+)
**Database:** PostgreSQL (separate databases for Sales and Recruiting)
**Authentication:** OAuth 2.0 with WellSky API credentials
**Deployment:** Mac Mini (Local) (production) with unified portal architecture

### 1.2 Application Structure

```
Colorado Care Assist Unified Portal
├── Main Website (coloradocareassist.mac-miniapp.com)
├── Unified Operations Portal (careassist-unified.mac-miniapp.com)
│   ├── Sales CRM Dashboard
│   ├── Recruiting Dashboard
│   └── Hub/Dashboard Selector
└── Gigi AI Voice Assistant (gigi-careassist.mac-miniapp.com)
```

### 1.3 WellSky Service Layer

**Core Module:** `services/wellsky_service.py` (2,800+ lines)
**Primary Class:** `WellSkyService`

**Configuration:**
```python
Environment Variables Required:
- WELLSKY_API_KEY
- WELLSKY_API_SECRET
- WELLSKY_AGENCY_ID
- WELLSKY_ENVIRONMENT (sandbox | production)

Base URLs:
- Sandbox: https://api-sandbox.clearcareonline.com/v1
- Production: https://api.clearcareonline.com/v1
```

---

## 2. API Endpoints & Data Models

### 2.1 Client Management

**Endpoints Used:**
- `GET /clients` - List clients with filters (status, date range)
- `POST /clients` - Create new client from prospect conversion
- `GET /clients/{id}` - Retrieve client profile details
- `PUT /clients/{id}` - Update client information
- `GET /clients/status-changes` - Track client lifecycle events

**Data Model: WellSkyClient**
```python
@dataclass
class WellSkyClient:
    id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: str
    address: Address
    status: ClientStatus  # prospect, pending, active, on_hold, discharged
    emergency_contacts: List[EmergencyContact]
    payer_source: str  # Medicaid, VA, Private Pay
    authorized_hours_per_week: int
    start_date: Optional[date]
    discharge_date: Optional[date]
    referral_source: Optional[str]
    care_coordinator: Optional[str]
```

**Key Use Cases:**
1. **Sales Pipeline Sync** - Closed deals create or update WellSky prospects
2. **Status Monitoring** - Track active → on-hold → discharged transitions for retention
3. **Referral Analytics** - Measure ROI by referral source
4. **Care Coordination** - Assign coordinator in CRM, sync to WellSky

---

### 2.2 Caregiver Management

**Endpoints Used:**
- `GET /caregivers` - List caregivers with availability filters
- `POST /caregivers` - Create caregiver from applicant conversion
- `GET /caregivers/{id}` - Retrieve caregiver profile
- `PUT /caregivers/{id}/availability` - Update availability windows

**Data Model: WellSkyCaregiver**
```python
@dataclass
class WellSkyCaregiver:
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    status: CaregiverStatus  # applicant, pending, active, inactive, terminated
    certifications: List[str]  # CNA, HHA, PCA, etc.
    availability: List[AvailabilityWindow]
    service_area: str  # ZIP codes or regions
    performance_rating: Optional[float]
    hire_date: Optional[date]
    background_check_status: str
    skills: List[str]
```

**Key Use Cases:**
1. **Recruiting Pipeline** - Hired applicants become WellSky caregivers
2. **Shift Matching** - Pull available caregivers for open shift alerts
3. **Performance Tracking** - Sync ratings from WellSky back to recruiting analytics
4. **Compliance** - Track certifications and background check expiration

---

### 2.3 Shift & Schedule Management

**Endpoints Used:**
- `GET /shifts` - List shifts by date range, client, or caregiver
- `GET /shifts/open` - Find unfilled shifts requiring coverage
- `POST /shifts/{id}/assignments` - Assign caregiver to open shift
- `GET /shifts/{id}/evv` - Retrieve EVV clock-in/out data

**Data Model: WellSkyShift**
```python
@dataclass
class WellSkyShift:
    id: str
    client_id: str
    caregiver_id: Optional[str]
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime]  # EVV clock-in
    actual_end: Optional[datetime]    # EVV clock-out
    status: ShiftStatus  # scheduled, in_progress, completed, missed, cancelled, open
    visit_type: str  # Personal Care, Homemaker, Companionship
    billable_hours: Optional[float]
```

**Key Use Cases:**
1. **Gigi AI Integration** - Voice assistant pulls shift data for call-off handling
2. **Open Shift Alerts** - Automated SMS blast to available caregivers
3. **EVV Compliance** - Monitor clock-in/out for Medicaid/VA billing
4. **Revenue Dashboard** - Calculate billable hours by payer source

---

### 2.4 Prospect & Applicant Pipelines

**Prospect Endpoints:**
- `GET /prospects` - List sales prospects
- `POST /prospects` - Create prospect from CRM deal
- `PUT /prospects/{id}` - Update prospect status
- `POST /prospects/{id}/convert-to-client` - Convert to active client

**Applicant Endpoints:**
- `GET /applicants` - List recruiting applicants
- `POST /applicants` - Create applicant from recruiting lead
- `PUT /applicants/{id}` - Update applicant status
- `POST /applicants/{id}/convert-to-caregiver` - Convert to active caregiver

**Status Enums:**
```python
ProspectStatus:
    new, contacted, assessment_scheduled, assessment_completed,
    proposal_sent, negotiating, won, lost, on_hold

ApplicantStatus:
    new, screening, phone_interview, in_person_interview,
    background_check, offer_extended, hired, rejected, withdrawn
```

**Key Workflow:**
```
SALES PIPELINE:
Deal Created → Prospect in WellSky → Assessment → Proposal → Deal Closed →
Paperwork Signed (GoFormz) → Convert to Client → Operational

RECRUITING PIPELINE:
Lead Created → Applicant in WellSky → Interviews → Background Check →
Hired → Paperwork Signed (GoFormz) → Convert to Caregiver → Shift-Ready
```

---

## 3. Integration Points

### 3.1 Sales CRM ↔ WellSky Sync

**Sync Service:** `services/sales_wellsky_sync.py`

**Outbound (Sales → WellSky):**
| Trigger | WellSky Action | Data Synced |
|---------|---------------|-------------|
| Deal created | Create Prospect | Name, contact info, address, referral source |
| Deal stage change | Update Prospect status | Pipeline stage → prospect status mapping |
| Deal closed-won | Update Prospect → "won" | Expected start date, authorized hours |
| Paperwork complete (GoFormz) | Convert Prospect → Client | Full client profile becomes operational |

**Inbound (WellSky → Sales):**
| WellSky Event | CRM Action | Business Logic |
|--------------|-----------|----------------|
| Client status → active | Update deal → "Active Client" | Trigger welcome automation |
| Client status → on-hold | Create task for retention team | Alert for churn risk |
| Client discharged | Update deal → "Discharged" | Log reason, trigger win-back campaign |
| New Family Room activity | Log note in CRM | Track family engagement |

**Field Mapping:**
```python
deal.name → prospect.first_name + last_name (split)
deal.phone → prospect.phone
deal.email → prospect.email
deal.address → prospect.address
deal.referral_source → prospect.referral_source
deal.expected_revenue → prospect.authorized_hours_per_week (calculated at rate)
deal.notes → prospect.notes
```

---

### 3.2 Recruiting Dashboard ↔ WellSky Sync

**Sync Service:** `services/recruiting_wellsky_sync.py`

**Outbound (Recruiting → WellSky):**
| Trigger | WellSky Action | Data Synced |
|---------|---------------|-------------|
| Lead created | Create Applicant | Name, contact info, source |
| Lead status change | Update Applicant status | Screening → interview → hired progression |
| Lead hired | Update Applicant → "hired" | Expected start date |
| Paperwork complete (GoFormz) | Convert Applicant → Caregiver | Certifications, availability, skills |

**Inbound (WellSky → Recruiting):**
| WellSky Event | Recruiting Action | Business Logic |
|--------------|------------------|----------------|
| Caregiver availability change | Update lead availability | Used for shift matching analytics |
| Caregiver performance rating | Log in recruiting notes | Measure recruiting source quality |
| Caregiver terminated | Update lead status | Analyze turnover by source |

**Field Mapping:**
```python
lead.name → applicant.first_name + last_name (split)
lead.email → applicant.email
lead.phone → applicant.phone
lead.source → applicant.recruiting_source
lead.certifications → applicant.certifications
lead.availability → applicant.availability (new fields added)
lead.skills → applicant.skills (new fields added)
```

---

### 3.3 Gigi AI Voice Assistant ↔ WellSky (Gigi Replacement)

**Strategic Context:** Gigi is our in-house AI voice assistant built to replace Gigi AI, which we currently use for automated scheduling and caregiver communications. By building Gigi with direct WellSky API access, we eliminate $6K-24K/year in SaaS fees while gaining full control over the AI logic and workflows.

**Integration Type:** Read-only data pull (no writes to WellSky)
**Platform:** Retell AI voice agent (same conversational AI platform Gigi uses)
**RingCentral Integration:** Voice calls and SMS (same phone platform Gigi uses)
**Sync Frequency:** Daily at 3:00 AM MT via `gigi/daily_sync.py`

**Data Pulled from WellSky:**
- **Caregivers:** Full roster with phone numbers, availability, status
- **Clients:** Active client list with primary caregiver assignments
- **Shifts:** Today's and tomorrow's schedule (upcoming 48 hours)
- **Open Shifts:** Unfilled shifts requiring coverage

**Core Use Cases (Gigi Feature Parity):**
1. **Call-Off Management** - Caregiver calls Gigi to report absence, system pulls shift data and sends SMS blast to available replacements
2. **Shift Filling Automation** - When open shifts detected, Gigi initiates parallel outreach to qualified caregivers
3. **Client Complaints** - Client calls after hours, Gigi pulls client record and escalates to on-call manager
4. **Prospect Inquiries** - Potential clients call, Gigi provides service info and creates lead in sales CRM
5. **Natural Language Understanding** - Intent-driven conversations (not rigid phone trees)

**Critical Operations Integration:**
```bash
# When WellSky API key is added, MUST set:
mac-mini config:set GIGI_OPERATIONS_SMS_ENABLED=true

# Without this flag:
# ❌ No SMS to on-call manager for call-outs
# ❌ No notifications to Cynthia (ext 105) or Jason (ext 101) for cancel threats
# ❌ No caregiver replacement blast SMS
```

**Escalation Contacts:**
- **Cynthia Pointe** (RingCentral ext 105) - Client cancel threats, urgent complaints
- **Jason Shulman** (RingCentral ext 101) - Client cancel threats, urgent complaints

---

### 3.4 GoFormz Document Workflow → WellSky

**Sync Service:** `services/goformz_wellsky_sync.py`

**Critical Compliance Workflow:**
```
1. Prospect signs client packet in GoFormz (liability, HIPAA, service agreement)
2. GoFormz webhook → Portal detects completion
3. Portal calls WellSky: POST /prospects/{id}/convert-to-client
4. Client becomes operational in WellSky (eligible for scheduling & billing)

SAME FOR CAREGIVERS:
1. Applicant signs employment packet in GoFormz (W4, I9, direct deposit, background check consent)
2. GoFormz webhook → Portal detects completion
3. Portal calls WellSky: POST /applicants/{id}/convert-to-caregiver
4. Caregiver becomes shift-available in WellSky (eligible for assignments)
```

**Why This Matters:**
- Ensures no client starts service without signed compliance documentation
- Prevents caregivers from working before background checks and employment paperwork complete
- Audit trail for Medicaid/VA compliance reviews

---

## 4. Advanced Features & Automation (Roadmap)

### Competitive Landscape: AI Scheduling in Home Care

Colorado Care Assist is building Gigi AI to compete with established players in the AI scheduling space:

| Competitor | Focus | Pricing (Est.) | Key Features (Jan 2026) |
|-----------|-------|---------------|-------------------------|
| **Gigi** (current provider) | AI phone assistant for shift filling, natural conversations | $500-2000/mo | Intent-driven conversations, RingCentral integration, "more natural" conversation flow, contextual outreach timing |
| **Gigi** | Proactive scheduling automation, caregiver engagement | $1000-3000/mo | Multi-shift outreach, caregiver recommendations (distance, history, overtime), multi-language SMS/voice, defer calls for on-shift caregivers, preference memory, care coordinator workflows, two-way WellSky sync |
| **Alden Health** | AI care coordinator, shift optimization | $1500-2500/mo | Clinical decision support, Medicare documentation |
| **AxisCare** | All-in-one platform with AI features | Full platform replacement | Integrated scheduling + billing + EVV (requires leaving WellSky) |
| **Careswitch** | No-call no-show elimination | $800-1500/mo | 90%+ accuracy predicting no-shows, automated backup scheduling |

**Our Competitive Advantage:**
1. **No Monthly SaaS Fees** - Pay once to build, own forever
2. **Deep WellSky Integration** - Direct API access (competitors use webhooks or slower integrations)
3. **Full Customization** - Tailor AI logic to our exact workflows and client base
4. **Data Ownership** - All caregiver interactions, preferences, and performance data stays in our systems
5. **Cross-System Intelligence** - Gigi connects to Sales CRM, Recruiting, and Marketing for holistic insights (competitors are siloed in operations only)

---

### 4.1 Real-Time Open Shift Alerts (Priority P0 - Gigi Replacement Core Feature)

**Problem:** Open shifts typically take 2-4 hours to fill manually
**Solution:** Automated SMS blast using WellSky availability data

**Workflow:**
```
1. Shift becomes open (call-off, scheduling gap, new client start)
2. Portal pulls from WellSky: GET /caregivers?available=true&date={shift_date}
3. Filter caregivers by:
   - Geographic proximity to client
   - Required certifications (e.g., client needs CNA)
   - Availability window matches shift time
   - No conflicting shifts
4. Send parallel SMS to top 5-10 matches via RingCentral/BeeTexting
5. First to claim gets assigned
6. If no response in 15 minutes, escalate to care coordinator
```

**Expected Impact:** 90% reduction in time to fill open shifts

---

### 4.2 Gigi AI Feature Roadmap (Gigi-Inspired)

Based on analysis of Gigi's recent updates (Jan 2026), here are proven features we should build into Gigi:

#### Phase 1: Core Scheduling (Months 1-2)

**Multi-Shift Outreach**
- **Problem:** Sending 5 separate texts for 5 open shifts = message fatigue
- **Solution:** "Hi Maria! We have 3 open shifts this week in your area: Mon 2-6pm (Aurora), Wed 9am-1pm (Denver), Fri 10am-2pm (Lakewood). Reply with which ones work for you!"
- **WellSky API Calls:** `GET /shifts?status=open&caregiver_match={caregiver_id}`
- **Impact:** Fewer texts, faster fill rate, better caregiver experience

**Smart Caregiver Recommendations**
```python
def rank_caregivers_for_shift(shift, wellsky_service):
    """
    Gigi's proven ranking algorithm
    """
    caregivers = wellsky_service.get_caregivers(status="active")

    for cg in caregivers:
        score = 0

        # Distance from client (WellSky has service area)
        if cg.service_area == shift.client_zip_code:
            score += 50

        # Previous work history with this client
        past_shifts = wellsky_service.get_shifts(
            caregiver_id=cg.id,
            client_id=shift.client_id
        )
        score += len(past_shifts) * 10  # Familiarity bonus

        # Schedule conflicts
        if has_conflicting_shift(cg, shift):
            score = 0  # Hard exclude

        # Overtime check (Gigi surfaces this)
        if would_cause_overtime(cg, shift):
            score -= 20  # Penalty but not excluded

        # Gender matching (for client preferences)
        if shift.client_gender_preference == cg.gender:
            score += 15

        # Language matching
        if shift.client_language in cg.languages:
            score += 25

        cg.match_score = score

    return sorted(caregivers, key=lambda x: x.match_score, reverse=True)
```

**Two-Way Sync: Assign → WellSky**
- **Current:** Gigi finds caregiver → coordinator manually assigns in WellSky
- **Gigi Feature:** Gigi assigns directly in WellSky via API
- **API Call:** `POST /shifts/{shift_id}/assignments` with `caregiver_id`
- **Impact:** Eliminate manual step, instant confirmation

**Follow-Up Messaging**
```
To Selected Caregiver:
"Great news! You've got the shift on Monday 2-6pm with Mrs. Johnson
at 123 Main St, Aurora 80012. See you there! Reply with any questions."

To All Other Responders:
"Thanks for your quick response! This shift has been filled, but we
really appreciate you. We'll keep you in mind for the next one! 🙏"
```

---

#### Phase 2: Caregiver Experience (Months 3-4)

**Multi-Language Support**
- **WellSky Data:** Pull `caregiver.preferred_language` from API
- **Languages:** Spanish, Tagalog, Vietnamese, Haitian Creole, Mandarin, Russian
- **Dynamic Switching:** If caregiver responds in Spanish, Gigi switches to Spanish
- **Implementation:** Use Google Translate API + language detection

**Defer Voice Calls for On-Shift Caregivers**
```python
def should_call_now(caregiver, wellsky_service):
    """
    Gigi feature: Don't interrupt caregivers on shift
    """
    current_shifts = wellsky_service.get_shifts(
        caregiver_id=caregiver.id,
        status="in_progress",
        date=today
    )

    if current_shifts:
        # Defer voice call until 10 min after shift ends
        shift_end = current_shifts[0].scheduled_end
        defer_until = shift_end + timedelta(minutes=10)

        # Still send SMS immediately
        send_sms(caregiver, shift_offer)
        schedule_voice_call(caregiver, shift_offer, defer_until)
        return False

    return True  # OK to call now
```

**Caregiver Preference Memory**
- **Example:** "Can't work Thursday afternoons because of kid's dance class"
- **Storage:** Save in portal database with `caregiver_id`, `constraint_type`, `description`
- **Usage:** Exclude from Thursday afternoon shift recommendations automatically
- **WellSky Integration:** Store as caregiver notes? Or keep in portal only?

**Recurring Shift Confirmations**
```
Weekly Check-In (Every Monday for recurring shifts):
"Hi Carlos! Just confirming your regular schedule this week:
• Tue 9am-1pm - Mr. Smith
• Thu 2pm-6pm - Mrs. Lopez
• Sat 10am-2pm - Mr. Chen

Reply ALL GOOD if these work, or let me know if you need changes."
```

---

#### Phase 3: Operations & Intelligence (Months 5-6)

**Clock In/Out Reminders**
- **15 min before shift:** "Hi Maria! Reminder to clock in for your 2pm shift with Mrs. Johnson in 15 minutes. See you soon!"
- **5 min late clock-in:** "Maria, we noticed you haven't clocked in yet for your shift with Mrs. Johnson. Everything OK?"
- **WellSky API:** `GET /shifts/{id}/evv` to check actual_start vs scheduled_start

**Overtime Alerts**
- **Gigi Feature:** Surface WellSky overtime warnings before assignment
- **API Call:** `GET /caregivers/{id}/schedule` + calculate total hours
- **Alert:** "⚠️ Assigning this shift will put Maria into overtime (42 hours this week). Proceed?"

**Care Coordinator Routing**
```python
# WellSky syncs coordinator assignments
shift.care_coordinator = "Cynthia Pointe"

# Only notify relevant coordinator
if shift.care_coordinator == "Cynthia":
    send_sms("+17205551105", f"Open shift needs coverage: {shift.details}")
else:
    # Don't spam other coordinators
    pass
```

**Pause/Resume Outreaches**
- **Use Case:** Started SMS blast, want to delay voice calls
- **UI:** "Pause Outreach" button in portal dashboard
- **Backend:** Set `outreach.status = "paused"`, voice calls queued but not sent

**Off Hours Auto-Responses**
```
Caregiver texts at 11 PM: "Can't make my shift tomorrow"

Gigi Auto-Response (if after 8 PM):
"Thanks for letting us know. Our team will follow up first thing
in the morning to find coverage. If this is urgent, call our
on-call line at (720) 555-0199."
```

**Cancellation Workflow**
```
When coordinator cancels an outreach mid-flight:

1. Add internal note: "Client cancelled service"
2. Choose: Notify caregivers? YES / NO
3. If YES, select reason:
   - "Shift no longer needed"
   - "Client schedule changed"
   - "Coverage found internally"
4. Auto-send: "Thanks! This shift has been filled. Appreciate your response!"
```

---

#### Phase 4: Advanced Intelligence (Months 7-9)

**Predictive No-Show Prevention** (Careswitch/Gigi feature)
- Track caregiver reliability score
- Weather correlation (caregivers less reliable on snowy days?)
- Shift time correlation (more no-shows on early morning shifts?)
- Alert coordinator 24 hours before high-risk shifts

**Bundled Shift Offers**
```
Instead of 3 separate outreaches:
"Hi Maria! We have a package deal for you this week:
Mon 2-6pm + Wed 2-6pm + Fri 2-6pm (same client, Mrs. Johnson)
20 hours total, close to your home. Want the whole week?"
```

**Organizational Memory System**
- Which caregivers accept which clients
- Which caregivers prefer certain shift times
- Which caregivers respond fastest
- Build "Caregiver DNA" profiles for smarter matching

**Email Notifications for Coordinators**
- "Maria accepted the Mon 2pm shift"
- "Carlos declined the Wed shift - reason: doctor appointment"
- "Open shift: Thu 9am still unfilled after 30 minutes"

---

### 4.3 Predictive Churn Prevention

**Data Sources:**
- WellSky: Client status changes, Family Room engagement, shift completion rate
- Sales CRM: Client satisfaction surveys, payment history, complaint logs

**Early Warning Triggers:**
```python
if client.status == "on_hold" or \
   client.family_room_last_login > 30 days or \
   client.shift_completion_rate < 85% or \
   client.complaint_count > 2 (last 30 days):

    create_crm_task(
        title="Churn Risk: {client.name}",
        assigned_to=client.care_coordinator,
        priority="HIGH"
    )
    trigger_retention_workflow(client)
```

**Retention Workflow:**
- Automated check-in email from care coordinator
- Offer care plan adjustment
- Family satisfaction call
- Caregiver re-matching if personality mismatch

---

### 4.3 Referral Source ROI Analytics

**Data Flow:**
```
Sales CRM (deal.referral_source) → WellSky Prospect (referral_source) →
WellSky Client (referral_source preserved) → Revenue dashboard
```

**Metrics Tracked:**
| Referral Source | Leads | Conversions | Avg LTV | CAC | ROI |
|----------------|-------|-------------|---------|-----|-----|
| Google Ads | 45 | 12 | $48,000 | $450 | 10.7x |
| Physician Referral | 18 | 14 | $72,000 | $0 | ∞ |
| Facebook Ads | 67 | 8 | $36,000 | $320 | 9.0x |
| Word of Mouth | 23 | 19 | $54,000 | $0 | ∞ |

**Business Impact:**
- Identify highest-ROI referral channels
- Optimize marketing spend allocation
- Build physician referral program (highest conversion rate)

---

### 4.4 Caregiver Performance & Recruiting Analytics

**Data Loop:**
```
WellSky Caregiver Performance Metrics → Recruiting Dashboard →
Analyze by Recruiting Source → Optimize sourcing strategy
```

**Metrics by Recruiting Source:**
| Source | Hired | 90-Day Retention | Avg Performance Rating | Cost per Hire |
|--------|-------|------------------|----------------------|---------------|
| Indeed | 34 | 68% | 4.2/5 | $85 |
| Care.com | 12 | 83% | 4.6/5 | $120 |
| Employee Referral | 19 | 91% | 4.8/5 | $200 (bonus) |
| Facebook Jobs | 28 | 54% | 3.9/5 | $45 |

**Optimization Actions:**
- Increase spend on Care.com (higher retention, performance)
- Expand employee referral bonus program (best retention)
- Reduce Facebook Jobs sourcing (high turnover)

---

## 5. Security & Compliance

### 5.1 Authentication & Authorization

**Method:** OAuth 2.0 with API Key/Secret
**Credential Storage:** 1Password Business vault → "WellSky Personal Care API"
**Test Environment:** Credentials in `/root/clawd/credentials/wellsky.json` (gitignored)

**Production Security:**
```bash
# Environment variables set in Mac Mini (Local)
mac-mini config:set WELLSKY_API_KEY="***" --app careassist-unified
mac-mini config:set WELLSKY_API_SECRET="***" --app careassist-unified
mac-mini config:set WELLSKY_AGENCY_ID="***" --app careassist-unified
mac-mini config:set WELLSKY_ENVIRONMENT="production" --app careassist-unified
```

### 5.2 Data Privacy & HIPAA Compliance

**PHI Handling:**
- Client names, addresses, phone numbers, health conditions are Protected Health Information (PHI)
- WellSky is HIPAA-compliant and HITRUST CSF certified
- Colorado Care Assist has Business Associate Agreement (BAA) with WellSky

**Data Minimization:**
- Portal only pulls necessary fields from WellSky
- No storage of sensitive health conditions in CRM (stored only in WellSky)
- Gigi AI never records or stores health information (only operational data: names, shifts, phone numbers)

**Access Controls:**
- Sales team: Access to prospects, clients (no access to caregiver SSN, background checks)
- Recruiting team: Access to applicants, caregivers (no access to client health data)
- Care coordinators (in WellSky): Full access to all client/caregiver data

---

### 5.3 EVV Compliance (Medicaid/VA)

**Requirement:** 21st Century CURES Act mandates Electronic Visit Verification for Medicaid/VA-funded personal care

**WellSky EVV Features Used:**
- GPS-verified clock-in/clock-out via mobile app
- Biometric authentication (prevent buddy punching)
- Real-time sync to state Medicaid portals
- Automated audit reports

**Portal Integration:**
```python
# Monitor EVV compliance in real-time
shifts = wellsky.get_shifts(
    date_range=(today, today),
    status="completed"
)

for shift in shifts:
    if shift.payer_source in ["Medicaid", "VA"]:
        evv_data = wellsky.get_shift_evv(shift.id)
        if not evv_data.gps_verified:
            alert_coordinator(shift.caregiver, "EVV GPS failed")
```

---

## 6. API Rate Limits & Performance

### 6.1 Rate Limit Strategy

**WellSky API Pricing & Limits:**
- **Colorado Care Assist Deal:** $220/month
- **Rate Limits:** No hard rate limits (WellSky trusts us not to abuse the API)
- **Good Citizenship:** We should still optimize to avoid unnecessary API calls

**Portal Optimization:**
```python
# Batch requests when possible
clients = wellsky.get_clients(
    status="active",
    updated_since=yesterday  # Only pull changed records
)

# Use webhooks instead of polling (if available)
# Preferred: WellSky pushes status changes → Portal webhook endpoint
# Fallback: Portal polls every 15 minutes for status updates
```

### 6.2 Caching Strategy

**Frequently Accessed Data:**
- Caregiver list (for Gigi shift matching) - Cache 24 hours, refresh at 3 AM daily
- Client list (for Gigi caller lookup) - Cache 24 hours, refresh at 3 AM daily
- Open shifts (for alerts) - Cache 5 minutes, real-time critical
- Shift schedule (for operations dashboard) - Cache 15 minutes

**Implementation:**
```python
from functools import lru_cache
import time

@lru_cache(maxsize=1)
def get_cached_caregivers():
    return wellsky.get_caregivers(status="active")

# Cache invalidation: Manual refresh on demand or time-based expiry
```

---

## 7. Error Handling & Monitoring

### 7.1 Retry Logic

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_wellsky_api(endpoint, method="GET", data=None):
    response = requests.request(
        method,
        f"{WELLSKY_BASE_URL}{endpoint}",
        headers={"Authorization": f"Bearer {get_access_token()}"},
        json=data
    )
    response.raise_for_status()
    return response.json()
```

### 7.2 Failure Modes & Fallbacks

| Scenario | Portal Behavior | User Impact |
|----------|----------------|-------------|
| WellSky API down | Use cached data (stale up to 24 hours) | Gigi can still handle calls with yesterday's data |
| WellSky slow response (>5s) | Timeout, use cache, log alert | Minimal user impact, ops team notified |
| Auth token expired | Auto-refresh OAuth token, retry request | Transparent to user |
| Rate limit exceeded | Queue request, retry after 60s | Slight delay in sync, no data loss |
| Webhook delivery failure | Retry 3x with exponential backoff, then email alert | Manual intervention required |

### 7.3 Monitoring & Alerts

**Metrics Tracked:**
- WellSky API response time (target: <2s p95)
- Success rate (target: >99.5%)
- Sync lag (target: <5 minutes for real-time data)
- Cache hit rate (target: >80% for Gigi queries)

**Alerting:**
```
IF wellsky_api_error_rate > 5% for 10 minutes:
    notify: ops@coloradocareassist.com
    severity: HIGH

IF wellsky_api_down for 5 minutes:
    notify: jason@coloradocareassist.com, robin.ponte@wellsky.com
    severity: CRITICAL
```

---

## 8. Testing Strategy

### 8.1 Sandbox Environment

**Sandbox API:** `https://api-sandbox.clearcareonline.com/v1`

**Test Data Strategy:**
```
Sandbox Clients: 10 test clients (5 active, 3 on-hold, 2 discharged)
Sandbox Caregivers: 8 test caregivers (6 active, 2 inactive)
Sandbox Shifts: 30 shifts (10 upcoming, 15 completed, 5 open)
```

**Test Cases:**
1. **Sales CRM → WellSky Prospect Sync**
   - Create deal in CRM → Verify prospect created in WellSky sandbox
   - Update deal stage → Verify prospect status updated
   - Close deal → Verify prospect status = "won"

2. **GoFormz → WellSky Conversion**
   - Simulate signed client packet webhook → Verify prospect converts to client
   - Simulate signed employee packet webhook → Verify applicant converts to caregiver

3. **Gigi → WellSky Data Pull**
   - Trigger Gigi daily sync → Verify caregiver/client lists updated
   - Simulate call-off → Verify Gigi pulls correct shift data

### 8.2 Production Rollout Plan

**Phase 1: Read-Only (Week 1)**
- Enable WellSky API credentials in production
- Activate data pulls (clients, caregivers, shifts) for dashboards
- No writes to WellSky yet - only display data in portal

**Phase 2: One-Way Sync (Week 2-3)**
- Enable Sales CRM → WellSky prospect creation
- Enable Recruiting → WellSky applicant creation
- Monitor for errors, data quality issues

**Phase 3: Two-Way Sync (Week 4)**
- Enable WellSky → Sales status updates
- Enable WellSky → Recruiting performance metrics
- Full production mode

**Phase 4: Automation (Week 5+)**
- Enable GoFormz → WellSky conversions
- Enable Gigi open shift alerts
- Enable predictive analytics dashboards

---

## 9. Stakeholder Contact Information

### Colorado Care Assist Team
- **Technical Lead:** Jason Shulman (jason@coloradocareassist.com)
- **Operations Manager:** Cynthia Pointe (cynthia@coloradocareassist.com)
- **Care Coordinator:** TBD (WellSky primary user)

### WellSky Team
- **API Product Manager:** Robin Ponte (robin.ponte@wellsky.com)
- **Credential Delivery:** Accellion/Kiteworks secure file portal
- **Expected Delivery Date:** Before February 3, 2026

---

## 10. Key Questions for WellSky Product Manager

### 10.1 API Capabilities

1. **Webhooks:** Does WellSky support outbound webhooks for real-time status changes? (vs. polling)
   - Preferred events: client status change, shift assigned, shift completed, caregiver availability update

2. **Batch Operations:** Are there batch endpoints for creating/updating multiple records?
   - Example: `POST /clients/batch` to create 50 prospects at once
   - Reduces API calls, faster sync

3. **Filtering & Pagination:** What's the max page size for list endpoints?
   - Example: `GET /clients?limit=1000` - is 1000 supported or is there a lower max?

### 10.2 Data & Schema

4. **Custom Fields:** Can we add custom fields to client/caregiver records via API?
   - Example: Track "CRM Deal ID" in WellSky client record for easy cross-reference

5. **Field Validation:** Are there required fields beyond what's documented?
   - Example: Does creating a client require a payer source, or can it be null initially?

6. **Status Enums:** Are the prospect/applicant/client/caregiver status values fixed, or can we add custom statuses?

### 10.3 Performance & Reliability

7. **Uptime SLA:** What's WellSky's API uptime commitment?
   - 99.9%? 99.5%? Maintenance windows?

8. **Response Time SLA:** What's the expected p95 response time?
   - Our target is <2s for user-facing queries

9. **Change Management:** How much notice for API deprecations or breaking changes?
    - We need 60+ days to update production code

### 10.4 Advanced Features

10. **EVV Data Access:** Can we pull raw EVV data (GPS coordinates, timestamps) via API?
    - Use case: Custom compliance dashboards

11. **Care Plan API:** Is there an endpoint for care plan CRUD operations?
    - Use case: Auto-generate care plans from sales assessment forms

12. **Family Room API:** Can we programmatically post updates to the Family Room portal?
    - Use case: Automated shift confirmations, care notes visible to families

---

## Appendix A: File Reference

**Core WellSky Integration Files:**
- `/Users/shulmeister/clawd-temp/clawd/services/wellsky_service.py` (2,800 lines)
- `/Users/shulmeister/clawd-temp/clawd/services/sales_wellsky_sync.py`
- `/Users/shulmeister/clawd-temp/clawd/services/recruiting_wellsky_sync.py`
- `/Users/shulmeister/clawd-temp/clawd/services/goformz_wellsky_sync.py`

**Documentation:**
- `/Users/shulmeister/colorado-careassist-portal/docs/WELLSKY_API_INTEGRATION_ROADMAP.md`
- `/Users/shulmeister/colorado-careassist-portal/docs/WELLSKY_PERSONAL_CARE_KNOWLEDGE.md`
- `/Users/shulmeister/clawd/elite-teams/wellsky-api-setup.md`

**Gigi AI Integration:**
- `/Users/shulmeister/colorado-careassist-portal/gigi/daily_sync.py`
- `/Users/shulmeister/colorado-careassist-portal/gigi/main.py`

---

## Appendix B: Data Flow Diagrams

### B.1 Sales Pipeline Data Flow
```
[Sales CRM] --Create Deal--> [WellSky Prospect]
     ↓                              ↓
Update Stage                  Update Status
     ↓                              ↓
Close Deal                    Mark Won
     ↓                              ↓
[GoFormz] --Signed Docs--> [WellSky Client]
                                   ↓
                           Operations Active
                                   ↓
                         [Schedule Shifts]
```

### B.2 Recruiting Pipeline Data Flow
```
[Recruiting Dashboard] --Hired--> [WellSky Applicant]
          ↓                              ↓
    Update Status                  Update Status
          ↓                              ↓
    Mark Hired                     Mark Hired
          ↓                              ↓
  [GoFormz] --Signed Docs--> [WellSky Caregiver]
                                        ↓
                              Shift Assignment Ready
                                        ↓
                              [Available for Shifts]
```

### B.3 Gigi AI Operational Flow
```
[Caregiver Calls Gigi] --"I can't make my shift"-->
    ↓
[Gigi pulls shift data from WellSky API]
    ↓
Identify: Client, Shift Time, Services Needed
    ↓
[Query WellSky for available caregivers]
    ↓
Filter by: Location, Certifications, Availability
    ↓
[Send SMS blast to top 5 matches via RingCentral]
    ↓
First to respond → Assign shift in WellSky
    ↓
Notify client: "Replacement caregiver confirmed"
```

---

**End of Document**

**Document Control:**
- Version 1.0 - Initial release (January 29, 2026)
- Next Review: Upon API credential delivery (before Feb 3, 2026)
- Distribution: Internal (Colorado Care Assist), External (WellSky Product Management)
