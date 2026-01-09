#!/usr/bin/env python3
"""Test business card extraction on 5 sample cards."""

# Register HEIF opener first
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

import os
import json
from google_drive_service import GoogleDriveService

# Import the extraction function
from app import _extract_business_card_ai

# Test with the 12-18 folder (18 cards)
FOLDER_URL = "https://drive.google.com/drive/folders/1lrt1NUKiDbr3FwpvHogC3rz7CThs8oLS"

def main():
    print("=" * 80)
    print("TESTING BUSINESS CARD EXTRACTION ON 5 SAMPLE CARDS")
    print("=" * 80)
    
    drive_service = GoogleDriveService()
    if not drive_service.enabled:
        print("ERROR: Google Drive not enabled")
        return
    
    files = drive_service.list_files_in_folder(FOLDER_URL, image_only=True)
    print(f"Found {len(files)} files")
    
    results = []
    
    for i, file_info in enumerate(files):  # Process all cards
        file_id = file_info.get("id")
        file_name = file_info.get("name", "unknown")
        
        print(f"\n--- Card {i+1}: {file_name} ---")
        
        result = drive_service.download_file_by_id(file_id)
        if not result:
            print("  ERROR: Download failed")
            continue
        
        content = result[0]
        print(f"  Downloaded {len(content):,} bytes")
        
        # Extract using our AI function
        card_data = _extract_business_card_ai(content, file_name)
        
        if card_data:
            first = card_data.get("first_name") or "-"
            last = card_data.get("last_name") or "-"
            title = card_data.get("title") or "-"
            company = card_data.get("company") or "-"
            email = card_data.get("email") or "-"
            phone = card_data.get("phone") or "-"
            
            print(f"  Name: {first} {last}")
            print(f"  Title: {title}")
            print(f"  Company: {company}")
            print(f"  Email: {email}")
            print(f"  Phone: {phone}")
            
            results.append({
                "file": file_name,
                "first_name": first,
                "last_name": last,
                "title": title,
                "company": company,
                "email": email,
                "phone": phone
            })
        else:
            print("  ERROR: Extraction failed")
    
    # Print summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"{'First Name':<15} {'Last Name':<15} {'Title':<30} {'Company':<25} {'Email':<30} {'Phone':<15}")
    print("-" * 130)
    for r in results:
        print(f"{r['first_name']:<15} {r['last_name']:<15} {r['title'][:28]:<30} {r['company'][:23]:<25} {r['email']:<30} {r['phone']:<15}")


if __name__ == "__main__":
    main()

