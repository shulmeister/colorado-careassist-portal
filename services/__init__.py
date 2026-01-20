# Service layer package
"""
Colorado Care Assist - Services Layer

Core services for portal operations:
- WellSky API integration (operational data)
- Client satisfaction tracking
- AI Care Coordinator (Zingage/Phoebe-style automation)
- RingCentral messaging
- OAuth management
"""

# WellSky integration
from services.wellsky_service import wellsky_service

# Client satisfaction tracking
from services.client_satisfaction_service import client_satisfaction_service

# AI Care Coordinator (autonomous monitoring)
from services.ai_care_coordinator import ai_care_coordinator

__all__ = [
    "wellsky_service",
    "client_satisfaction_service",
    "ai_care_coordinator",
]
