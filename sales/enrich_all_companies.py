#!/usr/bin/env python3
"""
Enrich all companies with OpenAI to add logos, websites, county, facility type
"""
import os
import sys
import time
import json
import re
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import ReferralSource

# Database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')

ENRICH_PROMPT_TEMPLATE = """You are a helpful assistant that enriches company records.
Given a company name, provide:
1. county: The Colorado county where this company is likely located (if it's in Colorado). Otherwise null.
2. facility_type: One of: "skilled_nursing", "assisted_living", "home_health", "hospice", "hospital", "other", or null if unknown.
3. website: The company's primary website URL (https://...). Otherwise null.
4. logo_url: A Clearbit logo URL like https://logo.clearbit.com/<domain> if you determined a website domain. Otherwise null.

Company Name: {company_name}

Respond ONLY with valid JSON (no markdown fences):
{{"county": ..., "facility_type": ..., "website": ..., "logo_url": ...}}
"""

def call_openai_enrich(company_name: str) -> dict:
    """Call OpenAI to enrich company data"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return {}

    prompt = ENRICH_PROMPT_TEMPLATE.format(company_name=company_name)

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=30.0,
        )
        if not resp.is_success:
            print(f"  OpenAI error {resp.status_code}: {resp.text[:200]}")
            return {}

        content = resp.json()["choices"][0]["message"]["content"]
        # Remove markdown fences if present
        content = re.sub(r"^```json\s*", "", content.strip(), flags=re.IGNORECASE)
        content = re.sub(r"```$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        print(f"  OpenAI exception: {e}")
        return {}

def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get all companies that need enrichment
    companies = session.query(ReferralSource).filter(
        (ReferralSource.logo_url == None) | (ReferralSource.website == None)
    ).all()

    print(f"\n=== Starting enrichment of {len(companies)} companies ===\n")

    enriched_count = 0
    failed_count = 0

    for i, company in enumerate(companies, 1):
        company_name = company.name or company.organization or "Unknown"
        print(f"[{i}/{len(companies)}] Enriching: {company_name}")

        enriched = call_openai_enrich(company_name)

        if enriched:
            # Update company with enriched data
            if enriched.get("county"):
                company.county = enriched["county"]
                print(f"  ✓ County: {enriched['county']}")

            if enriched.get("facility_type"):
                company.facility_type_normalized = enriched["facility_type"]
                print(f"  ✓ Facility type: {enriched['facility_type']}")

            if enriched.get("website"):
                company.website = enriched["website"]
                print(f"  ✓ Website: {enriched['website']}")

            if enriched.get("logo_url"):
                company.logo_url = enriched["logo_url"]
                print(f"  ✓ Logo: {enriched['logo_url']}")

            session.commit()
            enriched_count += 1
        else:
            print(f"  ✗ Failed to enrich")
            failed_count += 1

        # Rate limit to avoid overwhelming OpenAI
        time.sleep(0.5)

    session.close()

    print(f"\n=== ENRICHMENT COMPLETE ===")
    print(f"✓ Successfully enriched: {enriched_count}")
    print(f"✗ Failed: {failed_count}")
    print(f"Total processed: {len(companies)}")

if __name__ == "__main__":
    main()
