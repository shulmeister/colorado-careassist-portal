import os
import logging
from sqlalchemy import create_engine, text
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        # Database Connections
        # Use Env vars if available (Production), otherwise default to local SQLite paths
        self.sales_db_url = os.getenv("SALES_DATABASE_URL", "sqlite:///sales/sales_tracker.db")
        self.recruiting_db_url = os.getenv("RECRUITING_DATABASE_URL", "sqlite:///recruiting/instance/leads.db")
        
        # We don't need persistent connections, just URLs to create engines on demand
        
    def _get_engine(self, url):
        try:
            return create_engine(url)
        except Exception as e:
            logger.error(f"Failed to create engine for {url}: {e}")
            return None

    def search(self, query: str) -> List[Dict[str, Any]]:
        results = []
        if not query or len(query) < 2:
            return results

        # 1. Search Sales
        results.extend(self._search_sales(query))
        
        # 2. Search Recruiting
        results.extend(self._search_recruiting(query))
        
        return results

    def _search_sales(self, query: str) -> List[Dict[str, Any]]:
        results = []
        engine = self._get_engine(self.sales_db_url)
        if not engine:
            return results

        try:
            # Check if using SQLite (for LIKE vs ILIKE)
            is_sqlite = "sqlite" in self.sales_db_url
            like_op = "LIKE" if is_sqlite else "ILIKE"
            
            with engine.connect() as conn:
                # CONTACTS
                sql = f"""
                    SELECT id, first_name, last_name, email, phone, title
                    FROM contacts 
                    WHERE first_name {like_op} :q OR last_name {like_op} :q OR email {like_op} :q
                    LIMIT 5
                """
                rows = conn.execute(text(sql), {"q": f"%{query}%"}).fetchall()
                for row in rows:
                    name = f"{row.first_name or ''} {row.last_name or ''}".strip()
                    results.append({
                        "type": "Contact",
                        "name": name,
                        "details": f"{row.title or 'No Title'} | {row.email or ''}",
                        "url": f"/sales/#/contacts/{row.id}",
                        "source": "Sales"
                    })

                # COMPANIES (ReferralSource)
                sql = f"""
                    SELECT id, name, source_type, location
                    FROM referral_sources 
                    WHERE name {like_op} :q
                    LIMIT 5
                """
                rows = conn.execute(text(sql), {"q": f"%{query}%"}).fetchall()
                for row in rows:
                    results.append({
                        "type": "Company",
                        "name": row.name,
                        "details": f"{row.source_type or 'Company'} | {row.location or ''}",
                        "url": f"/sales/#/companies/{row.id}",
                        "source": "Sales"
                    })
                    
        except Exception as e:
            # Log but don't fail the whole search
            logger.warning(f"Error searching Sales DB: {e}")
            
        return results

    def _search_recruiting(self, query: str) -> List[Dict[str, Any]]:
        results = []
        engine = self._get_engine(self.recruiting_db_url)
        if not engine:
            return results

        try:
            is_sqlite = "sqlite" in self.recruiting_db_url
            like_op = "LIKE" if is_sqlite else "ILIKE"
            
            with engine.connect() as conn:
                # Search Leads (Applicants)
                # Table name confirmed as 'lead' in recruiting/app.py schema updates
                sql = f"""
                    SELECT id, name, email, phone, status
                    FROM lead
                    WHERE name {like_op} :q OR email {like_op} :q
                    LIMIT 5
                """
                rows = conn.execute(text(sql), {"q": f"%{query}%"}).fetchall()
                for row in rows:
                    results.append({
                        "type": "Applicant",
                        "name": row.name,
                        "details": f"{row.status or 'New'} | {row.email or ''}",
                        # Recruiting dashboard URL structure: /recruiting/?id=123 (Needs verification, assuming query param or hash)
                        # Looking at recruiting/templates/index.html would confirm, but usually it's a list. 
                        # We'll point to the main dashboard for now or a specific view if we find it.
                        "url": f"/recruiting?search={row.name}", 
                        "source": "Recruiting"
                    })
                    
        except Exception as e:
            logger.warning(f"Error searching Recruiting DB: {e}")
        
        return results

search_service = SearchService()
