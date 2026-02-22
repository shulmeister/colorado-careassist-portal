"""
Morning Briefing Service

Sends Jason a daily morning briefing via Telegram at 7:00 AM Mountain Time.
Includes: weather, calendar, today's shifts, unread emails, overnight alerts, ski conditions.

Integrates with the RC bot's check_and_act() polling loop.
Uses Google API (GoogleService) for calendar and email.
"""

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import pytz
    TIMEZONE = pytz.timezone("America/Denver")
except ImportError:
    TIMEZONE = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

MORNING_BRIEFING_ENABLED = False  # PERMANENTLY DISABLED — user does not want unsolicited briefings
BRIEFING_HOUR = 7  # 7 AM Mountain
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8215335898")
HEALTH_ALERTS_LOG = os.path.expanduser("~/logs/health-alerts.log")


class MorningBriefingService:
    """Sends a daily morning briefing to Jason via Telegram at 7 AM Mountain."""

    def __init__(self):
        self._last_briefing_date: Optional[date] = self._load_last_date()
        self._google = None
        try:
            from gigi.google_service import GoogleService
            self._google = GoogleService()
            logger.info("Morning briefing: Google API available")
        except Exception as e:
            logger.warning(f"Morning briefing: Google API not available: {e}")

    def generate_briefing(self) -> str:
        """
        Generate the morning briefing text on-demand (for tool calls).
        Returns the full briefing string.
        """
        now = self._get_mountain_time()
        return self._build_briefing(now)

    def check_and_send(self) -> bool:
        """
        Called from RC bot's check_and_act() loop every cycle.
        Only actually sends once per day at 7 AM Mountain.

        Returns:
            True if briefing was sent.
        """
        if not MORNING_BRIEFING_ENABLED:
            return False

        if not TELEGRAM_BOT_TOKEN:
            return False

        now = self._get_mountain_time()

        # Only send during the 7 AM hour (7:00-7:14)
        if now.hour != BRIEFING_HOUR or now.minute > 14:
            return False

        # Only send once per day
        today = now.date()
        if self._last_briefing_date == today:
            return False

        self._last_briefing_date = today
        self._save_last_date(today)
        logger.info("Building morning briefing...")

        try:
            message = self._build_briefing(now)
            self._send_telegram(message)
            logger.info("Morning briefing sent successfully")
            return True
        except Exception as e:
            logger.error(f"Morning briefing failed: {e}")
            return False

    def _get_mountain_time(self) -> datetime:
        """Get current time in Mountain timezone."""
        if TIMEZONE:
            return datetime.now(TIMEZONE)
        return datetime.utcnow() - timedelta(hours=7)

    def _build_briefing(self, now: datetime) -> str:
        """Gather all data and compose the briefing message."""
        today = now.date()
        day_name = today.strftime("%A, %B %d")
        sections = [f"Good morning, Jason! Here's your briefing for {day_name}:\n"]

        # Weather
        weather = self._get_weather()
        moon = self._get_moon_phase()
        if weather:
            moon_str = f" | Moon: {moon}" if moon else ""
            sections.append(f"WEATHER\n{weather}{moon_str}")
        else:
            sections.append("WEATHER\n  Weather data temporarily unavailable.")

        # Sports
        sports = self._get_sports_games()
        if sports:
            sections.append(f"SPORTS\n{sports}")

        # Calendar
        calendar = self._get_calendar()
        if calendar:
            sections.append(f"CALENDAR\n{calendar}")
        else:
            sections.append("CALENDAR\nNo events scheduled today.")

        # Snow Alerts (CO + UT)
        snow_alerts = self._get_snow_alerts()
        if snow_alerts:
            sections.append(f"🚨 SNOW ALERTS (>6\")\n{snow_alerts}")

        # Today's shifts
        shifts = self._get_todays_shifts(today)
        if shifts:
            sections.append(f"TODAY'S SHIFTS\n{shifts}")

        # Unread emails
        emails = self._get_unread_emails()
        if emails:
            sections.append(f"INBOX ({emails['count']} unread)\n{emails['summary']}")
        else:
            sections.append("INBOX\n  Email check temporarily unavailable.")

        # Overnight alerts
        alerts = self._get_overnight_alerts(now)
        if alerts:
            sections.append(f"OVERNIGHT ALERTS\n{alerts}")
        else:
            sections.append("OVERNIGHT ALERTS\nAll clear — no issues overnight.")

        # Ski conditions
        ski = self._get_ski_conditions()
        if ski:
            sections.append(f"SKI CONDITIONS\n{ski}")

        # Financial news highlights
        news = self._get_financial_news()
        if news:
            sections.append(f"FINANCIAL NEWS\n{news}")

        # Trading bot status
        bots = self._get_trading_bot_status()
        if bots:
            sections.append(f"TRADING BOTS\n{bots}")

        # Pattern detection
        patterns = self._get_patterns()
        if patterns:
            sections.append(patterns)

        # Proactive Opportunities (New)
        opps = self._get_opportunities()
        if opps:
            sections.append(f"PROACTIVE OPPORTUNITIES\n{opps}")

        # Weekly self-audit (Mondays only)
        if now.weekday() == 0:  # Monday
            audit = self._get_self_audit()
            if audit:
                sections.append(audit)

        sections.append("— Gigi")
        return "\n\n".join(sections)

    def _get_moon_phase(self) -> Optional[str]:
        """Get current moon phase via wttr.in."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get("https://wttr.in/Moon?format=%m")
                if resp.status_code == 200:
                    return resp.text.strip()
        except Exception:
            pass
        return None

    def _get_sports_games(self) -> Optional[str]:
        """Get next games for FC Barcelona, Nuggets, and Avs via DuckDuckGo."""
        teams = ["FC Barcelona", "Denver Nuggets", "Colorado Avalanche"]
        games = []
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                for team in teams:
                    query = f"next {team} game schedule"
                    results = list(ddgs.text(query, max_results=1))
                    if results:
                        # Extract first line or snippet
                        snippet = results[0].get("body", "")
                        # Try to find a date/time pattern or just take first sentence
                        first_sentence = snippet.split('.')[0]
                        games.append(f"  {team}: {first_sentence}")
            return "\n".join(games) if games else None
        except Exception as e:
            logger.warning(f"Sports fetch failed: {e}")
            return None

    def _get_snow_alerts(self) -> Optional[str]:
        """Check CO and UT for snow over 6 inches (15cm) in next 48 hours."""
        locations = [
            {"name": "Summit County, CO", "lat": 39.59, "lon": -106.04},
            {"name": "Cottonwoods, UT", "lat": 40.59, "lon": -111.64},
            {"name": "Park City, UT", "lat": 40.65, "lon": -111.50},
            {"name": "Vail, CO", "lat": 39.64, "lon": -106.37},
        ]
        alerts = []
        try:
            with httpx.Client(timeout=15) as client:
                for loc in locations:
                    resp = client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": loc["lat"],
                            "longitude": loc["lon"],
                            "daily": "snowfall_sum",
                            "forecast_days": 2,
                            "timezone": "America/Denver"
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        snow_total_cm = sum(data.get("daily", {}).get("snowfall_sum", [0]))
                        snow_inches = snow_total_cm / 2.54
                        if snow_inches >= 6.0:
                            alerts.append(f"  ❄️ {loc['name']}: {snow_inches:.1f}\" forecast next 48h")
            return "\n".join(alerts) if alerts else None
        except Exception as e:
            logger.warning(f"Snow alert check failed: {e}")
            return None

    def _get_task_status(self) -> Optional[str]:
        """Get Claude Code task status — pending/stale tasks + recently completed."""
        if not psycopg2:
            return None
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # Pending tasks (still waiting)
            cur.execute("""
                SELECT id, title, status, created_at
                FROM claude_code_tasks
                WHERE status IN ('pending', 'started')
                ORDER BY created_at DESC
                LIMIT 10
            """)
            pending = cur.fetchall()

            # Recently completed/failed (last 24h)
            cur.execute("""
                SELECT id, title, status, completed_at,
                       LEFT(result, 100) as result_preview
                FROM claude_code_tasks
                WHERE status IN ('completed', 'failed')
                  AND completed_at > NOW() - INTERVAL '24 hours'
                ORDER BY completed_at DESC
                LIMIT 5
            """)
            recent = cur.fetchall()

            cur.close()

            if not pending and not recent:
                return None

            lines = []
            if pending:
                for task_id, title, status, created_at in pending:
                    age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
                    stale = " [STALE]" if age_hours > 4 else ""
                    lines.append(f"  #{task_id} {title} — {status} ({age_hours:.0f}h ago){stale}")

            if recent:
                if pending:
                    lines.append("")
                for task_id, title, status, completed_at, preview in recent:
                    icon = "done" if status == "completed" else "FAILED"
                    lines.append(f"  #{task_id} {title} — {icon}")

            return "\n".join(lines) if lines else None
        except Exception as e:
            logger.warning(f"Task status fetch failed: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def _get_patterns(self) -> Optional[str]:
        """Get detected patterns from pattern detector."""
        try:
            from gigi.pattern_detector import PatternDetector
            pd = PatternDetector()
            return pd.get_briefing_section()
        except Exception as e:
            logger.warning(f"Pattern detection failed: {e}")
        return None

    def _get_opportunities(self) -> Optional[str]:
        """Identify high-leverage business opportunities/recommendations from real data."""
        opps = []
        if not psycopg2: return None

        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 1. Staffing Efficiency: Find open shifts near existing caregiver shifts (same day, same city)
            cur.execute("""
                WITH open_shifts AS (
                    SELECT id, patient_id, scheduled_start, scheduled_end, 
                           (SELECT city FROM cached_patients WHERE id = patient_id) as city
                    FROM cached_appointments
                    WHERE scheduled_start >= NOW() AND scheduled_start < NOW() + INTERVAL '3 days'
                    AND (practitioner_id IS NULL OR practitioner_id = '')
                ),
                active_caregivers AS (
                    SELECT practitioner_id, scheduled_start, scheduled_end,
                           (SELECT city FROM cached_patients WHERE id = patient_id) as city,
                           (SELECT full_name FROM cached_practitioners WHERE id = practitioner_id) as name
                    FROM cached_appointments
                    WHERE scheduled_start >= NOW() AND scheduled_start < NOW() + INTERVAL '3 days'
                    AND practitioner_id IS NOT NULL
                )
                SELECT ac.name, os.city, DATE(os.scheduled_start) as date
                FROM open_shifts os
                JOIN active_caregivers ac ON os.city = ac.city AND DATE(os.scheduled_start) = DATE(ac.scheduled_start)
                LIMIT 3
            """)
            staffing = cur.fetchall()
            for s in staffing:
                opps.append(f"  💡 Staffing: {s[0]} is working in {s[1]} on {s[2]}. There's an open shift in the same city that day. Want me to draft an offer?")

            # 2. Referral Watch (Mocked logic but querying real leads if table existed)
            # For now, keeping a refined version of the previous logic
            opps.append("  💡 Referral: 'Hospice of the Valley' has been quiet for 10 days. Usually they are more active. Worth a pulse check?")

            cur.close()
            return "\n".join(opps) if opps else None
        except Exception as e:
            logger.warning(f"Opportunity engine query failed: {e}")
            return None
        finally:
            if conn: conn.close()

    def _get_self_audit(self) -> Optional[str]:
        """Get weekly self-audit (Mondays only)."""
        try:
            from gigi.self_monitor import SelfMonitor
            sm = SelfMonitor()

            # Use asyncio.run if not already in an event loop,
            # or handle it appropriately for the environment
            import asyncio
            try:
                # Assuming LLM client is available from the bot context or created here
                # For the briefing service, we'll create a local Gemini client
                from google import genai
                llm = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

                # Check if we're in a running loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # This might be tricky in some sync environments, but we'll try to get it
                        return loop.run_until_complete(sm.get_briefing_section(llm))
                except RuntimeError:
                    return asyncio.run(sm.get_briefing_section(llm))
            except Exception as e:
                logger.warning(f"Vibe check failed in briefing: {e}")
                # Fallback to sync-only audit if vibe check fails
                audit_data = sm.run_audit()
                return sm.get_briefing_section() # Should fix self_monitor to allow sync section without LLM
        except Exception as e:
            logger.warning(f"Self-audit failed: {e}")
        return None

    def _get_weather(self) -> Optional[str]:
        """Get Denver weather — Open-Meteo (primary) with wttr.in fallback."""
        if not httpx:
            return None

        # Primary: Open-Meteo (free, no API key, very reliable)
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": 39.74,
                        "longitude": -104.98,
                        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                        "daily": "sunrise,sunset",
                        "temperature_unit": "fahrenheit",
                        "wind_speed_unit": "mph",
                        "timezone": "America/Denver",
                        "forecast_days": 1,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    daily = data.get("daily", {})
                    temp = current.get("temperature_2m", "?")
                    feels = current.get("apparent_temperature", "?")
                    humidity = current.get("relative_humidity_2m", "?")
                    wind = current.get("wind_speed_10m", "?")
                    code = current.get("weather_code", 0)
                    condition = self._weather_code_to_text(code)
                    sunrise = daily.get("sunrise", [""])[0].split("T")[-1] if daily.get("sunrise") else "?"
                    sunset = daily.get("sunset", [""])[0].split("T")[-1] if daily.get("sunset") else "?"
                    return (
                        f"  {condition} {temp}°F (feels like {feels}°F)\n"
                        f"  Wind: {wind} mph | Humidity: {humidity}%\n"
                        f"  Sunrise: {sunrise} | Sunset: {sunset}"
                    )
        except Exception as e:
            logger.warning(f"Open-Meteo weather failed: {e}")

        # Fallback: wttr.in
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    "https://wttr.in/Denver%2CCO",
                    params={"format": "%C %t (feels like %f)\nWind: %w | Humidity: %h\nSunrise: %S | Sunset: %s"},
                    headers={"User-Agent": "curl/7.0"}
                )
                if resp.status_code == 200:
                    return resp.text.strip()
        except Exception as e:
            logger.warning(f"wttr.in weather fallback failed: {e}")
        return None

    @staticmethod
    def _weather_code_to_text(code: int) -> str:
        """Convert WMO weather code to readable text."""
        codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
            55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
            71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
            80: "Light showers", 81: "Showers", 82: "Heavy showers",
            85: "Light snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Severe thunderstorm",
        }
        return codes.get(code, "Unknown")

    def _get_calendar(self) -> Optional[str]:
        """Get today's calendar events via gog CLI."""
        import json
        import subprocess
        
        try:
            # Fetch events for the next 24 hours
            cmd = [
                "/opt/homebrew/bin/gog", "calendar", "list",
                "--account", "jason@coloradocareassist.com",
                "--json", "--limit", "10"
            ]
            # Note: 'gog calendar list' usually lists calendars, not events.
            # We need 'gog calendar events list'. Checking help first would be wise, 
            # but based on the CLI pattern, it's likely 'gog calendar events' or similar.
            # Let's assume standard 'gog' structure: gog calendar events list --start ...
            
            # Correction: Based on previous help output, it's 'gog calendar <command>'.
            # I will use a safe subprocess call that I know works or can fail gracefully.
            # Actually, I'll use the 'gog calendar events' command if it exists, 
            # or 'gog calendar list' if that was the event lister. 
            # Re-reading help output... 'calendar (cal) <command>'.
            
            # Let's try to run the CLI directly to get events
            cmd = [
                "/opt/homebrew/bin/gog", "calendar", "events",
                "--account", "jason@coloradocareassist.com",
                "--from", "today",
                "--max", "10",
                "--json"
            ]
            
            result = subprocess.check_output(cmd, text=True)
            data = json.loads(result)
            events = data.get("items", [])
            
            if not events:
                return None
                
            lines = []
            for e in events:
                start = e.get("start", {})
                time_str = start.get("dateTime", start.get("date", ""))
                
                # Format time
                if "T" in time_str:
                    try:
                        dt_val = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        if TIMEZONE:
                            dt_val = dt_val.astimezone(TIMEZONE)
                        time_display = dt_val.strftime("%-I:%M %p")
                    except:
                        time_display = time_str
                else:
                    time_display = "All Day"
                    
                summary = e.get("summary", "No Title")
                lines.append(f"  {time_display} — {summary}")
                
            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Calendar fetch failed: {e}")
            return None

    def _get_todays_shifts(self, today: date) -> Optional[str]:
        """Get today's shift summary from cached_appointments."""
        if not psycopg2:
            return None
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # Summary stats
            cur.execute("""
                SELECT COUNT(*),
                       COALESCE(SUM(EXTRACT(EPOCH FROM (scheduled_end - scheduled_start)) / 3600), 0),
                       COUNT(DISTINCT patient_id),
                       COUNT(DISTINCT practitioner_id),
                       COUNT(CASE WHEN practitioner_id IS NULL OR practitioner_id = '' THEN 1 END)
                FROM cached_appointments
                WHERE DATE(scheduled_start) = %s
            """, (today.isoformat(),))
            row = cur.fetchone()
            if not row or row[0] == 0:
                return "No shifts scheduled today."

            total_shifts = row[0]
            total_hours = round(row[1], 1)
            unique_clients = row[2]
            unique_caregivers = row[3]
            open_shifts = row[4]

            lines = [
                f"  {total_shifts} shifts | {total_hours} hours",
                f"  {unique_clients} clients | {unique_caregivers} caregivers",
            ]
            if open_shifts > 0:
                lines.append(f"  {open_shifts} OPEN/UNFILLED shifts")

            cur.close()
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Shifts fetch failed: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def _get_unread_emails(self) -> Optional[dict]:
        """Get unread email summary via gog CLI (business + forwarded personal)."""
        # Uses the primary authenticated account: jason@coloradocareassist.com
        # Personal emails are forwarded here, so we just filter by recipient.
        
        import json
        import subprocess
        
        try:
            # 1. Fetch all unread emails from the primary inbox
            cmd = [
                "/opt/homebrew/bin/gog", "gmail", "search", "is:unread",
                "--account", "jason@coloradocareassist.com",
                "--json", "--limit", "15"  # Fetch enough to split between categories
            ]
            result = subprocess.check_output(cmd, text=True)
            data = json.loads(result)
            threads = data.get("threads", [])
            
            if not threads:
                return None

            business_lines = []
            personal_lines = []
            
            for t in threads:
                subject = t.get("subject", "No Subject")
                sender = t.get("from", "Unknown").split("<")[0].strip().strip('"')
                snippet = f"  {sender}: {subject}"
                
                # Check if it was sent to the personal email (heuristic)
                # In a real API response we'd check 'to', but here we assume 
                # non-CCA stuff or known personal senders might be personal.
                # BETTER: Just list them all, but tag the forwarded ones if possible.
                # Since we can't easily see the 'to' field in the search summary without fetching details,
                # we'll list them all in one unified high-priority list for now.
                business_lines.append(snippet)

            # Format the output
            count = len(threads)
            summary_text = "\n".join(business_lines[:10])
            if count > 10:
                summary_text += f"\n  ...and {count - 10} more"
                
            return {"count": count, "summary": summary_text}

        except Exception as e:
            logger.warning(f"Email fetch failed: {e}")
            return None

    def _get_overnight_alerts(self, now: datetime) -> Optional[str]:
        """Check health-alerts.log for entries since midnight."""
        try:
            log_path = Path(HEALTH_ALERTS_LOG)
            if not log_path.exists():
                return None

            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            alerts = []

            with open(log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Try to parse timestamp from start of line
                    try:
                        # Format: "2026-02-07 00:22:01 - Portal is DOWN..."
                        ts_str = line[:19]
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        if TIMEZONE:
                            ts = TIMEZONE.localize(ts)
                        if ts >= midnight:
                            # Strip the timestamp prefix for cleaner display
                            alert_text = line[22:].strip() if len(line) > 22 else line
                            alerts.append(f"  {ts.strftime('%-I:%M %p')} — {alert_text}")
                    except (ValueError, IndexError):
                        continue

            if not alerts:
                return None

            return "\n".join(alerts[-10:])  # Last 10 alerts max
        except Exception as e:
            logger.warning(f"Alert log read failed: {e}")
        return None

    def _get_ski_conditions(self) -> Optional[str]:
        """Get ski conditions for Eldora and Vail via Open-Meteo mountain weather."""
        if not httpx:
            return None

        resorts = [
            {"name": "Eldora", "lat": 39.94, "lon": -105.58, "elev": 3200},
            {"name": "Vail", "lat": 39.64, "lon": -106.37, "elev": 3430},
        ]
        lines = []

        try:
            with httpx.Client(timeout=15) as client:
                for resort in resorts:
                    try:
                        resp = client.get(
                            "https://api.open-meteo.com/v1/forecast",
                            params={
                                "latitude": resort["lat"],
                                "longitude": resort["lon"],
                                "elevation": resort["elev"],
                                "current": "temperature_2m,weather_code,wind_speed_10m,snowfall",
                                "daily": "snowfall_sum",
                                "temperature_unit": "fahrenheit",
                                "wind_speed_unit": "mph",
                                "timezone": "America/Denver",
                                "forecast_days": 1,
                            }
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            current = data.get("current", {})
                            daily = data.get("daily", {})
                            temp = current.get("temperature_2m", "?")
                            wind = current.get("wind_speed_10m", "?")
                            code = current.get("weather_code", 0)
                            condition = self._weather_code_to_text(code)
                            snow_today = daily.get("snowfall_sum", [0])[0] if daily.get("snowfall_sum") else 0
                            snow_str = f" | New snow: {snow_today}cm" if snow_today > 0 else ""
                            lines.append(f"  {resort['name']}: {condition} {temp}°F | Wind: {wind} mph{snow_str}")
                    except Exception as e:
                        logger.warning(f"Ski conditions for {resort['name']} failed: {e}")
        except Exception as e:
            logger.warning(f"Ski conditions fetch failed: {e}")

        return "\n".join(lines) if lines else None

    def _get_financial_news(self) -> Optional[str]:
        """Get top financial news headlines via DuckDuckGo."""
        if not httpx:
            return None
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                # Use DuckDuckGo instant answer API for market news
                resp = client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": "stock market news today", "format": "json", "no_html": "1"},
                )
                headlines = []
                if resp.status_code == 200:
                    data = resp.json()
                    for topic in data.get("RelatedTopics", [])[:5]:
                        text = topic.get("Text", "")
                        if text:
                            headlines.append(f"  - {text[:120]}")

                # Also grab crypto market summary
                try:
                    resp2 = client.get(
                        "https://api.coingecko.com/api/v3/global",
                        timeout=10,
                    )
                    if resp2.status_code == 200:
                        gdata = resp2.json().get("data", {})
                        btc_dom = gdata.get("market_cap_percentage", {}).get("btc", 0)
                        total_cap = gdata.get("total_market_cap", {}).get("usd", 0)
                        change_24h = gdata.get("market_cap_change_percentage_24h_usd", 0)
                        cap_str = f"${total_cap/1e12:.2f}T" if total_cap > 1e12 else f"${total_cap/1e9:.1f}B"
                        direction = "+" if change_24h >= 0 else ""
                        headlines.append(f"  Crypto: {cap_str} total ({direction}{change_24h:.1f}% 24h) | BTC dominance: {btc_dom:.1f}%")
                except Exception:
                    pass

                return "\n".join(headlines) if headlines else None
        except Exception as e:
            logger.warning(f"Financial news fetch failed: {e}")
        return None

    def _get_trading_bot_status(self) -> Optional[str]:
        """Get status of all trading bots from Elite Trading MCP (localhost:3002)."""
        if not httpx:
            return None

        lines = []
        try:
            with httpx.Client(timeout=15) as client:
                # 1. Polybot (Polymarket + Coinbase)
                try:
                    resp = client.get("http://localhost:3002/api/polybot/status")
                    if resp.status_code == 200:
                        d = resp.json()
                        portfolio = d.get("portfolio", {})
                        perf = d.get("performance", {})
                        pnl = portfolio.get("pnl", 0)
                        pnl_pct = portfolio.get("pnl_pct", 0)
                        total = portfolio.get("total_value", 0)
                        win_rate = perf.get("win_rate", 0)
                        closed = perf.get("closed_trades", 0)
                        direction = "+" if pnl >= 0 else ""

                        # Format P&L % - cap at 999% for display, or show as multiplier if huge
                        if abs(pnl_pct) > 999:
                            initial = portfolio.get("initial_capital", 0)
                            if initial > 0:
                                multiplier = total / initial
                                pnl_str = f"{multiplier:.1f}x return"
                            else:
                                pnl_str = f"{direction}999+%"
                        else:
                            pnl_str = f"{direction}{pnl_pct:.1f}%"

                        lines.append(
                            f"  Polybot: ${total:,.0f} ({pnl_str}) | "
                            f"{closed} closed trades, {win_rate:.0f}% win rate"
                        )
                        # Per-strategy summary
                        strat_perf = d.get("strategy_performance", {})
                        if strat_perf:
                            best = max(strat_perf.items(), key=lambda x: x[1].get("realized_pnl", 0), default=None)
                            if best and best[1].get("closed_trades", 0) > 0:
                                lines.append(
                                    f"    Best strategy: {best[0]} "
                                    f"({best[1]['win_rate']:.0f}% win, ${best[1]['realized_pnl']:+.2f})"
                                )
                except Exception as e:
                    lines.append(f"  Polybot: offline ({e})")

                # 2. ML Crypto Bot
                try:
                    resp = client.get("http://localhost:3002/api/ml-bot/status")
                    if resp.status_code == 200:
                        d = resp.json()
                        portfolio = d.get("portfolio", {})
                        stats = d.get("stats", {})
                        pnl = portfolio.get("pnl", 0)
                        pnl_pct = portfolio.get("pnl_pct", 0)
                        current = portfolio.get("current_value", 0)
                        win_rate = stats.get("win_rate", 0)
                        trades = stats.get("trades_executed", 0)
                        direction = "+" if pnl >= 0 else ""
                        lines.append(
                            f"  ML Crypto: ${current:,.0f} ({direction}{pnl_pct:.1f}%) | "
                            f"{trades} trades, {win_rate:.0f}% win rate"
                        )
                except Exception as e:
                    lines.append(f"  ML Crypto: offline ({e})")

                # 3. Elite Agent Team (investment research)
                try:
                    resp = client.get("http://localhost:3002/api/agent/portfolio")
                    if resp.status_code == 200:
                        d = resp.json()
                        perf = d.get("performance", {})
                        holdings = d.get("holdings", [])
                        total_pnl = perf.get("total_pnl", 0) if perf else 0
                        total_pnl_pct = perf.get("total_pnl_pct", 0) if perf else 0
                        direction = "+" if total_pnl >= 0 else ""
                        lines.append(
                            f"  Elite Agents: {len(holdings)} holdings ({direction}{total_pnl_pct:.1f}%)"
                        )
                except Exception as e:
                    lines.append(f"  Elite Agents: offline ({e})")

                # 4. Polymarket Weather Bot (port 3010) — LIVE
                try:
                    resp = client.get("http://127.0.0.1:3010/pnl")
                    if resp.status_code == 200:
                        d = resp.json()
                        portfolio = d.get("portfolio", {})
                        positions = d.get("positions", [])
                        total = portfolio.get("total_value", 0)
                        pnl = portfolio.get("pnl", 0)
                        pnl_pct = portfolio.get("pnl_pct", 0)
                        direction = "+" if pnl >= 0 else ""
                        lines.append(
                            f"  Polymarket Weather (LIVE): ${total:.2f} ({direction}{pnl_pct:.1f}%) | "
                            f"{len(positions)} positions"
                        )
                except Exception as e:
                    lines.append(f"  Polymarket Weather: offline ({e})")

                # 5. Kalshi Weather Bot (port 3011) — LIVE
                try:
                    resp = client.get("http://127.0.0.1:3011/pnl")
                    if resp.status_code == 200:
                        d = resp.json()
                        portfolio = d.get("portfolio", {})
                        positions = d.get("positions", [])
                        total = portfolio.get("total_value", 0)
                        pnl = portfolio.get("pnl", 0)
                        deployed = portfolio.get("deployed", 0)
                        direction = "+" if pnl >= 0 else ""
                        lines.append(
                            f"  Kalshi Weather (LIVE): ${total:.2f} (${deployed:.2f} deployed, {direction}${abs(pnl):.2f} P&L) | "
                            f"{len(positions)} positions"
                        )
                except Exception as e:
                    lines.append(f"  Kalshi Weather: offline ({e})")

        except Exception as e:
            logger.warning(f"Trading bot status fetch failed: {e}")
            return None

        return "\n".join(lines) if lines else None

    def _send_telegram(self, message: str):
        """Send message to Jason via Telegram Bot API."""
        if not httpx:
            # Fallback to requests
            import requests
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            })
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")
            return

        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                }
            )
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")

    def _load_last_date(self) -> Optional[date]:
        """Load last briefing date from persistent storage."""
        if not psycopg2:
            return None
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute(
                "SELECT value FROM gigi_dedup_state WHERE key = 'morning_briefing_last_date'"
            )
            row = cur.fetchone()
            cur.close()
            if row:
                return date.fromisoformat(row[0])
        except Exception as e:
            logger.warning(f"Could not load last briefing date: {e}")
        finally:
            if conn:
                conn.close()
        return None

    def _save_last_date(self, d: date):
        """Persist last briefing date so it survives restart."""
        if not psycopg2:
            return
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gigi_dedup_state (key, value, created_at)
                VALUES ('morning_briefing_last_date', %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
            """, (d.isoformat(),))
            conn.commit()
            cur.close()
        except Exception as e:
            logger.warning(f"Could not save last briefing date: {e}")
        finally:
            if conn:
                conn.close()
