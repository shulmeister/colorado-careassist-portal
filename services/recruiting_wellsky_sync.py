"""
Recruiting Dashboard → WellSky Applicant Sync Service

Synchronizes leads from the Recruiting Dashboard to WellSky applicants.
This enables the hub-and-spoke integration where:
- Recruiting Dashboard is the primary source for caregiver candidates
- WellSky is the central hub for operational data
- When a lead is hired and paperwork is complete, applicant converts to caregiver

Sync Logic:
1. New lead in Recruiting Dashboard → Create applicant in WellSky
2. Lead status change → Update applicant status in WellSky
3. Lead hired + GoFormz complete → Convert applicant to caregiver in WellSky
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from services.wellsky_service import (
    wellsky_service,
    WellSkyApplicant,
    ApplicantStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Status Mapping: Recruiting Dashboard → WellSky Applicant Status
# =============================================================================

# Map Recruiting Dashboard lead statuses to WellSky applicant statuses
STATUS_TO_APPLICANT_STATUS = {
    # Recruiting Dashboard statuses → WellSky ApplicantStatus
    "new": ApplicantStatus.NEW,
    "contacted": ApplicantStatus.SCREENING,
    "screening": ApplicantStatus.SCREENING,
    "phone_screen": ApplicantStatus.PHONE_INTERVIEW,
    "phone_interview": ApplicantStatus.PHONE_INTERVIEW,
    "interview_scheduled": ApplicantStatus.IN_PERSON_INTERVIEW,
    "interviewed": ApplicantStatus.IN_PERSON_INTERVIEW,
    "in_person_interview": ApplicantStatus.IN_PERSON_INTERVIEW,
    "background_check": ApplicantStatus.BACKGROUND_CHECK,
    "pending_background": ApplicantStatus.BACKGROUND_CHECK,
    "offer_extended": ApplicantStatus.OFFER_EXTENDED,
    "offer_sent": ApplicantStatus.OFFER_EXTENDED,
    "hired": ApplicantStatus.HIRED,
    "onboarding": ApplicantStatus.HIRED,
    "rejected": ApplicantStatus.REJECTED,
    "not_qualified": ApplicantStatus.REJECTED,
    "withdrawn": ApplicantStatus.WITHDRAWN,
    "no_show": ApplicantStatus.WITHDRAWN,
    "unresponsive": ApplicantStatus.WITHDRAWN,
}


class RecruitingWellSkySyncService:
    """
    Service for synchronizing Recruiting Dashboard leads with WellSky applicants.

    Provides bidirectional sync capabilities:
    - Push: Recruiting Dashboard → WellSky (primary direction)
    - Pull: WellSky → Recruiting Dashboard (for status updates)
    """

    def __init__(self):
        self.wellsky = wellsky_service
        self._sync_log: List[Dict[str, Any]] = []

    # =========================================================================
    # Core Sync Methods
    # =========================================================================

    def sync_lead_to_applicant(
        self,
        lead: Dict[str, Any],
        force_create: bool = False
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """
        Sync a Recruiting Dashboard lead to WellSky as an applicant.

        Args:
            lead: Lead dict from Recruiting Dashboard
            force_create: If True, create even if already exists

        Returns:
            Tuple of (success, applicant_or_none, message)
        """
        lead_id = str(lead.get("id", ""))
        lead_name = lead.get("name", "Unknown Lead")

        if not lead_id:
            return False, None, "Lead ID is required"

        # Check if applicant already exists for this lead
        existing = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

        if existing and not force_create:
            # Update existing applicant
            return self._update_applicant_from_lead(existing, lead)

        # Create new applicant
        return self._create_applicant_from_lead(lead)

    def sync_lead_status_change(
        self,
        lead_id: str,
        new_status: str,
        changed_by: Optional[str] = None,
        notes: str = ""
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """
        Sync a lead status change to WellSky applicant status.

        Called when a lead moves to a new status in Recruiting Dashboard.
        """
        # Find existing applicant
        applicant = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

        if not applicant:
            logger.warning(f"No applicant found for lead {lead_id} - skipping status sync")
            return False, None, f"No applicant found for lead {lead_id}"

        # Map status to applicant status
        new_applicant_status = STATUS_TO_APPLICANT_STATUS.get(
            new_status.lower().replace(" ", "_"),
            ApplicantStatus.NEW
        )

        if applicant.status == new_applicant_status:
            return True, applicant, f"Applicant already at status {new_applicant_status.value}"

        # Update the applicant status
        status_notes = f"Status changed to {new_status}"
        if changed_by:
            status_notes += f" by {changed_by}"
        if notes:
            status_notes += f": {notes}"

        updated = self.wellsky.update_applicant_status(
            applicant.id,
            new_applicant_status,
            notes=status_notes
        )

        if updated:
            self._log_sync(
                "status_change",
                lead_id=lead_id,
                applicant_id=applicant.id,
                from_status=applicant.status.value,
                to_status=new_applicant_status.value
            )
            return True, updated, f"Updated applicant status to {new_applicant_status.value}"

        return False, None, "Failed to update applicant status"

    def sync_lead_hired(
        self,
        lead_id: str,
        hire_date: Optional[str] = None,
        hourly_rate: Optional[float] = None
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """
        Handle a lead being hired - mark applicant as hired.

        Note: Actual conversion to caregiver happens when GoFormz paperwork
        is completed (see GoFormzWellSkySyncService).
        """
        applicant = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

        if not applicant:
            return False, None, f"No applicant found for lead {lead_id}"

        # Update to hired status
        updates = {"status": ApplicantStatus.HIRED.value}

        if hire_date:
            updates["start_date"] = hire_date
        if hourly_rate:
            updates["offer_hourly_rate"] = hourly_rate

        updated = self.wellsky.update_applicant(applicant.id, updates)

        if updated:
            # Also update the status through proper method for date tracking
            self.wellsky.update_applicant_status(
                applicant.id,
                ApplicantStatus.HIRED,
                notes="Hired in Recruiting Dashboard - awaiting paperwork for caregiver conversion"
            )

            self._log_sync(
                "lead_hired",
                lead_id=lead_id,
                applicant_id=applicant.id
            )
            return True, updated, "Applicant marked as hired - awaiting paperwork for caregiver conversion"

        return False, None, "Failed to mark applicant as hired"

    def sync_lead_rejected(
        self,
        lead_id: str,
        rejected_reason: str = ""
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """
        Handle a lead being rejected.
        """
        applicant = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

        if not applicant:
            return False, None, f"No applicant found for lead {lead_id}"

        updated = self.wellsky.update_applicant_status(
            applicant.id,
            ApplicantStatus.REJECTED,
            notes=rejected_reason or "Rejected in Recruiting Dashboard"
        )

        if updated:
            self._log_sync(
                "lead_rejected",
                lead_id=lead_id,
                applicant_id=applicant.id,
                reason=rejected_reason
            )
            return True, updated, "Applicant marked as rejected"

        return False, None, "Failed to mark applicant as rejected"

    def sync_lead_withdrawn(
        self,
        lead_id: str,
        withdrawn_reason: str = ""
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """
        Handle a lead withdrawing from the process.
        """
        applicant = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

        if not applicant:
            return False, None, f"No applicant found for lead {lead_id}"

        updated = self.wellsky.update_applicant_status(
            applicant.id,
            ApplicantStatus.WITHDRAWN,
            notes=withdrawn_reason or "Withdrawn in Recruiting Dashboard"
        )

        if updated:
            self._log_sync(
                "lead_withdrawn",
                lead_id=lead_id,
                applicant_id=applicant.id,
                reason=withdrawn_reason
            )
            return True, updated, "Applicant marked as withdrawn"

        return False, None, "Failed to mark applicant as withdrawn"

    # =========================================================================
    # Bulk Sync Methods
    # =========================================================================

    def sync_all_leads(
        self,
        leads: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Sync all leads from Recruiting Dashboard to WellSky.

        Args:
            leads: List of lead dicts from Recruiting Dashboard

        Returns:
            Summary of sync results
        """
        results = {
            "total": len(leads),
            "created": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        for lead in leads:
            try:
                # Skip leads with terminal statuses that shouldn't be synced
                status = lead.get("status", "").lower()
                if status in ("rejected", "withdrawn", "no_show", "unresponsive"):
                    results["skipped"] += 1
                    continue

                success, applicant, message = self.sync_lead_to_applicant(lead)

                if success:
                    if "Created" in message:
                        results["created"] += 1
                    else:
                        results["updated"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "lead_id": lead.get("id"),
                        "lead_name": lead.get("name"),
                        "error": message
                    })

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "lead_id": lead.get("id"),
                    "lead_name": lead.get("name"),
                    "error": str(e)
                })
                logger.exception(f"Error syncing lead {lead.get('id')}: {e}")

        logger.info(f"Bulk sync complete: {results['created']} created, "
                   f"{results['updated']} updated, {results['failed']} failed")

        return results

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_applicant_from_lead(
        self,
        lead: Dict[str, Any]
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """Create a new applicant from a lead."""
        lead_id = str(lead.get("id", ""))

        # Parse name
        full_name = lead.get("name", "Unknown")
        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else "Unknown"
        last_name = parts[1] if len(parts) > 1 else ""

        # Map status to applicant status
        status = lead.get("status", "new").lower().replace(" ", "_")
        applicant_status = STATUS_TO_APPLICANT_STATUS.get(status, ApplicantStatus.NEW)

        # Build applicant data
        applicant_data = {
            "first_name": first_name,
            "last_name": last_name,
            "status": applicant_status.value,
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "source": self._map_lead_source(lead.get("source", "")),
            "position_applied": "Caregiver",  # Default position
            "notes": lead.get("notes", ""),
            "recruiting_dashboard_lead_id": lead_id,
        }

        # Handle dates
        if lead.get("created_at"):
            try:
                created = datetime.fromisoformat(str(lead["created_at"]).replace("Z", "+00:00"))
                applicant_data["application_date"] = created.date().isoformat()
            except (ValueError, AttributeError):
                pass

        # Add recruiter if assigned
        assigned_to = lead.get("assigned_to")
        if assigned_to:
            applicant_data["recruiter"] = str(assigned_to)

        # Create the applicant
        applicant = self.wellsky.create_applicant(applicant_data)

        if applicant:
            self._log_sync(
                "create",
                lead_id=lead_id,
                applicant_id=applicant.id,
                applicant_name=applicant.full_name
            )
            return True, applicant, f"Created applicant {applicant.id}"

        return False, None, "Failed to create applicant"

    def _update_applicant_from_lead(
        self,
        applicant: WellSkyApplicant,
        lead: Dict[str, Any]
    ) -> Tuple[bool, Optional[WellSkyApplicant], str]:
        """Update an existing applicant from lead data."""
        updates = {}

        # Map status to applicant status
        status = lead.get("status", "").lower().replace(" ", "_")
        new_status = STATUS_TO_APPLICANT_STATUS.get(status)

        if new_status and applicant.status != new_status:
            updates["status"] = new_status.value

        # Update phone if changed
        phone = lead.get("phone", "")
        if phone and phone != applicant.phone:
            updates["phone"] = phone

        # Update email if changed
        email = lead.get("email", "")
        if email and email != applicant.email:
            updates["email"] = email

        # Update notes if changed
        notes = lead.get("notes", "")
        if notes and notes != applicant.notes:
            updates["notes"] = notes

        if not updates:
            return True, applicant, "Applicant already up to date"

        updated = self.wellsky.update_applicant(applicant.id, updates)

        if updated:
            self._log_sync(
                "update",
                lead_id=str(lead.get("id", "")),
                applicant_id=applicant.id,
                updates=list(updates.keys())
            )
            return True, updated, f"Updated applicant {applicant.id}"

        return False, None, "Failed to update applicant"

    def _map_lead_source(self, source: str) -> str:
        """Map lead source to standardized source value."""
        source_lower = source.lower() if source else ""

        source_mapping = {
            "facebook": "indeed",  # Facebook leads often come from job ads
            "indeed": "indeed",
            "linkedin": "linkedin",
            "referral": "referral",
            "walk_in": "walk_in",
            "walk-in": "walk_in",
            "manual": "other",
            "website": "website",
        }

        return source_mapping.get(source_lower, "other")

    def _log_sync(self, action: str, **kwargs):
        """Log a sync action for audit trail."""
        entry = {
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self._sync_log.append(entry)
        logger.info(f"Recruiting→WellSky sync: {action} - {kwargs}")

    def get_sync_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent sync log entries."""
        return self._sync_log[-limit:]

    # =========================================================================
    # Status Query Methods
    # =========================================================================

    def get_unsynced_leads(
        self,
        leads: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get leads that don't have corresponding WellSky applicants.

        Useful for identifying leads that need initial sync.
        """
        unsynced = []

        for lead in leads:
            lead_id = str(lead.get("id", ""))
            applicant = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

            if not applicant:
                unsynced.append(lead)

        return unsynced

    def get_sync_status(self, lead_id: str) -> Dict[str, Any]:
        """
        Get the sync status for a specific lead.
        """
        applicant = self.wellsky.get_applicant_by_recruiting_lead_id(lead_id)

        if not applicant:
            return {
                "synced": False,
                "lead_id": lead_id,
                "applicant_id": None,
                "applicant_status": None,
                "message": "Lead not synced to WellSky"
            }

        return {
            "synced": True,
            "lead_id": lead_id,
            "applicant_id": applicant.id,
            "applicant_status": applicant.status.value,
            "applicant_name": applicant.full_name,
            "is_hired": applicant.is_hired,
            "converted_caregiver_id": applicant.converted_caregiver_id,
            "last_updated": applicant.updated_at.isoformat() if applicant.updated_at else None,
        }

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the recruiting pipeline in WellSky.
        """
        applicants = self.wellsky.get_applicants(limit=1000)

        summary = {
            "total": len(applicants),
            "by_status": {},
            "open": 0,
            "hired": 0,
            "rejected_withdrawn": 0,
        }

        for applicant in applicants:
            status = applicant.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

            if applicant.is_open:
                summary["open"] += 1
            elif applicant.status == ApplicantStatus.HIRED:
                summary["hired"] += 1
            else:
                summary["rejected_withdrawn"] += 1

        return summary


# =============================================================================
# Singleton Instance
# =============================================================================

recruiting_wellsky_sync = RecruitingWellSkySyncService()
