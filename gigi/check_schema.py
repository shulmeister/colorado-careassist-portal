#!/usr/bin/env python3
"""Check the current Gigi database schema."""

import os
from sqlalchemy import create_engine, text

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("ERROR: DATABASE_URL not set")
    exit(1)

if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg2://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)

engine = create_engine(database_url)

print("=== GIGI DATABASE SCHEMA CHECK ===\n")

with engine.connect() as conn:
    # Check gigi_caregivers
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'gigi_caregivers'
        ORDER BY ordinal_position
    """))
    print("gigi_caregivers:")
    rows = list(result)
    if not rows:
        print("  TABLE DOES NOT EXIST!")
    for row in rows:
        print(f"  {row[0]}: {row[1]}")

    print()

    # Check gigi_clients
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'gigi_clients'
        ORDER BY ordinal_position
    """))
    print("gigi_clients:")
    rows = list(result)
    if not rows:
        print("  TABLE DOES NOT EXIST!")
    for row in rows:
        print(f"  {row[0]}: {row[1]}")

    print()

    # Check gigi_shifts
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'gigi_shifts'
        ORDER BY ordinal_position
    """))
    print("gigi_shifts:")
    rows = list(result)
    if not rows:
        print("  TABLE DOES NOT EXIST!")
    for row in rows:
        print(f"  {row[0]}: {row[1]}")

print("\n=== DONE ===")
