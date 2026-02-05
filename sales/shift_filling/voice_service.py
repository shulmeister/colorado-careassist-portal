"""
Voice Outreach Service for Shift Filling

Uses Retell AI to make outbound calls to caregivers offering shifts.
SMS is sent first, then voice call follows after a configurable delay
if the caregiver hasn't responded.
"""

import os
import re
import logging
import requests
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_API_BASE = "https://api.retellai.com"
SHIFT_OFFER_AGENT_ID = os.getenv("RETELL_SHIFT_OFFER_AGENT_ID", "")
FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER", "+17194283999")
VOICE_OUTREACH_ENABLED = os.getenv("VOICE_OUTREACH_ENABLED", "false").lower() == "true"

# Language code mapping for Retell
LANGUAGE_MAP = {
    "English": "en-US",
    "Spanish": "es-ES",
    "Vietnamese": "vi-VN",
    "French": "fr-FR",
    "Korean": "ko-KR",
    "Chinese": "zh-CN",
    "Russian": "ru-RU",
    "Portuguese": "pt-BR",
    "Arabic": "ar-SA",
}


class VoiceOutreachService:
    """Makes outbound Retell AI calls for shift offers."""

    def __init__(self):
        self.api_key = RETELL_API_KEY
        self.agent_id = SHIFT_OFFER_AGENT_ID
        self.enabled = bool(
            VOICE_OUTREACH_ENABLED
            and self.api_key
            and self.agent_id
        )

    def create_shift_offer_call(
        self,
        caregiver_phone: str,
        caregiver_name: str,
        client_name: str,
        shift_date: str,
        shift_time: str,
        shift_duration: float,
        campaign_id: str,
        language: str = "English"
    ) -> Tuple[bool, Optional[str]]:
        """
        Initiate an outbound Retell call to offer a shift.

        Args:
            caregiver_phone: Caregiver's phone number
            caregiver_name: Caregiver's first name
            client_name: Client's first name
            shift_date: Formatted date string (e.g. "Wednesday, February 5")
            shift_time: Formatted time range (e.g. "9:00 AM - 1:00 PM")
            shift_duration: Duration in hours
            campaign_id: Shift filling campaign ID
            language: Caregiver's preferred language

        Returns:
            Tuple of (success, call_id)
        """
        if not self.enabled:
            logger.debug("Voice outreach not enabled or not configured")
            return False, None

        to_number = self._format_phone(caregiver_phone)
        if not to_number:
            logger.warning(f"Invalid phone number: {caregiver_phone}")
            return False, None

        # Dynamic variables injected into the Retell agent prompt
        agent_prompt_params = {
            "caregiver_name": caregiver_name,
            "client_first_name": client_name,
            "shift_date": shift_date,
            "shift_time": shift_time,
            "shift_duration": f"{shift_duration:.1f}",
            "campaign_id": campaign_id,
        }

        retell_language = LANGUAGE_MAP.get(language, "en-US")

        try:
            payload = {
                "from_number": FROM_NUMBER,
                "to_number": to_number,
                "agent_id": self.agent_id,
                "retell_llm_dynamic_variables": agent_prompt_params,
                "metadata": {
                    "campaign_id": campaign_id,
                    "caregiver_phone": caregiver_phone,
                    "purpose": "shift_offer",
                },
            }

            # Set language if non-English
            if retell_language != "en-US":
                payload["language"] = retell_language

            response = requests.post(
                f"{RETELL_API_BASE}/v2/create-phone-call",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            if response.status_code in (200, 201):
                data = response.json()
                call_id = data.get("call_id")
                logger.info(
                    f"Outbound shift offer call initiated: {call_id} "
                    f"to {caregiver_name} ({to_number})"
                )
                return True, call_id
            else:
                logger.error(
                    f"Retell call failed: {response.status_code} - "
                    f"{response.text[:200]}"
                )
                return False, None

        except Exception as e:
            logger.error(f"Voice outreach error: {e}")
            return False, None

    def _format_phone(self, phone: str) -> Optional[str]:
        """Format phone number to E.164 format."""
        clean = re.sub(r"[^\d]", "", phone)
        if len(clean) == 10:
            return f"+1{clean}"
        elif len(clean) == 11 and clean.startswith("1"):
            return f"+{clean}"
        elif len(clean) > 11 and clean.startswith("1"):
            return f"+{clean[:11]}"
        return None


# Module-level singleton
voice_service = VoiceOutreachService()
