#!/usr/bin/env python3
"""
RingCentral integration service.
Currently disabled - webhook-based call logging is active.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RingCentralService:
    """Service for RingCentral call log synchronization."""

    def __init__(self):
        # RingCentral integration is currently handled via webhooks only
        # Manual sync is disabled to avoid breaking existing functionality
        pass

    def sync_call_logs_to_activities(self, db, since_minutes: int = 1440) -> int:
        """
        Sync call logs from RingCentral to CRM activities.

        Currently disabled - call logging is handled automatically via webhooks
        in the /webhooks/ringcentral endpoint.

        Args:
            db: Database session
            since_minutes: How far back to sync (minutes)

        Returns:
            Number of calls synced (currently always 0)
        """
        logger.info(f"RingCentral manual sync disabled - webhook-based logging is active. "
                   f"Skipped sync for last {since_minutes} minutes.")
        return 0


def sync_ringcentral_calls_job():
    """
    Background job to sync RingCentral call logs.

    Currently disabled - call logging is handled automatically via webhooks.
    This function exists only to prevent scheduler import errors.
    """
    logger.info("RingCentral sync job executed but disabled - using webhook-based call logging")
