#!/usr/bin/env python3
"""
Brevo (formerly Sendinblue) integration service.
Handles contact sync, tag management, and email campaigns.
"""

import os
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Tag mapping between CRM fields and Brevo list attributes
TAG_MAPPING = {
    # contact_type -> Brevo list/attribute
    'referral': 'Referral Source',
    'client': 'Client',
    'prospect': 'Prospect',
    # status -> Brevo attribute
    'hot': 'Hot Lead',
    'warm': 'Warm Lead', 
    'cold': 'Cold Lead',
}

REVERSE_TAG_MAPPING = {
    'Referral Source': ('contact_type', 'referral'),
    'Referral': ('contact_type', 'referral'),
    'Client': ('contact_type', 'client'),
    'Customer': ('contact_type', 'client'),
    'Prospect': ('contact_type', 'prospect'),
    'Hot Lead': ('status', 'hot'),
    'Hot': ('status', 'hot'),
    'Warm Lead': ('status', 'warm'),
    'Warm': ('status', 'warm'),
    'Cold Lead': ('status', 'cold'),
    'Cold': ('status', 'cold'),
}


class BrevoService:
    """Service for interacting with Brevo API."""
    
    def __init__(self):
        self.api_key = os.getenv('BREVO_API_KEY')
        self.enabled = bool(self.api_key)
        self.base_url = "https://api.brevo.com/v3"
        
        if not self.enabled:
            logger.warning("Brevo API key not configured. Brevo integration disabled.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self.api_key
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the Brevo API connection."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            response = requests.get(
                f"{self.base_url}/account",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": f"Connected to Brevo account: {data.get('companyName', 'Unknown')}",
                    "email": data.get('email'),
                    "plan": data.get('plan', [{}])[0].get('type', 'Unknown') if data.get('plan') else 'Free'
                }
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Brevo connection test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_all_contacts(self, limit: int = 1000) -> Dict[str, Any]:
        """Get all contacts from Brevo."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            all_contacts = []
            offset = 0
            
            while True:
                response = requests.get(
                    f"{self.base_url}/contacts",
                    headers=self._get_headers(),
                    params={"limit": min(limit, 50), "offset": offset}
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"API error: {response.status_code}"}
                
                data = response.json()
                contacts = data.get('contacts', [])
                all_contacts.extend(contacts)
                
                if len(contacts) < 50:
                    break
                    
                offset += 50
                
                if offset >= limit:
                    break
            
            return {"success": True, "contacts": all_contacts, "count": len(all_contacts)}
            
        except Exception as e:
            logger.error(f"Failed to get Brevo contacts: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def add_contact(self, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update a contact in Brevo."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        email = contact_info.get('email', '').strip().lower()
        if not email:
            return {"success": False, "error": "Email is required"}
        
        try:
            # Normalize first/last names - split if first_name contains full name
            first_name = contact_info.get('first_name', '').strip()
            last_name = contact_info.get('last_name', '').strip()
            
            # If first_name contains a space and last_name is empty, split it
            if first_name and ' ' in first_name and not last_name:
                parts = first_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''
            
            # Build attributes
            attributes = {}
            
            if first_name:
                attributes['FIRSTNAME'] = first_name
            if last_name:
                attributes['LASTNAME'] = last_name
            if contact_info.get('company'):
                attributes['COMPANY'] = contact_info['company']
            if contact_info.get('phone'):
                attributes['SMS'] = contact_info['phone']
            if contact_info.get('title'):
                attributes['TITLE'] = contact_info['title']
            if contact_info.get('address'):
                attributes['ADDRESS'] = contact_info['address']
            
            # Add CRM-specific attributes
            if contact_info.get('contact_type'):
                attributes['CONTACT_TYPE'] = contact_info['contact_type']
            if contact_info.get('status'):
                attributes['STATUS'] = contact_info['status']
            if contact_info.get('source'):
                attributes['SOURCE'] = contact_info['source']
            
            data = {
                "email": email,
                "attributes": attributes,
                "updateEnabled": True  # Update if exists
            }
            
            # Add to list if specified
            list_ids = contact_info.get('list_ids', [])
            if list_ids:
                data['listIds'] = list_ids
            
            response = requests.post(
                f"{self.base_url}/contacts",
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code in (200, 201, 204):
                logger.info(f"Added/updated contact in Brevo: {email}")
                return {"success": True, "email": email}
            elif response.status_code == 400:
                # Contact might already exist, try to update
                error_data = response.json()
                if 'duplicate' in str(error_data).lower():
                    return {"success": True, "email": email, "note": "Already exists"}
                return {"success": False, "error": error_data}
            else:
                return {"success": False, "error": f"API error: {response.status_code} - {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to add contact to Brevo: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def bulk_import_contacts(self, contacts: List[Dict[str, Any]], list_id: int = None) -> Dict[str, Any]:
        """Bulk import contacts to Brevo."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        if not contacts:
            return {"success": False, "error": "No contacts provided"}
        
        try:
            # Format contacts for Brevo bulk import
            formatted_contacts = []
            for c in contacts:
                email = c.get('email', '').strip().lower()
                if not email:
                    continue
                
                # Normalize first/last names - split if first_name contains full name
                first_name = (c.get('first_name') or '').strip()
                last_name = (c.get('last_name') or '').strip()
                
                # If first_name contains a space and last_name is empty, split it
                if first_name and ' ' in first_name and not last_name:
                    parts = first_name.split(' ', 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ''
                
                contact_data = {
                    "email": email,
                    "attributes": {}
                }
                
                if first_name:
                    contact_data['attributes']['FIRSTNAME'] = first_name
                if last_name:
                    contact_data['attributes']['LASTNAME'] = last_name
                if c.get('company'):
                    contact_data['attributes']['COMPANY'] = c['company']
                if c.get('phone'):
                    contact_data['attributes']['SMS'] = c['phone']
                if c.get('title'):
                    contact_data['attributes']['TITLE'] = c['title']
                if c.get('contact_type'):
                    contact_data['attributes']['CONTACT_TYPE'] = c['contact_type']
                if c.get('status'):
                    contact_data['attributes']['STATUS'] = c['status']
                if c.get('source'):
                    contact_data['attributes']['SOURCE'] = c['source']
                
                formatted_contacts.append(contact_data)
            
            # Brevo accepts up to 150 contacts per batch for inline import
            batch_size = 100
            total_added = 0
            total_updated = 0
            errors = []
            
            for i in range(0, len(formatted_contacts), batch_size):
                batch = formatted_contacts[i:i+batch_size]
                
                data = {
                    "jsonBody": batch,
                    "updateExistingContacts": True
                }
                
                if list_id:
                    data['listIds'] = [list_id]
                
                response = requests.post(
                    f"{self.base_url}/contacts/import",
                    headers=self._get_headers(),
                    json=data
                )
                
                if response.status_code in (200, 201, 202):
                    result = response.json() if response.text else {}
                    total_added += len(batch)
                    logger.info(f"Imported batch of {len(batch)} contacts to Brevo")
                else:
                    errors.append(f"Batch {i//batch_size + 1}: {response.status_code} - {response.text}")
            
            return {
                "success": len(errors) == 0,
                "added": total_added,
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"Bulk import to Brevo failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_lists(self) -> Dict[str, Any]:
        """Get all contact lists from Brevo."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            response = requests.get(
                f"{self.base_url}/contacts/lists",
                headers=self._get_headers(),
                params={"limit": 50}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "lists": data.get('lists', []), "count": data.get('count', 0)}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to get Brevo lists: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_list(self, name: str, folder_id: int = 1) -> Dict[str, Any]:
        """Create a new contact list in Brevo."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            response = requests.post(
                f"{self.base_url}/contacts/lists",
                headers=self._get_headers(),
                json={"name": name, "folderId": folder_id}
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                return {"success": True, "list_id": data.get('id'), "name": name}
            else:
                return {"success": False, "error": f"API error: {response.status_code} - {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to create Brevo list: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_attributes(self) -> Dict[str, Any]:
        """Create custom contact attributes for CRM data."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        attributes_to_create = [
            {"name": "TITLE", "type": "text"},
            {"name": "ADDRESS", "type": "text"},
            {"name": "CONTACT_TYPE", "type": "text"},  # referral, client, prospect
            {"name": "STATUS", "type": "text"},  # hot, warm, cold
            {"name": "SOURCE", "type": "text"},  # business card, mailchimp, manual
        ]
        
        created = []
        errors = []
        
        for attr in attributes_to_create:
            try:
                response = requests.post(
                    f"{self.base_url}/contacts/attributes/normal/{attr['name']}",
                    headers=self._get_headers(),
                    json={"type": attr['type']}
                )
                
                if response.status_code in (200, 201, 204):
                    created.append(attr['name'])
                elif response.status_code == 400 and 'already exists' in response.text.lower():
                    created.append(f"{attr['name']} (exists)")
                else:
                    errors.append(f"{attr['name']}: {response.status_code}")
                    
            except Exception as e:
                errors.append(f"{attr['name']}: {str(e)}")
        
        return {
            "success": len(errors) == 0,
            "created": created,
            "errors": errors if errors else None
        }
    
    def send_transactional_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        sender_name: str = "Colorado CareAssist",
        sender_email: str = None,
        to_name: str = None,
        reply_to: str = None
    ) -> Dict[str, Any]:
        """Send a transactional email to a single recipient."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            # Get sender email from account if not provided
            if not sender_email:
                account_info = self.test_connection()
                if account_info.get('success'):
                    sender_email = account_info.get('email')
                if not sender_email:
                    return {"success": False, "error": "No sender email configured"}
            
            data = {
                "sender": {
                    "name": sender_name,
                    "email": sender_email
                },
                "to": [{
                    "email": to_email,
                    "name": to_name or to_email
                }],
                "subject": subject,
                "htmlContent": html_content
            }
            
            if reply_to:
                data["replyTo"] = {"email": reply_to}
            
            response = requests.post(
                f"{self.base_url}/smtp/email",
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code in (200, 201):
                result = response.json()
                logger.info(f"Sent transactional email to {to_email}")
                return {
                    "success": True,
                    "message_id": result.get('messageId'),
                    "to": to_email
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Failed to send transactional email: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def send_newsletter_to_list(
        self,
        list_id: int,
        subject: str,
        html_content: str,
        sender_name: str = "Colorado CareAssist",
        sender_email: str = None,
        reply_to: str = None
    ) -> Dict[str, Any]:
        """Send a newsletter to all contacts in a list using transactional API."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            # Get list details
            lists_result = self.get_lists()
            if not lists_result.get("success"):
                return {"success": False, "error": "Failed to get lists"}
            
            target_list = next((l for l in lists_result.get("lists", []) if l.get("id") == list_id), None)
            if not target_list:
                return {"success": False, "error": f"List ID {list_id} not found"}
            
            # Get sender email from account if not provided
            if not sender_email:
                account_info = self.test_connection()
                if account_info.get('success'):
                    sender_email = account_info.get('email')
                if not sender_email:
                    return {"success": False, "error": "No sender email configured"}
            
            # Get all contacts from the list (with pagination)
            import time
            all_list_contacts = []
            offset = 0
            limit = 1000
            
            while True:
                response = requests.get(
                    f"{self.base_url}/contacts/lists/{list_id}/contacts",
                    headers=self._get_headers(),
                    params={"limit": limit, "offset": offset}
                )
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to get list contacts: {response.status_code} - {response.text[:200]}"
                    }
                
                list_data = response.json()
                contacts = list_data.get('contacts', [])
                all_list_contacts.extend(contacts)
                
                if len(contacts) < limit:
                    break
                
                offset += limit
                time.sleep(0.2)  # Rate limiting
            
            if not all_list_contacts:
                return {
                    "success": False,
                    "error": f"No contacts found in list '{target_list.get('name')}'"
                }
            
            # Send emails in batches (Brevo transactional API supports batch sending)
            batch_size = 50
            sent_count = 0
            errors = []
            
            for i in range(0, len(all_list_contacts), batch_size):
                batch = all_list_contacts[i:i+batch_size]
                
                # Prepare batch recipients
                recipients = []
                for c in batch:
                    email = c.get('email')
                    if not email:
                        continue
                    
                    attrs = c.get('attributes', {})
                    first_name = attrs.get('FIRSTNAME', '')
                    last_name = attrs.get('LASTNAME', '')
                    name = f"{first_name} {last_name}".strip() or email
                    
                    recipients.append({
                        "email": email,
                        "name": name
                    })
                
                if not recipients:
                    continue
                
                batch_data = {
                    "sender": {
                        "name": sender_name,
                        "email": sender_email
                    },
                    "to": recipients,
                    "subject": subject,
                    "htmlContent": html_content
                }
                
                if reply_to:
                    batch_data["replyTo"] = {"email": reply_to}
                
                batch_response = requests.post(
                    f"{self.base_url}/smtp/email",
                    headers=self._get_headers(),
                    json=batch_data
                )
                
                if batch_response.status_code in (200, 201):
                    sent_count += len(recipients)
                    logger.info(f"Sent batch {i//batch_size + 1}: {len(recipients)} emails")
                else:
                    error_msg = f"Batch {i//batch_size + 1}: {batch_response.status_code} - {batch_response.text[:200]}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                
                # Rate limiting - be nice to API
                if i + batch_size < len(all_list_contacts):
                    time.sleep(0.5)
            
            return {
                "success": len(errors) == 0,
                "sent": sent_count,
                "total": len(all_list_contacts),
                "list_name": target_list.get('name'),
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"Failed to send newsletter to list: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ===================================================================
    # CRM METHODS - Companies, Deals, Tasks, Pipeline
    # ===================================================================
    
    def create_or_update_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a company in Brevo CRM."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            # First try to find existing company by name
            name = company_data.get('name', '').strip()
            if not name:
                return {"success": False, "error": "Company name is required"}
            
            # Search for existing company
            search_response = requests.get(
                f"{self.base_url}/companies",
                headers=self._get_headers(),
                params={"name": name, "limit": 1}
            )
            
            company_id = None
            if search_response.status_code == 200:
                companies = search_response.json().get('companies', [])
                if companies:
                    company_id = companies[0].get('id')
            
            # Build company data
            data = {
                "name": name
            }
            
            # Add attributes if provided
            attributes = {}
            if company_data.get('email'):
                attributes['email'] = company_data['email']
            if company_data.get('phone'):
                attributes['phone'] = company_data['phone']
            if company_data.get('address'):
                attributes['address'] = company_data['address']
            if company_data.get('website'):
                attributes['website'] = company_data['website']
            if company_data.get('location'):
                attributes['location'] = company_data['location']
            if company_data.get('county'):
                attributes['county'] = company_data['county']
            if company_data.get('source_type'):
                attributes['source_type'] = company_data['source_type']
            if company_data.get('notes'):
                attributes['notes'] = company_data['notes']
            
            if attributes:
                data['attributes'] = attributes
            
            if company_id:
                # Update existing
                response = requests.patch(
                    f"{self.base_url}/companies/{company_id}",
                    headers=self._get_headers(),
                    json=data
                )
                action = "updated"
            else:
                # Create new
                response = requests.post(
                    f"{self.base_url}/companies",
                    headers=self._get_headers(),
                    json=data
                )
                action = "created"
            
            if response.status_code in (200, 201, 204):
                result = response.json() if response.text else {}
                return {
                    "success": True,
                    "action": action,
                    "company_id": result.get('id') or company_id,
                    "name": name
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text[:200]}"
                }
                
        except Exception as e:
            logger.error(f"Failed to create/update company in Brevo: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_or_update_deal(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a deal in Brevo CRM."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            name = deal_data.get('name', '').strip()
            if not name:
                return {"success": False, "error": "Deal name is required"}
            
            # Search for existing deal by name
            search_response = requests.get(
                f"{self.base_url}/crm/deals",
                headers=self._get_headers(),
                params={"name": name, "limit": 1}
            )
            
            deal_id = None
            if search_response.status_code == 200:
                deals = search_response.json().get('items', [])
                if deals:
                    deal_id = deals[0].get('id')
            
            # Build deal data
            data = {
                "name": name
            }
            
            # Add attributes
            attributes = {}
            if deal_data.get('amount'):
                attributes['amount'] = int(float(deal_data['amount']) * 100)  # Convert to cents
            if deal_data.get('category'):
                attributes['category'] = deal_data['category']
            if deal_data.get('description'):
                attributes['deal_notes'] = deal_data['description']
            
            if attributes:
                data['attributes'] = attributes
            
            # Add pipeline stage if provided
            if deal_data.get('stage'):
                # Map our stages to Brevo pipeline stages
                stage_mapping = {
                    'opportunity': 'open',
                    'proposal': 'open',
                    'negotiation': 'open',
                    'closed/won': 'won',
                    'closed/lost': 'lost'
                }
                brevo_stage = stage_mapping.get(deal_data['stage'].lower(), 'open')
                data['pipeline'] = brevo_stage
            
            # Link to company if provided
            if deal_data.get('company_id'):
                # We'd need to get Brevo company ID from our company_id
                # For now, we'll skip this - can be enhanced later
                pass
            
            if deal_id:
                # Update existing
                response = requests.patch(
                    f"{self.base_url}/crm/deals/{deal_id}",
                    headers=self._get_headers(),
                    json=data
                )
                action = "updated"
            else:
                # Create new
                response = requests.post(
                    f"{self.base_url}/crm/deals",
                    headers=self._get_headers(),
                    json=data
                )
                action = "created"
            
            if response.status_code in (200, 201, 204):
                result = response.json() if response.text else {}
                return {
                    "success": True,
                    "action": action,
                    "deal_id": result.get('id') or deal_id,
                    "name": name
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text[:200]}"
                }
                
        except Exception as e:
            logger.error(f"Failed to create/update deal in Brevo: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def sync_contact_to_crm(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync a contact to Brevo CRM (not just lists)."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            # First ensure contact is in Brevo (using existing add_contact method)
            result = self.add_contact(contact_data)
            if not result.get('success'):
                return result
            
            # Contacts in Brevo are automatically in CRM, so we're done
            return {
                "success": True,
                "message": "Contact synced to Brevo CRM",
                "email": contact_data.get('email')
            }
                
        except Exception as e:
            logger.error(f"Failed to sync contact to Brevo CRM: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_brevo_companies(self, limit: int = 100) -> Dict[str, Any]:
        """Get companies from Brevo CRM."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            response = requests.get(
                f"{self.base_url}/companies",
                headers=self._get_headers(),
                params={"limit": limit}
            )
            
            if response.status_code == 200:
                return {"success": True, "companies": response.json().get('companies', [])}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to get Brevo companies: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_brevo_deals(self, limit: int = 100) -> Dict[str, Any]:
        """Get deals from Brevo CRM."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            response = requests.get(
                f"{self.base_url}/crm/deals",
                headers=self._get_headers(),
                params={"limit": limit}
            )
            
            if response.status_code == 200:
                return {"success": True, "deals": response.json().get('items', [])}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to get Brevo deals: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_webhook(
        self,
        url: str,
        events: List[str],
        webhook_type: str = "marketing",
        description: str = None
    ) -> Dict[str, Any]:
        """
        Create a webhook in Brevo via API.
        
        Args:
            url: Webhook URL endpoint
            events: List of events to subscribe to. For marketing webhooks:
                    ['delivered', 'opened', 'click', 'hardBounce', 'softBounce', 'spam', 'unsubscribed', 'listAddition']
            webhook_type: Type of webhook - 'marketing', 'transactional', or 'inbound' (default: 'marketing')
            description: Optional description for the webhook
        
        Returns:
            Dict with success status and webhook ID if created
        """
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            payload = {
                "url": url,
                "events": events,
                "type": webhook_type
            }
            
            if description:
                payload["description"] = description
            
            response = requests.post(
                f"{self.base_url}/webhooks",
                headers=self._get_headers(),
                json=payload
            )
            
            if response.status_code == 201:
                data = response.json()
                webhook_id = data.get('id')
                logger.info(f"Created Brevo webhook {webhook_id} for URL: {url}")
                return {
                    "success": True,
                    "webhook_id": webhook_id,
                    "url": url,
                    "events": events,
                    "type": webhook_type
                }
            else:
                error_text = response.text
                logger.error(f"Failed to create webhook: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {error_text}"
                }
                
        except Exception as e:
            logger.error(f"Failed to create webhook: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_webhooks(self) -> Dict[str, Any]:
        """Get all webhooks configured in Brevo."""
        if not self.enabled:
            return {"success": False, "error": "Brevo not configured"}
        
        try:
            response = requests.get(
                f"{self.base_url}/webhooks",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "webhooks": data.get('webhooks', [])}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to get webhooks: {str(e)}")
            return {"success": False, "error": str(e)}


# Convenience function for quick testing
def test_brevo():
    """Test Brevo connection."""
    service = BrevoService()
    result = service.test_connection()
    print(f"Connection test: {result}")
    
    if result.get('success'):
        # Create custom attributes
        print("\nCreating custom attributes...")
        attr_result = service.create_attributes()
        print(f"Attributes: {attr_result}")
        
        # Get lists
        print("\nGetting lists...")
        lists_result = service.get_lists()
        print(f"Lists: {lists_result}")
    
    return result


if __name__ == "__main__":
    test_brevo()

