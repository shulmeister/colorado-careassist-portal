from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print('=== Contact Types in Dashboard ===')
    result = conn.execute(text('''
        SELECT contact_type, COUNT(*) as count 
        FROM contacts 
        GROUP BY contact_type 
        ORDER BY count DESC
    '''))
    for row in result:
        print(f'  {row[0] or "(none)"}: {row[1]}')
    
    print()
    print('=== Contact Status in Dashboard ===')
    result = conn.execute(text('''
        SELECT status, COUNT(*) as count 
        FROM contacts 
        GROUP BY status 
        ORDER BY count DESC
    '''))
    for row in result:
        print(f'  {row[0] or "(none)"}: {row[1]}')
    
    print()
    print('=== Sample Referral Source Contacts ===')
    result = conn.execute(text('''
        SELECT name, email, company, contact_type 
        FROM contacts 
        WHERE contact_type = 'referral'
        LIMIT 5
    '''))
    for row in result:
        print(f'  {row[0]} | {row[1]} | {row[2]} | {row[3]}')
    
    print()
    print('=== Sample Client Contacts ===')
    result = conn.execute(text('''
        SELECT name, email, company, contact_type 
        FROM contacts 
        WHERE contact_type = 'client'
        LIMIT 5
    '''))
    for row in result:
        print(f'  {row[0]} | {row[1]} | {row[2]} | {row[3]}')
