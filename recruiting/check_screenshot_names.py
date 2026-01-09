#!/usr/bin/env python3
"""
Check if the names from the screenshot are in the current employee CSV
"""
import csv

# Names from the screenshot
screenshot_names = [
    "Bolick, Katelynn",
    "Cammel, Collette", 
    "Everett, Kayla",
    "Garcia, Victoria",
    "Gebre, SELAMAWIT",
    "Hodge, Serena",
    "Jules, Watcharline",
    "Mohammed, Zulfa",
    "Morris, Maura",
    "Njoki, Lucy",
    "Puerta-Reyes, Victoria",
    "Romero, Melissa",
    "Sandoval, Chenelle",
    "Umutoniwase, Shakira",
    "Warner, Katherine"
]

screenshot_phones = {
    "Jules, Watcharline": "(203) 243-5326",
    "Mohammed, Zulfa": "(303) 564-7161",
    "Puerta-Reyes, Victoria": "(251) 472-6637",
    "Sandoval, Chenelle": "(719) 291-4235",
    "Umutoniwase, Shakira": "(720) 356-8421",
    "Warner, Katherine": "(720) 468-6761",
    "Everett, Kayla": "(719) 639-8970"
}

# Read CSV file
csv_file = '/Users/jasonshulman/Desktop/Current Employees - Sheet 0.csv'
employees = {}

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        last = row.get('Last Name', '').strip()
        first = row.get('First Name', '').strip()
        key = f"{last}, {first}"
        employees[key.lower()] = {
            'name': key,
            'phone': row.get('Mobile Phone', '').strip(),
            'job_title': row.get('Job Title', '').strip()
        }

print("Checking screenshot names against current employees...")
print("=" * 80)

matches = []
for name in screenshot_names:
    lower_name = name.lower()
    if lower_name in employees:
        emp = employees[lower_name]
        matches.append(name)
        phone_match = ""
        if name in screenshot_phones:
            # Clean phones for comparison
            screenshot_phone_clean = ''.join(c for c in screenshot_phones[name] if c.isdigit())
            emp_phone_clean = ''.join(c for c in emp['phone'] if c.isdigit())
            if screenshot_phone_clean == emp_phone_clean:
                phone_match = " ✓ Phone matches!"
            else:
                phone_match = f" ⚠️  Phone different: {emp['phone']}"
        
        print(f"✅ {name:30s} - {emp['job_title']:20s}{phone_match}")
    else:
        print(f"❌ {name:30s} - NOT in current employees")

print("=" * 80)
print(f"\nRESULT: {len(matches)} out of 15 are current employees")
if matches:
    print(f"\nMatches: {', '.join(matches)}")

