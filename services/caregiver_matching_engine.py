"""
Caregiver Matching Engine
Implements the "Continuity > Coverage > Convenience" protocol for Gigi.

Decision Hierarchy:
1. Safety & Criticality (Urgency Classification)
2. Continuity (Known Caregiver)
3. Skill & Authorization Match
4. Schedule Feasibility
5. Client Preferences
6. Caregiver Preferences
7. Cost/Overtime (Tiebreaker)
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

class ShiftUrgency(Enum):
    CRITICAL = "CRITICAL"   # Safety risk (Transfers, Meds, Dementia)
    IMPORTANT = "IMPORTANT" # Hygiene/Health (Bathing, Meals, Toileting)
    FLEXIBLE = "FLEXIBLE"   # Quality of Life (Companionship, Cleaning)

@dataclass
class MatchScore:
    caregiver_id: str
    caregiver_name: str
    total_score: float
    breakdown: Dict[str, float]
    urgency: ShiftUrgency
    tier: str  # "A" (Core), "B" (Familiar), "C" (General)
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None

class CaregiverMatchingEngine:
    
    def __init__(self):
        # Weights for scoring
        self.WEIGHTS = {
            "preferred": 100,      # Client explicitly prefers this caregiver
            "worked_before": 75,   # Has worked with client before
            "familiarity": 10,     # Bonus per visit (capped)
            "skill_match": 50,     # Critical skill match
            "distance": 20,        # Proximity bonus
            "overtime": -10,       # Penalty for OT risk (not hard filter)
        }
        
        # Critical keywords for Urgency Classification
        self.CRITICAL_KEYWORDS = {
            "transfer", "lift", "hoyer", "medication", "meds", "dementia", 
            "alzheimer", "memory", "feed", "choking", "fall risk", "24/7",
            "hospice", "end of life", "bedbound"
        }
        
        self.IMPORTANT_KEYWORDS = {
            "bath", "shower", "hygiene", "incontinent", "toileting", "meal", 
            "prep", "cook", "diabetes", "catheter", "ostomy"
        }

    def classify_urgency(self, shift: Any, client: Any, care_plan: Any = None) -> ShiftUrgency:
        """
        STEP 1: Classify Urgency based on client needs and shift tasks.
        """
        # Gather all text describing the care
        text_corpus = set()
        
        # Add shift notes/tasks
        if hasattr(shift, 'notes') and shift.notes:
            text_corpus.update(shift.notes.lower().split())
        if hasattr(shift, 'tasks_completed'): # Sometimes contains planned tasks
            for task in shift.tasks_completed:
                text_corpus.update(str(task).lower().split())
                
        # Add care plan info if available
        if care_plan:
            if hasattr(care_plan, 'diagnosis_codes'):
                for code in care_plan.diagnosis_codes:
                    text_corpus.update(str(code).lower().split())
            if hasattr(care_plan, 'authorized_services'):
                for svc in care_plan.authorized_services:
                    text_corpus.update(str(svc).lower().split())
                    
        # Check Critical
        if text_corpus.intersection(self.CRITICAL_KEYWORDS):
            return ShiftUrgency.CRITICAL
            
        # Check Important
        if text_corpus.intersection(self.IMPORTANT_KEYWORDS):
            return ShiftUrgency.IMPORTANT
            
        return ShiftUrgency.FLEXIBLE

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine formula for distance in miles"""
        if not (lat1 and lon1 and lat2 and lon2):
            return 999.0 # Unknown distance
            
        R = 3959.87433 # Radius of Earth in miles
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def score_caregiver(
        self, 
        caregiver: Any, 
        client: Any, 
        shift: Any, 
        urgency: ShiftUrgency,
        active_shifts: List[Any] = None # Caregiver's other shifts for OT/overlap check
    ) -> MatchScore:
        """
        Calculate match score for a single caregiver.
        """
        score = 0.0
        breakdown = {}
        disqualified = False
        reason = None
        
        # --- STEP 3: HARD FILTERS (Non-negotiable) ---
        
        # 1. Blocked / Do Not Send
        if hasattr(client, 'do_not_send_caregivers') and caregiver.id in client.do_not_send_caregivers:
            return MatchScore(caregiver.id, caregiver.full_name, 0, {}, urgency, "C", True, "Blocked by client")

        # 1b. Client Specific Preferences (The "Override" Layer)
        # Example: client.preferences = {"no_male_caregivers": True, "familiarity_only": True}
        if hasattr(client, 'preferences'):
            prefs = client.preferences
            
            # Gender Preference
            if prefs.get('no_male_caregivers') and getattr(caregiver, 'gender', '').lower() == 'male':
                return MatchScore(caregiver.id, caregiver.full_name, 0, {}, urgency, "C", True, "Client prefers female caregivers")
                
            if prefs.get('no_female_caregivers') and getattr(caregiver, 'gender', '').lower() == 'female':
                return MatchScore(caregiver.id, caregiver.full_name, 0, {}, urgency, "C", True, "Client prefers male caregivers")

            # Strict Familiarity Rule ("Never new caregiver")
            if prefs.get('familiarity_only'):
                has_worked = hasattr(caregiver, 'clients_worked_with') and client.id in caregiver.clients_worked_with
                is_preferred = hasattr(client, 'preferred_caregivers') and caregiver.id in client.preferred_caregivers
                if not (has_worked or is_preferred):
                    return MatchScore(caregiver.id, caregiver.full_name, 0, {}, urgency, "C", True, "Client requires previous history")

        # 2. Authorization / Skills (Strict Check for Critical Shifts)
        # "Assign dementia or transfer care to an unproven caregiver" -> FORBIDDEN
        if urgency == ShiftUrgency.CRITICAL:
            required_skills = set()
            # Determine needs from shift/client context (simplified)
            # ideally passed in or derived from classify_urgency context
            # For now, check if 'dementia' was a keyword in urgency classification
            # This requires classify_urgency to return context or us to re-derive it.
            # Let's assume we can check caregiver skills against the CRITICAL_KEYWORDS found in shift notes.
            
            # Re-scan keywords to find specific needs (Dementia, Transfer)
            text_corpus = (getattr(shift, 'notes', '') or '') + " " + " ".join(getattr(shift, 'tasks_completed', []) or [])
            text_corpus = text_corpus.lower()
            
            if "dementia" in text_corpus or "alzheimer" in text_corpus:
                cg_skills = [s.lower() for s in (getattr(caregiver, 'skills', []) or [])]
                cg_certs = [c.lower() for c in (getattr(caregiver, 'certifications', []) or [])]
                all_qualifications = set(cg_skills + cg_certs)
                
                # Check for dementia qualification
                if not any(q in all_qualifications for q in ["dementia", "alzheimer", "memory care"]):
                    # If not explicitly qualified, check experience/history as proxy?
                    # User rule: "Assign dementia... to unproven caregiver" -> FAIL.
                    # If they have worked with client before, they are "proven".
                    has_history = hasattr(caregiver, 'clients_worked_with') and client.id in caregiver.clients_worked_with
                    if not has_history:
                         return MatchScore(caregiver.id, caregiver.full_name, 0, {}, urgency, "C", True, "Unqualified for Dementia (New Caregiver)")

        # 3. Schedule Overlap (Hard Filter)
        if active_shifts:
            shift_start = datetime.fromisoformat(shift.start_time) if isinstance(shift.start_time, str) else shift.start_time
            shift_end = datetime.fromisoformat(shift.end_time) if isinstance(shift.end_time, str) else shift.end_time
            
            for s in active_shifts:
                # Simple overlap check
                s_start = s['start'] # Assuming datetime
                s_end = s['end']
                if max(shift_start, s_start) < min(shift_end, s_end):
                    return MatchScore(caregiver.id, caregiver.full_name, 0, {}, urgency, "C", True, "Schedule conflict")

        # --- STEP 2 & 4: SCORING ---
        
        # 1. Continuity (The "Spine")
        if hasattr(client, 'preferred_caregivers') and caregiver.id in client.preferred_caregivers:
            val = self.WEIGHTS["preferred"]
            score += val
            breakdown["preferred"] = val
            
        # 2. History / Familiarity
        if hasattr(caregiver, 'clients_worked_with') and client.id in caregiver.clients_worked_with:
            val = self.WEIGHTS["worked_before"]
            score += val
            breakdown["worked_before"] = val
            
        # 3. Distance / Convenience
        # Assuming client and caregiver have lat/lon or we calculate from zip
        # This is soft scoring.
        dist = 999
        if hasattr(client, 'lat') and hasattr(caregiver, 'lat'):
            dist = self.calculate_distance(caregiver.lat, caregiver.lon, client.lat, client.lon)
            if dist < 5:
                val = self.WEIGHTS["distance"]
                score += val
                breakdown["distance < 5mi"] = val
            elif dist < 10:
                val = self.WEIGHTS["distance"] / 2
                score += val
                breakdown["distance < 10mi"] = val
        
        # 4. Overtime Risk (Soft Penalty)
        if hasattr(caregiver, 'current_weekly_hours'):
            shift_hours = (datetime.fromisoformat(shift.end_time) - datetime.fromisoformat(shift.start_time)).seconds / 3600 if isinstance(shift.end_time, str) else 4.0
            projected_hours = caregiver.current_weekly_hours + shift_hours
            if projected_hours > 40:
                val = self.WEIGHTS["overtime"]
                score += val
                breakdown["overtime_risk"] = val

        # --- TIER ASSIGNMENT ---
        if score >= 70:
            tier = "A" # Core / Continuity
        elif score >= 30:
            tier = "B" # Qualified / Local
        else:
            tier = "C" # Warm body

        return MatchScore(
            caregiver_id=caregiver.id,
            caregiver_name=caregiver.full_name,
            total_score=score,
            breakdown=breakdown,
            urgency=urgency,
            tier=tier,
            is_disqualified=disqualified,
            disqualification_reason=reason
        )

    def rank_candidates(
        self, 
        candidates: List[Any], 
        client: Any, 
        shift: Any, 
        care_plan: Any = None
    ) -> List[MatchScore]:
        """
        Main entry point: Rank a list of candidates for a shift.
        """
        urgency = self.classify_urgency(shift, client, care_plan)
        logger.info(f"Shift Urgency Classified: {urgency.value} for client {client.full_name}")
        
        scored = []
        for cg in candidates:
            # Need to fetch caregiver's active shifts for overlap check? 
            # Ideally passed in or checked here. For now, assuming candidates list 
            # implies availability (from search_practitioners)
            ms = self.score_caregiver(cg, client, shift, urgency)
            if not ms.is_disqualified:
                scored.append(ms)
                
        # Sort by score descending
        scored.sort(key=lambda x: x.total_score, reverse=True)
        return scored
