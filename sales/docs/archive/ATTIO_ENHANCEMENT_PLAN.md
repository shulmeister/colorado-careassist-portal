# Sales Dashboard Enhancement Plan
## Inspired by Attio CRM Architecture

**Created:** 2026-01-19
**Status:** Planning

---

## Overview

This plan outlines four major enhancements to transform the Sales Dashboard into a more intelligent, relationship-aware CRM system inspired by Attio's architecture.

---

## 1. AI Enrichment

### Current State
- Gemini used for business card OCR/parsing (`business_card_scanner.py`, `ai_document_parser.py`)
- Manual data entry for company information
- No duplicate detection
- Gmail/RingCentral data exists but not summarized

### Enhancements

#### 1.1 Company Enrichment
**Trigger:** When creating/updating a ReferralSource

**Data to Fetch:**
- Company size (employees)
- Industry/facility type
- Website, phone, address validation
- Key contacts (from LinkedIn, website scraping)
- Logo/favicon

**Implementation:**
```
New file: ai_enrichment_service.py

async def enrich_company(name: str, address: str = None) -> dict:
    """
    Use Gemini + web search to enrich company data.
    Returns: {
        "size": "50-200 employees",
        "industry": "Skilled Nursing Facility",
        "website": "https://...",
        "phone": "...",
        "key_contacts": [{"name": "...", "title": "Administrator", "email": "..."}],
        "logo_url": "...",
        "confidence": 0.85
    }
    """
```

**API Endpoint:**
- `POST /api/companies/{id}/enrich` - Trigger enrichment
- `GET /api/companies/{id}/enrichment-status` - Check status

**UI Changes:**
- "Enrich" button on company detail page
- Auto-enrich toggle in settings
- Show enrichment confidence score

#### 1.2 Email/Call Summarization
**Trigger:** When viewing contact/company timeline

**Data Sources:**
- Gmail threads (existing `gmail_service.py`)
- RingCentral call logs (existing `ringcentral_service.py`)

**Implementation:**
```
async def summarize_interactions(contact_id: int) -> dict:
    """
    Aggregate and summarize all interactions.
    Returns: {
        "summary": "3 emails exchanged about home care services. Last contact was positive, discussing potential referral.",
        "sentiment": "positive",
        "key_topics": ["home care", "pricing", "availability"],
        "next_action": "Follow up on referral discussion",
        "last_interaction": "2026-01-15"
    }
    """
```

**API Endpoint:**
- `GET /api/contacts/{id}/interaction-summary`
- `GET /api/companies/{id}/interaction-summary`

**UI Changes:**
- AI summary card at top of contact/company detail
- "Refresh Summary" button
- Sentiment indicator (green/yellow/red)

#### 1.3 Contact Deduplication
**Trigger:** After business card scan, on-demand bulk scan

**Detection Criteria:**
- Exact email match (definite duplicate)
- Phone number match (likely duplicate)
- Name + Company fuzzy match (possible duplicate)
- Address similarity

**Implementation:**
```
async def find_duplicates(contact: Contact) -> list:
    """
    Find potential duplicates for a contact.
    Returns: [
        {"contact_id": 123, "match_type": "email", "confidence": 1.0},
        {"contact_id": 456, "match_type": "name+company", "confidence": 0.75}
    ]
    """

async def merge_contacts(primary_id: int, duplicate_ids: list) -> Contact:
    """
    Merge duplicate contacts, preserving all relationships.
    - Moves all activities to primary
    - Updates deal contact_ids
    - Preserves best data from each
    """
```

**API Endpoints:**
- `GET /api/contacts/{id}/duplicates` - Find duplicates for one contact
- `POST /api/contacts/scan-duplicates` - Bulk duplicate scan
- `POST /api/contacts/merge` - Merge duplicates

**UI Changes:**
- Duplicate warning after business card scan
- Bulk deduplication tool in settings
- Merge confirmation modal with field-by-field comparison

---

## 2. Relationship Graph

### Current State
```
Contact --company_id--> ReferralSource (FK exists)
Deal --company_id--> ReferralSource (no FK, just integer)
Deal --contact_ids--> [Contacts] (JSON array, no FK)
ActivityLog has contact_id, deal_id, company_id (FKs exist but no relationships defined)
```

### Enhancements

#### 2.1 Proper SQLAlchemy Relationships

**Model Changes:**

```python
# models.py updates

class Contact(Base):
    # Existing fields...
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True)

    # NEW: Relationships
    company = relationship("ReferralSource", back_populates="contacts")
    deals = relationship("Deal", secondary="deal_contacts", back_populates="contacts")
    activities = relationship("ActivityLog", back_populates="contact")
    tasks = relationship("ContactTask", back_populates="contact")

class ReferralSource(Base):
    # Existing fields...

    # NEW: Relationships
    contacts = relationship("Contact", back_populates="company")
    deals = relationship("Deal", back_populates="company")
    activities = relationship("ActivityLog", back_populates="company")

class Deal(Base):
    # Existing fields...
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True)  # ADD FK
    primary_contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)  # NEW: Decision maker

    # NEW: Relationships
    company = relationship("ReferralSource", back_populates="deals")
    primary_contact = relationship("Contact", foreign_keys=[primary_contact_id])
    contacts = relationship("Contact", secondary="deal_contacts", back_populates="deals")
    activities = relationship("ActivityLog", back_populates="deal")

# NEW: Association table for Deal <-> Contact many-to-many
class DealContact(Base):
    __tablename__ = "deal_contacts"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    role = Column(String(100), nullable=True)  # "decision_maker", "influencer", "user", "champion"
    created_at = Column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    # Existing fields...

    # NEW: Relationships
    contact = relationship("Contact", back_populates="activities")
    deal = relationship("Deal", back_populates="activities")
    company = relationship("ReferralSource", back_populates="activities")
```

#### 2.2 Migration Strategy

```python
# Migration script: migrate_deal_contacts.py

def migrate_contact_ids_to_association_table():
    """
    Migrate Deal.contact_ids JSON array to deal_contacts table.
    Preserves existing data.
    """
    for deal in deals:
        if deal.contact_ids:
            contact_ids = json.loads(deal.contact_ids)
            for cid in contact_ids:
                # Create DealContact record
                # First contact becomes primary_contact_id
```

#### 2.3 API Enhancements

**New Endpoints:**
- `GET /api/contacts/{id}/relationships` - Get all related entities
- `GET /api/companies/{id}/relationships` - Get all related entities
- `GET /api/deals/{id}/contacts` - Get contacts with roles
- `POST /api/deals/{id}/contacts` - Add contact to deal with role
- `DELETE /api/deals/{id}/contacts/{contact_id}` - Remove contact from deal

**Response Format:**
```json
{
  "contact": {...},
  "relationships": {
    "company": {"id": 1, "name": "Sunrise Senior Living"},
    "deals": [
      {"id": 5, "name": "New Client - Smith", "role": "decision_maker"}
    ],
    "activities_count": 12,
    "tasks_pending": 2
  }
}
```

#### 2.4 UI Changes

- **Contact Detail Page:**
  - Company card with link
  - Deals list with roles
  - "Add to Deal" button

- **Company Detail Page:**
  - Contacts list
  - Deals list
  - Activity count badge

- **Deal Detail Page:**
  - Contacts section with role assignment
  - Primary contact highlight
  - Company link

- **Relationship Visualization:**
  - Simple graph view showing Contact <-> Company <-> Deals

---

## 3. Time-in-Stage Tracking

### Current State
- `Deal.stage` exists (string field)
- `Deal.updated_at` exists but not stage-specific
- No history of stage changes
- No visibility into stuck deals

### Enhancements

#### 3.1 Stage History Table

```python
class DealStageHistory(Base):
    """Track every stage change for a deal"""
    __tablename__ = "deal_stage_history"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    from_stage = Column(String(100), nullable=True)  # NULL for initial stage
    to_stage = Column(String(100), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(String(255), nullable=True)  # User email
    duration_seconds = Column(Integer, nullable=True)  # Time spent in from_stage

    deal = relationship("Deal", back_populates="stage_history")
```

#### 3.2 Deal Model Updates

```python
class Deal(Base):
    # Existing fields...
    stage_entered_at = Column(DateTime, nullable=True)  # NEW

    # NEW: Relationships
    stage_history = relationship("DealStageHistory", back_populates="deal", order_by="DealStageHistory.changed_at")

    @property
    def days_in_current_stage(self) -> int:
        if self.stage_entered_at:
            return (datetime.utcnow() - self.stage_entered_at).days
        return 0

    @property
    def is_stale(self) -> bool:
        return self.days_in_current_stage > 30
```

#### 3.3 Stage Change Logic

```python
# In app.py or deals_service.py

def update_deal_stage(deal: Deal, new_stage: str, user_email: str = None):
    """
    Update deal stage with history tracking.
    """
    if deal.stage == new_stage:
        return  # No change

    # Calculate time in previous stage
    duration = None
    if deal.stage_entered_at:
        duration = int((datetime.utcnow() - deal.stage_entered_at).total_seconds())

    # Create history record
    history = DealStageHistory(
        deal_id=deal.id,
        from_stage=deal.stage,
        to_stage=new_stage,
        changed_by=user_email,
        duration_seconds=duration
    )
    db.add(history)

    # Update deal
    deal.stage = new_stage
    deal.stage_entered_at = datetime.utcnow()

    # Log activity
    log_activity(
        activity_type="deal_stage_change",
        deal_id=deal.id,
        description=f"Stage changed: {deal.stage} → {new_stage}"
    )
```

#### 3.4 API Enhancements

**New Endpoints:**
- `GET /api/deals/stale` - Get deals stuck > 30 days
- `GET /api/deals/{id}/stage-history` - Get stage change history
- `GET /api/analytics/stage-duration` - Average time per stage

**Response Format:**
```json
{
  "deal": {...},
  "current_stage": "proposal",
  "days_in_stage": 45,
  "is_stale": true,
  "stage_history": [
    {"from": null, "to": "opportunity", "date": "2026-01-01", "duration_days": null},
    {"from": "opportunity", "to": "qualified", "date": "2026-01-10", "duration_days": 9},
    {"from": "qualified", "to": "proposal", "date": "2026-01-15", "duration_days": 5}
  ]
}
```

#### 3.5 Dashboard & Alerts

**Dashboard Widget: "Stale Deals"**
- List of deals > 30 days in current stage
- Sort by days stuck (most stuck first)
- Quick action: "Update Stage" or "Add Note"

**Alert System:**
```python
# Daily job or on-demand
def check_stale_deals():
    stale = db.query(Deal).filter(
        Deal.stage_entered_at < datetime.utcnow() - timedelta(days=30),
        Deal.archived_at.is_(None)
    ).all()

    for deal in stale:
        # Create notification/task
        # Optionally send email alert
```

---

## 4. Unified Activity Timeline

### Current State
- `ActivityLog` table exists with contact_id, deal_id, company_id
- `ActivityNote` separate table (not linked to entities)
- `Visit` table (links via business_name, not company_id)
- Gmail emails synced separately
- RingCentral calls synced separately
- No unified view

### Enhancements

#### 4.1 Consolidate All Activities into ActivityLog

**Activity Types to Support:**
```python
ACTIVITY_TYPES = [
    # Manual
    "note",           # User-added note
    "task_created",   # Task created
    "task_completed", # Task completed

    # Automatic - Documents
    "card_scan",      # Business card scanned
    "document",       # Drive document linked

    # Automatic - Communication
    "email_sent",     # Email sent (Gmail)
    "email_received", # Email received (Gmail)
    "call_inbound",   # Inbound call (RingCentral)
    "call_outbound",  # Outbound call (RingCentral)
    "call_missed",    # Missed call (RingCentral)

    # Automatic - CRM Events
    "deal_created",   # New deal created
    "deal_stage_change",  # Deal stage changed
    "deal_won",       # Deal closed-won
    "deal_lost",      # Deal closed-lost
    "contact_created", # New contact created
    "visit",          # Sales visit logged
]
```

#### 4.2 Enhanced ActivityLog Model

```python
class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)

    # Core fields
    activity_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # NEW: Short title
    description = Column(Text, nullable=True)   # Detailed description

    # Entity relationships (polymorphic - can link to multiple)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True, index=True)

    # User tracking
    user_email = Column(String(255), nullable=True, index=True)

    # Communication metadata
    direction = Column(String(20), nullable=True)  # "inbound", "outbound"
    duration_seconds = Column(Integer, nullable=True)  # Call duration
    participants = Column(Text, nullable=True)  # JSON array of emails/phones

    # External references
    external_id = Column(String(255), nullable=True, index=True)  # Gmail ID, RingCentral ID, etc.
    external_url = Column(Text, nullable=True)  # Link to original (Gmail, Drive, etc.)

    # Rich content
    content = Column(Text, nullable=True)  # Full email body, note content, call transcript
    attachments = Column(Text, nullable=True)  # JSON array of attachment info

    # Metadata
    extra_data = Column(Text, nullable=True)  # JSON for any additional data

    # Timestamps
    occurred_at = Column(DateTime, nullable=False, index=True)  # When the activity happened
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    contact = relationship("Contact", back_populates="activities")
    deal = relationship("Deal", back_populates="activities")
    company = relationship("ReferralSource", back_populates="activities")
```

#### 4.3 Timeline API

**Unified Timeline Endpoint:**
```
GET /api/timeline?contact_id=123
GET /api/timeline?company_id=456
GET /api/timeline?deal_id=789
GET /api/timeline?contact_id=123&company_id=456  # Combined view
```

**Query Parameters:**
- `contact_id`, `company_id`, `deal_id` - Filter by entity (can combine)
- `activity_type` - Filter by type (comma-separated)
- `start_date`, `end_date` - Date range
- `limit`, `offset` - Pagination

**Response Format:**
```json
{
  "timeline": [
    {
      "id": 1001,
      "activity_type": "email_sent",
      "title": "Re: Home Care Services Inquiry",
      "description": "Sent follow-up email about service availability",
      "occurred_at": "2026-01-19T14:30:00Z",
      "user_email": "sales@coloradocareassist.com",
      "direction": "outbound",
      "external_url": "https://mail.google.com/...",
      "linked_entities": {
        "contact": {"id": 123, "name": "Jane Smith"},
        "company": {"id": 456, "name": "Sunrise Senior Living"}
      }
    },
    {
      "id": 1000,
      "activity_type": "call_inbound",
      "title": "Call from Jane Smith",
      "description": "Discussed pricing for 20 hours/week of care",
      "occurred_at": "2026-01-19T10:15:00Z",
      "duration_seconds": 480,
      "direction": "inbound",
      "linked_entities": {
        "contact": {"id": 123, "name": "Jane Smith"}
      }
    }
  ],
  "total": 45,
  "has_more": true
}
```

#### 4.4 Activity Creation Helpers

```python
# activity_service.py

def log_activity(
    activity_type: str,
    title: str = None,
    description: str = None,
    contact_id: int = None,
    deal_id: int = None,
    company_id: int = None,
    user_email: str = None,
    occurred_at: datetime = None,
    **kwargs
) -> ActivityLog:
    """
    Central function to log any activity.
    Automatically links related entities.
    """
    # Auto-link: If contact has company_id, also link to company
    if contact_id and not company_id:
        contact = db.query(Contact).get(contact_id)
        if contact and contact.company_id:
            company_id = contact.company_id

    activity = ActivityLog(
        activity_type=activity_type,
        title=title,
        description=description,
        contact_id=contact_id,
        deal_id=deal_id,
        company_id=company_id,
        user_email=user_email,
        occurred_at=occurred_at or datetime.utcnow(),
        **kwargs
    )
    db.add(activity)

    # Update last_activity on related entities
    if contact_id:
        db.query(Contact).filter_by(id=contact_id).update({"last_activity": activity.occurred_at})

    return activity
```

#### 4.5 Sync Services Update

**Gmail Sync (`gmail_service.py`):**
```python
def sync_gmail_to_timeline(contact: Contact):
    """
    Sync Gmail threads to ActivityLog.
    Dedupe by external_id (Gmail message ID).
    """
    emails = fetch_gmail_threads(contact.email)
    for email in emails:
        existing = db.query(ActivityLog).filter_by(external_id=email['id']).first()
        if not existing:
            log_activity(
                activity_type="email_sent" if email['from'] == 'me' else "email_received",
                title=email['subject'],
                description=email['snippet'],
                contact_id=contact.id,
                external_id=email['id'],
                external_url=email['link'],
                occurred_at=email['date'],
                direction="outbound" if email['from'] == 'me' else "inbound"
            )
```

**RingCentral Sync (`ringcentral_service.py`):**
```python
def sync_ringcentral_to_timeline():
    """
    Sync RingCentral calls to ActivityLog.
    Match phone numbers to contacts.
    """
    calls = fetch_recent_calls()
    for call in calls:
        contact = find_contact_by_phone(call['phone'])
        if contact:
            log_activity(
                activity_type=f"call_{call['direction']}",
                title=f"Call {'from' if call['direction'] == 'inbound' else 'to'} {contact.name}",
                contact_id=contact.id,
                external_id=call['id'],
                duration_seconds=call['duration'],
                occurred_at=call['timestamp'],
                direction=call['direction']
            )
```

#### 4.6 UI: Timeline Component

**Contact/Company Detail Page:**
```
┌─────────────────────────────────────────────────────────────┐
│ Activity Timeline                               [+ Add Note] │
├─────────────────────────────────────────────────────────────┤
│ ○ Today                                                      │
│   📧 Email sent: "Re: Home Care Services"          2:30 PM   │
│   📞 Inbound call (8 min)                         10:15 AM   │
│                                                              │
│ ○ Yesterday                                                  │
│   📝 Note: "Interested in 20 hrs/week"             3:45 PM   │
│   📋 Task completed: "Send pricing info"          11:00 AM   │
│                                                              │
│ ○ Jan 15, 2026                                              │
│   🎯 Deal stage: Opportunity → Qualified                     │
│   📧 Email received: "Pricing question"            9:30 AM   │
│                                                              │
│ [Load More]                                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. **Relationship Graph** - Model changes, migration, basic API
2. **Time-in-Stage** - Model changes, stage history, basic dashboard

### Phase 2: Timeline (Week 3-4)
3. **Unified Timeline** - Consolidate ActivityLog, new API, UI component
4. Update Gmail/RingCentral sync to use new system

### Phase 3: AI (Week 5-6)
5. **Company Enrichment** - Gemini integration, enrichment API
6. **Contact Deduplication** - Duplicate detection, merge UI
7. **Interaction Summarization** - AI summaries per contact/company

### Phase 4: Polish (Week 7-8)
8. Stale deals dashboard & alerts
9. Relationship visualization
10. Performance optimization & testing

---

## Database Migration Plan

```sql
-- Phase 1: Relationship Graph
CREATE TABLE deal_contacts (
    id SERIAL PRIMARY KEY,
    deal_id INTEGER NOT NULL REFERENCES deals(id),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    role VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(deal_id, contact_id)
);

ALTER TABLE deals ADD COLUMN primary_contact_id INTEGER REFERENCES contacts(id);
ALTER TABLE deals ADD CONSTRAINT fk_deals_company FOREIGN KEY (company_id) REFERENCES referral_sources(id);

-- Phase 1: Time-in-Stage
ALTER TABLE deals ADD COLUMN stage_entered_at TIMESTAMP;
UPDATE deals SET stage_entered_at = updated_at WHERE stage_entered_at IS NULL;

CREATE TABLE deal_stage_history (
    id SERIAL PRIMARY KEY,
    deal_id INTEGER NOT NULL REFERENCES deals(id),
    from_stage VARCHAR(100),
    to_stage VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP DEFAULT NOW(),
    changed_by VARCHAR(255),
    duration_seconds INTEGER
);

-- Phase 2: Timeline
ALTER TABLE activity_logs ADD COLUMN title VARCHAR(255);
ALTER TABLE activity_logs ADD COLUMN direction VARCHAR(20);
ALTER TABLE activity_logs ADD COLUMN duration_seconds INTEGER;
ALTER TABLE activity_logs ADD COLUMN participants TEXT;
ALTER TABLE activity_logs ADD COLUMN content TEXT;
ALTER TABLE activity_logs ADD COLUMN attachments TEXT;
ALTER TABLE activity_logs ADD COLUMN occurred_at TIMESTAMP;
UPDATE activity_logs SET occurred_at = created_at WHERE occurred_at IS NULL;
CREATE INDEX idx_activity_logs_occurred_at ON activity_logs(occurred_at);
```

---

## Success Metrics

| Feature | Metric | Target |
|---------|--------|--------|
| Relationship Graph | Contacts linked to companies | >90% |
| Relationship Graph | Deals with primary contact | >80% |
| Time-in-Stage | Stale deals identified | 100% visibility |
| Time-in-Stage | Avg time to close | Baseline established |
| Timeline | Activities per contact | >5 avg |
| Timeline | Gmail/RC sync coverage | >95% |
| AI Enrichment | Companies auto-enriched | >70% |
| AI Enrichment | Duplicates detected | >90% recall |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Migration breaks existing deals | High | Backup + staged rollout |
| Gmail API rate limits | Medium | Batch sync, caching |
| Gemini costs for enrichment | Low | Cache results, on-demand only |
| Duplicate merge loses data | High | Soft delete, audit log |

---

## Approval Checklist

- [ ] Phase 1: Relationship Graph
- [ ] Phase 2: Time-in-Stage Tracking
- [ ] Phase 3: Unified Activity Timeline
- [ ] Phase 4: AI Enrichment

**Next Step:** Review and approve individual phases before implementation.
