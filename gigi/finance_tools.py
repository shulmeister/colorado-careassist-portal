"""
Finance tools for Gigi — shared business logic.
Called by telegram_bot.py, voice_brain.py, ringcentral_bot.py.
All functions are SYNCHRONOUS — callers wrap in asyncio.to_thread() / run_sync().
All functions return dicts — callers json.dumps() the result.
"""
import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _get_qb_service():
    """Get an authenticated QuickBooksService instance."""
    from sales.quickbooks_service import QuickBooksService
    qb = QuickBooksService()
    loaded = qb.load_tokens_from_db()
    if not loaded:
        return None
    return qb


def get_pnl_report(period: str = "ThisMonth") -> Dict[str, Any]:
    """Profit & Loss report from QBO Reports API."""
    qb = _get_qb_service()
    if not qb:
        return {"error": "QuickBooks not connected. Visit portal to authorize."}
    return qb.get_profit_and_loss(period)


def get_balance_sheet(as_of_date: str = "") -> Dict[str, Any]:
    """Balance Sheet from QBO Reports API."""
    qb = _get_qb_service()
    if not qb:
        return {"error": "QuickBooks not connected. Visit portal to authorize."}
    return qb.get_balance_sheet(as_of_date or None)


def get_invoice_list(status: str = "Open") -> Dict[str, Any]:
    """Open/overdue invoice list from QBO."""
    qb = _get_qb_service()
    if not qb:
        return {"error": "QuickBooks not connected. Visit portal to authorize."}

    result = qb.get_invoices(status=status)
    if not result.get("success"):
        return result

    invoices = result.get("invoices", [])
    now_str = datetime.now().strftime("%Y-%m-%d")

    formatted = []
    for inv in invoices:
        balance = float(inv.get("Balance", 0))
        due_date = inv.get("DueDate", "N/A")
        is_overdue = due_date < now_str if due_date and due_date != "N/A" else False
        formatted.append({
            "invoice_number": inv.get("DocNumber", "N/A"),
            "customer": inv.get("CustomerRef", {}).get("name", "Unknown"),
            "balance": balance,
            "due_date": due_date,
            "overdue": is_overdue,
            "total": float(inv.get("TotalAmt", 0)),
        })

    # Sort: overdue first, then by balance descending
    formatted.sort(key=lambda x: (not x["overdue"], -x["balance"]))

    total_ar = sum(inv["balance"] for inv in formatted)
    overdue_count = sum(1 for inv in formatted if inv["overdue"])
    overdue_amount = sum(inv["balance"] for inv in formatted if inv["overdue"])

    return {
        "status_filter": status,
        "total_invoices": len(formatted),
        "total_ar": total_ar,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "invoices": formatted[:25],
    }


def get_cash_position() -> Dict[str, Any]:
    """Current cash position + runway estimate."""
    qb = _get_qb_service()
    if not qb:
        return {"error": "QuickBooks not connected. Visit portal to authorize."}

    bs = qb.get_balance_sheet()
    if not bs.get("success"):
        return bs

    pnl = qb.get_profit_and_loss("ThisMonth")
    last_pnl = qb.get_profit_and_loss("LastMonth")

    cash_on_hand = bs.get("cash_and_equivalents", 0)
    monthly_net = pnl.get("net_income", 0) if pnl.get("success") else 0
    last_monthly_net = last_pnl.get("net_income", 0) if last_pnl.get("success") else 0
    avg_monthly_net = (monthly_net + last_monthly_net) / 2 if last_monthly_net else monthly_net

    runway_months = None
    if avg_monthly_net < 0:
        runway_months = round(cash_on_hand / abs(avg_monthly_net), 1)

    return {
        "cash_on_hand": cash_on_hand,
        "this_month_net": monthly_net,
        "last_month_net": last_monthly_net,
        "avg_monthly_net": avg_monthly_net,
        "runway_months": runway_months,
        "runway_note": f"{runway_months} months at current burn" if runway_months else "Net positive - no burn",
    }


def get_financial_dashboard() -> Dict[str, Any]:
    """Aggregated finance snapshot: AR + Cash + P&L summary."""
    qb = _get_qb_service()
    if not qb:
        return {"error": "QuickBooks not connected. Visit portal to authorize."}

    result = {}

    try:
        ar = qb.get_ar_aging_summary()
        result["ar_aging"] = ar if ar.get("success") else {"error": ar.get("error")}
    except Exception as e:
        result["ar_aging"] = {"error": str(e)}

    result["cash"] = get_cash_position()

    try:
        pnl = qb.get_profit_and_loss("ThisMonth")
        result["pnl_this_month"] = pnl if pnl.get("success") else {"error": pnl.get("error")}
    except Exception as e:
        result["pnl_this_month"] = {"error": str(e)}

    try:
        inv_result = qb.get_invoices(status="Open")
        if inv_result.get("success"):
            invoices = inv_result["invoices"]
            now_str = datetime.now().strftime("%Y-%m-%d")
            total_ar = sum(float(i.get("Balance", 0)) for i in invoices)
            overdue = [i for i in invoices if i.get("DueDate", "") < now_str]
            result["invoices_summary"] = {
                "total_open": len(invoices),
                "total_ar": total_ar,
                "overdue_count": len(overdue),
                "overdue_amount": sum(float(i.get("Balance", 0)) for i in overdue),
            }
    except Exception as e:
        result["invoices_summary"] = {"error": str(e)}

    return result


def get_subscription_audit(months_back: int = 6) -> Dict[str, Any]:
    """Audit all recurring charges/subscriptions from QBO purchase history.

    Groups expenses by vendor, identifies recurring patterns, and calculates
    estimated monthly cost per vendor. Helps find subscriptions to cancel.
    """
    qb = _get_qb_service()
    if not qb:
        return {"error": "QuickBooks not connected. Visit portal to authorize."}

    result = qb.get_purchases(months_back=months_back)
    if not result.get("success"):
        return result

    purchases = result.get("purchases", [])

    # Group by vendor/payee
    vendor_charges: Dict[str, list] = {}
    for p in purchases:
        entity_ref = p.get("EntityRef", {})
        vendor = entity_ref.get("name", "Unknown")
        amount = float(p.get("TotalAmt", 0))
        txn_date = p.get("TxnDate", "")

        # Extract line item descriptions for context
        descriptions = []
        for line in p.get("Line", []):
            desc = line.get("Description", "")
            if desc:
                descriptions.append(desc)
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct = detail.get("AccountRef", {}).get("name", "")
            if acct:
                descriptions.append(acct)

        if vendor not in vendor_charges:
            vendor_charges[vendor] = []
        vendor_charges[vendor].append({
            "amount": amount,
            "date": txn_date,
            "descriptions": descriptions[:3],
        })

    # Identify recurring vendors (2+ charges in the period)
    recurring = []
    one_off = []
    for vendor, charges in vendor_charges.items():
        total = sum(c["amount"] for c in charges)
        avg_per_charge = total / len(charges) if charges else 0
        est_monthly = total / max(months_back, 1)

        entry = {
            "vendor": vendor,
            "charge_count": len(charges),
            "total_spent": round(total, 2),
            "avg_per_charge": round(avg_per_charge, 2),
            "est_monthly": round(est_monthly, 2),
            "last_charge": max(c["date"] for c in charges) if charges else "",
            "descriptions": charges[0].get("descriptions", []) if charges else [],
        }

        if len(charges) >= 2:
            recurring.append(entry)
        else:
            one_off.append(entry)

    # Sort recurring by estimated monthly cost descending
    recurring.sort(key=lambda x: -x["est_monthly"])
    one_off.sort(key=lambda x: -x["total_spent"])

    total_recurring_monthly = sum(r["est_monthly"] for r in recurring)
    total_recurring_annual = total_recurring_monthly * 12

    return {
        "months_analyzed": months_back,
        "total_purchases": len(purchases),
        "recurring_vendors": len(recurring),
        "one_off_vendors": len(one_off),
        "est_monthly_recurring": round(total_recurring_monthly, 2),
        "est_annual_recurring": round(total_recurring_annual, 2),
        "recurring": recurring[:30],
        "one_off": one_off[:15],
    }
