"""
GoFormz → WellSky Sync Service

Handles complete data transfer from GoFormz form submissions to WellSky:
- Employee Packet → WellSky Practitioner (POST /v1/practitioners/)
- Client Packet → WellSky Patient (POST /v1/patients/)

Field mappings use the ACTUAL GoFormz template field names from CCA's
Employee Packet and Client Packet templates.

Triggers:
1. GoFormz webhook fires on form completion → portal_app.py webhook endpoint
2. Webhook calls process_single_client_packet or process_single_employee_packet
3. This service extracts all fields from the GoFormz submission
4. Creates or updates the record in WellSky via FHIR API
"""
from __future__ import annotations

import os
import re
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
# GoFormz Field Name Constants (from actual CCA templates)
# =============================================================================

# --- Employee Packet Field Names ---
# These are the actual field IDs in the GoFormz Employee Packet template
EMPLOYEE_FIELDS = {
    # Personal Info
    "first_name": ["EmpFN", "EmpFirstName", "first_name", "First Name", "firstName"],
    "last_name": ["EmpLN", "EmpLastName", "last_name", "Last Name", "lastName"],
    "middle_initial": ["EmpMI", "EmpMiddleInitial", "middle_initial"],
    "address": ["EmpAddress", "EmpStreet", "employee_address", "Address"],
    "city": ["EmpCity", "employee_city", "City"],
    "state": ["EmpST", "EmpState", "employee_state", "State"],
    "zip": ["EmpZip", "EmpZipCode", "employee_zip", "Zip"],
    "phone": ["EmpPhone", "EmpCellPhone", "employee_phone", "Phone", "phone"],
    "home_phone": ["EmpHomePhone", "EmpHome", "home_phone"],
    "email": ["EmpEmail", "employee_email", "Email", "email"],
    "dob": ["EmpDOB", "EmpBirthDate", "EmpDateOfBirth", "employee_dob", "DOB"],
    "ssn": ["EmpSSN", "EmpSocialSecurity", "SSN", "employee_ssn"],
    "gender": ["GroupSex", "EmpGender", "Gender", "Sex"],
    "marital_status": ["GroupMarried", "EmpMaritalStatus", "MaritalStatus"],

    # Employment Info
    "hire_date": ["EmpHireDt", "EmpHireDate", "HireDate", "hire_date"],
    "start_date": ["EmpStartDate", "EmpStartDt", "StartDate", "start_date"],
    "position": ["EmpPosition", "EmpTitle", "Position", "JobTitle"],
    "pay_rate": ["EmpPayRate", "EmpRate", "PayRate", "pay_rate"],

    # Experience & Certifications (checkbox groups)
    "experience_cna": ["GroupExperience", "CNA", "Experience_CNA"],
    "experience_qmap": ["QMAP", "Experience_QMAP"],
    "skills": ["GroupSkills", "Skills", "Certifications"],

    # Citizenship/Work Authorization
    "citizenship": ["GroupCitizenship", "CitizenshipStatus", "WorkAuth"],

    # Emergency Contacts
    "ec1_first_name": ["EC1FN", "EC1FirstName", "EmergencyContact1FirstName"],
    "ec1_last_name": ["EC1LN", "EC1LastName", "EmergencyContact1LastName"],
    "ec1_phone": ["EC1Phone", "EmergencyContact1Phone"],
    "ec1_relationship": ["EC1Relationship", "EC1Relation"],
    "ec2_first_name": ["EC2FN", "EC2FirstName"],
    "ec2_last_name": ["EC2LN", "EC2LastName"],
    "ec2_phone": ["EC2Phone"],
    "ec2_relationship": ["EC2Relationship", "EC2Relation"],

    # W-4 Tax Fields
    "w4_filing_status": ["W4Filing", "W4FilingStatus", "FilingStatus"],
    "w4_allowances": ["W4Allowances", "W4Exemptions", "Allowances"],
    "w4_additional": ["W4Additional", "W4AdditionalWithholding"],

    # Direct Deposit
    "dd_bank_name": ["DDBankName", "BankName", "DirectDepositBank"],
    "dd_routing": ["DDRouting", "DDRoutingNumber", "RoutingNumber"],
    "dd_account": ["DDAccount", "DDAccountNumber", "AccountNumber"],
    "dd_account_type": ["DDAccountType", "AccountType"],

    # References
    "ref1_name": ["Ref1Name", "Reference1Name"],
    "ref1_phone": ["Ref1Phone", "Reference1Phone"],
    "ref1_relationship": ["Ref1Relationship", "Reference1Relationship"],
    "ref2_name": ["Ref2Name", "Reference2Name"],
    "ref2_phone": ["Ref2Phone", "Reference2Phone"],
    "ref2_relationship": ["Ref2Relationship", "Reference2Relationship"],

    # Signatures & Dates
    "employee_signature": ["EmpSignature", "EmployeeSignature", "Signature"],
    "signature_date": ["EmpSignDate", "SignatureDate", "DateSigned"],
}

# --- Client Packet Field Names ---
# These are the actual field IDs in the GoFormz Client Packet template
CLIENT_FIELDS = {
    # Personal Info
    "full_name": ["ClientName", "ClientFullName", "client_name", "Name"],
    "first_name": ["ClientFN", "ClientFirstName", "client_first_name", "FirstName"],
    "last_name": ["ClientLN", "ClientLastName", "client_last_name", "LastName"],
    "address": ["ClientAddress", "ClientStreet", "client_address", "Address"],
    "city": ["ClientCity", "client_city", "City"],
    "state": ["ClientST", "ClientState", "client_state", "State"],
    "zip": ["ClientZip", "ClientZipCode", "client_zip", "Zip"],
    "dob": ["ClientBirthDate", "ClientDOB", "ClientDateOfBirth", "DOB", "BirthDate"],
    "phone": ["ClientCellPhone", "ClientPhone", "ClientMobile", "client_phone", "Phone"],
    "home_phone": ["ClientHomePhone", "ClientHome", "HomePhone"],
    "email": ["ClientEmail", "client_email", "Email"],
    "gender": ["ClientGender", "ClientSex", "Gender"],
    "marital_status": ["ClientMarital", "ClientMaritalStatus", "MaritalStatus"],
    "language": ["ClientLanguage", "ClientPrimaryLanguage", "Language"],

    # Referral & Source
    "referral_source": ["ClientReferral", "ClientReferralSource", "ReferralSource", "HowDidYouHear"],

    # Health & Medical
    "health_info": ["ClientHealthInfo", "ClientMedical", "HealthInformation"],
    "diagnosis": ["A-ClientDiagnosis", "ClientDiagnosis", "Diagnosis", "PrimaryDiagnosis"],
    "medications": ["ClientMedications", "Medications", "CurrentMedications"],
    "allergies": ["ClientAllergies", "Allergies"],
    "physician_name": ["ClientPhysician", "PhysicianName", "PrimaryPhysician"],
    "physician_phone": ["ClientPhysicianPhone", "PhysicianPhone"],

    # Care Assessment
    "care_goal": ["A-CareGoal", "CareGoal", "CareObjective"],
    "care_plan": ["A-CarePlan", "CarePlan", "PlanOfCare"],
    "proposed_schedule": ["A-ProposedSchedule", "ProposedSchedule", "Schedule"],
    "care_needs": ["A-CareNeeds", "CareNeeds", "ServicesNeeded"],

    # Billing & Payment
    "bill_rate": ["ClientBillRate", "BillRate", "HourlyRate"],
    "hours_per_week": ["ClientHrs", "ClientHoursPerWeek", "HoursPerWeek"],
    "visits_per_week": ["ClientVisits", "ClientVisitsPerWeek", "VisitsPerWeek"],
    "payment_method": ["ClientPayMethod", "PaymentMethod", "PayMethod"],

    # Insurance / LTC
    "insurance_carrier": ["ClientInsCarrier", "InsuranceCarrier", "LTCCarrier"],
    "insurance_policy": ["ClientInsPolicy", "InsurancePolicy", "PolicyNumber"],
    "insurance_group": ["ClientInsGroup", "InsuranceGroup", "GroupNumber"],

    # Emergency Contacts
    "ec1_name": ["EC1Name", "EmergencyContact1Name", "EC1FullName"],
    "ec1_phone": ["EC1Phone", "EmergencyContact1Phone"],
    "ec1_relationship": ["EC1Relationship", "EC1Relation"],
    "ec2_name": ["EC2Name", "EmergencyContact2Name"],
    "ec2_phone": ["EC2Phone", "EmergencyContact2Phone"],
    "ec2_relationship": ["EC2Relationship", "EC2Relation"],

    # Responsible Party / POA
    "rp_name": ["RPName", "ResponsiblePartyName", "POAName"],
    "rp_phone": ["RPPhone", "ResponsiblePartyPhone", "POAPhone"],
    "rp_relationship": ["RPRelationship", "ResponsiblePartyRelationship"],
    "rp_address": ["RPAddress", "ResponsiblePartyAddress"],

    # Signatures
    "client_signature": ["ClientSignature", "Signature"],
    "signature_date": ["ClientSignDate", "SignatureDate", "DateSigned"],
    "rp_signature": ["RPSignature", "ResponsiblePartySignature"],
}

# Form type detection keywords
CLIENT_FORM_KEYWORDS = [
    "client packet", "client paperwork", "service agreement",
    "care agreement", "client intake", "patient intake",
    "home care agreement", "admission",
]

EMPLOYEE_FORM_KEYWORDS = [
    "employee packet", "caregiver packet", "employee paperwork",
    "caregiver paperwork", "new hire", "onboarding",
    "w4", "i9", "employment agreement", "employee handbook",
    "caregiver agreement",
]


def _get_field(data: Dict[str, Any], field_names: List[str]) -> str:
    """Try multiple field name variations and return the first match."""
    for name in field_names:
        val = data.get(name)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _clean_phone(phone: str) -> str:
    """Clean phone number to 10 digits."""
    if not phone:
        return ""
    digits = re.sub(r'[^\d]', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits


def _parse_date(date_str: str) -> Optional[str]:
    """Try to parse a date string into YYYY-MM-DD format."""
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_gender(gender_str: str) -> Optional[str]:
    """Parse gender string into FHIR-compliant value."""
    if not gender_str:
        return None
    g = gender_str.strip().lower()
    if g in ("m", "male"):
        return "male"
    elif g in ("f", "female"):
        return "female"
    elif g in ("other", "non-binary", "nonbinary"):
        return "other"
    return "unknown"


def _parse_certifications(form_data: Dict[str, Any]) -> List[str]:
    """Extract certifications/skills from GoFormz checkbox groups."""
    tags = []

    # Check common certification checkbox fields
    cert_fields = {
        "CNA": ["GroupExperience", "CNA", "Experience_CNA", "IsCNA"],
        "QMAP": ["QMAP", "Experience_QMAP", "IsQMAP"],
        "HHA": ["HHA", "Experience_HHA", "IsHHA"],
        "RN": ["RN", "Experience_RN", "IsRN"],
        "LPN": ["LPN", "Experience_LPN", "IsLPN"],
        "CPR": ["CPR", "IsCPR", "CPRCertified"],
        "FirstAid": ["FirstAid", "IsFirstAid"],
    }

    for cert_name, field_names in cert_fields.items():
        for field in field_names:
            val = form_data.get(field)
            if val and str(val).strip().lower() in ("true", "yes", "1", "x", "checked", cert_name.lower()):
                tags.append(cert_name)
                break

    # Also check GroupSkills if it's a comma-separated string
    skills = form_data.get("GroupSkills") or form_data.get("Skills") or ""
    if isinstance(skills, str) and skills.strip():
        for skill in skills.split(","):
            s = skill.strip()
            if s and s not in tags:
                tags.append(s)

    return tags


class GoFormzWellSkySyncService:
    """
    Service for syncing GoFormz form completions to WellSky.

    Handles two workflows:
    - Client Packet → WellSky Patient (via create_patient FHIR endpoint)
    - Employee Packet → WellSky Practitioner (via create_practitioner FHIR endpoint)
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
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sales'))
                from goformz_service import GoFormzService
                self._goformz_service = GoFormzService()
            except ImportError:
                logger.warning("GoFormz service not available")
                self._goformz_service = None
        return self._goformz_service

    # =========================================================================
    # Employee Packet → WellSky Practitioner
    # =========================================================================

    def _extract_employee_data(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ALL employee data from a GoFormz Employee Packet submission.

        Uses actual GoFormz field names: EmpFN, EmpLN, EmpPhone, EmpEmail, etc.
        """
        form_data = submission.get('data', {})
        if not form_data:
            # GoFormz webhook payload structure can vary
            form_data = submission.get('formData', {})
            if not form_data:
                item = submission.get('Item', {})
                form_data = item.get('formData', {}) or item.get('data', {}) or {}

        first_name = _get_field(form_data, EMPLOYEE_FIELDS["first_name"])
        last_name = _get_field(form_data, EMPLOYEE_FIELDS["last_name"])

        # If no separate first/last, try splitting a full name field
        if not first_name and not last_name:
            full_name = _get_field(form_data, ["EmpName", "EmployeeName", "Name", "name", "Employee Name"])
            if full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

        raw_dob = _get_field(form_data, EMPLOYEE_FIELDS["dob"])
        raw_gender = _get_field(form_data, EMPLOYEE_FIELDS["gender"])
        certifications = _parse_certifications(form_data)

        return {
            # Core identity
            "first_name": first_name,
            "last_name": last_name,
            "middle_initial": _get_field(form_data, EMPLOYEE_FIELDS["middle_initial"]),
            "name": f"{first_name} {last_name}".strip(),

            # Contact
            "phone": _get_field(form_data, EMPLOYEE_FIELDS["phone"]),
            "home_phone": _get_field(form_data, EMPLOYEE_FIELDS["home_phone"]),
            "email": _get_field(form_data, EMPLOYEE_FIELDS["email"]).lower() or "",

            # Address
            "address": _get_field(form_data, EMPLOYEE_FIELDS["address"]),
            "city": _get_field(form_data, EMPLOYEE_FIELDS["city"]),
            "state": _get_field(form_data, EMPLOYEE_FIELDS["state"]) or "CO",
            "zip": _get_field(form_data, EMPLOYEE_FIELDS["zip"]),

            # Demographics
            "dob": _parse_date(raw_dob),
            "ssn": _get_field(form_data, EMPLOYEE_FIELDS["ssn"]),
            "gender": _parse_gender(raw_gender),
            "marital_status": _get_field(form_data, EMPLOYEE_FIELDS["marital_status"]),

            # Employment
            "hire_date": _parse_date(_get_field(form_data, EMPLOYEE_FIELDS["hire_date"])),
            "start_date": _parse_date(_get_field(form_data, EMPLOYEE_FIELDS["start_date"])),
            "position": _get_field(form_data, EMPLOYEE_FIELDS["position"]),
            "pay_rate": _get_field(form_data, EMPLOYEE_FIELDS["pay_rate"]),
            "certifications": certifications,

            # Emergency contacts
            "emergency_contacts": [
                {
                    "first_name": _get_field(form_data, EMPLOYEE_FIELDS["ec1_first_name"]),
                    "last_name": _get_field(form_data, EMPLOYEE_FIELDS["ec1_last_name"]),
                    "phone": _get_field(form_data, EMPLOYEE_FIELDS["ec1_phone"]),
                    "relationship": _get_field(form_data, EMPLOYEE_FIELDS["ec1_relationship"]),
                },
                {
                    "first_name": _get_field(form_data, EMPLOYEE_FIELDS["ec2_first_name"]),
                    "last_name": _get_field(form_data, EMPLOYEE_FIELDS["ec2_last_name"]),
                    "phone": _get_field(form_data, EMPLOYEE_FIELDS["ec2_phone"]),
                    "relationship": _get_field(form_data, EMPLOYEE_FIELDS["ec2_relationship"]),
                },
            ],

            # W-4 (stored as notes, not sent to WellSky directly)
            "w4_filing_status": _get_field(form_data, EMPLOYEE_FIELDS["w4_filing_status"]),
            "w4_allowances": _get_field(form_data, EMPLOYEE_FIELDS["w4_allowances"]),

            # Direct deposit (stored as notes, not sent to WellSky directly)
            "dd_bank_name": _get_field(form_data, EMPLOYEE_FIELDS["dd_bank_name"]),
            "dd_account_type": _get_field(form_data, EMPLOYEE_FIELDS["dd_account_type"]),

            "source": "GoFormz Employee Packet",
        }

    def _create_practitioner_from_employee_data(
        self,
        employee_data: Dict[str, Any],
        submission_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a WellSky Practitioner from extracted GoFormz employee data.

        Uses the FHIR-compliant create_practitioner() method (POST /v1/practitioners/).
        Returns (success, practitioner_id or error message).
        """
        first_name = employee_data.get("first_name", "")
        last_name = employee_data.get("last_name", "")

        if not first_name or not last_name:
            return False, "Missing first_name or last_name"

        # Build profile tags from certifications
        profile_tags = employee_data.get("certifications", [])

        # Determine language from form data (default English)
        languages = ["en-us"]

        success, response = self.wellsky.create_practitioner(
            first_name=first_name,
            last_name=last_name,
            phone=_clean_phone(employee_data.get("phone", "")),
            home_phone=_clean_phone(employee_data.get("home_phone", "")),
            email=employee_data.get("email", ""),
            address=employee_data.get("address", ""),
            city=employee_data.get("city", ""),
            state=employee_data.get("state", "CO"),
            zip_code=employee_data.get("zip", ""),
            gender=employee_data.get("gender"),
            birth_date=employee_data.get("dob"),
            ssn=employee_data.get("ssn", ""),
            is_hired=True,
            status_id=100,  # 100 = Hired
            profile_tags=profile_tags if profile_tags else None,
            languages=languages,
        )

        if success:
            prac_id = response.get("id", "unknown") if isinstance(response, dict) else str(response)
            logger.info(f"Created WellSky practitioner {prac_id} from GoFormz submission {submission_id}")
            self._log_sync(
                "practitioner_created",
                submission_id=submission_id,
                practitioner_id=prac_id,
                name=f"{first_name} {last_name}",
                certifications=profile_tags,
            )
            return True, prac_id

        error_msg = str(response) if response else "Unknown error"
        logger.error(f"Failed to create practitioner from GoFormz {submission_id}: {error_msg}")
        return False, error_msg

    # =========================================================================
    # Client Packet → WellSky Patient
    # =========================================================================

    def _extract_customer_data(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ALL client data from a GoFormz Client Packet submission.

        Uses actual GoFormz field names: ClientName, ClientAddress, etc.
        """
        form_data = submission.get('data', {})
        if not form_data:
            form_data = submission.get('formData', {})
            if not form_data:
                item = submission.get('Item', {})
                form_data = item.get('formData', {}) or item.get('data', {}) or {}

        # Client name - may be a single "ClientName" field that needs splitting
        first_name = _get_field(form_data, CLIENT_FIELDS["first_name"])
        last_name = _get_field(form_data, CLIENT_FIELDS["last_name"])

        if not first_name and not last_name:
            full_name = _get_field(form_data, CLIENT_FIELDS["full_name"])
            if full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

        raw_dob = _get_field(form_data, CLIENT_FIELDS["dob"])
        raw_gender = _get_field(form_data, CLIENT_FIELDS["gender"])
        language = _get_field(form_data, CLIENT_FIELDS["language"])

        # Build assessment notes from multiple fields
        assessment_parts = []
        diagnosis = _get_field(form_data, CLIENT_FIELDS["diagnosis"])
        care_goal = _get_field(form_data, CLIENT_FIELDS["care_goal"])
        care_plan = _get_field(form_data, CLIENT_FIELDS["care_plan"])
        care_needs = _get_field(form_data, CLIENT_FIELDS["care_needs"])
        health_info = _get_field(form_data, CLIENT_FIELDS["health_info"])
        medications = _get_field(form_data, CLIENT_FIELDS["medications"])
        allergies = _get_field(form_data, CLIENT_FIELDS["allergies"])

        if diagnosis:
            assessment_parts.append(f"Diagnosis: {diagnosis}")
        if care_goal:
            assessment_parts.append(f"Care Goal: {care_goal}")
        if care_plan:
            assessment_parts.append(f"Care Plan: {care_plan}")
        if care_needs:
            assessment_parts.append(f"Care Needs: {care_needs}")
        if health_info:
            assessment_parts.append(f"Health Info: {health_info}")
        if medications:
            assessment_parts.append(f"Medications: {medications}")
        if allergies:
            assessment_parts.append(f"Allergies: {allergies}")

        return {
            # Core identity
            "first_name": first_name,
            "last_name": last_name,
            "name": f"{first_name} {last_name}".strip(),

            # Contact
            "phone": _get_field(form_data, CLIENT_FIELDS["phone"]),
            "home_phone": _get_field(form_data, CLIENT_FIELDS["home_phone"]),
            "email": _get_field(form_data, CLIENT_FIELDS["email"]).lower() or "",

            # Address
            "address": _get_field(form_data, CLIENT_FIELDS["address"]),
            "city": _get_field(form_data, CLIENT_FIELDS["city"]),
            "state": _get_field(form_data, CLIENT_FIELDS["state"]) or "CO",
            "zip": _get_field(form_data, CLIENT_FIELDS["zip"]),

            # Demographics
            "dob": _parse_date(raw_dob),
            "gender": _parse_gender(raw_gender),
            "marital_status": _get_field(form_data, CLIENT_FIELDS["marital_status"]),
            "language": language.lower() if language else "en",

            # Referral
            "referral_source": _get_field(form_data, CLIENT_FIELDS["referral_source"]),

            # Medical/Assessment (combined into notes)
            "diagnosis": diagnosis,
            "care_goal": care_goal,
            "care_plan": care_plan,
            "proposed_schedule": _get_field(form_data, CLIENT_FIELDS["proposed_schedule"]),
            "assessment_notes": "\n".join(assessment_parts),
            "physician_name": _get_field(form_data, CLIENT_FIELDS["physician_name"]),
            "physician_phone": _get_field(form_data, CLIENT_FIELDS["physician_phone"]),

            # Billing
            "bill_rate": _get_field(form_data, CLIENT_FIELDS["bill_rate"]),
            "hours_per_week": _get_field(form_data, CLIENT_FIELDS["hours_per_week"]),
            "visits_per_week": _get_field(form_data, CLIENT_FIELDS["visits_per_week"]),

            # Insurance
            "insurance_carrier": _get_field(form_data, CLIENT_FIELDS["insurance_carrier"]),
            "insurance_policy": _get_field(form_data, CLIENT_FIELDS["insurance_policy"]),

            # Emergency contacts
            "emergency_contacts": [
                {
                    "name": _get_field(form_data, CLIENT_FIELDS["ec1_name"]),
                    "phone": _get_field(form_data, CLIENT_FIELDS["ec1_phone"]),
                    "relationship": _get_field(form_data, CLIENT_FIELDS["ec1_relationship"]),
                },
                {
                    "name": _get_field(form_data, CLIENT_FIELDS["ec2_name"]),
                    "phone": _get_field(form_data, CLIENT_FIELDS["ec2_phone"]),
                    "relationship": _get_field(form_data, CLIENT_FIELDS["ec2_relationship"]),
                },
            ],

            # Responsible Party
            "responsible_party": {
                "name": _get_field(form_data, CLIENT_FIELDS["rp_name"]),
                "phone": _get_field(form_data, CLIENT_FIELDS["rp_phone"]),
                "relationship": _get_field(form_data, CLIENT_FIELDS["rp_relationship"]),
                "address": _get_field(form_data, CLIENT_FIELDS["rp_address"]),
            },

            "source": "GoFormz Client Packet",
        }

    def _create_patient_from_client_data(
        self,
        client_data: Dict[str, Any],
        submission_id: str
    ) -> Tuple[bool, Optional[Any]]:
        """
        Create a WellSky Patient from extracted GoFormz client data.

        Uses the FHIR-compliant create_patient() method (POST /v1/patients/).
        Returns (success, WellSkyClient or error message).
        """
        first_name = client_data.get("first_name", "")
        last_name = client_data.get("last_name", "")

        if not first_name or not last_name:
            return False, "Missing first_name or last_name"

        patient = self.wellsky.create_patient(
            first_name=first_name,
            last_name=last_name,
            phone=_clean_phone(client_data.get("phone", "")),
            email=client_data.get("email", ""),
            address=client_data.get("address", ""),
            city=client_data.get("city", ""),
            state=client_data.get("state", "CO"),
            zip_code=client_data.get("zip", ""),
            is_client=True,
            status_id=80,  # 80 = Care Started
            referral_source=client_data.get("referral_source", ""),
        )

        if patient:
            logger.info(f"Created WellSky patient {patient.id} from GoFormz submission {submission_id}")
            self._log_sync(
                "patient_created",
                submission_id=submission_id,
                patient_id=patient.id,
                name=f"{first_name} {last_name}",
            )
            return True, patient

        logger.error(f"Failed to create patient from GoFormz {submission_id}")
        return False, "Failed to create patient in WellSky"

    # =========================================================================
    # Matching Logic (find existing WellSky records)
    # =========================================================================

    def _find_matching_prospect(
        self,
        customer_data: Dict[str, Any],
        submission: Dict[str, Any]
    ) -> Optional[WellSkyProspect]:
        """Find a WellSky prospect matching the GoFormz submission data."""
        # Strategy 1: Match by linked sales deal ID
        form_data = submission.get("data", {})
        deal_id = form_data.get("deal_id") or form_data.get("sales_deal_id")
        if deal_id:
            prospect = self.wellsky.get_prospect_by_sales_deal_id(str(deal_id))
            if prospect:
                return prospect

        # Strategy 2: Search by name using FHIR patient search
        first_name = customer_data.get("first_name", "").strip()
        last_name = customer_data.get("last_name", "").strip()
        if first_name and last_name:
            patients = self.wellsky.search_patients(
                first_name=first_name,
                last_name=last_name,
                limit=10
            )
            for p in patients:
                if hasattr(p, 'is_open') and p.is_open:
                    return p

        # Strategy 3: Match by email in prospect list
        email = customer_data.get("email", "").lower()
        if email:
            prospects = self.wellsky.get_prospects(limit=1000)
            for prospect in prospects:
                if hasattr(prospect, 'email') and prospect.email.lower() == email and prospect.is_open:
                    return prospect

        # Strategy 4: Match by phone
        phone = _clean_phone(customer_data.get("phone", ""))
        if phone:
            prospects = self.wellsky.get_prospects(limit=1000)
            for prospect in prospects:
                if hasattr(prospect, 'phone') and _clean_phone(prospect.phone) == phone and prospect.is_open:
                    return prospect

        return None

    def _find_matching_applicant(
        self,
        employee_data: Dict[str, Any],
        submission: Dict[str, Any]
    ) -> Optional[WellSkyApplicant]:
        """Find a WellSky applicant matching the GoFormz submission data."""
        form_data = submission.get("data", {})
        lead_id = form_data.get("lead_id") or form_data.get("recruiting_lead_id")
        if lead_id:
            applicant = self.wellsky.get_applicant_by_recruiting_lead_id(str(lead_id))
            if applicant:
                return applicant

        # Search by name using FHIR practitioner search
        first_name = employee_data.get("first_name", "").strip()
        last_name = employee_data.get("last_name", "").strip()
        if first_name and last_name:
            practitioners = self.wellsky.search_practitioners(
                first_name=first_name,
                last_name=last_name,
                is_hired=False,  # Look for applicants
                limit=10
            )
            for p in practitioners:
                if hasattr(p, 'is_open') and p.is_open:
                    return p

        # Match by email
        email = employee_data.get("email", "").lower()
        if email:
            applicants = self.wellsky.get_applicants(limit=1000)
            for applicant in applicants:
                if hasattr(applicant, 'email') and applicant.email.lower() == email and applicant.is_open:
                    return applicant

        # Match by phone
        phone = _clean_phone(employee_data.get("phone", ""))
        if phone:
            applicants = self.wellsky.get_applicants(limit=1000)
            for applicant in applicants:
                if hasattr(applicant, 'phone') and _clean_phone(applicant.phone) == phone and applicant.is_open:
                    return applicant

        return None

    # =========================================================================
    # Single Packet Processing (for Webhook Events)
    # =========================================================================

    def process_single_client_packet(
        self,
        packet_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a single client packet from a GoFormz webhook event.

        Flow:
        1. Extract client data from GoFormz submission fields
        2. Try to find matching WellSky prospect
        3. If found: convert prospect → client
        4. If not found: create NEW patient directly via FHIR API
        """
        submission_id = packet_info.get('submission_id')
        form_name = packet_info.get('form_name', 'client packet')
        payload = packet_info.get('payload', {})

        result = {
            "submission_id": submission_id,
            "form_type": "client_packet",
            "success": False,
            "message": "",
            "fields_extracted": {},
        }

        try:
            # Extract customer data using actual GoFormz field names
            customer_data = self._extract_customer_data(payload)
            result["fields_extracted"] = {
                "name": customer_data.get("name"),
                "phone": customer_data.get("phone"),
                "email": customer_data.get("email"),
                "address": customer_data.get("address"),
                "city": customer_data.get("city"),
            }

            if not customer_data.get("first_name") and not customer_data.get("last_name"):
                result["message"] = "Could not extract client name from GoFormz submission"
                return result

            # Try to find matching prospect
            prospect = self._find_matching_prospect(customer_data, payload)

            if prospect:
                # Found existing prospect - convert to client
                if prospect.is_converted:
                    result["success"] = True
                    result["message"] = f"Prospect already converted to client {prospect.converted_client_id}"
                    result["client_id"] = prospect.converted_client_id
                    return result

                # Update prospect status to WON
                if prospect.status != ProspectStatus.WON:
                    self.wellsky.update_prospect_status(
                        prospect.id,
                        ProspectStatus.WON,
                        notes=f"Client packet signed (GoFormz {submission_id})"
                    )

                # Convert prospect → client
                client = self.wellsky.convert_prospect_to_client(
                    prospect.id,
                    client_data={
                        "start_date": date.today().isoformat(),
                        "notes": f"Activated via GoFormz {form_name} (submission {submission_id})",
                    }
                )

                if client:
                    self._log_sync(
                        "client_converted",
                        submission_id=submission_id,
                        prospect_id=prospect.id,
                        client_id=client.id,
                        client_name=client.full_name,
                    )
                    result["success"] = True
                    result["message"] = f"Converted prospect {prospect.id} to client {client.id}"
                    result["client_id"] = client.id
                    return result

                result["message"] = "Failed to convert prospect to client"
                return result

            # No matching prospect found - create NEW patient via FHIR
            logger.info(f"No prospect match for {customer_data.get('name')}. Creating new WellSky patient.")
            success, patient_or_error = self._create_patient_from_client_data(customer_data, submission_id)

            if success and patient_or_error:
                result["success"] = True
                pid = patient_or_error.id if hasattr(patient_or_error, 'id') else str(patient_or_error)
                result["message"] = f"Created new WellSky patient {pid}"
                result["patient_id"] = pid
            else:
                result["message"] = f"No prospect found and failed to create patient: {patient_or_error}"

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
        Process a single employee packet from a GoFormz webhook event.

        Flow:
        1. Extract employee data from GoFormz submission fields
        2. Try to find matching WellSky applicant
        3. If found: convert applicant → caregiver
        4. If not found: create NEW practitioner directly via FHIR API
        """
        submission_id = packet_info.get('submission_id')
        form_name = packet_info.get('form_name', 'employee packet')
        payload = packet_info.get('payload', {})

        result = {
            "submission_id": submission_id,
            "form_type": "employee_packet",
            "success": False,
            "message": "",
            "fields_extracted": {},
        }

        try:
            # Extract employee data using actual GoFormz field names
            employee_data = self._extract_employee_data(payload)
            result["fields_extracted"] = {
                "name": employee_data.get("name"),
                "phone": employee_data.get("phone"),
                "email": employee_data.get("email"),
                "address": employee_data.get("address"),
                "city": employee_data.get("city"),
                "certifications": employee_data.get("certifications", []),
            }

            if not employee_data.get("first_name") and not employee_data.get("last_name"):
                result["message"] = "Could not extract employee name from GoFormz submission"
                return result

            # Try to find matching applicant
            applicant = self._find_matching_applicant(employee_data, payload)

            if applicant:
                # Found existing applicant - convert to caregiver
                if applicant.is_hired and applicant.converted_caregiver_id:
                    result["success"] = True
                    result["message"] = f"Applicant already converted to caregiver {applicant.converted_caregiver_id}"
                    result["caregiver_id"] = applicant.converted_caregiver_id
                    return result

                # Update applicant status to HIRED
                if applicant.status != ApplicantStatus.HIRED:
                    self.wellsky.update_applicant_status(
                        applicant.id,
                        ApplicantStatus.HIRED,
                        notes=f"Employee packet signed (GoFormz {submission_id})"
                    )

                # Convert applicant → caregiver
                caregiver = self.wellsky.convert_applicant_to_caregiver(
                    applicant.id,
                    caregiver_data={
                        "hire_date": employee_data.get("hire_date") or date.today().isoformat(),
                        "notes": f"Activated via GoFormz {form_name} (submission {submission_id})",
                    }
                )

                if caregiver:
                    self._log_sync(
                        "caregiver_converted",
                        submission_id=submission_id,
                        applicant_id=applicant.id,
                        caregiver_id=caregiver.id,
                        caregiver_name=caregiver.full_name,
                    )
                    result["success"] = True
                    result["message"] = f"Converted applicant {applicant.id} to caregiver {caregiver.id}"
                    result["caregiver_id"] = caregiver.id
                    return result

                result["message"] = "Failed to convert applicant to caregiver"
                return result

            # No matching applicant found - create NEW practitioner via FHIR
            logger.info(f"No applicant match for {employee_data.get('name')}. Creating new WellSky practitioner.")
            success, prac_id_or_error = self._create_practitioner_from_employee_data(
                employee_data, submission_id
            )

            if success:
                result["success"] = True
                result["message"] = f"Created new WellSky practitioner {prac_id_or_error}"
                result["practitioner_id"] = prac_id_or_error
            else:
                result["message"] = f"No applicant found and failed to create practitioner: {prac_id_or_error}"

        except Exception as e:
            logger.exception(f"Error processing employee packet {submission_id}: {e}")
            result["message"] = str(e)
            result["error"] = str(e)

        return result

    # =========================================================================
    # Batch Processing (for scheduled jobs)
    # =========================================================================

    def process_completed_client_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Process completed client packets and create patients/convert prospects."""
        results = {
            "total_submissions": 0,
            "matched_prospects": 0,
            "converted_to_clients": 0,
            "created_new_patients": 0,
            "already_converted": 0,
            "no_match": 0,
            "errors": [],
        }

        if not self.goformz or not self.goformz.enabled:
            logger.warning("GoFormz service not available, using mock mode")
            return self._mock_process_client_packets()

        packets_result = self.goformz.get_completed_client_packets(since=since)
        if not packets_result.get("success"):
            results["errors"].append(packets_result.get("error", "Failed to fetch packets"))
            return results

        submissions = packets_result.get("submissions", [])
        results["total_submissions"] = len(submissions)

        for submission in submissions:
            try:
                sub_id = submission.get("id", submission.get("Id", ""))
                result = self.process_single_client_packet({
                    "submission_id": sub_id,
                    "form_name": "client packet",
                    "payload": submission,
                })

                if result.get("success"):
                    if "converted" in result.get("message", "").lower():
                        results["converted_to_clients"] += 1
                        results["matched_prospects"] += 1
                    elif "already" in result.get("message", "").lower():
                        results["already_converted"] += 1
                    elif "created" in result.get("message", "").lower():
                        results["created_new_patients"] += 1
                else:
                    results["no_match"] += 1

            except Exception as e:
                results["errors"].append({
                    "submission_id": submission.get("id"),
                    "error": str(e)
                })

        logger.info(f"Processed {results['total_submissions']} client packets: "
                   f"{results['converted_to_clients']} converted, "
                   f"{results['created_new_patients']} new patients created")
        return results

    def process_completed_employee_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Process completed employee packets and create practitioners/convert applicants."""
        results = {
            "total_submissions": 0,
            "matched_applicants": 0,
            "converted_to_caregivers": 0,
            "created_new_practitioners": 0,
            "already_converted": 0,
            "no_match": 0,
            "errors": [],
        }

        if not self.goformz or not self.goformz.enabled:
            logger.warning("GoFormz service not available, using mock mode")
            return self._mock_process_employee_packets()

        packets_result = self._get_completed_employee_packets(since=since)
        if not packets_result.get("success"):
            results["errors"].append(packets_result.get("error", "Failed to fetch packets"))
            return results

        submissions = packets_result.get("submissions", [])
        results["total_submissions"] = len(submissions)

        for submission in submissions:
            try:
                sub_id = submission.get("id", submission.get("Id", ""))
                result = self.process_single_employee_packet({
                    "submission_id": sub_id,
                    "form_name": "employee packet",
                    "payload": submission,
                })

                if result.get("success"):
                    if "converted" in result.get("message", "").lower():
                        results["converted_to_caregivers"] += 1
                        results["matched_applicants"] += 1
                    elif "already" in result.get("message", "").lower():
                        results["already_converted"] += 1
                    elif "created" in result.get("message", "").lower():
                        results["created_new_practitioners"] += 1
                else:
                    results["no_match"] += 1

            except Exception as e:
                results["errors"].append({
                    "submission_id": submission.get("id"),
                    "error": str(e)
                })

        logger.info(f"Processed {results['total_submissions']} employee packets: "
                   f"{results['converted_to_caregivers']} converted, "
                   f"{results['created_new_practitioners']} new practitioners created")
        return results

    def _get_completed_employee_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get completed employee/caregiver packets from GoFormz."""
        if not self.goformz:
            return {"success": False, "error": "GoFormz not available"}

        try:
            forms_result = self.goformz.get_forms(limit=1000)
            if not forms_result.get('success'):
                return forms_result

            forms = forms_result.get('forms', {}).get('data', [])

            employee_forms = []
            for form in forms:
                form_name = form.get('name', '').lower()
                if any(keyword in form_name for keyword in EMPLOYEE_FORM_KEYWORDS):
                    employee_forms.append(form)

            if not employee_forms:
                return {"success": True, "submissions": [], "message": "No employee forms found"}

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

    def process_all_completed_packets(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Process all completed packets (both client and employee). Main scheduled job entry point."""
        results = {
            "client_packets": {},
            "employee_packets": {},
            "total_conversions": 0,
            "total_new_records": 0,
            "processed_at": datetime.utcnow().isoformat(),
        }

        client_results = self.process_completed_client_packets(since=since)
        results["client_packets"] = client_results
        results["total_conversions"] += client_results.get("converted_to_clients", 0)
        results["total_new_records"] += client_results.get("created_new_patients", 0)

        employee_results = self.process_completed_employee_packets(since=since)
        results["employee_packets"] = employee_results
        results["total_conversions"] += employee_results.get("converted_to_caregivers", 0)
        results["total_new_records"] += employee_results.get("created_new_practitioners", 0)

        logger.info(f"Total: {results['total_conversions']} conversions, "
                   f"{results['total_new_records']} new records created")
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
        """Manually trigger prospect to client conversion."""
        prospect = self.wellsky.get_prospect(prospect_id)
        if not prospect:
            return False, None, f"Prospect {prospect_id} not found"

        if prospect.is_converted:
            client = self.wellsky.get_client(prospect.converted_client_id)
            return True, client, f"Already converted to client {prospect.converted_client_id}"

        if prospect.status != ProspectStatus.WON:
            self.wellsky.update_prospect_status(
                prospect_id, ProspectStatus.WON,
                notes=notes or "Manually marked as won"
            )

        client = self.wellsky.convert_prospect_to_client(
            prospect_id,
            client_data={
                "start_date": date.today().isoformat(),
                "notes": notes or "Manually converted",
            }
        )

        if client:
            self._log_sync("manual_client_conversion",
                          prospect_id=prospect_id, client_id=client.id, notes=notes)
            return True, client, f"Converted to client {client.id}"
        return False, None, "Failed to convert prospect"

    def manually_convert_applicant_to_caregiver(
        self,
        applicant_id: str,
        goformz_submission_id: Optional[str] = None,
        notes: str = ""
    ) -> Tuple[bool, Optional[WellSkyCaregiver], str]:
        """Manually trigger applicant to caregiver conversion."""
        applicant = self.wellsky.get_applicant(applicant_id)
        if not applicant:
            return False, None, f"Applicant {applicant_id} not found"

        if applicant.is_hired and applicant.converted_caregiver_id:
            caregiver = self.wellsky.get_caregiver(applicant.converted_caregiver_id)
            return True, caregiver, f"Already converted to caregiver {applicant.converted_caregiver_id}"

        if applicant.status != ApplicantStatus.HIRED:
            self.wellsky.update_applicant_status(
                applicant_id, ApplicantStatus.HIRED,
                notes=notes or "Manually marked as hired"
            )

        caregiver = self.wellsky.convert_applicant_to_caregiver(
            applicant_id,
            caregiver_data={
                "hire_date": date.today().isoformat(),
                "notes": notes or "Manually converted",
            }
        )

        if caregiver:
            self._log_sync("manual_caregiver_conversion",
                          applicant_id=applicant_id, caregiver_id=caregiver.id, notes=notes)
            return True, caregiver, f"Converted to caregiver {caregiver.id}"
        return False, None, "Failed to convert applicant"

    # =========================================================================
    # Mock Mode (for testing without GoFormz credentials)
    # =========================================================================

    def _mock_process_client_packets(self) -> Dict[str, Any]:
        """Mock processing for development/testing."""
        logger.info("Mock: Processing client packets")
        prospects = self.wellsky.get_prospects(status=ProspectStatus.WON)
        results = {
            "total_submissions": len(prospects),
            "matched_prospects": 0, "converted_to_clients": 0,
            "created_new_patients": 0, "already_converted": 0,
            "no_match": 0, "errors": [], "mock_mode": True,
        }
        for prospect in prospects:
            if prospect.is_converted:
                results["already_converted"] += 1
            else:
                client = self.wellsky.convert_prospect_to_client(
                    prospect.id, client_data={"start_date": date.today().isoformat()}
                )
                if client:
                    results["converted_to_clients"] += 1
                    results["matched_prospects"] += 1
        return results

    def _mock_process_employee_packets(self) -> Dict[str, Any]:
        """Mock processing for development/testing."""
        logger.info("Mock: Processing employee packets")
        applicants = self.wellsky.get_applicants(status=ApplicantStatus.HIRED)
        results = {
            "total_submissions": len(applicants),
            "matched_applicants": 0, "converted_to_caregivers": 0,
            "created_new_practitioners": 0, "already_converted": 0,
            "no_match": 0, "errors": [], "mock_mode": True,
        }
        for applicant in applicants:
            if applicant.is_hired and applicant.converted_caregiver_id:
                results["already_converted"] += 1
            else:
                caregiver = self.wellsky.convert_applicant_to_caregiver(
                    applicant.id, caregiver_data={"hire_date": date.today().isoformat()}
                )
                if caregiver:
                    results["converted_to_caregivers"] += 1
                    results["matched_applicants"] += 1
        return results

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

    def get_field_mapping_info(self) -> Dict[str, Any]:
        """Return info about the field mappings for debugging."""
        return {
            "employee_packet_fields": len(EMPLOYEE_FIELDS),
            "client_packet_fields": len(CLIENT_FIELDS),
            "employee_field_names": list(EMPLOYEE_FIELDS.keys()),
            "client_field_names": list(CLIENT_FIELDS.keys()),
            "employee_form_keywords": EMPLOYEE_FORM_KEYWORDS,
            "client_form_keywords": CLIENT_FORM_KEYWORDS,
        }


# =============================================================================
# Singleton Instance
# =============================================================================

goformz_wellsky_sync = GoFormzWellSkySyncService()
