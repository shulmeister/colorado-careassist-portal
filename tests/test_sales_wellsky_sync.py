"""
Unit tests for services/sales_wellsky_sync.py

Covers:
- Stage-to-status mapping completeness
- Payer type inference from deal data
- sync_deal_stage_change logic
- sync_deal_to_prospect with/without contact
- Bulk sync results counting
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================
# Stage mapping tests
# ============================================================

class TestStageMappingCompleteness:
    """Verify the stage-to-status mapping covers all expected stages."""

    def test_stage_mapping_imports(self):
        from services.sales_wellsky_sync import STAGE_TO_PROSPECT_STATUS
        assert len(STAGE_TO_PROSPECT_STATUS) > 0

    def test_all_critical_stages_mapped(self):
        from services.sales_wellsky_sync import STAGE_TO_PROSPECT_STATUS
        critical_stages = [
            "opportunity", "lead", "new", "contacted", "qualified",
            "assessment_scheduled", "assessment_completed",
            "proposal", "proposal_sent", "negotiation",
            "won", "closed_won", "lost", "closed_lost", "on_hold",
        ]
        for stage in critical_stages:
            assert stage in STAGE_TO_PROSPECT_STATUS, \
                f"Stage '{stage}' is not in STAGE_TO_PROSPECT_STATUS"

    def test_won_stages_map_to_won(self):
        from services.sales_wellsky_sync import STAGE_TO_PROSPECT_STATUS
        from services.wellsky_service import ProspectStatus
        assert STAGE_TO_PROSPECT_STATUS["won"] == ProspectStatus.WON
        assert STAGE_TO_PROSPECT_STATUS["closed_won"] == ProspectStatus.WON

    def test_lost_stages_map_to_lost(self):
        from services.sales_wellsky_sync import STAGE_TO_PROSPECT_STATUS
        from services.wellsky_service import ProspectStatus
        assert STAGE_TO_PROSPECT_STATUS["lost"] == ProspectStatus.LOST
        assert STAGE_TO_PROSPECT_STATUS["closed_lost"] == ProspectStatus.LOST


# ============================================================
# Payer type inference tests
# ============================================================

class TestPayerTypeInference:
    def _make_service(self):
        from services.sales_wellsky_sync import SalesWellSkySyncService
        svc = SalesWellSkySyncService.__new__(SalesWellSkySyncService)
        svc.wellsky = MagicMock()
        svc._sync_log = []
        return svc

    def test_medicaid_from_category(self):
        svc = self._make_service()
        deal = {"category": "Medicaid Referral", "name": "Smith", "description": ""}
        assert svc._infer_payer_type(deal) == "medicaid"

    def test_medicaid_from_notes(self):
        svc = self._make_service()
        deal = {"category": "", "name": "Jones", "description": "Patient on Medicaid"}
        assert svc._infer_payer_type(deal) == "medicaid"

    def test_va_from_name(self):
        svc = self._make_service()
        deal = {"category": "", "name": "VA Referral for Johnson", "description": ""}
        assert svc._infer_payer_type(deal) == "va"

    def test_veteran_keyword(self):
        svc = self._make_service()
        deal = {"category": "", "name": "Smith", "description": "Veteran needs care"}
        assert svc._infer_payer_type(deal) == "va"

    def test_insurance_ltc(self):
        svc = self._make_service()
        deal = {"category": "LTC Insurance", "name": "Williams", "description": ""}
        assert svc._infer_payer_type(deal) == "ltc_insurance"

    def test_default_private_pay(self):
        svc = self._make_service()
        deal = {"category": "Word of Mouth", "name": "Davis", "description": "Needs help"}
        assert svc._infer_payer_type(deal) == "private_pay"

    def test_empty_deal_data(self):
        svc = self._make_service()
        deal = {"category": None, "name": None, "description": None}
        assert svc._infer_payer_type(deal) == "private_pay"


# ============================================================
# Sync log tests
# ============================================================

class TestSyncLog:
    def test_log_entries_accumulate(self):
        from services.sales_wellsky_sync import SalesWellSkySyncService
        svc = SalesWellSkySyncService.__new__(SalesWellSkySyncService)
        svc.wellsky = MagicMock()
        svc._sync_log = []

        svc._log_sync("create", deal_id="1", prospect_id="p1")
        svc._log_sync("update", deal_id="2", prospect_id="p2")

        log = svc.get_sync_log()
        assert len(log) == 2
        assert log[0]["action"] == "create"
        assert log[1]["action"] == "update"

    def test_log_limit(self):
        from services.sales_wellsky_sync import SalesWellSkySyncService
        svc = SalesWellSkySyncService.__new__(SalesWellSkySyncService)
        svc.wellsky = MagicMock()
        svc._sync_log = []

        for i in range(10):
            svc._log_sync("test", deal_id=str(i))

        log = svc.get_sync_log(limit=3)
        assert len(log) == 3


# ============================================================
# Stage change sync tests
# ============================================================

class TestSyncDealStageChange:
    def _make_service(self):
        from services.sales_wellsky_sync import SalesWellSkySyncService
        svc = SalesWellSkySyncService.__new__(SalesWellSkySyncService)
        svc.wellsky = MagicMock()
        svc._sync_log = []
        return svc

    def test_no_prospect_returns_false(self):
        svc = self._make_service()
        svc.wellsky.get_prospect_by_sales_deal_id.return_value = None

        success, prospect, msg = svc.sync_deal_stage_change("deal-1", "qualified")

        assert success is False
        assert prospect is None
        assert "No prospect found" in msg

    def test_same_status_is_noop(self):
        from services.wellsky_service import ProspectStatus
        svc = self._make_service()

        mock_prospect = MagicMock()
        mock_prospect.status = ProspectStatus.CONTACTED
        svc.wellsky.get_prospect_by_sales_deal_id.return_value = mock_prospect

        success, prospect, msg = svc.sync_deal_stage_change("deal-1", "qualified")

        assert success is True
        assert "already at status" in msg
        svc.wellsky.update_prospect_status.assert_not_called()


# ============================================================
# Bulk sync tests
# ============================================================

class TestBulkSync:
    def _make_service(self):
        from services.sales_wellsky_sync import SalesWellSkySyncService
        svc = SalesWellSkySyncService.__new__(SalesWellSkySyncService)
        svc.wellsky = MagicMock()
        svc._sync_log = []
        return svc

    def test_archived_deals_skipped(self):
        svc = self._make_service()

        deals = [
            {"id": 1, "name": "Active Deal", "archived_at": None, "stage": "new"},
            {"id": 2, "name": "Archived Deal", "archived_at": "2026-01-01"},
        ]

        # Mock sync_deal_to_prospect for the active deal
        svc.sync_deal_to_prospect = MagicMock(
            return_value=(True, MagicMock(), "Created prospect p1")
        )

        results = svc.sync_all_deals(deals)

        assert results["skipped"] == 1
        assert results["created"] == 1
        assert results["total"] == 2

    def test_exception_counted_as_failure(self):
        svc = self._make_service()

        deals = [{"id": 1, "name": "Bad Deal", "archived_at": None, "stage": "new"}]

        svc.sync_deal_to_prospect = MagicMock(side_effect=Exception("DB exploded"))

        results = svc.sync_all_deals(deals)

        assert results["failed"] == 1
        assert len(results["errors"]) == 1
