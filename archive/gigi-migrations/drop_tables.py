#!/usr/bin/env python3
"""Drop and recreate Gigi tables with correct schema."""

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

print("Dropping existing Gigi tables...")
with engine.connect() as conn:
    conn.execute(text('DROP TABLE IF EXISTS gigi_caregivers CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_clients CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_shifts CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_unavailability CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_sync_logs CASCADE'))
    conn.commit()

print("Tables dropped successfully!")
print("Now run: python gigi/migrate_to_db.py")
