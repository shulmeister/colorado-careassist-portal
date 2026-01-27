"""
Apple Contacts Lookup via Mac Node
Queries Apple Contacts on Jason's Mac for caller ID
"""

import requests
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Gateway/node configuration
GATEWAY_URL = "https://gateway.clawd.io"  # Adjust if needed
MAC_NODE_ID = "46b7c9e5761d01f5737fc755e0a925b28ef1ea324426e8c8b32a000a1ca92cfc"

def lookup_contact_by_phone(phone: str, gateway_token: Optional[str] = None) -> Optional[Dict]:
    """
    Look up a contact in Apple Contacts by phone number via Mac node
    
    Args:
        phone: Phone number to look up (any format)
        gateway_token: Optional gateway auth token
        
    Returns:
        Dict with contact info if found, None otherwise
        Example: {"name": "Jennifer Smith", "phone": "+16039971495", "email": "..."}
    """
    try:
        # Clean phone number - extract last 10 digits
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]
        
        # Format for AppleScript search (various formats)
        search_formats = [
            f"({clean_phone[:3]}) {clean_phone[3:6]}-{clean_phone[6:]}",
            f"{clean_phone[:3]}-{clean_phone[3:6]}-{clean_phone[6:]}",
            f"+1{clean_phone}",
            clean_phone
        ]
        
        # AppleScript to search contacts
        applescript = f"""
tell application "Contacts"
    set foundPeople to {{}}
    set phoneNumbers to {{"{search_formats[0]}", "{search_formats[1]}", "{search_formats[2]}", "{search_formats[3]}"}}
    
    repeat with phoneNum in phoneNumbers
        set matches to (every person whose (phone contains phoneNum))
        if (count of matches) > 0 then
            set foundPeople to matches
            exit repeat
        end if
    end repeat
    
    if (count of foundPeople) > 0 then
        set thePerson to item 1 of foundPeople
        set personName to name of thePerson
        
        -- Get first phone number
        set personPhone to ""
        try
            set phonesList to phones of thePerson
            if (count of phonesList) > 0 then
                set personPhone to value of item 1 of phonesList
            end if
        end try
        
        -- Get first email
        set personEmail to ""
        try
            set emailsList to emails of thePerson
            if (count of emailsList) > 0 then
                set personEmail to value of item 1 of emailsList
            end if
        end try
        
        return personName & "|" & personPhone & "|" & personEmail
    else
        return "NOT_FOUND"
    end if
end tell
"""
        
        # Execute via node (you'll need to implement the actual node call)
        # For now, this is a placeholder that would call the Mac node
        # TODO: Integrate with clawdbot node API
        
        logger.info(f"Looking up {clean_phone} in Apple Contacts via Mac node")
        
        # Placeholder response - in production this would query the Mac node
        # The actual implementation would use the nodes API or exec command
        
        return None  # Not implemented yet - need Mac node connection
        
    except Exception as e:
        logger.error(f"Apple Contacts lookup failed: {e}")
        return None


def is_jason(phone: str) -> bool:
    """Quick check if the caller is Jason"""
    clean = ''.join(filter(str.isdigit, phone))[-10:]
    return clean == "6039971495"  # Jason's number
