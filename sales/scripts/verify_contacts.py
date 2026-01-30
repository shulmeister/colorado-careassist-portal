#!/usr/bin/env python3
"""Verify contacts from business card scanner are in database"""

import os
import sys
from sqlalchemy import create_engine, text

# Get database URL
db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(db_url)

with engine.connect() as conn:
    # Check total contacts by account_manager
    result = conn.execute(text('''
        SELECT account_manager, COUNT(*) as count
        FROM contacts
        WHERE account_manager IS NOT NULL
        GROUP BY account_manager
        ORDER BY count DESC
    ''')).fetchall()

    print('\n=== CONTACTS BY ACCOUNT MANAGER ===')
    for row in result:
        print(f'{row[0]}: {row[1]} contacts')

    # Check Jen's recent contacts
    result = conn.execute(text('''
        SELECT id, name, company, account_manager, created_at
        FROM contacts
        WHERE account_manager = 'jen@coloradocareassist.com'
        ORDER BY created_at DESC
        LIMIT 20
    ''')).fetchall()

    print(f'\n=== JEN\'S MOST RECENT CONTACTS (showing up to 20) ===')
    if result:
        for row in result:
            print(f'ID: {row[0]}, Name: {row[1]}, Company: {row[2]}, Created: {row[4]}')
    else:
        print('NO CONTACTS FOUND FOR JEN')

    # Check Colorado Springs contacts
    result = conn.execute(text('''
        SELECT COUNT(*) as count
        FROM contacts
        WHERE account_manager = 'cosprings@coloradocareassist.com'
    ''')).fetchone()

    print(f'\n=== COLORADO SPRINGS CONTACTS ===')
    print(f'Total: {result[0]} contacts')

    # Check contacts created in last 24 hours
    result = conn.execute(text('''
        SELECT account_manager, COUNT(*) as count
        FROM contacts
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY account_manager
        ORDER BY count DESC
    ''')).fetchall()

    print('\n=== CONTACTS CREATED IN LAST 24 HOURS ===')
    if result:
        for row in result:
            print(f'{row[0] if row[0] else "NULL"}: {row[1]} contacts')
    else:
        print('NO CONTACTS CREATED IN LAST 24 HOURS')

    # Sample a few recent contacts to see full data
    result = conn.execute(text('''
        SELECT id, name, email, phone, company, title, account_manager, source, created_at
        FROM contacts
        WHERE account_manager IN ('jen@coloradocareassist.com', 'cosprings@coloradocareassist.com')
        ORDER BY created_at DESC
        LIMIT 5
    ''')).fetchall()

    print('\n=== SAMPLE RECENT CONTACTS (Jen + CO Springs) ===')
    if result:
        for row in result:
            print(f'ID: {row[0]}')
            print(f'  Name: {row[1]}')
            print(f'  Email: {row[2]}')
            print(f'  Phone: {row[3]}')
            print(f'  Company: {row[4]}')
            print(f'  Title: {row[5]}')
            print(f'  Account Manager: {row[6]}')
            print(f'  Source: {row[7]}')
            print(f'  Created: {row[8]}')
            print()
    else:
        print('NO CONTACTS FOUND')

print('\n=== VERIFICATION COMPLETE ===')
