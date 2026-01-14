"""
AI-Powered Shift Filling Engine for Colorado Care Assist

This module provides automated shift filling capabilities:
- Detects call-offs from incoming SMS/calls
- Matches qualified caregivers to open shifts
- Sends parallel SMS outreach via RingCentral
- Handles responses and assigns shifts
- Integrates with WellSky for schedule updates
"""

from .engine import ShiftFillingEngine, shift_filling_engine
from .matcher import CaregiverMatcher
from .models import Shift, Caregiver, Client, ShiftOutreach, CaregiverOutreach, OutreachStatus
from .sms_service import SMSService, sms_service
from .wellsky_mock import wellsky_mock

__all__ = [
    'ShiftFillingEngine',
    'shift_filling_engine',
    'CaregiverMatcher',
    'Shift',
    'Caregiver',
    'Client',
    'ShiftOutreach',
    'CaregiverOutreach',
    'OutreachStatus',
    'SMSService',
    'sms_service',
    'wellsky_mock'
]
