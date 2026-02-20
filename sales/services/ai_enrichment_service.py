"""
AI Enrichment Service for CRM

Uses Anthropic Haiku to:
- Enrich company data (size, industry, contacts)
- Detect duplicate contacts
- Summarize interactions
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from models import ActivityLog, Contact, ReferralSource

# Anthropic Haiku for text-only enrichment (fast, reliable, cheap)
_ENRICHMENT_MODEL = "claude-haiku-4-5-20251001"


def _get_anthropic_client():
    """Get configured Anthropic client"""
    if not ANTHROPIC_AVAILABLE:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


# =============================================================================
# Company Enrichment
# =============================================================================

async def enrich_company(
    db: Session,
    company_id: int,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Enrich a company with AI-gathered data.

    Args:
        db: Database session
        company_id: Company (ReferralSource) ID
        force: Force re-enrichment even if already enriched

    Returns:
        Dict with enrichment results
    """
    company = db.query(ReferralSource).filter_by(id=company_id).first()
    if not company:
        return {"error": "Company not found"}

    # Skip if recently enriched (unless forced)
    if not force and company.enriched_at:
        days_since = (datetime.utcnow() - company.enriched_at).days
        if days_since < 30:
            return {
                "status": "skipped",
                "message": f"Already enriched {days_since} days ago",
                "data": {
                    "employee_count": company.employee_count,
                    "industry": company.industry,
                    "enrichment_confidence": company.enrichment_confidence,
                }
            }

    client = _get_anthropic_client()
    if not client:
        return {"error": "Anthropic not available"}

    # Build prompt
    prompt = f"""You are a business research assistant. Given the following company information,
provide enriched data. Return ONLY valid JSON, no markdown.

Company Name: {company.name}
Organization: {company.organization or 'N/A'}
Address: {company.address or 'N/A'}
Source Type: {company.source_type or 'N/A'}
Website: {company.website or 'N/A'}

Return JSON with these fields:
{{
    "employee_count": "estimated range like '10-50', '50-200', '200-500', '500+', or 'Unknown'",
    "industry": "specific industry like 'Skilled Nursing Facility', 'Home Health Agency', 'Hospital', 'Assisted Living', etc.",
    "facility_type": "normalized type like 'skilled_nursing', 'assisted_living', 'hospital', 'home_health', 'hospice', 'physician_office', etc.",
    "confidence": 0.0-1.0 confidence score based on available information
}}

If you cannot determine a field with reasonable confidence, use null.
"""

    try:
        response = client.messages.create(
            model=_ENRICHMENT_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()

        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            return {"error": "Could not parse AI response", "raw": text}

        # Update company
        if data.get("employee_count"):
            company.employee_count = data["employee_count"]
        if data.get("industry"):
            company.industry = data["industry"]
        if data.get("facility_type"):
            company.facility_type_normalized = data["facility_type"]

        company.enrichment_confidence = data.get("confidence", 0.5)
        company.enriched_at = datetime.utcnow()

        db.commit()

        return {
            "status": "success",
            "data": {
                "employee_count": company.employee_count,
                "industry": company.industry,
                "facility_type": company.facility_type_normalized,
                "confidence": company.enrichment_confidence,
            }
        }

    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Contact Deduplication
# =============================================================================

def find_duplicate_contacts(
    db: Session,
    contact_id: int = None,
    contact: Contact = None,
) -> List[Dict[str, Any]]:
    """
    Find potential duplicate contacts.

    Args:
        db: Database session
        contact_id: Contact ID to check
        contact: Or pass Contact object directly

    Returns:
        List of potential duplicates with match info
    """
    if contact_id and not contact:
        contact = db.query(Contact).filter_by(id=contact_id).first()

    if not contact:
        return []

    duplicates = []

    # 1. Exact email match (definite duplicate)
    if contact.email:
        email_matches = db.query(Contact).filter(
            Contact.id != contact.id,
            func.lower(Contact.email) == contact.email.lower()
        ).all()
        for match in email_matches:
            duplicates.append({
                "contact": match.to_dict(),
                "match_type": "email",
                "match_field": contact.email,
                "confidence": 1.0,
            })

    # 2. Phone match (likely duplicate)
    if contact.phone:
        # Normalize phone for comparison
        phone_digits = re.sub(r'\D', '', contact.phone)
        if len(phone_digits) >= 10:
            phone_matches = db.query(Contact).filter(
                Contact.id != contact.id,
                Contact.phone.isnot(None)
            ).all()
            for match in phone_matches:
                match_digits = re.sub(r'\D', '', match.phone or '')
                if len(match_digits) >= 10 and phone_digits[-10:] == match_digits[-10:]:
                    # Avoid adding if already matched by email
                    if not any(d["contact"]["id"] == match.id for d in duplicates):
                        duplicates.append({
                            "contact": match.to_dict(),
                            "match_type": "phone",
                            "match_field": contact.phone,
                            "confidence": 0.9,
                        })

    # 3. Name + Company fuzzy match
    if contact.name and contact.company:
        name_parts = contact.name.lower().split()
        if len(name_parts) >= 2:
            name_matches = db.query(Contact).filter(
                Contact.id != contact.id,
                func.lower(Contact.company) == contact.company.lower(),
                or_(
                    func.lower(Contact.name).contains(name_parts[0]),
                    func.lower(Contact.name).contains(name_parts[-1])
                )
            ).all()
            for match in name_matches:
                if not any(d["contact"]["id"] == match.id for d in duplicates):
                    duplicates.append({
                        "contact": match.to_dict(),
                        "match_type": "name+company",
                        "match_field": f"{contact.name} @ {contact.company}",
                        "confidence": 0.7,
                    })

    # Sort by confidence
    duplicates.sort(key=lambda x: x["confidence"], reverse=True)

    return duplicates


def scan_all_duplicates(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Scan all contacts for potential duplicates.

    Returns:
        List of duplicate groups
    """
    # Get contacts with email or phone
    contacts = db.query(Contact).filter(
        or_(
            Contact.email.isnot(None),
            Contact.phone.isnot(None)
        )
    ).limit(limit * 2).all()  # Get more to account for duplicates

    seen_pairs = set()
    duplicate_groups = []

    for contact in contacts:
        dupes = find_duplicate_contacts(db, contact=contact)
        for dupe in dupes:
            # Create a sorted pair key to avoid duplicates
            pair_key = tuple(sorted([contact.id, dupe["contact"]["id"]]))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                duplicate_groups.append({
                    "primary": contact.to_dict(),
                    "duplicate": dupe["contact"],
                    "match_type": dupe["match_type"],
                    "confidence": dupe["confidence"],
                })

        if len(duplicate_groups) >= limit:
            break

    return duplicate_groups


def merge_contacts(
    db: Session,
    primary_id: int,
    duplicate_ids: List[int],
    user_email: str = None,
) -> Dict[str, Any]:
    """
    Merge duplicate contacts into a primary contact.

    Args:
        db: Database session
        primary_id: ID of contact to keep
        duplicate_ids: IDs of contacts to merge into primary
        user_email: User performing the merge

    Returns:
        Result of merge operation
    """
    from services.activity_service import ActivityType, log_activity

    primary = db.query(Contact).filter_by(id=primary_id).first()
    if not primary:
        return {"error": "Primary contact not found"}

    duplicates = db.query(Contact).filter(Contact.id.in_(duplicate_ids)).all()
    if not duplicates:
        return {"error": "No duplicate contacts found"}

    merged_count = 0
    for dupe in duplicates:
        # Move activities
        db.query(ActivityLog).filter_by(contact_id=dupe.id).update({
            "contact_id": primary_id
        })

        # Move deal associations
        from models import DealContact
        db.query(DealContact).filter_by(contact_id=dupe.id).update({
            "contact_id": primary_id
        })

        # Fill in missing fields on primary
        if not primary.email and dupe.email:
            primary.email = dupe.email
        if not primary.phone and dupe.phone:
            primary.phone = dupe.phone
        if not primary.title and dupe.title:
            primary.title = dupe.title
        if not primary.address and dupe.address:
            primary.address = dupe.address
        if not primary.company_id and dupe.company_id:
            primary.company_id = dupe.company_id

        # Append notes
        if dupe.notes:
            primary.notes = (primary.notes or "") + f"\n\n[Merged from {dupe.name}]: {dupe.notes}"

        # Delete duplicate
        db.delete(dupe)
        merged_count += 1

    # Log the merge
    log_activity(
        db=db,
        activity_type=ActivityType.NOTE,
        title="Contacts merged",
        description=f"Merged {merged_count} duplicate contact(s) into this record",
        contact_id=primary_id,
        user_email=user_email,
    )

    db.commit()

    return {
        "status": "success",
        "merged_count": merged_count,
        "primary": primary.to_dict(),
    }


# =============================================================================
# Interaction Summarization
# =============================================================================

async def summarize_interactions(
    db: Session,
    contact_id: int = None,
    company_id: int = None,
) -> Dict[str, Any]:
    """
    Use AI to summarize all interactions with a contact or company.

    Args:
        db: Database session
        contact_id: Contact to summarize
        company_id: Or company to summarize

    Returns:
        AI-generated summary
    """
    client = _get_anthropic_client()
    if not client:
        return {"error": "Anthropic not available"}

    # Get activities
    query = db.query(ActivityLog)
    if contact_id:
        query = query.filter_by(contact_id=contact_id)
    elif company_id:
        query = query.filter_by(company_id=company_id)
    else:
        return {"error": "Must specify contact_id or company_id"}

    activities = query.order_by(ActivityLog.occurred_at.desc()).limit(50).all()

    if not activities:
        return {
            "summary": "No interactions recorded yet.",
            "sentiment": "neutral",
            "key_topics": [],
            "next_action": "Schedule initial outreach",
        }

    # Build activity log text
    activity_text = "\n".join([
        f"- [{a.activity_type}] {a.occurred_at.strftime('%Y-%m-%d')}: {a.title or a.description or 'No description'}"
        for a in activities[:30]
    ])

    prompt = f"""Analyze these CRM activities and provide a summary. Return ONLY valid JSON, no markdown.

Activities (most recent first):
{activity_text}

Return JSON with:
{{
    "summary": "2-3 sentence summary of the relationship and recent interactions",
    "sentiment": "positive", "neutral", or "negative" based on interaction patterns,
    "key_topics": ["topic1", "topic2"] - main topics discussed,
    "next_action": "recommended next step",
    "last_meaningful_contact": "YYYY-MM-DD of last substantive interaction",
    "engagement_level": "high", "medium", or "low"
}}
"""

    try:
        response = client.messages.create(
            model=_ENRICHMENT_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()

        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return data
        else:
            return {"error": "Could not parse AI response", "raw": text}

    except Exception as e:
        return {"error": str(e)}
