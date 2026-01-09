#!/usr/bin/env python3
"""
Sync Companies, Deals, and Tasks from Dashboard to Brevo CRM.
"""

import sys
import requests
from datetime import datetime
from database import db_manager
from models import ReferralSource, Deal, ContactTask, CompanyTask, DealTask
from brevo_service import BrevoService


def create_crm_attributes(brevo):
    """Create custom CRM attributes in Brevo if they don't exist."""
    print("\nCreating CRM custom attributes...")
    
    headers = brevo._get_headers()
    base = brevo.base_url
    
    # Company attributes
    company_attrs = [
        {"name": "location", "type": "text"},
        {"name": "county", "type": "text"},
        {"name": "source_type", "type": "text"},
        {"name": "notes", "type": "text"},
    ]
    
    for attr in company_attrs:
        try:
            resp = requests.post(
                f"{base}/companies/attributes",
                headers=headers,
                json={"name": attr["name"], "type": attr["type"]}
            )
            if resp.status_code in (200, 201):
                print(f"  ✓ Created company attribute: {attr['name']}")
            elif 'already exist' in resp.text.lower() or resp.status_code == 409:
                pass  # Already exists
            else:
                print(f"  - Company attr '{attr['name']}': {resp.status_code}")
        except Exception as e:
            pass
    
    # Deal attributes  
    deal_attrs = [
        {"name": "deal_amount", "type": "number"},
        {"name": "category", "type": "text"},
        {"name": "deal_notes", "type": "text"},
    ]
    
    for attr in deal_attrs:
        try:
            resp = requests.post(
                f"{base}/crm/attributes/deals",
                headers=headers,
                json={"name": attr["name"], "type": attr["type"]}
            )
            if resp.status_code in (200, 201):
                print(f"  ✓ Created deal attribute: {attr['name']}")
            elif 'already exist' in resp.text.lower() or resp.status_code == 409:
                pass
        except Exception:
            pass
    
    print("  Attribute setup complete")


def sync_companies_to_brevo(db, brevo):
    """Sync all companies (ReferralSource) to Brevo."""
    print("\n" + "="*60)
    print("SYNCING COMPANIES")
    print("="*60)
    
    companies = db.query(ReferralSource).all()
    print(f"Found {len(companies)} companies in dashboard")
    
    success = 0
    errors = 0
    
    for company in companies:
        try:
            # Build company data - only use Brevo's default company fields
            data = {
                "name": company.name or "Unknown Company"
            }
            
            # Create company in Brevo
            response = requests.post(
                f"{brevo.base_url}/companies",
                headers=brevo._get_headers(),
                json=data
            )
            
            if response.status_code in (200, 201):
                success += 1
            elif 'duplicate' in response.text.lower() or 'already exist' in response.text.lower():
                success += 1  # Already exists
            else:
                errors += 1
                if errors <= 3:
                    print(f"  Error: {company.name}: {response.status_code} - {response.text[:150]}")
                    
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Exception: {company.name}: {str(e)}")
    
    print(f"\n✓ Companies synced: {success}")
    if errors:
        print(f"✗ Errors: {errors}")
    
    return success, errors


def sync_deals_to_brevo(db, brevo):
    """Sync all deals to Brevo."""
    print("\n" + "="*60)
    print("SYNCING DEALS")
    print("="*60)
    
    deals = db.query(Deal).all()
    print(f"Found {len(deals)} deals in dashboard")
    
    success = 0
    errors = 0
    
    for deal in deals:
        try:
            # Brevo requires minimal fields for deals
            data = {
                "name": deal.name or f"Deal #{deal.id}"
            }
            
            # Add amount if present - Brevo expects it in a specific format
            if deal.amount and deal.amount > 0:
                data["attributes"] = {"amount": int(deal.amount * 100)}  # Cents
            
            # Create deal in Brevo
            response = requests.post(
                f"{brevo.base_url}/crm/deals",
                headers=brevo._get_headers(),
                json=data
            )
            
            if response.status_code in (200, 201):
                success += 1
            elif 'duplicate' in response.text.lower():
                success += 1
            else:
                errors += 1
                if errors <= 3:
                    print(f"  Error: {deal.name}: {response.status_code} - {response.text[:150]}")
                    
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Exception: {deal.name}: {str(e)}")
    
    print(f"\n✓ Deals synced: {success}")
    if errors:
        print(f"✗ Errors: {errors}")
    
    return success, errors


def sync_tasks_to_brevo(db, brevo):
    """Sync all tasks to Brevo."""
    print("\n" + "="*60)
    print("SYNCING TASKS")
    print("="*60)
    
    # Get tasks from all task tables
    contact_tasks = db.query(ContactTask).all()
    company_tasks = db.query(CompanyTask).all()
    deal_tasks = db.query(DealTask).all()
    
    all_tasks = []
    for t in contact_tasks:
        all_tasks.append({'title': t.title, 'due_date': t.due_date, 'status': t.status})
    for t in company_tasks:
        all_tasks.append({'title': t.title, 'due_date': t.due_date, 'status': t.status})
    for t in deal_tasks:
        all_tasks.append({'title': t.title, 'due_date': t.due_date, 'status': t.status})
    
    print(f"Found {len(all_tasks)} total tasks")
    
    if not all_tasks:
        print("No tasks to sync")
        return 0, 0
    
    success = 0
    errors = 0
    
    # Get available task types from Brevo
    task_type_id = None
    try:
        types_response = requests.get(
            f"{brevo.base_url}/crm/tasktypes",
            headers=brevo._get_headers()
        )
        if types_response.status_code == 200:
            task_types = types_response.json()
            if task_types:
                task_type_id = task_types[0].get('id')
                print(f"Using task type ID: {task_type_id}")
    except Exception as e:
        print(f"  Could not get task types: {e}")
    
    for task in all_tasks:
        try:
            data = {
                "name": task['title'] or "Task"
            }
            
            if task_type_id:
                data["taskTypeId"] = task_type_id
            
            # Mark as done if completed
            if task.get('status') == 'completed':
                data["done"] = True
            
            # Add due date in ISO datetime format (required by Brevo)
            if task.get('due_date') and hasattr(task['due_date'], 'isoformat'):
                data["date"] = task['due_date'].strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                # Default to tomorrow if no date
                from datetime import datetime, timedelta
                tomorrow = datetime.utcnow() + timedelta(days=1)
                data["date"] = tomorrow.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Create task in Brevo
            response = requests.post(
                f"{brevo.base_url}/crm/tasks",
                headers=brevo._get_headers(),
                json=data
            )
            
            if response.status_code in (200, 201):
                success += 1
            else:
                errors += 1
                if errors <= 3:
                    print(f"  Error: {response.status_code} - {response.text[:150]}")
                    
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Exception: {str(e)}")
    
    print(f"\n✓ Tasks synced: {success}")
    if errors:
        print(f"✗ Errors: {errors}")
    
    return success, errors


def main():
    print("="*60)
    print("BREVO CRM SYNC")
    print("="*60)
    
    db = db_manager.SessionLocal()
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    # Test connection
    test = brevo.test_connection()
    if not test.get('success'):
        print(f"ERROR: Brevo connection failed: {test.get('error')}")
        return
    
    print(f"Connected to Brevo: {test.get('message')}")
    
    try:
        # Sync Companies
        comp_success, comp_errors = sync_companies_to_brevo(db, brevo)
        
        # Sync Deals
        deal_success, deal_errors = sync_deals_to_brevo(db, brevo)
        
        # Sync Tasks
        task_success, task_errors = sync_tasks_to_brevo(db, brevo)
        
        print("\n" + "="*60)
        print("SYNC COMPLETE")
        print("="*60)
        print(f"Companies: {comp_success} synced, {comp_errors} errors")
        print(f"Deals: {deal_success} synced, {deal_errors} errors")
        print(f"Tasks: {task_success} synced, {task_errors} errors")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
