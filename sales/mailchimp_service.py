import requests
import logging
from typing import Dict, Any, Optional, List
import os

logger = logging.getLogger(__name__)

# Tag mapping between Dashboard and Mailchimp
TAG_MAPPING = {
    # contact_type → Mailchimp tag
    "contact_type": {
        "referral": "Referral Source",
        "client": "Customer",           # Mailchimp uses "Customer" not "Client"
        "customer": "Customer",
        "prospect": "Prospect",
    },
    # status → Mailchimp tag
    "status": {
        "hot": "Hot Lead",
        "warm": "Warm Lead",
        "cold": "Cold Lead",
    }
}

# Reverse mapping for imports (Mailchimp tag → dashboard field)
REVERSE_TAG_MAPPING = {
    "Referral Source": ("contact_type", "referral"),
    "Customer": ("contact_type", "client"),           # Map "Customer" to "client"
    "QuickBooks Customer": ("contact_type", "client"), # Also map QB customers
    "Client": ("contact_type", "client"),             # In case it exists
    "Prospect": ("contact_type", "prospect"),
    "Hot Lead": ("status", "hot"),
    "Warm Lead": ("status", "warm"),
    "Cold Lead": ("status", "cold"),
}


class MailchimpService:
    """Service for integrating with Mailchimp API with proper tag mapping"""
    
    def __init__(self):
        self.api_key = os.getenv('MAILCHIMP_API_KEY')
        self.server_prefix = os.getenv('MAILCHIMP_SERVER_PREFIX')  # e.g., 'us1', 'us2', etc.
        self.list_id = os.getenv('MAILCHIMP_LIST_ID')
        
        if not all([self.api_key, self.server_prefix, self.list_id]):
            logger.warning("Mailchimp credentials not configured. Export functionality will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            self.base_url = f"https://{self.server_prefix}.api.mailchimp.com/3.0"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def _build_tags_for_mailchimp(self, contact_info: Dict[str, Any]) -> List[str]:
        """
        Build Mailchimp tags from contact info.
        Maps contact_type and status to appropriate Mailchimp tags.
        """
        tags = []
        
        # Map contact_type to Mailchimp tag
        contact_type = contact_info.get('contact_type', '').lower()
        if contact_type and contact_type in TAG_MAPPING['contact_type']:
            tags.append(TAG_MAPPING['contact_type'][contact_type])
        
        # Map status to Mailchimp tag
        status = contact_info.get('status', '').lower()
        if status and status in TAG_MAPPING['status']:
            tags.append(TAG_MAPPING['status'][status])
        
        # Add any custom tags from the contact
        custom_tags = contact_info.get('tags', [])
        if isinstance(custom_tags, str):
            import json
            try:
                custom_tags = json.loads(custom_tags)
            except:
                custom_tags = [t.strip() for t in custom_tags.split(',') if t.strip()]
        
        if isinstance(custom_tags, list):
            for tag in custom_tags:
                if tag and tag not in tags:
                    tags.append(tag)
        
        return tags
    
    def _parse_mailchimp_tags(self, mailchimp_tags: List[Dict]) -> Dict[str, Any]:
        """
        Parse Mailchimp tags back to dashboard fields.
        Returns dict with contact_type, status, and remaining tags.
        """
        result = {
            'contact_type': None,
            'status': None,
            'tags': []
        }
        
        for tag_obj in mailchimp_tags:
            tag_name = tag_obj.get('name', '') if isinstance(tag_obj, dict) else str(tag_obj)
            
            if tag_name in REVERSE_TAG_MAPPING:
                field, value = REVERSE_TAG_MAPPING[tag_name]
                result[field] = value
            else:
                # Keep as custom tag
                if tag_name:
                    result['tags'].append(tag_name)
        
        return result
    
    def add_contact(self, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update a contact in Mailchimp list with proper tags"""
        if not self.enabled:
            return {
                "success": False,
                "error": "Mailchimp not configured"
            }
        
        # Generic email prefixes that indicate company/team emails
        GENERIC_EMAIL_PREFIXES = {
            'info', 'team', 'admin', 'contact', 'hello', 'support', 'sales',
            'office', 'help', 'service', 'marketing', 'billing', 'hr',
            'careers', 'jobs', 'press', 'media', 'general', 'mail', 'enquiries',
            'inquiries', 'reception', 'feedback', 'customerservice'
            }
        
        try:
            email = contact_info.get('email', '').strip()
            if not email:
                return {
                    "success": False,
                    "error": "Email address is required for Mailchimp export"
                }
            
            first_name = (contact_info.get('first_name') or '').strip()
            last_name = (contact_info.get('last_name') or '').strip()
            company = (contact_info.get('company') or '').strip()
            
            # Check if this is a generic email (info@, team@, etc.)
            email_prefix = email.split('@')[0].lower() if '@' in email else ''
            is_generic_email = email_prefix in GENERIC_EMAIL_PREFIXES
            
            # If no first name and (generic email OR no name at all), use company name
            if not first_name and (is_generic_email or not last_name):
                if company:
                    # Split company name: first word = first name, rest = last name
                    company_words = company.split()
                    if len(company_words) >= 2:
                        first_name = company_words[0]
                        last_name = ' '.join(company_words[1:])
                    elif len(company_words) == 1:
                        first_name = company_words[0]
            
            # Build merge fields
            merge_fields = {}
            
            if first_name:
                merge_fields['FNAME'] = first_name
            if last_name:
                merge_fields['LNAME'] = last_name
            if company:
                merge_fields['COMPANY'] = company
            
            phone = (contact_info.get('phone') or '').strip()
            if phone and len(phone) >= 10:
                merge_fields['PHONE'] = phone
            
            address = (contact_info.get('address') or '').strip()
            if address and len(address) > 10:
                merge_fields['ADDRESS'] = address
            
            website = (contact_info.get('website') or '').strip()
            if website and '.' in website and len(website) > 5:
                merge_fields['WEBSITE'] = website
            
            # Build tags from contact_type, status, and custom tags
            tags = self._build_tags_for_mailchimp(contact_info)
            
            data = {
                "email_address": email,
                "status": "subscribed",
                "merge_fields": merge_fields
            }
            
            if tags:
                data['tags'] = tags
            
            # Use PUT with subscriber hash for upsert behavior
            import hashlib
            subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
            url = f"{self.base_url}/lists/{self.list_id}/members/{subscriber_hash}"
            
            # Try PUT first (upsert)
            data['status_if_new'] = 'subscribed'
            response = requests.put(url, json=data, headers=self._get_headers())
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully synced contact to Mailchimp: {email} with tags: {tags}")
                return {
                    "success": True,
                    "message": f"Contact {email} synced to Mailchimp with tags: {', '.join(tags) if tags else 'none'}",
                    "mailchimp_id": response.json().get('id'),
                    "tags_applied": tags
                }
            else:
                error_data = response.json()
                logger.error(f"Mailchimp error: {error_data}")
                return {
                    "success": False,
                    "error": f"Mailchimp error: {error_data.get('detail', response.text)}"
                }
                
        except Exception as e:
            logger.error(f"Error syncing contact to Mailchimp: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to sync contact to Mailchimp: {str(e)}"
            }
    
    def update_contact_tags(self, email: str, tags_to_add: List[str] = None, tags_to_remove: List[str] = None) -> Dict[str, Any]:
        """Update tags for an existing contact"""
        if not self.enabled:
            return {"success": False, "error": "Mailchimp not configured"}
        
        try:
            import hashlib
            subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
            url = f"{self.base_url}/lists/{self.list_id}/members/{subscriber_hash}/tags"
            
            tag_updates = []
            
            if tags_to_add:
                for tag in tags_to_add:
                    tag_updates.append({"name": tag, "status": "active"})
            
            if tags_to_remove:
                for tag in tags_to_remove:
                    tag_updates.append({"name": tag, "status": "inactive"})
            
            if not tag_updates:
                return {"success": True, "message": "No tag changes"}
            
            response = requests.post(url, json={"tags": tag_updates}, headers=self._get_headers())
            
            if response.status_code in [200, 204]:
                    return {
                    "success": True,
                    "message": f"Tags updated for {email}",
                    "added": tags_to_add or [],
                    "removed": tags_to_remove or []
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to update tags: {response.text}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_segment_members(self, segment_name: str = "Referral Source") -> List[Dict[str, Any]]:
        """Get all members from a specific segment"""
        if not self.enabled:
            logger.warning("Mailchimp not configured")
            return []
        
        try:
            # First, get all segments
            url = f"{self.base_url}/lists/{self.list_id}/segments"
            response = requests.get(url, headers=self._get_headers(), params={'count': 1000})
            
            if response.status_code != 200:
                logger.error(f"Failed to get segments: {response.status_code}")
                return []
            
            segments = response.json().get('segments', [])
            target_segment = None
            
            for segment in segments:
                if segment.get('name', '').lower() == segment_name.lower():
                    target_segment = segment
                    break
            
            if not target_segment:
                logger.warning(f"Segment '{segment_name}' not found")
                return []
            
            segment_id = target_segment.get('id')
            logger.info(f"Found segment '{segment_name}' with ID: {segment_id}")
            
            # Get all members
            members_url = f"{self.base_url}/lists/{self.list_id}/segments/{segment_id}/members"
            all_members = []
            offset = 0
            count = 1000
            
            while True:
                params = {'count': count, 'offset': offset}
                members_response = requests.get(members_url, headers=self._get_headers(), params=params)
                
                if members_response.status_code != 200:
                    break
                
                data = members_response.json()
                members = data.get('members', [])
                
                if not members:
                    break
                
                all_members.extend(members)
                
                if len(all_members) >= data.get('total_items', 0):
                    break
                
                offset += count
            
            logger.info(f"Retrieved {len(all_members)} members from segment '{segment_name}'")
            return all_members
            
        except Exception as e:
            logger.error(f"Error getting segment members: {str(e)}")
            return []
    
    def get_tagged_members(self, tag_name: str) -> List[Dict[str, Any]]:
        """Get all members with a specific tag"""
        if not self.enabled:
            return []
        
        try:
            # Use segment search with tag filter
            url = f"{self.base_url}/lists/{self.list_id}/members"
            all_members = []
            offset = 0
            count = 1000
            
            while True:
                params = {
                    'count': count,
                    'offset': offset,
                    'fields': 'members.email_address,members.merge_fields,members.tags,members.id'
                }
                response = requests.get(url, headers=self._get_headers(), params=params)
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                members = data.get('members', [])
                
                if not members:
                    break
                
                # Filter by tag
                for member in members:
                    member_tags = [t.get('name', '') for t in member.get('tags', [])]
                    if tag_name in member_tags:
                        all_members.append(member)
                
                if offset + count >= data.get('total_items', 0):
                    break
                
                offset += count
            
            return all_members
            
        except Exception as e:
            logger.error(f"Error getting tagged members: {str(e)}")
            return []
    
    def sync_from_mailchimp(self, tag_filter: str = None) -> Dict[str, Any]:
        """
        Pull contacts from Mailchimp and return them with proper field mapping.
        Use tag_filter to only get contacts with a specific tag (e.g., "Referral Source", "Client")
        """
        if not self.enabled:
            return {"success": False, "error": "Mailchimp not configured", "contacts": []}
        
        try:
            if tag_filter:
                members = self.get_tagged_members(tag_filter)
            else:
                # Get all members
                url = f"{self.base_url}/lists/{self.list_id}/members"
                members = []
                offset = 0
                
                while True:
                    params = {'count': 1000, 'offset': offset}
                    response = requests.get(url, headers=self._get_headers(), params=params)
                    if response.status_code != 200:
                        break
                    data = response.json()
                    batch = data.get('members', [])
                    if not batch:
                        break
                    members.extend(batch)
                    if len(members) >= data.get('total_items', 0):
                        break
                    offset += 1000
            
            # Generic email prefixes that indicate company/team emails, not personal
            GENERIC_EMAIL_PREFIXES = {
                'info', 'team', 'admin', 'contact', 'hello', 'support', 'sales',
                'office', 'help', 'service', 'marketing', 'billing', 'hr',
                'careers', 'jobs', 'press', 'media', 'general', 'mail', 'enquiries',
                'inquiries', 'reception', 'feedback', 'customerservice'
            }
            
            contacts = []
            for member in members:
                merge = member.get('merge_fields', {})
                tags_parsed = self._parse_mailchimp_tags(member.get('tags', []))
                
                email = member.get('email_address', '') or ''
                first_name = (merge.get('FNAME', '') or '').strip()
                last_name = (merge.get('LNAME', '') or '').strip()
                company = (merge.get('COMPANY', '') or '').strip()
                
                # Check if this is a generic email (info@, team@, etc.)
                email_prefix = email.split('@')[0].lower() if '@' in email else ''
                is_generic_email = email_prefix in GENERIC_EMAIL_PREFIXES
                
                # If no first name and (generic email OR no name at all), use company name
                if not first_name and (is_generic_email or not last_name):
                    if company:
                        # Split company name: first word = first name, rest = last name
                        company_words = company.split()
                        if len(company_words) >= 2:
                            first_name = company_words[0]
                            last_name = ' '.join(company_words[1:])
                        elif len(company_words) == 1:
                            first_name = company_words[0]
                            last_name = ''
                
                # Build full name
                name = f"{first_name} {last_name}".strip()
                if not name:
                    # Last resort: use email prefix
                    name = email.split('@')[0] if '@' in email else email
                
                # Handle address - can be dict or string
                address_field = merge.get('ADDRESS', '')
                if isinstance(address_field, dict):
                    address = address_field.get('addr1', '') or ''
                else:
                    address = str(address_field) if address_field else ''
                
                contact = {
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'name': name,
                    'company': company,
                    'phone': (merge.get('PHONE', '') or '').strip(),
                    'address': address,
                    'website': (merge.get('WEBSITE', '') or '').strip(),
                    'contact_type': tags_parsed.get('contact_type'),
                    'status': tags_parsed.get('status'),
                    'tags': tags_parsed.get('tags', []),
                    'mailchimp_id': member.get('id'),
                }
                contacts.append(contact)
            
            return {
                "success": True,
                "contacts": contacts,
                "count": len(contacts),
                "filter": tag_filter
            }
            
        except Exception as e:
            logger.error(f"Error syncing from Mailchimp: {str(e)}")
            return {"success": False, "error": str(e), "contacts": []}
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Mailchimp API connection"""
        if not self.enabled:
            return {
                "success": False,
                "error": "Mailchimp not configured"
            }
        
        try:
            url = f"{self.base_url}/lists/{self.list_id}"
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                list_info = response.json()
                return {
                    "success": True,
                    "message": f"Connected to Mailchimp list: {list_info.get('name', 'Unknown')}",
                    "list_name": list_info.get('name'),
                    "member_count": list_info.get('stats', {}).get('member_count', 0)
                }
            else:
                return {
                    "success": False,
                    "error": f"Mailchimp API error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error testing Mailchimp connection: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to connect to Mailchimp: {str(e)}"
            }
