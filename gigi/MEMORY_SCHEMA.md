# Gigi's Memory Schema (v1.0)

**Memory is not a junk drawer.**

This defines what gets stored, how long it lives, and how it evolves.

---

## Memory Types

### 1. Explicit Instructions
**Source:** Direct statements from you
**Lifetime:** Permanent (until explicitly changed)
**Confidence:** 1.0
**Examples:**
- "I hate elevators in hotels"
- "Never book United"
- "Always cc legal on vendor contracts"

### 2. Corrections
**Source:** You correcting Gigi's behavior
**Lifetime:** Long-term (decays slowly)
**Confidence:** 0.9 (initial)
**Examples:**
- "Don't use that tone with clients"
- "This should be 'urgent' not 'high priority'"
- "Next time, ask before sending"

### 3. Confirmed Patterns
**Source:** Repeated behavior you've reinforced
**Lifetime:** Medium-term (requires periodic reinforcement)
**Confidence:** 0.7-0.9
**Examples:**
- You always respond to X person within 1 hour
- You prefer morning meetings over afternoon
- You escalate tone after 2 ignored follow-ups

### 4. Inferred Patterns
**Source:** Gigi detecting patterns in your behavior
**Lifetime:** Short-term (decays unless confirmed)
**Confidence:** 0.5-0.7
**Examples:**
- You seem to prefer Slack over email for quick questions
- You tend to skip meetings on Fridays
- You respond faster to certain people

### 5. Single Inferences
**Source:** One-time observations
**Lifetime:** Very short-term (decays rapidly)
**Confidence:** 0.3-0.5
**Examples:**
- You seemed annoyed by that interruption
- You skipped lunch today
- You changed this template once

### 6. Temporary Insights (Thinking Mode)
**Source:** Captured during exploration
**Lifetime:** 48 hours (unless promoted)
**Confidence:** N/A (not actionable)
**Examples:**
- "This approach might work because X"
- "Pattern noticed: Y correlates with Z"
- Framework sketched during brainstorm

---

## Decay Mechanism

### How Memories Degrade

**On decay:**
- Confidence degrades
- Memory becomes "inactive"
- **Not deleted — archived**

### Decay Rates by Type

| Memory Type | Decay Rate | Inactive Threshold |
|-------------|------------|-------------------|
| Explicit Instructions | None | Never |
| Corrections | 5% per month | <0.5 confidence |
| Confirmed Patterns | 10% per month | <0.5 confidence |
| Inferred Patterns | 20% per month | <0.4 confidence |
| Single Inferences | 50% per week | <0.3 confidence |
| Temporary Insights | 50% per day | 48 hours |

### Reinforcement

Memories get reinforced when:
- You repeat the behavior
- You explicitly confirm it
- Pattern continues to hold
- Correction is followed consistently

**Reinforcement effect:** +10-20% confidence (capped at type maximum)

---

## Source Hierarchy (Trust Order)

**When conflicts occur, this always wins:**

1. **Explicit instruction from you**
2. **Recent correction**
3. **Repeated confirmed behavior**
4. **Pattern inference**
5. **Single inference**

### Conflict Resolution

Gigi must surface conflicts explicitly:

> "This conflicts with an older preference — which should win?"

**No silent overriding.**

---

## Promotion Rules (How Memory Evolves)

### Temporary → Preference

**Requires:**
- Repetition (2-3 times)
- No contradictions
- Confidence ≥0.7

**Process:**
1. Gigi notices pattern
2. Captures as temporary insight
3. Sees it repeat
4. Asks: "I'm noticing [pattern]. Should I treat this as a preference?"
5. On confirmation → promotes to Confirmed Pattern

### Pattern → Preference

**Requires:**
- Explicit confirmation from you

**Process:**
1. Gigi detects pattern
2. States it clearly
3. You confirm
4. Promoted to Confirmed Pattern or Explicit Instruction

### Inference → Rule

**NEVER ALLOWED**

Inferences can become patterns.
Patterns can become preferences.
But nothing auto-promotes to hard rules.

---

## Memory Hygiene Rules (Non-Negotiable)

### Gigi must:

1. **Periodically summarize active memory**
   - Monthly in Review Mode
   - Surface high-confidence memories for review
   - Flag any that seem stale

2. **Flag stale high-impact memories**
   - If confidence <0.6 and memory affects money/reputation
   - Ask for reconfirmation

3. **Ask for confirmation sparingly**
   - Bundle multiple checks into one question
   - Only for high-impact decisions
   - Never ask about the same thing twice in a row

4. **Never surprise you with old assumptions**
   - If acting on memory >6 months old, mention it
   - If acting on low-confidence memory, state it
   - If memory source is unclear, don't use it

### If unsure:

> "This might be outdated — confirm?"

---

## Failure Mode Protection

### If Gigi detects:

**Conflicting memories:**
- Example: Old preference says X, recent correction says Y
- **Action:** Pause, surface conflict, ask which wins

**Low confidence driving action:**
- Example: Confidence <0.6 being used for autonomous action
- **Action:** Stop, state confidence level, ask for confirmation

**Excessive memory growth:**
- Example: Too many single inferences cluttering memory
- **Action:** Auto-archive low-confidence memories, summarize to you

### Protocol:

1. **Pause promotion**
2. **Surface summary**
3. **Ask for clarification once**

**Example:**
> "I have 3 conflicting preferences about meeting length. Here's what I see: [summary]. Which should I follow?"

---

## The Trust Line

**You should always be able to ask:**
> "Why did you do that?"

**And Gigi must answer:**
> "Because of this memory, last confirmed [when], confidence [X]."

### Requirements:

- Every action must trace to a memory
- Every memory must have a confidence score
- Every memory must have a source
- Every memory must have a last-updated timestamp

**If she can't explain it, she shouldn't act on it.**

---

## Memory Storage Format

Each memory must include:

```json
{
  "type": "explicit_instruction | correction | confirmed_pattern | inferred_pattern | single_inference | temporary",
  "content": "The actual preference/rule/pattern",
  "confidence": 0.0-1.0,
  "source": "explicit | correction | pattern | inference",
  "created": "timestamp",
  "last_confirmed": "timestamp",
  "last_reinforced": "timestamp",
  "reinforcement_count": 0,
  "conflicts_with": ["memory_id_1", "memory_id_2"],
  "status": "active | inactive | archived",
  "category": "communication | scheduling | money | relationships | preferences | other",
  "impact_level": "high | medium | low"
}
```

---

## Memory Audit (Review Mode)

### Monthly Audit Checklist:

1. **High-confidence review**
   - List all memories with confidence >0.8
   - Ask: "Still accurate?"

2. **Conflict detection**
   - Find all conflicting memories
   - Resolve or clarify

3. **Stale pattern check**
   - Find patterns not reinforced in 60+ days
   - Ask: "Still relevant?"

4. **Archive old inferences**
   - Auto-archive single inferences >30 days old
   - Summarize: "Archived 47 old observations, none seemed significant"

5. **Promotion candidates**
   - List patterns that could become preferences
   - Ask: "Should any of these become rules?"

---

## Examples in Practice

### Good Memory Evolution

**Day 1:**
- You skip a 4pm meeting
- Gigi logs: Single inference ("Jason skipped 4pm meeting"), confidence 0.3

**Day 8:**
- You skip another 4pm meeting
- Gigi updates: Inferred pattern ("Jason avoids late afternoon meetings"), confidence 0.5

**Day 15:**
- Gigi asks: "I'm noticing you often skip late afternoon meetings. Should I avoid scheduling them?"
- You confirm: "Yes, nothing after 3pm"
- Promoted to: Explicit instruction, confidence 1.0

### Bad Memory Evolution (Prevented)

**Day 1:**
- You're short with someone on Slack
- ❌ OLD BEHAVIOR: Gigi assumes you hate Slack
- ✅ NEW BEHAVIOR: Gigi logs single inference ("Jason seemed frustrated on Slack"), confidence 0.3, does not act on it

**Day 8:**
- Pattern hasn't repeated
- Memory decays to confidence 0.15
- Auto-archived

**No false preference created.**

---

## The North Star

**Good memory system:**
- Gigi learns without being told
- Gigi never surprises you with stale assumptions
- Gigi can explain every action
- You feel understood, not stereotyped

**Bad memory system:**
- Gigi asks you to repeat yourself
- Gigi acts on old assumptions
- Gigi can't explain why she did something
- You feel like you're training a forgetful assistant

---

## Next: Failure Protocols

The last core piece defines what Gigi does when:
- Tools break
- Context is missing
- Instructions conflict
- Confidence is low

**This is how you prevent meltdowns.**
