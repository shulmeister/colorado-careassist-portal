"""Find and fix garbage contacts from bad OCR scans."""
import os
import sys
import re

# Set up the environment
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))

from database import db_manager
from models import Contact, ReferralSource
from sqlalchemy.orm import Session

def looks_like_garbage(text: str) -> bool:
    """Check if text looks like OCR garbage."""
    if not text or len(text) < 2:
        return False
    # Repeated characters
    if len(set(text.lower())) < len(text) / 3:
        return True
    # Too many consonants in a row
    consonants = "bcdfghjklmnpqrstvwxyz"
    max_consonants = 0
    current = 0
    for c in text.lower():
        if c in consonants:
            current += 1
            max_consonants = max(max_consonants, current)
        else:
            current = 0
    if max_consonants >= 4:
        return True
    # Nonsense patterns
    garbage_patterns = ["www ", "xxx", "yyy", "zzz", "sss", "tss"]
    for pattern in garbage_patterns:
        if pattern in text.lower():
            return True
    return False

def main():
    db = db_manager.SessionLocal()
    try:
        # Find garbage contacts
        all_contacts = db.query(Contact).filter(
            Contact.first_name.isnot(None)
        ).all()
        
        garbage_contacts = []
        for c in all_contacts:
            name = f"{c.first_name or ''} {c.last_name or ''}".strip()
            if looks_like_garbage(c.first_name or "") or looks_like_garbage(c.last_name or ""):
                garbage_contacts.append(c)
                print(f"  GARBAGE: {name} | {c.company} | {c.email}")
        
        print(f"\nFound {len(garbage_contacts)} garbage contacts out of {len(all_contacts)} total")
        
        # Also find "Unnamed contact" entries
        unnamed = db.query(Contact).filter(
            Contact.first_name == "Unnamed"
        ).all()
        print(f"Found {len(unnamed)} 'Unnamed contact' entries")
        
        if garbage_contacts or unnamed:
            print("\nTo delete these, run with --delete flag")
            if len(sys.argv) > 1 and sys.argv[1] == "--delete":
                for c in garbage_contacts + unnamed:
                    print(f"  Deleting: {c.first_name} {c.last_name}")
                    db.delete(c)
                db.commit()
                print(f"Deleted {len(garbage_contacts) + len(unnamed)} bad contacts")
    finally:
        db.close()

if __name__ == "__main__":
    main()
