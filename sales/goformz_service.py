#!/usr/bin/env python3
"""
GoFormz API integration service.
Handles form completion detection and syncing to Brevo.
"""

import os
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GoFormzService:
    """Service for interacting with GoFormz API."""
    
    def __init__(self):
        self.client_id = os.getenv('GOFORMZ_CLIENT_ID')
        self.client_secret = os.getenv('GOFORMZ_CLIENT_SECRET')
        self.enabled = bool(self.client_id and self.client_secret)
        
        # GoFormz API uses OAuth 2.0 with client_id:client_secret
        # Base URL may vary - trying common patterns
        # v1 API is more stable for authentication
        self.base_url = "https://api.goformz.com/v1"
        # GoFormz OAuth endpoint is at accounts.goformz.com, not api.goformz.com
        self.auth_url = "https://accounts.goformz.com/connect/token"
        
        self.access_token = None
        self.token_expires_at = None
        
        # Cache for form IDs to reduce API calls
        self._form_id_cache = {}
        
        if not self.enabled:
            logger.warning("GoFormz credentials not configured. GoFormz integration disabled.")
    
    def _get_access_token(self) -> str:
        """Get or refresh GoFormz access token."""
        # Check if we have a valid token
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        # Try multiple authentication methods
        # Method 1: OAuth with Basic Auth
        try:
            import base64
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            response = requests.post(
                self.auth_url,
                data={
                    "grant_type": "client_credentials"
                },
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                expires_in = data.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info("GoFormz access token obtained")
                return self.access_token
            else:
                # Try alternative: Basic Auth directly for API calls
                logger.warning(f"OAuth failed ({response.status_code}), will try Basic Auth for API calls")
                self.access_token = auth_b64  # Store Basic Auth string
                self.token_expires_at = datetime.now() + timedelta(days=365)  # Basic Auth doesn't expire
                return self.access_token
                
        except Exception as e:
            logger.error(f"Error getting GoFormz token: {str(e)}")
            # Fallback: use Basic Auth directly
            try:
                import base64
                auth_string = f"{self.client_id}:{self.client_secret}"
                auth_bytes = auth_string.encode('ascii')
                auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
                self.access_token = auth_b64
                self.token_expires_at = datetime.now() + timedelta(days=365)
                return self.access_token
            except:
                raise
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        token = self._get_access_token()
        # Check if it's a Bearer token or Basic Auth
        if token.startswith('eyJ'):  # JWT tokens typically start with 'eyJ'
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else:
            # Basic Auth
            return {
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the GoFormz API connection."""
        if not self.enabled:
            return {"success": False, "error": "GoFormz not configured"}
        
        try:
            # Try to get forms list to test connection
            response = requests.get(
                f"{self.base_url}/forms",
                headers=self._get_headers(),
                params={"limit": 1}
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Connected to GoFormz API"
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text[:200]}"
                }
                
        except Exception as e:
            logger.error(f"GoFormz connection test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_forms(self, limit: int = 100) -> Dict[str, Any]:
        """Get all forms from GoFormz."""
        if not self.enabled:
            return {"success": False, "error": "GoFormz not configured"}
        
        try:
            response = requests.get(
                f"{self.base_url}/forms",
                headers=self._get_headers(),
                params={"limit": limit}
            )
            
            if response.status_code == 200:
                return {"success": True, "forms": response.json()}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to get GoFormz forms: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_form_submissions(self, form_id: str = None, form_name: str = None, limit: int = 100, since: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get form submissions from GoFormz.
        Can filter by form_id, form_name, or get all recent submissions.
        """
        if not self.enabled:
            return {"success": False, "error": "GoFormz not configured"}
        
        try:
            params = {"limit": limit}
            
            # If form_id provided, use it
            if form_id:
                params["formId"] = form_id
            elif form_name:
                # Check cache first
                if form_name in self._form_id_cache:
                    params["formId"] = self._form_id_cache[form_name]
                else:
                    # First find form by name
                    forms_result = self.get_forms(limit=1000)
                    if forms_result.get('success'):
                        forms = forms_result.get('forms', {}).get('data', [])
                        # Populate cache
                        for f in forms:
                            self._form_id_cache[f.get('name', '')] = f.get('id')
                            
                        matching_form = next((f for f in forms if f.get('name', '').lower() == form_name.lower()), None)
                        if matching_form:
                            params["formId"] = matching_form.get('id')
                            self._form_id_cache[form_name] = matching_form.get('id')
                        else:
                            return {"success": False, "error": f"Form '{form_name}' not found"}
            
            # Add date filter if provided
            if since:
                params["modifiedSince"] = since.isoformat()
            
            response = requests.get(
                f"{self.base_url}/submissions",
                headers=self._get_headers(),
                params=params
            )
            
            if response.status_code == 200:
                return {"success": True, "submissions": response.json()}
            else:
                return {"success": False, "error": f"API error: {response.status_code} - {response.text[:200]}"}
                
        except Exception as e:
            logger.error(f"Failed to get GoFormz submissions: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_completed_client_packets(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get completed Client Packet submissions.
        Looks for forms with "Client Packet" in the name that are completed.
        """
        if not self.enabled:
            return {"success": False, "error": "GoFormz not configured"}
        
        try:
            client_packet_ids = []
            
            # Check if we have cached IDs for 'Client Packet'
            cached_ids = [fid for name, fid in self._form_id_cache.items() if 'client packet' in name.lower()]
            
            if cached_ids:
                client_packet_ids = cached_ids
            else:
                # Get all forms to find Client Packet
                forms_result = self.get_forms(limit=1000)
                if not forms_result.get('success'):
                    return forms_result
                
                forms = forms_result.get('forms', {}).get('data', [])
                # Update cache
                for f in forms:
                    self._form_id_cache[f.get('name', '')] = f.get('id')
                    
                client_packet_forms = [f for f in forms if 'client packet' in f.get('name', '').lower()]
                client_packet_ids = [f.get('id') for f in client_packet_forms]
            
            if not client_packet_ids:
                return {"success": True, "submissions": [], "message": "No Client Packet forms found"}
            
            # Get submissions for all Client Packet forms
            all_submissions = []
            for form_id in client_packet_ids:
                submissions_result = self.get_form_submissions(form_id=form_id, limit=1000, since=since)
                if submissions_result.get('success'):
                    submissions = submissions_result.get('submissions', {}).get('data', [])
                    # Filter for completed submissions
                    completed = [s for s in submissions if s.get('status', '').lower() in ['completed', 'submitted', 'signed']]
                    all_submissions.extend(completed)
            
            return {"success": True, "submissions": all_submissions}
            
        except Exception as e:
            logger.error(f"Failed to get completed client packets: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def extract_customer_data_from_submission(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract customer data from a GoFormz submission.
        Looks for common fields like name, email, phone, etc.
        """
        # GoFormz submissions have a 'data' field with form field values
        form_data = submission.get('data', {})
        
        # Common field name variations
        email = (
            form_data.get('email') or 
            form_data.get('Email') or 
            form_data.get('EMAIL') or
            form_data.get('client_email') or
            form_data.get('Client Email') or
            form_data.get('email_address') or
            ''
        ).strip()
        
        first_name = (
            form_data.get('first_name') or 
            form_data.get('First Name') or 
            form_data.get('FIRST_NAME') or
            form_data.get('firstName') or
            form_data.get('fname') or
            ''
        ).strip()
        
        last_name = (
            form_data.get('last_name') or 
            form_data.get('Last Name') or 
            form_data.get('LAST_NAME') or
            form_data.get('lastName') or
            form_data.get('lname') or
            ''
        ).strip()
        
        # If we have a full name field, try to split it
        if not first_name and not last_name:
            full_name = (
                form_data.get('name') or 
                form_data.get('Name') or 
                form_data.get('NAME') or
                form_data.get('client_name') or
                form_data.get('Client Name') or
                ''
            ).strip()
            if full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0] if parts else ''
                last_name = parts[1] if len(parts) > 1 else ''
        
        phone = (
            form_data.get('phone') or 
            form_data.get('Phone') or 
            form_data.get('PHONE') or
            form_data.get('phone_number') or
            form_data.get('Phone Number') or
            form_data.get('mobile') or
            ''
        ).strip()
        
        address = (
            form_data.get('address') or 
            form_data.get('Address') or 
            form_data.get('ADDRESS') or
            form_data.get('street_address') or
            ''
        ).strip()
        
        return {
            'email': email.lower() if email else '',
            'first_name': first_name,
            'last_name': last_name,
            'name': f"{first_name} {last_name}".strip() or email,
            'phone': phone,
            'address': address,
            'contact_type': 'client',
            'source': 'GoFormz Client Packet',
            'notes': f"Completed Client Packet on {submission.get('completedDate', submission.get('modifiedDate', 'Unknown'))}"
        }

