#!/usr/bin/env python3
"""
Check how many current employees are in the recruiter dashboard as leads
"""
import csv
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Connect to database
engine = create_engine(database_url)

# Read CSV file
csv_file = '/Users/jasonshulman/Desktop/Current Employees - Sheet 0.csv'
employees = []

print("Reading employee CSV file...")
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        first_name = row.get('First Name', '').strip()
        last_name = row.get('Last Name', '').strip()
        full_name = f"{first_name} {last_name}".strip()
        mobile = row.get('Mobile Phone', '').strip()
        email = row.get('Email Address', '').strip()
        job_title = row.get('Job Title', '').strip()
        
        # Only include caregivers, not admin staff
        if 'caregiver' in job_title.lower() or 'pcw' in job_title.lower():
            employees.append({
                'name': full_name,
                'first_name': first_name,
                'last_name': last_name,
                'phone': mobile,
                'email': email,
                'job_title': job_title
            })

print(f"Found {len(employees)} caregivers in employee file\n")

# Get all leads from database
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, name, phone, email FROM leads"))
    leads = [dict(row._mapping) for row in result]

print(f"Found {len(leads)} leads in recruiter dashboard\n")

# Compare and find matches
matches = []
for emp in employees:
    for lead in leads:
        # Clean phone numbers for comparison
        emp_phone = ''.join(c for c in emp['phone'] if c.isdigit())[-10:] if emp['phone'] else ''
        lead_phone = ''.join(c for c in (lead['phone'] or '') if c.isdigit())[-10:] if lead['phone'] else ''
        
        # Check for match by name, phone, or email
        name_match = emp['name'].lower() == (lead['name'] or '').lower()
        phone_match = emp_phone and lead_phone and emp_phone == lead_phone
        email_match = emp['email'].lower() == (lead['email'] or '').lower() if emp['email'] and lead['email'] else False
        
        if name_match or phone_match or email_match:
            matches.append({
                'employee_name': emp['name'],
                'employee_phone': emp['phone'],
                'employee_email': emp['email'],
                'lead_name': lead['name'],
                'lead_phone': lead['phone'],
                'lead_email': lead['email'],
                'match_type': 'name' if name_match else ('phone' if phone_match else 'email')
            })
            break  # Found a match, move to next employee

print("=" * 80)
print(f"RESULTS: {len(matches)} out of {len(employees)} caregivers are in the recruiter dashboard")
print(f"That's {len(matches)/len(employees)*100:.1f}% of your current caregiver workforce")
print("=" * 80)

if matches:
    print("\nMatched employees:")
    print("-" * 80)
    for i, match in enumerate(matches, 1):
        print(f"{i}. {match['employee_name']}")
        print(f"   Employee: {match['employee_phone']} | {match['employee_email']}")
        print(f"   In Dashboard: {match['lead_name']} ({match['match_type']} match)")
        print()

print("\nNOT in recruiter dashboard:")
print("-" * 80)
matched_names = {m['employee_name'] for m in matches}
not_in_dashboard = [emp for emp in employees if emp['name'] not in matched_names]
for i, emp in enumerate(not_in_dashboard, 1):
    print(f"{i}. {emp['name']} - {emp['phone']} - {emp['email']}")

