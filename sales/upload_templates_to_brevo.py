#!/usr/bin/env python3
"""
Upload newsletter templates to Brevo as saved email templates.
This allows you to use them in the Brevo UI when creating campaigns.
"""

import os
import sys
import requests
from brevo_service import BrevoService

def upload_template_to_brevo(brevo: BrevoService, template_name: str, html_content: str, folder_id: int = 1) -> dict:
    """Upload an HTML template to Brevo."""
    try:
        # Brevo API endpoint for creating email templates
        # Note: Brevo's template API may vary - this is based on typical email marketing APIs
        response = requests.post(
            f"{brevo.base_url}/smtp/templates",
            headers=brevo._get_headers(),
            json={
                "name": template_name,
                "htmlContent": html_content,
                "subject": template_name,  # Default subject, can be changed later
                "sender": {
                    "name": "Colorado CareAssist",
                    "email": "noreply@coloradocareassist.com"  # This will need to be your verified sender
                }
            }
        )
        
        if response.status_code in (200, 201):
            data = response.json()
            return {
                "success": True,
                "template_id": data.get('id'),
                "name": template_name
            }
        else:
            error_text = response.text
            return {
                "success": False,
                "error": f"API error {response.status_code}: {error_text[:200]}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def read_template_file(filepath: str) -> str:
    """Read HTML template file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"ERROR reading {filepath}: {e}")
        return None

def upload_templates():
    """Upload newsletter templates to Brevo."""
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    print("=== UPLOAD NEWSLETTER TEMPLATES TO BREVO ===\n")
    
    # Define templates to upload
    templates = [
        {
            "file": "newsletter_template_clients.html",
            "name": "Client Newsletter Template"
        },
        {
            "file": "newsletter_template_referral_sources.html",
            "name": "Referral Source Newsletter Template"
        },
        {
            "file": "newsletter_january_2025_clients.html",
            "name": "January 2025 Client Newsletter"
        },
        {
            "file": "newsletter_january_2025_referral_sources.html",
            "name": "January 2025 Referral Source Newsletter"
        }
    ]
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploaded = []
    errors = []
    
    for template_info in templates:
        filepath = os.path.join(base_dir, template_info["file"])
        template_name = template_info["name"]
        
        if not os.path.exists(filepath):
            print(f"⚠️  Skipping {template_name} - file not found: {filepath}")
            errors.append(f"{template_name}: File not found")
            continue
        
        print(f"\nReading {template_info['file']}...")
        html_content = read_template_file(filepath)
        
        if not html_content:
            errors.append(f"{template_name}: Failed to read file")
            continue
        
        print(f"Uploading '{template_name}' to Brevo...")
        result = upload_template_to_brevo(brevo, template_name, html_content)
        
        if result.get("success"):
            template_id = result.get("template_id")
            print(f"✅ Successfully uploaded '{template_name}' (Template ID: {template_id})")
            uploaded.append(template_name)
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"❌ Failed to upload '{template_name}': {error_msg}")
            errors.append(f"{template_name}: {error_msg}")
    
    # Summary
    print("\n" + "=" * 60)
    print("UPLOAD SUMMARY")
    print("=" * 60)
    print(f"Successfully uploaded: {len(uploaded)}")
    for name in uploaded:
        print(f"  ✅ {name}")
    
    if errors:
        print(f"\nErrors: {len(errors)}")
        for error in errors:
            print(f"  ❌ {error}")
    
    if errors:
        print("\n⚠️  Note: If upload failed, you may need to:")
        print("   1. Upload templates manually through Brevo UI")
        print("   2. Check Brevo API documentation for template endpoints")
        print("   3. Verify your Brevo plan includes template API access")

if __name__ == "__main__":
    upload_templates()

