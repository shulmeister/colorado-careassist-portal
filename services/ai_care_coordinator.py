"""
AI Care Coordinator Service

Autonomous 24/7 care coordination engine inspired by Gigi Operator and Gigi.work.

This service provides:
- Real-time monitoring of WellSky operational data
- AI-powered satisfaction risk detection
- Automated SMS/voice outreach via RingCentral
- Intelligent escalation to human coordinators
- Proactive family engagement campaigns
- Audit trail and compliance documentation

The coordinator operates as a "first line of defense" - handling routine tasks
autonomously while escalating complex issues to human staff.
"""
from __future__ import annotations

import os
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# AI Coordinator settings
AI_COORDINATOR_ENABLED = os.getenv("AI_COORDINATOR_ENABLED", "false").lower() == "true"
BUSINESS_HOURS_START = int(os.getenv("BUSINESS_HOURS_START", "8"))  # 8 AM
BUSINESS_HOURS_END = int(os.getenv("BUSINESS_HOURS_END", "18"))  # 6 PM
ESCALATION_PHONE = os.getenv("ESCALATION_PHONE", "")
ESCALATION_EMAIL = os.getenv("ESCALATION_EMAIL", "")

# Risk thresholds
HIGH_RISK_THRESHOLD = int(os.getenv("HIGH_RISK_THRESHOLD", "60"))
MEDIUM_RISK_THRESHOLD = int(os.getenv("MEDIUM_RISK_THRESHOLD", "40"))
ENGAGEMENT_LOW_THRESHOLD = float(os.getenv("ENGAGEMENT_LOW_THRESHOLD", "30"))

# Import dependencies
try:
    from services.wellsky_service import wellsky_service
except ImportError:
    wellsky_service = None
    logger.warning("WellSky service not available for AI coordinator")

try:
    from services.ringcentral_messaging_service import ringcentral_service
except ImportError:
    ringcentral_service = None
    logger.warning("RingCentral service not available for AI coordinator")


# =============================================================================
# Data Models
# =============================================================================

class AlertPriority(Enum):
    """Alert priority levels"""
    CRITICAL = "critical"  # Requires immediate human attention
    HIGH = "high"          # Needs attention within hours
    MEDIUM = "medium"      # Should be addressed today
    LOW = "low"            # Can wait for regular review


class AlertType(Enum):
    """Types of satisfaction alerts"""
    HIGH_RISK_CLIENT = "high_risk_client"
    LOW_ENGAGEMENT = "low_engagement"
    CARE_PLAN_OVERDUE = "care_plan_overdue"
    MISSED_VISIT = "missed_visit"
    COMPLAINT_RECEIVED = "complaint_received"
    CAREGIVER_ISSUE = "caregiver_issue"
    HOURS_DECLINING = "hours_declining"
    SURVEY_DUE = "survey_due"
    ANNIVERSARY = "anniversary"
    FAMILY_MESSAGE = "family_message"


class OutreachChannel(Enum):
    """Communication channels for outreach"""
    SMS = "sms"
    VOICE = "voice"
    EMAIL = "email"
    PORTAL = "portal"


class OutreachStatus(Enum):
    """Status of outreach attempts"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    RESPONDED = "responded"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class SatisfactionAlert:
    """A satisfaction-related alert requiring attention"""
    id: str
    type: AlertType
    priority: AlertPriority
    client_id: str
    client_name: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    risk_score: int = 0
    risk_factors: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: str = ""
    resolution_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['type'] = self.type.value
        d['priority'] = self.priority.value
        d['created_at'] = self.created_at.isoformat()
        d['acknowledged_at'] = self.acknowledged_at.isoformat() if self.acknowledged_at else None
        d['resolved_at'] = self.resolved_at.isoformat() if self.resolved_at else None
        return d


@dataclass
class OutreachTask:
    """A proactive outreach task"""
    id: str
    type: str  # engagement_check, survey_request, anniversary, etc.
    client_id: str
    client_name: str
    contact_phone: str = ""
    contact_email: str = ""
    channel: OutreachChannel = OutreachChannel.SMS
    status: OutreachStatus = OutreachStatus.PENDING
    message_template: str = ""
    personalized_message: str = ""
    reason: str = ""
    suggested_action: str = ""
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    response_received: Optional[str] = None
    response_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['channel'] = self.channel.value
        d['status'] = self.status.value
        d['scheduled_at'] = self.scheduled_at.isoformat() if self.scheduled_at else None
        d['sent_at'] = self.sent_at.isoformat() if self.sent_at else None
        d['response_at'] = self.response_at.isoformat() if self.response_at else None
        d['created_at'] = self.created_at.isoformat()
        return d


@dataclass
class CoordinatorAction:
    """Record of an action taken by the AI coordinator"""
    id: str
    action_type: str  # alert_created, outreach_sent, escalation, etc.
    description: str
    client_id: Optional[str] = None
    alert_id: Optional[str] = None
    outreach_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    automated: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        return d


# =============================================================================
# Message Templates
# =============================================================================

OUTREACH_TEMPLATES = {
    "engagement_check": {
        "sms": """Hi {family_name}! This is Colorado Care Assist checking in about {client_first_name}'s care.

We noticed you haven't logged into the Family Portal recently. We're here to help!

Reply YES if everything is going well, or CALL to request a callback.""",

        "voice": """Hello, this is Colorado Care Assist calling to check in about {client_first_name}'s care.
We want to make sure everything is going well and you have everything you need.
Press 1 if everything is good, Press 2 to request a callback from our care team,
or Press 3 to speak with someone now.""",
    },

    "survey_request": {
        "sms": """Hi {family_name}! We'd love your feedback on {client_first_name}'s care.

Your input helps us improve! Please take our quick 2-minute survey: {survey_link}

Thank you! 🙏""",
    },

    "anniversary": {
        "sms": """🎉 Happy {milestone} Anniversary!

We're honored to have been caring for {client_first_name} for {milestone}. Thank you for trusting Colorado Care Assist!

Would you be willing to share your experience? Reply YES and we'll send a quick link.""",
    },

    "care_plan_reminder": {
        "sms": """Hi {family_name}, this is Colorado Care Assist.

{client_first_name}'s care plan is due for review. We'd like to schedule a quick call to ensure their care is meeting their needs.

Reply with a good time to call, or call us at {office_phone}.""",
    },

    "satisfaction_followup": {
        "sms": """Hi {family_name}, thank you for your recent feedback about {client_first_name}'s care.

We take your input seriously and want to address any concerns. A care coordinator will reach out within 24 hours.

Questions? Call {office_phone}.""",
    },

    "after_hours_response": {
        "sms": """Thank you for contacting Colorado Care Assist. Our office is currently closed.

If this is a care EMERGENCY, please call {emergency_phone}.

For non-urgent matters, a coordinator will respond first thing tomorrow morning.

Your message has been logged and will be reviewed.""",
    },
}


# =============================================================================
# AI Care Coordinator Service
# =============================================================================

class AICareCoordinator:
    """
    AI-powered care coordination engine.

    Monitors client satisfaction indicators and takes autonomous action:
    - Generates alerts for at-risk clients
    - Sends proactive outreach messages
    - Handles after-hours communication
    - Escalates critical issues to human staff
    - Maintains audit trail for compliance
    """

    def __init__(self):
        self.wellsky = wellsky_service
        self.ringcentral = ringcentral_service
        self.enabled = AI_COORDINATOR_ENABLED

        # In-memory storage (would be database in production)
        self._alerts: Dict[str, SatisfactionAlert] = {}
        self._outreach_tasks: Dict[str, OutreachTask] = {}
        self._action_log: List[CoordinatorAction] = []

        # Callbacks for external integrations
        self._on_alert_created: Optional[Callable] = None
        self._on_escalation: Optional[Callable] = None

        logger.info(f"AI Care Coordinator initialized (enabled: {self.enabled})")

    @property
    def is_enabled(self) -> bool:
        """Check if coordinator is enabled"""
        return self.enabled

    @property
    def wellsky_available(self) -> bool:
        """Check if WellSky service is available"""
        return self.wellsky is not None

    @property
    def ringcentral_available(self) -> bool:
        """Check if RingCentral service is available"""
        return self.ringcentral is not None

    def is_business_hours(self) -> bool:
        """Check if currently within business hours"""
        now = datetime.now()
        return BUSINESS_HOURS_START <= now.hour < BUSINESS_HOURS_END and now.weekday() < 5

    # =========================================================================
    # Alert Management
    # =========================================================================

    def generate_alerts(self) -> List[SatisfactionAlert]:
        """
        Scan WellSky data and generate satisfaction alerts.

        This is the core monitoring function - call periodically to
        identify issues requiring attention.
        """
        if not self.wellsky_available:
            logger.warning("Cannot generate alerts - WellSky not available")
            return []

        alerts = []
        now = datetime.utcnow()

        try:
            # Get at-risk clients
            at_risk = self.wellsky.get_at_risk_clients(threshold=MEDIUM_RISK_THRESHOLD)

            for client_data in at_risk:
                client_id = client_data.get("client_id")

                # Skip if we already have an active alert for this client
                existing = self._get_active_alert_for_client(client_id)
                if existing:
                    continue

                risk_score = client_data.get("risk_score", 0)
                risk_level = client_data.get("risk_level", "medium")

                priority = AlertPriority.HIGH if risk_level == "high" else AlertPriority.MEDIUM

                alert = SatisfactionAlert(
                    id=f"alert_{client_id}_{now.strftime('%Y%m%d%H%M%S')}",
                    type=AlertType.HIGH_RISK_CLIENT,
                    priority=priority,
                    client_id=client_id,
                    client_name=client_data.get("client_name", "Unknown"),
                    message=f"Client has satisfaction risk score of {risk_score}",
                    risk_score=risk_score,
                    risk_factors=client_data.get("risk_factors", []),
                    recommended_actions=client_data.get("recommendations", []),
                    details=client_data.get("metrics", {}),
                )

                self._alerts[alert.id] = alert
                alerts.append(alert)

                self._log_action(
                    action_type="alert_created",
                    description=f"Created {priority.value} risk alert for {alert.client_name}",
                    client_id=client_id,
                    alert_id=alert.id,
                    data={"risk_score": risk_score, "risk_factors": alert.risk_factors}
                )

            # Get low engagement families
            low_engagement = self.wellsky.get_low_engagement_clients(threshold=ENGAGEMENT_LOW_THRESHOLD)

            for client, activity in low_engagement:
                client_id = client.id

                # Skip if we already have an alert
                existing = self._get_active_alert_for_client(client_id, AlertType.LOW_ENGAGEMENT)
                if existing:
                    continue

                alert = SatisfactionAlert(
                    id=f"alert_engagement_{client_id}_{now.strftime('%Y%m%d%H%M%S')}",
                    type=AlertType.LOW_ENGAGEMENT,
                    priority=AlertPriority.MEDIUM,
                    client_id=client_id,
                    client_name=client.full_name,
                    message=f"No family portal activity in {(now - activity.last_login).days if activity.last_login else 999} days",
                    details={
                        "engagement_score": activity.engagement_score,
                        "last_login": activity.last_login.isoformat() if activity.last_login else None,
                        "login_count_30d": activity.login_count_30d,
                    },
                    recommended_actions=["Proactive phone check-in", "Send portal reminder email"],
                )

                self._alerts[alert.id] = alert
                alerts.append(alert)

            # Get care plans due for review
            care_plans_due = self.wellsky.get_care_plans_due_for_review(days_ahead=7)

            for cp in care_plans_due:
                client = self.wellsky.get_client(cp.client_id)
                if not client:
                    continue

                # Skip if we already have an alert
                existing = self._get_active_alert_for_client(cp.client_id, AlertType.CARE_PLAN_OVERDUE)
                if existing:
                    continue

                is_overdue = cp.days_until_review <= 0
                priority = AlertPriority.HIGH if is_overdue else AlertPriority.MEDIUM

                alert = SatisfactionAlert(
                    id=f"alert_careplan_{cp.client_id}_{now.strftime('%Y%m%d%H%M%S')}",
                    type=AlertType.CARE_PLAN_OVERDUE,
                    priority=priority,
                    client_id=cp.client_id,
                    client_name=client.full_name,
                    message=f"Care plan review {'overdue' if is_overdue else f'due in {cp.days_until_review} days'}",
                    details={
                        "review_date": cp.review_date.isoformat() if cp.review_date else None,
                        "days_until_review": cp.days_until_review,
                    },
                    recommended_actions=["Schedule care plan review meeting", "Contact family to discuss care needs"],
                )

                self._alerts[alert.id] = alert
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error generating alerts: {e}")

        logger.info(f"Generated {len(alerts)} new satisfaction alerts")
        return alerts

    def _get_active_alert_for_client(
        self,
        client_id: str,
        alert_type: AlertType = None
    ) -> Optional[SatisfactionAlert]:
        """Check if there's already an active (unresolved) alert for this client"""
        for alert in self._alerts.values():
            if alert.client_id == client_id and alert.resolved_at is None:
                if alert_type is None or alert.type == alert_type:
                    return alert
        return None

    def get_active_alerts(self, priority: AlertPriority = None) -> List[SatisfactionAlert]:
        """Get all active (unresolved) alerts"""
        alerts = [a for a in self._alerts.values() if a.resolved_at is None]

        if priority:
            alerts = [a for a in alerts if a.priority == priority]

        # Sort by priority (critical first) then by created time
        priority_order = {
            AlertPriority.CRITICAL: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
        }
        alerts.sort(key=lambda a: (priority_order.get(a.priority, 4), a.created_at))

        return alerts

    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        """Acknowledge an alert (mark as seen)"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.acknowledged_at = datetime.utcnow()
        self._log_action(
            action_type="alert_acknowledged",
            description=f"Alert acknowledged by {user}",
            alert_id=alert_id,
            data={"acknowledged_by": user}
        )
        return True

    def resolve_alert(self, alert_id: str, user: str, notes: str = "") -> bool:
        """Resolve an alert"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user
        alert.resolution_notes = notes

        self._log_action(
            action_type="alert_resolved",
            description=f"Alert resolved by {user}: {notes}",
            alert_id=alert_id,
            client_id=alert.client_id,
            data={"resolved_by": user, "notes": notes}
        )
        return True

    # =========================================================================
    # Outreach Management
    # =========================================================================

    def create_outreach_task(
        self,
        task_type: str,
        client_id: str,
        client_name: str,
        contact_phone: str = "",
        contact_email: str = "",
        channel: OutreachChannel = OutreachChannel.SMS,
        reason: str = "",
        suggested_action: str = "",
        schedule_at: datetime = None,
    ) -> OutreachTask:
        """Create a new outreach task"""
        now = datetime.utcnow()
        task_id = f"outreach_{client_id}_{now.strftime('%Y%m%d%H%M%S')}"

        task = OutreachTask(
            id=task_id,
            type=task_type,
            client_id=client_id,
            client_name=client_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
            channel=channel,
            reason=reason,
            suggested_action=suggested_action,
            scheduled_at=schedule_at or now,
        )

        # Get message template
        template_key = task_type
        templates = OUTREACH_TEMPLATES.get(template_key, {})
        task.message_template = templates.get(channel.value, "")

        self._outreach_tasks[task_id] = task

        self._log_action(
            action_type="outreach_created",
            description=f"Created {task_type} outreach for {client_name}",
            client_id=client_id,
            outreach_id=task_id,
            data={"type": task_type, "channel": channel.value, "reason": reason}
        )

        return task

    def generate_outreach_queue(self) -> List[OutreachTask]:
        """
        Generate outreach tasks based on current client satisfaction data.

        Creates tasks for:
        - Low engagement families
        - Upcoming anniversaries
        - Survey-due clients
        """
        if not self.wellsky_available:
            logger.warning("Cannot generate outreach queue - WellSky not available")
            return []

        tasks = []

        try:
            # Low engagement families
            low_engagement = self.wellsky.get_low_engagement_clients(threshold=ENGAGEMENT_LOW_THRESHOLD)

            for client, activity in low_engagement[:10]:  # Limit to 10
                # Skip if we already have a pending outreach for this client
                existing = self._get_pending_outreach_for_client(client.id, "engagement_check")
                if existing:
                    continue

                task = self.create_outreach_task(
                    task_type="engagement_check",
                    client_id=client.id,
                    client_name=client.full_name,
                    contact_phone=client.phone,
                    channel=OutreachChannel.SMS,
                    reason=f"No portal activity in {(datetime.utcnow() - activity.last_login).days if activity.last_login else 'many'} days",
                    suggested_action="Check in on care satisfaction",
                )
                tasks.append(task)

            # Upcoming anniversaries (from client satisfaction service)
            # This would integrate with the client_satisfaction_service
            # For now, we'll use WellSky client data directly

            clients = self.wellsky.get_clients()
            active_clients = [c for c in clients if c.is_active and c.start_date]

            today = date.today()

            for client in active_clients:
                # Check for milestone anniversaries
                months = client.tenure_days // 30
                next_milestone = ((months // 6) + 1) * 6

                milestone_date = client.start_date + timedelta(days=next_milestone * 30)
                days_until = (milestone_date - today).days

                if 7 <= days_until <= 14:  # 1-2 weeks before milestone
                    existing = self._get_pending_outreach_for_client(client.id, "anniversary")
                    if existing:
                        continue

                    milestone_str = f"{next_milestone} months" if next_milestone < 12 else f"{next_milestone // 12} year"

                    task = self.create_outreach_task(
                        task_type="anniversary",
                        client_id=client.id,
                        client_name=client.full_name,
                        contact_phone=client.phone,
                        channel=OutreachChannel.SMS,
                        reason=f"{milestone_str} service anniversary",
                        suggested_action="Send appreciation message and request testimonial",
                    )
                    tasks.append(task)

        except Exception as e:
            logger.error(f"Error generating outreach queue: {e}")

        logger.info(f"Generated {len(tasks)} outreach tasks")
        return tasks

    def _get_pending_outreach_for_client(self, client_id: str, task_type: str = None) -> Optional[OutreachTask]:
        """Check if there's already a pending outreach for this client"""
        for task in self._outreach_tasks.values():
            if task.client_id == client_id and task.status == OutreachStatus.PENDING:
                if task_type is None or task.type == task_type:
                    return task
        return None

    def get_pending_outreach(self) -> List[OutreachTask]:
        """Get all pending outreach tasks"""
        tasks = [t for t in self._outreach_tasks.values() if t.status == OutreachStatus.PENDING]
        tasks.sort(key=lambda t: t.scheduled_at or t.created_at)
        return tasks

    async def execute_outreach(self, task_id: str, personalized_vars: Dict[str, str] = None) -> bool:
        """
        Execute an outreach task (send SMS or initiate voice call).

        Args:
            task_id: ID of the outreach task
            personalized_vars: Variables to substitute in message template

        Returns:
            True if outreach was sent successfully
        """
        task = self._outreach_tasks.get(task_id)
        if not task:
            logger.error(f"Outreach task not found: {task_id}")
            return False

        if task.status != OutreachStatus.PENDING:
            logger.warning(f"Outreach task {task_id} is not pending (status: {task.status})")
            return False

        if not self.ringcentral_available:
            logger.error("RingCentral not available - cannot execute outreach")
            task.status = OutreachStatus.FAILED
            return False

        # Personalize message
        vars_dict = personalized_vars or {}
        vars_dict.setdefault("client_first_name", task.client_name.split()[0] if task.client_name else "")
        vars_dict.setdefault("family_name", task.client_name)
        vars_dict.setdefault("office_phone", os.getenv("OFFICE_PHONE", "303-555-0100"))
        vars_dict.setdefault("emergency_phone", os.getenv("EMERGENCY_PHONE", "303-555-0199"))

        message = task.message_template
        for key, value in vars_dict.items():
            message = message.replace(f"{{{key}}}", str(value))

        task.personalized_message = message
        task.attempts += 1

        try:
            if task.channel == OutreachChannel.SMS:
                # Send SMS via RingCentral
                result = await self.ringcentral.send_sms(
                    to_phone=task.contact_phone,
                    message=message
                )
                if result.get("success"):
                    task.status = OutreachStatus.SENT
                    task.sent_at = datetime.utcnow()
                    logger.info(f"Sent SMS outreach to {task.client_name}")
                else:
                    raise Exception(result.get("error", "SMS send failed"))

            elif task.channel == OutreachChannel.VOICE:
                # Initiate voice call via RingCentral
                result = await self.ringcentral.initiate_call(
                    to_phone=task.contact_phone,
                    script=message
                )
                if result.get("success"):
                    task.status = OutreachStatus.SENT
                    task.sent_at = datetime.utcnow()
                    logger.info(f"Initiated voice call to {task.client_name}")
                else:
                    raise Exception(result.get("error", "Voice call failed"))

            self._log_action(
                action_type="outreach_sent",
                description=f"Sent {task.channel.value} outreach to {task.client_name}",
                client_id=task.client_id,
                outreach_id=task_id,
                data={"channel": task.channel.value, "attempt": task.attempts}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to execute outreach {task_id}: {e}")

            if task.attempts >= task.max_attempts:
                task.status = OutreachStatus.FAILED
                self._escalate(
                    reason=f"Outreach failed after {task.attempts} attempts",
                    client_id=task.client_id,
                    details={"task_id": task_id, "error": str(e)}
                )
            else:
                # Keep as pending for retry
                task.status = OutreachStatus.PENDING

            return False

    def record_response(self, task_id: str, response: str) -> bool:
        """Record a response to an outreach task"""
        task = self._outreach_tasks.get(task_id)
        if not task:
            return False

        task.response_received = response
        task.response_at = datetime.utcnow()
        task.status = OutreachStatus.RESPONDED

        self._log_action(
            action_type="outreach_response",
            description=f"Received response from {task.client_name}: {response[:50]}...",
            client_id=task.client_id,
            outreach_id=task_id,
            data={"response": response}
        )

        return True

    # =========================================================================
    # Escalation
    # =========================================================================

    def _escalate(self, reason: str, client_id: str = None, details: Dict = None):
        """Escalate an issue to human coordinators"""
        logger.warning(f"ESCALATION: {reason}")

        self._log_action(
            action_type="escalation",
            description=f"Escalated to human coordinator: {reason}",
            client_id=client_id,
            data=details or {}
        )

        # If callback is registered, call it
        if self._on_escalation:
            try:
                self._on_escalation(reason, client_id, details)
            except Exception as e:
                logger.error(f"Escalation callback failed: {e}")

        # TODO: Send escalation notification via RingCentral/email
        # This would integrate with the existing notification systems

    # =========================================================================
    # After-Hours Handling
    # =========================================================================

    def handle_after_hours_message(self, from_phone: str, message: str) -> str:
        """
        Handle incoming message outside business hours.

        Provides automatic acknowledgment and triages for urgency.

        Args:
            from_phone: Sender's phone number
            message: Message content

        Returns:
            Auto-response message
        """
        # Check for urgent keywords
        urgent_keywords = ["emergency", "urgent", "911", "fall", "hospital", "immediate"]
        is_urgent = any(kw in message.lower() for kw in urgent_keywords)

        self._log_action(
            action_type="after_hours_message",
            description=f"Received after-hours message from {from_phone}",
            data={
                "from_phone": from_phone,
                "message_preview": message[:100],
                "is_urgent": is_urgent,
            }
        )

        if is_urgent:
            # Escalate immediately
            self._escalate(
                reason=f"Urgent after-hours message from {from_phone}",
                details={"message": message, "from_phone": from_phone}
            )
            return f"""This message appears to be URGENT.

If this is a medical emergency, please call 911 immediately.

An on-call coordinator has been notified and will contact you as soon as possible.

If you need immediate assistance, call our emergency line: {os.getenv('EMERGENCY_PHONE', '303-555-0199')}"""

        # Standard after-hours response
        response = OUTREACH_TEMPLATES["after_hours_response"]["sms"]
        response = response.replace("{emergency_phone}", os.getenv('EMERGENCY_PHONE', '303-555-0199'))

        return response

    # =========================================================================
    # Logging & Audit
    # =========================================================================

    def _log_action(
        self,
        action_type: str,
        description: str,
        client_id: str = None,
        alert_id: str = None,
        outreach_id: str = None,
        data: Dict = None
    ):
        """Log a coordinator action for audit trail"""
        action = CoordinatorAction(
            id=f"action_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            action_type=action_type,
            description=description,
            client_id=client_id,
            alert_id=alert_id,
            outreach_id=outreach_id,
            data=data or {},
        )

        self._action_log.append(action)

        # Keep log size manageable (in production, would persist to database)
        if len(self._action_log) > 1000:
            self._action_log = self._action_log[-500:]

        logger.info(f"[AI Coordinator] {action_type}: {description}")

    def get_action_log(self, limit: int = 100, client_id: str = None) -> List[Dict]:
        """Get recent action log entries"""
        actions = self._action_log

        if client_id:
            actions = [a for a in actions if a.client_id == client_id]

        # Sort by created_at descending (most recent first)
        actions = sorted(actions, key=lambda a: a.created_at, reverse=True)

        return [a.to_dict() for a in actions[:limit]]

    # =========================================================================
    # Dashboard / Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status summary"""
        active_alerts = self.get_active_alerts()
        pending_outreach = self.get_pending_outreach()

        return {
            "enabled": self.enabled,
            "wellsky_connected": self.wellsky_available,
            "wellsky_mode": "mock" if self.wellsky_available and self.wellsky.is_mock_mode else "live" if self.wellsky_available else "disconnected",
            "ringcentral_connected": self.ringcentral_available,
            "is_business_hours": self.is_business_hours(),
            "alerts": {
                "total_active": len(active_alerts),
                "critical": len([a for a in active_alerts if a.priority == AlertPriority.CRITICAL]),
                "high": len([a for a in active_alerts if a.priority == AlertPriority.HIGH]),
                "medium": len([a for a in active_alerts if a.priority == AlertPriority.MEDIUM]),
            },
            "outreach": {
                "pending": len(pending_outreach),
                "total_logged": len(self._outreach_tasks),
            },
            "action_log_size": len(self._action_log),
            "last_scan": self._action_log[-1].created_at.isoformat() if self._action_log else None,
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data for UI"""
        return {
            "status": self.get_status(),
            "alerts": [a.to_dict() for a in self.get_active_alerts()[:20]],
            "outreach_queue": [t.to_dict() for t in self.get_pending_outreach()[:20]],
            "recent_actions": self.get_action_log(limit=20),
            "generated_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

ai_care_coordinator = AICareCoordinator()
