"""
GoFormz → WellSky Status Triggers Service

Handles paperwork completion triggers for WellSky status updates.
This is the final step in the hub-and-spoke integration where:
- Completed Client Packets trigger prospect → client conversion in WellSky
- Completed Employee Packets trigger applicant → caregiver conversion in WellSky

This service acts as the bridge between GoFormz signed paperwork and WellSky
operational records, ensuring compliance documentation is complete before
activating clients or caregivers.

Workflow:
1. Poll GoFormz for completed submissions
2. Match submissions to WellSky prospects/applicants
3. Trigger conversions when paperwork is complete
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Tuple

from services.wellsky_service import (
    wellsky_service,
    WellSkyProspect,
    WellSkyApplicant,
    WellSkyClient,
    WellSkyCaregiver,
    ProspectStatus,
    ApplicantStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Form Type Detection
# =============================================================================

# Keywords to identify client vs employee forms
CLIENT_FORM_KEYWORDS = [
    "client packet",
    "client paperwork",
    "service agreement",
    "care agreement",
    "client intake",
    "patient intake",
    "home care agreement",
    "admission",
]

EMPLOYEE_FORM_KEYWORDS = [
    "employee packet",
    "caregiver packet",
    "employee paperwork",
    "caregiver paperwork",
    "new hire",
    "onboarding",
    "w4",
    "i9",
    "employment agreement",
    "employee handbook",
    "caregiver agreement",
]


class GoFormzWellSkySyncService:
    """
    Service for triggering WellSky status updates from GoFormz completions.

    Handles the critical paperwork → activation workflow:
    - Client Packet signed → Prospect becomes Client
    - Employee Packet signed → Applicant becomes Caregiver
    """

    def __init__(self):
        self.wellsky = wellsky_service
        self._sync_log: List[Dict[str, Any]] = []
        self._goformz_service = None

    @property
    def goformz(self):
        """Lazy load GoFormz service."""
        if self._goformz_service is None:
            try:
                # Import from sales dashboard
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sales'))
                from goformz_service import GoFormzService
                self._goformz_service = GoFormzService()
            except ImportError:
                logger.warning("GoFormz service not available")
                self._goformz_service = None
        return self._goformz_service

    # =========================================================================
    # Client Packet Processing
    # =========================================================================

    def process_completed_client_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Process completed client packets and convert prospects to clients.

        Args:
            since: Only process submissions completed after this time

        Returns:
            Summary of processing results
        """
        results = {
            "total_submissions": 0,
            "matched_prospects": 0,
            "converted_to_clients": 0,
            "already_converted": 0,
            "no_match": 0,
            "errors": [],
        }

        if not self.goformz or not self.goformz.enabled:
            logger.warning("GoFormz service not available, using mock mode")
            # In mock mode, simulate processing
            return self._mock_process_client_packets()

        # Get completed client packets from GoFormz
        packets_result = self.goformz.get_completed_client_packets(since=since)

        if not packets_result.get("success"):
            results["errors"].append(packets_result.get("error", "Failed to fetch packets"))
            return results

        submissions = packets_result.get("submissions", [])
        results["total_submissions"] = len(submissions)

        for submission in submissions:
            try:
                success, message = self._process_client_submission(submission)

                if "converted" in message.lower():
                    results["converted_to_clients"] += 1
                    results["matched_prospects"] += 1
                elif "already" in message.lower():
                    results["already_converted"] += 1
                    results["matched_prospects"] += 1
                elif "no match" in message.lower() or "not found" in message.lower():
                    results["no_match"] += 1
                else:
                    results["matched_prospects"] += 1

            except Exception as e:
                results["errors"].append({
                    "submission_id": submission.get("id"),
                    "error": str(e)
                })
                logger.exception(f"Error processing client submission: {e}")

        logger.info(f"Processed {results['total_submissions']} client packets, "
                   f"converted {results['converted_to_clients']} to clients")

        return results

    def _process_client_submission(
        self,
        submission: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Process a single client packet submission."""
        submission_id = submission.get("id", "")

        # Extract customer data from submission
        if self.goformz:
            customer_data = self.goformz.extract_customer_data_from_submission(submission)
        else:
            customer_data = self._extract_customer_data(submission)

        # Try to match to a WellSky prospect
        prospect = self._find_matching_prospect(customer_data, submission)

        if not prospect:
            self._log_sync(
                "client_packet_no_match",
                submission_id=submission_id,
                customer_data=customer_data
            )
            return False, "No matching prospect found"

        # Check if already converted
        if prospect.is_converted:
            return True, f"Prospect {prospect.id} already converted to client {prospect.converted_client_id}"

        # Check if prospect is in WON status
        if prospect.status != ProspectStatus.WON:
            # Update to WON first since paperwork is signed
            self.wellsky.update_prospect_status(
                prospect.id,
                ProspectStatus.WON,
                notes=f"Client packet signed (GoFormz submission {submission_id})"
            )

        # Convert prospect to client
        client = self.wellsky.convert_prospect_to_client(
            prospect.id,
            client_data={
                "start_date": date.today().isoformat(),
                "notes": f"Activated via GoFormz submission {submission_id}",
            }
        )

        if client:
            # Update prospect with GoFormz submission ID
            self.wellsky.update_prospect(prospect.id, {
                "goformz_submission_id": submission_id
            })

            self._log_sync(
                "client_converted",
                submission_id=submission_id,
                prospect_id=prospect.id,
                client_id=client.id,
                client_name=client.full_name
            )
            return True, f"Converted prospect {prospect.id} to client {client.id}"

        return False, "Failed to convert prospect to client"

    def _find_matching_prospect(
        self,
        customer_data: Dict[str, Any],
        submission: Dict[str, Any]
    ) -> Optional[WellSkyProspect]:
        """Find a WellSky prospect matching the GoFormz submission data."""
        # Strategy 1: Match by linked sales deal ID (if available in submission)
        deal_id = submission.get("data", {}).get("deal_id") or \
                  submission.get("data", {}).get("sales_deal_id")
        if deal_id:
            prospect = self.wellsky.get_prospect_by_sales_deal_id(str(deal_id))
            if prospect:
                return prospect

        # Strategy 2: Match by email
        email = customer_data.get("email", "").lower()
        if email:
            prospects = self.wellsky.get_prospects(limit=1000)
            for prospect in prospects:
                if prospect.email.lower() == email and prospect.is_open:
                    return prospect

        # Strategy 3: Match by phone
        phone = customer_data.get("phone", "")
        if phone:
            import re
            clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
            if clean_phone:
                prospects = self.wellsky.get_prospects(limit=1000)
                for prospect in prospects:
                    prospect_phone = re.sub(r'[^\d]', '', prospect.phone)[-10:]
                    if prospect_phone == clean_phone and prospect.is_open:
                        return prospect

        # Strategy 4: Match by name
        first_name = customer_data.get("first_name", "").lower()
        last_name = customer_data.get("last_name", "").lower()
        if first_name and last_name:
            prospects = self.wellsky.get_prospects(limit=1000)
            for prospect in prospects:
                if (prospect.first_name.lower() == first_name and
                    prospect.last_name.lower() == last_name and
                    prospect.is_open):
                    return prospect

        return None

    # =========================================================================
    # Employee Packet Processing
    # =========================================================================

    def process_completed_employee_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Process completed employee packets and convert applicants to caregivers.

        Args:
            since: Only process submissions completed after this time

        Returns:
            Summary of processing results
        """
        results = {
            "total_submissions": 0,
            "matched_applicants": 0,
            "converted_to_caregivers": 0,
            "already_converted": 0,
            "no_match": 0,
            "errors": [],
        }

        if not self.goformz or not self.goformz.enabled:
            logger.warning("GoFormz service not available, using mock mode")
            return self._mock_process_employee_packets()

        # Get completed employee packets from GoFormz
        packets_result = self._get_completed_employee_packets(since=since)

        if not packets_result.get("success"):
            results["errors"].append(packets_result.get("error", "Failed to fetch packets"))
            return results

        submissions = packets_result.get("submissions", [])
        results["total_submissions"] = len(submissions)

        for submission in submissions:
            try:
                success, message = self._process_employee_submission(submission)

                if "converted" in message.lower():
                    results["converted_to_caregivers"] += 1
                    results["matched_applicants"] += 1
                elif "already" in message.lower():
                    results["already_converted"] += 1
                    results["matched_applicants"] += 1
                elif "no match" in message.lower() or "not found" in message.lower():
                    results["no_match"] += 1
                else:
                    results["matched_applicants"] += 1

            except Exception as e:
                results["errors"].append({
                    "submission_id": submission.get("id"),
                    "error": str(e)
                })
                logger.exception(f"Error processing employee submission: {e}")

        logger.info(f"Processed {results['total_submissions']} employee packets, "
                   f"converted {results['converted_to_caregivers']} to caregivers")

        return results

    def _get_completed_employee_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get completed employee/caregiver packets from GoFormz."""
        if not self.goformz:
            return {"success": False, "error": "GoFormz not available"}

        try:
            # Get all forms
            forms_result = self.goformz.get_forms(limit=1000)
            if not forms_result.get('success'):
                return forms_result

            forms = forms_result.get('forms', {}).get('data', [])

            # Find employee/caregiver forms
            employee_forms = []
            for form in forms:
                form_name = form.get('name', '').lower()
                if any(keyword in form_name for keyword in EMPLOYEE_FORM_KEYWORDS):
                    employee_forms.append(form)

            if not employee_forms:
                return {"success": True, "submissions": [], "message": "No employee forms found"}

            # Get completed submissions
            all_submissions = []
            for form in employee_forms:
                form_id = form.get('id')
                submissions_result = self.goformz.get_form_submissions(
                    form_id=form_id,
                    limit=1000,
                    since=since
                )
                if submissions_result.get('success'):
                    submissions = submissions_result.get('submissions', {}).get('data', [])
                    completed = [s for s in submissions
                               if s.get('status', '').lower() in ['completed', 'submitted', 'signed']]
                    all_submissions.extend(completed)

            return {"success": True, "submissions": all_submissions}

        except Exception as e:
            logger.error(f"Failed to get employee packets: {e}")
            return {"success": False, "error": str(e)}

    def _process_employee_submission(
        self,
        submission: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Process a single employee packet submission."""
        submission_id = submission.get("id", "")

        # Extract employee data from submission
        employee_data = self._extract_employee_data(submission)

        # Try to match to a WellSky applicant
        applicant = self._find_matching_applicant(employee_data, submission)

        if not applicant:
            self._log_sync(
                "employee_packet_no_match",
                submission_id=submission_id,
                employee_data=employee_data
            )
            return False, "No matching applicant found"

        # Check if already converted
        if applicant.is_hired and applicant.converted_caregiver_id:
            return True, f"Applicant {applicant.id} already converted to caregiver {applicant.converted_caregiver_id}"

        # Check if applicant is in HIRED status
        if applicant.status != ApplicantStatus.HIRED:
            # Update to HIRED first since paperwork is signed
            self.wellsky.update_applicant_status(
                applicant.id,
                ApplicantStatus.HIRED,
                notes=f"Employee packet signed (GoFormz submission {submission_id})"
            )

        # Convert applicant to caregiver
        caregiver = self.wellsky.convert_applicant_to_caregiver(
            applicant.id,
            caregiver_data={
                "hire_date": date.today().isoformat(),
                "notes": f"Activated via GoFormz submission {submission_id}",
            }
        )

        if caregiver:
            # Update applicant with GoFormz submission ID
            self.wellsky.update_applicant(applicant.id, {
                "goformz_submission_id": submission_id
            })

            self._log_sync(
                "caregiver_converted",
                submission_id=submission_id,
                applicant_id=applicant.id,
                caregiver_id=caregiver.id,
                caregiver_name=caregiver.full_name
            )
            return True, f"Converted applicant {applicant.id} to caregiver {caregiver.id}"

        return False, "Failed to convert applicant to caregiver"

    def _find_matching_applicant(
        self,
        employee_data: Dict[str, Any],
        submission: Dict[str, Any]
    ) -> Optional[WellSkyApplicant]:
        """Find a WellSky applicant matching the GoFormz submission data."""
        # Strategy 1: Match by linked recruiting lead ID (if available)
        lead_id = submission.get("data", {}).get("lead_id") or \
                  submission.get("data", {}).get("recruiting_lead_id")
        if lead_id:
            applicant = self.wellsky.get_applicant_by_recruiting_lead_id(str(lead_id))
            if applicant:
                return applicant

        # Strategy 2: Match by email
        email = employee_data.get("email", "").lower()
        if email:
            applicants = self.wellsky.get_applicants(limit=1000)
            for applicant in applicants:
                if applicant.email.lower() == email and applicant.is_open:
                    return applicant

        # Strategy 3: Match by phone
        phone = employee_data.get("phone", "")
        if phone:
            import re
            clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
            if clean_phone:
                applicants = self.wellsky.get_applicants(limit=1000)
                for applicant in applicants:
                    applicant_phone = re.sub(r'[^\d]', '', applicant.phone)[-10:]
                    if applicant_phone == clean_phone and applicant.is_open:
                        return applicant

        # Strategy 4: Match by name
        first_name = employee_data.get("first_name", "").lower()
        last_name = employee_data.get("last_name", "").lower()
        if first_name and last_name:
            applicants = self.wellsky.get_applicants(limit=1000)
            for applicant in applicants:
                if (applicant.first_name.lower() == first_name and
                    applicant.last_name.lower() == last_name and
                    applicant.is_open):
                    return applicant

        return None

    def _extract_employee_data(
        self,
        submission: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract employee data from a GoFormz submission."""
        form_data = submission.get('data', {})

        # Common field name variations for employee forms
        email = (
            form_data.get('email') or
            form_data.get('Email') or
            form_data.get('employee_email') or
            form_data.get('Employee Email') or
            ''
        ).strip()

        first_name = (
            form_data.get('first_name') or
            form_data.get('First Name') or
            form_data.get('firstName') or
            form_data.get('employee_first_name') or
            ''
        ).strip()

        last_name = (
            form_data.get('last_name') or
            form_data.get('Last Name') or
            form_data.get('lastName') or
            form_data.get('employee_last_name') or
            ''
        ).strip()

        # Try full name if parts not found
        if not first_name and not last_name:
            full_name = (
                form_data.get('name') or
                form_data.get('Name') or
                form_data.get('employee_name') or
                form_data.get('Employee Name') or
                ''
            ).strip()
            if full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0] if parts else ''
                last_name = parts[1] if len(parts) > 1 else ''

        phone = (
            form_data.get('phone') or
            form_data.get('Phone') or
            form_data.get('employee_phone') or
            form_data.get('mobile') or
            ''
        ).strip()

        return {
            'email': email.lower() if email else '',
            'first_name': first_name,
            'last_name': last_name,
            'name': f"{first_name} {last_name}".strip() or email,
            'phone': phone,
            'source': 'GoFormz Employee Packet',
        }

    def _extract_customer_data(
        self,
        submission: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract customer data from a GoFormz submission (fallback)."""
        form_data = submission.get('data', {})

        email = (
            form_data.get('email') or
            form_data.get('Email') or
            form_data.get('client_email') or
            ''
        ).strip()

        first_name = (
            form_data.get('first_name') or
            form_data.get('First Name') or
            form_data.get('client_first_name') or
            ''
        ).strip()

        last_name = (
            form_data.get('last_name') or
            form_data.get('Last Name') or
            form_data.get('client_last_name') or
            ''
        ).strip()

        if not first_name and not last_name:
            full_name = (
                form_data.get('name') or
                form_data.get('Name') or
                form_data.get('client_name') or
                ''
            ).strip()
            if full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0] if parts else ''
                last_name = parts[1] if len(parts) > 1 else ''

        phone = (
            form_data.get('phone') or
            form_data.get('Phone') or
            form_data.get('client_phone') or
            ''
        ).strip()

        return {
            'email': email.lower() if email else '',
            'first_name': first_name,
            'last_name': last_name,
            'name': f"{first_name} {last_name}".strip() or email,
            'phone': phone,
            'source': 'GoFormz Client Packet',
        }

    # =========================================================================
    # Combined Processing
    # =========================================================================

    def process_all_completed_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Process all completed packets (both client and employee).

        This is the main entry point for scheduled jobs.
        """
        results = {
            "client_packets": {},
            "employee_packets": {},
            "total_conversions": 0,
            "processed_at": datetime.utcnow().isoformat(),
        }

        # Process client packets
        client_results = self.process_completed_client_packets(since=since)
        results["client_packets"] = client_results
        results["total_conversions"] += client_results.get("converted_to_clients", 0)

        # Process employee packets
        employee_results = self.process_completed_employee_packets(since=since)
        results["employee_packets"] = employee_results
        results["total_conversions"] += employee_results.get("converted_to_caregivers", 0)

        logger.info(f"Total conversions: {results['total_conversions']} "
                   f"({client_results.get('converted_to_clients', 0)} clients, "
                   f"{employee_results.get('converted_to_caregivers', 0)} caregivers)")

        return results

    # =========================================================================
    # Manual Conversion Methods
    # =========================================================================

    def manually_convert_prospect_to_client(
        self,
        prospect_id: str,
        goformz_submission_id: Optional[str] = None,
        notes: str = ""
    ) -> Tuple[bool, Optional[WellSkyClient], str]:
        """
        Manually trigger prospect to client conversion.

        Use when paperwork was completed outside GoFormz or needs manual override.
        """
        prospect = self.wellsky.get_prospect(prospect_id)

        if not prospect:
            return False, None, f"Prospect {prospect_id} not found"

        if prospect.is_converted:
            client = self.wellsky.get_client(prospect.converted_client_id)
            return True, client, f"Prospect already converted to client {prospect.converted_client_id}"

        # Ensure status is WON
        if prospect.status != ProspectStatus.WON:
            self.wellsky.update_prospect_status(
                prospect_id,
                ProspectStatus.WON,
                notes=notes or "Manually marked as won for conversion"
            )

        # Convert to client
        client = self.wellsky.convert_prospect_to_client(
            prospect_id,
            client_data={
                "start_date": date.today().isoformat(),
                "notes": notes or "Manually converted",
            }
        )

        if client:
            if goformz_submission_id:
                self.wellsky.update_prospect(prospect_id, {
                    "goformz_submission_id": goformz_submission_id
                })

            self._log_sync(
                "manual_client_conversion",
                prospect_id=prospect_id,
                client_id=client.id,
                notes=notes
            )
            return True, client, f"Successfully converted to client {client.id}"

        return False, None, "Failed to convert prospect to client"

    def manually_convert_applicant_to_caregiver(
        self,
        applicant_id: str,
        goformz_submission_id: Optional[str] = None,
        notes: str = ""
    ) -> Tuple[bool, Optional[WellSkyCaregiver], str]:
        """
        Manually trigger applicant to caregiver conversion.

        Use when paperwork was completed outside GoFormz or needs manual override.
        """
        applicant = self.wellsky.get_applicant(applicant_id)

        if not applicant:
            return False, None, f"Applicant {applicant_id} not found"

        if applicant.is_hired and applicant.converted_caregiver_id:
            caregiver = self.wellsky.get_caregiver(applicant.converted_caregiver_id)
            return True, caregiver, f"Applicant already converted to caregiver {applicant.converted_caregiver_id}"

        # Ensure status is HIRED
        if applicant.status != ApplicantStatus.HIRED:
            self.wellsky.update_applicant_status(
                applicant_id,
                ApplicantStatus.HIRED,
                notes=notes or "Manually marked as hired for conversion"
            )

        # Convert to caregiver
        caregiver = self.wellsky.convert_applicant_to_caregiver(
            applicant_id,
            caregiver_data={
                "hire_date": date.today().isoformat(),
                "notes": notes or "Manually converted",
            }
        )

        if caregiver:
            if goformz_submission_id:
                self.wellsky.update_applicant(applicant_id, {
                    "goformz_submission_id": goformz_submission_id
                })

            self._log_sync(
                "manual_caregiver_conversion",
                applicant_id=applicant_id,
                caregiver_id=caregiver.id,
                notes=notes
            )
            return True, caregiver, f"Successfully converted to caregiver {caregiver.id}"

        return False, None, "Failed to convert applicant to caregiver"

    # =========================================================================
    # Mock Mode Methods
    # =========================================================================

    def _mock_process_client_packets(self) -> Dict[str, Any]:
        """Mock processing for development/testing."""
        logger.info("Mock: Processing client packets")

        # In mock mode, find any WON prospects and simulate conversion
        prospects = self.wellsky.get_prospects(status=ProspectStatus.WON)

        results = {
            "total_submissions": len(prospects),
            "matched_prospects": 0,
            "converted_to_clients": 0,
            "already_converted": 0,
            "no_match": 0,
            "errors": [],
            "mock_mode": True,
        }

        for prospect in prospects:
            if prospect.is_converted:
                results["already_converted"] += 1
            else:
                # Simulate conversion
                client = self.wellsky.convert_prospect_to_client(
                    prospect.id,
                    client_data={"start_date": date.today().isoformat()}
                )
                if client:
                    results["converted_to_clients"] += 1
                    results["matched_prospects"] += 1

        return results

    def _mock_process_employee_packets(self) -> Dict[str, Any]:
        """Mock processing for development/testing."""
        logger.info("Mock: Processing employee packets")

        # In mock mode, find any HIRED applicants and simulate conversion
        applicants = self.wellsky.get_applicants(status=ApplicantStatus.HIRED)

        results = {
            "total_submissions": len(applicants),
            "matched_applicants": 0,
            "converted_to_caregivers": 0,
            "already_converted": 0,
            "no_match": 0,
            "errors": [],
            "mock_mode": True,
        }

        for applicant in applicants:
            if applicant.is_hired and applicant.converted_caregiver_id:
                results["already_converted"] += 1
            else:
                # Simulate conversion
                caregiver = self.wellsky.convert_applicant_to_caregiver(
                    applicant.id,
                    caregiver_data={"hire_date": date.today().isoformat()}
                )
                if caregiver:
                    results["converted_to_caregivers"] += 1
                    results["matched_applicants"] += 1

        return results

    # =========================================================================
    # Single Packet Processing (for Webhook Events)
    # =========================================================================

    def process_single_client_packet(
        self,
        packet_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a single client packet from a webhook event.

        Args:
            packet_info: Dict with submission_id, form_name, and optional payload

        Returns:
            Result dict with success status and details
        """
        submission_id = packet_info.get('submission_id')
        form_name = packet_info.get('form_name', 'client packet')
        payload = packet_info.get('payload', {})

        result = {
            "submission_id": submission_id,
            "form_type": "client_packet",
            "success": False,
            "message": "",
        }

        try:
            # Extract customer data from payload
            item = payload.get('Item', {})
            form_data = payload.get('formData', {}) or item.get('formData', {})

            # Build submission-like dict for _extract_customer_data
            submission = {'data': form_data}
            customer_data = self._extract_customer_data(submission)

            if not customer_data.get('email') and not customer_data.get('phone'):
                # Try to get from payload directly
                customer_data = {
                    'email': payload.get('email', ''),
                    'first_name': payload.get('firstName', '') or payload.get('first_name', ''),
                    'last_name': payload.get('lastName', '') or payload.get('last_name', ''),
                    'phone': payload.get('phone', ''),
                }

            # Find matching prospect
            prospect = self._find_matching_prospect(customer_data, {'data': form_data})

            if not prospect:
                result["message"] = "No matching prospect found"
                self._log_sync("client_packet_no_match", submission_id=submission_id)
                return result

            if prospect.is_converted:
                result["success"] = True
                result["message"] = f"Prospect already converted to client {prospect.converted_client_id}"
                result["client_id"] = prospect.converted_client_id
                return result

            # Convert prospect to client
            success, message = self._process_client_packet_match(
                prospect, submission_id
            )
            result["success"] = success
            result["message"] = message
            if success:
                # Refresh to get client ID
                prospect = self.wellsky.get_prospect(prospect.id)
                result["client_id"] = prospect.converted_client_id if prospect else None

        except Exception as e:
            logger.exception(f"Error processing client packet {submission_id}: {e}")
            result["message"] = str(e)
            result["error"] = str(e)

        return result

    def process_single_employee_packet(
        self,
        packet_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a single employee packet from a webhook event.

        Args:
            packet_info: Dict with submission_id, form_name, and optional payload

        Returns:
            Result dict with success status and details
        """
        submission_id = packet_info.get('submission_id')
        form_name = packet_info.get('form_name', 'employee packet')
        payload = packet_info.get('payload', {})

        result = {
            "submission_id": submission_id,
            "form_type": "employee_packet",
            "success": False,
            "message": "",
        }

        try:
            # Extract employee data from payload
            item = payload.get('Item', {})
            form_data = payload.get('formData', {}) or item.get('formData', {})

            # Build submission-like dict for _extract_employee_data
            submission = {'data': form_data}
            employee_data = self._extract_employee_data(submission)

            if not employee_data.get('email') and not employee_data.get('phone'):
                # Try to get from payload directly
                employee_data = {
                    'email': payload.get('email', ''),
                    'first_name': payload.get('firstName', '') or payload.get('first_name', ''),
                    'last_name': payload.get('lastName', '') or payload.get('last_name', ''),
                    'phone': payload.get('phone', ''),
                }

            # Find matching applicant
            applicant = self._find_matching_applicant(employee_data, {'data': form_data})

            if not applicant:
                result["message"] = "No matching applicant found"
                self._log_sync("employee_packet_no_match", submission_id=submission_id)
                return result

            if applicant.converted_caregiver_id:
                result["success"] = True
                result["message"] = f"Applicant already converted to caregiver {applicant.converted_caregiver_id}"
                result["caregiver_id"] = applicant.converted_caregiver_id
                return result

            # Convert applicant to caregiver
            success, message = self._process_employee_packet_match(
                applicant, submission_id
            )
            result["success"] = success
            result["message"] = message
            if success:
                # Refresh to get caregiver ID
                applicant = self.wellsky.get_applicant(applicant.id)
                result["caregiver_id"] = applicant.converted_caregiver_id if applicant else None

        except Exception as e:
            logger.exception(f"Error processing employee packet {submission_id}: {e}")
            result["message"] = str(e)
            result["error"] = str(e)

        return result

    # =========================================================================
    # Logging
    # =========================================================================

    def _log_sync(self, action: str, **kwargs):
        """Log a sync action for audit trail."""
        entry = {
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self._sync_log.append(entry)
        logger.info(f"GoFormz→WellSky sync: {action} - {kwargs}")

    def get_sync_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent sync log entries."""
        return self._sync_log[-limit:]


# =============================================================================
# Singleton Instance
# =============================================================================

goformz_wellsky_sync = GoFormzWellSkySyncService()
