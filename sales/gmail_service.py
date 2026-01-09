import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailService:
    """Service for integrating with Gmail API using domain-wide delegation"""

    def __init__(self):
        self.service_account_email = os.getenv("GMAIL_SERVICE_ACCOUNT_EMAIL")
        self.service_account_key = os.getenv("GMAIL_SERVICE_ACCOUNT_KEY")  # JSON string

        # Support multiple mailboxes via comma-separated env var, fall back to legacy single-user env
        multi_user_env = os.getenv("GMAIL_USER_EMAILS")
        if multi_user_env:
            self.user_emails = [
                email.strip()
                for email in multi_user_env.split(",")
                if email.strip()
            ]
        else:
            single_user = os.getenv(
                "GMAIL_USER_EMAIL", "maryssa@coloradocareassist.com"
            )
            self.user_emails = [single_user]

        # Legacy attribute retained for backwards compatibility (first email in list)
        self.user_email = self.user_emails[0] if self.user_emails else ""

        if not all([self.service_account_email, self.service_account_key, self.user_emails]):
            logger.warning(
                "Gmail credentials or user emails not configured. Email functionality will be disabled."
            )
            self.enabled = False
            self.base_credentials = None
            self.service_cache: Dict[str, Any] = {}
        else:
            self.enabled = True
            self.base_credentials = None
            self.service_cache: Dict[str, Any] = {}
            self.last_user_counts: Dict[str, int] = {}
            self._initialize_credentials()

    def _initialize_credentials(self):
        """Load service account credentials (without binding to a specific user)."""
        if not self.enabled:
            return

        try:
            credentials_info = json.loads(self.service_account_key)
            self.base_credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            )
            self.service_cache = {}
            logger.info(
                "Gmail base credentials loaded; ready to impersonate %d users.",
                len(self.user_emails),
            )
        except Exception as exc:
            logger.error(f"Error loading Gmail credentials: {exc}")
            self.enabled = False
            self.base_credentials = None
            self.service_cache = {}

    def _get_service_for_user(self, user_email: str):
        """Build (or reuse) a Gmail service for a specific user via domain-wide delegation."""
        if not self.base_credentials:
            return None

        if user_email in self.service_cache:
            return self.service_cache[user_email]

        try:
            delegated_credentials = self.base_credentials.with_subject(user_email)
            service = build(
                "gmail",
                "v1",
                credentials=delegated_credentials,
                cache_discovery=False,
            )
            self.service_cache[user_email] = service
            logger.info(f"Gmail service initialized for {user_email}")
            return service
        except Exception as exc:
            logger.error(f"Error building Gmail service for {user_email}: {exc}")
            return None

    def _count_sent_for_service(self, service, user_email: str, after_date: str) -> int:
        """Count sent messages for a given Gmail service object."""
        if service is None:
            return 0

        query = f"in:sent after:{after_date}"
        messages: list = []
        page_token: Optional[str] = None

        while True:
            try:
                request_params = {
                    "userId": "me",
                    "q": query,
                    "maxResults": 500,
                }
                if page_token:
                    request_params["pageToken"] = page_token

                result = service.users().messages().list(**request_params).execute()
                messages.extend(result.get("messages", []))

                page_token = result.get("nextPageToken")
                if not page_token:
                    break
            except HttpError as error:
                logger.error(f"Gmail API error for {user_email}: {error}")
                break
            except Exception as exc:
                logger.error(
                    f"Unexpected error while counting emails for {user_email}: {exc}",
                    exc_info=True,
                )
                break

        count = len(messages)
        logger.info(f"Found {count} emails sent by {user_email} in the last 7 days")
        return count

    def get_emails_sent_last_7_days(self) -> Dict[str, Any]:
        """
        Get counts of emails sent in the last 7 days using Admin Reports API.
        This matches Google Workspace Admin Console reporting.
        Returns a dict: {"total": int, "per_user": {email: count}}
        """
        if not self.enabled or not self.base_credentials:
            logger.warning("Gmail service not available")
            return {"total": 0, "per_user": {}}

        # Use Admin Reports API for accurate organizational email counts
        try:
            # Build Admin SDK Reports service
            admin_credentials = service_account.Credentials.from_service_account_info(
                json.loads(self.service_account_key),
                scopes=['https://www.googleapis.com/auth/admin.reports.audit.readonly']
            )
            # Need to impersonate an admin user for Reports API
            admin_email = os.getenv("GMAIL_ADMIN_EMAIL", "jason@coloradocareassist.com")
            admin_credentials = admin_credentials.with_subject(admin_email)
            
            reports_service = build('admin', 'reports_v1', credentials=admin_credentials, cache_discovery=False)
            
            # Get date range (last 7 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            per_user_counts: Dict[str, int] = {}
            total = 0
            
            # Query Gmail usage for each user
            for email in self.user_emails:
                try:
                    # Get Gmail activity for user
                    results = reports_service.userUsageReport().get(
                        userKey=email,
                        date=start_date_str,
                        parameters='gmail:num_emails_sent'
                    ).execute()
                    
                    # Extract emails sent
                    if 'usageReports' in results:
                        for report in results['usageReports']:
                            for param in report.get('parameters', []):
                                if param.get('name') == 'gmail:num_emails_sent':
                                    count = int(param.get('intValue', 0))
                                    per_user_counts[email] = count
                                    total += count
                                    logger.info(f"Admin Reports API: {email} sent {count} emails")
                                    break
                    else:
                        logger.warning(f"No usage reports found for {email}")
                        per_user_counts[email] = 0
                        
                except HttpError as e:
                    logger.error(f"Admin Reports API error for {email}: {e}")
                    # Fallback to Gmail API for this user
                    count = self._count_sent_via_gmail_api(email, start_date)
                    per_user_counts[email] = count
                    total += count
                except Exception as e:
                    logger.error(f"Error getting reports for {email}: {e}", exc_info=True)
                    per_user_counts[email] = 0
            
            logger.info(f"Total emails sent (last 7 days via Admin Reports): {total}")
            return {"total": total, "per_user": per_user_counts}
            
        except Exception as e:
            logger.error(f"Admin Reports API failed, falling back to Gmail API: {e}", exc_info=True)
            # Fallback to original Gmail API method
            return self._get_emails_via_gmail_api()
    
    def _count_sent_via_gmail_api(self, email: str, start_date: datetime) -> int:
        """Helper: Count sent emails for a user using Gmail API"""
        after_date = start_date.strftime("%Y/%m/%d")
        service = self._get_service_for_user(email)
        return self._count_sent_for_service(service, email, after_date)
    
    def _get_emails_via_gmail_api(self) -> Dict[str, Any]:
        """Fallback: Count emails using Gmail API (original method)"""
        seven_days_ago = datetime.now() - timedelta(days=7)
        after_date = seven_days_ago.strftime("%Y/%m/%d")

        per_user_counts: Dict[str, int] = {}
        total = 0

        for email in self.user_emails:
            service = self._get_service_for_user(email)
            count = self._count_sent_for_service(service, email, after_date)
            per_user_counts[email] = count
            total += count

        self.last_user_counts = per_user_counts
        return {"total": total, "per_user": per_user_counts}

    def test_connection(self) -> Dict[str, Any]:
        """Test Gmail API connection for the first configured user."""
        if not self.enabled or not self.user_emails:
            return {
                "success": False,
                "error": "Gmail not configured",
            }

        primary_email = self.user_emails[0]
        service = self._get_service_for_user(primary_email)
        if service is None:
            return {
                "success": False,
                "error": f"Unable to initialize Gmail service for {primary_email}",
            }

        try:
            profile = service.users().getProfile(userId="me").execute()
            return {
                "success": True,
                "email": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal", 0),
            }
        except Exception as exc:
            logger.error(f"Error testing Gmail connection: {exc}")
            return {
                "success": False,
                "error": str(exc),
            }
