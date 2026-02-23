#!/usr/bin/env python3
"""
Finance Team Daily Pulse Check
Integrated with QuickBooks CLI for automated daily finance monitoring.

Usage: python3 finance-daily-pulse.py
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

QB_CLI = Path("/root/clawd/tools/quickbooks/qb.py")


def run_qb_command(*args):
    """Run qb.py command and return output."""
    cmd = ["python3", str(QB_CLI)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def parse_invoices(output):
    """Parse invoice list output for AR analysis."""
    lines = [l.strip() for l in output.split("\n") if l.strip() and not l.startswith("-")]
    data_lines = [l for l in lines[1:] if l and not l.startswith("Date")]
    
    total_ar = 0
    overdue_30 = []
    overdue_60 = []
    
    for line in data_lines:
        parts = line.split()
        if len(parts) >= 4:
            try:
                date_str = parts[0]
                balance = float(parts[-1].replace(",", ""))
                total_ar += balance
                
                # Check aging
                inv_date = datetime.strptime(date_str, "%Y-%m-%d")
                age_days = (datetime.now() - inv_date).days
                
                if balance > 0:
                    customer = " ".join(parts[1:-2])
                    if age_days > 60:
                        overdue_60.append({
                            "customer": customer,
                            "age_days": age_days,
                            "balance": balance
                        })
                    elif age_days > 30:
                        overdue_30.append({
                            "customer": customer,
                            "age_days": age_days,
                            "balance": balance
                        })
            except (ValueError, IndexError):
                continue
    
    return total_ar, overdue_30, overdue_60


def main():
    print("\n" + "="*70)
    print(f"  💰 FINANCE TEAM DAILY PULSE")
    print(f"  {datetime.now().strftime('%A, %B %d, %Y')}")
    print("="*70 + "\n")
    
    # === Accounts Receivable ===
    print("📊 ACCOUNTS RECEIVABLE")
    inv_output = run_qb_command("invoices")
    total_ar, overdue_30, overdue_60 = parse_invoices(inv_output)
    
    print(f"   Total AR: ${total_ar:,.2f}")
    
    # Red alerts (>60 days)
    if overdue_60:
        print(f"\n   🔴 URGENT: {len(overdue_60)} invoice(s) >60 days overdue:")
        for inv in overdue_60[:5]:
            print(f"      • {inv['customer'][:35]}: ${inv['balance']:,.2f} ({inv['age_days']} days)")
    
    # Yellow alerts (30-60 days)
    if overdue_30:
        print(f"\n   ⚠️  {len(overdue_30)} invoice(s) 30-60 days:")
        for inv in overdue_30[:3]:
            print(f"      • {inv['customer'][:35]}: ${inv['balance']:,.2f} ({inv['age_days']} days)")
    
    if not overdue_30 and not overdue_60:
        print("   ✅ No overdue invoices")
    
    print()
    
    # === Action Items ===
    print("🎯 ACTION ITEMS")
    
    action_items = []
    
    if overdue_60:
        action_items.append(f"🔴 URGENT: Follow up on {len(overdue_60)} invoices >60 days")
    
    if overdue_30:
        action_items.append(f"⚠️  Monitor {len(overdue_30)} invoices 30-60 days")
    
    if total_ar > 50000:
        action_items.append(f"💰 High AR balance: ${total_ar:,.2f} - prioritize collections")
    
    if action_items:
        for item in action_items:
            print(f"   {item}")
    else:
        print("   ✅ No urgent action items")
    
    print("\n" + "="*70)
    print("💡 For detailed reports, run:")
    print("   qb pnl ThisMonth    - Profit & Loss")
    print("   qb balance          - Balance Sheet")
    print("   qb customers        - Customer AR detail")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
