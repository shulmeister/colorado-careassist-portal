#!/usr/bin/env python3
"""
Fix contact tags to match contact_type.
Maps:
  - contact_type="referral" -> tags includes "Referral Source"
  - contact_type="client" -> tags includes "Client"
  - contact_type="prospect" -> tags includes "Prospect"
"""
import json
from database import db_manager
from models import Contact

TAG_MAP = {
    "referral": "Referral Source",
    "client": "Client",
    "prospect": "Prospect",
}

def fix_contact_tags():
    db = db_manager.get_session()

    try:
        contacts = db.query(Contact).all()
        print(f"Found {len(contacts)} contacts to check")

        updated = 0
        for contact in contacts:
            contact_type = (contact.contact_type or "").lower().strip()
            if not contact_type:
                continue

            expected_tag = TAG_MAP.get(contact_type)
            if not expected_tag:
                continue

            # Parse existing tags
            existing_tags = []
            if contact.tags:
                try:
                    existing_tags = json.loads(contact.tags)
                    if not isinstance(existing_tags, list):
                        existing_tags = [str(existing_tags)]
                except json.JSONDecodeError:
                    existing_tags = [t.strip() for t in contact.tags.split(",") if t.strip()]

            # Check if tag already exists
            if expected_tag not in existing_tags:
                existing_tags.insert(0, expected_tag)  # Add at beginning
                contact.tags = json.dumps(existing_tags)
                updated += 1
                print(f"  Updated: {contact.name or contact.email} -> {existing_tags}")

        db.commit()
        print(f"\nUpdated {updated} contacts")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_contact_tags()
