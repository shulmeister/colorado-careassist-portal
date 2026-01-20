"""
Client Satisfaction Service

Provides functionality for tracking client satisfaction metrics:
- Survey responses (from Google Forms/Sheets or manual entry)
- Complaints tracking and resolution
- Quality visits
- External reviews
- Care plan status
- WellSky operational data integration
- AI-powered satisfaction risk prediction (Phoebe/Zingage style)
"""
from __future__ import annotations

import os
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import gspread
from google.oauth2.service_account import Credentials

# Import WellSky service for operational data
try:
    from services.wellsky_service import wellsky_service, WellSkyClient
except ImportError:
    wellsky_service = None
    WellSkyClient = None

logger = logging.getLogger(__name__)

# Google Sheets configuration for survey responses
SURVEY_RESPONSES_SHEET_ID = os.getenv("CLIENT_SURVEY_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")


class ClientSatisfactionService:
    """
    Service for managing client satisfaction data.

    Integrates multiple data sources:
    - Google Sheets/Forms for survey responses
    - Portal database for complaints, quality visits, reviews
    - WellSky API for operational data (clients, shifts, care plans, engagement)

    Provides AI-powered satisfaction risk prediction similar to Zingage Operator
    and Phoebe.work functionality.
    """

    def __init__(self):
        self.sheets_client = None
        self.wellsky = wellsky_service  # May be None if import failed
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

    # =========================================================================
    # WellSky Integration Methods
    # =========================================================================

    @property
    def wellsky_available(self) -> bool:
        """Check if WellSky service is available"""
        return self.wellsky is not None

    def get_enhanced_dashboard_summary(self, db_session, days: int = 30) -> Dict[str, Any]:
        """
        Get enhanced dashboard summary combining portal data with WellSky operational data.

        This provides a complete picture of client satisfaction by merging:
        - Survey/complaint/review data from portal database
        - Operational metrics from WellSky (hours, EVV, care plans)
        - AI-calculated risk indicators

        Args:
            db_session: SQLAlchemy session
            days: Number of days to look back

        Returns:
            Enhanced dashboard summary with WellSky data
        """
        # Get base summary from portal database
        summary = self.get_dashboard_summary(db_session, days)

        # Add WellSky operational data if available
        if self.wellsky_available:
            try:
                wellsky_ops = self.wellsky.get_operations_summary(days)
                summary["wellsky"] = {
                    "available": True,
                    "mode": "mock" if self.wellsky.is_mock_mode else "live",
                    "clients": wellsky_ops.get("clients", {}),
                    "caregivers": wellsky_ops.get("caregivers", {}),
                    "shifts": wellsky_ops.get("shifts", {}),
                    "hours": wellsky_ops.get("hours", {}),
                    "compliance": wellsky_ops.get("compliance", {}),
                }

                # Get at-risk clients count
                at_risk = self.get_at_risk_clients()
                summary["at_risk_clients"] = {
                    "total": len(at_risk),
                    "high_risk": len([c for c in at_risk if c.get("risk_level") == "high"]),
                    "medium_risk": len([c for c in at_risk if c.get("risk_level") == "medium"]),
                }

                # Get care plan status
                care_plans_due = self.wellsky.get_care_plans_due_for_review()
                summary["wellsky"]["care_plans_due"] = len(care_plans_due)

            except Exception as e:
                logger.error(f"Error fetching WellSky data: {e}")
                summary["wellsky"] = {"available": False, "error": str(e)}
        else:
            summary["wellsky"] = {"available": False, "error": "WellSky service not configured"}

        return summary

    def get_at_risk_clients(self, threshold: int = 40) -> List[Dict[str, Any]]:
        """
        Get clients with satisfaction risk indicators above threshold.

        Uses WellSky operational data to identify clients at risk:
        - Declining hours
        - High caregiver turnover
        - Missed visits
        - Low family portal engagement
        - Overdue care plan reviews

        This is the core of Zingage Operator / Phoebe-style proactive monitoring.

        Args:
            threshold: Risk score threshold (0-100)

        Returns:
            List of at-risk client indicators, sorted by risk score
        """
        if not self.wellsky_available:
            logger.warning("WellSky not available - cannot calculate at-risk clients")
            return []

        try:
            return self.wellsky.get_at_risk_clients(threshold)
        except Exception as e:
            logger.error(f"Error getting at-risk clients: {e}")
            return []

    def get_client_satisfaction_indicators(self, client_id: str) -> Dict[str, Any]:
        """
        Get detailed satisfaction risk indicators for a specific client.

        Combines:
        - WellSky operational signals (hours, visits, engagement)
        - Portal satisfaction data (surveys, complaints)
        - AI-generated risk score and recommendations

        Args:
            client_id: WellSky client ID

        Returns:
            Comprehensive satisfaction indicators
        """
        if not self.wellsky_available:
            return {"error": "WellSky service not configured", "client_id": client_id}

        try:
            return self.wellsky.get_client_satisfaction_indicators(client_id)
        except Exception as e:
            logger.error(f"Error getting client indicators: {e}")
            return {"error": str(e), "client_id": client_id}

    def get_low_engagement_families(self, threshold: float = 30.0) -> List[Dict[str, Any]]:
        """
        Get families with low portal engagement (proactive outreach candidates).

        Low engagement often precedes satisfaction issues - this enables
        proactive check-ins before problems arise.

        Args:
            threshold: Engagement score threshold (0-100)

        Returns:
            List of clients with low family engagement
        """
        if not self.wellsky_available:
            return []

        try:
            results = []
            low_engagement = self.wellsky.get_low_engagement_clients(threshold)
            for client, activity in low_engagement:
                results.append({
                    "client_id": client.id,
                    "client_name": client.full_name,
                    "city": client.city,
                    "payer_source": client.payer_source,
                    "days_since_login": (datetime.utcnow() - activity.last_login).days if activity.last_login else 999,
                    "engagement_score": activity.engagement_score,
                    "shift_notes_viewed": activity.shift_notes_viewed_30d,
                    "recommended_action": "Proactive phone check-in" if activity.login_count_30d == 0 else "Send portal reminder",
                })
            return results
        except Exception as e:
            logger.error(f"Error getting low engagement families: {e}")
            return []

    def get_clients_needing_surveys(self, days_since_last: int = 90) -> List[Dict[str, Any]]:
        """
        Get active clients who haven't had a satisfaction survey recently.

        Supports automated survey triggering for systematic feedback collection.

        Args:
            days_since_last: Days since last survey to consider due

        Returns:
            List of clients needing surveys
        """
        if not self.wellsky_available:
            return []

        try:
            results = []
            clients = self.wellsky.get_clients(status=None)  # Get all
            active_clients = [c for c in clients if c.is_active]

            # TODO: Cross-reference with portal survey database to find
            # clients without recent surveys

            for client in active_clients:
                # For now, include clients with tenure > 30 days
                if client.tenure_days >= 30:
                    results.append({
                        "client_id": client.id,
                        "client_name": client.full_name,
                        "tenure_days": client.tenure_days,
                        "payer_source": client.payer_source,
                        "survey_due": True,  # Would be calculated from portal data
                    })

            return results[:20]  # Limit results
        except Exception as e:
            logger.error(f"Error getting clients needing surveys: {e}")
            return []

    def get_upcoming_anniversaries(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Get clients with upcoming service anniversaries.

        Anniversaries are ideal times for:
        - Testimonial requests
        - Referral asks
        - Satisfaction check-ins
        - Recognition/appreciation

        Args:
            days_ahead: Days to look ahead

        Returns:
            List of clients with upcoming anniversaries
        """
        if not self.wellsky_available:
            return []

        try:
            results = []
            clients = self.wellsky.get_clients(status=None)
            active_clients = [c for c in clients if c.is_active and c.start_date]

            today = date.today()

            for client in active_clients:
                # Check for monthly anniversaries (6mo, 12mo, 18mo, etc.)
                months_of_service = client.tenure_days // 30
                next_milestone = ((months_of_service // 6) + 1) * 6  # Next 6-month milestone

                # Calculate days until next milestone
                milestone_date = client.start_date + timedelta(days=next_milestone * 30)
                days_until = (milestone_date - today).days

                if 0 <= days_until <= days_ahead:
                    milestone_type = f"{next_milestone} months" if next_milestone < 12 else f"{next_milestone // 12} year{'s' if next_milestone >= 24 else ''}"
                    results.append({
                        "client_id": client.id,
                        "client_name": client.full_name,
                        "start_date": client.start_date.isoformat(),
                        "milestone": milestone_type,
                        "milestone_date": milestone_date.isoformat(),
                        "days_until": days_until,
                        "recommended_action": "Request testimonial" if next_milestone >= 12 else "Send appreciation message",
                    })

            # Sort by days until milestone
            results.sort(key=lambda x: x["days_until"])
            return results
        except Exception as e:
            logger.error(f"Error getting upcoming anniversaries: {e}")
            return []

    # =========================================================================
    # AI Care Coordinator Methods (Zingage/Phoebe Style)
    # =========================================================================

    def get_satisfaction_alerts(self) -> List[Dict[str, Any]]:
        """
        Get prioritized satisfaction alerts requiring attention.

        This is the core "AI Care Coordinator" view - surfacing issues
        that need human review or automated action.

        Returns alerts for:
        - High-risk clients needing intervention
        - Overdue care plan reviews
        - Low engagement families
        - Unresolved complaints
        - Pending quality visits

        Returns:
            Prioritized list of alerts with recommended actions
        """
        alerts = []

        # High-risk clients (from WellSky)
        if self.wellsky_available:
            try:
                at_risk = self.get_at_risk_clients(threshold=50)
                for client in at_risk[:5]:  # Top 5 highest risk
                    alerts.append({
                        "type": "high_risk_client",
                        "priority": "high" if client.get("risk_level") == "high" else "medium",
                        "client_id": client.get("client_id"),
                        "client_name": client.get("client_name"),
                        "risk_score": client.get("risk_score"),
                        "message": f"{client.get('client_name')} has risk score of {client.get('risk_score')}",
                        "factors": client.get("risk_factors", []),
                        "recommended_actions": client.get("recommendations", []),
                        "alert_category": "Satisfaction Risk",
                    })

                # Low engagement families
                low_engagement = self.get_low_engagement_families(threshold=20)
                for family in low_engagement[:3]:
                    alerts.append({
                        "type": "low_engagement",
                        "priority": "medium",
                        "client_id": family.get("client_id"),
                        "client_name": family.get("client_name"),
                        "message": f"No family portal activity in {family.get('days_since_login', 'many')} days",
                        "recommended_actions": [family.get("recommended_action", "Proactive outreach")],
                        "alert_category": "Family Engagement",
                    })

                # Care plans due for review
                care_plans_due = self.wellsky.get_care_plans_due_for_review(days_ahead=14)
                for cp in care_plans_due[:3]:
                    client = self.wellsky.get_client(cp.client_id)
                    client_name = client.full_name if client else cp.client_id
                    alerts.append({
                        "type": "care_plan_review",
                        "priority": "medium" if cp.days_until_review > 0 else "high",
                        "client_id": cp.client_id,
                        "client_name": client_name,
                        "message": f"Care plan review {'overdue' if cp.days_until_review <= 0 else f'due in {cp.days_until_review} days'}",
                        "recommended_actions": ["Schedule care plan review meeting", "Update authorized services"],
                        "alert_category": "Care Plan",
                    })

            except Exception as e:
                logger.error(f"Error generating WellSky alerts: {e}")

        # Sort by priority (high first)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

        return alerts

    def get_ai_coordinator_dashboard(self, db_session) -> Dict[str, Any]:
        """
        Get the AI Care Coordinator dashboard view.

        This provides the Zingage Operator / Phoebe-style overview:
        - Real-time alerts requiring attention
        - At-risk client summary
        - Proactive outreach queue
        - Satisfaction trends

        Args:
            db_session: SQLAlchemy session for portal data

        Returns:
            Complete AI coordinator dashboard data
        """
        # Get base metrics
        summary = self.get_enhanced_dashboard_summary(db_session, days=30)

        # Get prioritized alerts
        alerts = self.get_satisfaction_alerts()

        # Get proactive outreach opportunities
        outreach_queue = []

        if self.wellsky_available:
            # Add low engagement families
            low_engagement = self.get_low_engagement_families(threshold=30)
            for item in low_engagement[:5]:
                outreach_queue.append({
                    "type": "engagement_check",
                    "client_id": item["client_id"],
                    "client_name": item["client_name"],
                    "reason": "Low portal engagement",
                    "suggested_action": item["recommended_action"],
                    "channel": "phone",  # Recommend phone for engagement issues
                })

            # Add upcoming anniversaries
            anniversaries = self.get_upcoming_anniversaries(days_ahead=14)
            for item in anniversaries[:5]:
                outreach_queue.append({
                    "type": "anniversary",
                    "client_id": item["client_id"],
                    "client_name": item["client_name"],
                    "reason": f"{item['milestone']} anniversary",
                    "suggested_action": item["recommended_action"],
                    "channel": "email",  # Email appropriate for celebrations
                })

            # Add clients needing surveys
            survey_due = self.get_clients_needing_surveys(days_since_last=90)
            for item in survey_due[:5]:
                outreach_queue.append({
                    "type": "survey_request",
                    "client_id": item["client_id"],
                    "client_name": item["client_name"],
                    "reason": f"No survey in {item['tenure_days']} days",
                    "suggested_action": "Send satisfaction survey",
                    "channel": "sms",  # SMS for survey requests
                })

        return {
            "summary": summary,
            "alerts": {
                "total": len(alerts),
                "high_priority": len([a for a in alerts if a.get("priority") == "high"]),
                "items": alerts[:10],  # Top 10 alerts
            },
            "outreach_queue": {
                "total": len(outreach_queue),
                "items": outreach_queue[:15],
            },
            "wellsky_status": {
                "connected": self.wellsky_available,
                "mode": "mock" if self.wellsky_available and self.wellsky.is_mock_mode else "live" if self.wellsky_available else "disconnected",
            },
            "generated_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
client_satisfaction_service = ClientSatisfactionService()
