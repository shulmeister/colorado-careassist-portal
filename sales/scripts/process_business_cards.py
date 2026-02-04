#!/usr/bin/env python3
"""
Bulk process business cards from a Google Drive folder.
Run on Mac Mini (Local): mac-mini run python3 scripts/process_business_cards.py <folder_url>

Uses Gemini Vision (faster, no rate limits) with OpenAI fallback.
"""
import sys
import os
import re
import json
import base64
import time
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager
from models import Contact, ReferralSource
from google_drive_service import GoogleDriveService

BUSINESS_CARD_PROMPT = """You are extracting contact information from a business card image.

Extract ALL available information and return ONLY valid JSON (no markdown):
{
  "first_name": "...",
  "last_name": "...",
  "title": "...",
  "company": "...",
  "email": "...",
  "phone": "...",
  "address": "...",
  "website": "...",
  "notes": "..."
}

If a field is not visible/available, set it to null. For phone, include area code."""


def extract_with_gemini(content: bytes, filename: str) -> dict | None:
    """Extract business card data using Gemini Vision."""
    import httpx
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        return None
    
    b64 = base64.b64encode(content).decode("utf-8")
    mime = "image/jpeg"
    if filename.lower().endswith(".png"):
        mime = "image/png"
    elif filename.lower().endswith(".heic"):
        mime = "image/heic"
    
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [
                        {"text": BUSINESS_CARD_PROMPT},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }]
            },
            timeout=30.0,
        )
        
        if resp.status_code != 200:
            print(f"  Gemini error: {resp.status_code}")
            return None
        
        data = resp.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        print(f"  Gemini extraction failed: {e}")
        return None


def process_folder(folder_url: str, assign_to: str = "jacob@coloradocareassist.com"):
    """Process all business card images in a folder."""
    
    drive = GoogleDriveService()
    if not drive.enabled:
        print("ERROR: Google Drive API not configured. Set GOOGLE_SERVICE_ACCOUNT_KEY.")
        return
    
    print(f"\n📁 Listing files in folder...")
    files = drive.list_files_in_folder(folder_url, image_only=True)
    
    if not files:
        print("ERROR: No image files found. Make sure the folder is shared with the service account.")
        return
    
    print(f"Found {len(files)} images to process\n")
    
    db = db_manager.get_session()
    
    stats = {
        "processed": 0,
        "contacts_created": 0,
        "contacts_updated": 0,
        "companies_created": 0,
        "companies_linked": 0,
        "errors": 0,
    }
    
    try:
        for i, file_info in enumerate(files, 1):
            file_id = file_info.get("id")
            file_name = file_info.get("name", "unknown")
            
            print(f"[{i}/{len(files)}] {file_name}...", end=" ", flush=True)
            
            # Download
            result = drive.download_file_by_id(file_id)
            if not result:
                print("❌ download failed")
                stats["errors"] += 1
                continue
            
            content, _, _ = result
            
            # Extract with Gemini
            card = extract_with_gemini(content, file_name)
            if not card:
                print("❌ extraction failed")
                stats["errors"] += 1
                continue
            
            first_name = (card.get("first_name") or "").strip()
            last_name = (card.get("last_name") or "").strip()
            company_name = (card.get("company") or "").strip()
            email = (card.get("email") or "").strip()
            phone = (card.get("phone") or "").strip()
            title = (card.get("title") or "").strip()
            address = (card.get("address") or "").strip()
            website = (card.get("website") or "").strip()
            
            if not first_name and not last_name and not company_name:
                print("❌ no data extracted")
                stats["errors"] += 1
                continue
            
            stats["processed"] += 1
            
            # Find or create company
            company_id = None
            if company_name:
                existing = db.query(ReferralSource).filter(
                    ReferralSource.organization.ilike(company_name)
                ).first()
                if existing:
                    company_id = existing.id
                    stats["companies_linked"] += 1
                else:
                    new_company = ReferralSource(
                        name=f"{first_name} {last_name}".strip() or company_name,
                        organization=company_name,
                        contact_name=f"{first_name} {last_name}".strip() if first_name or last_name else None,
                        email=email,
                        phone=phone,
                        address=address,
                        source_type="Healthcare Facility",
                        status="incoming",
                    )
                    db.add(new_company)
                    db.flush()
                    company_id = new_company.id
                    stats["companies_created"] += 1
            
            # Find or create contact
            existing_contact = None
            if email:
                existing_contact = db.query(Contact).filter(Contact.email == email).first()
            
            if existing_contact:
                if first_name:
                    existing_contact.first_name = first_name
                if last_name:
                    existing_contact.last_name = last_name
                if company_name:
                    existing_contact.company = company_name
                if company_id:
                    existing_contact.company_id = company_id
                if title:
                    existing_contact.title = title
                if phone:
                    existing_contact.phone = phone
                existing_contact.updated_at = datetime.utcnow()
                existing_contact.last_seen = datetime.utcnow()
                existing_contact.account_manager = assign_to
                db.add(existing_contact)
                stats["contacts_updated"] += 1
                print(f"✅ updated: {first_name} {last_name}")
            else:
                new_contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    name=f"{first_name} {last_name}".strip(),
                    company=company_name,
                    company_id=company_id,
                    title=title,
                    email=email,
                    phone=phone,
                    address=address,
                    website=website,
                    status="cold",
                    account_manager=assign_to,
                    source="Business Card Scan",
                    scanned_date=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )
                db.add(new_contact)
                stats["contacts_created"] += 1
                print(f"✅ created: {first_name} {last_name}")
            
            # Commit after each card
            db.commit()
            
            # Small delay to avoid rate limits
            time.sleep(0.2)
        
        print("\n" + "=" * 50)
        print("✅ COMPLETE!")
        print(f"   Processed: {stats['processed']}/{len(files)}")
        print(f"   Contacts created: {stats['contacts_created']}")
        print(f"   Contacts updated: {stats['contacts_updated']}")
        print(f"   Companies created: {stats['companies_created']}")
        print(f"   Companies linked: {stats['companies_linked']}")
        print(f"   Errors: {stats['errors']}")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/process_business_cards.py <folder_url> [assign_to_email]")
        print("\nExample:")
        print("  mac-mini run python3 scripts/process_business_cards.py 'https://drive.google.com/drive/folders/1aGO6vxe50yA-1UcanPDEVlIFrXOMRYK4'")
        sys.exit(1)
    
    folder_url = sys.argv[1]
    assign_to = sys.argv[2] if len(sys.argv) > 2 else "jacob@coloradocareassist.com"
    
    print("=" * 50)
    print("🃏 Bulk Business Card Processor")
    print("=" * 50)
    print(f"Folder: {folder_url}")
    print(f"Assign to: {assign_to}")
    
    process_folder(folder_url, assign_to)







