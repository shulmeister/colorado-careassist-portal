#!/usr/bin/env python3
"""
Import Companies from Google Sheet (Visits Tab)

Imports company names from the Visits tab of the tracking spreadsheet
and adds them to the referral_sources table if they don't exist.
"""

import sys
import os
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.gigi-env')
except:
    pass

from database import db_manager
from models import ReferralSource
from sqlalchemy import func

# Google Sheets API
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import pickle
except ImportError:
    print("ERROR: google-api-python-client not installed")
    print("Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

SPREADSHEET_ID = '1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg'
RANGE_NAME = 'Visits!A2:Z1000'  # Skip header row


def get_sheets_service():
    """Get authenticated Google Sheets service."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    creds = None
    token_path = Path.home() / '.gigi-creds' / 'token.pickle'

    # Try loading saved credentials
    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If no valid credentials, need to authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("ERROR: No valid credentials found.")
            print("Need to set up Google Sheets API access.")
            return None

    return build('sheets', 'v4', credentials=creds)


def normalize_company_name(name: str) -> str:
    """Normalize company name for comparison."""
    if not name:
        return ""
    return name.strip().lower()


def import_companies_from_sheet(dry_run=False):
    """Import companies from Google Sheet."""

    print("=" * 70)
    print("IMPORT COMPANIES FROM GOOGLE SHEET")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    # Get Google Sheets service
    print("Connecting to Google Sheets...")
    service = get_sheets_service()
    if not service:
        print("ERROR: Could not authenticate with Google Sheets")
        return

    # Read the spreadsheet
    print(f"Reading {SPREADSHEET_ID}...")
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        values = result.get('values', [])
    except Exception as e:
        print(f"ERROR reading spreadsheet: {e}")
        return

    print(f"Found {len(values)} rows in Visits tab\n")

    if not values:
        print("No data found in spreadsheet")
        return

    # Extract company names from first column
    company_names = set()
    for row in values:
        if row and len(row) > 0 and row[0]:
            company_name = row[0].strip()
            if company_name and len(company_name) > 2:
                company_names.add(company_name)

    print(f"Found {len(company_names)} unique company names\n")

    # Connect to database
    with db_manager.SessionLocal() as db:
        # Get existing companies
        existing = db.query(ReferralSource).all()
        existing_names = {normalize_company_name(c.name): c for c in existing}

        print(f"Existing companies in database: {len(existing_names)}\n")

        added = 0
        skipped = 0

        for company_name in sorted(company_names):
            normalized = normalize_company_name(company_name)

            if normalized in existing_names:
                skipped += 1
                continue

            print(f"+ {company_name}")

            if not dry_run:
                new_company = ReferralSource(
                    name=company_name,
                    source_type='referral',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_company)
                added += 1

        if not dry_run and added > 0:
            db.commit()
            print(f"\n✅ Committed {added} new companies to database")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Companies in spreadsheet: {len(company_names)}")
        print(f"Already in database: {skipped}")
        print(f"New companies added: {added}")
        print(f"Final total: {len(existing_names) + added}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Import companies from Google Sheet')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying database')
    args = parser.parse_args()

    import_companies_from_sheet(dry_run=args.dry_run)
