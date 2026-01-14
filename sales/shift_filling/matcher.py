"""
Caregiver Matching Algorithm for Shift Filling

Scores and ranks caregivers based on:
- Prior relationship with client
- Client preferences
- Geographic proximity
- Availability and overtime status
- Performance metrics
- Response history
"""

import logging
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from .models import Shift, Caregiver, Client, CaregiverOutreach

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of caregiver matching"""
    caregiver: Caregiver
    score: float
    tier: int  # 1 = best, 2 = good, 3 = acceptable
    reasons: List[str]  # Why they were scored this way


class CaregiverMatcher:
    """
    Intelligent caregiver matching for shift filling.

    Uses a scoring algorithm that considers multiple factors
    to find the best replacement caregivers for an open shift.
    """

    # Scoring weights (total possible = 100)
    WEIGHTS = {
        "prior_client_relationship": 30,  # Worked with this client before
        "client_preference": 20,          # Client specifically requested them
        "geographic_proximity": 15,       # Lives nearby
        "availability": 10,               # Not near overtime
        "performance": 10,                # High ratings and reliability
        "response_history": 10,           # Historically responsive
        "recency_bonus": 5,               # Recently worked with client
    }

    # Tier thresholds
    TIER_1_THRESHOLD = 60  # Excellent match
    TIER_2_THRESHOLD = 40  # Good match
    # Below 40 = Tier 3 (acceptable)

    def __init__(self, wellsky_service=None):
        """
        Initialize matcher with WellSky service.

        Args:
            wellsky_service: WellSky API service (mock or real)
        """
        if wellsky_service is None:
            from .wellsky_mock import wellsky_mock
            wellsky_service = wellsky_mock
        self.wellsky = wellsky_service

    def find_replacements(self, shift: Shift, max_results: int = 20) -> List[MatchResult]:
        """
        Find and rank replacement caregivers for an open shift.

        Args:
            shift: The shift that needs to be filled
            max_results: Maximum number of candidates to return

        Returns:
            List of MatchResult sorted by score (highest first)
        """
        logger.info(f"Finding replacements for shift {shift.id} - {shift.client.full_name if shift.client else 'Unknown'}")

        # Get client
        client = shift.client
        if not client:
            client = self.wellsky.get_client(shift.client_id)
            shift.client = client

        if not client:
            logger.error(f"Could not find client for shift {shift.id}")
            return []

        # Get available caregivers (exclude original caregiver)
        exclude_ids = [shift.original_caregiver_id] if shift.original_caregiver_id else []
        available_caregivers = self.wellsky.get_available_caregivers(
            shift_date=shift.date,
            exclude_ids=exclude_ids
        )

        logger.info(f"Found {len(available_caregivers)} available caregivers for {shift.date}")

        # Score each caregiver
        results = []
        for caregiver in available_caregivers:
            score, reasons = self._calculate_match_score(caregiver, shift, client)

            # Determine tier
            if score >= self.TIER_1_THRESHOLD:
                tier = 1
            elif score >= self.TIER_2_THRESHOLD:
                tier = 2
            else:
                tier = 3

            results.append(MatchResult(
                caregiver=caregiver,
                score=score,
                tier=tier,
                reasons=reasons
            ))

        # Sort by score (highest first)
        results.sort(key=lambda x: x.score, reverse=True)

        # Limit results
        results = results[:max_results]

        logger.info(f"Matched {len(results)} caregivers. "
                   f"Tier 1: {sum(1 for r in results if r.tier == 1)}, "
                   f"Tier 2: {sum(1 for r in results if r.tier == 2)}, "
                   f"Tier 3: {sum(1 for r in results if r.tier == 3)}")

        return results

    def _calculate_match_score(self, caregiver: Caregiver, shift: Shift,
                                client: Client) -> Tuple[float, List[str]]:
        """
        Calculate match score for a caregiver-shift pair.

        Args:
            caregiver: Potential replacement caregiver
            shift: Shift to fill
            client: Client who needs care

        Returns:
            Tuple of (score 0-100, list of scoring reasons)
        """
        score = 0.0
        reasons = []

        # 1. Prior Client Relationship (+30 max)
        if client.id in caregiver.clients_worked_with:
            score += self.WEIGHTS["prior_client_relationship"]
            reasons.append(f"+{self.WEIGHTS['prior_client_relationship']}: Worked with {client.first_name} before")

        # 2. Client Preference (+20 max)
        if caregiver.id in client.preferred_caregivers:
            score += self.WEIGHTS["client_preference"]
            reasons.append(f"+{self.WEIGHTS['client_preference']}: {client.first_name}'s preferred caregiver")

        # 3. Geographic Proximity (+15 max)
        distance = self._calculate_distance(caregiver, client)
        if distance is not None:
            if distance < 10:
                prox_score = self.WEIGHTS["geographic_proximity"]
                reasons.append(f"+{prox_score}: Very close ({distance:.1f} mi)")
            elif distance < 20:
                prox_score = self.WEIGHTS["geographic_proximity"] * 0.7
                reasons.append(f"+{prox_score:.0f}: Nearby ({distance:.1f} mi)")
            elif distance < 30:
                prox_score = self.WEIGHTS["geographic_proximity"] * 0.4
                reasons.append(f"+{prox_score:.0f}: Reasonable distance ({distance:.1f} mi)")
            else:
                prox_score = 0
                reasons.append(f"+0: Far away ({distance:.1f} mi)")
            score += prox_score

        # 4. Availability / Overtime Status (+10 max)
        if caregiver.hours_available >= shift.duration_hours:
            if not caregiver.is_near_overtime:
                score += self.WEIGHTS["availability"]
                reasons.append(f"+{self.WEIGHTS['availability']}: Has {caregiver.hours_available:.0f} hrs available")
            else:
                avail_score = self.WEIGHTS["availability"] * 0.5
                score += avail_score
                reasons.append(f"+{avail_score:.0f}: Available but near overtime ({caregiver.current_weekly_hours:.0f} hrs)")
        else:
            reasons.append("+0: Would exceed weekly hours")

        # 5. Performance Metrics (+10 max)
        perf_score = 0
        if caregiver.avg_rating >= 4.5:
            perf_score += 5
        elif caregiver.avg_rating >= 4.0:
            perf_score += 3

        if caregiver.reliability_score >= 0.95:
            perf_score += 5
        elif caregiver.reliability_score >= 0.90:
            perf_score += 3

        if perf_score > 0:
            score += min(perf_score, self.WEIGHTS["performance"])
            reasons.append(f"+{min(perf_score, self.WEIGHTS['performance'])}: High performer "
                          f"(rating: {caregiver.avg_rating}, reliability: {caregiver.reliability_score*100:.0f}%)")

        # 6. Response History (+10 max)
        if caregiver.response_rate >= 0.80:
            resp_score = self.WEIGHTS["response_history"]
            reasons.append(f"+{resp_score}: Very responsive ({caregiver.response_rate*100:.0f}% response rate)")
        elif caregiver.response_rate >= 0.60:
            resp_score = self.WEIGHTS["response_history"] * 0.6
            reasons.append(f"+{resp_score:.0f}: Responsive ({caregiver.response_rate*100:.0f}% response rate)")
        else:
            resp_score = 0
            reasons.append(f"+0: Low response rate ({caregiver.response_rate*100:.0f}%)")
        score += resp_score

        # 7. Tenure Bonus (experience) - part of recency bonus
        if caregiver.tenure_days >= 365:
            score += 3
            reasons.append("+3: Experienced (1+ year tenure)")
        elif caregiver.tenure_days >= 180:
            score += 2
            reasons.append("+2: Established (6+ months tenure)")

        # Cap at 100
        score = min(score, 100)

        return score, reasons

    def _calculate_distance(self, caregiver: Caregiver, client: Client) -> Optional[float]:
        """
        Calculate approximate distance between caregiver and client.

        Uses simple lat/lon distance calculation.
        In production, use Google Maps API for accurate drive time.

        Returns:
            Distance in miles, or None if coordinates unavailable
        """
        # For POC, use city-based distance estimates
        # In production, use actual coordinates or Google Maps API

        city_distances = {
            ("Aurora", "Aurora"): 5,
            ("Aurora", "Denver"): 12,
            ("Aurora", "Centennial"): 10,
            ("Aurora", "Littleton"): 15,
            ("Aurora", "Lakewood"): 18,
            ("Aurora", "Englewood"): 12,
            ("Denver", "Denver"): 5,
            ("Denver", "Aurora"): 12,
            ("Denver", "Centennial"): 14,
            ("Denver", "Littleton"): 12,
            ("Denver", "Lakewood"): 8,
            ("Denver", "Englewood"): 8,
            ("Centennial", "Centennial"): 5,
            ("Centennial", "Aurora"): 10,
            ("Centennial", "Denver"): 14,
            ("Centennial", "Littleton"): 8,
            ("Centennial", "Lakewood"): 15,
            ("Centennial", "Englewood"): 6,
            ("Littleton", "Littleton"): 5,
            ("Littleton", "Denver"): 12,
            ("Littleton", "Aurora"): 15,
            ("Littleton", "Centennial"): 8,
            ("Littleton", "Lakewood"): 10,
            ("Littleton", "Englewood"): 6,
            ("Lakewood", "Lakewood"): 5,
            ("Lakewood", "Denver"): 8,
            ("Lakewood", "Aurora"): 18,
            ("Lakewood", "Centennial"): 15,
            ("Lakewood", "Littleton"): 10,
            ("Lakewood", "Englewood"): 8,
            ("Englewood", "Englewood"): 5,
            ("Englewood", "Denver"): 8,
            ("Englewood", "Aurora"): 12,
            ("Englewood", "Centennial"): 6,
            ("Englewood", "Littleton"): 6,
            ("Englewood", "Lakewood"): 8,
        }

        cg_city = caregiver.city
        client_city = client.city

        # Try direct lookup
        key = (cg_city, client_city)
        if key in city_distances:
            return city_distances[key]

        # Try reverse
        key_rev = (client_city, cg_city)
        if key_rev in city_distances:
            return city_distances[key_rev]

        # Default estimate
        return 15.0

    def create_outreach_list(self, matches: List[MatchResult]) -> List[CaregiverOutreach]:
        """
        Convert match results to outreach objects.

        Args:
            matches: List of MatchResult from find_replacements

        Returns:
            List of CaregiverOutreach ready for SMS sending
        """
        outreach_list = []

        for match in matches:
            outreach = CaregiverOutreach(
                caregiver_id=match.caregiver.id,
                caregiver=match.caregiver,
                phone=match.caregiver.phone,
                match_score=match.score,
                tier=match.tier
            )
            outreach_list.append(outreach)

        return outreach_list
