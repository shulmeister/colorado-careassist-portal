#!/usr/bin/env python3
"""Test the Gemini business name lookup for addresses"""
from ai_document_parser import ai_parser

# Test addresses from the screenshot (typical Denver healthcare locations)
test_addresses = [
    ("3461 Ringsby Ct", "Denver"),
    ("3461 Ringsby Ct, Ste 350", "Denver"),
    ("4045 Pecos St, Ste 150", "Denver"),
    ("3210 Meade St", "Denver"),
    ("2130 Arapahoe St", "Denver"),
    ("1760 N Gaylord St", "Denver"),
    ("1400 Jackson St", "Denver"),
    ("4700 E Hale Pkwy", "Denver"),
    ("3300 E First Ave, Ste 280", "Denver"),
    ("44 Cook St, Ste 100", "Denver"),
    ("501 S Cherry St", "Glendale"),
]

print("Testing Gemini business name lookup...")
print("=" * 60)

for address, city in test_addresses:
    result = ai_parser.lookup_business_at_address(address, city)
    status = "✓" if result else "✗"
    print(f"{status} {address}, {city}")
    print(f"   → {result or 'No business identified'}")
    print()

print("=" * 60)
print("Done!")
