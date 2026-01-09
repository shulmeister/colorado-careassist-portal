"""List all contacts to spot garbage."""
from database import db_manager
from models import Contact

db = db_manager.SessionLocal()
contacts = db.query(Contact).order_by(Contact.created_at.desc()).limit(50).all()
print(f'Last 50 contacts:')
for c in contacts:
    name = f"{c.first_name or ''} {c.last_name or ''}".strip()
    print(f'  {name[:30]:30} | {(c.company or "")[:25]:25} | {c.email or ""}')
db.close()
