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

    def _api_request(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Optional[Dict]:
        """Make an authenticated API request to RingCentral."""
        token = self._get_access_token()
        if not token:
            return None

        try:
            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0{endpoint}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, params=params, json=data, timeout=30)
            else:
                logger.error(f"Unsupported method: {method}")
                return None

            if response.status_code in (200, 201):
                return response.json()
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                logger.error(f"RC API Rate Limit (429). Retry after: {retry_after}s")
                return None
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
        Load client names from the database or WellSky for matching.
        """
        from services.wellsky_service import wellsky_service
        
        # 1. Try WellSky (Source of Truth)
        if wellsky_service and wellsky_service.is_configured:
            try:
                clients = wellsky_service.get_clients(status="active", limit=500)
                if clients:
                    self._client_names_cache = [c.full_name for c in clients]
                    logger.info(f"Loaded {len(self._client_names_cache)} client names from WellSky")
                    return self._client_names_cache
            except Exception as e:
                logger.warning(f"Failed to load client names from WellSky: {e}")

        # 2. Fallback to Portal DB
        from portal.portal_models import CarePlanStatus
        try:
            clients = db_session.query(CarePlanStatus.client_name).distinct().all()
            self._client_names_cache = [c[0] for c in clients if c[0]]
            logger.info(f"Loaded {len(self._client_names_cache)} client names from database")
            return self._client_names_cache
        except Exception as e:
            logger.error(f"Error loading client names from DB: {e}")
            
        return self._client_names_cache or []

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
            first_name = name_parts[0] if name_parts else None

            # 1. Check for full name match (highest confidence)
            if client_name.lower() in text_lower:
                pos = text_lower.find(client_name.lower())
                mentions.append((client_name, pos))
                continue

            # 2. Check for First Name match (common in chats)
            if first_name and len(first_name) > 2:
                # Use word boundary to avoid partial name matches (e.g. "Ma" in "Maryland")
                pattern = rf'\b{re.escape(first_name)}\b'
                match = re.search(pattern, text_lower)
                if match:
                    mentions.append((client_name, match.start()))
                    continue

            # 3. Check for last name match (if 2+ parts)
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
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
        auto_create: bool = False,
        push_to_wellsky: bool = True
    ) -> Dict[str, Any]:
        """
        Automatically create complaint records and sync to WellSky.
        """
        from portal.portal_models import ClientComplaint
        from services.wellsky_service import wellsky_service

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
                # 1. Create local Portal record
                new_complaint = ClientComplaint(
                    client_name=complaint.get("client_name") or "Unknown Client",
                    complaint_date=datetime.utcnow().date(),
                    category="auto_detected",
                    severity=complaint.get("severity", "medium"),
                    description=f"Auto-detected from {complaint.get('chat_name')} chat",
                    details=complaint.get("message_text"),
                    status="review",
                    reported_by="RingCentral Scanner",
                    notes=f"Keywords: {', '.join(complaint.get('matched_keywords', []))}\n"
                          f"ringcentral_msg:{message_id}"
                )
                db_session.add(new_complaint)
                
                # 2. PUSH TO WELLSKY (Direct Action)
                wellsky_status = "skipped"
                if push_to_wellsky and wellsky_service and wellsky_service.is_configured:
                    try:
                        # Find client in WellSky to get ID
                        client_name = complaint.get("client_name")
                        wellsky_client = None
                        if client_name:
                            search_res = wellsky_service.search_patients(last_name=client_name.split()[-1])
                            if search_res:
                                wellsky_client = search_res[0] # Take first match
                        
                        if wellsky_client:
                            # Create an Admin Task in WellSky
                            task_title = f"GIGI ALERT: {complaint.get('severity').upper()} Issue - {client_name}"
                            task_desc = f"Message: {complaint.get('message_text')}\n\nDetected in RC Chat: {complaint.get('chat_name')}\nKeywords: {', '.join(complaint.get('matched_keywords', []))}"
                            
                            wellsky_service.create_admin_task(
                                title=task_title,
                                description=task_desc,
                                priority="urgent" if complaint.get("severity") == "high" else "normal",
                                related_client_id=wellsky_client.id
                            )
                            wellsky_status = "success"
                            logger.info(f"Pushed RC complaint for {client_name} to WellSky Task")
                    except Exception as e:
                        wellsky_status = f"error: {str(e)}"
                        logger.error(f"Failed to push RC complaint to WellSky: {e}")

                created.append({
                    "client_name": new_complaint.client_name,
                    "keywords": complaint.get("matched_keywords"),
                    "severity": new_complaint.severity,
                    "wellsky_sync": wellsky_status
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

    # =========================================================================
    # Call Pattern Monitoring (works without call recordings)
    # =========================================================================

    def get_call_queues(self) -> List[Dict[str, Any]]:
        """Get list of call queues from RingCentral."""
        result = self._api_request("/account/~/call-queues")
        if result:
            queues = result.get("records", [])
            return queues
        return []

    def get_call_logs(
        self,
        days_back: int = 7,
        extension_id: str = None,
        queue_id: str = None,
        limit: int = 250
    ) -> List[Dict[str, Any]]:
        """
        Fetch call logs from RingCentral.

        Args:
            days_back: Number of days to look back
            extension_id: Filter by specific extension
            queue_id: Filter by call queue (use extension ID of queue)
            limit: Maximum records to fetch

        Returns:
            List of call log records
        """
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "dateFrom": since,
            "perPage": min(limit, 250),
            "view": "Detailed"
        }

        # Build the endpoint based on filters
        if extension_id:
            endpoint = f"/account/~/extension/{extension_id}/call-log"
        elif queue_id:
            endpoint = f"/account/~/extension/{queue_id}/call-log"
        else:
            endpoint = "/account/~/call-log"

        result = self._api_request(endpoint, params=params)
        if result:
            calls = result.get("records", [])
            logger.info(f"Fetched {len(calls)} call logs")
            return calls
        return []

    def load_client_phones(self, db_session) -> Dict[str, str]:
        """
        Load client phone numbers from database for matching.

        Returns:
            Dict mapping cleaned phone number to client name
        """
        # Try to get from contacts table first
        try:
            from sales.app import Contact
            contacts = db_session.query(Contact).filter(Contact.phone.isnot(None)).all()
            phone_map = {}
            for c in contacts:
                if c.phone:
                    # Clean phone number - keep last 10 digits
                    clean = re.sub(r'[^\d]', '', c.phone)[-10:]
                    if len(clean) >= 10:
                        phone_map[clean] = c.name
            logger.info(f"Loaded {len(phone_map)} client phone numbers from contacts")
            return phone_map
        except Exception as e:
            logger.warning(f"Could not load contacts: {e}")
            return {}

    def match_phone_to_client(
        self,
        phone_number: str,
        phone_map: Dict[str, str]
    ) -> Optional[str]:
        """Match a phone number to a client name."""
        if not phone_number:
            return None
        clean = re.sub(r'[^\d]', '', phone_number)[-10:]
        return phone_map.get(clean)

    def analyze_call_patterns(
        self,
        calls: List[Dict[str, Any]],
        phone_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Analyze call logs for concerning patterns.

        Detects:
        - Repeat callers (3+ calls in period)
        - Very short calls (<10 sec, potential hang-ups)
        - Missed/voicemail calls
        - Calls to Client Support queue

        Returns:
            Analysis results with flagged patterns
        """
        # Track patterns by phone number
        caller_stats = {}  # phone -> {calls, total_duration, short_calls, missed, etc}

        # Client Support queue extension
        CLIENT_SUPPORT_QUEUE = "6"  # From your queues list

        flagged_patterns = []

        for call in calls:
            direction = call.get("direction", "")
            from_info = call.get("from", {})
            to_info = call.get("to", {})
            result = call.get("result", "")
            duration = call.get("duration", 0)

            # Get the external phone number (caller for inbound, callee for outbound)
            if direction == "Inbound":
                external_phone = from_info.get("phoneNumber", "")
                internal_ext = to_info.get("extensionNumber", "")
            else:
                external_phone = to_info.get("phoneNumber", "")
                internal_ext = from_info.get("extensionNumber", "")

            if not external_phone:
                continue

            clean_phone = re.sub(r'[^\d]', '', external_phone)[-10:]
            if len(clean_phone) < 10:
                continue

            # Initialize stats for this caller
            if clean_phone not in caller_stats:
                caller_stats[clean_phone] = {
                    "phone": external_phone,
                    "client_name": phone_map.get(clean_phone),
                    "call_count": 0,
                    "total_duration": 0,
                    "short_calls": 0,  # < 10 seconds
                    "missed_calls": 0,
                    "voicemail": 0,
                    "to_support_queue": 0,
                    "calls": []
                }

            stats = caller_stats[clean_phone]
            stats["call_count"] += 1
            stats["total_duration"] += duration
            stats["calls"].append({
                "direction": direction,
                "duration": duration,
                "result": result,
                "time": call.get("startTime"),
                "extension": internal_ext
            })

            # Track patterns
            if duration < 10 and result == "Accepted":
                stats["short_calls"] += 1
            if result in ("Missed", "No Answer"):
                stats["missed_calls"] += 1
            if result == "Voicemail":
                stats["voicemail"] += 1
            if internal_ext == CLIENT_SUPPORT_QUEUE:
                stats["to_support_queue"] += 1

        # Flag concerning patterns
        for phone, stats in caller_stats.items():
            issues = []
            severity = "low"

            # Repeat caller (3+ calls)
            if stats["call_count"] >= 3:
                issues.append(f"Repeat caller: {stats['call_count']} calls")
                severity = "medium"

            # Multiple short calls (frustration indicator)
            if stats["short_calls"] >= 2:
                issues.append(f"Multiple short calls: {stats['short_calls']}")
                severity = "medium"

            # Multiple missed + callback attempts
            if stats["missed_calls"] >= 2:
                issues.append(f"Multiple missed calls: {stats['missed_calls']}")
                severity = "medium"

            # Called support queue multiple times
            if stats["to_support_queue"] >= 2:
                issues.append(f"Multiple calls to Client Support: {stats['to_support_queue']}")
                severity = "high"

            # High frequency + short duration (very frustrated)
            if stats["call_count"] >= 4 and stats["short_calls"] >= 2:
                severity = "high"

            if issues:
                flagged_patterns.append({
                    "phone": stats["phone"],
                    "client_name": stats["client_name"],
                    "issues": issues,
                    "severity": severity,
                    "call_count": stats["call_count"],
                    "total_duration": stats["total_duration"],
                    "short_calls": stats["short_calls"],
                    "missed_calls": stats["missed_calls"],
                    "to_support_queue": stats["to_support_queue"],
                    "recent_calls": stats["calls"][-5:]  # Last 5 calls
                })

        # Sort by severity and call count
        severity_order = {"high": 0, "medium": 1, "low": 2}
        flagged_patterns.sort(key=lambda x: (severity_order.get(x["severity"], 3), -x["call_count"]))

        return {
            "total_calls_analyzed": len(calls),
            "unique_callers": len(caller_stats),
            "flagged_patterns": flagged_patterns,
            "flagged_count": len(flagged_patterns)
        }

    def scan_calls_for_issues(
        self,
        db_session,
        days_back: int = 7,
        queue_id: str = None
    ) -> Dict[str, Any]:
        """
        Scan call logs for patterns indicating potential client issues.

        Args:
            db_session: SQLAlchemy session
            days_back: Number of days to analyze
            queue_id: Optional - filter to specific call queue

        Returns:
            Scan results with flagged patterns
        """
        # Load client phone mappings
        phone_map = self.load_client_phones(db_session)

        # Get call logs
        calls = self.get_call_logs(days_back=days_back, queue_id=queue_id)
        if not calls:
            return {
                "success": True,
                "message": "No calls found in period",
                "flagged_patterns": [],
                "total_calls": 0
            }

        # Analyze patterns
        analysis = self.analyze_call_patterns(calls, phone_map)

        return {
            "success": True,
            "days_analyzed": days_back,
            "queue_filter": queue_id,
            "total_calls": analysis["total_calls_analyzed"],
            "unique_callers": analysis["unique_callers"],
            "flagged_count": analysis["flagged_count"],
            "flagged_patterns": analysis["flagged_patterns"],
            "scanned_at": datetime.utcnow().isoformat()
        }

    def auto_create_call_complaints(
        self,
        db_session,
        scan_results: Dict[str, Any],
        auto_create: bool = False,
        min_severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Create complaint records from flagged call patterns.

        Args:
            db_session: SQLAlchemy session
            scan_results: Results from scan_calls_for_issues
            auto_create: If True, create records; if False, preview only
            min_severity: Minimum severity to create complaints for

        Returns:
            Creation results
        """
        from portal_models import ClientComplaint

        severity_levels = {"high": 3, "medium": 2, "low": 1}
        min_level = severity_levels.get(min_severity, 2)

        created = []
        skipped = []

        for pattern in scan_results.get("flagged_patterns", []):
            pattern_severity = severity_levels.get(pattern.get("severity"), 1)

            if pattern_severity < min_level:
                skipped.append({
                    "reason": f"Below minimum severity ({pattern.get('severity')})",
                    "phone": pattern.get("phone")
                })
                continue

            # Check if already tracked by phone number
            phone = pattern.get("phone", "")
            clean_phone = re.sub(r'[^\d]', '', phone)[-10:]

            existing = db_session.query(ClientComplaint).filter(
                ClientComplaint.notes.like(f'%call_pattern:{clean_phone}%'),
                ClientComplaint.complaint_date >= (datetime.utcnow().date() - timedelta(days=7))
            ).first()

            if existing:
                skipped.append({
                    "reason": "Already tracked this week",
                    "phone": phone,
                    "existing_id": existing.id
                })
                continue

            # Build description
            issues_text = "; ".join(pattern.get("issues", []))
            description = f"Call pattern alert: {issues_text}"

            if auto_create:
                new_complaint = ClientComplaint(
                    client_name=pattern.get("client_name") or f"Caller: {phone}",
                    complaint_date=datetime.utcnow().date(),
                    category="call_pattern",
                    severity=pattern.get("severity", "medium"),
                    description=description,
                    details=f"Phone: {phone}\nCalls: {pattern.get('call_count')}\n"
                            f"Short calls: {pattern.get('short_calls')}\n"
                            f"Missed: {pattern.get('missed_calls')}\n"
                            f"To Support: {pattern.get('to_support_queue')}",
                    status="review",
                    source="ringcentral",
                    reported_by="Call Pattern Monitor",
                    notes=f"call_pattern:{clean_phone}"
                )
                db_session.add(new_complaint)
                created.append({
                    "client_name": new_complaint.client_name,
                    "phone": phone,
                    "issues": pattern.get("issues"),
                    "severity": pattern.get("severity")
                })
            else:
                created.append({
                    "would_create": True,
                    "client_name": pattern.get("client_name") or f"Caller: {phone}",
                    "phone": phone,
                    "issues": pattern.get("issues"),
                    "severity": pattern.get("severity")
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
            "call_queues": [],
            "error": None
        }

        if has_credentials:
            token = self._get_access_token()
            if token:
                status["api_connected"] = True
                teams = self.list_teams()
                status["teams_available"] = [t.get("name") for t in teams[:10]]
                queues = self.get_call_queues()
                status["call_queues"] = [
                    {"id": q.get("id"), "name": q.get("name"), "ext": q.get("extensionNumber")}
                    for q in queues
                ]
            else:
                status["error"] = "Failed to authenticate with RingCentral API"
        else:
            status["error"] = "Missing RINGCENTRAL_CLIENT_SECRET or RINGCENTRAL_JWT_TOKEN"

        return status


    # =========================================================================
    # SENDING Messages to Team Chats (for Gigi notifications)
    # =========================================================================

    def send_message_to_chat(
        self,
        chat_name: str,
        message: str,
        attachments: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send a message to a team chat.

        This is used by Gigi to notify the team about:
        - Caregiver call-outs (to New Scheduler chat)
        - Client complaints (direct to Cynthia)
        - Urgent issues (to Jason)

        Args:
            chat_name: Name of the chat to send to (e.g., "New Scheduler", "Cynthia Pointe")
            message: The message text to send
            attachments: Optional list of attachment dicts

        Returns:
            Result dict with success status
        """
        # Find the target chat
        chat = self.find_chat_by_name(chat_name)
        if not chat:
            logger.error(f"Cannot send message - chat '{chat_name}' not found")
            return {
                "success": False,
                "error": f"Chat '{chat_name}' not found"
            }

        chat_id = chat.get("id")

        try:
            data = {"text": message}
            if attachments:
                data["attachments"] = attachments

            result = self._api_request(f"/glip/chats/{chat_id}/posts", method="POST", params=data)

            if result:
                logger.info(f"Message sent to chat '{chat_name}': {message[:50]}...")
                return {
                    "success": True,
                    "chat_name": chat_name,
                    "message_id": result.get("id")
                }
            else:
                return {
                    "success": False,
                    "error": "API request failed"
                }

        except Exception as e:
            logger.error(f"Error sending message to chat '{chat_name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def send_direct_message(
        self,
        person_email: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send a direct message to a specific person by email.

        Args:
            person_email: Email address of the recipient
            message: The message text

        Returns:
            Result dict with success status
        """
        try:
            # First, find or create a 1:1 chat with this person
            # RingCentral uses "conversations" for 1:1 chats
            create_result = self._api_request(
                "/glip/conversations",
                method="POST",
                params={"members": [{"email": person_email}]}
            )

            if not create_result:
                return {
                    "success": False,
                    "error": f"Could not create conversation with {person_email}"
                }

            chat_id = create_result.get("id")

            # Now send the message
            data = {"text": message}
            result = self._api_request(f"/glip/chats/{chat_id}/posts", method="POST", params=data)

            if result:
                logger.info(f"Direct message sent to {person_email}: {message[:50]}...")
                return {
                    "success": True,
                    "recipient": person_email,
                    "message_id": result.get("id")
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send message"
                }

        except Exception as e:
            logger.error(f"Error sending direct message to {person_email}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def notify_scheduler_chat(self, message: str) -> Dict[str, Any]:
        """
        Send a notification to the New Scheduling chat.
        Used by Gigi for shift-related notifications.
        """
        return self.send_message_to_chat("New Scheduling", message)

    def notify_cynthia(self, message: str) -> Dict[str, Any]:
        """
        Send a notification directly to Cynthia Pointe.
        Used by Gigi for client escalations and urgent issues.
        """
        # Try direct message first, fall back to chat
        result = self.send_direct_message("cynthia@coloradocareassist.com", message)
        if not result.get("success"):
            # Fall back to finding her in a chat
            return self.send_message_to_chat("Cynthia", message)
        return result

    def notify_jason(self, message: str) -> Dict[str, Any]:
        """
        Send a notification directly to Jason.
        Used by Gigi for critical issues.
        """
        return self.send_direct_message("jason@coloradocareassist.com", message)

    def notify_israt(self, message: str) -> Dict[str, Any]:
        """
        Send a notification directly to Israt (scheduler).
        Used by Gigi for scheduling issues.
        """
        return self.send_direct_message("israt@coloradocareassist.com", message)

    def reply_to_sender(self, sender_info: Dict, message: str) -> Dict[str, Any]:
        """
        Reply to a message sender using whatever identifier is available.

        Args:
            sender_info: Dict with any of: email, extensionId, id, personId
            message: The reply message

        Returns:
            Result dict with success status
        """
        try:
            # Try email first (most reliable)
            if sender_info.get("email"):
                return self.send_direct_message(sender_info["email"], message)

            # Try extension number to find email
            extension_id = sender_info.get("extensionId") or sender_info.get("id")
            if extension_id:
                # Look up extension to get email
                ext_info = self._api_request(f"/account/~/extension/{extension_id}")
                if ext_info:
                    email = ext_info.get("contact", {}).get("email")
                    if email:
                        return self.send_direct_message(email, message)
                    # If no email, try the extension's name
                    name = ext_info.get("name")
                    logger.info(f"No email for extension {extension_id}, name: {name}")

            # Fallback: post to New Scheduling with attribution
            sender_name = sender_info.get("name", "Unknown")
            return self.send_message_to_chat(
                "New Scheduling",
                f"[Reply to {sender_name}]: {message}"
            )

        except Exception as e:
            logger.error(f"Error replying to sender: {e}")
            return {"success": False, "error": str(e)}


    def sync_tasks_to_wellsky(
        self,
        db_session,
        chat_name: str,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Scan a team chat for task completions (Laundry, Cleaning, etc.) 
        and log them as notes directly into the WellSky client file.
        """
        from services.wellsky_service import wellsky_service
        
        if not wellsky_service or not wellsky_service.is_configured:
            return {"success": False, "error": "WellSky not configured"}

        # Find the target chat
        chat = self.find_chat_by_name(chat_name)
        if not chat:
            return {"success": False, "error": f"Chat '{chat_name}' not found"}

        # Load client names for matching
        client_names = self.load_client_names(db_session)
        
        # Get messages
        since = datetime.utcnow() - timedelta(hours=hours_back)
        messages = self.get_chat_messages(chat["id"], since=since)
        
        synced_count = 0
        task_keywords = [
            "laundry", "cleaned", "bath", "shower", "meal", "fed", "meds", "medication", 
            "shopped", "errand", "cover", "cancel", "assessment", "clock", "visit", "appointment"
        ]

        for msg in messages:
            text = msg.get("text", "")
            if not text:
                continue

            # 1. Identify Client (Simple heuristic for common formats)
            mentions = self.find_client_mentions(text, client_names)
            
            # 1b. Fallback: Check for common names manually if list is empty
            if not mentions:
                # Look for capitalized words that might be names near task keywords
                name_match = re.search(r'for\s+([A-Z][a-z]+)', text)
                if name_match:
                    possible_name = name_match.group(1)
                    # We'll try to resolve this via WellSky later
                    client_name = possible_name
                else:
                    continue
            else:
                client_name = mentions[0][0]

            # 2. Check for Task Keywords
            if any(kw in text.lower() for kw in task_keywords):
                try:
                    # 3. Find WellSky ID
                    # Use the last part of the name for broader search
                    search_term = client_name.split()[-1]
                    ws_clients = wellsky_service.search_patients(last_name=search_term)
                    
                    target_client = None
                    if ws_clients:
                        # Try to find exact or contains match
                        for c in ws_clients:
                            if client_name.lower() in c.full_name.lower() or c.full_name.lower() in client_name.lower():
                                target_client = c
                                break
                        if not target_client:
                            target_client = ws_clients[0] # Fallback to first search result
                    
                    if target_client:
                        # 4. Log the Note in WellSky
                        timestamp = msg.get("creationTime", "")
                        note_text = f"RC DOCUMENTATION SYNC ({timestamp}): {text}"
                        
                        # Use add_note_to_client (the one on line 3765)
                        wellsky_service.add_note_to_client(
                            client_id=target_client.id,
                            note=note_text,
                            note_type="care_plan",
                            source="gigi_ai"
                        )
                        synced_count += 1
                        logger.info(f"Synced task for {target_client.full_name} from RC to WellSky")
                except Exception as e:
                    logger.error(f"Error syncing RC task to WellSky: {e}")

        return {
            "success": True,
            "chat_name": chat_name,
            "tasks_synced": synced_count,
            "messages_scanned": len(messages)
        }

# Singleton instance
ringcentral_messaging_service = RingCentralMessagingService()
