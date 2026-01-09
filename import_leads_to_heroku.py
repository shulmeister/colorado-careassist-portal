#!/usr/bin/env python3
"""Import Facebook leads directly to Heroku production database"""
import csv
import psycopg2
from datetime import datetime

# Heroku DATABASE_URL
DATABASE_URL = "postgres://ubmvbm9ld42rfd:p104a11c3cbb9336594ad919acf6069e82bcc5208a9fab5c35acefea834480995@cet8r1hlj0mlnt.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dcamd7mcq5dkl3"

def clean_phone(phone):
    """Clean phone number format"""
    if not phone:
        return None
    phone = str(phone).strip()
    phone = phone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
    if phone and not phone.startswith('+'):
        if len(phone) == 10:
            phone = '+1' + phone
        elif len(phone) == 11 and phone.startswith('1'):
            phone = '+' + phone
    return phone if phone else None

def parse_date(date_str):
    """Parse date from CSV format"""
    if not date_str:
        return datetime.now()
    try:
        return datetime.strptime(date_str, '%m/%d/%Y %I:%M%p')
    except:
        try:
            return datetime.strptime(date_str, '%m/%d/%Y %H:%M')
        except:
            return datetime.now()

def import_leads():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    added = 0
    skipped = 0

    with open('/Users/shulmeister/Desktop/leads.csv', 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            name = row.get('Name', '').strip()
            email = row.get('Email', '').strip()
            phone = clean_phone(row.get('Phone', ''))
            created_date = parse_date(row.get('Created', ''))

            if not name or not phone:
                skipped += 1
                continue

            # Check if lead exists
            cur.execute("SELECT id FROM lead WHERE phone = %s", (phone,))
            if cur.fetchone():
                print(f"Skipping duplicate: {name} ({phone})")
                skipped += 1
                continue

            # Insert lead
            cur.execute("""
                INSERT INTO lead (name, email, phone, source, status, priority, notes, created_at, updated_at)
                VALUES (%s, %s, %s, 'facebook_ads', 'new', 'medium', 'Imported from CSV', %s, %s)
            """, (name, email or 'noemail@example.com', phone, created_date, datetime.now()))

            added += 1
            if added <= 10:
                print(f"Added: {name} ({phone})")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n=== IMPORT COMPLETE ===")
    print(f"✓ Added: {added} leads")
    print(f"⊘ Skipped: {skipped}")

if __name__ == "__main__":
    import_leads()
