#!/usr/bin/env python3
"""Add Meg user to the database"""
from app import app, db, User

with app.app_context():
    # Check if Meg already exists
    existing = User.query.filter_by(email='meg@coloradocareassist.com').first()
    if existing:
        print('Meg already exists in database')
    else:
        # Create Meg user
        meg = User(name='Meg', email='meg@coloradocareassist.com', is_active=True)
        db.session.add(meg)
        db.session.commit()
        print(f'Successfully added Meg (ID: {meg.id}) to database')
    
    # List all users
    users = User.query.filter_by(is_active=True).all()
    print(f'\nAll active users:')
    for u in users:
        print(f'  - {u.name} ({u.email}) - ID: {u.id}')

