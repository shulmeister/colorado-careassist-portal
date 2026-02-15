"""
Morning Briefing Service

Sends Jason a daily morning briefing via Telegram at 7:00 AM Mountain Time.
Includes: weather, calendar, today's shifts, unread emails, overnight alerts, ski conditions.

Integrates with the RC bot's check_and_act() polling loop.
Uses Google API (GoogleService) for calendar and email — NOT the gog CLI.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional
from pathlib import Path

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

MORNING_BRIEFING_ENABLED = os.getenv("MORNING_BRIEFING_ENABLED", "true").lower() == "true"
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
        if weather:
            sections.append(f"WEATHER\n{weather}")
        else:
            sections.append("WEATHER\n  Weather data temporarily unavailable.")

        # Calendar
        calendar = self._get_calendar()
        if calendar:
            sections.append(f"CALENDAR\n{calendar}")
        else:
            sections.append("CALENDAR\nNo events scheduled today.")

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

        # Weekly self-audit (Mondays only)
        if now.weekday() == 0:  # Monday
            audit = self._get_self_audit()
            if audit:
                sections.append(audit)

        sections.append("— Gigi")
        return "\n\n".join(sections)

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

    def _get_self_audit(self) -> Optional[str]:
        """Get weekly self-audit (Mondays only)."""
        try:
            from gigi.self_monitor import SelfMonitor
            sm = SelfMonitor()
            return sm.get_briefing_section()
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
        """Get today's calendar events via Google API."""
        if not self._google:
            return None
        try:
            events = self._google.get_calendar_events(days=1, max_results=10)
            if not events:
                return None
            lines = []
            for e in events:
                time_str = e.get("start", "")
                # Parse ISO datetime to friendly time
                if "T" in str(time_str):
                    try:
                        dt = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                        if TIMEZONE:
                            dt = dt.astimezone(TIMEZONE)
                        time_str = dt.strftime("%-I:%M %p")
                    except (ValueError, TypeError):
                        pass
                summary = e.get("summary", "No Title")
                location = e.get("location", "")
                line = f"  {time_str} — {summary}"
                if location and location != "N/A":
                    line += f" ({location})"
                lines.append(line)
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
        """Get unread email summary via Google API."""
        if not self._google:
            return None
        try:
            emails = self._google.search_emails(query="is:unread", max_results=10)
            if not emails:
                return None

            count = len(emails)
            lines = []
            for e in emails[:5]:  # Show top 5
                sender = e.get("from", "Unknown")
                # Clean up sender to just name
                if "<" in sender:
                    sender = sender.split("<")[0].strip().strip('"')
                subject = e.get("subject", "No Subject")
                lines.append(f"  {sender}: {subject}")

            if count > 5:
                lines.append(f"  ...and {count - 5} more")

            return {"count": count, "summary": "\n".join(lines)}
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
