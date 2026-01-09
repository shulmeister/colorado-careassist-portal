"""Check if Nov 25 visits exist in database"""
from app import get_db
from models import Visit
from datetime import datetime

db = next(get_db())

# Count all visits
total_visits = db.query(Visit).count()
print(f"Total visits in database: {total_visits}")

# Get Nov 25 visits
nov25_visits = db.query(Visit).filter(
    Visit.visit_date >= datetime(2025, 11, 25),
    Visit.visit_date < datetime(2025, 11, 26)
).all()

print(f"\nNov 25 visits found: {len(nov25_visits)}")
for visit in nov25_visits:
    print(f"  - {visit.id}: {visit.business_name} at {visit.visit_date} (user: {visit.user_email})")

# Get most recent visits
recent = db.query(Visit).order_by(Visit.created_at.desc()).limit(5).all()
print(f"\n5 Most recently created visits:")
for visit in recent:
    print(f"  - {visit.id}: {visit.business_name} on {visit.visit_date} (created: {visit.created_at}, user: {visit.user_email})")

