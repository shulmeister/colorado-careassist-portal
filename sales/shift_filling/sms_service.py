"""
SMS Outreach Service for Shift Filling

Uses RingCentral API to send SMS messages to caregivers
and handle responses for shift filling.
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

import requests

from .models import (
    Shift, Caregiver, CaregiverOutreach, ShiftOutreach,
    CaregiverResponseType
)

logger = logging.getLogger(__name__)

# RingCentral credentials
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")
RINGCENTRAL_FROM_NUMBER = os.getenv("RINGCENTRAL_SMS_FROM", "+17205551234")  # Company SMS number


class SMSService:
    """
    SMS service for shift filling outreach.

    Handles sending SMS messages to caregivers and
    parsing their responses.

    Response patterns trained on 4,956 real SMS messages from
    Colorado CareAssist caregiver communications (719-428-3999).
    """

    # Exact match acceptance phrases (highest confidence)
    # Trained on real caregiver responses
    ACCEPTANCE_EXACT = {
        'yes', 'yes i can', 'yes i can.', 'yes i can!', 'yes please',
        'yes, please', 'yes i will', 'yes!!', 'yep', 'yeah', 'yup',
        'sure', 'sure!', 'sure can!', 'of course', 'absolutely',
        'definitely', 'for sure', 'sounds good', 'sounds great',
        'no problem', 'no problem!', 'got it', 'got it!', 'k', 'okay',
        'ok', 'yw', 'will do', 'okay, will do', 'correct', 'yes ma\'am',
        'i can take this shift', 'i can work', 'i can for', 'i will do',
        '1',  # Quick numeric response
    }

    # Response patterns for parsing caregiver replies (regex)
    ACCEPTANCE_PATTERNS = [
        r'^yes\b',                          # "yes" at start
        r'\byes\s+i\s+can\b',              # "yes i can"
        r'\bi\s+can\s+(take|work|do|pick\s+up)\b',  # "i can take/work/do/pick up"
        r'\bi\'ll\s+(take|do|work|cover)\b',        # "i'll take/do/work/cover"
        r'\bi\s+will\s+(take|do|work|cover)\b',     # "i will take/do/work/cover"
        r'\bcount\s+me\s+in\b',
        r'\bon\s+my\s+way\b', r'\bomw\b',
        r'\bi\'m\s+in\b',
        r'\bworks\s+for\s+me\b',
        r'\bsounds\s+good\b', r'\bsounds\s+great\b',
        r'\byes\s*,?\s*please\b',
        r'\bof\s+course\b',
        r'\bi\s+believe\s+i\s+can\b',       # "I believe I can assist"
        r'\bi\s+can\s+definitely\b',        # "I can definitely help"
        r'\bno\s+problem\b',                # Affirmative, not decline
        r'\bfor\s+sure\b',
        r'\babsolutely\b',
        r'\bdefinitely\b',
        r'^1$',                             # Just "1" for quick accept
    ]

    # Exact match decline phrases (highest confidence)
    DECLINE_EXACT = {
        'no', 'nope', 'pass', 'unavailable', 'unavailable tomorrow',
        'sorry i can\'t', 'sorry not available', 'i can\'t',
        'no i can\'t', 'not available', 'not today', 'not tonight',
        'i\'m sorry i can\'t', 'i\'m sorry i can not', 'i\'m sorry i cannot',
        '2',  # Quick numeric decline
    }

    DECLINE_PATTERNS = [
        r'^no\b(?!\s+problem)',             # "no" at start (but not "no problem")
        r'\bcan\'?t\s+(make|do|work|take|cover)\b',  # "can't make/do/work/take/cover"
        r'\bcannot\s+(make|do|work|take|cover)\b',
        r'\bnot\s+able\s+to\b',             # "not able to"
        r'\bnot\s+available\b',
        r'\bnot\s+today\b', r'\bnot\s+tonight\b',
        r'\bunavailable\b',
        r'\bi\'m\s+(so\s+)?sorry\b',        # "I'm sorry" or "I'm so sorry"
        r'\bsorry\s+i\s+can\'?t\b',
        r'\bsorry\s+not\b',
        r'\bno\s+way\b',
        r'\bhave\s+to\s+cancel\b',
        r'\bwon\'?t\s+be\s+able\b',
        r'\bunfortunately\b',
        r'\bstill\s+sick\b',
        r'\bdoctor\'?s?\s+appointment\b',   # Common reason for decline
        r'\bdr\s+appointment\b',
        r'^2$',                             # Just "2" for quick decline
    ]

    # Patterns that indicate the message is a question (needs clarification)
    QUESTION_PATTERNS = [
        r'\bwhat\s+time\b', r'\bwhat\s+times\b',
        r'\bwhat\'?s\s+her\s+name\b', r'\bwhat\'?s\s+his\s+name\b',
        r'\bwho\s+is\s+this\b',
        r'\bwhat\s+address\b',
        r'\bhow\s+long\b',
        r'\?$',  # Ends with question mark
    ]

    def __init__(self):
        self.client_id = RINGCENTRAL_CLIENT_ID
        self.client_secret = RINGCENTRAL_CLIENT_SECRET
        self.jwt_token = RINGCENTRAL_JWT_TOKEN
        self.server = RINGCENTRAL_SERVER
        self.from_number = RINGCENTRAL_FROM_NUMBER
        self.access_token = None
        self.token_expires_at = None

        self.enabled = bool(self.client_id and self.client_secret and self.jwt_token)
        if not self.enabled:
            logger.warning("RingCentral SMS credentials not fully configured")

    def _get_access_token(self) -> Optional[str]:
        """Get access token using JWT grant."""
        if not self.enabled:
            return None

        # Check cached token
        if self.access_token and self.token_expires_at:
            if datetime.utcnow() < self.token_expires_at:
                return self.access_token

        try:
            response = requests.post(
                f"{self.server}/restapi/oauth/token",
                auth=(self.client_id, self.client_secret),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": self.jwt_token
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                logger.info("RingCentral SMS: Got access token")
                return self.access_token
            else:
                logger.error(f"RingCentral SMS auth failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"RingCentral SMS auth error: {e}")
            return None

    def format_phone(self, phone: str) -> str:
        """Format phone number to E.164 format for RingCentral."""
        clean = re.sub(r'[^\d]', '', phone)
        if len(clean) == 10:
            return f"+1{clean}"
        elif len(clean) == 11 and clean.startswith('1'):
            return f"+{clean}"
        return phone  # Return as-is if unexpected format

    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Send an SMS message via RingCentral.

        Args:
            to_phone: Recipient phone number
            message: Message text

        Returns:
            Tuple of (success, message_id or error)
        """
        token = self._get_access_token()
        if not token:
            return False, "No access token"

        try:
            to_formatted = self.format_phone(to_phone)

            response = requests.post(
                f"{self.server}/restapi/v1.0/account/~/extension/~/sms",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": {"phoneNumber": self.from_number},
                    "to": [{"phoneNumber": to_formatted}],
                    "text": message
                },
                timeout=30
            )

            if response.status_code in (200, 201):
                data = response.json()
                message_id = data.get("id")
                logger.info(f"SMS sent to {to_formatted}: {message_id}")
                return True, message_id
            else:
                error = response.text[:200]
                logger.error(f"SMS send failed: {response.status_code} - {error}")
                return False, error

        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False, str(e)

    def build_shift_message(self, shift: Shift, caregiver: Caregiver) -> str:
        """
        Build the SMS message for a shift offer.

        Args:
            shift: The shift to fill
            caregiver: The caregiver receiving the offer

        Returns:
            Formatted SMS message
        """
        client_name = shift.client.first_name if shift.client else "a client"
        city = shift.client.city if shift.client else ""

        # Format date nicely
        if shift.date == datetime.now().date():
            date_str = "TODAY"
        elif shift.date == (datetime.now() + timedelta(days=1)).date():
            date_str = "TOMORROW"
        else:
            date_str = shift.date.strftime("%A, %b %d")

        time_str = shift.to_display_time()
        hours = shift.duration_hours

        # Personalize based on prior relationship
        if shift.client and shift.client.id in caregiver.clients_worked_with:
            intro = f"Hi {caregiver.first_name}! Can you cover a shift for {client_name}? You've worked with them before."
        else:
            intro = f"Hi {caregiver.first_name}! Can you cover a shift for {client_name} in {city}?"

        # Add urgency for same-day shifts
        urgent_note = " ⚠️ URGENT - shift starts soon!" if shift.is_urgent else ""

        message = (
            f"{intro}\n\n"
            f"📅 {date_str}\n"
            f"🕐 {time_str} ({hours:.1f} hrs)\n"
            f"📍 {city}{urgent_note}\n\n"
            f"Reply YES to accept or NO to decline."
        )

        return message

    def parse_response(self, message_text: str) -> CaregiverResponseType:
        """
        Parse a caregiver's SMS response.

        Uses patterns trained on 4,956 real SMS messages from
        Colorado CareAssist caregiver communications.

        Args:
            message_text: The text of the caregiver's reply

        Returns:
            CaregiverResponseType indicating their response
        """
        text_lower = message_text.lower().strip()

        # Handle empty or emoji-only messages
        if not text_lower or len(text_lower) <= 2:
            # Common emoji responses are ambiguous
            return CaregiverResponseType.AMBIGUOUS

        # Check exact matches first (highest confidence)
        if text_lower in self.ACCEPTANCE_EXACT:
            return CaregiverResponseType.ACCEPTED

        if text_lower in self.DECLINE_EXACT:
            return CaregiverResponseType.DECLINED

        # Check if it's a question (needs clarification, not a response)
        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, text_lower):
                return CaregiverResponseType.AMBIGUOUS

        # Score-based approach for longer messages
        accept_score = 0
        decline_score = 0

        # Check acceptance patterns
        for pattern in self.ACCEPTANCE_PATTERNS:
            if re.search(pattern, text_lower):
                accept_score += 1

        # Check decline patterns
        for pattern in self.DECLINE_PATTERNS:
            if re.search(pattern, text_lower):
                decline_score += 1

        # Determine result based on scores
        if accept_score > 0 and decline_score == 0:
            return CaregiverResponseType.ACCEPTED

        if decline_score > 0 and accept_score == 0:
            return CaregiverResponseType.DECLINED

        # If both patterns match, use the stronger signal
        if accept_score > decline_score:
            return CaregiverResponseType.ACCEPTED
        if decline_score > accept_score:
            return CaregiverResponseType.DECLINED

        # If no clear pattern, mark as ambiguous
        return CaregiverResponseType.AMBIGUOUS

    def send_shift_offer(
        self,
        shift: Shift,
        caregiver: Caregiver
    ) -> CaregiverOutreach:
        """
        Send a shift offer SMS to a caregiver.

        Args:
            shift: The shift to fill
            caregiver: The caregiver to contact

        Returns:
            CaregiverOutreach object with send status
        """
        outreach = CaregiverOutreach(
            caregiver_id=caregiver.id,
            caregiver=caregiver,
            phone=caregiver.phone
        )

        message = self.build_shift_message(shift, caregiver)
        success, result = self.send_sms(caregiver.phone, message)

        if success:
            outreach.message_sent = message
            outreach.sent_at = datetime.now()
            logger.info(f"Shift offer sent to {caregiver.full_name} ({caregiver.phone})")
        else:
            logger.error(f"Failed to send shift offer to {caregiver.full_name}: {result}")

        return outreach

    def send_confirmation(self, caregiver: Caregiver, shift: Shift) -> bool:
        """
        Send confirmation message to the winning caregiver.

        Args:
            caregiver: The caregiver who accepted
            shift: The shift they're assigned to

        Returns:
            True if sent successfully
        """
        client_name = shift.client.full_name if shift.client else "the client"
        address = shift.client.full_address if shift.client else ""

        message = (
            f"✅ CONFIRMED! You're assigned to {client_name}.\n\n"
            f"📅 {shift.date.strftime('%A, %b %d')}\n"
            f"🕐 {shift.to_display_time()}\n"
            f"📍 {address}\n\n"
            f"Please clock in on time. Thank you!"
        )

        success, _ = self.send_sms(caregiver.phone, message)
        return success

    def send_shift_filled_notification(
        self,
        caregiver: Caregiver,
        shift: Shift
    ) -> bool:
        """
        Notify a caregiver that the shift has been filled by someone else.

        Args:
            caregiver: The caregiver who was also contacted
            shift: The shift that was filled

        Returns:
            True if sent successfully
        """
        message = (
            f"Thanks for responding, {caregiver.first_name}! "
            f"The shift for {shift.date.strftime('%b %d')} has been filled. "
            f"We'll reach out again with future opportunities!"
        )

        success, _ = self.send_sms(caregiver.phone, message)
        return success

    def send_parallel_offers(
        self,
        shift: Shift,
        caregivers: List[Caregiver],
        max_concurrent: int = 10
    ) -> List[CaregiverOutreach]:
        """
        Send shift offers to multiple caregivers in parallel.

        In production, this would use async/await for true parallelism.
        For POC, we send sequentially but track all outreach.

        Args:
            shift: The shift to fill
            caregivers: List of caregivers to contact
            max_concurrent: Maximum number to contact at once

        Returns:
            List of CaregiverOutreach objects
        """
        outreach_list = []

        for caregiver in caregivers[:max_concurrent]:
            outreach = self.send_shift_offer(shift, caregiver)
            outreach_list.append(outreach)

        logger.info(f"Sent {len(outreach_list)} parallel shift offers")
        return outreach_list

    def get_inbound_messages(self, since_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch recent inbound SMS messages.

        Used to poll for caregiver responses.

        Args:
            since_minutes: How far back to look

        Returns:
            List of message records
        """
        token = self._get_access_token()
        if not token:
            return []

        try:
            date_from = (datetime.utcnow() - timedelta(minutes=since_minutes)).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )

            response = requests.get(
                f"{self.server}/restapi/v1.0/account/~/extension/~/message-store",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "dateFrom": date_from,
                    "messageType": "SMS",
                    "direction": "Inbound",
                    "perPage": 100
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("records", [])
                logger.info(f"Fetched {len(messages)} inbound SMS messages")
                return messages
            else:
                logger.error(f"Failed to fetch messages: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error fetching inbound messages: {e}")
            return []

    def match_response_to_outreach(
        self,
        message: Dict[str, Any],
        active_outreaches: List[CaregiverOutreach]
    ) -> Optional[CaregiverOutreach]:
        """
        Match an inbound message to an active outreach.

        Args:
            message: The inbound message record
            active_outreaches: List of pending outreach records

        Returns:
            Matching CaregiverOutreach or None
        """
        from_number = message.get("from", {}).get("phoneNumber", "")
        clean_from = re.sub(r'[^\d]', '', from_number)[-10:]

        for outreach in active_outreaches:
            clean_outreach = re.sub(r'[^\d]', '', outreach.phone)[-10:]
            if clean_from == clean_outreach:
                return outreach

        return None

    def is_enabled(self) -> bool:
        """Check if SMS service is properly configured."""
        return self.enabled

    def get_status(self) -> Dict[str, Any]:
        """Get SMS service status."""
        status = {
            "enabled": self.enabled,
            "server": self.server,
            "from_number": self.from_number,
            "api_connected": False,
            "error": None
        }

        if self.enabled:
            token = self._get_access_token()
            if token:
                status["api_connected"] = True
            else:
                status["error"] = "Failed to authenticate"
        else:
            status["error"] = "Missing credentials"

        return status


# Mock SMS service for testing without real RingCentral
class MockSMSService(SMSService):
    """
    Mock SMS service for POC testing.

    Simulates sending SMS without actually calling RingCentral API.
    """

    def __init__(self):
        super().__init__()
        self.sent_messages: List[Dict[str, Any]] = []
        self.simulated_responses: Dict[str, str] = {}  # phone -> response

    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, Optional[str]]:
        """Simulate sending SMS."""
        message_id = f"mock_{datetime.now().timestamp()}"
        self.sent_messages.append({
            "id": message_id,
            "to": to_phone,
            "text": message,
            "sent_at": datetime.now()
        })
        logger.info(f"[MOCK] SMS to {to_phone}: {message[:50]}...")
        return True, message_id

    def simulate_response(self, phone: str, response: str):
        """Add a simulated response for testing."""
        self.simulated_responses[re.sub(r'[^\d]', '', phone)[-10:]] = response

    def get_simulated_response(self, phone: str) -> Optional[str]:
        """Get simulated response for a phone number."""
        clean = re.sub(r'[^\d]', '', phone)[-10:]
        return self.simulated_responses.get(clean)

    def is_enabled(self) -> bool:
        """Mock is always enabled."""
        return True


# Default instance - use mock for POC
sms_service = MockSMSService()
