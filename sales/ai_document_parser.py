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

    def _looks_like_address(self, text: str) -> bool:
        """Check if text looks like a street address rather than a business name"""
        if not text:
            return True
        text = text.strip().lower()
        # Common address patterns
        address_indicators = [
            r'^\d+\s+\w',  # Starts with number + space + word (123 Main St)
            r'\bst\b',     # Street
            r'\bave\b',    # Avenue
            r'\bblvd\b',   # Boulevard
            r'\bdr\b',     # Drive
            r'\brd\b',     # Road
            r'\bct\b',     # Court
            r'\bpkwy\b',   # Parkway
            r'\bln\b',     # Lane
            r'\bway\b',    # Way
            r'\bste\b',    # Suite
            r'#\d+',       # Unit numbers
        ]
        for pattern in address_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def lookup_business_at_address(self, address: str, city: str = "") -> Optional[str]:
        """Use Gemini to identify the healthcare business at an address"""
        if not GEMINI_API_KEY or not address:
            return None

        httpx = self._get_httpx()
        if not httpx:
            return None

        full_address = f"{address}, {city}" if city else address

        prompt = f"""What healthcare facility or medical business is located at this address?

Address: {full_address}

This is likely a:
- Nursing home / Skilled Nursing Facility (SNF)
- Assisted Living facility
- Memory Care facility
- Rehabilitation hospital
- Hospice
- Senior living community
- Medical office building
- Hospital

Return ONLY the business name (no explanation). If you cannot identify a specific healthcare facility at this address, return "UNKNOWN".

Examples:
- "2101 S Blackhawk St, Aurora CO" → "The Medical Center of Aurora"
- "1400 Jackson St, Denver CO" → "National Jewish Health"
- "4700 E Hale Pkwy, Denver CO" → "Kindred Hospital Denver"
- "501 S Cherry St, Glendale CO" → "Cherry Creek Nursing Center"
"""

        try:
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
                                "parts": [{"text": prompt}]
                            }]
                        },
                        timeout=15.0,
                    )

                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

                    if text and text.upper() != "UNKNOWN" and not self._looks_like_address(text):
                        logger.info(f"Gemini identified: {address} → {text}")
                        return text

                except Exception as e:
                    continue

            return None

        except Exception as e:
            logger.error(f"Error looking up business at address: {e}")
            return None

    def parse_myway_pdf(self, pdf_content: bytes, filename: str = "") -> Dict[str, Any]:
        """Parse MyWay route PDF using AI"""

        prompt = """Analyze this MyWay route PDF and extract ALL the information.

This is a sales route for a home care company visiting healthcare facilities (nursing homes, assisted living, rehab centers, hospitals, etc).

Return a JSON object with this EXACT structure:
{
    "date": "YYYY-MM-DD format or null if not found",
    "total_mileage": number or null,
    "visits": [
        {
            "stop_number": 1,
            "business_name": "Full healthcare facility/business name",
            "address": "Street address",
            "city": "City name",
            "notes": "Any notes or status like SKIPPED",
            "skipped": true/false
        }
    ]
}

CRITICAL - BUSINESS NAME IDENTIFICATION:
- MyWay often shows only addresses without business names
- You MUST identify the healthcare facility at each address using your knowledge
- These are typically: nursing homes, skilled nursing facilities, assisted living, memory care, rehab hospitals, hospice, senior living communities
- Example: "2101 S Blackhawk St, Aurora CO" → "The Medical Center of Aurora"
- Example: "1000 Southpark Dr, Littleton CO" → "Littleton Adventist Hospital"
- If you cannot identify the facility, use the address but TRY to identify it first
- Do NOT just copy the address as the business name if you can identify the actual facility

OTHER REQUIREMENTS:
- Extract EVERY stop/visit listed, even if marked as SKIPPED
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

                business_name = v.get("business_name", "")
                address = v.get("address", "")
                city = v.get("city", "")

                # If business_name looks like an address, try to enrich it
                if self._looks_like_address(business_name):
                    lookup_address = address or business_name
                    enriched_name = self.lookup_business_at_address(lookup_address, city)
                    if enriched_name:
                        business_name = enriched_name
                    elif not business_name:
                        business_name = "Unknown"

                visit = {
                    "stop_number": v.get("stop_number", len(visits) + 1),
                    "business_name": business_name,
                    "address": address,
                    "city": city,
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
