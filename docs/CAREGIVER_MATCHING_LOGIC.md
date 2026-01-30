# Caregiver Matching Engine - "Continuity-First" Logic

**Document Version:** 1.0
**Date:** January 30, 2026

## 1. Core Principle
The matching engine's primary goal is **Continuity of Care > Coverage > Convenience**. It is explicitly designed to prevent the "just fill the shift" anti-pattern. The engine prioritizes client safety and familiarity above all other metrics.

## 2. Decision Hierarchy
When ranking caregivers for a shift, the engine scores them in this strict order:

1.  **Hard Filters (Disqualification):** Non-negotiable rules that remove a candidate.
2.  **Continuity & Familiarity Scoring:** Massive bonuses for caregivers who know the client.
3.  **Safety & Skill Scoring:** Bonuses for critical skill matches, weighted by urgency.
4.  **Convenience Scoring:** Minor bonuses for proximity or penalties for overtime risk.

---

## 3. The Algorithm

### Step 1: Urgency Classification
The engine first classifies the shift's urgency based on keywords found in the shift notes, tasks, or the client's care plan.

-   **CRITICAL:** Triggers if keywords like `transfer`, `meds`, `dementia`, `hospice`, `fall risk` are present.
-   **IMPORTANT:** Triggers for ADLs like `bath`, `hygiene`, `meal prep`.
-   **FLEXIBLE:** Default for companionship or low-risk tasks.

### Step 2: Hard Filters (Exclusion)
The engine will immediately **disqualify** a caregiver if:
-   They are on the client's "Do Not Send" list in WellSky.
-   The client has a "Familiarity Only" rule and the caregiver has never worked with them.
-   The client has a gender preference (e.g., "female caregivers only") that is not met.
-   The caregiver has a direct schedule conflict (checked via WellSky).
-   **For CRITICAL shifts:** The caregiver lacks essential qualifications (e.g., a "dementia" shift requires a caregiver with a "dementia care" certification or proven history with the client).

### Step 3: Weighted Scoring
If a caregiver passes the hard filters, they are scored based on the following weights:

| Factor | Weight | Notes |
| :--- | :--- | :--- |
| **Preferred Caregiver** | `+100` | Highest possible score. The client's core team. |
| **Worked Before** | `+75` | Has a history with the client. The most important factor after "Preferred". |
| **Critical Skill Match** | `+50` | Matches a CRITICAL shift's needs (e.g., has "Dementia Care" cert). |
| **Proximity (< 5 miles)** | `+20` | Minor convenience bonus. **Intentionally low** to prevent it from outranking familiarity. |
| **Proximity (< 10 miles)** | `+10` | |
| **Overtime Risk** | `-10` | Minor penalty if the shift would push them over 40 hours. Not a hard filter. |

*A "Familiar but Far" caregiver (75 points) will always outrank a "Stranger but Close" caregiver (20 points).*

### Step 4: Tiering & Outreach
Based on the final score, caregivers are grouped into Tiers for the SMS outreach:

-   **Tier A (Score > 70):** The "Core Team." These are the client's preferred and most familiar caregivers. They are contacted **first**, individually or in a small group.
-   **Tier B (Score > 30):** "Qualified & Nearby." Good matches who are qualified but may not have a deep history with the client. Contacted if Tier A doesn't respond.
-   **Tier C:** "General Pool." Contacted only for CRITICAL shifts if no one from Tiers A or B is available.

---

## 4. Integration
This logic is implemented in `services/caregiver_matching_engine.py` and is called by the `execute_caregiver_call_out` and `handle_inbound_sms` functions in `gigi/main.py`. This ensures both voice and text call-outs use the same intelligent, safe, and human-centric logic.
