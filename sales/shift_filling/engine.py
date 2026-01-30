"""
Shift Filling Engine - Main Orchestrator

Coordinates the entire shift filling process:
1. Receives calloff notifications
2. Finds qualified replacement caregivers
3. Sends parallel SMS outreach
4. Handles responses and selects winner
5. Assigns shift and notifies all parties
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable

from .models import (
    Shift, Caregiver, Client, ShiftOutreach, CaregiverOutreach,
    OutreachStatus, CaregiverResponseType
)
from .matcher import CaregiverMatcher, MatchResult
from .sms_service import sms_service, SMSService
from .db_lock import ShiftAssignmentLock, ShiftLockConflictError, ShiftLockDatabaseError

logger = logging.getLogger(__name__)


class ShiftFillingEngine:
    """
    AI-Powered Shift Filling Engine.

    Automatically finds and assigns replacement caregivers
    when shifts become open due to calloffs.
    """

    def __init__(
        self,
        wellsky_service=None,
        sms_service: SMSService = None,
        on_shift_filled: Callable = None,
        on_escalation: Callable = None
    ):
        """
        Initialize the shift filling engine.

        Args:
            wellsky_service: WellSky API service (or mock)
            sms_service: SMS service for outreach
            on_shift_filled: Callback when shift is successfully filled
            on_escalation: Callback when shift needs manual intervention
        """
        if wellsky_service is None:
            from .wellsky_mock import wellsky_mock
            wellsky_service = wellsky_mock

        self.wellsky = wellsky_service
        self.matcher = CaregiverMatcher(wellsky_service)
        self.sms = sms_service or globals()['sms_service']

        # Callbacks
        self.on_shift_filled = on_shift_filled
        self.on_escalation = on_escalation

        # Active outreach campaigns
        self.active_campaigns: Dict[str, ShiftOutreach] = {}

        # Database lock for preventing race conditions
        try:
            self.shift_lock = ShiftAssignmentLock()
            logger.info("ShiftFillingEngine initialized with database locking enabled")
        except ValueError as e:
            logger.warning(f"Database locking disabled: {e}")
            self.shift_lock = None
            logger.info("ShiftFillingEngine initialized WITHOUT database locking (race conditions possible)")

    def process_calloff(
        self,
        shift_id: str,
        caregiver_id: str,
        reason: str = "",
        reported_by: str = "system"
    ) -> ShiftOutreach:
        """
        Process a caregiver calloff and initiate shift filling.

        This is the main entry point when a caregiver calls off.

        Args:
            shift_id: ID of the shift being called off
            caregiver_id: ID of caregiver who called off
            reason: Reason for calloff (optional)
            reported_by: Who reported the calloff

        Returns:
            ShiftOutreach campaign object
        """
        logger.info(f"Processing calloff for shift {shift_id} by caregiver {caregiver_id}")

        # 1. Record the calloff in WellSky
        shift = self.wellsky.create_calloff(
            shift_id=shift_id,
            caregiver_id=caregiver_id,
            reason=reason
        )

        if not shift:
            logger.error(f"Could not find shift {shift_id}")
            return None

        # 2. Create outreach campaign
        campaign = ShiftOutreach(
            shift_id=shift_id,
            shift=shift,
            status=OutreachStatus.IN_PROGRESS,
            started_at=datetime.now()
        )

        # 3. Find replacement caregivers
        matches = self.matcher.find_replacements(shift)

        if not matches:
            logger.warning(f"No available caregivers found for shift {shift_id}")
            self._escalate_campaign(campaign, "No available caregivers")
            return campaign

        # 4. Start parallel outreach
        self._initiate_outreach(campaign, matches)

        # 5. Store campaign
        self.active_campaigns[campaign.id] = campaign

        logger.info(f"Calloff processed. Campaign {campaign.id} started with {campaign.total_contacted} caregivers")
        return campaign

    def _initiate_outreach(
        self,
        campaign: ShiftOutreach,
        matches: List[MatchResult]
    ) -> None:
        """
        Send SMS offers to matched caregivers.

        Sends to Tier 1 caregivers first, then Tier 2, etc.
        """
        shift = campaign.shift

        # Start with top tier matches
        tier1_matches = [m for m in matches if m.tier == 1]
        tier2_matches = [m for m in matches if m.tier == 2]
        tier3_matches = [m for m in matches if m.tier == 3]

        # Send to Tier 1 first (best matches)
        contacts_to_send = tier1_matches[:10]  # Max 10 tier 1

        if len(contacts_to_send) < 5:
            # Add tier 2 if not enough tier 1
            contacts_to_send.extend(tier2_matches[:10 - len(contacts_to_send)])

        logger.info(f"Initiating outreach to {len(contacts_to_send)} caregivers "
                   f"(Tier1: {len([m for m in contacts_to_send if m.tier == 1])}, "
                   f"Tier2: {len([m for m in contacts_to_send if m.tier == 2])})")

        # Send SMS offers
        for match in contacts_to_send:
            outreach = self.sms.send_shift_offer(shift, match.caregiver)
            outreach.match_score = match.score
            outreach.tier = match.tier
            campaign.add_caregiver_outreach(outreach)

        # Store remaining matches for potential second wave
        campaign._pending_matches = tier2_matches[10:] + tier3_matches

    def process_response(
        self,
        campaign_id: str,
        phone: str,
        message_text: str
    ) -> Dict[str, Any]:
        """
        Process an incoming SMS response from a caregiver.

        Args:
            campaign_id: ID of the active campaign
            phone: Phone number of responder
            message_text: The response message text

        Returns:
            Dict with response handling result
        """
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            logger.warning(f"No active campaign found: {campaign_id}")
            return {"success": False, "error": "Campaign not found"}

        # Find the matching outreach
        outreach = None
        for o in campaign.caregivers_contacted:
            if self._phones_match(o.phone, phone):
                outreach = o
                break

        if not outreach:
            logger.warning(f"No outreach found for phone {phone} in campaign {campaign_id}")
            return {"success": False, "error": "Outreach not found"}

        # Parse the response
        response_type = self.sms.parse_response(message_text)

        # Record the response
        campaign.record_response(
            caregiver_id=outreach.caregiver_id,
            response_type=response_type,
            response_text=message_text
        )

        logger.info(f"Response from {outreach.caregiver.full_name}: {response_type.value}")

        # Handle based on response type
        if response_type == CaregiverResponseType.ACCEPTED:
            return self._handle_acceptance(campaign, outreach)

        elif response_type == CaregiverResponseType.DECLINED:
            return self._handle_decline(campaign, outreach)

        elif response_type == CaregiverResponseType.AMBIGUOUS:
            return self._handle_ambiguous(campaign, outreach, message_text)

        return {"success": True, "response_type": response_type.value}

    def _handle_acceptance(
        self,
        campaign: ShiftOutreach,
        outreach: CaregiverOutreach
    ) -> Dict[str, Any]:
        """
        Handle a caregiver accepting a shift.

        Uses database-level locking to prevent race condition where two caregivers
        accept the same shift simultaneously.
        """
        shift = campaign.shift
        caregiver = outreach.caregiver

        # Acquire database lock for this specific shift
        # This prevents race condition where two caregivers accept at the same time
        if self.shift_lock:
            try:
                with self.shift_lock.acquire_shift_lock(shift.id):
                    # Inside lock: only ONE process can execute this block at a time
                    # for this specific shift

                    # Double-check shift is still available (another process might have filled it)
                    if campaign.status == OutreachStatus.FILLED:
                        logger.info(f"Shift {shift.id} already filled (race condition avoided)")
                        self.sms.send_shift_filled_notification(caregiver, shift)
                        return {
                            "success": True,
                            "action": "already_filled",
                            "message": "Shift was already filled by another caregiver"
                        }

                    # First acceptance wins!
                    logger.info(f"Lock acquired for shift {shift.id}, assigning to {caregiver.full_name}")

                    # 1. Mark winner in campaign
                    campaign.mark_winner(caregiver.id)

                    # 2. Assign in WellSky
                    self.wellsky.assign_shift(shift.id, caregiver.id)

                    # 3. Send confirmation to winner
                    self.sms.send_confirmation(caregiver, shift)

                    # 4. Notify others that shift is filled
                    for other_outreach in campaign.caregivers_contacted:
                        if other_outreach.caregiver_id != caregiver.id:
                            if other_outreach.response_type == CaregiverResponseType.NO_RESPONSE:
                                # Don't notify those who haven't responded yet
                                pass
                            else:
                                self.sms.send_shift_filled_notification(other_outreach.caregiver, shift)

                    # 5. Trigger callback
                    if self.on_shift_filled:
                        self.on_shift_filled(campaign, caregiver)

                    logger.info(f"Shift {shift.id} successfully filled by {caregiver.full_name}")

                    return {
                        "success": True,
                        "action": "shift_filled",
                        "assigned_caregiver": caregiver.full_name,
                        "caregiver_id": caregiver.id,
                        "match_score": outreach.match_score
                    }
                # Lock automatically released here

            except ShiftLockConflictError as e:
                # Another process is currently assigning this shift
                logger.warning(f"Lock conflict for shift {shift.id}: {e}")
                return {
                    "success": False,
                    "action": "lock_conflict",
                    "message": "Another caregiver is being assigned to this shift right now. Please try again in a moment."
                }

            except ShiftLockDatabaseError as e:
                # Database connection failed - fall back to unlocked assignment
                logger.error(f"Database locking failed for shift {shift.id}: {e}")
                logger.warning("Proceeding with assignment WITHOUT lock (race condition possible)")
                # Fall through to unlocked code below

        # Fallback: No locking available (development mode or database error)
        logger.warning(f"Processing shift {shift.id} acceptance WITHOUT database lock (race conditions possible)")

        # Check if shift is already filled
        if campaign.status == OutreachStatus.FILLED:
            self.sms.send_shift_filled_notification(caregiver, shift)
            return {
                "success": True,
                "action": "already_filled",
                "message": "Shift was already filled"
            }

        # First acceptance wins!
        campaign.mark_winner(caregiver.id)
        self.wellsky.assign_shift(shift.id, caregiver.id)
        self.sms.send_confirmation(caregiver, shift)

        # Notify others
        for other_outreach in campaign.caregivers_contacted:
            if other_outreach.caregiver_id != caregiver.id:
                if other_outreach.response_type != CaregiverResponseType.NO_RESPONSE:
                    self.sms.send_shift_filled_notification(other_outreach.caregiver, shift)

        if self.on_shift_filled:
            self.on_shift_filled(campaign, caregiver)

        logger.info(f"Shift {shift.id} filled by {caregiver.full_name}")

        return {
            "success": True,
            "action": "shift_filled",
            "assigned_caregiver": caregiver.full_name,
            "caregiver_id": caregiver.id,
            "match_score": outreach.match_score
        }

    def _handle_decline(
        self,
        campaign: ShiftOutreach,
        outreach: CaregiverOutreach
    ) -> Dict[str, Any]:
        """Handle a caregiver declining a shift."""

        # Check if we need to send more outreach
        remaining_pending = sum(
            1 for o in campaign.caregivers_contacted
            if o.response_type == CaregiverResponseType.NO_RESPONSE
        )

        logger.info(f"{outreach.caregiver.full_name} declined. {remaining_pending} still pending.")

        # If too few pending, send second wave
        if remaining_pending < 3 and hasattr(campaign, '_pending_matches'):
            pending_matches = campaign._pending_matches[:5]
            if pending_matches:
                logger.info(f"Sending second wave to {len(pending_matches)} more caregivers")
                for match in pending_matches:
                    new_outreach = self.sms.send_shift_offer(campaign.shift, match.caregiver)
                    new_outreach.match_score = match.score
                    new_outreach.tier = match.tier
                    campaign.add_caregiver_outreach(new_outreach)
                campaign._pending_matches = campaign._pending_matches[5:]

        return {
            "success": True,
            "action": "decline_recorded",
            "remaining_pending": remaining_pending
        }

    def _handle_ambiguous(
        self,
        campaign: ShiftOutreach,
        outreach: CaregiverOutreach,
        message_text: str
    ) -> Dict[str, Any]:
        """Handle an ambiguous response that needs clarification."""

        # Send clarification request
        clarification_msg = (
            f"Thanks for responding! To confirm, are you AVAILABLE for the shift on "
            f"{campaign.shift.date.strftime('%b %d')} at {campaign.shift.to_display_time()}?\n\n"
            f"Reply YES to accept or NO to decline."
        )

        self.sms.send_sms(outreach.phone, clarification_msg)

        return {
            "success": True,
            "action": "clarification_sent",
            "original_message": message_text
        }

    def _escalate_campaign(
        self,
        campaign: ShiftOutreach,
        reason: str
    ) -> None:
        """Escalate a campaign that couldn't be filled automatically."""

        campaign.status = OutreachStatus.ESCALATED
        campaign.escalated_at = datetime.now()
        campaign.escalation_reason = reason

        logger.warning(f"Campaign {campaign.id} escalated: {reason}")

        if self.on_escalation:
            self.on_escalation(campaign)

    def check_campaign_timeouts(self) -> List[ShiftOutreach]:
        """
        Check for campaigns that have timed out.

        Called periodically to escalate stale campaigns.

        Returns:
            List of escalated campaigns
        """
        escalated = []
        now = datetime.now()

        for campaign_id, campaign in list(self.active_campaigns.items()):
            if campaign.status != OutreachStatus.IN_PROGRESS:
                continue

            # Check timeout
            elapsed_minutes = (now - campaign.started_at).total_seconds() / 60
            if elapsed_minutes > campaign.timeout_minutes:
                # Check if anyone accepted
                if campaign.total_accepted == 0:
                    self._escalate_campaign(campaign, "Timeout - no acceptances")
                    escalated.append(campaign)

        return escalated

    def _phones_match(self, phone1: str, phone2: str) -> bool:
        """Check if two phone numbers match (ignoring formatting)."""
        import re
        clean1 = re.sub(r'[^\d]', '', phone1)[-10:]
        clean2 = re.sub(r'[^\d]', '', phone2)[-10:]
        return clean1 == clean2 and len(clean1) >= 10

    def get_campaign_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an active campaign."""
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            return None

        return campaign.to_dict()

    def get_all_active_campaigns(self) -> List[Dict[str, Any]]:
        """Get all active campaigns."""
        return [
            c.to_dict() for c in self.active_campaigns.values()
            if c.status == OutreachStatus.IN_PROGRESS
        ]

    def simulate_demo(self) -> Dict[str, Any]:
        """
        Run a demonstration of the shift filling process.

        Uses mock data to show the complete flow.
        """
        logger.info("Starting shift filling demonstration...")

        # Get a sample open shift
        shifts = self.wellsky.get_open_shifts()
        if not shifts:
            return {"success": False, "error": "No open shifts available"}

        shift = shifts[0]
        logger.info(f"Demo shift: {shift.id} for {shift.client.full_name if shift.client else 'Unknown'}")

        # Find replacements
        matches = self.matcher.find_replacements(shift)

        # Create campaign
        campaign = ShiftOutreach(
            shift_id=shift.id,
            shift=shift,
            status=OutreachStatus.IN_PROGRESS,
            started_at=datetime.now()
        )

        # Send offers to top 5 matches
        for match in matches[:5]:
            outreach = self.sms.send_shift_offer(shift, match.caregiver)
            outreach.match_score = match.score
            outreach.tier = match.tier
            campaign.add_caregiver_outreach(outreach)

        self.active_campaigns[campaign.id] = campaign

        # Simulate first response (acceptance)
        if matches:
            first_caregiver = matches[0].caregiver
            self.process_response(
                campaign_id=campaign.id,
                phone=first_caregiver.phone,
                message_text="Yes, I can take it!"
            )

        return {
            "success": True,
            "campaign_id": campaign.id,
            "shift": {
                "id": shift.id,
                "client": shift.client.full_name if shift.client else "Unknown",
                "date": shift.date.isoformat(),
                "time": shift.to_display_time()
            },
            "matches_found": len(matches),
            "caregivers_contacted": campaign.total_contacted,
            "campaign_status": campaign.status.value,
            "winner": campaign.winning_caregiver.full_name if campaign.winning_caregiver else None
        }


# Default engine instance
shift_filling_engine = ShiftFillingEngine()
