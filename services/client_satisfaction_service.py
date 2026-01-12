"""
Client Satisfaction Service

Provides functionality for tracking client satisfaction metrics:
- Survey responses (from Google Forms/Sheets or manual entry)
- Complaints tracking and resolution
- Quality visits
- External reviews
- Care plan status
"""
from __future__ import annotations

import os
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

# Google Sheets configuration for survey responses
SURVEY_RESPONSES_SHEET_ID = os.getenv("CLIENT_SURVEY_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")


class ClientSatisfactionService:
    """Service for managing client satisfaction data"""

    def __init__(self):
        self.sheets_client = None
        self._init_google_sheets()

    def _init_google_sheets(self):
        """Initialize Google Sheets client for survey data"""
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            logger.info("Google service account not configured - sheets integration disabled")
            return

        try:
            # Parse service account credentials
            creds_info = json.loads(GOOGLE_SERVICE_ACCOUNT_KEY)
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")

            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive.readonly"
            ]

            credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
            self.sheets_client = gspread.authorize(credentials)
            logger.info("Google Sheets client initialized for client satisfaction")

        except Exception as e:
            logger.warning(f"Failed to initialize Google Sheets: {e}")
            self.sheets_client = None

    def get_survey_responses_from_sheet(self, sheet_id: str = None) -> List[Dict[str, Any]]:
        """
        Fetch survey responses from Google Sheets (linked to Google Form).

        Args:
            sheet_id: Google Sheet ID (uses env var if not provided)

        Returns:
            List of survey response dictionaries
        """
        sheet_id = sheet_id or SURVEY_RESPONSES_SHEET_ID
        if not self.sheets_client or not sheet_id:
            logger.warning("Cannot fetch survey responses - sheets not configured")
            return []

        try:
            spreadsheet = self.sheets_client.open_by_key(sheet_id)
            worksheet = spreadsheet.sheet1  # Form responses go to first sheet

            records = worksheet.get_all_records()
            logger.info(f"Fetched {len(records)} survey responses from Google Sheets")

            # Transform to our format
            responses = []
            for record in records:
                responses.append(self._transform_form_response(record))

            return responses

        except Exception as e:
            logger.error(f"Error fetching survey responses: {e}")
            return []

    def _transform_form_response(self, record: Dict) -> Dict[str, Any]:
        """Transform Google Form response to our survey format"""
        # This mapping will need to be adjusted based on actual form questions
        # Common Google Form field patterns
        return {
            "timestamp": record.get("Timestamp", ""),
            "client_name": record.get("Client Name", record.get("Name", "")),
            "overall_satisfaction": self._parse_rating(
                record.get("Overall Satisfaction", record.get("How satisfied are you overall?", ""))
            ),
            "caregiver_satisfaction": self._parse_rating(
                record.get("Caregiver Rating", record.get("How would you rate your caregiver?", ""))
            ),
            "communication_rating": self._parse_rating(
                record.get("Communication", record.get("How well do we communicate?", ""))
            ),
            "would_recommend": self._parse_yes_no(
                record.get("Would Recommend", record.get("Would you recommend us?", ""))
            ),
            "feedback_comments": record.get("Comments", record.get("Additional Feedback", "")),
            "source": "google_form",
            "raw_data": record,
        }

    def _parse_rating(self, value: Any) -> Optional[int]:
        """Parse rating from various formats (1-5, text, etc.)"""
        if not value:
            return None
        try:
            # Handle numeric values
            if isinstance(value, (int, float)):
                return int(value)
            # Handle string numbers
            val_str = str(value).strip()
            if val_str.isdigit():
                return int(val_str)
            # Handle text ratings
            rating_map = {
                "very satisfied": 5, "excellent": 5, "5": 5,
                "satisfied": 4, "good": 4, "4": 4,
                "neutral": 3, "average": 3, "3": 3,
                "dissatisfied": 2, "poor": 2, "2": 2,
                "very dissatisfied": 1, "very poor": 1, "1": 1,
            }
            return rating_map.get(val_str.lower())
        except Exception:
            return None

    def _parse_yes_no(self, value: Any) -> Optional[bool]:
        """Parse yes/no response"""
        if not value:
            return None
        val_str = str(value).strip().lower()
        if val_str in ("yes", "y", "true", "1", "definitely", "absolutely"):
            return True
        if val_str in ("no", "n", "false", "0", "never"):
            return False
        return None

    def get_dashboard_summary(self, db_session, days: int = 30) -> Dict[str, Any]:
        """
        Get summary statistics for the client satisfaction dashboard.

        Args:
            db_session: SQLAlchemy session
            days: Number of days to look back

        Returns:
            Dashboard summary dictionary
        """
        from portal_models import (
            ClientSurveyResponse, ClientComplaint, QualityVisit, ClientReview, CarePlanStatus
        )

        start_date = date.today() - timedelta(days=days)

        # Survey metrics
        surveys = db_session.query(ClientSurveyResponse).filter(
            ClientSurveyResponse.survey_date >= start_date
        ).all()

        survey_count = len(surveys)
        avg_satisfaction = 0
        recommend_rate = 0
        if surveys:
            ratings = [s.overall_satisfaction for s in surveys if s.overall_satisfaction]
            avg_satisfaction = round(sum(ratings) / len(ratings), 1) if ratings else 0
            recommends = [s.would_recommend for s in surveys if s.would_recommend is not None]
            recommend_rate = round(sum(recommends) / len(recommends) * 100, 1) if recommends else 0

        # Complaint metrics
        complaints = db_session.query(ClientComplaint).filter(
            ClientComplaint.complaint_date >= start_date
        ).all()

        complaint_count = len(complaints)
        open_complaints = len([c for c in complaints if c.status in ("open", "in_progress")])
        resolved_complaints = len([c for c in complaints if c.status in ("resolved", "closed")])

        # Calculate average resolution time
        resolved_with_dates = [c for c in complaints if c.resolution_date and c.complaint_date]
        avg_resolution_days = 0
        if resolved_with_dates:
            total_days = sum((c.resolution_date - c.complaint_date).days for c in resolved_with_dates)
            avg_resolution_days = round(total_days / len(resolved_with_dates), 1)

        # Quality visit metrics
        quality_visits = db_session.query(QualityVisit).filter(
            QualityVisit.visit_date >= start_date
        ).all()

        visit_count = len(quality_visits)
        avg_quality_score = 0
        if quality_visits:
            scores = []
            for v in quality_visits:
                avg = v._average_score()
                if avg:
                    scores.append(avg)
            avg_quality_score = round(sum(scores) / len(scores), 1) if scores else 0

        # Review metrics
        reviews = db_session.query(ClientReview).filter(
            ClientReview.review_date >= start_date
        ).all()

        review_count = len(reviews)
        avg_review_rating = 0
        if reviews:
            ratings = [r.rating for r in reviews if r.rating]
            avg_review_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

        # Care plan metrics
        care_plans = db_session.query(CarePlanStatus).filter(
            CarePlanStatus.status == "current"
        ).all()

        total_care_plans = len(care_plans)
        plans_due_review = len([
            p for p in care_plans
            if p.next_review_date and p.next_review_date <= date.today() + timedelta(days=30)
        ])

        return {
            "period_days": days,
            "surveys": {
                "total": survey_count,
                "average_satisfaction": avg_satisfaction,
                "recommend_rate": recommend_rate,
            },
            "complaints": {
                "total": complaint_count,
                "open": open_complaints,
                "resolved": resolved_complaints,
                "avg_resolution_days": avg_resolution_days,
            },
            "quality_visits": {
                "total": visit_count,
                "average_score": avg_quality_score,
            },
            "reviews": {
                "total": review_count,
                "average_rating": avg_review_rating,
            },
            "care_plans": {
                "total_active": total_care_plans,
                "due_for_review": plans_due_review,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    def sync_survey_responses(self, db_session, sheet_id: str = None) -> Dict[str, Any]:
        """
        Sync survey responses from Google Sheets to database.

        Args:
            db_session: SQLAlchemy session
            sheet_id: Google Sheet ID

        Returns:
            Sync result summary
        """
        from portal_models import ClientSurveyResponse

        responses = self.get_survey_responses_from_sheet(sheet_id)
        if not responses:
            return {"success": True, "synced": 0, "skipped": 0, "message": "No responses to sync"}

        synced = 0
        skipped = 0

        for resp in responses:
            # Check if already exists (by timestamp + client name)
            timestamp = resp.get("timestamp", "")
            client_name = resp.get("client_name", "")

            if not client_name:
                skipped += 1
                continue

            # Create unique identifier from form response
            form_response_id = f"{timestamp}_{client_name}".replace(" ", "_")[:255]

            existing = db_session.query(ClientSurveyResponse).filter(
                ClientSurveyResponse.google_form_response_id == form_response_id
            ).first()

            if existing:
                skipped += 1
                continue

            # Parse date from timestamp
            survey_date = date.today()
            if timestamp:
                try:
                    # Google Form timestamp format: "1/12/2026 10:30:00"
                    dt = datetime.strptime(timestamp, "%m/%d/%Y %H:%M:%S")
                    survey_date = dt.date()
                except Exception:
                    pass

            # Create new survey response
            survey = ClientSurveyResponse(
                client_name=client_name,
                survey_date=survey_date,
                overall_satisfaction=resp.get("overall_satisfaction"),
                caregiver_satisfaction=resp.get("caregiver_satisfaction"),
                communication_rating=resp.get("communication_rating"),
                would_recommend=resp.get("would_recommend"),
                feedback_comments=resp.get("feedback_comments"),
                source="google_form",
                google_form_response_id=form_response_id,
            )
            db_session.add(survey)
            synced += 1

        db_session.commit()

        return {
            "success": True,
            "synced": synced,
            "skipped": skipped,
            "message": f"Synced {synced} new responses, skipped {skipped} duplicates",
        }


# Singleton instance
client_satisfaction_service = ClientSatisfactionService()
