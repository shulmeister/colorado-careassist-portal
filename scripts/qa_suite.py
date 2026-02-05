import os
import sys
import requests
import json
import logging
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BASE_URL = os.getenv("PORTAL_URL", "https://portal.coloradocareassist.com").rstrip("/")

ENDPOINTS = [
    # Portal
    ("GET", "/", [200, 302, 307]),
    ("GET", "/health", [200, 404, 405]), # Some health endpoints might be different
    ("GET", "/api/tools", [200, 401]),
    ("GET", "/api/search?q=test", [200, 401]),
    ("GET", "/api/activity-stream", [200, 401]),
    
    # Sales
    ("GET", "/sales", [200, 302, 307]), 
    ("GET", "/api/contacts", [401]),
    
    # Recruiting
    ("GET", "/recruiting", [200, 302, 307]),
    
    # Gigi
    ("GET", "/gigi/health", [200, 404, 405]),
    ("POST", "/gigi/webhook/retell", [401, 422]), 
    ("POST", "/gigi/webhook/ringcentral-sms", [200, 401]), 
]

def run_tests():
    logger.info(f"Starting QA Suite against {BASE_URL}")
    failed = 0
    passed = 0
    
    for method, path, expected in ENDPOINTS:
        url = urljoin(BASE_URL, path)
        try:
            if method == "GET":
                resp = requests.get(url, timeout=10, allow_redirects=True)
            else:
                resp = requests.post(url, timeout=10, allow_redirects=True)
                
            status_code = resp.status_code
            
            # Normalize expected to list
            if not isinstance(expected, list):
                expected = [expected]
            
            if status_code in expected:
                logger.info(f"✅ {method} {path} -> {status_code}")
                passed += 1
            else:
                logger.error(f"❌ {method} {path} -> {status_code} (Expected {expected})")
                failed += 1
                
        except Exception as e:
            logger.error(f"❌ {method} {path} -> Error: {str(e)}")
            failed += 1
            
    logger.info(f"QA Complete. Passed: {passed}, Failed: {failed}")
    
    # Test Activity Feed Logging (Internal)
    test_activity_feed()

def test_activity_feed():
    logger.info("Testing Activity Feed Logging...")
    url = urljoin(BASE_URL, "/api/internal/event")
    payload = {
        "source": "QA_Bot",
        "description": "Automated QA Test",
        "event_type": "test",
        "icon": "🧪"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
             logger.info("✅ Activity Feed Log -> 200 OK")
        else:
             logger.error(f"❌ Activity Feed Log -> {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"❌ Activity Feed Log -> Error: {e}")

if __name__ == "__main__":
    run_tests()
