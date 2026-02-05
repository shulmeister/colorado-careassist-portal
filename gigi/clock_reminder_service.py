"""
Clock In/Out Reminder Service

Monitors today's shifts and sends SMS reminders to caregivers
who haven't clocked in/out within 5 minutes of shift start/end.

Integrates with the RC bot's check_and_act() polling loop.
"""

import os
import logging
from datetime import datetime, date, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

CLOCK_REMINDER_ENABLED = os.getenv("CLOCK_REMINDER_ENABLED", "false").lower() == "true"
REMINDER_THRESHOLD_MINUTES = 5   # Send reminder after this many minutes past shift start/end
REMINDER_COOLDOWN_MINUTES = 60   # Don't re-remind for same shift within this window
MAX_LATE_MINUTES = 120           # Don't send reminders if shift started > 2 hours ago


class ClockReminderService:
    """Monitors shifts and sends clock-in/out SMS reminders."""

    def __init__(self, wellsky_service, sms_send_fn: Callable):
        """
        Args:
            wellsky_service: WellSky API service instance
            sms_send_fn: Callable(phone: str, message: str) -> Tuple[bool, Optional[str]]
        """
        self.wellsky = wellsky_service
        self.send_sms = sms_send_fn

        # Local shift cache (refreshed hourly)
        self._cached_shifts: List[Dict] = []
        self._last_cache_refresh: Optional[datetime] = None
        self._cache_refresh_interval = timedelta(hours=1)

        # Track sent reminders to avoid duplicates: "shift_id:type" -> sent_at
        self._sent_reminders: Dict[str, datetime] = {}

    def check_and_remind(self) -> List[str]:
        """
        Main method called from RC bot every 5 minutes.

        Returns:
            List of actions taken (e.g., ["clock_in_reminder:Maria", ...])
        """
        if not CLOCK_REMINDER_ENABLED:
            return []

        now = datetime.now()
        actions = []

        # Refresh cache if stale
        if self._should_refresh_cache(now):
            self._refresh_shift_cache()

        for shift in self._cached_shifts:
            # Skip if not today
            if shift.get("shift_date") != date.today():
                continue

            # Check clock-in reminder
            if self._needs_clock_in_reminder(shift, now):
                sent = self._send_clock_in_reminder(shift, now)
                if sent:
                    actions.append(f"clock_in_reminder:{shift.get('caregiver_name', '?')}")

            # Check clock-out reminder
            if self._needs_clock_out_reminder(shift, now):
                sent = self._send_clock_out_reminder(shift, now)
                if sent:
                    actions.append(f"clock_out_reminder:{shift.get('caregiver_name', '?')}")

        # Clean up old reminder tracking entries
        self._cleanup_old_reminders(now)

        return actions

    def _should_refresh_cache(self, now: datetime) -> bool:
        if self._last_cache_refresh is None:
            return True
        return (now - self._last_cache_refresh) >= self._cache_refresh_interval

    def _refresh_shift_cache(self):
        """Fetch today's shifts and cache them locally."""
        try:
            today = date.today()
            shifts = self.wellsky.get_shifts(
                date_from=today, date_to=today, limit=500
            )

            self._cached_shifts = []
            for s in shifts:
                if not s.caregiver_id:
                    continue
                if hasattr(s, 'status') and hasattr(s.status, 'value'):
                    status = s.status.value
                else:
                    status = str(s.status) if s.status else "scheduled"

                if status not in ("scheduled", "confirmed", "in_progress"):
                    continue

                # Get caregiver phone from the shift or look up
                phone = ""
                if hasattr(s, 'caregiver_phone') and s.caregiver_phone:
                    phone = s.caregiver_phone
                else:
                    try:
                        cg = self.wellsky.get_caregiver(s.caregiver_id)
                        phone = cg.phone if cg else ""
                    except Exception:
                        pass

                caregiver_name = ""
                if hasattr(s, 'caregiver_first_name') and s.caregiver_first_name:
                    caregiver_name = s.caregiver_first_name
                elif hasattr(s, 'caregiver_name') and s.caregiver_name:
                    caregiver_name = s.caregiver_name

                client_name = ""
                if hasattr(s, 'client_first_name') and s.client_first_name:
                    client_name = s.client_first_name
                elif hasattr(s, 'client_name') and s.client_name:
                    client_name = s.client_name

                self._cached_shifts.append({
                    "shift_id": s.id,
                    "caregiver_id": s.caregiver_id,
                    "caregiver_phone": phone,
                    "caregiver_name": caregiver_name,
                    "client_name": client_name,
                    "shift_date": s.date if hasattr(s, 'date') else today,
                    "start_time": s.start_time if hasattr(s, 'start_time') else None,
                    "end_time": s.end_time if hasattr(s, 'end_time') else None,
                    "clock_in_time": s.clock_in_time if hasattr(s, 'clock_in_time') else None,
                    "clock_out_time": s.clock_out_time if hasattr(s, 'clock_out_time') else None,
                    "status": status,
                })

            self._last_cache_refresh = datetime.now()
            logger.info(f"Clock reminder cache refreshed: {len(self._cached_shifts)} shifts today")

        except Exception as e:
            logger.error(f"Failed to refresh shift cache: {e}")

    def _parse_time(self, time_str) -> Optional[dt_time]:
        """Parse a time string into a time object."""
        if not time_str:
            return None
        if isinstance(time_str, dt_time):
            return time_str
        try:
            # Try HH:MM format
            return datetime.strptime(str(time_str)[:5], "%H:%M").time()
        except (ValueError, TypeError):
            try:
                # Try HH:MM:SS format
                return datetime.strptime(str(time_str)[:8], "%H:%M:%S").time()
            except (ValueError, TypeError):
                return None

    def _needs_clock_in_reminder(self, shift: Dict, now: datetime) -> bool:
        if shift.get("clock_in_time") is not None:
            return False
        if shift.get("status") not in ("scheduled", "confirmed"):
            return False
        if not shift.get("caregiver_phone"):
            return False

        start = self._parse_time(shift.get("start_time"))
        if not start:
            return False

        start_dt = datetime.combine(date.today(), start)
        minutes_late = (now - start_dt).total_seconds() / 60

        if minutes_late < REMINDER_THRESHOLD_MINUTES or minutes_late > MAX_LATE_MINUTES:
            return False

        key = f"{shift['shift_id']}:clock_in"
        return not self._was_recently_reminded(key)

    def _needs_clock_out_reminder(self, shift: Dict, now: datetime) -> bool:
        if shift.get("clock_in_time") is None:
            return False  # Never clocked in
        if shift.get("clock_out_time") is not None:
            return False  # Already clocked out
        if not shift.get("caregiver_phone"):
            return False

        end = self._parse_time(shift.get("end_time"))
        if not end:
            return False

        end_dt = datetime.combine(date.today(), end)
        minutes_past = (now - end_dt).total_seconds() / 60

        if minutes_past < REMINDER_THRESHOLD_MINUTES or minutes_past > MAX_LATE_MINUTES:
            return False

        key = f"{shift['shift_id']}:clock_out"
        return not self._was_recently_reminded(key)

    def _was_recently_reminded(self, key: str) -> bool:
        if key in self._sent_reminders:
            elapsed = (datetime.now() - self._sent_reminders[key]).total_seconds() / 60
            return elapsed < REMINDER_COOLDOWN_MINUTES
        return False

    def _send_clock_in_reminder(self, shift: Dict, now: datetime) -> bool:
        name = shift.get("caregiver_name", "there")
        client = shift.get("client_name", "your client")
        start = shift.get("start_time", "?")

        msg = (
            f"Hi {name}, reminder: please clock in for your shift "
            f"with {client} that started at {start}. "
            f"Reply DONE when complete."
        )

        success, _ = self.send_sms(shift["caregiver_phone"], msg)
        if success:
            self._sent_reminders[f"{shift['shift_id']}:clock_in"] = datetime.now()
            logger.info(f"Clock-in reminder sent to {name} for shift {shift['shift_id']}")
        return success

    def _send_clock_out_reminder(self, shift: Dict, now: datetime) -> bool:
        name = shift.get("caregiver_name", "there")
        client = shift.get("client_name", "your client")
        end = shift.get("end_time", "?")

        msg = (
            f"Hi {name}, your shift with {client} ended at {end}. "
            f"Please clock out if you haven't already."
        )

        success, _ = self.send_sms(shift["caregiver_phone"], msg)
        if success:
            self._sent_reminders[f"{shift['shift_id']}:clock_out"] = datetime.now()
            logger.info(f"Clock-out reminder sent to {name} for shift {shift['shift_id']}")
        return success

    def _cleanup_old_reminders(self, now: datetime):
        """Remove reminder tracking entries older than 24 hours."""
        cutoff = now - timedelta(hours=24)
        keys_to_remove = [
            k for k, v in self._sent_reminders.items()
            if v < cutoff
        ]
        for k in keys_to_remove:
            del self._sent_reminders[k]
