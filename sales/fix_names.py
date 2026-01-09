"""Fix contacts with generic emails to use company name as first/last name"""
from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)
engine = create_engine(DATABASE_URL)

GENERIC_PREFIXES = {
    'info', 'team', 'admin', 'contact', 'hello', 'support', 'sales',
    'office', 'help', 'service', 'marketing', 'billing', 'hr',
    'careers', 'jobs', 'press', 'media', 'general', 'mail', 'enquiries',
    'inquiries', 'reception', 'feedback', 'customerservice'
}

with engine.connect() as conn:
    # Get contacts with no first_name
    result = conn.execute(text('''
        SELECT id, email, first_name, last_name, name, company 
        FROM contacts 
        WHERE (first_name IS NULL OR first_name = '')
        AND email IS NOT NULL
    '''))
    
    rows = result.fetchall()
    print(f"Found {len(rows)} contacts without first_name")
    
    fixed = 0
    for row in rows:
        id, email, first_name, last_name, name, company = row
        
        if not email:
            continue
            
        email_prefix = email.split('@')[0].lower() if '@' in email else ''
        is_generic = email_prefix in GENERIC_PREFIXES
        
        # Only fix if generic email or truly no name
        if is_generic or (not first_name and not last_name):
            new_first = None
            new_last = None
            
            if company:
                words = company.split()
                if len(words) >= 2:
                    new_first = words[0]
                    new_last = ' '.join(words[1:])
                elif len(words) == 1:
                    new_first = words[0]
                    new_last = ''
            
            if new_first:
                new_name = f"{new_first} {new_last}".strip() if new_last else new_first
                conn.execute(text('''
                    UPDATE contacts 
                    SET first_name = :first, last_name = :last, name = :name
                    WHERE id = :id
                '''), {"first": new_first, "last": new_last, "name": new_name, "id": id})
                print(f"  Fixed: {email} → {new_first} {new_last} (from company: {company})")
                fixed += 1
    
    conn.commit()
    print(f"\nFixed {fixed} contacts")
