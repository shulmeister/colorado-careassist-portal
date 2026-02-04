#!/usr/bin/env python3
"""
RingCentral integration service - Polls call logs and syncs to CRM activities
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import requests

from activity_logger import ActivityLogger
from models import Contact, Lead, ActivityLog

logger = logging.getLogger(__name__)

# RingCentral credentials
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")


class RingCentralService:
    """Service for RingCentral call log synchronization via polling."""

    def __init__(self):
        self.client_id = RINGCENTRAL_CLIENT_ID
        self.client_secret = RINGCENTRAL_CLIENT_SECRET
        self.jwt_token = RINGCENTRAL_JWT_TOKEN
        self.server = RINGCENTRAL_SERVER
        self.access_token = None
        self.token_expires_at = None

        self.enabled = bool(self.client_id and self.client_secret)
        if not self.enabled:
            logger.warning("RingCentral credentials not configured")

    def _get_access_token(self) -> Optional[str]:
        """Get access token using password grant (more reliable than JWT for some apps)"""
        if not self.enabled:
            return None

        # Check if we have a valid cached token
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token

        try:
            # Try JWT grant first
            if self.jwt_token:
                response = requests.post(
                    f"{self.server}/restapi/oauth/token",
                    auth=(self.client_id, self.client_secret),
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": self.jwt_token
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )

                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                    logger.info("RingCentral: Got access token via JWT")
                    return self.access_token
                else:
                    logger.warning(f"RingCentral JWT auth failed: {response.status_code} - {response.text[:200]}")

            return None

        except Exception as e:
            logger.error(f"RingCentral auth error: {e}")
            return None

    def get_call_logs(self, since_minutes: int = 1440) -> List[Dict[str, Any]]:
        """
        Fetch call logs from RingCentral API

        Args:
            since_minutes: How far back to fetch (default 24 hours)

        Returns:
            List of call log records
        """
        token = self._get_access_token()
        if not token:
            logger.warning("RingCentral: No access token, cannot fetch call logs")
            return []

        try:
            # Calculate date range
            date_from = (datetime.utcnow() - timedelta(minutes=since_minutes)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            # Fetch call logs
            response = requests.get(
                f"{self.server}/restapi/v1.0/account/~/extension/~/call-log",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "dateFrom": date_from,
                    "type": "Voice",
                    "view": "Detailed",
                    "perPage": 250
                }
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                logger.info(f"RingCentral: Fetched {len(records)} call logs")
                return records
            else:
                logger.error(f"RingCentral call log fetch failed: {response.status_code} - {response.text[:200]}")
                return []

        except Exception as e:
            logger.error(f"RingCentral call log error: {e}")
            return []

    def sync_call_logs_to_activities(self, db, since_minutes: int = 1440) -> int:
        """
        Sync call logs from RingCentral to CRM activities.

        Args:
            db: Database session
            since_minutes: How far back to sync (minutes)

        Returns:
            Number of calls synced
        """
        if not self.enabled:
            logger.info("RingCentral service not enabled")
            return 0

        call_logs = self.get_call_logs(since_minutes)
        if not call_logs:
            return 0

        synced_count = 0

        for call in call_logs:
            try:
                # Extract call details
                call_id = call.get("id")
                direction = call.get("direction", "Outbound").lower()  # "Inbound" or "Outbound"
                duration = call.get("duration", 0)
                start_time = call.get("startTime")

                # Get phone number (from or to depending on direction)
                if direction == "inbound":
                    phone_data = call.get("from", {})
                else:
                    phone_data = call.get("to", {})

                phone_number = phone_data.get("phoneNumber", "")
                if not phone_number:
                    continue

                # Check if we've already logged this call
                existing = db.query(ActivityLog).filter(
                    ActivityLog.activity_type == "call",
                    ActivityLog.extra_data.like(f'%"call_id": "{call_id}"%')
                ).first()

                if existing:
                    continue

                # Find contact by phone number (last 10 digits)
                clean_phone = re.sub(r'[^\d]', '', phone_number)[-10:]
                contact = db.query(Contact).filter(
                    Contact.phone.like(f'%{clean_phone}%')
                ).first() if clean_phone else None

                # Find related deal if contact exists
                deal = None
                company_id = None
                if contact:
                    company_id = contact.company_id
                    deal = db.query(Lead).filter(
                        Lead.contact_name == contact.name,
                        Lead.status == "active"
                    ).first()

                # Get caller email/name
                caller_name = call.get("extension", {}).get("name", "")
                caller_email = f"{caller_name.lower().replace(' ', '.')}@coloradocareassist.com" if caller_name else "unknown@coloradocareassist.com"

                # Log the call activity
                ActivityLogger.log_call(
                    db=db,
                    contact_id=contact.id if contact else None,
                    phone_number=phone_number,
                    duration=duration,
                    user_email=caller_email,
                    call_direction=direction,
                    metadata={
                        "call_id": call_id,
                        "start_time": start_time,
                        "company_id": company_id,
                        "deal_id": deal.id if deal else None,
                        "contact_name": contact.name if contact else None,
                        "result": call.get("result", ""),
                        "recording_id": call.get("recording", {}).get("id") if call.get("recording") else None
                    }
                )

                synced_count += 1
                logger.info(f"RingCentral: Synced call to {phone_number} ({duration}s)")

            except Exception as e:
                logger.error(f"RingCentral: Error syncing call: {e}")
                continue

        logger.info(f"RingCentral: Synced {synced_count} calls to activities")
        return synced_count


def sync_ringcentral_calls_job():
    """
    Background job to sync RingCentral call logs.
    Add this to Mac Mini (Local) Scheduler to run every 30 minutes.
    """
    try:
        from database import get_db
        db = next(get_db())
        service = RingCentralService()
        synced = service.sync_call_logs_to_activities(db, since_minutes=60)  # Last hour
        logger.info(f"RingCentral sync job completed: {synced} calls synced")
        db.close()
        return synced
    except Exception as e:
        logger.error(f"RingCentral sync job error: {e}")
        return 0
