"""Fix 'Unnamed contact' entries by extracting names from their emails."""
import re
from database import db_manager
from models import Contact

def extract_name_from_email(email: str) -> tuple:
    """Extract first and last name from email prefix."""
    if not email or "@" not in email:
        return None, None
    
    email_prefix = email.split("@")[0].lower()
    parts = re.split(r'[._]', email_prefix)
    
    first_name = None
    last_name = None
    
    if len(parts) >= 2:
        potential_first = parts[0].capitalize()
        potential_last = parts[-1].capitalize()
        
        if potential_first.isalpha() and 2 <= len(potential_first) <= 15:
            first_name = potential_first
        if potential_last.isalpha() and 2 <= len(potential_last) <= 20:
            last_name = potential_last
    
    return first_name, last_name

def main():
    db = db_manager.SessionLocal()
    try:
        # Find contacts with "Unnamed" or missing first name but have email
        unnamed = db.query(Contact).filter(
            (Contact.first_name == "Unnamed") | 
            (Contact.first_name == None) |
            (Contact.first_name == "")
        ).filter(Contact.email.isnot(None)).all()
        
        print(f"Found {len(unnamed)} contacts with missing names but have emails")
        print()
        
        fixed = 0
        for c in unnamed:
            first, last = extract_name_from_email(c.email)
            if first or last:
                old_name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                new_name = f"{first or ''} {last or ''}".strip()
                
                if first and (not c.first_name or c.first_name == "Unnamed"):
                    c.first_name = first
                if last and not c.last_name:
                    c.last_name = last
                c.name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                
                print(f"  Fixed: '{old_name}' -> '{c.name}' (from {c.email})")
                fixed += 1
        
        if fixed > 0:
            db.commit()
            print(f"\nFixed {fixed} contacts!")
        else:
            print("No contacts needed fixing.")
    finally:
        db.close()

if __name__ == "__main__":
    main()

