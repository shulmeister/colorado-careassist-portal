"""
tool_executor.py — Shared tool execution engine for all Gigi channels.

Single implementation of every tool in CANONICAL_TOOLS.  All three channel
handlers (telegram_bot, ringcentral_bot, voice_brain) delegate here.

Usage:
    import gigi.tool_executor as tool_executor
    tool_executor.set_google_service(self.google)
    result = await tool_executor.execute(tool_name, tool_input)

Adding a new tool:
  1. Add the schema to gigi/tool_registry.py  CANONICAL_TOOLS
  2. Add an elif branch here in execute()
  3. Done — all channels pick it up automatically.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date

import psycopg2.pool

logger = logging.getLogger(__name__)

# ============================================================
# Shared database connection pool (initialized on first use)
# ============================================================

_db_pool = None


def _get_db_pool():
    global _db_pool
    if _db_pool is None:
        db_url = os.environ.get(
            "DATABASE_URL", "postgresql://careassist@localhost:5432/careassist"
        )
        _db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2, maxconn=10, dsn=db_url
        )
    return _db_pool


def _get_conn():
    """Get a pooled database connection."""
    return _get_db_pool().getconn()


def _put_conn(conn):
    """Return a connection to the pool."""
    if conn is None:
        return
    try:
        _get_db_pool().putconn(conn)
    except Exception as e:
        logger.warning(f"Failed to return connection to pool: {e}")


# ============================================================
# Module-level shared services (initialized once at import)
# ============================================================

try:
    from gigi.chief_of_staff_tools import cos_tools
except Exception:
    cos_tools = None

try:
    from services.wellsky_service import WellSkyService
except Exception:
    WellSkyService = None

try:
    from gigi.memory_system import ImpactLevel, MemorySource, MemorySystem, MemoryType

    _memory_system = MemorySystem()
    MEMORY_AVAILABLE = True
except Exception:
    _memory_system = None
    MEMORY_AVAILABLE = False
    MemoryType = MemorySource = ImpactLevel = None  # type: ignore

try:
    from gigi.failure_handler import FailureHandler

    _failure_handler = FailureHandler()
    FAILURE_HANDLER_AVAILABLE = True
except Exception:
    _failure_handler = None
    FAILURE_HANDLER_AVAILABLE = False

# Injected per-channel service (set by channel handler on startup)
_google_service = None


def set_google_service(svc) -> None:
    """Register the Google service instance from the channel handler."""
    global _google_service
    _google_service = svc


# ============================================================
# Main dispatch function
# ============================================================


async def execute(tool_name: str, tool_input: dict) -> str:
    """Execute a named tool and return the result as a JSON string."""
    try:
        # === CHIEF-OF-STAFF / ENTERTAINMENT ===

        if tool_name == "search_events":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.search_events(
                query=tool_input.get("query", ""),
                city=tool_input.get("city", "Denver"),
                state=tool_input.get("state", "CO"),
                start_date=tool_input.get("start_date"),
                end_date=tool_input.get("end_date"),
                limit=tool_input.get("limit", 10),
            )
            return json.dumps(result)

        elif tool_name == "search_concerts":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.search_concerts(query=tool_input.get("query", ""))
            return json.dumps(result)

        elif tool_name == "buy_tickets_request":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.buy_tickets_request(
                artist=tool_input.get("artist"),
                venue=tool_input.get("venue"),
                quantity=tool_input.get("quantity", 2),
            )
            return json.dumps(result)

        elif tool_name == "book_table_request":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.book_table_request(
                restaurant=tool_input.get("restaurant"),
                party_size=tool_input.get("party_size"),
                date=tool_input.get("date"),
                time=tool_input.get("time"),
            )
            return json.dumps(result)

        elif tool_name == "explore_national_parks":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.explore_national_parks(
                action=tool_input.get("action", "parks"),
                query=tool_input.get("query"),
                park_code=tool_input.get("park_code"),
                state=tool_input.get("state"),
                limit=tool_input.get("limit", 5),
            )
            return json.dumps(result)

        elif tool_name == "explore_art":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.explore_art(
                action=tool_input.get("action", "search"),
                query=tool_input.get("query"),
                artwork_id=tool_input.get("artwork_id"),
                art_type=tool_input.get("art_type"),
                origin=tool_input.get("origin"),
                material=tool_input.get("material"),
                earliest_year=tool_input.get("earliest_year"),
                latest_year=tool_input.get("latest_year"),
                limit=tool_input.get("limit", 5),
            )
            return json.dumps(result)

        elif tool_name == "search_phish":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.search_phish(
                action=tool_input.get("action", "shows"),
                query=tool_input.get("query"),
                date=tool_input.get("date"),
                song_slug=tool_input.get("song_slug"),
                limit=tool_input.get("limit", 5),
            )
            return json.dumps(result)

        elif tool_name == "search_books":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.search_books(
                action=tool_input.get("action", "search"),
                query=tool_input.get("query"),
                book_id=tool_input.get("book_id"),
                author=tool_input.get("author"),
                subject=tool_input.get("subject"),
                isbn=tool_input.get("isbn"),
                filter_type=tool_input.get("filter_type"),
                limit=tool_input.get("limit", 5),
            )
            return json.dumps(result)

        elif tool_name == "search_nytimes":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.search_nytimes(
                action=tool_input.get("action", "top_stories"),
                query=tool_input.get("query"),
                section=tool_input.get("section", "home"),
                period=tool_input.get("period", 1),
                begin_date=tool_input.get("begin_date"),
                end_date=tool_input.get("end_date"),
                list_name=tool_input.get("list_name"),
                limit=tool_input.get("limit", 5),
            )
            return json.dumps(result)

        elif tool_name == "search_f1":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.search_f1(
                action=tool_input.get("action", "standings"),
                query=tool_input.get("query"),
                year=tool_input.get("year"),
                round_num=tool_input.get("round_num"),
                limit=tool_input.get("limit", 10),
            )
            return json.dumps(result)

        # === WELLSKY / OPERATIONS ===

        elif tool_name == "get_client_current_status":
            client_name = tool_input.get("client_name", "")
            if not client_name:
                return json.dumps({"error": "No client name provided"})

            def _sync_client_status(name_val):
                from datetime import datetime

                conn = None
                cur = None
                try:
                    conn = _get_conn()
                    cur = conn.cursor()
                    search_lower = f"%{name_val.lower()}%"
                    cur.execute(
                        """
                        SELECT id, full_name, address, city
                        FROM cached_patients
                        WHERE is_active = true
                        AND (lower(full_name) LIKE %s OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                        LIMIT 1
                    """,
                        (search_lower, search_lower, search_lower),
                    )
                    client_row = cur.fetchone()
                    if not client_row:
                        return {
                            "status": "not_found",
                            "message": f"Could not find active client matching '{name_val}'",
                        }
                    client_id, client_full_name, addr, city = client_row
                    cur.execute(
                        """
                        SELECT a.scheduled_start, a.scheduled_end,
                               p.full_name as caregiver_name, p.phone as caregiver_phone, a.status
                        FROM cached_appointments a
                        LEFT JOIN cached_practitioners p ON a.practitioner_id = p.id
                        WHERE a.patient_id = %s
                        AND a.scheduled_start >= CURRENT_DATE
                        AND a.scheduled_start < CURRENT_DATE + INTERVAL '1 day'
                        ORDER BY a.scheduled_start ASC
                    """,
                        (client_id,),
                    )
                    shifts = cur.fetchall()
                    if not shifts:
                        return {
                            "client": client_full_name,
                            "status": "no_shifts",
                            "message": f"No shifts scheduled for {client_full_name} today.",
                        }
                    now = datetime.now()
                    current_shift = next_shift = last_shift = None
                    for s in shifts:
                        start, end, cg_name, cg_phone, status = s
                        if start <= now <= end:
                            current_shift = s
                            break
                        elif start > now:
                            if not next_shift:
                                next_shift = s
                        elif end < now:
                            last_shift = s
                    if current_shift:
                        start, end, cg_name, _, _ = current_shift
                        return {
                            "client": client_full_name,
                            "status": "active",
                            "message": f"YES. {cg_name} is with {client_full_name} right now.\nShift: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}\nLocation: {addr}, {city}",
                        }
                    elif next_shift:
                        start, end, cg_name, _, _ = next_shift
                        return {
                            "client": client_full_name,
                            "status": "upcoming",
                            "message": f"No one is there right now. Next shift is {cg_name} at {start.strftime('%I:%M %p')}.",
                        }
                    else:
                        start, end, cg_name, _, _ = (
                            last_shift
                            if last_shift
                            else (None, None, "None", None, None)
                        )
                        msg = (
                            f"No one is there right now. {cg_name} finished at {end.strftime('%I:%M %p')}."
                            if last_shift
                            else f"No active shifts right now for {client_full_name}."
                        )
                        return {
                            "client": client_full_name,
                            "status": "completed",
                            "message": msg,
                        }
                except Exception as e:
                    logger.error(f"Status check failed: {e}")
                    if conn:
                        conn.rollback()
                    return {"error": str(e)}
                finally:
                    if cur:
                        cur.close()
                    _put_conn(conn)

            result = await asyncio.to_thread(_sync_client_status, client_name)
            return json.dumps(result)

        elif tool_name == "get_calendar_events":
            if not _google_service:
                return json.dumps(
                    {
                        "error": "Google service not configured. Missing GOOGLE_WORK_* environment variables."
                    }
                )
            days = tool_input.get("days", 1)
            events = _google_service.get_calendar_events(days=min(days, 7))
            if not events:
                return json.dumps({"message": "No upcoming events found", "events": []})
            return json.dumps({"events": events})

        elif tool_name == "search_emails":
            if not _google_service:
                return json.dumps(
                    {
                        "error": "Google service not configured. Missing GOOGLE_WORK_* environment variables."
                    }
                )
            query = tool_input.get("query", "is:unread")
            max_results = tool_input.get("max_results", 5)
            emails = _google_service.search_emails(query=query, max_results=max_results)
            if not emails:
                return json.dumps(
                    {"message": f"No emails found for query: {query}", "emails": []}
                )
            return json.dumps({"emails": emails})

        elif tool_name == "get_weather":
            location = tool_input.get("location", "")
            if not location:
                return json.dumps({"error": "No location provided"})
            try:
                import httpx

                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"https://wttr.in/{location}?format=j1")
                    if resp.status_code == 200:
                        w = resp.json()
                        current = w.get("current_condition", [{}])[0]
                        area = w.get("nearest_area", [{}])[0]
                        area_name = area.get("areaName", [{}])[0].get("value", location)
                        forecast_today = w.get("weather", [{}])[0]
                        return json.dumps(
                            {
                                "location": area_name,
                                "temp_f": current.get("temp_F"),
                                "feels_like_f": current.get("FeelsLikeF"),
                                "description": current.get("weatherDesc", [{}])[0].get(
                                    "value"
                                ),
                                "humidity": current.get("humidity"),
                                "wind_mph": current.get("windspeedMiles"),
                                "high_f": forecast_today.get("maxtempF"),
                                "low_f": forecast_today.get("mintempF"),
                            }
                        )
            except Exception as e:
                logger.warning(f"wttr.in failed: {e}")
            try:
                from ddgs import DDGS

                def _ddg_weather():
                    return list(
                        DDGS().text(f"current weather {location}", max_results=1)
                    )

                results = await asyncio.to_thread(_ddg_weather)
                if results:
                    return json.dumps(
                        {"location": location, "weather": results[0].get("body")}
                    )
            except Exception as e:
                logger.warning(f"DDG weather fallback failed: {e}")
            return json.dumps({"error": "Weather service temporarily unavailable"})

        elif tool_name == "get_wellsky_clients":
            search_name = tool_input.get("search_name", "")
            active_only = tool_input.get("active_only", True)

            def _sync_get_clients():
                conn = None
                cur = None
                try:
                    conn = _get_conn()
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email
                                 FROM cached_patients WHERE (lower(full_name) LIKE %s
                                 OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)"""
                        params = [search_lower, search_lower, search_lower]
                        if active_only:
                            sql += " AND is_active = true"
                        sql += " ORDER BY full_name LIMIT 20"
                        cur.execute(sql, params)
                    else:
                        sql = "SELECT id, first_name, last_name, full_name, phone, home_phone, email FROM cached_patients"
                        if active_only:
                            sql += " WHERE is_active = true"
                        sql += " ORDER BY full_name LIMIT 100"
                        cur.execute(sql)
                    rows = cur.fetchall()
                    client_list = [
                        {
                            "id": str(r[0]),
                            "first_name": r[1],
                            "last_name": r[2],
                            "name": r[3],
                            "phone": r[4] or r[5] or "",
                            "email": r[6] or "",
                        }
                        for r in rows
                    ]
                    return {
                        "count": len(client_list),
                        "clients": client_list,
                        "search": search_name or "all",
                    }
                except Exception as e:
                    logger.error(f"Client cache lookup failed: {e}")
                    if conn:
                        conn.rollback()
                    return {"error": f"Client lookup failed: {str(e)}"}
                finally:
                    if cur:
                        cur.close()
                    _put_conn(conn)

            return json.dumps(await asyncio.to_thread(_sync_get_clients))

        elif tool_name == "get_wellsky_caregivers":
            search_name = tool_input.get("search_name", "")
            active_only = tool_input.get("active_only", True)

            def _sync_get_caregivers():
                conn = None
                cur = None
                try:
                    conn = _get_conn()
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email,
                                        preferred_language
                                 FROM cached_practitioners WHERE (lower(full_name) LIKE %s
                                 OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)"""
                        params = [search_lower, search_lower, search_lower]
                        if active_only:
                            sql += " AND is_active = true"
                        sql += " ORDER BY full_name LIMIT 20"
                        cur.execute(sql, params)
                    else:
                        sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email,
                                        preferred_language
                                 FROM cached_practitioners"""
                        if active_only:
                            sql += " WHERE is_active = true"
                        sql += " ORDER BY full_name LIMIT 100"
                        cur.execute(sql)
                    rows = cur.fetchall()
                    cg_list = [
                        {
                            "id": str(r[0]),
                            "first_name": r[1],
                            "last_name": r[2],
                            "name": r[3],
                            "phone": r[4] or r[5] or "",
                            "email": r[6] or "",
                            "preferred_language": r[7] or "English",
                        }
                        for r in rows
                    ]
                    return {
                        "count": len(cg_list),
                        "caregivers": cg_list,
                        "search": search_name or "all",
                    }
                except Exception as e:
                    logger.error(f"Caregiver cache lookup failed: {e}")
                    if conn:
                        conn.rollback()
                    return {"error": f"Caregiver lookup failed: {str(e)}"}
                finally:
                    if cur:
                        cur.close()
                    _put_conn(conn)

            return json.dumps(await asyncio.to_thread(_sync_get_caregivers))

        elif tool_name == "get_wellsky_shifts":
            days = min(tool_input.get("days", 7), 30)
            past_days = min(tool_input.get("past_days", 0), 90)
            open_only = tool_input.get("open_only", False)
            client_id = tool_input.get("client_id")
            caregiver_id = tool_input.get("caregiver_id")

            def _sync_get_shifts():
                if past_days > 0:
                    from datetime import timedelta as td

                    date_from = date.today() - td(days=past_days)
                    date_to = date.today()
                else:
                    from datetime import timedelta as td

                    date_from = date.today()
                    date_to = date.today() + td(days=days)
                conn = None
                cur = None
                try:
                    conn = _get_conn()
                    cur = conn.cursor()
                    conditions = ["a.scheduled_start >= %s", "a.scheduled_start < %s"]
                    params = [date_from, date_to]
                    if client_id:
                        conditions.append("a.patient_id = %s")
                        params.append(client_id)
                    if caregiver_id:
                        conditions.append("a.practitioner_id = %s")
                        params.append(caregiver_id)
                    if open_only:
                        conditions.append(
                            "(a.practitioner_id IS NULL OR a.status IN ('open', 'pending', 'proposed'))"
                        )
                    where = " AND ".join(conditions)
                    cur.execute(
                        f"""
                        SELECT a.id, a.scheduled_start, a.scheduled_end,
                               a.actual_start, a.actual_end, a.status,
                               a.patient_id, a.practitioner_id, a.service_type,
                               p.full_name as client_name, pr.full_name as caregiver_name
                        FROM cached_appointments a
                        LEFT JOIN cached_patients p ON a.patient_id = p.id
                        LEFT JOIN cached_practitioners pr ON a.practitioner_id = pr.id
                        WHERE {where} ORDER BY a.scheduled_start LIMIT 50
                    """,
                        params,
                    )
                    shift_list = []
                    total_hours = 0
                    for row in cur.fetchall():
                        scheduled_hours = None
                        if row[1] and row[2]:
                            scheduled_hours = round(
                                (row[2] - row[1]).total_seconds() / 3600, 1
                            )
                            total_hours += scheduled_hours
                        actual_hours = None
                        if row[3] and row[4]:
                            actual_hours = round(
                                (row[4] - row[3]).total_seconds() / 3600, 1
                            )
                        shift_list.append(
                            {
                                "id": row[0],
                                "scheduled_start": row[1].isoformat()
                                if row[1]
                                else None,
                                "scheduled_end": row[2].isoformat() if row[2] else None,
                                "actual_start": row[3].isoformat() if row[3] else None,
                                "actual_end": row[4].isoformat() if row[4] else None,
                                "status": row[5],
                                "client_id": row[6],
                                "caregiver_id": row[7],
                                "service_type": row[8],
                                "client_name": row[9] or "Unknown",
                                "caregiver_name": row[10] or "Unassigned",
                                "scheduled_hours": scheduled_hours,
                                "actual_hours": actual_hours,
                            }
                        )
                    return {
                        "count": len(shift_list),
                        "total_scheduled_hours": round(total_hours, 1),
                        "date_range": f"{date_from.isoformat()} to {date_to.isoformat()}",
                        "shifts": shift_list,
                    }
                except Exception as e:
                    logger.error(f"Error querying cached shifts: {e}")
                    if conn:
                        conn.rollback()
                    return {"error": f"Database error: {str(e)}"}
                finally:
                    if cur:
                        cur.close()
                    _put_conn(conn)

            return json.dumps(await asyncio.to_thread(_sync_get_shifts))

        elif tool_name == "clock_in_shift":
            appointment_id = tool_input.get("appointment_id", "")
            caregiver_name = tool_input.get("caregiver_name", "")
            notes = tool_input.get("notes", "Clocked in via Gigi")
            if not appointment_id:
                return json.dumps(
                    {
                        "error": "Missing appointment_id. Use get_wellsky_shifts first to find the shift, then pass the appointment ID."
                    }
                )

            # Strip composite key suffix if present (e.g. "8006814_2026-02-27" → "8006814")
            clean_id = (
                appointment_id.split("_")[0]
                if "_" in appointment_id
                else appointment_id
            )

            def _clock_in():
                if WellSkyService is None:
                    return {"error": "WellSky service not available"}
                ws = WellSkyService()
                success, message = ws.clock_in_shift(clean_id, notes=notes)
                if success:
                    return {
                        "success": True,
                        "message": message,
                        "appointment_id": clean_id,
                        "caregiver_name": caregiver_name,
                    }
                return {
                    "success": False,
                    "message": message,
                    "appointment_id": clean_id,
                    "caregiver_name": caregiver_name,
                    "fallback_action": "Use save_memory to log this clock-in request for manual processing. Tell the caregiver you have logged their clock-in and it will be updated.",
                }

            return json.dumps(await asyncio.to_thread(_clock_in))

        elif tool_name == "clock_out_shift":
            appointment_id = tool_input.get("appointment_id", "")
            caregiver_name = tool_input.get("caregiver_name", "")
            notes = tool_input.get("notes", "Clocked out via Gigi")
            if not appointment_id:
                return json.dumps(
                    {
                        "error": "Missing appointment_id. Use get_wellsky_shifts first to find the shift, then pass the appointment ID."
                    }
                )

            # Strip composite key suffix if present (e.g. "8006814_2026-02-27" → "8006814")
            clean_id = (
                appointment_id.split("_")[0]
                if "_" in appointment_id
                else appointment_id
            )

            def _clock_out():
                if WellSkyService is None:
                    return {"error": "WellSky service not available"}
                ws = WellSkyService()
                success, message = ws.clock_out_shift(clean_id, notes=notes)
                if success:
                    return {
                        "success": True,
                        "message": message,
                        "appointment_id": clean_id,
                        "caregiver_name": caregiver_name,
                    }
                return {
                    "success": False,
                    "message": message,
                    "appointment_id": clean_id,
                    "caregiver_name": caregiver_name,
                    "fallback_action": "Use save_memory to log this clock-out request for manual processing. Tell the caregiver you have logged their clock-out and it will be updated.",
                }

            return json.dumps(await asyncio.to_thread(_clock_out))

        elif tool_name == "find_replacement_caregiver":
            shift_id = tool_input.get("shift_id", "")
            original_caregiver_id = tool_input.get("original_caregiver_id", "")
            reason = tool_input.get("reason", "called out")
            if not shift_id or not original_caregiver_id:
                return json.dumps(
                    {"error": "Missing shift_id or original_caregiver_id"}
                )

            def _find_replacement():
                try:
                    from sales.shift_filling.engine import shift_filling_engine

                    campaign = shift_filling_engine.process_calloff(
                        shift_id=shift_id,
                        caregiver_id=original_caregiver_id,
                        reason=reason,
                        reported_by="gigi",
                    )
                    if not campaign:
                        return {
                            "success": False,
                            "error": "Could not create replacement campaign",
                        }
                    return {
                        "success": True,
                        "campaign_id": campaign.id,
                        "status": campaign.status.value
                        if hasattr(campaign.status, "value")
                        else str(campaign.status),
                        "caregivers_contacted": campaign.total_contacted,
                        "message": f"Replacement search started. Contacting {campaign.total_contacted} caregivers via SMS.",
                    }
                except ImportError:
                    return {"error": "Shift filling engine not available"}
                except Exception as e:
                    return {"error": f"Shift filling failed: {str(e)}"}

            return json.dumps(await asyncio.to_thread(_find_replacement))

        # === WEB / RESEARCH ===

        elif tool_name == "web_search":
            query = tool_input.get("query", "")
            if not query:
                return json.dumps({"error": "No search query provided"})
            try:
                import httpx

                brave_api_key = os.getenv("BRAVE_API_KEY")
                if brave_api_key:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            "https://api.search.brave.com/res/v1/web/search",
                            headers={"X-Subscription-Token": brave_api_key},
                            params={"q": query, "count": 5},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            results = [
                                {
                                    "title": r.get("title"),
                                    "description": r.get("description"),
                                    "url": r.get("url"),
                                }
                                for r in data.get("web", {}).get("results", [])[:5]
                            ]
                            return json.dumps({"query": query, "results": results})
                try:
                    from ddgs import DDGS

                    def _ddg_search():
                        return list(DDGS().text(query, max_results=5))

                    results = await asyncio.to_thread(_ddg_search)
                    if results:
                        formatted = [
                            {
                                "title": r.get("title", ""),
                                "description": r.get("body", ""),
                                "url": r.get("href", ""),
                            }
                            for r in results
                        ]
                        return json.dumps({"query": query, "results": formatted})
                except Exception as ddg_err:
                    logger.warning(f"DDG search fallback failed: {ddg_err}")
                return json.dumps(
                    {
                        "query": query,
                        "message": "No results found. Try a more specific query.",
                    }
                )
            except Exception as e:
                logger.error(f"Web search error: {e}")
                return json.dumps({"error": f"Search failed: {str(e)}"})

        elif tool_name == "browse_webpage":
            from gigi.claude_code_tools import browse_with_claude

            url = tool_input.get("url", "")
            result = await browse_with_claude(
                task=f"Navigate to {url} and extract the main text content of the page.",
                url=url,
            )
            return json.dumps(result)

        elif tool_name == "take_screenshot":
            from gigi.claude_code_tools import browse_with_claude

            url = tool_input.get("url", "")
            result = await browse_with_claude(
                task=f"Navigate to {url} and describe what the page looks like and its content.",
                url=url,
            )
            return json.dumps(result)

        elif tool_name == "deep_research":
            question = tool_input.get("question", "")
            try:
                import httpx

                async with httpx.AsyncClient(timeout=150.0) as client:
                    resp = await client.post(
                        "http://localhost:3002/api/research/deep",
                        json={"question": question},
                    )
                    data = resp.json()
                    answer = data.get("answer", "Research unavailable.")
                    confidence = data.get("confidence", 0)
                    tools_used = data.get("metadata", {}).get("tools_used", [])
                    duration = data.get("metadata", {}).get("total_duration_seconds", 0)
                    return f"{answer}\n\n---\nConfidence: {confidence:.0%} | Data sources: {len(tools_used)} | Research time: {duration:.0f}s"
            except Exception as e:
                logger.error(f"Deep research failed: {e}")
                return json.dumps({"error": f"Elite Trading research unavailable: {e}"})

        # === MARKET DATA ===

        elif tool_name == "get_stock_price":
            symbol = tool_input.get("symbol", "").upper()
            if not symbol:
                return json.dumps({"error": "No stock symbol provided"})
            try:
                import httpx

                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d",
                        headers={"User-Agent": "Mozilla/5.0 (CareAssist/1.0)"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        meta = (
                            data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                        )
                        price = meta.get("regularMarketPrice")
                        if price:
                            prev = meta.get("chartPreviousClose") or meta.get(
                                "previousClose", 0
                            )
                            change = price - prev if prev else 0
                            pct = (change / prev * 100) if prev else 0
                            return json.dumps(
                                {
                                    "symbol": symbol,
                                    "price": f"${price:.2f}",
                                    "previous_close": f"${prev:.2f}",
                                    "change": f"${change:+.2f}",
                                    "change_percent": f"{pct:+.2f}%",
                                    "currency": meta.get("currency", "USD"),
                                }
                            )
                from ddgs import DDGS

                def _ddg_stock():
                    return list(
                        DDGS().text(f"{symbol} stock price today", max_results=1)
                    )

                results = await asyncio.to_thread(_ddg_stock)
                if results:
                    return json.dumps(
                        {"symbol": symbol, "info": results[0].get("body", "")}
                    )
                return json.dumps({"error": f"Could not find stock price for {symbol}"})
            except Exception as e:
                logger.error(f"Stock price error: {e}")
                return json.dumps({"error": f"Stock lookup failed: {str(e)}"})

        elif tool_name == "get_crypto_price":
            symbol = tool_input.get("symbol", "").upper()
            if not symbol:
                return json.dumps({"error": "No crypto symbol provided"})
            crypto_map = {
                "BTC": "bitcoin",
                "BITCOIN": "bitcoin",
                "ETH": "ethereum",
                "ETHEREUM": "ethereum",
                "DOGE": "dogecoin",
                "DOGECOIN": "dogecoin",
                "SOL": "solana",
                "SOLANA": "solana",
                "XRP": "ripple",
                "RIPPLE": "ripple",
                "ADA": "cardano",
                "CARDANO": "cardano",
                "MATIC": "matic-network",
                "POLYGON": "matic-network",
                "DOT": "polkadot",
                "POLKADOT": "polkadot",
                "AVAX": "avalanche-2",
                "AVALANCHE": "avalanche-2",
                "LINK": "chainlink",
                "CHAINLINK": "chainlink",
            }
            coin_id = crypto_map.get(symbol, symbol.lower())
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if coin_id in data:
                            info = data[coin_id]
                            return json.dumps(
                                {
                                    "symbol": symbol,
                                    "name": coin_id.replace("-", " ").title(),
                                    "price": f"${info.get('usd', 0):,.2f}",
                                    "change_24h": f"{info.get('usd_24h_change', 0):.2f}%",
                                    "market_cap": f"${info.get('usd_market_cap', 0):,.0f}",
                                }
                            )
                return json.dumps(
                    {
                        "error": f"Could not find price for {symbol}. Try BTC, ETH, DOGE, SOL, etc."
                    }
                )
            except Exception as e:
                logger.error(f"Crypto price error: {e}")
                return json.dumps({"error": f"Crypto lookup failed: {str(e)}"})

        elif tool_name == "get_polybot_status":
            try:
                import httpx

                async with httpx.AsyncClient(timeout=30.0) as client:
                    polybot_resp, mlbot_resp = await asyncio.gather(
                        client.get("http://localhost:3002/api/polybot/status"),
                        client.get("http://localhost:3002/api/ml-bot/status"),
                        return_exceptions=True,
                    )
                    report = []
                    if isinstance(polybot_resp, Exception):
                        report.append("POLYBOT: UNAVAILABLE")
                    else:
                        pb = polybot_resp.json()
                        portfolio = pb.get("portfolio", {})
                        perf = pb.get("performance", {})
                        risk = pb.get("risk", {})
                        poly_positions = pb.get("positions", {}).get("polymarket", [])
                        report.append(
                            f"POLYBOT (Polymarket) — {'Paper Mode' if pb.get('paper_mode') else 'LIVE'}"
                        )
                        report.append(
                            f"Status: {'RUNNING' if pb.get('is_running') else 'STOPPED'} | Cycles: {pb.get('cycles_completed', 0)}"
                        )
                        report.append(
                            f"Portfolio: ${portfolio.get('total_value', 0):,.2f} | P&L: ${portfolio.get('pnl', 0):,.2f} ({portfolio.get('pnl_pct', 0):.2f}%)"
                        )
                        report.append(
                            f"Trades: {perf.get('total_trades', 0)} total | {perf.get('winning_trades', 0)}W/{perf.get('losing_trades', 0)}L ({perf.get('win_rate', 0):.1f}% win rate)"
                        )
                        report.append(
                            f"Drawdown: {risk.get('drawdown_pct', 0):.1f}% | Kill switch: {risk.get('kill_switch', {}).get('state', '?')}"
                        )
                        report.append("")
                        strategies = pb.get("strategies", [])
                        enabled_names = [
                            s["name"] for s in strategies if s.get("enabled")
                        ]
                        report.append(
                            f"Strategies ({len(enabled_names)} active): {', '.join(enabled_names)}"
                        )
                        report.append("")
                        strat_perf = pb.get("strategy_performance", {})
                        if strat_perf:
                            report.append("Strategy Performance:")
                            for name, sp in sorted(
                                strat_perf.items(),
                                key=lambda x: x[1].get("realized_pnl", 0),
                                reverse=True,
                            ):
                                report.append(
                                    f"  {name}: {sp.get('total_trades', 0)} trades, ${sp.get('realized_pnl', 0):+,.2f} P&L ({sp.get('win_rate', 0):.0f}% WR)"
                                )
                            report.append("")
                        report.append(f"Open Positions ({len(poly_positions)}):")
                        for p in poly_positions[:8]:
                            report.append(
                                f"  {p.get('symbol', '?')[:50]}: {p.get('amount', 0):.1f} shares @ {p.get('entry_price', 0):.4f} (P&L: ${p.get('unrealized_pnl', 0):+.2f})"
                            )
                        if len(poly_positions) > 8:
                            report.append(f"  ... and {len(poly_positions) - 8} more")
                    report.append("")
                    if isinstance(mlbot_resp, Exception):
                        report.append("ML BOT (Crypto): UNAVAILABLE")
                    else:
                        ml = mlbot_resp.json()
                        ml_port = ml.get("portfolio", {})
                        ml_stats = ml.get("stats", {})
                        report.append(
                            f"ML BOT (Crypto) — {'Paper Mode' if ml.get('paper_trading') else 'LIVE'}"
                        )
                        report.append(f"Status: {ml.get('status', '?').upper()}")
                        report.append(
                            f"Portfolio: ${ml_port.get('current_value', 0):,.2f} | P&L: ${ml_port.get('pnl', 0):,.2f} ({ml_port.get('pnl_pct', 0):.2f}%)"
                        )
                        report.append(
                            f"Trades: {ml_stats.get('trades_executed', 0)} | {ml_stats.get('winning_trades', 0)}W/{ml_stats.get('losing_trades', 0)}L ({ml_stats.get('win_rate', 0):.1f}% WR)"
                        )
                        for mp in ml.get("positions", [])[:5]:
                            report.append(
                                f"  {mp.get('symbol', '?')}: {mp.get('amount', 0):.4f} @ ${mp.get('entry_price', 0):,.2f}"
                            )
                    return "\n".join(report)
            except Exception as e:
                logger.error(f"Polybot status failed: {e}")
                return json.dumps({"error": f"Trading bots unavailable: {e}"})

        elif tool_name == "get_weather_arb_status":
            try:
                import httpx

                result = {
                    "polymarket": {"status": "offline"},
                    "kalshi": {"status": "offline"},
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    try:
                        status_resp, pnl_resp = await asyncio.gather(
                            client.get("http://127.0.0.1:3010/status"),
                            client.get("http://127.0.0.1:3010/pnl"),
                            return_exceptions=True,
                        )
                        poly = {"status": "online"}
                        if (
                            not isinstance(status_resp, Exception)
                            and status_resp.status_code == 200
                        ):
                            st = status_resp.json()
                            sniper = st.get("sniper", {})
                            poly.update(
                                {
                                    "running": bool(st.get("running")),
                                    "clob_ready": bool(st.get("clob_ready")),
                                    "snipe_window_active": bool(st.get("snipe_window")),
                                    "scans": sniper.get("scan_count", 0),
                                    "orders_placed": sniper.get("orders_placed", 0),
                                }
                            )
                        if (
                            not isinstance(pnl_resp, Exception)
                            and pnl_resp.status_code == 200
                        ):
                            data = pnl_resp.json()
                            positions = data.get("positions", [])
                            poly.update(
                                {
                                    "portfolio_value": data.get("portfolio_value", 0),
                                    "cash": data.get("cash", 0),
                                    "deployed": data.get("deployed", 0),
                                    "unrealized_pnl": data.get("unrealized_pnl", 0),
                                    "num_positions": len(positions),
                                    "positions": [
                                        {
                                            "title": p.get("title", "?")[:60],
                                            "shares": p.get("shares", 0),
                                            "entry_pct": round(p.get("entry", 0) * 100),
                                            "current_pct": round(
                                                (p.get("current") or 0) * 100
                                            ),
                                            "pnl": round(p.get("pnl", 0), 2),
                                            "pnl_pct": round(p.get("pnl_pct", 0), 1),
                                        }
                                        for p in positions[:10]
                                    ],
                                }
                            )
                        result["polymarket"] = poly
                    except Exception as e:
                        logger.warning(f"Polymarket status fetch: {e}")
                    try:
                        kalshi_resp = await client.get("http://127.0.0.1:3011/pnl")
                        if kalshi_resp.status_code == 200:
                            data = kalshi_resp.json()
                            positions = data.get("positions", [])
                            result["kalshi"] = {
                                "status": "online",
                                "portfolio_value": data.get("portfolio_value", 0),
                                "cash": data.get("cash", 0),
                                "deployed": data.get("deployed", 0),
                                "unrealized_pnl": data.get("unrealized_pnl", 0),
                                "num_positions": len(positions),
                                "positions": [
                                    {
                                        "ticker": p.get("ticker", "?"),
                                        "side": p.get("side", "?"),
                                        "count": p.get("count", 0),
                                        "value": round(p.get("value", 0), 2),
                                        "pnl": round(p.get("pnl", 0), 2),
                                    }
                                    for p in positions[:10]
                                ],
                            }
                    except Exception as e:
                        logger.warning(f"Kalshi status fetch: {e}")
                return json.dumps(result)
            except Exception as e:
                logger.error(f"Weather arb status failed: {e}")
                return json.dumps({"error": f"Weather bots unavailable: {str(e)}"})

        # === CLAUDE CODE / TERMINAL ===

        elif tool_name == "create_claude_task":
            title = tool_input.get("title", "")
            description = tool_input.get("description", "")
            priority = tool_input.get("priority", "normal")
            working_dir = tool_input.get(
                "working_directory",
                "/Users/shulmeister/mac-mini-apps/careassist-unified",
            )
            if not title or not description:
                return json.dumps({"error": "Missing title or description"})

            def _sync_create_task():
                conn = None
                cur = None
                try:
                    conn = _get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO claude_code_tasks (title, description, priority, status, requested_by, working_directory, created_at)
                        VALUES (%s, %s, %s, 'pending', %s, %s, NOW())
                        RETURNING id
                    """,
                        (title, description, priority, "gigi", working_dir),
                    )
                    task_id = cur.fetchone()[0]
                    conn.commit()
                    return json.dumps(
                        {
                            "success": True,
                            "task_id": task_id,
                            "message": f"Task #{task_id} created: {title}. Claude Code will pick it up shortly.",
                        }
                    )
                except Exception as e:
                    if conn:
                        conn.rollback()
                    return json.dumps({"error": f"Failed to create task: {str(e)}"})
                finally:
                    if cur:
                        cur.close()
                    _put_conn(conn)

            return await asyncio.to_thread(_sync_create_task)

        elif tool_name == "check_claude_task":
            task_id = tool_input.get("task_id")

            def _sync_check_task():
                conn = None
                cur = None
                try:
                    conn = _get_conn()
                    cur = conn.cursor()
                    if task_id:
                        cur.execute(
                            "SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks WHERE id = %s",
                            (int(task_id),),
                        )
                    else:
                        cur.execute(
                            "SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks ORDER BY id DESC LIMIT 1"
                        )
                    row = cur.fetchone()
                    if not row:
                        return json.dumps({"message": "No tasks found"})
                    result_preview = row[3][:500] if row[3] else None
                    return json.dumps(
                        {
                            "task_id": row[0],
                            "title": row[1],
                            "status": row[2],
                            "result_preview": result_preview,
                            "error": row[4],
                            "created_at": row[5].isoformat() if row[5] else None,
                            "completed_at": row[6].isoformat() if row[6] else None,
                        }
                    )
                except Exception as e:
                    if conn:
                        conn.rollback()
                    return json.dumps({"error": f"Failed to check task: {str(e)}"})
                finally:
                    if cur:
                        cur.close()
                    _put_conn(conn)

            return await asyncio.to_thread(_sync_check_task)

        elif tool_name == "run_claude_code":
            from gigi.claude_code_tools import run_claude_code

            result = await run_claude_code(
                prompt=tool_input.get("prompt", ""),
                directory=tool_input.get("directory"),
                model=tool_input.get("model"),
            )
            return json.dumps(result)

        elif tool_name == "browse_with_claude":
            from gigi.claude_code_tools import browse_with_claude

            result = await browse_with_claude(
                task=tool_input.get("task", ""),
                url=tool_input.get("url"),
            )
            return json.dumps(result)

        elif tool_name == "run_terminal":
            from gigi.terminal_tools import run_terminal

            result = await run_terminal(
                command=tool_input.get("command", ""),
                timeout=min(tool_input.get("timeout", 30), 120),
            )
            return json.dumps(result)

        # === MEMORY ===

        elif tool_name == "save_memory":
            if not MEMORY_AVAILABLE or not _memory_system:
                return json.dumps({"error": "Memory system not available"})
            content = tool_input.get("content", "")
            category = tool_input.get("category", "general")
            importance = tool_input.get("importance", "medium")
            impact_map = {
                "high": ImpactLevel.HIGH,
                "medium": ImpactLevel.MEDIUM,
                "low": ImpactLevel.LOW,
            }
            memory_id = _memory_system.create_memory(
                content=content,
                memory_type=MemoryType.EXPLICIT_INSTRUCTION,
                source=MemorySource.EXPLICIT,
                confidence=1.0,
                category=category,
                impact_level=impact_map.get(importance, ImpactLevel.MEDIUM),
            )
            return json.dumps(
                {"saved": True, "memory_id": memory_id, "content": content}
            )

        elif tool_name == "recall_memories":
            if not MEMORY_AVAILABLE or not _memory_system:
                return json.dumps(
                    {"memories": [], "message": "Memory system not available"}
                )
            category = tool_input.get("category")
            search_text = tool_input.get("search_text")
            memories = _memory_system.query_memories(
                category=category, min_confidence=0.3, limit=10
            )
            if search_text:
                search_lower = search_text.lower()
                memories = [m for m in memories if search_lower in m.content.lower()]
            results = [
                {
                    "id": m.id,
                    "content": m.content,
                    "category": m.category,
                    "confidence": float(m.confidence),
                    "type": m.type.value,
                }
                for m in memories
            ]
            return json.dumps({"memories": results, "count": len(results)})

        elif tool_name == "forget_memory":
            if not MEMORY_AVAILABLE or not _memory_system:
                return json.dumps({"error": "Memory system not available"})
            memory_id = tool_input.get("memory_id", "")
            memory = _memory_system.get_memory(memory_id)
            if not memory:
                return json.dumps({"error": f"Memory {memory_id} not found"})
            with _memory_system._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE gigi_memories SET status = 'archived' WHERE id = %s",
                        (memory_id,),
                    )
                    _memory_system._log_event(
                        cur,
                        memory_id,
                        "archived",
                        memory.confidence,
                        memory.confidence,
                        "User requested forget",
                    )
                conn.commit()
            return json.dumps(
                {"archived": True, "memory_id": memory_id, "content": memory.content}
            )

        elif tool_name == "search_memory_logs":
            from gigi.memory_logger import MemoryLogger

            ml = MemoryLogger()
            query = tool_input.get("query", "")
            days_back = tool_input.get("days_back", 30)
            results = await asyncio.to_thread(
                ml.search_logs, query, days_back=days_back
            )
            return json.dumps(
                {"query": query, "results": results[:10], "total": len(results)}
            )

        # === AR / FINANCE ===

        elif tool_name == "get_ar_report":
            from sales.quickbooks_service import QuickBooksService

            qb = QuickBooksService()
            loaded = await asyncio.to_thread(qb.load_tokens_from_db)
            if not loaded:
                return json.dumps(
                    {
                        "error": "QuickBooks not connected. Visit https://portal.coloradocareassist.com/auth/quickbooks to authorize."
                    }
                )
            detail_level = tool_input.get("detail_level", "summary")
            result = await asyncio.to_thread(qb.generate_ar_report, detail_level)
            if result.get("success"):
                return result["report"]
            return json.dumps(result)

        # === MARKETING ===

        elif tool_name == "get_marketing_dashboard":
            from gigi.marketing_tools import get_marketing_dashboard

            result = await asyncio.to_thread(
                get_marketing_dashboard, tool_input.get("date_range", "7d")
            )
            return json.dumps(result)

        elif tool_name == "get_google_ads_report":
            from gigi.marketing_tools import get_google_ads_report

            result = await asyncio.to_thread(
                get_google_ads_report, tool_input.get("date_range", "30d")
            )
            return json.dumps(result)

        elif tool_name == "get_website_analytics":
            from gigi.marketing_tools import get_website_analytics

            result = await asyncio.to_thread(
                get_website_analytics, tool_input.get("date_range", "7d")
            )
            return json.dumps(result)

        elif tool_name == "get_social_media_report":
            from gigi.marketing_tools import get_social_media_report

            result = await asyncio.to_thread(
                get_social_media_report,
                tool_input.get("date_range", "7d"),
                tool_input.get("platform", ""),
            )
            return json.dumps(result)

        elif tool_name == "get_gbp_report":
            from gigi.marketing_tools import get_gbp_report

            result = await asyncio.to_thread(
                get_gbp_report, tool_input.get("date_range", "30d")
            )
            return json.dumps(result)

        elif tool_name == "get_email_campaign_report":
            from gigi.marketing_tools import get_email_campaign_report

            result = await asyncio.to_thread(
                get_email_campaign_report, tool_input.get("date_range", "30d")
            )
            return json.dumps(result)

        elif tool_name == "generate_social_content":
            from gigi.marketing_tools import generate_social_content

            result = await asyncio.to_thread(
                generate_social_content,
                tool_input.get("prompt", ""),
                tool_input.get("media_type", "single_image"),
            )
            return json.dumps(result)

        # === FINANCE ===

        elif tool_name == "get_pnl_report":
            from gigi.finance_tools import get_pnl_report

            result = await asyncio.to_thread(
                get_pnl_report, tool_input.get("period", "ThisMonth")
            )
            return json.dumps(result)

        elif tool_name == "get_balance_sheet":
            from gigi.finance_tools import get_balance_sheet

            result = await asyncio.to_thread(
                get_balance_sheet, tool_input.get("as_of_date", "")
            )
            return json.dumps(result)

        elif tool_name == "get_invoice_list":
            from gigi.finance_tools import get_invoice_list

            result = await asyncio.to_thread(
                get_invoice_list, tool_input.get("status", "Open")
            )
            return json.dumps(result)

        elif tool_name == "get_cash_position":
            from gigi.finance_tools import get_cash_position

            result = await asyncio.to_thread(get_cash_position)
            return json.dumps(result)

        elif tool_name == "get_financial_dashboard":
            from gigi.finance_tools import get_financial_dashboard

            result = await asyncio.to_thread(get_financial_dashboard)
            return json.dumps(result)

        elif tool_name == "get_subscription_audit":
            from gigi.finance_tools import get_subscription_audit

            result = await asyncio.to_thread(
                get_subscription_audit, tool_input.get("months_back", 6)
            )
            return json.dumps(result)

        # === THINKING ===

        elif tool_name == "sequential_thinking":
            from gigi.sequential_thinking import sequential_thinking

            result = await sequential_thinking(
                thought=tool_input.get("thought", ""),
                thought_number=tool_input.get("thought_number", 1),
                total_thoughts=tool_input.get("total_thoughts", 1),
                next_thought_needed=tool_input.get("next_thought_needed", False),
                is_revision=tool_input.get("is_revision", False),
                revises_thought=tool_input.get("revises_thought"),
                branch_from_thought=tool_input.get("branch_from_thought"),
                branch_id=tool_input.get("branch_id"),
            )
            return json.dumps(result)

        elif tool_name == "get_thinking_summary":
            from gigi.sequential_thinking import get_thinking_summary

            result = await get_thinking_summary()
            return json.dumps(result)

        # === KNOWLEDGE GRAPH ===

        elif tool_name == "update_knowledge_graph":
            from gigi.knowledge_graph import update_knowledge_graph

            result = await update_knowledge_graph(
                action=tool_input.get("action", ""),
                entities=tool_input.get("entities"),
                relations=tool_input.get("relations"),
                observations=tool_input.get("observations"),
                entity_names=tool_input.get("entity_names"),
                deletions=tool_input.get("deletions"),
            )
            return json.dumps(result)

        elif tool_name == "query_knowledge_graph":
            from gigi.knowledge_graph import query_knowledge_graph

            result = await query_knowledge_graph(
                action=tool_input.get("action", ""),
                query=tool_input.get("query"),
                names=tool_input.get("names"),
            )
            return json.dumps(result)

        # === GOOGLE MAPS ===

        elif tool_name == "get_directions":
            from gigi.maps_tools import get_directions

            result = await get_directions(
                origin=tool_input.get("origin", ""),
                destination=tool_input.get("destination", ""),
                mode=tool_input.get("mode", "driving"),
            )
            return json.dumps(result)

        elif tool_name == "geocode_address":
            from gigi.maps_tools import geocode_address

            result = await geocode_address(address=tool_input.get("address", ""))
            return json.dumps(result)

        elif tool_name == "search_nearby_places":
            from gigi.maps_tools import search_nearby_places

            result = await search_nearby_places(
                location=tool_input.get("location", ""),
                place_type=tool_input.get("place_type", ""),
                radius_miles=int(tool_input.get("radius_miles", 5)),
            )
            return json.dumps(result)

        # === GOOGLE WORKSPACE ADMIN ===

        elif tool_name == "query_workspace":
            from gigi.gam_tools import query_workspace

            result = await query_workspace(command=tool_input.get("command", ""))
            return json.dumps(result)

        # === FAX ===

        elif tool_name == "send_fax":
            from services.fax_service import send_fax as _send_fax

            result = await _send_fax(
                to=tool_input.get("to", ""), media_url=tool_input.get("media_url", "")
            )
            return json.dumps(result)

        elif tool_name == "list_faxes":
            from services.fax_service import list_faxes as _list_faxes

            result = _list_faxes(
                direction=tool_input.get("direction"), limit=tool_input.get("limit", 10)
            )
            return json.dumps(result)

        elif tool_name == "read_fax":
            from services.fax_service import read_fax as _read_fax

            result = await _read_fax(fax_id=int(tool_input.get("fax_id", 0)))
            return json.dumps(result)

        elif tool_name == "file_fax_referral":
            from services.fax_service import file_fax_referral as _file_fax

            result = await _file_fax(fax_id=int(tool_input.get("fax_id", 0)))
            return json.dumps(result)

        # === TASK MANAGEMENT ===

        elif tool_name == "get_task_board":

            def _read_task_board():
                try:
                    path = os.path.expanduser("~/Task Board.md")
                    with open(path, "r") as f:
                        return {"task_board": f.read()}
                except FileNotFoundError:
                    return {"task_board": "(empty)", "note": "No task board file found"}

            return json.dumps(await asyncio.to_thread(_read_task_board))

        elif tool_name == "add_task":
            task_text = tool_input.get("task", "").strip()
            section = tool_input.get("section", "Today").strip()
            if not task_text:
                return json.dumps({"error": "No task text provided"})
            valid_sections = [
                "Today",
                "Soon",
                "Later",
                "Waiting",
                "Agenda",
                "Inbox",
                "Reference",
            ]
            section_match = next(
                (s for s in valid_sections if s.lower() == section.lower()), "Today"
            )

            def _add_task():
                try:
                    path = os.path.expanduser("~/Task Board.md")
                    with open(path, "r") as f:
                        content = f.read()
                    marker = f"## {section_match}\n"
                    if marker in content:
                        idx = content.index(marker) + len(marker)
                        rest = content[idx:]
                        if rest.startswith("-\n") or rest.startswith("- \n"):
                            content_new = (
                                content[:idx]
                                + f"- [ ] {task_text}\n"
                                + rest[rest.index("\n") + 1 :]
                            )
                        else:
                            content_new = content[:idx] + f"- [ ] {task_text}\n" + rest
                    else:
                        content_new = (
                            content + f"\n## {section_match}\n- [ ] {task_text}\n"
                        )
                    with open(path, "w") as f:
                        f.write(content_new)
                    return {
                        "success": True,
                        "task": task_text,
                        "section": section_match,
                    }
                except Exception as e:
                    return {"error": f"Failed to add task: {str(e)}"}

            return json.dumps(await asyncio.to_thread(_add_task))

        elif tool_name == "complete_task":
            task_text = tool_input.get("task_text", "").strip().lower()
            if not task_text:
                return json.dumps({"error": "No task text provided"})

            def _complete_task():
                try:
                    path = os.path.expanduser("~/Task Board.md")
                    with open(path, "r") as f:
                        lines = f.readlines()
                    completed = False
                    completed_task = ""
                    new_lines = []
                    for line in lines:
                        if (
                            not completed
                            and "- [ ]" in line
                            and task_text in line.lower()
                        ):
                            completed_task = line.replace("- [ ]", "- [x]").strip()
                            completed = True
                        else:
                            new_lines.append(line)
                    if not completed:
                        return {
                            "error": f"No uncompleted task matching '{task_text}' found"
                        }
                    content = "".join(new_lines)
                    done_marker = "## Done\n"
                    if done_marker in content:
                        idx = content.index(done_marker) + len(done_marker)
                        rest = content[idx:]
                        if rest.startswith("-\n") or rest.startswith("- \n"):
                            content = (
                                content[:idx]
                                + completed_task
                                + "\n"
                                + rest[rest.index("\n") + 1 :]
                            )
                        else:
                            content = content[:idx] + completed_task + "\n" + rest
                    else:
                        content += f"\n## Done\n{completed_task}\n"
                    with open(path, "w") as f:
                        f.write(content)
                    return {"success": True, "completed": completed_task}
                except Exception as e:
                    return {"error": f"Failed to complete task: {str(e)}"}

            return json.dumps(await asyncio.to_thread(_complete_task))

        elif tool_name == "capture_note":
            note = tool_input.get("note", "").strip()
            if not note:
                return json.dumps({"error": "No note provided"})

            def _capture_note():
                try:
                    path = os.path.expanduser("~/Scratchpad.md")
                    try:
                        with open(path, "r") as f:
                            content = f.read()
                    except FileNotFoundError:
                        content = "# Scratchpad\n\n---\n"
                    from datetime import datetime as dt

                    timestamp = dt.now().strftime("%I:%M %p")
                    content = content.rstrip() + f"\n- {note} ({timestamp})\n"
                    with open(path, "w") as f:
                        f.write(content)
                    return {"success": True, "note": note, "captured_at": timestamp}
                except Exception as e:
                    return {"error": f"Failed to capture note: {str(e)}"}

            return json.dumps(await asyncio.to_thread(_capture_note))

        elif tool_name == "get_daily_notes":
            target_date = tool_input.get("date", "")

            def _read_daily_notes():
                try:
                    import glob as g
                    import re as _re
                    from datetime import datetime as dt

                    if target_date:
                        d = (
                            target_date
                            if _re.match(r"^\d{4}-\d{2}-\d{2}$", target_date)
                            else dt.now().strftime("%Y-%m-%d")
                        )
                    else:
                        d = dt.now().strftime("%Y-%m-%d")
                    notes_dir = os.path.expanduser("~/Daily Notes")
                    matches = g.glob(os.path.join(notes_dir, f"{d}*"))
                    if matches:
                        with open(matches[0], "r") as f:
                            return {"date": d, "notes": f.read()}
                    return {"date": d, "notes": "(no daily notes for this date)"}
                except Exception as e:
                    return {"error": f"Failed to read daily notes: {str(e)}"}

            return json.dumps(await asyncio.to_thread(_read_daily_notes))

        # === TICKET WATCHES ===

        elif tool_name == "watch_tickets":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.watch_tickets(
                artist=tool_input.get("artist", ""),
                venue=tool_input.get("venue"),
                city=tool_input.get("city", "Denver"),
            )
            return json.dumps(result)

        elif tool_name == "list_ticket_watches":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.list_ticket_watches()
            return json.dumps(result)

        elif tool_name == "remove_ticket_watch":
            if not cos_tools:
                return json.dumps({"error": "Chief of Staff tools not available."})
            result = await cos_tools.remove_ticket_watch(
                watch_id=tool_input.get("watch_id")
            )
            return json.dumps(result)

        # === TRAVEL ===

        elif tool_name == "search_flights":
            from gigi.travel_tools import search_flights

            result = await search_flights(
                origin=tool_input.get("origin", ""),
                destination=tool_input.get("destination", ""),
                departure_date=tool_input.get("departure_date", ""),
                return_date=tool_input.get("return_date"),
                adults=tool_input.get("adults", 1),
                max_stops=tool_input.get("max_stops", 1),
                travel_class=tool_input.get("travel_class"),
            )
            return json.dumps(result)

        elif tool_name == "search_hotels":
            from gigi.travel_tools import search_hotels

            result = await search_hotels(
                city=tool_input.get("city", ""),
                checkin=tool_input.get("checkin", ""),
                checkout=tool_input.get("checkout", ""),
                guests=tool_input.get("guests", 2),
                max_price=tool_input.get("max_price"),
            )
            return json.dumps(result)

        elif tool_name == "search_car_rentals":
            from gigi.travel_tools import search_car_rentals

            result = await search_car_rentals(
                pickup_location=tool_input.get("pickup_location", ""),
                pickup_date=tool_input.get("pickup_date", ""),
                dropoff_date=tool_input.get("dropoff_date", ""),
                dropoff_location=tool_input.get("dropoff_location"),
                car_class=tool_input.get("car_class"),
            )
            return json.dumps(result)

        elif tool_name == "search_transfers":
            from gigi.travel_tools import search_transfers

            result = await search_transfers(
                start_location=tool_input.get("start_location", ""),
                end_location=tool_input.get("end_location"),
                start_date_time=tool_input.get("start_date_time", ""),
                passengers=tool_input.get("passengers", 1),
                transfer_type=tool_input.get("transfer_type", "PRIVATE"),
                end_address=tool_input.get("end_address"),
                end_city=tool_input.get("end_city"),
                end_country=tool_input.get("end_country"),
            )
            return json.dumps(result)

        elif tool_name == "get_flight_status":
            from gigi.travel_tools import get_flight_status

            result = await get_flight_status(
                carrier_code=tool_input.get("carrier_code", ""),
                flight_number=tool_input.get("flight_number", ""),
                departure_date=tool_input.get("departure_date", ""),
                predict_delay=tool_input.get("predict_delay", True),
            )
            return json.dumps(result)

        elif tool_name == "explore_flights":
            from gigi.travel_tools import explore_flights

            result = await explore_flights(
                origin=tool_input.get("origin", ""),
                destination=tool_input.get("destination"),
                departure_date=tool_input.get("departure_date"),
                currency=tool_input.get("currency", "USD"),
            )
            return json.dumps(result)

        elif tool_name == "confirm_flight_price":
            from gigi.travel_tools import confirm_flight_price

            result = await confirm_flight_price(
                flight_offer=tool_input.get("flight_offer", {}),
                include_bags=tool_input.get("include_bags", False),
                include_branded_fares=tool_input.get("include_branded_fares", False),
            )
            return json.dumps(result)

        elif tool_name == "get_seatmap":
            from gigi.travel_tools import get_seatmap

            result = await get_seatmap(
                flight_offer=tool_input.get("flight_offer"),
                flight_order_id=tool_input.get("flight_order_id"),
            )
            return json.dumps(result)

        elif tool_name == "search_flight_availability":
            from gigi.travel_tools import search_flight_availability

            result = await search_flight_availability(
                origin=tool_input.get("origin", ""),
                destination=tool_input.get("destination", ""),
                departure_date=tool_input.get("departure_date", ""),
                adults=tool_input.get("adults", 1),
                travel_class=tool_input.get("travel_class"),
            )
            return json.dumps(result)

        elif tool_name == "book_flight":
            from gigi.travel_tools import book_flight

            result = await book_flight(
                flight_offer=tool_input.get("flight_offer", {}),
                travelers=tool_input.get("travelers", []),
            )
            return json.dumps(result)

        elif tool_name == "manage_flight_booking":
            from gigi.travel_tools import manage_flight_booking

            result = await manage_flight_booking(
                order_id=tool_input.get("order_id", ""),
                action=tool_input.get("action", "get"),
            )
            return json.dumps(result)

        elif tool_name == "get_airport_info":
            from gigi.travel_tools import get_airport_info

            result = await get_airport_info(
                action=tool_input.get("action", "search"),
                query=tool_input.get("query"),
                airport_code=tool_input.get("airport_code"),
                latitude=tool_input.get("latitude"),
                longitude=tool_input.get("longitude"),
                date=tool_input.get("date"),
            )
            return json.dumps(result)

        elif tool_name == "get_airline_info":
            from gigi.travel_tools import get_airline_info

            result = await get_airline_info(
                action=tool_input.get("action", "lookup"),
                airline_code=tool_input.get("airline_code", ""),
            )
            return json.dumps(result)

        elif tool_name == "get_hotel_ratings":
            from gigi.travel_tools import get_hotel_ratings

            result = await get_hotel_ratings(hotel_ids=tool_input.get("hotel_ids", ""))
            return json.dumps(result)

        elif tool_name == "book_hotel":
            from gigi.travel_tools import book_hotel

            result = await book_hotel(
                offer_id=tool_input.get("offer_id", ""),
                guests=tool_input.get("guests", []),
                payment=tool_input.get("payment", {}),
            )
            return json.dumps(result)

        elif tool_name == "book_transfer":
            from gigi.travel_tools import book_transfer

            result = await book_transfer(
                offer_id=tool_input.get("offer_id", ""),
                passengers=tool_input.get("passengers", []),
                payment=tool_input.get("payment"),
            )
            return json.dumps(result)

        elif tool_name == "manage_transfer":
            from gigi.travel_tools import manage_transfer

            result = await manage_transfer(
                order_id=tool_input.get("order_id", ""),
                confirm_number=tool_input.get("confirm_number", ""),
            )
            return json.dumps(result)

        elif tool_name == "search_activities":
            from gigi.travel_tools import search_activities

            result = await search_activities(
                city=tool_input.get("city"),
                latitude=tool_input.get("latitude"),
                longitude=tool_input.get("longitude"),
                radius=tool_input.get("radius"),
            )
            return json.dumps(result)

        elif tool_name == "get_travel_insights":
            from gigi.travel_tools import get_travel_insights

            result = await get_travel_insights(
                action=tool_input.get("action", ""),
                origin=tool_input.get("origin"),
                city=tool_input.get("city"),
                period=tool_input.get("period"),
                destination=tool_input.get("destination"),
                departure_date=tool_input.get("departure_date"),
                return_date=tool_input.get("return_date"),
                country_code=tool_input.get("country_code", "US"),
            )
            return json.dumps(result)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        if FAILURE_HANDLER_AVAILABLE and _failure_handler:
            try:
                _failure_handler.handle_tool_failure(
                    tool_name, e, {"tool_input": str(tool_input)[:200]}
                )
            except Exception:
                pass
        return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})
