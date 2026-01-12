"""
RingCentral Team Messaging Scanner Service

Scans team messaging chats (Glip) for client mentions and auto-detects potential
complaints or issues that should be tracked in the Client Satisfaction dashboard.

Requirements:
- RingCentral app must have JWT auth flow enabled
- Required scopes: Team Messaging (Read), Internal Messages
"""
from __future__ import annotations

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# RingCentral API Configuration
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID", "cqaJllTcFyndtgsussicsd")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com")

# Target chat name to scan
TARGET_CHAT_NAME = os.getenv("RINGCENTRAL_TARGET_CHAT", "New Scheduling")

# Keywords that might indicate a complaint or issue
COMPLAINT_KEYWORDS = [
    "complaint", "complain", "unhappy", "upset", "angry", "frustrated",
    "problem", "issue", "concern", "worried", "disappointed", "dissatisfied",
    "missed", "late", "no-show", "no show", "didn't show", "cancelled",
    "wrong", "mistake", "error", "forgot", "missing", "incorrect",
    "rude", "unprofessional", "disrespectful",
    "hurt", "injured", "fall", "fell", "incident", "accident",
    "refund", "cancel service", "stop service", "discontinue",
    "family called", "family complaint", "son called", "daughter called",
]


class RingCentralMessagingService:
    """Service for scanning RingCentral team messaging for client mentions."""

    def __init__(self):
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._client_names_cache: List[str] = []
        self._chat_id_cache: Dict[str, str] = {}

    def _get_access_token(self) -> Optional[str]:
        """
        Get access token using JWT authentication.

        Returns:
            Access token string or None if authentication fails
        """
        if not RINGCENTRAL_JWT_TOKEN or not RINGCENTRAL_CLIENT_SECRET:
            logger.warning("RingCentral JWT credentials not configured")
            return None

        # Check if we have a valid cached token
        if self.access_token and self.token_expires_at:
            if datetime.utcnow() < self.token_expires_at - timedelta(minutes=5):
                return self.access_token

        try:
            url = f"{RINGCENTRAL_SERVER}/restapi/oauth/token"
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": RINGCENTRAL_JWT_TOKEN
            }

            response = requests.post(
                url,
                data=data,
                auth=(RINGCENTRAL_CLIENT_ID, RINGCENTRAL_CLIENT_SECRET),
                timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                logger.info("RingCentral access token obtained successfully")
                return self.access_token
            else:
                logger.error(f"Failed to get RingCentral access token: {response.status_code}")
                logger.error(response.text)
                return None

        except Exception as e:
            logger.error(f"Error getting RingCentral access token: {e}")
            return None

    def _api_request(self, endpoint: str, method: str = "GET", params: Dict = None) -> Optional[Dict]:
        """Make an authenticated API request to RingCentral."""
        token = self._get_access_token()
        if not token:
            return None

        try:
            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0{endpoint}"
            headers = {"Authorization": f"Bearer {token}"}

            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"RingCentral API error: {response.status_code} - {response.text[:500]}")
                return None

        except Exception as e:
            logger.error(f"RingCentral API request failed: {e}")
            return None

    def list_teams(self) -> List[Dict[str, Any]]:
        """
        List all teams/chats the user has access to.

        Returns:
            List of team dictionaries with id, name, description, etc.
        """
        result = self._api_request("/glip/teams")
        if result:
            teams = result.get("records", [])
            logger.info(f"Found {len(teams)} RingCentral teams")
            return teams
        return []

    def find_chat_by_name(self, chat_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a team/chat by name.

        Args:
            chat_name: Name of the chat to find (case-insensitive)

        Returns:
            Team dictionary or None if not found
        """
        # Check cache first
        if chat_name.lower() in self._chat_id_cache:
            chat_id = self._chat_id_cache[chat_name.lower()]
            result = self._api_request(f"/glip/teams/{chat_id}")
            if result:
                return result

        teams = self.list_teams()
        for team in teams:
            team_name = team.get("name", "").lower()
            if chat_name.lower() in team_name or team_name in chat_name.lower():
                self._chat_id_cache[chat_name.lower()] = team["id"]
                return team

        logger.warning(f"Chat '{chat_name}' not found")
        return None

    def get_chat_messages(
        self,
        chat_id: str,
        since: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a specific chat.

        Args:
            chat_id: The team/chat ID
            since: Only get messages after this time (defaults to last 24 hours)
            limit: Maximum number of messages to retrieve

        Returns:
            List of message dictionaries
        """
        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)

        params = {
            "recordCount": min(limit, 250),  # RC API limit
            "dateFrom": since.isoformat() + "Z"
        }

        result = self._api_request(f"/glip/chats/{chat_id}/posts", params=params)
        if result:
            messages = result.get("records", [])
            logger.info(f"Retrieved {len(messages)} messages from chat {chat_id}")
            return messages
        return []

    def load_client_names(self, db_session) -> List[str]:
        """
        Load client names from the database for matching.

        Args:
            db_session: SQLAlchemy session

        Returns:
            List of client names
        """
        from portal_models import CarePlanStatus

        try:
            # Get unique client names from care plans
            clients = db_session.query(CarePlanStatus.client_name).distinct().all()
            self._client_names_cache = [c[0] for c in clients if c[0]]
            logger.info(f"Loaded {len(self._client_names_cache)} client names for matching")
            return self._client_names_cache
        except Exception as e:
            logger.error(f"Error loading client names: {e}")
            return []

    def find_client_mentions(
        self,
        message_text: str,
        client_names: List[str] = None
    ) -> List[Tuple[str, int]]:
        """
        Find client name mentions in a message.

        Args:
            message_text: The message text to scan
            client_names: List of client names to search for

        Returns:
            List of (client_name, match_position) tuples
        """
        if client_names is None:
            client_names = self._client_names_cache

        mentions = []
        text_lower = message_text.lower()

        for client_name in client_names:
            if not client_name:
                continue

            # Split name for partial matching
            name_parts = client_name.lower().split()

            # Check for full name match
            if client_name.lower() in text_lower:
                pos = text_lower.find(client_name.lower())
                mentions.append((client_name, pos))
                continue

            # Check for last name match (if 2+ parts)
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                # Only match if it's a standalone word
                pattern = rf'\b{re.escape(last_name)}\b'
                match = re.search(pattern, text_lower)
                if match:
                    mentions.append((client_name, match.start()))

        return mentions

    def detect_potential_complaints(
        self,
        message_text: str
    ) -> Tuple[bool, List[str]]:
        """
        Detect if a message might contain a complaint or issue.

        Args:
            message_text: The message text to analyze

        Returns:
            Tuple of (is_potential_complaint, list of matched keywords)
        """
        text_lower = message_text.lower()
        matched_keywords = []

        for keyword in COMPLAINT_KEYWORDS:
            if keyword in text_lower:
                matched_keywords.append(keyword)

        return len(matched_keywords) > 0, matched_keywords

    def scan_chat_for_client_issues(
        self,
        db_session,
        chat_name: str = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Scan a chat for client mentions that might indicate issues/complaints.

        Args:
            db_session: SQLAlchemy session
            chat_name: Name of chat to scan (defaults to TARGET_CHAT_NAME)
            hours_back: How many hours back to scan

        Returns:
            Dictionary with scan results
        """
        chat_name = chat_name or TARGET_CHAT_NAME

        # Find the target chat
        chat = self.find_chat_by_name(chat_name)
        if not chat:
            return {
                "success": False,
                "error": f"Chat '{chat_name}' not found",
                "potential_complaints": []
            }

        # Load client names
        client_names = self.load_client_names(db_session)
        if not client_names:
            logger.warning("No client names loaded - scanning for keywords only")

        # Get messages
        since = datetime.utcnow() - timedelta(hours=hours_back)
        messages = self.get_chat_messages(chat["id"], since=since)

        potential_complaints = []

        for msg in messages:
            text = msg.get("text", "")
            if not text:
                continue

            # Check for client mentions
            mentions = self.find_client_mentions(text, client_names)

            # Check for complaint keywords
            is_complaint, keywords = self.detect_potential_complaints(text)

            # If we found a client mention with complaint keywords, flag it
            if mentions and is_complaint:
                for client_name, _ in mentions:
                    potential_complaints.append({
                        "client_name": client_name,
                        "message_text": text[:500],  # Truncate for storage
                        "matched_keywords": keywords,
                        "author": msg.get("creatorId"),
                        "timestamp": msg.get("creationTime"),
                        "chat_name": chat_name,
                        "message_id": msg.get("id"),
                        "severity": "high" if len(keywords) > 2 else "medium"
                    })
            # Also flag messages with complaint keywords but no specific client
            elif is_complaint and not mentions:
                potential_complaints.append({
                    "client_name": None,
                    "message_text": text[:500],
                    "matched_keywords": keywords,
                    "author": msg.get("creatorId"),
                    "timestamp": msg.get("creationTime"),
                    "chat_name": chat_name,
                    "message_id": msg.get("id"),
                    "severity": "low"
                })

        return {
            "success": True,
            "chat_name": chat_name,
            "messages_scanned": len(messages),
            "potential_complaints": potential_complaints,
            "scan_period_hours": hours_back,
            "scanned_at": datetime.utcnow().isoformat()
        }

    def auto_create_complaints(
        self,
        db_session,
        scan_results: Dict[str, Any],
        auto_create: bool = False
    ) -> Dict[str, Any]:
        """
        Automatically create complaint records from scan results.

        Args:
            db_session: SQLAlchemy session
            scan_results: Results from scan_chat_for_client_issues
            auto_create: If True, automatically create records (else just preview)

        Returns:
            Summary of created/skipped complaints
        """
        from portal_models import ClientComplaint

        if not scan_results.get("success"):
            return scan_results

        created = []
        skipped = []

        for complaint in scan_results.get("potential_complaints", []):
            # Skip if no client name and it's low severity
            if not complaint.get("client_name") and complaint.get("severity") == "low":
                skipped.append({
                    "reason": "No client identified, low severity",
                    "message_preview": complaint["message_text"][:100]
                })
                continue

            # Check if already exists (by message_id)
            message_id = complaint.get("message_id")
            if message_id:
                existing = db_session.query(ClientComplaint).filter(
                    ClientComplaint.notes.like(f'%ringcentral_msg:{message_id}%')
                ).first()

                if existing:
                    skipped.append({
                        "reason": "Already tracked",
                        "complaint_id": existing.id
                    })
                    continue

            if auto_create:
                # Create new complaint record
                new_complaint = ClientComplaint(
                    client_name=complaint.get("client_name") or "Unknown Client",
                    complaint_date=datetime.utcnow().date(),
                    category="auto_detected",
                    severity=complaint.get("severity", "medium"),
                    description=f"Auto-detected from {complaint.get('chat_name')} chat",
                    details=complaint.get("message_text"),
                    status="review",  # Requires manual review
                    reported_by="RingCentral Scanner",
                    notes=f"Keywords: {', '.join(complaint.get('matched_keywords', []))}\n"
                          f"ringcentral_msg:{message_id}"
                )
                db_session.add(new_complaint)
                created.append({
                    "client_name": new_complaint.client_name,
                    "keywords": complaint.get("matched_keywords"),
                    "severity": new_complaint.severity
                })
            else:
                created.append({
                    "would_create": True,
                    "client_name": complaint.get("client_name"),
                    "keywords": complaint.get("matched_keywords"),
                    "severity": complaint.get("severity")
                })

        if auto_create:
            db_session.commit()

        return {
            "success": True,
            "mode": "created" if auto_create else "preview",
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created": created,
            "skipped": skipped
        }

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the RingCentral messaging integration.

        Returns:
            Status dictionary with configuration and connectivity info
        """
        has_credentials = bool(RINGCENTRAL_JWT_TOKEN and RINGCENTRAL_CLIENT_SECRET)

        status = {
            "configured": has_credentials,
            "target_chat": TARGET_CHAT_NAME,
            "server": RINGCENTRAL_SERVER,
            "api_connected": False,
            "teams_available": [],
            "error": None
        }

        if has_credentials:
            token = self._get_access_token()
            if token:
                status["api_connected"] = True
                teams = self.list_teams()
                status["teams_available"] = [t.get("name") for t in teams[:10]]
            else:
                status["error"] = "Failed to authenticate with RingCentral API"
        else:
            status["error"] = "Missing RINGCENTRAL_CLIENT_SECRET or RINGCENTRAL_JWT_TOKEN"

        return status


# Singleton instance
ringcentral_messaging_service = RingCentralMessagingService()
