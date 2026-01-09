"""List companies to spot garbage."""
from database import db_manager
from models import ReferralSource

db = db_manager.SessionLocal()
companies = db.query(ReferralSource).order_by(ReferralSource.created_at.desc()).limit(50).all()
print(f'Last 50 companies:')
for c in companies:
    name = (c.organization or c.name or "")[:35]
    contact = (c.contact_name or "")[:25]
    print(f'  {name:35} | {contact:25}')
db.close()
