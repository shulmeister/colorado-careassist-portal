"""
AI-Powered Document Parser using Gemini REST API (primary) and OpenAI (fallback)
Replaces OCR/Tesseract garbage with actual AI that works.

Handles:
- MyWay route PDFs → extracts visits, mileage, dates
- Receipts → extracts amount, vendor, date, category
- Business cards → extracts contact info
"""

import base64
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Gemini models that support PDFs (1.5+ models)
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]


class AIDocumentParser:
    """Parse documents using AI vision models via REST API"""

    def __init__(self):
        self._httpx = None
        self._openai = None

    def _get_httpx(self):
        if self._httpx is None:
            try:
                import httpx
                self._httpx = httpx
            except ImportError:
                logger.warning("httpx not installed")
        return self._httpx

    def _get_openai(self):
        if self._openai is None and OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self._openai = OpenAI(api_key=OPENAI_API_KEY)
            except ImportError:
                logger.warning("openai not installed")
        return self._openai

    def parse_myway_pdf(self, pdf_content: bytes, filename: str = "") -> Dict[str, Any]:
        """Parse MyWay route PDF using AI"""
        
        prompt = """Analyze this MyWay route PDF and extract ALL the information.

Return a JSON object with this EXACT structure:
{
    "date": "YYYY-MM-DD format or null if not found",
    "total_mileage": number or null,
    "visits": [
        {
            "stop_number": 1,
            "business_name": "Full business/facility name",
            "address": "Street address",
            "city": "City name",
            "notes": "Any notes or status like SKIPPED",
            "skipped": true/false
        }
    ]
}

IMPORTANT:
- Extract EVERY stop/visit listed, even if marked as SKIPPED
- For "Address Only" entries, use the street address as business_name
- Include the full business name when available
- Set skipped=true for entries marked SKIPPED
- Extract the route date from the header
- Extract total mileage if shown
- Return ONLY valid JSON, no markdown or explanation"""

        result = self._call_gemini(pdf_content, prompt, "application/pdf")
        
        if not result.get("success"):
            return {
                "type": "myway_route",
                "success": False,
                "error": result.get("error", "AI parsing failed"),
                "visits": [],
                "mileage": None,
                "date": None
            }
        
        try:
            data = result["data"]
            
            # Parse date
            pdf_date = None
            if data.get("date"):
                try:
                    pdf_date = datetime.strptime(data["date"], "%Y-%m-%d")
                except:
                    pass
            
            # Process visits
            visits = []
            for v in data.get("visits", []):
                if v.get("skipped"):
                    continue  # Skip visits marked as skipped
                
                visit = {
                    "stop_number": v.get("stop_number", len(visits) + 1),
                    "business_name": v.get("business_name", "Unknown"),
                    "address": v.get("address", ""),
                    "city": v.get("city", ""),
                    "notes": v.get("notes", ""),
                    "visit_date": pdf_date
                }
                visits.append(visit)
            
            return {
                "type": "myway_route",
                "success": True,
                "visits": visits,
                "count": len(visits),
                "mileage": data.get("total_mileage"),
                "date": pdf_date
            }
            
        except Exception as e:
            logger.error(f"Error processing MyWay AI response: {e}")
            return {
                "type": "myway_route",
                "success": False,
                "error": str(e),
                "visits": [],
                "mileage": None,
                "date": None
            }

    def parse_receipt(self, image_content: bytes, filename: str = "") -> Dict[str, Any]:
        """Parse receipt image using AI"""
        
        prompt = """Analyze this receipt image and extract the expense information.

Return a JSON object with this EXACT structure:
{
    "amount": 123.45,
    "vendor": "Store or business name",
    "date": "YYYY-MM-DD format or null",
    "category": "One of: Gas, Food, Office Supplies, Travel, Medical, Other",
    "description": "Brief description of purchase",
    "items": ["list", "of", "items", "if visible"]
}

IMPORTANT:
- Extract the TOTAL amount paid (look for Total, Grand Total, Amount Due)
- Return amount as a number, not string
- Infer category from vendor/items if not obvious
- Return ONLY valid JSON, no markdown or explanation"""

        # Detect mime type
        mime_type = self._detect_mime_type(image_content, filename)
        
        result = self._call_gemini(image_content, prompt, mime_type)
        
        if not result.get("success"):
            return {
                "type": "receipt",
                "success": False,
                "error": result.get("error", "AI parsing failed")
            }
        
        try:
            data = result["data"]
            return {
                "type": "receipt",
                "success": True,
                "amount": data.get("amount", 0),
                "vendor": data.get("vendor", "Unknown"),
                "date": data.get("date"),
                "category": data.get("category", "Other"),
                "description": data.get("description", ""),
                "items": data.get("items", [])
            }
        except Exception as e:
            logger.error(f"Error processing receipt AI response: {e}")
            return {
                "type": "receipt",
                "success": False,
                "error": str(e)
            }

    def parse_business_card(self, image_content: bytes, filename: str = "") -> Dict[str, Any]:
        """Parse business card image using AI"""
        
        prompt = """Analyze this business card image and extract contact information.

Return a JSON object with this EXACT structure:
{
    "first_name": "First name",
    "last_name": "Last name", 
    "company": "Company or organization name",
    "title": "Job title",
    "email": "email@example.com",
    "phone": "Phone number with area code",
    "address": "Full address if shown",
    "website": "Website URL if shown",
    "notes": "Any other relevant info"
}

IMPORTANT:
- Read the card carefully, don't guess
- Return null for fields you cannot clearly read
- For phone, include area code
- For email, ensure it's a valid format
- Return ONLY valid JSON, no markdown or explanation"""

        # Detect mime type
        mime_type = self._detect_mime_type(image_content, filename)
        
        result = self._call_gemini(image_content, prompt, mime_type)
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "AI parsing failed")
            }
        
        try:
            data = result["data"]
            return {
                "success": True,
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "company": data.get("company"),
                "title": data.get("title"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "address": data.get("address"),
                "website": data.get("website"),
                "notes": data.get("notes")
            }
        except Exception as e:
            logger.error(f"Error processing business card AI response: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _call_gemini(self, content: bytes, prompt: str, mime_type: str) -> Dict[str, Any]:
        """Call Gemini Vision API via REST"""
        if not GEMINI_API_KEY:
            return {"success": False, "error": "No Gemini API key"}
        
        httpx = self._get_httpx()
        if not httpx:
            return {"success": False, "error": "httpx not installed"}
        
        try:
            b64 = base64.b64encode(content).decode("utf-8")
            
            for model in GEMINI_MODELS:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    resp = httpx.post(
                        url,
                        headers={
                            "x-goog-api-key": GEMINI_API_KEY,
                            "Content-Type": "application/json"
                        },
                        json={
                            "contents": [{
                                "parts": [
                                    {"text": prompt},
                                    {"inline_data": {"mime_type": mime_type, "data": b64}},
                                ]
                            }]
                        },
                        timeout=60.0,  # Longer timeout for PDFs
                    )
                    
                    if resp.status_code == 404:
                        logger.info(f"Gemini model {model} not found, trying next")
                        continue
                    if resp.status_code != 200:
                        logger.warning(f"Gemini {model} returned {resp.status_code}: {resp.text[:300]}")
                        continue
                    
                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    if not text:
                        logger.warning(f"Gemini {model} returned empty text")
                        continue
                    
                    # Parse JSON from response
                    json_data = self._extract_json(text)
                    if json_data:
                        logger.info(f"Gemini ({model}) successfully parsed document")
                        return {"success": True, "data": json_data}
                    else:
                        logger.warning(f"Gemini {model} returned non-JSON: {text[:200]}")
                        continue
                        
                except Exception as model_error:
                    logger.debug(f"Gemini {model} failed: {model_error}")
                    continue
            
            return {"success": False, "error": "All Gemini models failed"}
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {"success": False, "error": str(e)}

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from AI response text"""
        if not text:
            return None
        
        # Clean up markdown code blocks
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"```$", "", text.strip())
        
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try to find JSON object in text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        return None

    def _detect_mime_type(self, content: bytes, filename: str) -> str:
        """Detect MIME type from content or filename"""
        # Check magic bytes
        if content[:4] == b'%PDF':
            return "application/pdf"
        if content[:3] == b'\xff\xd8\xff':
            return "image/jpeg"
        if content[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        if len(content) > 12 and (content[4:12] == b'ftypheic' or content[4:12] == b'ftypmif1'):
            return "image/heic"
        
        # Fall back to filename
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        mime_map = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'heic': 'image/heic',
            'heif': 'image/heif'
        }
        
        return mime_map.get(ext, "application/octet-stream")


# Singleton instance
ai_parser = AIDocumentParser()
