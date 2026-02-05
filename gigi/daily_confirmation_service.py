"""
Daily Shift Confirmation Service

Sends "you have shifts tomorrow" reminder texts at 2pm Mountain daily.
One SMS per caregiver, even if they have multiple shifts.

Integrates with the RC bot's check_and_act() polling loop.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Callable

try:
    import pytz
    TIMEZONE = pytz.timezone("America/Denver")
except ImportError:
    TIMEZONE = None

logger = logging.getLogger(__name__)

DAILY_CONFIRMATION_ENABLED = os.getenv("DAILY_CONFIRMATION_ENABLED", "false").lower() == "true"
CONFIRMATION_HOUR = 14  # 2pm Mountain


class DailyConfirmationService:
    """Sends daily shift confirmation texts at 2pm Mountain."""

    def __init__(self, wellsky_service, sms_send_fn: Callable):
        """
        Args:
            wellsky_service: WellSky API service instance
            sms_send_fn: Callable(phone: str, message: str) -> Tuple[bool, Optional[str]]
        """
        self.wellsky = wellsky_service
        self.send_sms = sms_send_fn
        self._last_confirmation_date: Optional[date] = None

    def check_and_send(self) -> List[str]:
        """
        Called from RC bot's check_and_act() loop every cycle.
        Only actually sends once per day at 2pm Mountain.

        Returns:
            List of caregiver names who were notified.
        """
        if not DAILY_CONFIRMATION_ENABLED:
            return []

        now = self._get_mountain_time()

        # Only send during the 2pm hour (14:00-14:29)
        if now.hour != CONFIRMATION_HOUR or now.minute > 29:
            return []

        # Only send once per day
        today = now.date()
        if self._last_confirmation_date == today:
            return []

        self._last_confirmation_date = today
        logger.info("Starting daily shift confirmations...")
        return self._send_all_confirmations()

    def _get_mountain_time(self) -> datetime:
        """Get current time in Mountain timezone."""
        if TIMEZONE:
            return datetime.now(TIMEZONE)
        # Fallback: assume UTC-7
        return datetime.utcnow() - timedelta(hours=7)

    def _send_all_confirmations(self) -> List[str]:
        """Query tomorrow's shifts and send grouped confirmation texts."""
        tomorrow = date.today() + timedelta(days=1)
        notified = []

        try:
            # Get active caregivers from cache
            from services.wellsky_service import CaregiverStatus
            caregivers = self.wellsky.get_caregivers(
                status=CaregiverStatus.ACTIVE, limit=200
            )

            caregiver_count = 0
            shift_count = 0

            for cg in caregivers:
                if not cg.phone:
                    continue

                try:
                    shifts = self.wellsky.get_shifts(
                        caregiver_id=cg.id,
                        date_from=tomorrow,
                        date_to=tomorrow
                    )
                except Exception as e:
                    logger.warning(f"Failed to get shifts for {cg.first_name}: {e}")
                    continue

                if not shifts:
                    continue

                # Filter to only scheduled/confirmed shifts
                active_shifts = []
                for s in shifts:
                    status = s.status.value if hasattr(s.status, 'value') else str(s.status)
                    if status in ("scheduled", "confirmed"):
                        active_shifts.append(s)

                if not active_shifts:
                    continue

                message = self._build_confirmation_message(cg.first_name, active_shifts)
                success, _ = self.send_sms(cg.phone, message)

                if success:
                    notified.append(cg.first_name)
                    caregiver_count += 1
                    shift_count += len(active_shifts)

            logger.info(
                f"Daily confirmations complete: {caregiver_count} caregivers, "
                f"{shift_count} shifts"
            )

        except Exception as e:
            logger.error(f"Daily confirmation error: {e}")

        return notified

    def _build_confirmation_message(self, caregiver_name: str, shifts: list) -> str:
        """Build the confirmation SMS for a caregiver."""
        n = len(shifts)
        tomorrow = date.today() + timedelta(days=1)
        day_name = tomorrow.strftime("%A, %b %d")

        if n == 1:
            s = shifts[0]
            client = self._get_client_name(s)
            time_range = self._get_time_range(s)
            msg = (
                f"Hi {caregiver_name}, reminder: you have a shift tomorrow "
                f"({day_name}):\n"
                f"- {client} {time_range}\n\n"
                f"Please confirm by replying YES."
            )
        else:
            lines = []
            for s in shifts:
                client = self._get_client_name(s)
                time_range = self._get_time_range(s)
                lines.append(f"- {client} {time_range}")

            shift_list = "\n".join(lines)
            msg = (
                f"Hi {caregiver_name}, reminder: you have {n} shifts tomorrow "
                f"({day_name}):\n"
                f"{shift_list}\n\n"
                f"Please confirm by replying YES."
            )

        return msg

    def _get_client_name(self, shift) -> str:
        """Extract client name from shift object."""
        if hasattr(shift, 'client_first_name') and shift.client_first_name:
            return shift.client_first_name
        if hasattr(shift, 'client_name') and shift.client_name:
            return shift.client_name
        return "Client"

    def _get_time_range(self, shift) -> str:
        """Format shift time range."""
        start = getattr(shift, 'start_time', None)
        end = getattr(shift, 'end_time', None)
        if start and end:
            return f"{start}-{end}"
        elif start:
            return f"starting {start}"
        return ""
