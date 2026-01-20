# Service layer package
"""
Colorado Care Assist - Services Layer

Core services for portal operations:
- WellSky API integration (operational data)
- Client satisfaction tracking
- AI Care Coordinator (Zingage/Phoebe-style automation)
- Hub-and-spoke integrations:
  - Sales Dashboard → WellSky Prospects
  - Recruiting Dashboard → WellSky Applicants
  - GoFormz → WellSky status triggers (paperwork completion)
- RingCentral messaging
- OAuth management
"""

# WellSky integration
from services.wellsky_service import wellsky_service

# Client satisfaction tracking
from services.client_satisfaction_service import client_satisfaction_service

# AI Care Coordinator (autonomous monitoring)
from services.ai_care_coordinator import ai_care_coordinator

# Hub-and-spoke sync services
from services.sales_wellsky_sync import sales_wellsky_sync
from services.recruiting_wellsky_sync import recruiting_wellsky_sync
from services.goformz_wellsky_sync import goformz_wellsky_sync

__all__ = [
    "wellsky_service",
    "client_satisfaction_service",
    "ai_care_coordinator",
    "sales_wellsky_sync",
    "recruiting_wellsky_sync",
    "goformz_wellsky_sync",
]
