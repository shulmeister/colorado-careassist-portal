#!/usr/bin/env python3
"""
Helper script to send newsletter to referral sources in Brevo.

Usage:
    python send_newsletter.py --test              # Test Brevo connection and list lists
    python send_newsletter.py --list-id 123       # Send newsletter to list ID 123
    python send_newsletter.py --referral-sources  # Send to referral sources list (auto-detects)
"""

import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brevo_service import BrevoService


def test_connection_and_lists():
    """Test Brevo connection and display all lists."""
    print("Testing Brevo connection...")
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("❌ ERROR: Brevo not configured. Set BREVO_API_KEY environment variable.")
        return False
    
    # Test connection
    result = brevo.test_connection()
    if result.get('success'):
        print(f"✅ Connected to Brevo!")
        print(f"   Account: {result.get('message', '').split('account: ')[-1] if 'account:' in result.get('message', '') else 'Unknown'}")
        print(f"   Email: {result.get('email', 'N/A')}")
        print(f"   Plan: {result.get('plan', 'N/A')}")
    else:
        print(f"❌ Connection failed: {result.get('error')}")
        return False
    
    # Get lists
    print("\n📋 Available Lists:")
    lists_result = brevo.get_lists()
    if lists_result.get('success'):
        lists = lists_result.get('lists', [])
        if lists:
            for lst in lists:
                print(f"   ID: {lst.get('id')} | Name: {lst.get('name')} | Contacts: {lst.get('uniqueSubscribers', 0)}")
        else:
            print("   No lists found")
    else:
        print(f"   Error getting lists: {lists_result.get('error')}")
    
    return True


def send_newsletter(list_id=None, list_name_filter=None, subject=None, month=None):
    """Send newsletter to a list."""
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("❌ ERROR: Brevo not configured. Set BREVO_API_KEY environment variable.")
        return False
    
    # Get lists to find the target list
    lists_result = brevo.get_lists()
    if not lists_result.get('success'):
        print(f"❌ Error getting lists: {lists_result.get('error')}")
        return False
    
    lists = lists_result.get('lists', [])
    
    # Find target list
    target_list = None
    if list_id:
        target_list = next((l for l in lists if l.get('id') == list_id), None)
    elif list_name_filter:
        # Search for list by name (case-insensitive, partial match)
        for lst in lists:
            if list_name_filter.lower() in lst.get('name', '').lower():
                target_list = lst
                break
    
    if not target_list:
        print("❌ List not found. Available lists:")
        for lst in lists:
            print(f"   ID: {lst.get('id')} | Name: {lst.get('name')}")
        return False
    
    list_id = target_list.get('id')
    list_name = target_list.get('name')
    contact_count = target_list.get('uniqueSubscribers', 0)
    
    print(f"\n📧 Sending newsletter to: {list_name}")
    print(f"   List ID: {list_id}")
    print(f"   Contacts: {contact_count}")
    
    if contact_count == 0:
        print("⚠️  Warning: List has 0 contacts!")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Load template
    template_path = os.path.join(os.path.dirname(__file__), "newsletter_template.html")
    if not os.path.exists(template_path):
        print(f"❌ Newsletter template not found: {template_path}")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Set month
    if not month:
        month = datetime.now().strftime("%B %Y")
    html_content = html_content.replace("{{MONTH}}", month)
    
    # Get subject
    if not subject:
        subject = f"Colorado CareAssist Newsletter - {month}"
    
    print(f"\n📝 Subject: {subject}")
    print(f"📅 Month: {month}")
    
    # Confirm
    print(f"\n⚠️  About to send newsletter to {contact_count} contacts in '{list_name}'")
    response = input("Continue? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return False
    
    # Send
    print("\n📤 Sending newsletter...")
    result = brevo.send_newsletter_to_list(
        list_id=list_id,
        subject=subject,
        html_content=html_content,
        sender_name="Colorado CareAssist"
    )
    
    if result.get('success'):
        print(f"\n✅ Newsletter sent successfully!")
        print(f"   Sent: {result.get('sent')} / {result.get('total')}")
        print(f"   List: {result.get('list_name')}")
        return True
    else:
        print(f"\n❌ Failed to send newsletter: {result.get('error')}")
        if result.get('errors'):
            print("   Errors:")
            for err in result.get('errors', []):
                print(f"     - {err}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Send newsletter to Brevo lists')
    parser.add_argument('--test', action='store_true', help='Test connection and list all lists')
    parser.add_argument('--list-id', type=int, help='List ID to send to')
    parser.add_argument('--referral-sources', action='store_true', help='Send to referral sources list (auto-detects)')
    parser.add_argument('--subject', type=str, help='Email subject (default: auto-generated)')
    parser.add_argument('--month', type=str, help='Month name for template (default: current month)')
    
    args = parser.parse_args()
    
    if args.test:
        test_connection_and_lists()
    elif args.list_id:
        send_newsletter(list_id=args.list_id, subject=args.subject, month=args.month)
    elif args.referral_sources:
        send_newsletter(list_name_filter='referral', subject=args.subject, month=args.month)
    else:
        print("Use --test to see available lists, or --list-id <id> to send newsletter")
        print("Use --referral-sources to auto-detect and send to referral sources list")
        parser.print_help()


if __name__ == "__main__":
    main()

