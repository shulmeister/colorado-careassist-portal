"""
Utility script to capture the December 2025 incoming lead batch that
was provided out-of-band (portal downtime).

Run this against the production database (or any target DATABASE_URL)
to seed the three incoming leads plus their follow-up tasks.

Usage:
    export DATABASE_URL=postgresql://...
    python add_december_2025_leads.py

The script is idempotent: it updates existing leads with matching names
and only creates missing tasks.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func  # type: ignore

from database import db_manager
from models import (
    Contact,
    Lead,
    LeadActivity,
    LeadTask,
    PipelineStage,
    ReferralSource,
    Deal,
)

SYSTEM_USER_EMAIL = "portal-batch-import@coloradocareassist.com"
DEFAULT_STAGE_NAME = "Incoming Leads"


def _notes(*lines: str) -> str:
    """Join note fragments with line breaks for readability."""
    return "\n".join(line.strip() for line in lines if line and line.strip())


LEAD_BATCH: List[Dict[str, Any]] = [
    {
        "name": "Gail Redfox",
        "contact_name": "Gail Redfox",
        "email": "gailredfox@yahoo.com",
        "phone": "701-620-1769",
        "source": "Web",
        "payor_source": "Unknown",
        "priority": "high",
        "city": "Denver, CO",
        "address": "South Stewart Street, Denver, CO",
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Sister of Juanita Redleaf. Juanita's husband Dale (77-78) has mesothelioma and needs care guidance.",
            "Not eating and family hoped he could receive IV support. Older daughter is present with Gail.",
            "Family has insurance funds available but payor is still unknown.",
            "Needs immediate confirmation on assessment date/time.",
            "11/18 - Phone rang out, sent follow-up email. Waiting for reply.",
        ),
        "tasks": [
            {
                "title": "Confirm assessment date/time (Gail Redfox)",
                "description": "Coordinate with Gail and Juanita to lock in the assessment for Dale Redleaf.",
            }
        ],
    },
    {
        "name": "Carin Craft",
        "contact_name": "Carin Craft",
        "email": "craftcarin@gmail.com",
        "phone": "720-461-8145",
        "source": "Google",
        "payor_source": "Unknown",
        "priority": "high",
        "city": "Aurora / Stapleton (moving to Denver)",
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Primary caregiver is her niece Tania Johnson (720-993-6151 / nia2104johnson@gmail.com).",
            "Client relocating from Aurora to Denver/Stapleton area and will need 6 hours per day.",
            "Tania wants a 9am-3pm schedule with her aunt, currently works as an independent caregiver and asked about doing both.",
            "Waiting on Sierra approval. Need to confirm assessment date/time once payor status is clear.",
        ),
        "tasks": [
            {
                "title": "Confirm assessment availability (Carin Craft)",
                "description": "Loop in Tania Johnson once Sierra approval lands and lock assessment time.",
            }
        ],
    },
    {
        "name": "Maryanne Tyler",
        "contact_name": "Maryanne Tyler",
        "email": None,
        "phone": "719-246-0922",
        "source": "Employment",
        "payor_source": "Medicaid (Dual Complete)",
        "priority": "medium",
        "city": "Colorado Springs, CO",
        "address": "232 N 14th St, Colorado Springs, CO 80904",
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Has Medicaid Duo Complete plan. Girlfriend provides daily 3-hour care and is already an approved caregiver.",
            "Maryanne applied ~3 months ago and needs coverage while undergoing chemo at the cancer center every day for at least 30 days.",
            "Needs constant care during treatment. Secondary contact: Courtney Moore (352-834-5523 / thechurchofalice@gmail.com).",
            "Assessment scheduled for Tuesday at 11:00 AM; ensure caregiver coverage is aligned.",
            "Requested callback after Medicaid eligibility update was sent.",
        ),
        "tasks": [
            {
                "title": "Prep Tuesday 11AM assessment (Maryanne Tyler)",
                "description": "Confirm caregiver coverage and paperwork before the scheduled assessment.",
            }
        ],
    },
    {
        "name": "Linda Lehman",
        "contact_name": "Dean Lehman (spouse / primary contact)",
        "email": "dklehman88@gmail.com",
        "phone": "614-354-4536",
        "source": "Family referral via son Fritz Lehman (Dallas)",
        "payor_source": "Private Pay",
        "priority": "medium",
        "city": "Louisville, CO",
        "address": "1376 Golden Eagle Way, Louisville, CO 80027",
        "stage_name": "Incoming Leads",
        "notes": _notes(
            "Dean and Linda recently turned 70; adult children live in Dallas and Chicago.",
            "Family is proactively lining up support: two Tibetan terrier puppies arriving in the next two weeks, and they want a handyman to prep the home.",
            "Linda has fallen three times during the past year and is developing additional health issues; med-management oversight is needed.",
            "Immediate request is an in-home assessment plus safety check. Son Fritz wants to build a relationship now so care can ramp when needed.",
            "Opportunity to nudge toward starting services sooner even though they consider this future planning.",
        ),
        "tasks": [
            {
                "title": "Schedule in-home assessment (Lehman family)",
                "description": "Book on-site visit to review safety risks, puppies, and med-management needs.",
            },
            {
                "title": "Line up handyman walkthrough (Lehman family)",
                "description": "Coordinate contractor referral for accessibility remodel ideas during assessment.",
            },
            {
                "title": "Draft proactive care roadmap (Lehman family)",
                "description": "Summarize options for part-time companion care so son Fritz can step in quickly.",
            },
        ],
    },
    {
        "name": "Mimi Meyers",
        "contact_name": "Danielle Mulluski (POA & daughter-in-law)",
        "email": None,
        "phone": "303-641-0915",
        "source": "Google Search",
        "payor_source": "Private Pay",
        "priority": "medium",
        "city": "Westminster, CO",
        "address": "Hidden Lake Homes Senior Living, 5430 W 73rd Ave, Westminster, CO 80003",
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Client is Mimi Meyers (86) with moderate dementia; Danielle Mulluski is POA and daughter-in-law.",
            "Family wants 3-4 hours of companionship on Thu/Sat/Sun. Physical health is excellent.",
            "They currently use another agency on other days but want to expand coverage with us.",
            "Meeting scheduled today at 3:30 PM at Hidden Lake Homes.",
            "Looking for long-term partnership and would like to stay when we accept Medicaid.",
            "Finalization targeted for Thursday, Nov 20.",
            "Awaiting Medicaid approval update (status 11/20).",
        ),
        "tasks": [
            {
                "title": "Attend 3:30 PM meeting (Mimi Meyers)",
                "description": "On-site meeting at Hidden Lake Homes with Danielle to scope care plan.",
            },
            {
                "title": "Prepare finalization packet for Nov 20 (Mimi Meyers)",
                "description": "Have private-pay agreement and companion schedule ready for signature.",
            },
            {
                "title": "Track Medicaid eligibility update (Mimi Meyers)",
                "description": "Stay in sync with Danielle on Medicaid status so services can expand when approved.",
            },
        ],
    },
    {
        "name": "Michael Romo",
        "contact_name": "Michael Romo",
        "email": "mromo1962@gmail.com",
        "phone": "323-229-0800",
        "source": "Web",
        "payor_source": "Pikes Peak Voucher",
        "priority": "medium",
        "city": "Fountain, CO (client) / California (son)",
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Michael's 99-year-old mother lives in Fountain, CO; he currently resides in California and is coordinating care with his brother locally.",
            "Still applying for the Pikes Peak voucher; gathering paperwork to submit.",
            "Wants us ready to engage as soon as voucher approval lands; sending preliminary intake info now.",
        ),
        "tasks": [
            {
                "title": "Monitor Pikes Peak voucher application (Romo family)",
                "description": "Track voucher status and prep onboarding docs so service can start immediately upon approval.",
            }
        ],
    },
    {
        "name": "Linda Tubb",
        "contact_name": "John Tubb (spouse)",
        "email": None,
        "phone": "805-674-1240",
        "source": "Encompass Health & Rehab of Colorado Springs",
        "payor_source": "Private / Medicare / Supplemental",
        "priority": "high",
        "city": "Colorado Springs, CO",
        "address": "10042 Rolling Ridge Rd, Colorado Springs, CO 80925",
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Care requested for Linda Tubb (DOB 4/4/1951) following Penrose Main hospitalization and Encompass rehab stay.",
            "Medical summary: frequent falls, hypercholesteremia, hypothyroid; 10/29/25 fall led to displaced periprosthetic fracture near left hip arthroplasty.",
            "Current function: bed mobility & transfers require moderate assistance, ADLs largely dependent; ambulation not yet assessed.",
            "Set up assessment for 11/25 at 11:00 AM to design home-care plan immediately post-discharge.",
        ),
        "tasks": [
            {
                "title": "Confirm 11/25 11AM assessment (Linda Tubb)",
                "description": "Coordinate with John and Encompass team to finalize assessment logistics.",
            },
            {
                "title": "Draft immediate care plan post-discharge (Linda Tubb)",
                "description": "Outline caregiver coverage for transfers, ADLs, and mobility support starting right after assessment.",
            },
        ],
    },
    {
        "name": "Elijah Ernest Leyba Jr.",
        "contact_name": "Elijah Ernest Leyba Jr.",
        "email": None,  # Provided email incomplete (bleyba2018@)
        "phone": None,
        "source": None,
        "payor_source": None,
        "priority": "medium",
        "city": None,
        "stage_name": "Ongoing Leads",
        "notes": _notes(
            "Lead captured 11/11. Limited contact info provided (email listed as bleyba2018@; need confirmation).",
            "Diagnosis: Lymphoma. Requires coordinated assessment, contract, and caregiver assignment.",
        ),
        "tasks": [
            {"title": "Verify contact details (Elijah Leyba Jr.)", "description": "Get full email/phone before scheduling."},
            {"title": "Schedule assessment (Elijah Leyba Jr.)", "description": "Confirm availability and document lymphoma care needs."},
            {"title": "Send contract for signature (Elijah Leyba Jr.)", "description": "Follow up after assessment to secure agreement."},
            {"title": "Assign caregiver (Elijah Leyba Jr.)", "description": "Match caregiver experienced with oncology support."},
        ],
    },
    {
        "name": "David Akin",
        "contact_name": "Nancy Akin",
        "email": None,
        "phone": "719-351-4307",
        "source": "Encompass COS",
        "payor_source": "Private Pay (Nancy Akin)",
        "priority": "medium",
        "city": "Colorado Springs, CO",
        "stage_name": "Incoming Leads",
        "notes": _notes(
            "Referral from Encompass Colorado Springs. David required ventilation and extended hospitalization.",
            "Family will move forward once he comes off the ventilator and is discharged (status 10/31/25).",
        ),
        "tasks": [
            {
                "title": "Follow up after ventilator discharge (David Akin)",
                "description": "Check with Nancy on discharge plan and schedule in-home assessment when cleared.",
            }
        ],
    },
    {
        "name": "Nancy Olander",
        "contact_name": "Susan Ward (sister) / Nancy Olander",
        "email": None,
        "phone": "720-361-5904",
        "source": "Self-Research",
        "payor_source": "Private Pay (Nancy Olander)",
        "priority": "medium",
        "city": None,
        "stage_name": "Incoming Leads",
        "notes": _notes(
            "Diabetic with recent back surgery and another scheduled; currently immobile.",
            "Hospitalized for low insulin levels; physicians recommend staying inpatient for now.",
            "Primary contacts: sister Susan Ward (402-203-5280) and Nancy herself (720-361-5904 / 303-499-7814).",
            "Family will reconnect once home-care services are required (status 10/10/25).",
        ),
        "tasks": [
            {
                "title": "Check in post-surgery (Nancy Olander)",
                "description": "Revisit after next back surgery to align on in-home support timing.",
            }
        ],
    },
    {
        "name": "Gary Lynn Galawa",
        "contact_name": "Stella Ulm (ex-wife)",
        "email": None,
        "phone": "303-499-7814",
        "source": "Self-Research",
        "payor_source": "Private Pay (Gary Galawa)",
        "priority": "medium",
        "city": None,
        "stage_name": "Incoming Leads",
        "notes": _notes(
            "Diagnosed with lymphoma and transferred to a higher level of care.",
            "Stella will reach back out if one-on-one care is needed in addition to assisted living (status 10/05/25).",
        ),
        "tasks": [
            {
                "title": "Monitor assisted living needs (Gary Galawa)",
                "description": "Stay in touch with Stella in case additional personal care is requested.",
            }
        ],
    },
    {
        "name": "Samantha Fogel",
        "contact_name": "Samantha Fogel",
        "email": None,
        "phone": "719-308-4087",
        "source": "TRE – Kaitlin Torres",
        "payor_source": "TRE / Medicaid",
        "priority": "medium",
        "city": None,
        "stage_name": "Incoming Leads",
        "notes": _notes(
            "Has her own caregiver currently; waiting on Medicaid authorization through TRE (status 11/21/25).",
        ),
        "tasks": [
            {
                "title": "Track TRE Medicaid approval (Samantha Fogel)",
                "description": "Coordinate with Kaitlin Torres once waiver funding is available.",
            }
        ],
    },
]


REFERRAL_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "Barbara Scriven",
        "organization": "PAM",
        "email": "bscriven@pamspecialty.com",
        "phone": "303-264-6969",
        "source_type": "Hospital / Transitions",
        "status": "incoming",
        "notes": _notes(
            "Director of Social Services met on cookie route.",
            "Mentioned they rarely partner with private home care but we followed up anyway.",
        ),
    },
    {
        "name": "Paul DeLoux",
        "organization": "Sloan's Lake Rehabilitation",
        "email": "paledoux@ensignservices.net",
        "phone": "720-508-7313",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Executive Director; awaiting follow-up after cookie route introduction."),
    },
    {
        "name": "Michelle Carr, RN, COO",
        "organization": "Sloan's Lake Rehabilitation",
        "email": None,
        "phone": None,
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Director of Nursing connection from Sloan's Lake; contact details pending."),
    },
    {
        "name": "Kristen Henning M.MSc, CCht",
        "organization": "Cambridge Care Center",
        "email": "khenning@cambridgecarecenter.com",
        "phone": "303-232-4405 ext. 3113",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Director of Social Services; already received cookie route follow-up."),
    },
    {
        "name": "Savannah Stark, NHA",
        "organization": "Allison Care Center",
        "email": "sstark@allisoncc.health",
        "phone": "303-232-7177",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("CEO; interested in continued coordination after cookie route visit."),
    },
    {
        "name": "Leslyann Mascorro",
        "organization": "Allison Care Center",
        "email": "lmascorro@allisoncc.health",
        "phone": None,
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Social Services Director; follow-up already sent."),
    },
    {
        "name": "Angela Kopriva",
        "organization": "Lakeside Post Acute",
        "email": "angela.kopriva@lakesidepa.com",
        "phone": None,
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Director of Nursing; cookie route follow-up completed."),
    },
    {
        "name": "Jennifer Hines",
        "organization": "Lakeside Post Acute",
        "email": "jennifer.hines@lakesidepa.com",
        "phone": "303-421-2272",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Marketing contact; part of Lakeside outreach set."),
    },
    {
        "name": "Daniel Pederson",
        "organization": "Lakeside Post Acute",
        "email": "daniel.pederson@lakesidepa.com",
        "phone": "303-421-2272",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Administrator; included in cookie route follow-ups."),
    },
    {
        "name": "Kurt Cummiskey",
        "organization": "Wheat Ridge Care Center",
        "email": "kcummiskey@wheatridgemanorcc.health",
        "phone": "303-238-0481",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes("Social Services Director; follow-up completed."),
    },
    {
        "name": "Gifty Opare",
        "organization": "Marycrest Assisted Living",
        "email": "gopare@marycrest.org",
        "phone": None,
        "source_type": "Senior Housing",
        "status": "incoming",
        "notes": _notes(
            "Executive Director currently on medical leave; plans to step down to Assistant Director.",
            "No acting ED right now; still wants to keep referrals flowing.",
        ),
    },
    {
        "name": "Meko Lincoln",
        "organization": "Marycrest Assisted Living",
        "email": "mlincoln@marycrest.org",
        "phone": "303-433-0282 ext. 226",
        "source_type": "Senior Housing",
        "status": "incoming",
        "notes": _notes(
            "Director of Nursing and only onsite leadership at the moment; met 12/2.",
        ),
    },
    {
        "name": "Tamara Drees NP-C",
        "organization": "Stone Mountain Primary Care",
        "email": "tamara@stonemountainprimarycare.org",
        "phone": "303-551-3643",
        "source_type": "Primary Care",
        "status": "incoming",
        "notes": _notes("Primary care partner; provided updated card and email."),
    },
    {
        "name": "LemLem Ahmed",
        "organization": "Park Hill Assisted Living",
        "email": "parkhillrsd@seniorhousingoptions.org",
        "phone": "303-993-5049 ext. 402",
        "source_type": "Senior Housing",
        "status": "ongoing",
        "notes": _notes(
            "Resident Services Coordinator & Housing Eligibility Specialist.",
            "Met on cookie route; coordinating new resident referrals.",
            "Sent email and placed follow-up call regarding next steps.",
        ),
    },
    {
        "name": "Anyula Whitmill",
        "organization": "Park Hill Assisted Living",
        "email": None,
        "phone": "303-993-5049 ext. 16",
        "source_type": "Senior Housing",
        "status": "ongoing",
        "notes": _notes(
            "Administrator. Connected on cookie route.",
            "Provided general site parkhillseniorhousingoptions.org for follow-up.",
        ),
    },
    {
        "name": "Sandra Barrera",
        "organization": "Uptown Healthcare Center",
        "email": "sbarrera@uptowncc.health",
        "phone": "720-633-2381",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "Social Services Assistant and lead point of contact from cookie route visit.",
            "Email and call completed; meeting scheduled for 12/5 at 11:30 AM.",
        ),
    },
    {
        "name": "Seifu Tolu",
        "organization": "Uptown Healthcare Center",
        "email": None,
        "phone": "303-860-0500 ext. 37102",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "DON, RN, MSN, PhD. Partnering via cookie route introduction.",
            "Meeting scheduled for 12/5 at 11:30 AM.",
        ),
    },
    {
        "name": "Sarah Nanfuka",
        "organization": "The Community at Franklin Park",
        "email": "snanfuka@abhomes.org",
        "phone": "303-479-3707",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "Social Services Coordinator met during cookie route.",
            "Emailed and called to confirm ongoing collaboration.",
        ),
    },
    {
        "name": "Tamika Atkins",
        "organization": "The Community at Franklin Park",
        "email": "tatkins@abhomes.org",
        "phone": "303-479-3692 / 720-417-5668",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "Administrator (Nursing Home Admin). Wants ongoing partnership; introduced on cookie route.",
        ),
    },
    {
        "name": "Ann Cambigue",
        "organization": "The Community at Franklin Park",
        "email": None,
        "phone": "303-479-3694 (O) / 303-830-3182 (C)",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "Marketing & Admissions Director connected via cookie route drop-off.",
        ),
    },
    {
        "name": "Shayla Eidson, NHA",
        "organization": "Denver North Care Center",
        "email": "seidson@denvernorthcc.health",
        "phone": "303-861-4825 ext. 33103",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "CEO met during cookie route outreach.",
            "Sent email and placed follow-up call to confirm interest.",
        ),
    },
    {
        "name": "Robert (with DON)",
        "organization": "Briarwood Care Center",
        "email": "robert_franklin@lcca.com",
        "phone": "303-399-0350",
        "source_type": "Skilled Nursing",
        "status": "ongoing",
        "notes": _notes(
            "Wants to meet with DON next week; include Marissa since it is her territory.",
            "Left messages on 12/1 and 12/2 plus follow-up email; Tuesdays work best and awaiting confirmation.",
        ),
    },
    {
        "name": "Kang Ho",
        "organization": "Alpine Pharmacy",
        "email": "manager@alpinepharmacy.com",
        "phone": None,
        "source_type": "Healthcare Facility",
        "status": "ongoing",
        "notes": _notes(
            "Re-engaged previous pharmacy contact. Virtual meeting scheduled for Thursday, Nov 20.",
        ),
    },
    {
        "name": "Melodie Oppenheim & Genie Ruiz",
        "organization": "Colorado Economic Defense Project",
        "email": "genie.ruiz@cedproject.org",
        "phone": None,
        "source_type": "Community Organization",
        "status": "ongoing",
        "notes": _notes(
            "Team previously connected; virtual meeting scheduled Monday, Nov 24 to coordinate referrals.",
        ),
    },
    {
        "name": "Carolyn Bravo",
        "organization": "Guardianship Alliance / Ability Connection Colorado",
        "email": "cbravo@abilityconnectioncolorado.org",
        "phone": None,
        "source_type": "Legal / Guardianship",
        "status": "ongoing",
        "notes": _notes(
            "Phone discussion confirmed wide age-range support; will exchange referrals and share guardianship resources.",
            "Website: abilityconnectioncolorado.org",
        ),
    },
    {
        "name": "Megan Hazel / Housing Transitions Team",
        "organization": "UC Health",
        "email": "megan.hazel@uchealth.org,housingtransitionsteam@uchealth.org",
        "phone": None,
        "source_type": "Hospital / Transitions",
        "status": "ongoing",
        "notes": _notes(
            "Megan transitioned off the team but connected us with Housing Transitions staff; working to schedule virtual or in-person meeting.",
        ),
    },
    {
        "name": "Doug Page",
        "organization": "Care Patrol (North Denver)",
        "email": "dpage@carepatrol.com",
        "phone": "720-485-5114",
        "source_type": "Placement Agency",
        "status": "ongoing",
        "notes": _notes(
            "Introduced via Amy at CarePatrol. Wants to set up a call and circle back after Thanksgiving.",
        ),
    },
]


BUSINESS_CARD_CONTACTS: List[Dict[str, Any]] = [
    {
        "name": "Ruth Mayberry, LPN, CWCA",
        "organization": "Clermont Park (A Life Plan Community)",
        "email": "rmayberry@clcliving.org",
        "phone": "720-974-3772",
        "address": "2480 S Clermont Street, Denver, CO 80222",
        "source_type": "Senior Living",
        "status": "incoming",
        "notes": _notes(
            "Transition Care Manager. Main line 720-974-3700, fax 303-758-1787.",
            "Shared card during facility visit for discharge coordination."
        ),
    },
    {
        "name": "Julie McKiernan, RN, MSN, CEN",
        "organization": "Clermont Park (A Life Plan Community)",
        "email": "jmckiernan@clcliving.org",
        "phone": "720-974-3711",
        "address": "2480 S Clermont Street, Denver, CO 80222",
        "source_type": "Senior Living",
        "status": "incoming",
        "notes": _notes(
            "Director of Nursing. Main 720-974-3700, fax 303-758-1787, cell 303-909-9284.",
            "Key clinical contact for escalated resident needs."
        ),
    },
    {
        "name": "Jennifer King",
        "organization": "Amberwood Post Acute",
        "email": "Jennifer.King@amberwoodpa.com",
        "phone": "303-756-1566",
        "address": "4686 E Asbury Circle, Denver, CO 80222",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Director of Social Services. Cell 720-739-0689, fax 303-756-5261.",
            "Shared business card during facility rounds; main point for Amberwood referrals."
        ),
    },
    {
        "name": "Jill Bash",
        "organization": "WestLake Care Community",
        "email": "JBash@colavria.com",
        "phone": "303-238-5363 x129",
        "address": "1655 Eaton Street, Lakewood, CO 80214",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Admissions/Marketing Coordinator. Fax 303-845-9145.",
            "Interested in coordinated admissions support."
        ),
    },
    {
        "name": "Julie Goulding",
        "organization": "Park Hill Assisted Living",
        "email": "parkhillwellness@seniorhousingoptions.org",
        "phone": "303-993-5049 ext. 10",
        "address": "1901 Eudora Street, Denver, CO 80220",
        "source_type": "Senior Housing",
        "status": "incoming",
        "notes": _notes(
            "Wellness Coordinator; fax 303-370-1063.",
            "New care coordination contact from business card batch."
        ),
    },
    {
        "name": "Charice Shackelford",
        "organization": "The Woodlands Assisted Living",
        "email": "wellness@woodlands2.com",
        "source_type": "Senior Housing",
        "status": "incoming",
        "notes": _notes(
            "Wellness lead identified during business card scan; coordinate resident support."
        ),
    },
    {
        "name": "Christer Cabasug",
        "organization": "Residence at University Hills (AMC)",
        "email": "residenceatunivhills.mgr@liveamc.com",
        "source_type": "Senior Housing",
        "status": "incoming",
        "notes": _notes(
            "Community manager for Residence at University Hills, captured from handwritten note."
        ),
    },
    {
        "name": "Dustin Turner",
        "organization": "Family Tree Private Care",
        "email": "dustin.turner@familytreecares.com",
        "phone": "720-204-6083",
        "address": "636 Coffman Street, Suite 102, Longmont, CO 80501",
        "source_type": "Home Care Partner",
        "status": "incoming",
        "notes": _notes(
            "Business Development Executive. Cell 720-552-0191, fax 720-873-2010.",
            "Partner for private-duty overflow cases."
        ),
    },
    {
        "name": "Demetrea Kinnermon",
        "organization": "Family Tree Private Care",
        "email": "demetrea.kinnermon@familytreecares.com",
        "phone": "303-791-3155",
        "source_type": "Home Care Partner",
        "status": "incoming",
        "notes": _notes(
            "Market Director - Colorado. Cell 303-877-3205.",
            "Shared business card; coordinating field marketing efforts."
        ),
    },
    {
        "name": "Susan Perucchini, COTA, CM",
        "organization": "Encompass Health Rehabilitation Hospital of Littleton",
        "email": "susan.perucchini@encompasshealth.com",
        "phone": "303-334-1135",
        "address": "1001 West Mineral Avenue, Littleton, CO 80120",
        "source_type": "Hospital / Transitions",
        "status": "incoming",
        "notes": _notes(
            "Case Manager II. Fax 303-334-1494.",
            "Primary liaison for ventilator and neuro rehab discharges."
        ),
    },
    {
        "name": "Valarie Bates",
        "organization": "Encompass Health Rehabilitation Hospital of Littleton",
        "email": "valarie.bates@encompasshealth.com",
        "phone": "303-334-1166",
        "address": "1001 West Mineral Avenue, Littleton, CO 80120",
        "source_type": "Hospital / Transitions",
        "status": "incoming",
        "notes": _notes(
            "Case Management Assistant. Fax 303-334-1494.",
            "Handles document routing for Encompass discharges."
        ),
    },
    {
        "name": "Melissa Jacobs, BA, CCM",
        "organization": "Encompass Health Rehabilitation Hospital of Littleton",
        "email": "melissa.jacobs@encompasshealth.com",
        "phone": "303-334-1163",
        "address": "1001 West Mineral Avenue, Littleton, CO 80120",
        "source_type": "Hospital / Transitions",
        "status": "incoming",
        "notes": _notes(
            "Certified Case Manager. Cell 720-813-0060, fax 303-334-1494."
        ),
    },
    {
        "name": "Irene Ntui",
        "organization": "Encompass Health Rehabilitation Hospital of Littleton",
        "email": "Irene.EbhambohNtuiEwenye@encompasshealth.com",
        "phone": "303-334-1195",
        "address": "1001 West Mineral Avenue, Littleton, CO 80120",
        "source_type": "Hospital / Transitions",
        "status": "incoming",
        "notes": _notes(
            "Case Manager II. Fax 303-334-1494.",
            "Contact captured from business card batch."
        ),
    },
    {
        "name": "Scott Zulauf",
        "organization": "Littleton Care and Rehabilitation Center",
        "email": "SZulauf@ensignservices.net",
        "phone": "303-798-2497",
        "address": "5822 S Lowell Way, Littleton, CO 80123",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Admissions Director. Office 720-955-4728, fax 303-797-6847, eFax 949-385-9221."
        ),
    },
    {
        "name": "Kayla Bergen",
        "organization": "Littleton Care and Rehabilitation Center",
        "email": "KBergen@ensignservices.net",
        "phone": "303-798-2497",
        "address": "5822 S Lowell Way, Littleton, CO 80123",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Social Services Director. Office 720-409-5604, fax 303-797-6847, eFax 949-385-9221."
        ),
    },
    {
        "name": "Savannah Leifer",
        "organization": "Brookshire Post Acute",
        "email": "savannah.leifer@brookshirepa.com",
        "phone": "303-756-1546",
        "address": "4660 E Asbury Circle, Denver, CO 80222",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Social Services Director. Cell 970-234-0216.",
            "Shared card with Colorado CareAssist brochure."
        ),
    },
    {
        "name": "Lizbeth Castaneda Solis",
        "organization": "Brookdale Senior Living",
        "email": "e000791712@brookdale.com",
        "phone": "303-696-0576",
        "address": "8030 E Girard Ave, Denver, CO 80231",
        "source_type": "Senior Housing",
        "status": "incoming",
        "notes": _notes(
            "Resident Services Director for Brookdale. Business card captured during route."
        ),
    },
    {
        "name": "Isaac Moir",
        "organization": "Denver North Care Center",
        "email": "imoir@dncarecenter.com",
        "phone": "303-861-4826",
        "address": "2201 N Downing Street, Denver, CO 80205",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Director of Environmental Services. Cell 720-483-3019, fax 303-861-4308."
        ),
    },
    {
        "name": "Jeff Carlson",
        "organization": "UnitedHealthcare Senior Community Care",
        "email": "jeff_carlson@optum.com",
        "phone": "801-599-4912",
        "address": "2600 West Executive Parkway, Suite 400, Salt Lake City, UT 84043",
        "source_type": "Payer / Insurance",
        "status": "incoming",
        "notes": _notes(
            "Community Outreach Representative; met during outreach swing."
        ),
    },
    {
        "name": "Cyrus Maes",
        "organization": "Highlands Ranch Community Association",
        "email": "Cyrus.Maes@HRCAonline.org",
        "phone": "303-471-8850",
        "address": "8800 Broadway, Highlands Ranch, CO 80126",
        "source_type": "Community Organization",
        "status": "incoming",
        "notes": _notes(
            "Facility Manager; handles HRCA space usage and wellness partnerships."
        ),
    },
    {
        "name": "Hannah Yeager",
        "organization": "Highlands Ranch Community Association",
        "email": "Hannah.yeager@hrcaonline.org",
        "phone": "303-471-7044",
        "source_type": "Community Organization",
        "status": "incoming",
        "notes": _notes(
            "Fitness Supervisor. Captured via handwritten note."
        ),
    },
    {
        "name": "Tara Acklam, MSW",
        "organization": "Highline Post Acute",
        "email": "tara.acklam@highlinepost.com",
        "phone": "303-569-4262",
        "address": "616 S Wadsworth Blvd, Lakewood, CO 80226",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Social Services Director. Fax 303-301-1483."
        ),
    },
    {
        "name": "Rachel Elliott",
        "organization": "Vi at Highlands Ranch",
        "email": "RElliott@ViLiving.com",
        "phone": "262-744-0303",
        "address": "9085 Ranch River Circle, Highlands Ranch, CO 80126",
        "source_type": "Senior Living",
        "status": "incoming",
        "notes": _notes(
            "Outreach Manager; shared interest in reciprocal referrals."
        ),
    },
    {
        "name": "Benjamin Hoover, NHA",
        "organization": "Vi at Highlands Ranch",
        "email": "BHoover@ViLiving.com",
        "phone": "720-348-7928",
        "address": "9085 Ranch River Circle, Highlands Ranch, CO 80126",
        "source_type": "Senior Living",
        "status": "incoming",
        "notes": _notes(
            "Care Center Administrator. Fax 720-348-7999."
        ),
    },
    {
        "name": "Marjorie Olson, LCSW",
        "organization": "Vi at Highlands Ranch",
        "email": "MOlson@ViLiving.com",
        "phone": "720-348-7904",
        "address": "9085 Ranch River Circle, Highlands Ranch, CO 80126",
        "source_type": "Senior Living",
        "status": "incoming",
        "notes": _notes(
            "Social Services Manager; part of Vi contact suite."
        ),
    },
    {
        "name": "Jolene Rees-Underwood",
        "organization": "Sloan's Lake Rehabilitation Center",
        "email": "JRees-Underwood@ensignservices.net",
        "phone": "720-508-7317",
        "address": "1601 Lowell Blvd, Denver, CO 80204",
        "source_type": "Skilled Nursing",
        "status": "incoming",
        "notes": _notes(
            "Assistant Director of Nursing. Fax 720-508-7297."
        ),
    },
]

REFERRAL_SOURCES.extend(BUSINESS_CARD_CONTACTS)


stage_cache: Dict[str, PipelineStage] = {}


def ensure_stage(session, stage_name: str) -> PipelineStage:
    """Fetch a pipeline stage by name, caching results for this run."""
    cached = stage_cache.get(stage_name.lower())
    if cached:
        return cached

    stage = (
        session.query(PipelineStage)
        .filter(func.lower(PipelineStage.name) == stage_name.lower())
        .first()
    )
    if not stage:
        raise RuntimeError(
            f"Pipeline stage '{stage_name}' not found. Run init_pipeline.py first."
        )

    stage_cache[stage_name.lower()] = stage
    return stage


def ensure_lead(
    session, stage: PipelineStage, payload: Dict[str, Any]
) -> Tuple[Lead, bool]:
    """Create or update the lead record. Returns (lead, created_flag)."""
    existing = (
        session.query(Lead)
        .filter(func.lower(Lead.name) == payload["name"].lower())
        .first()
    )
    now = datetime.now(timezone.utc)

    if existing:
        updated = False
        for field in [
            "contact_name",
            "email",
            "phone",
            "source",
            "payor_source",
            "priority",
            "city",
            "address",
        ]:
            new_val = payload.get(field)
            if new_val and getattr(existing, field) != new_val:
                setattr(existing, field, new_val)
                updated = True

        # Always make sure latest notes are present.
        notes = payload.get("notes")
        if notes and notes not in (existing.notes or ""):
            existing.notes = (existing.notes or "").strip()
            if existing.notes:
                existing.notes += "\n\n"
            existing.notes += notes
            updated = True

        if existing.stage_id != stage.id:
            existing.stage_id = stage.id
            updated = True

        if updated:
            session.add(
                LeadActivity(
                    lead_id=existing.id,
                    activity_type="batch_update",
                    description="Lead details refreshed from December 2025 batch import",
                    user_email=SYSTEM_USER_EMAIL,
                    new_value=payload["name"],
                )
            )
        return existing, False

    order_index = (
        session.query(func.count(Lead.id))
        .filter(Lead.stage_id == stage.id)
        .scalar()
        or 0
    )

    lead = Lead(
        name=payload["name"],
        contact_name=payload.get("contact_name"),
        email=payload.get("email"),
        phone=payload.get("phone"),
        address=payload.get("address"),
        city=payload.get("city"),
        source=payload.get("source"),
        payor_source=payload.get("payor_source"),
        priority=payload.get("priority", "medium"),
        notes=payload.get("notes"),
        stage_id=stage.id,
        order_index=order_index,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(lead)
    session.flush()

    session.add(
        LeadActivity(
            lead_id=lead.id,
            activity_type="created",
            description=f"Lead created via December 2025 batch import: {lead.name}",
            user_email=SYSTEM_USER_EMAIL,
            new_value=lead.name,
        )
    )
    return lead, True


def ensure_tasks(session, lead: Lead, payload: Dict[str, Any]) -> None:
    for task_payload in payload.get("tasks", []):
        title = task_payload["title"]
        existing_task = (
            session.query(LeadTask)
            .filter(LeadTask.lead_id == lead.id, LeadTask.title == title)
            .first()
        )
        if existing_task:
            continue

        due_date = task_payload.get("due_date")
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        task = LeadTask(
            lead_id=lead.id,
            title=title,
            description=task_payload.get("description"),
            due_date=due_date,
            status="pending",
        )
        session.add(task)
        session.flush()

        session.add(
            LeadActivity(
                lead_id=lead.id,
                activity_type="task_created",
                description=f"Task added: {task.title}",
                user_email=SYSTEM_USER_EMAIL,
                new_value=task.title,
            )
        )


def ensure_referral_source(session, payload: Dict[str, Any]) -> bool:
    """Create or update referral source. Returns True if created."""
    query = session.query(ReferralSource).filter(
        func.lower(ReferralSource.name) == payload["name"].lower()
    )
    if payload.get("organization"):
        query = query.filter(
            func.lower(ReferralSource.organization) == payload["organization"].lower()
        )

    source = query.first()
    fields = {
        "organization": payload.get("organization"),
        "email": payload.get("email"),
        "phone": payload.get("phone"),
        "source_type": payload.get("source_type"),
        "status": payload.get("status", "active"),
        "notes": payload.get("notes"),
    }

    if source:
        updated = False
        for field, value in fields.items():
            if value and getattr(source, field) != value:
                setattr(source, field, value)
                updated = True
        if updated:
            session.add(source)
        return False

    source = ReferralSource(
        name=payload["name"],
        organization=payload.get("organization"),
        email=payload.get("email"),
        phone=payload.get("phone"),
        source_type=payload.get("source_type"),
        status=payload.get("status", "active"),
        notes=payload.get("notes"),
    )
    session.add(source)
    session.flush()
    return True


def _find_contact(session, name: Optional[str], email: Optional[str]) -> Optional[Contact]:
    """Find an existing contact by email (preferred) or name."""
    if email:
        contact = (
            session.query(Contact)
            .filter(func.lower(Contact.email) == email.lower())
            .first()
        )
        if contact:
            return contact
    if name:
        return (
            session.query(Contact)
            .filter(func.lower(Contact.name) == name.lower())
            .first()
        )
    return None


def _serialize_tags(tags: List[str]) -> str:
    return json.dumps(tags)


def _lead_priority_to_status(priority: Optional[str]) -> str:
    mapping = {"high": "hot", "medium": "warm", "low": "cold"}
    if not priority:
        return "warm"
    return mapping.get(priority.lower(), "warm")


def _referral_status_to_contact_status(status: Optional[str]) -> str:
    mapping = {"incoming": "cold", "ongoing": "warm", "active": "hot"}
    if not status:
        return "warm"
    return mapping.get(status.lower(), "warm")


def ensure_contact_from_lead(session, lead: Lead) -> None:
    """Create or update a Contact record for the given lead."""
    contact_name = lead.contact_name or lead.name
    contact = _find_contact(session, contact_name, lead.email)
    created_at = lead.created_at or datetime.now(timezone.utc)
    last_activity = lead.updated_at or lead.created_at or created_at
    tags = ["Prospect"]
    status = _lead_priority_to_status(lead.priority)

    if contact:
        updated = False
        for field, value in [
            ("name", contact_name),
            ("email", lead.email),
            ("phone", lead.phone),
            ("address", lead.address or lead.city),
            ("notes", lead.notes),
            ("source", lead.source),
        ]:
            if value and getattr(contact, field) != value:
                setattr(contact, field, value)
                updated = True

        if contact.contact_type != "prospect":
            contact.contact_type = "prospect"
            updated = True
        if contact.status != status:
            contact.status = status
            updated = True

        if contact.tags != _serialize_tags(tags):
            contact.tags = _serialize_tags(tags)
            updated = True

        if not contact.last_activity or contact.last_activity < last_activity:
            contact.last_activity = last_activity
            updated = True

        if updated:
            contact.updated_at = datetime.now(timezone.utc)
            session.add(contact)
        return

    contact = Contact(
        name=contact_name,
        company=None,
        email=lead.email,
        phone=lead.phone,
        address=lead.address or lead.city,
        notes=lead.notes,
        contact_type="prospect",
        status=status,
        tags=_serialize_tags(tags),
        last_activity=last_activity,
        source=lead.source,
        created_at=created_at,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(contact)


def ensure_contact_from_referral(session, referral: ReferralSource) -> None:
    """Create or update a Contact record for the given referral source."""
    contact = _find_contact(session, referral.name, referral.email)
    created_at = referral.created_at or datetime.now(timezone.utc)
    last_activity = referral.updated_at or referral.created_at or created_at
    tags = ["Referral Source"]
    status = _referral_status_to_contact_status(referral.status)

    if contact:
        updated = False
        for field, value in [
            ("name", referral.name),
            ("company", referral.organization),
            ("email", referral.email),
            ("phone", referral.phone),
            ("address", getattr(referral, "address", None)),
            ("notes", referral.notes),
            ("source", referral.source_type),
        ]:
            if value and getattr(contact, field) != value:
                setattr(contact, field, value)
                updated = True

        if contact.contact_type != "referral":
            contact.contact_type = "referral"
            updated = True
        if contact.status != status:
            contact.status = status
            updated = True

        if contact.tags != _serialize_tags(tags):
            contact.tags = _serialize_tags(tags)
            updated = True

        if not contact.last_activity or contact.last_activity < last_activity:
            contact.last_activity = last_activity
            updated = True

        if updated:
            contact.updated_at = datetime.now(timezone.utc)
            session.add(contact)
        return

    contact = Contact(
        name=referral.name,
        company=referral.organization,
        email=referral.email,
        phone=referral.phone,
        address=getattr(referral, "address", None),
        notes=referral.notes,
        contact_type="referral",
        status=status,
        tags=_serialize_tags(tags),
        last_activity=last_activity,
        source=referral.source_type,
        created_at=created_at,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(contact)


def _lead_to_deal_payload(lead: Lead) -> Dict[str, Any]:
    """Map a lead into a simple deal payload."""
    # Approximate hours from notes when possible
    hours_map = {
        "carin craft": 42,  # 6 hours/day * 7 days (requested 9-3)
        "mimi meyers": 10.5,  # 3-4 hours Thu/Sat/Sun (~3.5*3)
    }
    est_hours = hours_map.get(lead.name.lower())

    def _rate(payor: Optional[str]) -> float:
        if payor and "va" in payor.lower():
            return 67.0
        return 40.0

    rate = _rate(lead.payor_source)
    amount = (est_hours or 0) * rate

    return {
        "name": lead.name,
        "amount": amount,
        "stage": "opportunity",
        "description": (lead.notes or "")[:500],
        "created_at": lead.created_at,
        "expected_closing_date": None,
        "contact_ids": [],
        "company_id": None,
        "est_weekly_hours": est_hours,
    }


def ensure_deal_from_lead(session, lead: Lead) -> None:
    """Create a Deal for the lead if not present."""
    existing = (
        session.query(Deal)
        .filter(func.lower(Deal.name) == lead.name.lower())
        .first()
    )
    payload = _lead_to_deal_payload(lead)
    now = datetime.now(timezone.utc)
    if existing:
        updated = False
        for field in ["amount", "stage", "description", "expected_closing_date", "est_weekly_hours"]:
            new_val = payload.get(field)
            if getattr(existing, field) != new_val:
                setattr(existing, field, new_val)
                updated = True
        if updated:
            existing.updated_at = now
            session.add(existing)
        return

    deal = Deal(
        name=payload["name"],
        amount=payload["amount"],
        stage=payload["stage"],
        description=payload["description"],
        est_weekly_hours=payload["est_weekly_hours"],
        contact_ids=json.dumps(payload["contact_ids"]),
        company_id=payload["company_id"],
        created_at=payload["created_at"] or now,
        updated_at=now,
    )
    session.add(deal)


def main() -> None:
    session = db_manager.get_session()
    created = 0
    updated = 0
    ref_created = 0
    ref_updated = 0
    try:
        for payload in LEAD_BATCH:
            stage_name = payload.get("stage_name", DEFAULT_STAGE_NAME)
            stage = ensure_stage(session, stage_name)
            lead, was_created = ensure_lead(session, stage, payload)
            ensure_tasks(session, lead, payload)
            ensure_contact_from_lead(session, lead)
            ensure_deal_from_lead(session, lead)
            if was_created:
                created += 1
                print(f"✅ Created lead '{lead.name}' (ID {lead.id})")
            else:
                updated += 1
                print(f"🔁 Updated lead '{lead.name}' (ID {lead.id})")

        for payload in REFERRAL_SOURCES:
            created_flag = ensure_referral_source(session, payload)
            # Refresh referral object to capture created_at/updated_at
            referral = (
                session.query(ReferralSource)
                .filter(func.lower(ReferralSource.name) == payload["name"].lower())
                .first()
            )
            if referral:
                ensure_contact_from_referral(session, referral)
            if created_flag:
                ref_created += 1
                print(f"✅ Added referral source '{payload['name']}'")
            else:
                ref_updated += 1
                print(f"🔁 Refreshed referral source '{payload['name']}'")

        session.commit()
        print(
            f"\nCompleted December 2025 lead import: {created} created, {updated} updated."
        )
        print(
            f"Referral sources processed: {ref_created} created, {ref_updated} updated."
        )
    except Exception as exc:
        session.rollback()
        raise SystemExit(f"Lead import failed: {exc}") from exc
    finally:
        session.close()


if __name__ == "__main__":
    main()
