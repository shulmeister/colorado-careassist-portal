#!/usr/bin/env python3
"""
QuickBooks Online API integration service.
Handles customer data fetching and syncing to Brevo.
"""

import os
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class QuickBooksService:
    """Service for interacting with QuickBooks Online API."""
    
    def __init__(self):
        # Support both QB_* and QUICKBOOKS_* naming conventions
        self.client_id = os.getenv('QB_CLIENT_ID') or os.getenv('QUICKBOOKS_CLIENT_ID')
        self.client_secret = os.getenv('QB_CLIENT_SECRET') or os.getenv('QUICKBOOKS_CLIENT_SECRET')
        self.realm_id = os.getenv('QB_REALM_ID') or os.getenv('QUICKBOOKS_REALM_ID')  # Company ID
        self.access_token = os.getenv('QB_ACCESS_TOKEN') or os.getenv('QUICKBOOKS_ACCESS_TOKEN')
        self.refresh_token = os.getenv('QB_REFRESH_TOKEN') or os.getenv('QUICKBOOKS_REFRESH_TOKEN')
        self.enabled = bool(self.client_id and self.client_secret and self.realm_id)
        
        self.base_url = "https://sandbox-quickbooks.api.intuit.com" if os.getenv('QUICKBOOKS_SANDBOX') == 'true' else "https://quickbooks.api.intuit.com"
        self.auth_url = "https://appcenter.intuit.com/connect/oauth2" if os.getenv('QUICKBOOKS_SANDBOX') != 'true' else "https://appcenter.intuit.com/connect/oauth2"
        
        if not self.enabled:
            logger.warning("QuickBooks credentials not configured. QuickBooks integration disabled.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        if not self.access_token:
            raise ValueError("QuickBooks access token not configured")
        
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the QuickBooks access token using refresh token."""
        if not self.refresh_token:
            return {"success": False, "error": "Refresh token not configured"}
        
        try:
            response = requests.post(
                f"{self.auth_url}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                # Optionally update refresh token if provided
                if 'refresh_token' in data:
                    self.refresh_token = data.get('refresh_token')
                
                logger.info("QuickBooks access token refreshed successfully")
                return {
                    "success": True,
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expires_in": data.get('expires_in')
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to refresh token: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error refreshing QuickBooks token: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the QuickBooks API connection."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}
        
        try:
            # Try to get company info
            response = requests.get(
                f"{self.base_url}/v3/company/{self.realm_id}/companyinfo/{self.realm_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                company_info = data.get('CompanyInfo', {})
                return {
                    "success": True,
                    "message": f"Connected to QuickBooks: {company_info.get('CompanyName', 'Unknown')}",
                    "company_name": company_info.get('CompanyName'),
                    "realm_id": self.realm_id
                }
            elif response.status_code == 401:
                # Token expired, try to refresh
                refresh_result = self.refresh_access_token()
                if refresh_result.get('success'):
                    # Retry the request
                    response = requests.get(
                        f"{self.base_url}/v3/company/{self.realm_id}/companyinfo/{self.realm_id}",
                        headers=self._get_headers()
                    )
                    if response.status_code == 200:
                        data = response.json()
                        company_info = data.get('CompanyInfo', {})
                        return {
                            "success": True,
                            "message": f"Connected to QuickBooks: {company_info.get('CompanyName', 'Unknown')}",
                            "company_name": company_info.get('CompanyName'),
                            "realm_id": self.realm_id,
                            "token_refreshed": True
                        }
                
                return {"success": False, "error": "Authentication failed. Token may be expired."}
            else:
                return {"success": False, "error": f"API error: {response.status_code} - {response.text[:200]}"}
                
        except Exception as e:
            logger.error(f"QuickBooks connection test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_customers(self, limit: int = 1000, start_position: int = 1) -> Dict[str, Any]:
        """Get all customers from QuickBooks."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}
        
        try:
            all_customers = []
            max_results = min(limit, 1000)  # QuickBooks max is 1000 per query
            position = start_position
            
            while True:
                # QuickBooks Query API
                query = f"SELECT * FROM Customer MAXRESULTS {max_results} STARTPOSITION {position}"
                
                response = requests.get(
                    f"{self.base_url}/v3/company/{self.realm_id}/query",
                    headers=self._get_headers(),
                    params={"query": query}
                )
                
                if response.status_code == 401:
                    # Token expired, try to refresh
                    refresh_result = self.refresh_access_token()
                    if not refresh_result.get('success'):
                        return {"success": False, "error": "Failed to refresh token"}
                    # Retry with new token
                    response = requests.get(
                        f"{self.base_url}/v3/company/{self.realm_id}/query",
                        headers=self._get_headers(),
                        params={"query": query}
                    )
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code} - {response.text[:200]}"
                    }
                
                data = response.json()
                query_response = data.get('QueryResponse', {})
                customers = query_response.get('Customer', [])
                
                # Handle single customer vs list
                if isinstance(customers, dict):
                    customers = [customers]
                
                all_customers.extend(customers)
                
                # Check if there are more results
                max_results_returned = query_response.get('maxResults', 0)
                if len(customers) < max_results_returned:
                    break
                
                position += len(customers)
                
                if len(all_customers) >= limit:
                    break
            
            return {
                "success": True,
                "customers": all_customers,
                "count": len(all_customers)
            }
            
        except Exception as e:
            logger.error(f"Failed to get QuickBooks customers: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def normalize_customer_data(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize QuickBooks customer data for Brevo/CRM."""
        # Extract name
        display_name = customer.get('DisplayName', '')
        given_name = customer.get('GivenName', '')
        family_name = customer.get('FamilyName', '')
        
        # Use GivenName/FamilyName if available, otherwise split DisplayName
        first_name = given_name or ''
        last_name = family_name or ''
        
        if not first_name and not last_name and display_name:
            # Split display name
            parts = display_name.split(' ', 1)
            first_name = parts[0] if parts else ''
            last_name = parts[1] if len(parts) > 1 else ''
        
        # Extract email from PrimaryEmailAddr or EmailAddr
        email = ''
        if customer.get('PrimaryEmailAddr'):
            email = customer.get('PrimaryEmailAddr', {}).get('Address', '').strip()
        elif customer.get('EmailAddr'):
            email = customer.get('EmailAddr', {}).get('Address', '').strip()
        
        # Extract phone
        phone = ''
        if customer.get('PrimaryPhone'):
            phone = customer.get('PrimaryPhone', {}).get('FreeFormNumber', '').strip()
        elif customer.get('Mobile'):
            phone = customer.get('Mobile', {}).get('FreeFormNumber', '').strip()
        
        # Extract company name
        company = customer.get('CompanyName', '') or display_name
        
        # Extract address
        address_parts = []
        if customer.get('BillAddr'):
            addr = customer.get('BillAddr', {})
            if addr.get('Line1'):
                address_parts.append(addr.get('Line1'))
            if addr.get('Line2'):
                address_parts.append(addr.get('Line2'))
            if addr.get('City'):
                address_parts.append(addr.get('City'))
            if addr.get('CountrySubDivisionCode'):  # State
                address_parts.append(addr.get('CountrySubDivisionCode'))
            if addr.get('PostalCode'):
                address_parts.append(addr.get('PostalCode'))
        address = ', '.join(address_parts) if address_parts else ''
        
        return {
            'qb_id': customer.get('Id'),
            'qb_sync_token': customer.get('SyncToken'),  # For tracking updates
            'email': email.lower().strip() if email else '',
            'first_name': first_name.strip(),
            'last_name': last_name.strip(),
            'name': f"{first_name} {last_name}".strip() or display_name,
            'company': company.strip(),
            'phone': phone.strip(),
            'address': address,
            'contact_type': 'client',  # All QuickBooks customers are clients
            'source': 'QuickBooks',
            'notes': f"QuickBooks Customer ID: {customer.get('Id')}"
        }

