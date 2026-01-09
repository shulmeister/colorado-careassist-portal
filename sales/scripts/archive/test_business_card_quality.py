#!/usr/bin/env python3
"""Test business card extraction quality with different models."""

import os
import sys
import json
import base64
import httpx
from dotenv import load_dotenv

load_dotenv()

# Test folder with 5 business cards
FOLDER_URL = "https://drive.google.com/drive/folders/1af0ZVmsBnY_n_LRuA7FVZBemyLeK7LME?usp=drive_link"

def get_folder_id(url: str) -> str:
    import re
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

def list_files_in_folder(folder_id: str) -> list:
    """List image files in a Google Drive folder."""
    from google_drive_service import GoogleDriveService
    drive_service = GoogleDriveService()
    if not drive_service.enabled:
        print("ERROR: Google Drive service not enabled")
        return []
    
    files = drive_service.list_files_in_folder(FOLDER_URL, image_only=True, recursive=True)
    return files

def download_file(file_id: str, file_name: str) -> bytes:
    """Download a file from Google Drive."""
    from google_drive_service import GoogleDriveService
    drive_service = GoogleDriveService()
    result = drive_service.download_file_by_id(file_id)
    if result:
        return result[0]  # content bytes
    return None

def convert_heic_if_needed(content: bytes, filename: str) -> tuple:
    """Convert HEIC to JPEG if needed."""
    if filename.lower().endswith(('.heic', '.heif')):
        try:
            from PIL import Image, ImageOps
            from pillow_heif import register_heif_opener
            import io
            register_heif_opener()
            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=95)
            return output.getvalue(), "image/jpeg"
        except Exception as e:
            print(f"  HEIC conversion failed: {e}")
            return content, "image/jpeg"
    
    mime = "image/jpeg"
    if filename.lower().endswith('.png'):
        mime = "image/png"
    elif filename.lower().endswith('.webp'):
        mime = "image/webp"
    return content, mime

SIMPLE_PROMPT = """Extract contact information from this business card.
Return JSON with: first_name, last_name, title, company, email, phone
If you can't read a field clearly, use null."""

FULL_PROMPT = """You are extracting contact information from a business card image.

CRITICAL INSTRUCTIONS:
- Read the text on the card CAREFULLY and ACCURATELY
- Do NOT guess or make up names - if you can't read it clearly, use null
- Names should be real human names (e.g., "John Smith", "Maria Garcia")
- Company names should be real business names
- If the image is blurry or unreadable, return all nulls

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

RULES:
- If a field is not visible or unreadable, set it to null
- For phone, include area code (format: 303-555-1234)
- For email, must be a valid email format
- For company, use the full official company name
- The "notes" field can include department, fax, cell phone, credentials after name, etc.
- NEVER return gibberish or random characters - use null instead"""


def extract_with_openai(content: bytes, filename: str, model: str = "gpt-4o-mini", prompt: str = FULL_PROMPT) -> dict:
    """Extract using OpenAI Vision."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "No OpenAI API key"}
    
    content, mime = convert_heic_if_needed(content, filename)
    b64 = base64.b64encode(content).decode("utf-8")
    
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        ],
                    }
                ],
                "max_tokens": 500,
                "temperature": 0,
            },
            timeout=60.0,
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        
        text = resp.json()["choices"][0]["message"]["content"]
        # Clean markdown
        import re
        text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def extract_with_gemini(content: bytes, filename: str, model: str = "gemini-2.0-flash", prompt: str = FULL_PROMPT) -> dict:
    """Extract using Gemini Vision."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "No Gemini API key"}
    
    content, mime = convert_heic_if_needed(content, filename)
    b64 = base64.b64encode(content).decode("utf-8")
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }]
            },
            timeout=60.0,
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        
        data = resp.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        # Clean markdown
        import re
        text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 80)
    print("BUSINESS CARD EXTRACTION QUALITY TEST")
    print("=" * 80)
    
    # Get the folder ID and list files
    folder_id = get_folder_id(FOLDER_URL)
    print(f"\nFolder ID: {folder_id}")
    
    files = list_files_in_folder(folder_id)
    print(f"Found {len(files)} files in folder")
    
    if not files:
        print("No files found!")
        return
    
    results = []
    
    for i, file_info in enumerate(files[:5]):  # Process first 5
        file_id = file_info.get("id")
        file_name = file_info.get("name", "unknown")
        
        print(f"\n{'=' * 80}")
        print(f"FILE {i+1}: {file_name}")
        print("=" * 80)
        
        content = download_file(file_id, file_name)
        if not content:
            print("  ERROR: Could not download file")
            continue
        
        print(f"  Downloaded {len(content)} bytes")
        
        # Test with different configurations
        configs = [
            ("gpt-4o-mini (current)", lambda: extract_with_openai(content, file_name, "gpt-4o-mini", FULL_PROMPT)),
            ("gpt-4o (full model)", lambda: extract_with_openai(content, file_name, "gpt-4o", FULL_PROMPT)),
            ("gemini-2.0-flash (current)", lambda: extract_with_gemini(content, file_name, "gemini-2.0-flash", FULL_PROMPT)),
            ("gemini-1.5-pro", lambda: extract_with_gemini(content, file_name, "gemini-1.5-pro", FULL_PROMPT)),
        ]
        
        file_results = {"file": file_name, "extractions": {}}
        
        for config_name, extractor in configs:
            print(f"\n  --- {config_name} ---")
            try:
                result = extractor()
                file_results["extractions"][config_name] = result
                
                if "error" in result:
                    print(f"    ERROR: {result['error']}")
                else:
                    first = result.get("first_name", "?")
                    last = result.get("last_name", "?")
                    title = result.get("title", "?")
                    company = result.get("company", "?")
                    email = result.get("email", "?")
                    phone = result.get("phone", "?")
                    
                    print(f"    Name: {first} {last}")
                    print(f"    Title: {title}")
                    print(f"    Company: {company}")
                    print(f"    Email: {email}")
                    print(f"    Phone: {phone}")
            except Exception as e:
                print(f"    EXCEPTION: {e}")
                file_results["extractions"][config_name] = {"error": str(e)}
        
        results.append(file_results)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY - COMPARING MODELS")
    print("=" * 80)
    
    print("\n┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ FINDINGS:                                                                    │")
    print("├─────────────────────────────────────────────────────────────────────────────┤")
    
    # Count successful extractions per model
    success_counts = {}
    for file_result in results:
        for model, extraction in file_result["extractions"].items():
            if model not in success_counts:
                success_counts[model] = {"success": 0, "has_name": 0, "has_email": 0, "total": 0}
            success_counts[model]["total"] += 1
            if "error" not in extraction:
                success_counts[model]["success"] += 1
                if extraction.get("first_name") or extraction.get("last_name"):
                    success_counts[model]["has_name"] += 1
                if extraction.get("email"):
                    success_counts[model]["has_email"] += 1
    
    for model, counts in success_counts.items():
        print(f"│ {model:30} - Success: {counts['success']}/{counts['total']}, Names: {counts['has_name']}, Emails: {counts['has_email']} │")
    
    print("└─────────────────────────────────────────────────────────────────────────────┘")


if __name__ == "__main__":
    main()

