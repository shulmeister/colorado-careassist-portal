#!/usr/bin/env python3
"""
One-time bulk enrichment of referral_sources (companies) with:
  - county (Colorado county name)
  - facility_type_normalized
  - website
  - logo_url (Clearbit URL)

Run on Heroku:
  heroku run python scripts/enrich_companies.py

Uses OpenAI (gpt-4o-mini) first; falls back to Gemini if OpenAI fails.
Requires OPENAI_API_KEY and optionally GEMINI_API_KEY env vars.
"""
import os
import sys
import json
import re
import time
import httpx

# Add project root so we can import models / database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager  # noqa: E402
from models import ReferralSource  # noqa: E402

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PROMPT_TEMPLATE = """You are a helpful assistant that enriches company records.

Given the following company information, determine:
1. company_name: Derive a proper, human-readable company name. If the name is a domain (like "3ahomes.org"), transform it into a proper company name (like "3A Homes"). If the name is already proper, return it as-is. Examples:
   - "3ahomes.org" -> "3A Homes"
   - "abilityconnectioncolorado.org" -> "Ability Connection Colorado"
   - "parallon.com" -> "Parallon"
   - "Denver Health" -> "Denver Health" (already proper)
2. county: The Colorado county where this company is located (e.g., "Denver", "El Paso", "Jefferson"). If unknown, return null.
3. facility_type: A normalized facility type from this list: skilled_nursing, hospital, rehab_hospital, assisted_living, independent_living, memory_care, home_health, hospice, primary_care, outpatient, placement_agency, legal, community_org, insurance, other. Pick the best match.
4. website: The company's website URL (with https://). If you can infer it from email domain or organization name, provide it. If unknown, return null.
5. logo_url: A Clearbit logo URL like https://logo.clearbit.com/<domain> if you determined a website domain. Otherwise null.

Company data:
- Name: {name}
- Organization: {organization}
- Contact Name: {contact_name}
- Email: {email}
- Phone: {phone}
- Address: {address}
- Source Type: {source_type}
- Notes: {notes}

Respond ONLY with valid JSON (no markdown):
{{"company_name": ..., "county": ..., "facility_type": ..., "website": ..., "logo_url": ...}}
"""


def call_openai(prompt: str) -> dict | None:
    if not OPENAI_API_KEY:
        return None
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=30.0,
        )
        if resp.status_code == 429:
            print("OpenAI rate limited, waiting 10s...")
            time.sleep(10)
            return call_openai(prompt)
        if resp.status_code != 200:
            print(f"OpenAI error {resp.status_code}: {resp.text[:200]}")
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        content = re.sub(r"^```json\s*", "", content.strip(), flags=re.IGNORECASE)
        content = re.sub(r"```$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        print(f"OpenAI exception: {e}")
        return None


def call_gemini(prompt: str) -> dict | None:
    if not GEMINI_API_KEY:
        return None
    # Try latest Gemini models (you have enterprise access)
    models = ["gemini-2.0-flash-thinking-exp", "gemini-2.0-flash-exp", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            resp = httpx.post(
                url,
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0}
                },
                timeout=30.0,
            )
            if resp.status_code == 404:
                continue  # model not available, try next
            if resp.status_code != 200:
                print(f"Gemini {model} error {resp.status_code}")
                continue
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())
            return json.loads(text)
        except Exception as e:
            print(f"Gemini {model} exception: {e}")
            continue
    return None


def enrich_company(source: ReferralSource) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        name=source.name or "",
        organization=source.organization or "",
        contact_name=source.contact_name or "",
        email=source.email or "",
        phone=source.phone or "",
        address=source.address or "",
        source_type=source.source_type or "",
        notes=(source.notes or "")[:500],  # truncate long notes
    )
    # Try Gemini first (you have enterprise access)
    result = call_gemini(prompt)
    if not result:
        # Fallback to OpenAI if Gemini fails
        result = call_openai(prompt)
    return result or {}


def main():
    session = db_manager.get_session()
    companies = session.query(ReferralSource).all()
    print(f"Enriching {len(companies)} companies...")

    for i, company in enumerate(companies):
        print(f"[{i+1}/{len(companies)}] {company.name or company.organization}...")
        enriched = enrich_company(company)
        if not enriched:
            print("  -> no enrichment data")
            continue

        if enriched.get("company_name"):
            company.name = enriched["company_name"]
            print(f"  ✓ Name: {enriched['company_name']}")
        if enriched.get("county"):
            company.county = enriched["county"]
        if enriched.get("facility_type"):
            company.facility_type_normalized = enriched["facility_type"]
        if enriched.get("website"):
            company.website = enriched["website"]
        if enriched.get("logo_url"):
            company.logo_url = enriched["logo_url"]

        print(f"  -> county={company.county}, type={company.facility_type_normalized}, website={company.website}")
        session.commit()
        time.sleep(0.5)  # be polite to APIs

    session.close()
    print("Done!")


if __name__ == "__main__":
    main()







