"""
Sales Dashboard → WellSky Prospect Sync Service

Synchronizes deals from the Sales Dashboard to WellSky prospects.
This enables the hub-and-spoke integration where:
- Sales Dashboard is the primary source for new sales opportunities
- WellSky is the central hub for operational data
- When a deal is won and paperwork is complete, prospect converts to client

Sync Logic:
1. New deal in Sales Dashboard → Create prospect in WellSky
2. Deal stage change → Update prospect status in WellSky
3. Deal won + GoFormz complete → Convert prospect to client in WellSky
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from services.wellsky_service import (
    wellsky_service,
    WellSkyProspect,
    ProspectStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Stage Mapping: Sales Dashboard → WellSky Prospect Status
# =============================================================================

# Map Sales Dashboard deal stages to WellSky prospect statuses
STAGE_TO_PROSPECT_STATUS = {
    # Sales Dashboard stages → WellSky ProspectStatus
    "opportunity": ProspectStatus.NEW,
    "lead": ProspectStatus.NEW,
    "new": ProspectStatus.NEW,
    "contacted": ProspectStatus.CONTACTED,
    "qualified": ProspectStatus.CONTACTED,
    "assessment_scheduled": ProspectStatus.ASSESSMENT_SCHEDULED,
    "assessment": ProspectStatus.ASSESSMENT_SCHEDULED,
    "assessment_completed": ProspectStatus.ASSESSMENT_COMPLETED,
    "proposal": ProspectStatus.PROPOSAL_SENT,
    "proposal_sent": ProspectStatus.PROPOSAL_SENT,
    "negotiation": ProspectStatus.NEGOTIATING,
    "negotiating": ProspectStatus.NEGOTIATING,
    "contract": ProspectStatus.NEGOTIATING,
    "won": ProspectStatus.WON,
    "closed_won": ProspectStatus.WON,
    "lost": ProspectStatus.LOST,
    "closed_lost": ProspectStatus.LOST,
    "on_hold": ProspectStatus.ON_HOLD,
}


class SalesWellSkySyncService:
    """
    Service for synchronizing Sales Dashboard deals with WellSky prospects.

    Provides bidirectional sync capabilities:
    - Push: Sales Dashboard → WellSky (primary direction)
    - Pull: WellSky → Sales Dashboard (for status updates)
    """

    def __init__(self):
        self.wellsky = wellsky_service
        self._sync_log: List[Dict[str, Any]] = []

    # =========================================================================
    # Core Sync Methods
    # =========================================================================

    def sync_deal_to_prospect(
        self,
        deal: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None,
        force_create: bool = False
    ) -> Tuple[bool, Optional[WellSkyProspect], str]:
        """
        Sync a Sales Dashboard deal to WellSky as a prospect.

        Args:
            deal: Deal dict from Sales Dashboard
            contact: Primary contact dict (optional, for additional info)
            force_create: If True, create even if already exists

        Returns:
            Tuple of (success, prospect_or_none, message)
        """
        deal_id = str(deal.get("id", ""))
        deal_name = deal.get("name", "Unknown Deal")

        if not deal_id:
            return False, None, "Deal ID is required"

        # Check if prospect already exists for this deal
        existing = self.wellsky.get_prospect_by_sales_deal_id(deal_id)

        if existing and not force_create:
            # Update existing prospect
            return self._update_prospect_from_deal(existing, deal, contact)

        # Create new prospect
        return self._create_prospect_from_deal(deal, contact)

    def sync_deal_stage_change(
        self,
        deal_id: str,
        new_stage: str,
        changed_by: Optional[str] = None
    ) -> Tuple[bool, Optional[WellSkyProspect], str]:
        """
        Sync a deal stage change to WellSky prospect status.

        Called when a deal moves to a new stage in Sales Dashboard.
        """
        # Find existing prospect
        prospect = self.wellsky.get_prospect_by_sales_deal_id(deal_id)

        if not prospect:
            logger.warning(f"No prospect found for deal {deal_id} - skipping stage sync")
            return False, None, f"No prospect found for deal {deal_id}"

        # Map stage to prospect status
        new_status = STAGE_TO_PROSPECT_STATUS.get(
            new_stage.lower().replace(" ", "_"),
            ProspectStatus.NEW
        )

        if prospect.status == new_status:
            return True, prospect, f"Prospect already at status {new_status.value}"

        # Update the prospect status
        notes = f"Stage changed to {new_stage}"
        if changed_by:
            notes += f" by {changed_by}"

        updated = self.wellsky.update_prospect_status(
            prospect.id,
            new_status,
            notes=notes
        )

        if updated:
            self._log_sync(
                "stage_change",
                deal_id=deal_id,
                prospect_id=prospect.id,
                from_status=prospect.status.value,
                to_status=new_status.value
            )
            return True, updated, f"Updated prospect status to {new_status.value}"

        return False, None, "Failed to update prospect status"

    def sync_deal_won(
        self,
        deal_id: str,
        client_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Any], str]:
        """
        Handle a deal being won - mark prospect as won.

        Note: Actual conversion to client happens when GoFormz paperwork
        is completed (see GoFormzWellSkySyncService).
        """
        prospect = self.wellsky.get_prospect_by_sales_deal_id(deal_id)

        if not prospect:
            return False, None, f"No prospect found for deal {deal_id}"

        # Update status to WON
        updated = self.wellsky.update_prospect_status(
            prospect.id,
            ProspectStatus.WON,
            notes="Deal closed won in Sales Dashboard"
        )

        if updated:
            self._log_sync(
                "deal_won",
                deal_id=deal_id,
                prospect_id=prospect.id
            )
            return True, updated, "Prospect marked as won - awaiting paperwork for client conversion"

        return False, None, "Failed to mark prospect as won"

    def sync_deal_lost(
        self,
        deal_id: str,
        lost_reason: str = ""
    ) -> Tuple[bool, Optional[WellSkyProspect], str]:
        """
        Handle a deal being lost.
        """
        prospect = self.wellsky.get_prospect_by_sales_deal_id(deal_id)

        if not prospect:
            return False, None, f"No prospect found for deal {deal_id}"

        updated = self.wellsky.update_prospect_status(
            prospect.id,
            ProspectStatus.LOST,
            notes=lost_reason or "Deal lost in Sales Dashboard"
        )

        if updated:
            self._log_sync(
                "deal_lost",
                deal_id=deal_id,
                prospect_id=prospect.id,
                reason=lost_reason
            )
            return True, updated, "Prospect marked as lost"

        return False, None, "Failed to mark prospect as lost"

    # =========================================================================
    # Bulk Sync Methods
    # =========================================================================

    def sync_all_deals(
        self,
        deals: List[Dict[str, Any]],
        contacts_by_id: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Sync all deals from Sales Dashboard to WellSky.

        Args:
            deals: List of deal dicts from Sales Dashboard
            contacts_by_id: Optional dict mapping contact ID to contact dict

        Returns:
            Summary of sync results
        """
        results = {
            "total": len(deals),
            "created": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        contacts_by_id = contacts_by_id or {}

        for deal in deals:
            try:
                # Get primary contact if available
                contact = None
                primary_contact_id = deal.get("primary_contact_id")
                if primary_contact_id and primary_contact_id in contacts_by_id:
                    contact = contacts_by_id[primary_contact_id]

                # Skip archived deals
                if deal.get("archived_at"):
                    results["skipped"] += 1
                    continue

                success, prospect, message = self.sync_deal_to_prospect(deal, contact)

                if success:
                    if "Created" in message:
                        results["created"] += 1
                    else:
                        results["updated"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "deal_id": deal.get("id"),
                        "deal_name": deal.get("name"),
                        "error": message
                    })

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "deal_id": deal.get("id"),
                    "deal_name": deal.get("name"),
                    "error": str(e)
                })
                logger.exception(f"Error syncing deal {deal.get('id')}: {e}")

        logger.info(f"Bulk sync complete: {results['created']} created, "
                   f"{results['updated']} updated, {results['failed']} failed")

        return results

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_prospect_from_deal(
        self,
        deal: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[WellSkyProspect], str]:
        """Create a new prospect from a deal."""
        deal_id = str(deal.get("id", ""))

        # Extract contact info (prefer contact dict, fallback to deal name parsing)
        if contact:
            first_name = contact.get("first_name", "")
            last_name = contact.get("last_name", "")
            phone = contact.get("phone", "")
            email = contact.get("email", "")
            address = contact.get("address", "")

            # Parse name if first/last not available
            if not first_name and contact.get("name"):
                parts = contact.get("name", "").split(None, 1)
                first_name = parts[0] if parts else ""
                last_name = parts[1] if len(parts) > 1 else ""
        else:
            # Use deal name as prospect name
            parts = deal.get("name", "Unknown").split(None, 1)
            first_name = parts[0] if parts else "Unknown"
            last_name = parts[1] if len(parts) > 1 else ""
            phone = ""
            email = ""
            address = ""

        # Map deal stage to prospect status
        stage = deal.get("stage", "opportunity").lower().replace(" ", "_")
        status = STAGE_TO_PROSPECT_STATUS.get(stage, ProspectStatus.NEW)

        # Build prospect data
        prospect_data = {
            "first_name": first_name,
            "last_name": last_name,
            "status": status.value,
            "phone": phone,
            "email": email,
            "address": address,
            "city": contact.get("city", "") if contact else "",
            "state": contact.get("state", "CO") if contact else "CO",
            "referral_source": deal.get("category", ""),
            "estimated_hours_weekly": deal.get("est_weekly_hours", 0) or 0,
            "payer_type": self._infer_payer_type(deal),
            "sales_rep": "",  # Could be populated from deal owner
            "proposal_amount": deal.get("amount", 0) or 0,
            "notes": deal.get("description", ""),
            "sales_dashboard_deal_id": deal_id,
        }

        # Handle dates
        if deal.get("created_at"):
            try:
                created = datetime.fromisoformat(deal["created_at"].replace("Z", "+00:00"))
                prospect_data["referral_date"] = created.date().isoformat()
            except (ValueError, AttributeError):
                pass

        if status == ProspectStatus.PROPOSAL_SENT and deal.get("stage_entered_at"):
            try:
                entered = datetime.fromisoformat(deal["stage_entered_at"].replace("Z", "+00:00"))
                prospect_data["proposal_date"] = entered.date().isoformat()
            except (ValueError, AttributeError):
                pass

        # Create the prospect
        prospect = self.wellsky.create_prospect(prospect_data)

        if prospect:
            self._log_sync(
                "create",
                deal_id=deal_id,
                prospect_id=prospect.id,
                prospect_name=prospect.full_name
            )
            return True, prospect, f"Created prospect {prospect.id}"

        return False, None, "Failed to create prospect"

    def _update_prospect_from_deal(
        self,
        prospect: WellSkyProspect,
        deal: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[WellSkyProspect], str]:
        """Update an existing prospect from deal data."""
        updates = {}

        # Map deal stage to prospect status
        stage = deal.get("stage", "").lower().replace(" ", "_")
        new_status = STAGE_TO_PROSPECT_STATUS.get(stage)

        if new_status and prospect.status != new_status:
            updates["status"] = new_status.value

        # Update amount if changed
        amount = deal.get("amount", 0) or 0
        if amount != prospect.proposal_amount:
            updates["proposal_amount"] = amount

        # Update hours if changed
        hours = deal.get("est_weekly_hours", 0) or 0
        if hours != prospect.estimated_hours_weekly:
            updates["estimated_hours_weekly"] = hours

        # Update notes/description
        description = deal.get("description", "")
        if description and description != prospect.notes:
            updates["notes"] = description

        if not updates:
            return True, prospect, "Prospect already up to date"

        updated = self.wellsky.update_prospect(prospect.id, updates)

        if updated:
            self._log_sync(
                "update",
                deal_id=str(deal.get("id", "")),
                prospect_id=prospect.id,
                updates=list(updates.keys())
            )
            return True, updated, f"Updated prospect {prospect.id}"

        return False, None, "Failed to update prospect"

    def _infer_payer_type(self, deal: Dict[str, Any]) -> str:
        """Infer payer type from deal data."""
        category = (deal.get("category") or "").lower()
        name = (deal.get("name") or "").lower()
        notes = (deal.get("description") or "").lower()

        combined = f"{category} {name} {notes}"

        if "medicaid" in combined:
            return "medicaid"
        elif "va" in combined or "veteran" in combined:
            return "va"
        elif "insurance" in combined or "ltc" in combined:
            return "ltc_insurance"
        else:
            return "private_pay"

    def _log_sync(self, action: str, **kwargs):
        """Log a sync action for audit trail."""
        entry = {
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self._sync_log.append(entry)
        logger.info(f"Sales→WellSky sync: {action} - {kwargs}")

    def get_sync_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent sync log entries."""
        return self._sync_log[-limit:]

    # =========================================================================
    # Status Query Methods
    # =========================================================================

    def get_unsynced_deals(
        self,
        deals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get deals that don't have corresponding WellSky prospects.

        Useful for identifying deals that need initial sync.
        """
        unsynced = []

        for deal in deals:
            deal_id = str(deal.get("id", ""))
            prospect = self.wellsky.get_prospect_by_sales_deal_id(deal_id)

            if not prospect:
                unsynced.append(deal)

        return unsynced

    def get_sync_status(self, deal_id: str) -> Dict[str, Any]:
        """
        Get the sync status for a specific deal.
        """
        prospect = self.wellsky.get_prospect_by_sales_deal_id(deal_id)

        if not prospect:
            return {
                "synced": False,
                "deal_id": deal_id,
                "prospect_id": None,
                "prospect_status": None,
                "message": "Deal not synced to WellSky"
            }

        return {
            "synced": True,
            "deal_id": deal_id,
            "prospect_id": prospect.id,
            "prospect_status": prospect.status.value,
            "prospect_name": prospect.full_name,
            "is_converted": prospect.is_converted,
            "converted_client_id": prospect.converted_client_id,
            "last_updated": prospect.updated_at.isoformat() if prospect.updated_at else None,
        }


# =============================================================================
# Singleton Instance
# =============================================================================

sales_wellsky_sync = SalesWellSkySyncService()
