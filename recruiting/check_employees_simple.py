#!/usr/bin/env python3
"""
Simple check - just count caregivers in CSV and show who they are
"""
import csv

# Read CSV file
csv_file = '/Users/jasonshulman/Desktop/Current Employees - Sheet 0.csv'
caregivers = []

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
            caregivers.append({
                'name': full_name,
                'phone': mobile,
                'email': email
            })

print(f"\nTotal caregivers in employee file: {len(caregivers)}")
print("\nCaregiver list (will search in database):")
print("=" * 80)

# Output names and phones for manual checking
for i, cg in enumerate(caregivers, 1):
    print(f"{i:2d}. {cg['name']:30s} | {cg['phone']:15s} | {cg['email']}")

