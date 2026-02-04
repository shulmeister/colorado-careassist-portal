#!/usr/bin/env python3
"""Test business card extraction quality with different models - runs on Heroku."""

# CRITICAL: Register HEIF opener BEFORE importing PIL
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("HEIF opener registered successfully!")
except ImportError as e:
    print(f"Warning: pillow_heif not available: {e}")

import os
import sys
import json
import base64
import re
import httpx
from PIL import Image, ImageOps
import io

# Test with 5 business cards from the folder
FOLDER_URL = "https://drive.google.com/drive/folders/1af0ZVmsBnY_n_LRuA7FVZBemyLeK7LME"

from dotenv import load_dotenv
load_dotenv()

from google_drive_service import GoogleDriveService

# Prompts to test
CURRENT_PROMPT = """You are extracting contact information from a business card image.

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

# Simple prompt like user might type directly to Gemini/ChatGPT
SIMPLE_PROMPT = """Look at this business card and extract:
- First Name
- Last Name  
- Title/Position
- Company Name
- Email Address
- Phone Number

Return as JSON. If something is unclear, use null."""


def convert_heic_to_jpeg(content: bytes) -> tuple:
    """Convert HEIC to JPEG."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        image = Image.open(io.BytesIO(content))
        image = ImageOps.exif_transpose(image)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=95)
        return output.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"  HEIC conversion failed: {e}")
        raise


def prepare_image(content: bytes, filename: str) -> tuple:
    """Convert to base64 with proper mime type."""
    if filename.lower().endswith(('.heic', '.heif')):
        content, mime = convert_heic_to_jpeg(content)
    else:
        mime = "image/jpeg"
        if filename.lower().endswith('.png'):
            mime = "image/png"
        elif filename.lower().endswith('.webp'):
            mime = "image/webp"
    
    b64 = base64.b64encode(content).decode("utf-8")
    return b64, mime


def extract_openai(b64: str, mime: str, model: str, prompt: str) -> dict:
    """Extract using OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "No OPENAI_API_KEY"}
    
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
            return {"error": f"HTTP {resp.status_code}"}
        
        text = resp.json()["choices"][0]["message"]["content"]
        text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def extract_gemini(b64: str, mime: str, model: str, prompt: str) -> dict:
    """Extract using Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "No GEMINI_API_KEY"}
    
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
            return {"error": f"HTTP {resp.status_code}"}
        
        data = resp.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def format_result(result: dict) -> str:
    """Format extraction result for display."""
    if "error" in result:
        return f"ERROR: {result['error']}"
    
    first = result.get("first_name") or "-"
    last = result.get("last_name") or "-"
    title = result.get("title") or "-"
    company = result.get("company") or "-"
    email = result.get("email") or "-"
    phone = result.get("phone") or "-"
    
    return f"{first} {last} | {title} @ {company} | {email} | {phone}"


def main():
    print("=" * 100)
    print("BUSINESS CARD EXTRACTION QUALITY COMPARISON")
    print("=" * 100)
    
    drive_service = GoogleDriveService()
    if not drive_service.enabled:
        print("ERROR: Google Drive not enabled")
        return
    
    files = drive_service.list_files_in_folder(FOLDER_URL, image_only=True, recursive=True)
    print(f"\nFound {len(files)} files in folder")
    
    if not files:
        print("No files found!")
        return
    
    # Test configurations
    test_configs = [
        # (name, provider, model, prompt)
        ("gpt-4o-mini + our prompt", "openai", "gpt-4o-mini", CURRENT_PROMPT),
        ("gpt-4o + our prompt", "openai", "gpt-4o", CURRENT_PROMPT),
        ("gpt-4o + simple prompt", "openai", "gpt-4o", SIMPLE_PROMPT),
        ("gemini-2.0-flash + our prompt", "gemini", "gemini-2.0-flash", CURRENT_PROMPT),
        ("gemini-1.5-pro + our prompt", "gemini", "gemini-1.5-pro", CURRENT_PROMPT),
        ("gemini-1.5-pro + simple prompt", "gemini", "gemini-1.5-pro", SIMPLE_PROMPT),
    ]
    
    all_results = []
    
    for i, file_info in enumerate(files[:5]):
        file_id = file_info.get("id")
        file_name = file_info.get("name", "unknown")
        
        print(f"\n{'=' * 100}")
        print(f"CARD {i+1}: {file_name}")
        print("=" * 100)
        
        # Download
        result = drive_service.download_file_by_id(file_id)
        if not result:
            print("  ERROR: Failed to download")
            continue
        
        content = result[0]
        print(f"  Downloaded: {len(content):,} bytes")
        
        # Prepare image
        try:
            b64, mime = prepare_image(content, file_name)
        except Exception as e:
            print(f"  ERROR preparing image: {e}")
            continue
        
        file_results = {"file": file_name}
        
        for config_name, provider, model, prompt in test_configs:
            print(f"\n  {config_name}:")
            
            if provider == "openai":
                result = extract_openai(b64, mime, model, prompt)
            else:
                result = extract_gemini(b64, mime, model, prompt)
            
            file_results[config_name] = result
            print(f"    {format_result(result)}")
        
        all_results.append(file_results)
    
    # Summary analysis
    print("\n" + "=" * 100)
    print("ANALYSIS")
    print("=" * 100)
    
    print("""
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ KEY FINDINGS:                                                                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. gpt-4o-mini (current) vs gpt-4o (full): Is there quality difference?                        │
│ 2. gemini-2.0-flash (current) vs gemini-1.5-pro: Is there quality difference?                  │
│ 3. Our detailed prompt vs simple prompt: Does complexity help or hurt?                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    main()

