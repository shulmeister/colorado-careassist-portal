#!/usr/bin/env python3
"""
QuickBooks Online API integration service.
Handles customer data fetching and syncing to Brevo.
"""

import base64
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import psycopg2
import requests

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
            return

        # Auto-load tokens from DB if not in env vars (tokens are persisted there after OAuth)
        if not (self.access_token and self.refresh_token):
            self.load_tokens_from_db()

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
            # QB requires Basic Auth (base64 clientId:clientSecret), not form body
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            response = requests.post(
                f"{self.auth_url}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                if 'refresh_token' in data:
                    self.refresh_token = data.get('refresh_token')

                # Always persist refreshed tokens so they survive restarts
                self._save_tokens_to_db()
                logger.info("QuickBooks access token refreshed and saved to DB")
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

    def load_tokens_from_db(self) -> bool:
        """Load OAuth tokens from the oauth_tokens table. Auto-refreshes if expired."""
        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
        try:
            conn = psycopg2.connect(db_url)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT access_token, refresh_token, expires_at, extra_data "
                    "FROM oauth_tokens WHERE service = 'quickbooks' AND is_active = true "
                    "ORDER BY updated_at DESC LIMIT 1"
                )
                row = cur.fetchone()
            conn.close()

            if not row:
                logger.warning("No active QuickBooks token found in database")
                return False

            self.access_token = row[0]
            self.refresh_token = row[1]
            expires_at = row[2]
            extra_data = row[3] or {}

            # Get realm_id from extra_data or env
            if extra_data.get("realm_id"):
                self.realm_id = extra_data["realm_id"]
            if not self.realm_id:
                self.realm_id = os.getenv("QB_REALM_ID")

            self.enabled = bool(self.client_id and self.client_secret and self.realm_id)

            # Auto-refresh if expired
            if expires_at and datetime.utcnow() > expires_at:
                logger.info("QuickBooks token expired, refreshing...")
                result = self.refresh_access_token()
                if result.get("success"):
                    self._save_tokens_to_db()
                else:
                    logger.error(f"Token refresh failed: {result.get('error')}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to load QBO tokens from DB: {e}")
            return False

    def _save_tokens_to_db(self):
        """Update tokens in the database after a refresh."""
        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
        try:
            conn = psycopg2.connect(db_url)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE oauth_tokens SET access_token = %s, refresh_token = %s, "
                    "expires_at = %s, updated_at = NOW() "
                    "WHERE service = 'quickbooks' AND is_active = true",
                    (self.access_token, self.refresh_token,
                     datetime.utcnow() + timedelta(hours=1))
                )
            conn.commit()
            conn.close()
            logger.info("QuickBooks tokens updated in database")
        except Exception as e:
            logger.error(f"Failed to save QBO tokens to DB: {e}")

    def _api_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make an API request with auto-refresh on 401."""
        url = f"{self.base_url}/v3/company/{self.realm_id}/{endpoint}"
        response = requests.request(method, url, headers=self._get_headers(), **kwargs)

        if response.status_code == 401:
            logger.info("QBO 401 - refreshing token and retrying")
            result = self.refresh_access_token()
            if result.get("success"):
                self._save_tokens_to_db()
                response = requests.request(method, url, headers=self._get_headers(), **kwargs)
            else:
                return None

        return response

    def get_invoices(self, status: str = "Open", limit: int = 500) -> Dict[str, Any]:
        """Get invoices from QuickBooks. status='Open' for unpaid, 'All' for everything."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        try:
            if status == "Open":
                query = f"SELECT * FROM Invoice WHERE Balance > '0' MAXRESULTS {limit}"
            else:
                query = f"SELECT * FROM Invoice MAXRESULTS {limit}"

            response = self._api_request("GET", "query", params={"query": query})
            if not response or response.status_code != 200:
                error_text = response.text[:200] if response else "No response"
                return {"success": False, "error": f"API error: {error_text}"}

            data = response.json()
            invoices = data.get("QueryResponse", {}).get("Invoice", [])
            if isinstance(invoices, dict):
                invoices = [invoices]

            return {"success": True, "invoices": invoices, "count": len(invoices)}

        except Exception as e:
            logger.error(f"Failed to get invoices: {e}")
            return {"success": False, "error": str(e)}

    def get_ar_aging_summary(self) -> Dict[str, Any]:
        """Get the Accounts Receivable Aging Summary report from QBO."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        try:
            response = self._api_request("GET", "reports/AgedReceivables")
            if not response or response.status_code != 200:
                error_text = response.text[:200] if response else "No response"
                return {"success": False, "error": f"API error: {error_text}"}

            return {"success": True, "report": response.json()}

        except Exception as e:
            logger.error(f"Failed to get AR aging summary: {e}")
            return {"success": False, "error": str(e)}

    def generate_ar_report(self, detail_level: str = "summary") -> Dict[str, Any]:
        """Generate a formatted AR report combining aging summary and open invoices."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        lines = []

        # Get aging summary
        aging = self.get_ar_aging_summary()
        if aging.get("success"):
            report_data = aging["report"]
            header = report_data.get("Header", {})
            lines.append(f"📊 AR Aging Report — {header.get('ReportName', 'Aged Receivables')}")
            lines.append(f"As of: {header.get('DateMacro', header.get('EndPeriod', 'today'))}")
            lines.append("")

            # Parse rows from QBO report format
            rows_section = report_data.get("Rows", {})
            row_list = rows_section.get("Row", [])

            for row in row_list:
                row_type = row.get("type", "")
                if row_type == "Data":
                    cols = row.get("ColData", [])
                    if cols:
                        name = cols[0].get("value", "")
                        amounts = [c.get("value", "") for c in cols[1:]]
                        if name and any(a and a != "0" and a != "" for a in amounts):
                            lines.append(f"  {name}: {', '.join(a for a in amounts if a)}")
                elif row_type == "Section":
                    section_header = row.get("Header", {})
                    if section_header:
                        cols = section_header.get("ColData", [])
                        if cols:
                            lines.append(f"\n{cols[0].get('value', '')}")
                    # Process section rows
                    section_rows = row.get("Rows", {}).get("Row", [])
                    for sr in section_rows:
                        cols = sr.get("ColData", [])
                        if cols:
                            name = cols[0].get("value", "")
                            amounts = [c.get("value", "") for c in cols[1:]]
                            if name and any(a and a != "0" and a != "" for a in amounts):
                                lines.append(f"  {name}: {', '.join(a for a in amounts if a)}")
                    # Section summary
                    summary = row.get("Summary", {})
                    if summary:
                        cols = summary.get("ColData", [])
                        if cols:
                            name = cols[0].get("value", "")
                            amounts = [c.get("value", "") for c in cols[1:]]
                            lines.append(f"  ** {name}: {', '.join(a for a in amounts if a)}")

            # Columns header (aging buckets)
            columns = report_data.get("Columns", {}).get("Column", [])
            if columns:
                col_names = [c.get("ColTitle", "") for c in columns]
                lines.insert(3, f"Buckets: {' | '.join(col_names)}")
                lines.insert(4, "")
        else:
            lines.append(f"⚠️ Could not fetch aging summary: {aging.get('error', 'unknown')}")

        # Get open invoices for detail
        if detail_level == "detailed":
            invoices_result = self.get_invoices(status="Open")
            if invoices_result.get("success"):
                invoices = invoices_result["invoices"]
                lines.append(f"\n--- Open Invoices ({len(invoices)} total) ---")

                # Sort by balance descending
                invoices.sort(key=lambda x: float(x.get("Balance", 0)), reverse=True)

                total_ar = sum(float(inv.get("Balance", 0)) for inv in invoices)
                lines.append(f"Total AR Outstanding: ${total_ar:,.2f}")
                lines.append("")

                for inv in invoices[:20]:  # Top 20
                    customer = inv.get("CustomerRef", {}).get("name", "Unknown")
                    balance = float(inv.get("Balance", 0))
                    due_date = inv.get("DueDate", "N/A")
                    inv_num = inv.get("DocNumber", "N/A")
                    lines.append(f"  #{inv_num} — {customer}: ${balance:,.2f} (due {due_date})")

                if len(invoices) > 20:
                    lines.append(f"  ... and {len(invoices) - 20} more invoices")
        else:
            # Summary: just get totals from open invoices
            invoices_result = self.get_invoices(status="Open")
            if invoices_result.get("success"):
                invoices = invoices_result["invoices"]
                total_ar = sum(float(inv.get("Balance", 0)) for inv in invoices)
                overdue = [inv for inv in invoices
                          if inv.get("DueDate") and inv["DueDate"] < datetime.now().strftime("%Y-%m-%d")]
                lines.append("\n--- Summary ---")
                lines.append(f"Total AR Outstanding: ${total_ar:,.2f}")
                lines.append(f"Open Invoices: {len(invoices)}")
                lines.append(f"Overdue Invoices: {len(overdue)}")
                if overdue:
                    overdue_total = sum(float(inv.get("Balance", 0)) for inv in overdue)
                    lines.append(f"Overdue Amount: ${overdue_total:,.2f}")

                # Top 5 overdue
                if overdue:
                    overdue.sort(key=lambda x: float(x.get("Balance", 0)), reverse=True)
                    lines.append("\nTop Overdue:")
                    for inv in overdue[:5]:
                        customer = inv.get("CustomerRef", {}).get("name", "Unknown")
                        balance = float(inv.get("Balance", 0))
                        due_date = inv.get("DueDate", "N/A")
                        lines.append(f"  {customer}: ${balance:,.2f} (due {due_date})")

        return {"success": True, "report": "\n".join(lines)}

    def get_profit_and_loss(self, period: str = "ThisMonth") -> Dict[str, Any]:
        """Get Profit & Loss report from QBO Reports API.

        period: "ThisMonth", "LastMonth", "ThisQuarter", "ThisYear", "LastYear"
        """
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        try:
            period_map = {
                "ThisMonth": "This Month",
                "LastMonth": "Last Month",
                "ThisQuarter": "This Fiscal Quarter",
                "ThisYear": "This Fiscal Year",
                "LastYear": "Last Fiscal Year",
            }
            date_macro = period_map.get(period, "This Month")

            response = self._api_request("GET", "reports/ProfitAndLoss", params={"date_macro": date_macro})
            if not response or response.status_code != 200:
                error_text = response.text[:200] if response else "No response"
                return {"success": False, "error": f"API error: {error_text}"}

            report = response.json()
            header = report.get("Header", {})
            rows = report.get("Rows", {}).get("Row", [])

            parsed = {
                "success": True,
                "period": date_macro,
                "start_date": header.get("StartPeriod", ""),
                "end_date": header.get("EndPeriod", ""),
            }

            for row in rows:
                group = row.get("group", "")
                summary = row.get("Summary", {})
                cols = summary.get("ColData", [])
                if len(cols) >= 2:
                    try:
                        amount = float(cols[1].get("value", "0"))
                    except (ValueError, TypeError):
                        amount = 0
                    if group == "Income":
                        parsed["total_income"] = amount
                    elif group == "Expenses":
                        parsed["total_expenses"] = amount

                # NetIncome can be at top level or nested
                if row.get("type") == "Section" and row.get("group") == "NetIncome":
                    ni_cols = row.get("Summary", {}).get("ColData", [])
                    if len(ni_cols) >= 2:
                        try:
                            parsed["net_income"] = float(ni_cols[1].get("value", "0"))
                        except (ValueError, TypeError):
                            pass
                elif group == "NetIncome" and len(cols) >= 2:
                    try:
                        parsed["net_income"] = float(cols[1].get("value", "0"))
                    except (ValueError, TypeError):
                        pass

            return parsed

        except Exception as e:
            logger.error(f"P&L report failed: {e}")
            return {"success": False, "error": str(e)}

    def get_balance_sheet(self, as_of_date: str = None) -> Dict[str, Any]:
        """Get Balance Sheet report from QBO Reports API.

        as_of_date: Optional YYYY-MM-DD string. Defaults to today.
        """
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        try:
            params = {}
            if as_of_date:
                params["start_date"] = as_of_date
                params["end_date"] = as_of_date

            response = self._api_request("GET", "reports/BalanceSheet", params=params)
            if not response or response.status_code != 200:
                error_text = response.text[:200] if response else "No response"
                return {"success": False, "error": f"API error: {error_text}"}

            report = response.json()
            header = report.get("Header", {})
            rows = report.get("Rows", {}).get("Row", [])

            parsed = {
                "success": True,
                "as_of": header.get("EndPeriod", as_of_date or "today"),
            }

            cash_total = 0
            for row in rows:
                group = row.get("group", "")
                summary = row.get("Summary", {})
                cols = summary.get("ColData", [])
                if len(cols) >= 2:
                    try:
                        amount = float(cols[1].get("value", "0"))
                    except (ValueError, TypeError):
                        amount = 0

                    if "Asset" in group:
                        parsed["total_assets"] = amount
                    elif "Liabilit" in group:
                        parsed["total_liabilities"] = amount
                    elif "Equity" in group:
                        parsed["total_equity"] = amount

                # Look for cash/bank in nested sections
                section_rows = row.get("Rows", {}).get("Row", [])
                for sr in section_rows:
                    sr_group = sr.get("group", "")
                    sr_header = sr.get("Header", {})
                    sr_header_cols = sr_header.get("ColData", [])
                    header_name = sr_header_cols[0].get("value", "").lower() if sr_header_cols else ""

                    if "bank" in sr_group.lower() or "bank" in header_name or "cash" in header_name:
                        sr_summary = sr.get("Summary", {})
                        sr_cols = sr_summary.get("ColData", [])
                        if len(sr_cols) >= 2:
                            try:
                                cash_total += float(sr_cols[1].get("value", "0"))
                            except (ValueError, TypeError):
                                pass

            if cash_total:
                parsed["cash_and_equivalents"] = cash_total

            return parsed

        except Exception as e:
            logger.error(f"Balance sheet failed: {e}")
            return {"success": False, "error": str(e)}

    def get_purchases(self, months_back: int = 6, limit: int = 1000) -> Dict[str, Any]:
        """Get purchase/expense transactions from QuickBooks for the last N months."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        try:
            cutoff = (datetime.now() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
            query = f"SELECT * FROM Purchase WHERE TxnDate >= '{cutoff}' MAXRESULTS {limit}"

            response = self._api_request("GET", "query", params={"query": query})
            if not response or response.status_code != 200:
                error_text = response.text[:200] if response else "No response"
                return {"success": False, "error": f"API error: {error_text}"}

            data = response.json()
            purchases = data.get("QueryResponse", {}).get("Purchase", [])
            if isinstance(purchases, dict):
                purchases = [purchases]

            return {"success": True, "purchases": purchases, "count": len(purchases)}

        except Exception as e:
            logger.error(f"Failed to get purchases: {e}")
            return {"success": False, "error": str(e)}

    def get_vendors(self, limit: int = 500) -> Dict[str, Any]:
        """Get all vendors from QuickBooks."""
        if not self.enabled:
            return {"success": False, "error": "QuickBooks not configured"}

        try:
            query = f"SELECT * FROM Vendor WHERE Active = true MAXRESULTS {limit}"

            response = self._api_request("GET", "query", params={"query": query})
            if not response or response.status_code != 200:
                error_text = response.text[:200] if response else "No response"
                return {"success": False, "error": f"API error: {error_text}"}

            data = response.json()
            vendors = data.get("QueryResponse", {}).get("Vendor", [])
            if isinstance(vendors, dict):
                vendors = [vendors]

            return {"success": True, "vendors": vendors, "count": len(vendors)}

        except Exception as e:
            logger.error(f"Failed to get vendors: {e}")
            return {"success": False, "error": str(e)}

