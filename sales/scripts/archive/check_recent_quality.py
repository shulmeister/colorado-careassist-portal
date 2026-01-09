from database import db_manager
from models import Contact
from datetime import datetime, timedelta

db = db_manager.SessionLocal()
one_hour_ago = datetime.utcnow() - timedelta(hours=1)
recent = db.query(Contact).filter(Contact.updated_at >= one_hour_ago).order_by(Contact.updated_at.desc()).limit(25).all()
print(f'=== {len(recent)} contacts updated in past hour ===')
print()
for c in recent:
    name = f'{c.first_name or ""} {c.last_name or ""}'.strip()
    company = (c.company or '')[:28]
    email = (c.email or '')[:35]
    print(f'{name[:22]:22} | {company:28} | {email}')
db.close()
