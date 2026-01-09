#!/usr/bin/env python3
"""Mark matching leads as hired based on current caregiver list"""
from app import app, db, Lead

# Current caregivers list
current_caregivers = [
    "Lieljuris Karen",
    "Knoefler Jean", 
    "Wambugu Zipporah",
    "Sinatra Kristin",
    "Pointe Cynthia",
    "Dorrance Serenity",
    "Jeffers Jennifer",
    "Truesdell Courtney",
    "Oliver Shaunte",
    "Sandoval Sheila",
    "Boone Andrea",
    "Kvapil Gloria",
    "Stearns Kirah",
    "Aldan-Muna Diana",
    "Muna Dennis",
    "Gutierrez Halie",
    "Paillette Heather",
    "Seaman Virginia",
    "Grant-Rose Ann Marie",
    "Ramasamy Kavitha",
    "PRATOOMCHAI SIRIPRAPA",
    "Widger Stacey",
    "Burt Lakiah",
    "Yu Karen",
    "Pierson Aliyah",
    "Gourley Beth",
    "Hairfield Addison",
    "Ritchie Tamara",
    "Wood Destine",
    "keys Kandis",
    "Edwards Brandy",
    "Damron Ladonna",
    "Trujillo Sarah",
    "Dickerson Juniper",
    "Marable Lola",
    "Wambui Racheal",
    "Ricketts Andrea",
    "Martin Beth",
    "Atteberry Angela"
]

def normalize_name(name):
    """Normalize name for comparison"""
    return name.lower().strip().replace(" ", "").replace("-", "").replace("'", "").replace('"', "")

def mark_hired_caregivers():
    with app.app_context():
        # Get all leads
        leads = Lead.query.all()
        
        # Create normalized caregiver names for comparison
        normalized_caregivers = {}
        for caregiver in current_caregivers:
            normalized = normalize_name(caregiver)
            normalized_caregivers[normalized] = caregiver
        
        matches_found = 0
        
        print("Searching for matches between leads and current caregivers...")
        print(f"Total caregivers to check: {len(current_caregivers)}")
        print(f"Total leads to check: {len(leads)}")
        print()
        
        for lead in leads:
            lead_normalized = normalize_name(lead.name)
            
            # Check for exact matches
            if lead_normalized in normalized_caregivers:
                print(f"✅ EXACT MATCH: '{lead.name}' matches caregiver '{normalized_caregivers[lead_normalized]}'")
                lead.status = 'hired'
                lead.notes = f"{lead.notes}\n\nMARKED AS HIRED: Matches current caregiver list".strip()
                matches_found += 1
                continue
            
            # Check for reversed name matches (Last First vs First Last)
            lead_parts = lead.name.split()
            if len(lead_parts) >= 2:
                first_name = normalize_name(lead_parts[0])
                last_name = normalize_name(lead_parts[-1])
                
                # Try reversed order
                reversed_name = f"{last_name}{first_name}"
                
                for caregiver_normalized, caregiver_original in normalized_caregivers.items():
                    if reversed_name == caregiver_normalized:
                        print(f"✅ REVERSED MATCH: '{lead.name}' matches caregiver '{caregiver_original}'")
                        lead.status = 'hired'
                        lead.notes = f"{lead.notes}\n\nMARKED AS HIRED: Matches current caregiver list (reversed name)".strip()
                        matches_found += 1
                        break
                
                # Check for partial matches with high confidence
                for caregiver_normalized, caregiver_original in normalized_caregivers.items():
                    # Check if both first and last names match (in any order)
                    caregiver_parts = caregiver_original.split()
                    if len(caregiver_parts) >= 2:
                        caregiver_first = normalize_name(caregiver_parts[0])
                        caregiver_last = normalize_name(caregiver_parts[-1])
                        
                        # High confidence match: both names present in both
                        if ((first_name == caregiver_first and last_name == caregiver_last) or
                            (first_name == caregiver_last and last_name == caregiver_first)):
                            print(f"✅ HIGH CONFIDENCE MATCH: '{lead.name}' matches caregiver '{caregiver_original}'")
                            lead.status = 'hired'
                            lead.notes = f"{lead.notes}\n\nMARKED AS HIRED: Matches current caregiver list (high confidence)".strip()
                            matches_found += 1
                            break
        
        # Commit changes
        db.session.commit()
        
        print(f"\n🎉 Successfully marked {matches_found} leads as HIRED!")
        
        # Show updated statistics
        hired_count = Lead.query.filter_by(status='hired').count()
        print(f"Total hired leads now: {hired_count}")

if __name__ == "__main__":
    mark_hired_caregivers()
