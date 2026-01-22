#!/usr/bin/env python3
"""Reset Gigi tables with correct schema using raw SQL."""

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

print("=== RESETTING GIGI DATABASE SCHEMA ===")

with engine.connect() as conn:
    # Drop all Gigi tables
    print("\n1. Dropping existing tables...")
    conn.execute(text('DROP TABLE IF EXISTS gigi_sync_logs CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_unavailability CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_shifts CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_clients CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS gigi_caregivers CASCADE'))
    conn.commit()
    print("   Tables dropped.")

    # Create tables with explicit schema
    print("\n2. Creating gigi_caregivers table...")
    conn.execute(text('''
        CREATE TABLE gigi_caregivers (
            id SERIAL PRIMARY KEY,
            phone VARCHAR(10) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'active',
            location VARCHAR(100),
            city VARCHAR(100),
            email VARCHAR(255),
            can_sms BOOLEAN DEFAULT TRUE,
            wellsky_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    conn.execute(text('CREATE INDEX idx_gigi_caregivers_phone ON gigi_caregivers(phone)'))
    conn.commit()
    print("   Created gigi_caregivers.")

    print("\n3. Creating gigi_clients table...")
    conn.execute(text('''
        CREATE TABLE gigi_clients (
            id SERIAL PRIMARY KEY,
            phone VARCHAR(10) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'active',
            location VARCHAR(100),
            address TEXT,
            primary_caregiver VARCHAR(255),
            wellsky_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    conn.execute(text('CREATE INDEX idx_gigi_clients_phone ON gigi_clients(phone)'))
    conn.commit()
    print("   Created gigi_clients.")

    print("\n4. Creating gigi_shifts table...")
    conn.execute(text('''
        CREATE TABLE gigi_shifts (
            id SERIAL PRIMARY KEY,
            caregiver_name VARCHAR(255) NOT NULL,
            caregiver_phone VARCHAR(10),
            client_name VARCHAR(255) NOT NULL,
            client_phone VARCHAR(10),
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status VARCHAR(50) DEFAULT 'Scheduled',
            location VARCHAR(255),
            pay_amount FLOAT,
            pay_method VARCHAR(50),
            wellsky_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    conn.execute(text('CREATE INDEX idx_gigi_shifts_caregiver ON gigi_shifts(caregiver_name)'))
    conn.execute(text('CREATE INDEX idx_gigi_shifts_client ON gigi_shifts(client_name)'))
    conn.execute(text('CREATE INDEX idx_gigi_shifts_start ON gigi_shifts(start_time)'))
    conn.commit()
    print("   Created gigi_shifts.")

    print("\n5. Creating gigi_unavailability table...")
    conn.execute(text('''
        CREATE TABLE gigi_unavailability (
            id SERIAL PRIMARY KEY,
            caregiver_name VARCHAR(255) NOT NULL,
            reason VARCHAR(100) DEFAULT 'Unavailable',
            description TEXT,
            is_recurring BOOLEAN DEFAULT FALSE,
            recurring_days JSONB,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            all_day BOOLEAN DEFAULT TRUE,
            start_time VARCHAR(10),
            end_time VARCHAR(10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    conn.execute(text('CREATE INDEX idx_gigi_unavailability_caregiver ON gigi_unavailability(caregiver_name)'))
    conn.commit()
    print("   Created gigi_unavailability.")

    print("\n6. Creating gigi_sync_logs table...")
    conn.execute(text('''
        CREATE TABLE gigi_sync_logs (
            id SERIAL PRIMARY KEY,
            sync_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            caregivers_synced INTEGER DEFAULT 0,
            clients_synced INTEGER DEFAULT 0,
            shifts_synced INTEGER DEFAULT 0,
            unavailability_synced INTEGER DEFAULT 0,
            error_message TEXT,
            duration_seconds FLOAT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    '''))
    conn.commit()
    print("   Created gigi_sync_logs.")

print("\n=== SCHEMA RESET COMPLETE ===")
print("\nNow run: python gigi/migrate_to_db.py")
