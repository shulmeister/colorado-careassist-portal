#!/usr/bin/env python3
from database import db_manager
from models import Contact
db = db_manager.get_session()
clients = db.query(Contact).filter(Contact.contact_type == 'client').all()
print(f'Total clients: {len(clients)}')
for c in clients[:15]:
    print(f'  - {c.name}: tags={c.tags}')
db.close()
