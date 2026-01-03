#!/usr/bin/env python3
"""
Test script to verify all Marketing Dashboard API connections.

Run this script to check:
- Google Ads API configuration and connectivity
- Facebook Ads API configuration
- GA4 API configuration
- GBP API configuration
- Other marketing service connections

Usage:
    python test_marketing_apis.py
    heroku run python test_marketing_apis.py -a portal-coloradocareassist
"""

import os
import sys
from datetime import date, timedelta
from typing import Dict, Any, List

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_status(service: str, status: bool, message: str = ""):
    """Print a formatted status line."""
    icon = "✅" if status else "❌"
    print(f"{icon} {service:<30} {message}")

def check_env_var(name: str, mask: bool = True) -> tuple[bool, str]:
    """Check if an environment variable is set."""
    value = os.getenv(name)
    if value:
        display_value = value[:10] + "..." if mask and len(value) > 10 else value
        return True, display_value
    return False, "Not set"

def test_google_ads() -> Dict[str, Any]:
    """Test Google Ads API configuration and connectivity."""
    print_section("Google Ads API")
    
    results = {
        "configured": False,
        "env_vars": {},
        "client_built": False,
        "connection_test": False,
        "data_test": False,
        "errors": []
    }
    
    # Check environment variables
    env_vars = [
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CUSTOMER_ID",
        "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    ]
    
    all_present = True
    for var in env_vars:
        is_set, value = check_env_var(var)
        results["env_vars"][var] = {"set": is_set, "value": value}
        print_status(f"  {var}", is_set, value if is_set else "")
        if not is_set and var in ["GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID"]:
            all_present = False
    
    if not all_present:
        results["errors"].append("Missing required environment variables")
        return results
    
    results["configured"] = True
    
    # Try to import and initialize service
    try:
        from services.marketing.google_ads_service import google_ads_service
        
        # Check if service is configured
        if not google_ads_service._is_configured():
            results["errors"].append("Service reports not configured")
            print_status("  Service configured", False, "Service reports not configured")
            return results
        
        print_status("  Service configured", True, "")
        results["client_built"] = True
        
        # Try to build client
        client = google_ads_service._build_client()
        if not client:
            results["errors"].append("Failed to build Google Ads client (check refresh token)")
            print_status("  Client built", False, "Failed to build client")
            return results
        
        print_status("  Client built", True, "")
        results["connection_test"] = True
        
        # Try to fetch data
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            print(f"\n  Testing data fetch (last 7 days: {start_date} to {end_date})...")
            metrics = google_ads_service.get_metrics(start_date, end_date)
            
            if metrics.get("is_placeholder"):
                results["errors"].append("API returned placeholder data (not configured or account suspended)")
                print_status("  Data fetch", False, "Returned placeholder data")
                print(f"    Message: {metrics.get('message', 'Unknown error')}")
            else:
                results["data_test"] = True
                print_status("  Data fetch", True, "Success!")
                print(f"    Spend: ${metrics.get('spend', {}).get('total', 0):.2f}")
                print(f"    Clicks: {metrics.get('performance', {}).get('clicks', 0)}")
                print(f"    Impressions: {metrics.get('performance', {}).get('impressions', 0)}")
                print(f"    Campaigns: {len(metrics.get('campaigns', []))}")
                print(f"    Source: {metrics.get('source', 'unknown')}")
                
        except Exception as e:
            results["errors"].append(f"Data fetch error: {str(e)}")
            print_status("  Data fetch", False, str(e))
            
    except ImportError as e:
        results["errors"].append(f"Import error: {str(e)}")
        print_status("  Service import", False, str(e))
    except Exception as e:
        results["errors"].append(f"Unexpected error: {str(e)}")
        print_status("  Service test", False, str(e))
    
    return results

def test_facebook_ads() -> Dict[str, Any]:
    """Test Facebook Ads API configuration."""
    print_section("Facebook Ads API")
    
    results = {
        "configured": False,
        "env_vars": {},
        "connection_test": False,
        "errors": []
    }
    
    env_vars = [
        "FACEBOOK_ACCESS_TOKEN",
        "FACEBOOK_AD_ACCOUNT_ID",
    ]
    
    all_present = True
    for var in env_vars:
        is_set, value = check_env_var(var)
        results["env_vars"][var] = {"set": is_set, "value": value}
        print_status(f"  {var}", is_set, value if is_set else "")
        if not is_set:
            all_present = False
    
    if not all_present:
        results["errors"].append("Missing required environment variables")
        return results
    
    results["configured"] = True
    
    # Try to test service
    try:
        from services.marketing.facebook_ads_service import facebook_ads_service
        
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        print(f"\n  Testing data fetch (last 7 days: {start_date} to {end_date})...")
        account_metrics = facebook_ads_service.get_account_metrics(start_date, end_date)
        
        if account_metrics.get("error"):
            results["errors"].append(account_metrics.get("error", "Unknown error"))
            print_status("  Data fetch", False, account_metrics.get("error", "Unknown error"))
        else:
            results["connection_test"] = True
            print_status("  Data fetch", True, "Success!")
            print(f"    Spend: ${account_metrics.get('spend', 0):.2f}")
            print(f"    Clicks: {account_metrics.get('clicks', 0)}")
            
    except Exception as e:
        results["errors"].append(f"Service test error: {str(e)}")
        print_status("  Service test", False, str(e))
    
    return results

def test_ga4() -> Dict[str, Any]:
    """Test GA4 API configuration."""
    print_section("Google Analytics 4 (GA4)")
    
    results = {
        "configured": False,
        "connection_test": False,
        "errors": []
    }
    
    is_set, value = check_env_var("GOOGLE_SERVICE_ACCOUNT_JSON", mask=False)
    print_status("  GOOGLE_SERVICE_ACCOUNT_JSON", is_set, "Set" if is_set else "Not set")
    
    prop_id = os.getenv("GA4_PROPERTY_ID", "445403783")
    print_status("  GA4_PROPERTY_ID", True, prop_id)
    
    if not is_set:
        results["errors"].append("GOOGLE_SERVICE_ACCOUNT_JSON not set")
        return results
    
    results["configured"] = True
    
    try:
        from services.marketing.ga4_service import ga4_service
        
        if not ga4_service.client:
            results["errors"].append("GA4 client not initialized")
            print_status("  Client initialized", False, "Client is None")
            return results
        
        print_status("  Client initialized", True, "")
        
        # Test data fetch
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        print(f"\n  Testing data fetch (last 7 days: {start_date} to {end_date})...")
        metrics = ga4_service.get_website_metrics(start_date, end_date)
        
        results["connection_test"] = True
        print_status("  Data fetch", True, "Success!")
        print(f"    Users: {metrics.get('total_users', 0)}")
        print(f"    Sessions: {metrics.get('total_sessions', 0)}")
        
    except Exception as e:
        results["errors"].append(f"GA4 test error: {str(e)}")
        print_status("  Service test", False, str(e))
    
    return results

def test_gbp() -> Dict[str, Any]:
    """Test Google Business Profile API configuration."""
    print_section("Google Business Profile (GBP)")
    
    results = {
        "configured": False,
        "connection_test": False,
        "errors": []
    }
    
    is_set, value = check_env_var("GOOGLE_SERVICE_ACCOUNT_JSON", mask=False)
    print_status("  GOOGLE_SERVICE_ACCOUNT_JSON", is_set, "Set" if is_set else "Not set")
    
    location_ids = os.getenv("GBP_LOCATION_IDS", "")
    print_status("  GBP_LOCATION_IDS", bool(location_ids), location_ids if location_ids else "Not set")
    
    if not is_set or not location_ids:
        results["errors"].append("Missing required configuration")
        return results
    
    results["configured"] = True
    
    try:
        from services.marketing.gbp_service import gbp_service
        
        if not gbp_service.service:
            results["errors"].append("GBP service not initialized")
            print_status("  Service initialized", False, "Service is None")
            return results
        
        print_status("  Service initialized", True, "")
        
        # Test location info
        locations = gbp_service.get_location_info()
        results["connection_test"] = True
        print_status("  Location access", True, f"Found {len(locations)} locations")
        
    except Exception as e:
        results["errors"].append(f"GBP test error: {str(e)}")
        print_status("  Service test", False, str(e))
    
    return results

def test_facebook_social() -> Dict[str, Any]:
    """Test Facebook Graph API for social metrics."""
    print_section("Facebook Graph API (Social)")
    
    results = {
        "configured": False,
        "connection_test": False,
        "errors": []
    }
    
    is_set, value = check_env_var("FACEBOOK_ACCESS_TOKEN")
    print_status("  FACEBOOK_ACCESS_TOKEN", is_set, value if is_set else "Not set")
    
    page_id = os.getenv("FACEBOOK_PAGE_ID", "")
    print_status("  FACEBOOK_PAGE_ID", bool(page_id), page_id if page_id else "Not set")
    
    if not is_set or not page_id:
        results["errors"].append("Missing required configuration")
        return results
    
    results["configured"] = True
    
    try:
        from services.marketing.facebook_service import facebook_service
        
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        print(f"\n  Testing data fetch (last 7 days: {start_date} to {end_date})...")
        metrics = facebook_service.get_page_metrics(page_id, start_date, end_date)
        
        results["connection_test"] = True
        print_status("  Data fetch", True, "Success!")
        print(f"    Page likes: {metrics.get('current_page_likes', 0)}")
        
    except Exception as e:
        results["errors"].append(f"Facebook service test error: {str(e)}")
        print_status("  Service test", False, str(e))
    
    return results

def print_summary(all_results: Dict[str, Dict[str, Any]]):
    """Print a summary of all test results."""
    print_section("Summary")
    
    total_tests = len(all_results)
    passed = sum(1 for r in all_results.values() if r.get("connection_test") or (r.get("data_test")))
    configured = sum(1 for r in all_results.values() if r.get("configured"))
    
    print(f"\nTests Run: {total_tests}")
    print(f"Configured: {configured}/{total_tests}")
    print(f"Connection/Data Tests Passed: {passed}/{total_tests}")
    
    print("\nDetailed Status:")
    for service_name, results in all_results.items():
        status_icon = "✅" if (results.get("connection_test") or results.get("data_test")) else "❌"
        config_status = "✅ Configured" if results.get("configured") else "⚠️  Not Configured"
        test_status = "✅ Working" if (results.get("connection_test") or results.get("data_test")) else "❌ Failed"
        
        print(f"\n{status_icon} {service_name}")
        print(f"   Configuration: {config_status}")
        print(f"   Connection: {test_status}")
        
        if results.get("errors"):
            print(f"   Errors: {len(results['errors'])}")
            for error in results["errors"]:
                print(f"     - {error}")

def main():
    """Run all marketing API tests."""
    print("\n" + "=" * 70)
    print("  Marketing Dashboard API Connection Test")
    print("=" * 70)
    
    all_results = {}
    
    # Test all services
    all_results["Google Ads"] = test_google_ads()
    all_results["Facebook Ads"] = test_facebook_ads()
    all_results["GA4"] = test_ga4()
    all_results["GBP"] = test_gbp()
    all_results["Facebook Social"] = test_facebook_social()
    
    # Print summary
    print_summary(all_results)
    
    print("\n" + "=" * 70)
    print("  Test Complete")
    print("=" * 70 + "\n")
    
    # Return exit code based on results
    if all(results.get("connection_test") or results.get("data_test") for results in all_results.values() if results.get("configured")):
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())

