import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_paths = [
        Path(__file__).parent.parent / '.env',
        Path.home() / '.gigi-env',
        Path('/Users/shulmeister/.gigi-env'),
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

# Load from environment with fallback defaults
WORK_CLIENT_ID = os.getenv("GOOGLE_WORK_CLIENT_ID", "516104802353-sgilgrdn7ohmfapbfuucfuforgcu6air.apps.googleusercontent.com")
WORK_CLIENT_SECRET = os.getenv("GOOGLE_WORK_CLIENT_SECRET", "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")
WORK_REFRESH_TOKEN = os.getenv("GOOGLE_WORK_REFRESH_TOKEN")  # This MUST be set - requires OAuth flow

PERS_CLIENT_ID = os.getenv("GOOGLE_PERS_CLIENT_ID")
PERS_CLIENT_SECRET = os.getenv("GOOGLE_PERS_CLIENT_SECRET")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly", 
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

class GoogleService:
    def __init__(self):
        self._creds = None
        if all([WORK_CLIENT_ID, WORK_CLIENT_SECRET, WORK_REFRESH_TOKEN]):
            self._creds = Credentials(
                token=None,
                refresh_token=WORK_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=WORK_CLIENT_ID,
                client_secret=WORK_CLIENT_SECRET,
                scopes=SCOPES
            )
            logger.info("✓ Google Service initialized via environment variables")
        else:
            logger.warning("Google Service credentials missing from environment")

    def _get_service(self, name, version):
        if not self._creds:
            return None
            
        if not self._creds.valid:
            if self._creds.expired and self._creds.refresh_token:
                try:
                    self._creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Google token refresh failed: {e}")
                    return None
        return build(name, version, credentials=self._creds)

    def search_emails(self, query="is:unread", max_results=5):
        """Search Gmail for messages. Includes personal mail via forwarding labels."""
        try:
            service = self._get_service('gmail', 'v1')
            if not service: return []
            
            # If searching for personal stuff, look for the forward label
            if "personal" in query.lower() or "shulmeister" in query.lower():
                query = f"({query}) OR label:\"Gigi's Inbox\""
                
            results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = results.get('messages', [])
            
            detailed_messages = []
            for msg in messages:
                m = service.users().messages().get(userId='me', id=msg['id']).execute()
                headers = m.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                snippet = m.get('snippet', '')
                detailed_messages.append({
                    "id": msg['id'],
                    "from": sender,
                    "subject": subject,
                    "snippet": snippet
                })
            return detailed_messages
        except Exception as e:
            logger.error(f"Gmail search error: {e}")
            return []

    def get_calendar_events(self, days=1, max_results=10):
        """List upcoming events from all accessible calendars"""
        try:
            service = self._get_service('calendar', 'v3')
            if not service: return []
            
            now = datetime.utcnow().isoformat() + 'Z'
            end = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
            
            # Get list of all calendars
            calendar_list = service.calendarList().list().execute().get('items', [])
            
            all_events = []
            for cal in calendar_list:
                if cal.get('selected'):
                    events_result = service.events().list(
                        calendarId=cal['id'], timeMin=now, timeMax=end,
                        maxResults=max_results, singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    events = events_result.get('items', [])
                    
                    for event in events:
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        all_events.append({
                            "summary": event.get('summary', 'No Title'),
                            "start": start,
                            "location": event.get('location', 'N/A'),
                            "calendar": cal.get('summaryOverride', cal.get('summary'))
                        })
            
            all_events.sort(key=lambda x: x['start'])
            return all_events[:max_results]
        except Exception as e:
            logger.error(f"Calendar error: {e}")
            return []

# Singleton instance
google_service = GoogleService()