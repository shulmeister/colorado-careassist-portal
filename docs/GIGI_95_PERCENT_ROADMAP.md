# Gigi 95% Text Handling Roadmap
**Goal:** Replace Gigi completely by handling 95%+ of caregiver texts autonomously

**Current State:** 70% autonomous (voice call-outs + shift offers work perfectly)
**Target:** 95%+ in 2-4 weeks

---

## Week 1: Close Critical Gaps (Days 1-7)

### Day 1-2: Partial Availability Integration ✅ PARSER BUILT
**Status:** Parser complete and tested on real data (Dina's message)

**Tasks:**
- [x] Build partial availability parser (✅ DONE - `partial_availability_parser.py`)
- [ ] Integrate into `handle_inbound_sms()` in `gigi/main.py`
- [ ] Add new SMS response template for partial availability
- [ ] Test end-to-end with real scenarios

**Integration Code:**
```python
from gigi.partial_availability_parser import detect_partial_availability

async def handle_inbound_sms(sms: InboundSMS):
    # ... existing code ...

    # Check for partial availability BEFORE simple call-out
    partial_avail = detect_partial_availability(sms.message)

    if partial_avail.offers_alternative:
        # NEW: Handle partial availability
        response = await handle_partial_availability(
            phone=sms.from_number,
            caregiver_id=caller_info.person_id,
            alternative_time=f"{partial_avail.start_time}-{partial_avail.end_time}",
            original_message=sms.message
        )
        return response
    elif partial_avail.is_cancelling:
        # Existing call-out handling
        ...
```

**Expected Response:**
```
Caregiver: "I can't work with Judy tomorrow but I could do 8:30 to 11:30"

Gigi: "Thanks for letting us know! I've notified the coordinator about your
       availability from 8:30am-11:30am. They'll reach out within the hour
       to confirm if we can adjust the shift. I really appreciate you offering
       an alternative time!"

[BACKEND: Sends SMS to coordinator with parsed data]
```

**Impact:** Handles 10-15% more texts (partial availability scenarios)

---

### Day 3-4: Running Late Notifications
**Current:** Escalates to human
**Target:** Auto-notify client + log in WellSky

**Tasks:**
- [ ] Add `detect_running_late()` intent
- [ ] Add `notify_client_caregiver_late()` function
- [ ] Extract delay time ("15 minutes", "30 mins")
- [ ] Send SMS to client
- [ ] Log in WellSky shift notes
- [ ] Confirm with caregiver

**Example Scenarios:**
```
"I'm running 15 minutes late to Mrs. Johnson's"
"Traffic is bad, I'll be there at 2:20 instead of 2:00"
"Running late, about 10 minutes"
```

**Gigi Response:**
```
"No problem! I've let Mrs. Johnson know you're running about 15 minutes late.
 Drive safe and see you there!"

[BACKEND: SMS to client]
To: Mrs. Johnson (303-555-1234)
"Hi Mrs. Johnson! This is Colorado Care Assist. Your caregiver Maria is
running about 15 minutes late due to traffic. She'll be there around 2:15pm.
Thank you for your patience!"
```

**Impact:** Handles 5-8% more texts

---

### Day 5-7: Conversational Context (Multi-Turn SMS)
**Current:** Stateless (forgets previous messages)
**Target:** Remember last 3 messages in conversation

**Tasks:**
- [ ] Add `sms_conversation_context` table to database
- [ ] Store last 3 messages per phone number
- [ ] Pass context to Gemini for better responses
- [ ] Auto-expire context after 30 minutes of inactivity

**Schema:**
```sql
CREATE TABLE sms_conversation_context (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    messages JSONB NOT NULL,  -- Array of last 3 messages
    last_updated TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    INDEX idx_phone_context (phone_number, expires_at)
);
```

**Example:**
```
Caregiver: "Can I pick up a shift Thursday?"
Gigi: "Let me check what's available Thursday. We have Mrs. Davis 2-6pm.
       Interested?"
Caregiver: "Only after 3pm"  ← Gigi remembers we're talking about Thursday
Gigi: "Got it! I don't have Thursday 3-6pm available right now, but I'll
       let you know if something opens up. Thanks!"
```

**Impact:** Handles 10-12% more texts (follow-up questions)

---

## Week 2: Polish & Edge Cases (Days 8-14)

### Day 8-9: Clock-In/Out Automation
**Current:** Detects intent, suggests calling office
**Target:** Auto clock-out via WellSky API + confirm

**Tasks:**
- [ ] Add WellSky clock-in/clock-out API integration
- [ ] Verify caregiver's active shift
- [ ] Execute clock action
- [ ] Send confirmation

**Example:**
```
"Can you clock me out? I forgot"
→ Gigi checks WellSky
→ Finds active shift for Mrs. Johnson 2-6pm
→ Clocks out at current time
→ "Done! I've clocked you out at 5:58pm for Mrs. Johnson. Have a great evening!"
```

**Impact:** Handles 5% more texts

---

### Day 10-11: Schedule Queries (Full Week View)
**Current:** Gives generic response
**Target:** Pull full schedule from WellSky, format as SMS

**Tasks:**
- [ ] Query WellSky for next 7 days of shifts
- [ ] Format as readable SMS (max 160 chars per SMS)
- [ ] Handle "when do I work", "my schedule", "shifts this week"

**Example:**
```
"When do I work this week?"

Gigi: "Your schedule for this week:
Mon 1/29: Mrs. Johnson 2-6pm
Tue 1/30: Mr. Davis 10am-2pm
Wed 1/31: Mrs. Johnson 2-6pm
Thu 2/1: OFF
Fri 2/2: Mrs. Martinez 9am-1pm
Sat 2/3: OFF
Sun 2/4: Mrs. Johnson 2-6pm

Need to make any changes? Let me know!"
```

**Impact:** Handles 8-10% more texts

---

### Day 12-14: Testing & Refinement
**Tasks:**
- [ ] Run full test suite on real caregiver messages
- [ ] Measure autonomous handling rate
- [ ] Fix edge cases
- [ ] A/B test response templates
- [ ] Document failure cases

**Test Data Sources:**
1. RingCentral "New Scheduling" chat (coordinator notes about caregiver issues)
2. BeeTexting message history
3. Retell AI call transcripts (convert voice scenarios to SMS)

**Success Metrics:**
- [ ] 90%+ autonomous handling rate
- [ ] <5% escalation rate for known scenarios
- [ ] <2% caregiver complaints about Gigi responses
- [ ] 0 critical failures (wrong shift assigned, etc.)

---

## Week 3-4: Advanced Features (Optional - Exceed Gigi)

### Proactive Features
1. **Shift Reminders** (Day 15-16)
   - Send SMS 2 hours before shift starts
   - "Hi Maria! Reminder: Mrs. Johnson today at 2pm (123 Main St). See you there!"

2. **No-Show Prevention** (Day 17-18)
   - If caregiver doesn't clock in within 15 min of start time
   - Auto-SMS: "Hi Maria! Just checking - are you on your way to Mrs. Johnson's?
     Let me know if you need help!"

3. **Reliability Scoring** (Day 19-20)
   - Track caregiver response patterns
   - Prioritize reliable caregivers for shift offers
   - Flag potential no-shows before they happen

4. **Smart Shift Matching** (Day 21-22)
   - Learn caregiver preferences (clients, times, locations)
   - Only offer shifts that match preferences
   - Higher acceptance rate = faster filling

---

## Success Criteria

### Week 1 End (Day 7)
- ✅ 85%+ autonomous text handling
- ✅ Partial availability parser integrated
- ✅ Running late notifications working
- ✅ Conversational context implemented

### Week 2 End (Day 14)
- ✅ 90%+ autonomous text handling
- ✅ Clock-in/out automation working
- ✅ Schedule queries working
- ✅ All tests passing

### Week 4 End (Day 28)
- ✅ 95%+ autonomous text handling
- ✅ Proactive features launched
- ✅ Full Gigi replacement achieved
- ✅ $33.6K/year cost savings realized

---

## Cost Analysis

| Timeframe | Autonomous Rate | Coordinator Time Saved | Annual Savings |
|---|---|---|---|
| **Today** | 70% | 50% | $22.8K |
| **Week 1** | 85% | 70% | $27.3K |
| **Week 2** | 90% | 85% | $30.6K |
| **Week 4** | 95% | 95% | $33.6K+ |

**ROI:**
- Development time: 2-4 weeks
- WellSky API cost: $220/month = $2,640/year
- **Net savings Year 1:** $31,000+
- **Payback period:** Immediate (already saving $22.8K with current features)

---

## Implementation Order (Priority)

### CRITICAL (Must Have for Gigi Replacement)
1. ✅ Partial availability parser (DONE)
2. Running late notifications
3. Conversational context

### HIGH PRIORITY (Significant Impact)
4. Clock-in/out automation
5. Schedule queries

### NICE TO HAVE (Exceed Gigi)
6. Shift reminders
7. No-show prevention
8. Reliability scoring

---

## Risk Mitigation

**Risk:** Gigi makes a mistake and assigns wrong shift
**Mitigation:**
- Database locks prevent race conditions (✅ DONE in Fix #2)
- All WellSky updates logged with rollback capability
- Human escalation for ambiguous cases

**Risk:** Caregivers don't trust AI responses
**Mitigation:**
- Soft launch with 5-10 test caregivers first
- Collect feedback and iterate
- Always offer option to "speak to a coordinator"

**Risk:** SMS costs increase significantly
**Mitigation:**
- Track SMS volume daily
- Set alerts at >500 SMS/day
- Optimize message templates to reduce length

---

## Next Steps

**IMMEDIATE (TODAY):**
1. Integrate partial availability parser into `handle_inbound_sms()`
2. Write test cases for Dina's scenario
3. Deploy to staging

**THIS WEEK:**
1. Build running late notification
2. Add conversational context
3. Test with real caregiver messages

**NEXT WEEK:**
1. Clock-in/out automation
2. Schedule queries
3. Full regression testing

---

**Bottom Line:** We can hit 95%+ text handling in 2-4 weeks and fully replace Gigi, saving $31K+/year.
