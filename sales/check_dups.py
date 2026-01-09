from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    total_visits = conn.execute(text('SELECT COUNT(*) FROM visits')).scalar()
    dup_visits = conn.execute(text('''
        SELECT COUNT(*) FROM (
            SELECT DATE(visit_date), LOWER(business_name), stop_number
            FROM visits 
            WHERE business_name IS NOT NULL
            GROUP BY DATE(visit_date), LOWER(business_name), stop_number 
            HAVING COUNT(*) > 1
        ) d
    ''')).scalar()
    
    total_contacts = conn.execute(text('SELECT COUNT(*) FROM contacts')).scalar()
    dup_contacts = conn.execute(text('''
        SELECT COUNT(*) FROM (
            SELECT LOWER(email)
            FROM contacts 
            WHERE email IS NOT NULL AND email != ''
            GROUP BY LOWER(email) 
            HAVING COUNT(*) > 1
        ) d
    ''')).scalar()
    
    total_companies = conn.execute(text('SELECT COUNT(*) FROM referral_sources')).scalar()

print('='*50)
print('PRODUCTION DATABASE STATUS')
print('='*50)
print(f'Visits:    {total_visits} total, {dup_visits} duplicate groups')
print(f'Contacts:  {total_contacts} total, {dup_contacts} duplicate email groups')  
print(f'Companies: {total_companies} total')
print('='*50)
