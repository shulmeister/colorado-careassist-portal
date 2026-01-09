"""Find specific garbage contacts."""
from database import db_manager
from models import Contact
from sqlalchemy import or_

db = db_manager.SessionLocal()
contacts = db.query(Contact).filter(
    or_(
        Contact.first_name.ilike('%Tss%'),
        Contact.first_name.ilike('%Www%'),
        Contact.first_name.ilike('Sal Ere%'),
        Contact.first_name == 'Unnamed',
        Contact.last_name.ilike('%Sss%'),
        Contact.first_name.ilike('He Tul%'),
    )
).all()
print(f'Found {len(contacts)} suspicious contacts:')
for c in contacts:
    print(f'  ID {c.id}: {c.first_name} {c.last_name} | {c.company} | {c.email}')
db.close()
