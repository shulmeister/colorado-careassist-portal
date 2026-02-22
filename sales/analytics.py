import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from models import (
    ActivityLog,
    Contact,
    FinancialEntry,
    Lead,
    ReferralSource,
    SalesBonus,
    TimeEntry,
    Visit,
)
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PG_URL = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")

class AnalyticsEngine:
    """Generate analytics and KPIs for the sales dashboard"""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get overall dashboard summary - focused on Jacob's sales manager KPIs"""
        try:
            now = datetime.now()
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_30_days = now - timedelta(days=30)
            last_7_days = now - timedelta(days=7)
            # Start of this week (Monday)
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

            # Quarter boundaries for closed deals
            current_quarter = (now.month - 1) // 3 + 1
            current_quarter_start = datetime(now.year, (current_quarter - 1) * 3 + 1, 1)
            if current_quarter == 1:
                last_quarter_start = datetime(now.year - 1, 10, 1)
                last_quarter_end = datetime(now.year, 1, 1)
            else:
                last_quarter_start = datetime(now.year, (current_quarter - 2) * 3 + 1, 1)
                last_quarter_end = current_quarter_start

            # === VISITS KPIs ===
            total_visits = self.db.query(Visit).count()
            visits_this_month = self.db.query(Visit).filter(
                Visit.visit_date >= current_month_start
            ).count()
            visits_last_30_days = self.db.query(Visit).filter(
                Visit.visit_date >= last_30_days
            ).count()
            visits_ytd = self.db.query(Visit).filter(
                Visit.visit_date >= year_start
            ).count()
            visits_this_week = self.db.query(Visit).filter(
                Visit.visit_date >= week_start
            ).count()

            # === CONTACTS KPIs ===
            total_contacts = self.db.query(Contact).count()
            new_contacts_this_month = self.db.query(Contact).filter(
                Contact.created_at >= current_month_start
            ).count()
            new_contacts_last_7_days = self.db.query(Contact).filter(
                Contact.created_at >= last_7_days
            ).count()
            new_contacts_ytd = self.db.query(Contact).filter(
                Contact.created_at >= year_start
            ).count()
            new_contacts_this_week = self.db.query(Contact).filter(
                Contact.created_at >= week_start
            ).count()

            # === COMPANIES KPIs ===
            total_companies = self.db.query(ReferralSource).count()
            new_companies_this_month = self.db.query(ReferralSource).filter(
                ReferralSource.created_at >= current_month_start
            ).count()
            new_companies_last_7_days = self.db.query(ReferralSource).filter(
                ReferralSource.created_at >= last_7_days
            ).count()
            new_companies_ytd = self.db.query(ReferralSource).filter(
                ReferralSource.created_at >= year_start
            ).count()
            new_companies_this_week = self.db.query(ReferralSource).filter(
                ReferralSource.created_at >= week_start
            ).count()

            # === DEALS KPIs ===
            total_deals = self.db.query(Lead).count()
            active_deals = self.db.query(Lead).filter(
                Lead.status == "active"
            ).count()
            new_deals_this_month = self.db.query(Lead).filter(
                Lead.created_at >= current_month_start
            ).count()
            new_deals_last_7_days = self.db.query(Lead).filter(
                Lead.created_at >= last_7_days
            ).count()
            new_deals_ytd = self.db.query(Lead).filter(
                Lead.created_at >= year_start
            ).count()
            new_deals_this_week = self.db.query(Lead).filter(
                Lead.created_at >= week_start
            ).count()

            # === NEW CLIENTS by quarter (from WellSky cached_patients — active, isClient=True, deduplicated) ===
            closed_deals_this_quarter = 0
            closed_deals_last_quarter = 0
            try:
                import psycopg2
                pg_url = PG_URL
                if pg_url.startswith("postgresql+psycopg2://"):
                    pg_url = pg_url.replace("postgresql+psycopg2://", "postgresql://", 1)
                conn = psycopg2.connect(pg_url)
                cur = conn.cursor()
                # Count distinct clients who are active + isClient=True in WellSky.
                # Deduplicate by first_name + cleaned last_name (strip nicknames/quotes)
                # to handle WellSky duplicate records for the same person.
                client_query = """
                    SELECT COUNT(*) FROM (
                        SELECT first_name,
                               REGEXP_REPLACE(last_name, '^"[^"]*"\\s*', '') as clean_last,
                               MIN(start_date) as earliest_start
                        FROM cached_patients
                        WHERE is_active = true
                          AND start_date IS NOT NULL
                          AND EXISTS (
                              SELECT 1 FROM jsonb_array_elements(wellsky_data->'meta'->'tag') t
                              WHERE t->>'code' = 'isClient' AND t->>'display' = 'True'
                          )
                        GROUP BY first_name, REGEXP_REPLACE(last_name, '^"[^"]*"\\s*', '')
                        HAVING MIN(start_date) >= %s AND MIN(start_date) < %s
                    ) sub
                """
                q_end = datetime(now.year + 1, 1, 1) if current_quarter == 4 else datetime(now.year, current_quarter * 3 + 1, 1)
                cur.execute(client_query, (current_quarter_start.date(), q_end.date()))
                closed_deals_this_quarter = cur.fetchone()[0]
                cur.execute(client_query, (last_quarter_start.date(), last_quarter_end.date()))
                closed_deals_last_quarter = cur.fetchone()[0]
                conn.close()
            except Exception as e:
                logger.warning(f"Error querying cached_patients for closed deals: {e}")

            # Forecast revenue from active deals
            forecast_revenue = self.db.query(func.sum(Lead.expected_revenue)).filter(
                Lead.status == "active"
            ).scalar() or 0.0

            # === EMAILS KPI ===
            from models import ActivityLog, EmailCount
            try:
                email_count_record = self.db.query(EmailCount).order_by(EmailCount.updated_at.desc()).first()
                emails_sent_7_days = email_count_record.emails_sent_7_days if email_count_record else 0
            except Exception as e:
                logger.warning(f"Error getting email count: {str(e)}")
                emails_sent_7_days = 0

            # === PHONE CALLS KPI (from ActivityLog) ===
            try:
                phone_calls_7_days = self.db.query(ActivityLog).filter(
                    ActivityLog.activity_type == "call",
                    ActivityLog.created_at >= last_7_days
                ).count()
            except Exception as e:
                logger.warning(f"Error getting phone call count: {str(e)}")
                phone_calls_7_days = 0

            # === BONUSES (keep for reference) ===
            total_bonuses_earned = self.db.query(func.sum(SalesBonus.bonus_amount)).scalar() or 0.0

            last_updated = datetime.utcnow().isoformat()

            return {
                # Visits
                "total_visits": total_visits,
                "visits_this_month": visits_this_month,
                "visits_last_30_days": visits_last_30_days,
                "visits_ytd": visits_ytd,
                "visits_this_week": visits_this_week,
                # Contacts
                "total_contacts": total_contacts,
                "new_contacts_this_month": new_contacts_this_month,
                "new_contacts_last_7_days": new_contacts_last_7_days,
                "new_contacts_ytd": new_contacts_ytd,
                "new_contacts_this_week": new_contacts_this_week,
                # Companies
                "total_companies": total_companies,
                "new_companies_this_month": new_companies_this_month,
                "new_companies_last_7_days": new_companies_last_7_days,
                "new_companies_ytd": new_companies_ytd,
                "new_companies_this_week": new_companies_this_week,
                # Deals
                "total_deals": total_deals,
                "active_deals": active_deals,
                "new_deals_this_month": new_deals_this_month,
                "new_deals_last_7_days": new_deals_last_7_days,
                "new_deals_ytd": new_deals_ytd,
                "new_deals_this_week": new_deals_this_week,
                # Closed deals by quarter
                "closed_deals_this_quarter": closed_deals_this_quarter,
                "closed_deals_last_quarter": closed_deals_last_quarter,
                "forecast_revenue": round(forecast_revenue, 0),
                # Activity KPIs
                "emails_sent_7_days": emails_sent_7_days,
                "phone_calls_7_days": phone_calls_7_days,
                "total_bonuses": round(total_bonuses_earned, 2),
                "last_updated": last_updated,
                "kpi_source": "database",
            }

        except Exception as e:
            logger.error(f"Error getting dashboard summary: {str(e)}")
            return {}

    def get_visits_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get visits grouped by month"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)

            results = self.db.query(
                func.date_trunc('month', Visit.visit_date).label('month'),
                func.count(Visit.id).label('count')
            ).filter(
                Visit.visit_date >= start_date
            ).group_by(
                func.date_trunc('month', Visit.visit_date)
            ).order_by('month').all()

            return [
                {
                    "month": result.month.strftime("%Y-%m"),
                    "count": result.count
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error getting visits by month: {str(e)}")
            return []

    def get_hours_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get hours worked grouped by month"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)

            results = self.db.query(
                func.date_trunc('month', TimeEntry.date).label('month'),
                func.sum(TimeEntry.hours_worked).label('total_hours')
            ).filter(
                TimeEntry.date >= start_date
            ).group_by(
                func.date_trunc('month', TimeEntry.date)
            ).order_by('month').all()

            return [
                {
                    "month": result.month.strftime("%Y-%m"),
                    "hours": round(result.total_hours, 2)
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error getting hours by month: {str(e)}")
            return []

    def get_top_facilities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most visited facilities"""
        try:
            results = self.db.query(
                Visit.business_name,
                func.count(Visit.id).label('visit_count')
            ).group_by(
                Visit.business_name
            ).order_by(
                desc('visit_count')
            ).limit(limit).all()

            return [
                {
                    "facility": result.business_name,
                    "visits": result.visit_count
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error getting top facilities: {str(e)}")
            return []

    def _categorize_referral_type(self, business_name: str, address: str = "", notes: str = "") -> str:
        """Categorize a visit by referral type - expanded categorization"""
        text = f"{business_name} {address} {notes}".lower()

        # Hospitals (most specific first)
        hospital_keywords = [
            'hospital', 'medical center', 'health center', 'healthcare center',
            'uchealth', 'centura', 'penrose', 'memorial hospital', 'st. francis',
            'emergency room', 'er', 'emergency department', 'icu', 'ccu'
        ]
        if any(keyword in text for keyword in hospital_keywords):
            return 'Hospitals'

        # Veterans Centers (VFW, American Legion)
        veteran_keywords = [
            'vfw', 'american legion', 'legion', 'veterans', 'veteran',
            'legion post', 'veterans center', 'veteran center', 'veterans of foreign wars',
            'vfw post', 'legion hall', 'veterans affairs', 'va center'
        ]
        if any(keyword in text for keyword in veteran_keywords):
            return 'Veterans Centers'

        # Assisted Living / Senior Living / Nursing Homes
        assisted_living_keywords = [
            'assisted living', 'senior living', 'nursing home', 'nursing facility',
            'skilled nursing', 'snf', 'long term care', 'ltc', 'care center',
            'memory care', 'independent living', 'retirement community', 'retirement home',
            'elder care', 'residential care', 'adult care', 'elderly care'
        ]
        if any(keyword in text for keyword in assisted_living_keywords):
            return 'Assisted Living/Nursing'

        # Doctors Offices / Clinics
        doctor_keywords = [
            'doctor', 'physician', 'medical office', 'clinic', 'medical clinic',
            'family medicine', 'internal medicine', 'urgent care', 'md', 'd.o.',
            'primary care', 'specialist', 'practitioner', 'medical practice',
            'pediatric', 'orthopedic', 'cardiology', 'neurology', 'oncology'
        ]
        if any(keyword in text for keyword in doctor_keywords):
            return 'Doctors Offices'

        # Rehabs / Treatment Centers
        rehab_keywords = [
            'rehab', 'rehabilitation', 'recovery', 'treatment center', 'detox',
            'addiction', 'substance abuse', 'drug treatment', 'alcohol treatment',
            'behavioral health', 'mental health', 'psychiatric', 'therapy center'
        ]
        if any(keyword in text for keyword in rehab_keywords):
            return 'Rehabs'

        # Home Health/Hospice
        home_health_keywords = [
            'hospice', 'home health', 'homehealth', 'palliative care',
            'pikes peak hospice', 'end of life', 'comfort care',
            'visiting nurse', 'home care', 'homecare', 'in-home care'
        ]
        if any(keyword in text for keyword in home_health_keywords):
            return 'Home Health/Hospice'

        # Community Centers / Non-Profits
        community_keywords = [
            'community center', 'senior center', 'community', 'non-profit',
            'nonprofit', 'foundation', 'association', 'society', 'organization'
        ]
        if any(keyword in text for keyword in community_keywords):
            return 'Community Centers'

        # Pharmacies / Medical Supply
        pharmacy_keywords = [
            'pharmacy', 'drug store', 'pharmacist', 'cvs', 'walgreens',
            'rite aid', 'medical supply', 'durable medical', 'dme'
        ]
        if any(keyword in text for keyword in pharmacy_keywords):
            return 'Pharmacies/Supply'

        # Social Services / Case Management
        social_service_keywords = [
            'case manager', 'case management', 'social worker', 'social services',
            'disability services', 'medicaid', 'medicare', 'insurance',
            'health department', 'public health'
        ]
        if any(keyword in text for keyword in social_service_keywords):
            return 'Social Services'

        # Default to "Other" if no match
        return 'Other'

    def get_referral_types(self) -> List[Dict[str, Any]]:
        """Get visits categorized by referral type"""
        try:
            # Get all visits
            visits = self.db.query(Visit).all()

            # Categorize visits
            referral_counts = {
                'Hospitals': 0,
                'Veterans Centers': 0,
                'Assisted Living/Nursing': 0,
                'Doctors Offices': 0,
                'Rehabs': 0,
                'Home Health/Hospice': 0,
                'Community Centers': 0,
                'Pharmacies/Supply': 0,
                'Social Services': 0,
                'Other': 0
            }

            for visit in visits:
                referral_type = self._categorize_referral_type(
                    visit.business_name or "",
                    visit.address or "",
                    visit.notes or ""
                )
                referral_counts[referral_type] += 1

            # Convert to list format, excluding "Other" if it's 0 or if we want to show top 5
            results = [
                {"type": k, "count": v}
                for k, v in referral_counts.items()
                if v > 0  # Only include types with visits
            ]

            # Sort by count descending
            results.sort(key=lambda x: x['count'], reverse=True)

            return results

        except Exception as e:
            logger.error(f"Error getting referral types: {str(e)}")
            return []

    def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent activity across all data types"""
        try:
            activities = []

            # Recent ActivityLogs (business card scans, calls, emails, etc.)
            recent_activity_logs = self.db.query(ActivityLog).order_by(
                desc(ActivityLog.created_at)
            ).limit(limit * 2).all()  # Get more to ensure we have enough after filtering

            for log in recent_activity_logs:
                # Get user name from email if available
                user_name = log.user_email.split('@')[0] if log.user_email else 'Unknown'

                activities.append({
                    "type": log.activity_type,
                    "description": log.description or log.title or f"{log.activity_type} activity",
                    "date": log.created_at.isoformat(),
                    "details": {
                        "user": user_name,
                        "contact_id": log.contact_id,
                        "company_id": log.company_id,
                        "deal_id": log.deal_id
                    }
                })

            # Recent visits
            recent_visits = self.db.query(Visit).order_by(
                desc(Visit.visit_date)
            ).limit(limit).all()

            for visit in recent_visits:
                activities.append({
                    "type": "visit",
                    "description": f"Visit to {visit.business_name}",
                    "date": visit.visit_date.isoformat(),
                    "details": {
                        "stop": visit.stop_number,
                        "address": visit.address,
                        "city": visit.city
                    }
                })

            # Recent time entries
            recent_time = self.db.query(TimeEntry).order_by(
                desc(TimeEntry.created_at)
            ).limit(limit).all()

            for entry in recent_time:
                activities.append({
                    "type": "time_entry",
                    "description": f"Logged {entry.hours_worked} hours",
                    "date": entry.created_at.isoformat(),
                    "details": {
                        "date": entry.date.isoformat(),
                        "hours": entry.hours_worked
                    }
                })

            # Recent contacts
            recent_contacts = self.db.query(Contact).order_by(
                desc(Contact.created_at)
            ).limit(limit).all()

            for contact in recent_contacts:
                activities.append({
                    "type": "contact",
                    "description": f"Added contact: {contact.name or contact.company}",
                    "date": contact.created_at.isoformat(),
                    "details": {
                        "name": contact.name,
                        "company": contact.company,
                        "phone": contact.phone,
                        "email": contact.email
                    }
                })

            # Sort by date and return top N
            activities.sort(key=lambda x: x['date'], reverse=True)
            return activities[:limit]

        except Exception as e:
            logger.error(f"Error getting recent activity: {str(e)}")
            return []

    def get_weekly_summary(self) -> Dict[str, Any]:
        """Get this week's summary"""
        try:
            # Start of this week (Monday)
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

            # Visits this week
            visits_this_week = self.db.query(Visit).filter(
                Visit.visit_date >= start_of_week
            ).count()

            # Hours this week
            hours_this_week = self.db.query(func.sum(TimeEntry.hours_worked)).filter(
                TimeEntry.date >= start_of_week
            ).scalar() or 0

            # New contacts this week
            contacts_this_week = self.db.query(Contact).filter(
                Contact.created_at >= start_of_week
            ).count()

            return {
                "visits_this_week": visits_this_week,
                "hours_this_week": round(hours_this_week, 2),
                "contacts_this_week": contacts_this_week,
                "week_start": start_of_week.isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting weekly summary: {str(e)}")
            return {}

    def get_financial_summary(self) -> Dict[str, Any]:
        """Get comprehensive financial summary"""
        try:
            # Total financials - COSTS ONLY (no revenue from visits)
            total_costs = self.db.query(func.sum(FinancialEntry.total_daily_cost)).scalar() or 0

            # This month
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            costs_this_month = self.db.query(func.sum(FinancialEntry.total_daily_cost)).filter(
                FinancialEntry.date >= current_month_start
            ).scalar() or 0

            # Cost breakdown
            total_labor_cost = self.db.query(func.sum(FinancialEntry.labor_cost)).scalar() or 0
            total_mileage_cost = self.db.query(func.sum(FinancialEntry.mileage_cost)).scalar() or 0
            total_materials_cost = self.db.query(func.sum(FinancialEntry.materials_cost)).scalar() or 0

            # Visit metrics
            total_visits = self.db.query(Visit).count()
            cost_per_visit = total_costs / total_visits if total_visits > 0 else 0

            return {
                "total_costs": round(total_costs, 2),
                "costs_this_month": round(costs_this_month, 2),
                "total_labor_cost": round(total_labor_cost, 2),
                "total_mileage_cost": round(total_mileage_cost, 2),
                "total_materials_cost": round(total_materials_cost, 2),
                "cost_per_visit": round(cost_per_visit, 2)
            }

        except Exception as e:
            logger.error(f"Error getting financial summary: {str(e)}")
            return {}

    def get_revenue_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get costs grouped by month (no revenue from visits)"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)

            results = self.db.query(
                func.date_trunc('month', FinancialEntry.date).label('month'),
                func.sum(FinancialEntry.total_daily_cost).label('costs')
            ).filter(
                FinancialEntry.date >= start_date
            ).group_by(
                func.date_trunc('month', FinancialEntry.date)
            ).order_by('month').all()

            return [
                {
                    "month": result.month.strftime("%Y-%m"),
                    "revenue": 0,  # No revenue from visits
                    "costs": round(result.costs, 2),
                    "profit": round(0 - result.costs, 2)  # Negative profit (costs only)
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error getting revenue by month: {str(e)}")
            return []

    def get_costs_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get costs grouped by month - exclude future months"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)
            # Don't include future months - only up to current month
            current_month_start = datetime(end_date.year, end_date.month, 1)

            results = self.db.query(
                func.date_trunc('month', FinancialEntry.date).label('month'),
                func.sum(FinancialEntry.total_daily_cost).label('costs')
            ).filter(
                FinancialEntry.date >= start_date,
                FinancialEntry.date < current_month_start.replace(day=1) if end_date.day == 1 else func.date_trunc('month', FinancialEntry.date) <= func.date_trunc('month', current_month_start)
            ).group_by(
                func.date_trunc('month', FinancialEntry.date)
            ).order_by('month').all()

            # Filter out future months in Python (more reliable)
            filtered_results = []
            for result in results:
                result_month = result.month
                # Only include months up to and including the current month
                if result_month.year < end_date.year or (result_month.year == end_date.year and result_month.month <= end_date.month):
                    filtered_results.append({
                        "month": result_month.strftime("%Y-%m"),
                        "costs": round(result.costs, 2)
                    })

            return filtered_results

        except Exception as e:
            logger.error(f"Error getting costs by month: {str(e)}")
            return []
