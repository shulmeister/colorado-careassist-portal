"""Ticket Watch & Alert Service — monitors Ticketmaster/Bandsintown for on-sale dates."""

import json
import logging
import os
from datetime import datetime

import psycopg2
import requests

logger = logging.getLogger(__name__)

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")
BANDSINTOWN_APP_ID = os.getenv("BANDSINTOWN_APP_ID", "gigi_careassist")
SEATGEEK_CLIENT_ID = os.getenv("SEATGEEK_CLIENT_ID", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")


class TicketMonitorService:
    """Polls ticket APIs for watched artists and sends Telegram alerts."""

    def check_watches(self):
        """Called from RC bot every ~15 min. Check all active watches."""
        try:
            watches = self._get_active_watches()
            if not watches:
                return
            for watch in watches:
                try:
                    self._check_single_watch(watch)
                except Exception as e:
                    logger.error(f"Ticket watch #{watch['id']} ({watch['artist']}) error: {e}")
        except Exception as e:
            logger.error(f"Ticket monitor error: {e}")

    def _check_single_watch(self, watch):
        """Check one watch against Ticketmaster + Bandsintown."""
        watch_id = watch["id"]
        artist = watch["artist"]
        venue = watch.get("venue") or ""
        city = watch.get("city") or "Denver"
        notified_events = watch.get("notified_events") or []
        notified_set = {e.get("event_id") for e in notified_events if isinstance(e, dict)}

        # Search Ticketmaster
        events = self._search_ticketmaster(artist, city)

        # Search Bandsintown (catches some AXS events when registered)
        bit_events = self._search_bandsintown(artist)
        events.extend(bit_events)

        # Search SeatGeek (native AXS inventory — primary AXS source for Colorado)
        sg_events = self._search_seatgeek(artist, city)
        events.extend(sg_events)

        # Filter by venue if specified
        if venue:
            venue_lower = venue.lower()
            events = [e for e in events if venue_lower in e.get("venue", "").lower()]

        if not events:
            self._update_last_checked(watch_id)
            return

        now = datetime.utcnow()
        new_notifications = []

        for event in events:
            event_id = event.get("event_id", "")
            if not event_id:
                continue

            # New event discovery
            if event_id not in notified_set:
                self._send_alert(
                    f"NEW EVENT FOUND for '{artist}'",
                    event,
                    watch,
                )
                new_notifications.append({
                    "event_id": event_id,
                    "type": "new_event",
                    "notified_at": now.isoformat(),
                })
                notified_set.add(event_id)

            # Check presale alerts
            for sale in event.get("sales", []):
                sale_start = sale.get("start_datetime")
                if not sale_start:
                    continue
                sale_dt = _parse_datetime(sale_start)
                if not sale_dt:
                    continue

                sale_type = sale.get("type", "general")
                alert_key_24h = f"{event_id}_{sale_type}_24h"
                alert_key_15m = f"{event_id}_{sale_type}_15m"

                # 24h alert
                time_until = (sale_dt - now).total_seconds()
                if 0 < time_until <= 86400 and alert_key_24h not in notified_set:
                    hours = int(time_until / 3600)
                    self._send_alert(
                        f"{sale_type.upper()} ON-SALE IN ~{hours}H for '{artist}'",
                        event,
                        watch,
                        extra=f"On-sale: {sale_start}\nType: {sale_type}",
                    )
                    new_notifications.append({
                        "event_id": alert_key_24h,
                        "type": f"{sale_type}_24h",
                        "notified_at": now.isoformat(),
                    })
                    notified_set.add(alert_key_24h)

                # 15-min alert
                if 0 < time_until <= 900 and alert_key_15m not in notified_set:
                    mins = int(time_until / 60)
                    self._send_alert(
                        f"GET IN QUEUE NOW — {sale_type.upper()} ON-SALE IN {mins} MIN for '{artist}'",
                        event,
                        watch,
                        extra=f"On-sale: {sale_start}\nType: {sale_type}\nLink: {event.get('url', 'N/A')}",
                    )
                    new_notifications.append({
                        "event_id": alert_key_15m,
                        "type": f"{sale_type}_15m",
                        "notified_at": now.isoformat(),
                    })
                    notified_set.add(alert_key_15m)

        # Update DB
        self._update_watch(watch_id, events, new_notifications)

    def _search_ticketmaster(self, artist, city):
        """Search Ticketmaster Discovery API."""
        if not TICKETMASTER_API_KEY:
            return []
        try:
            resp = requests.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={
                    "apikey": TICKETMASTER_API_KEY,
                    "keyword": artist,
                    "city": city,
                    "size": 10,
                    "sort": "date,asc",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"Ticketmaster API {resp.status_code}: {resp.text[:200]}")
                return []
            data = resp.json()
            events = []
            for ev in data.get("_embedded", {}).get("events", []):
                venue_name = ""
                venue_obj = ev.get("_embedded", {}).get("venues", [{}])
                if venue_obj:
                    venue_name = venue_obj[0].get("name", "")
                sales = []
                for sale_type, sale_info in ev.get("sales", {}).items():
                    if isinstance(sale_info, dict) and sale_info.get("startDateTime"):
                        sales.append({
                            "type": sale_type,
                            "start_datetime": sale_info["startDateTime"],
                            "end_datetime": sale_info.get("endDateTime"),
                        })
                    elif isinstance(sale_info, list):
                        for s in sale_info:
                            if isinstance(s, dict) and s.get("startDateTime"):
                                sales.append({
                                    "type": s.get("name", sale_type),
                                    "start_datetime": s["startDateTime"],
                                    "end_datetime": s.get("endDateTime"),
                                })
                events.append({
                    "event_id": f"tm_{ev.get('id', '')}",
                    "name": ev.get("name", ""),
                    "date": ev.get("dates", {}).get("start", {}).get("localDate", ""),
                    "time": ev.get("dates", {}).get("start", {}).get("localTime", ""),
                    "venue": venue_name,
                    "url": ev.get("url", ""),
                    "source": "ticketmaster",
                    "sales": sales,
                    "price_range": ev.get("priceRanges", []),
                    "status": ev.get("dates", {}).get("status", {}).get("code", ""),
                })
            return events
        except Exception as e:
            logger.error(f"Ticketmaster search error: {e}")
            return []

    def _search_bandsintown(self, artist):
        """Search Bandsintown API."""
        try:
            resp = requests.get(
                f"https://rest.bandsintown.com/artists/{requests.utils.quote(artist)}/events",
                params={"app_id": BANDSINTOWN_APP_ID},
                timeout=10,
            )
            if resp.status_code == 403:
                logger.warning(
                    f"Bandsintown 403 for '{artist}' — app_id '{BANDSINTOWN_APP_ID}' not authorized. "
                    "Register at artists.bandsintown.com or set SEATGEEK_CLIENT_ID for AXS coverage."
                )
                return []
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            events = []
            for ev in data:
                venue_info = ev.get("venue", {})
                offers = ev.get("offers", [])
                sales = []
                for offer in offers:
                    if offer.get("url"):
                        sales.append({
                            "type": offer.get("type", "general"),
                            "start_datetime": ev.get("on_sale_datetime") or ev.get("datetime", ""),
                            "url": offer.get("url", ""),
                        })
                events.append({
                    "event_id": f"bit_{ev.get('id', '')}",
                    "name": ev.get("title") or f"{ev.get('artist', {}).get('name', '')} at {venue_info.get('name', '')}",
                    "date": ev.get("datetime", "")[:10],
                    "time": ev.get("datetime", "")[11:16] if "T" in ev.get("datetime", "") else "",
                    "venue": venue_info.get("name", ""),
                    "city": venue_info.get("city", ""),
                    "url": ev.get("url", ""),
                    "source": "bandsintown",
                    "sales": sales,
                })
            return events
        except Exception as e:
            logger.error(f"Bandsintown search error: {e}")
            return []

    def _search_seatgeek(self, artist, city="Denver"):
        """Search SeatGeek API — has native AXS inventory, free with client_id.
        Register at seatgeek.com/account/developer for a free client_id.
        Set SEATGEEK_CLIENT_ID env var to enable.
        """
        if not SEATGEEK_CLIENT_ID:
            return []
        try:
            # Find performer slug first
            resp = requests.get(
                "https://api.seatgeek.com/2/performers",
                params={"q": artist, "client_id": SEATGEEK_CLIENT_ID},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"SeatGeek performers API {resp.status_code} for '{artist}'")
                return []
            performers = resp.json().get("performers", [])
            if not performers:
                return []
            slug = performers[0].get("slug", "")

            # Search events for this performer in target city
            resp = requests.get(
                "https://api.seatgeek.com/2/events",
                params={
                    "performers.slug": slug,
                    "venue.city": city,
                    "client_id": SEATGEEK_CLIENT_ID,
                    "per_page": 10,
                    "sort": "datetime_local.asc",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"SeatGeek events API {resp.status_code} for '{artist}'")
                return []

            events = []
            for ev in resp.json().get("events", []):
                venue_obj = ev.get("venue", {})
                dt_str = ev.get("datetime_local", "")
                sales = []
                if ev.get("announce_date"):
                    sales.append({
                        "type": "general",
                        "start_datetime": ev["announce_date"],
                    })
                events.append({
                    "event_id": f"sg_{ev.get('id', '')}",
                    "name": ev.get("title", ""),
                    "date": dt_str[:10] if dt_str else "",
                    "time": dt_str[11:16] if "T" in dt_str else "",
                    "venue": venue_obj.get("name", ""),
                    "city": venue_obj.get("city", ""),
                    "url": ev.get("url", ""),
                    "source": "seatgeek",
                    "sales": sales,
                })
            return events
        except Exception as e:
            logger.error(f"SeatGeek search error: {e}")
            return []

    def _send_alert(self, title, event, watch, extra=""):
        """Send Telegram alert."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram creds missing, skipping ticket alert")
            return
        lines = [
            f"TICKET ALERT: {title}",
            f"Event: {event.get('name', 'Unknown')}",
            f"Date: {event.get('date', 'TBD')} {event.get('time', '')}",
            f"Venue: {event.get('venue', 'TBD')}",
            f"Source: {event.get('source', '')}",
        ]
        if event.get("url"):
            lines.append(f"Link: {event['url']}")
        if event.get("price_range"):
            pr = event["price_range"][0]
            lines.append(f"Price: ${pr.get('min', '?')} - ${pr.get('max', '?')}")
        if extra:
            lines.append(extra)
        message = "\n".join(lines)
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
                timeout=5,
            )
            logger.info(f"Ticket alert sent: {title}")
        except Exception as e:
            logger.error(f"Ticket alert send failed: {e}")

    def _get_active_watches(self):
        """Get all active watches from DB."""
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, artist, venue, city, notified_events, found_events "
                "FROM gigi_ticket_watches WHERE status = 'active' ORDER BY id"
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "artist": r[1], "venue": r[2], "city": r[3],
                    "notified_events": r[4] or [], "found_events": r[5] or [],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def _update_watch(self, watch_id, events, new_notifications):
        """Update watch with found events and notification history."""
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            events_json = json.dumps([
                {k: v for k, v in e.items() if k != "sales"}
                for e in events[:20]
            ])
            if new_notifications:
                cur.execute(
                    "UPDATE gigi_ticket_watches SET last_checked_at = NOW(), "
                    "last_notified_at = NOW(), "
                    "found_events = %s::jsonb, "
                    "notified_events = notified_events || %s::jsonb "
                    "WHERE id = %s",
                    (events_json, json.dumps(new_notifications), watch_id),
                )
            else:
                cur.execute(
                    "UPDATE gigi_ticket_watches SET last_checked_at = NOW(), "
                    "found_events = %s::jsonb WHERE id = %s",
                    (events_json, watch_id),
                )
            conn.commit()
        finally:
            conn.close()

    def _update_last_checked(self, watch_id):
        """Just update the last_checked timestamp."""
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE gigi_ticket_watches SET last_checked_at = NOW() WHERE id = %s",
                (watch_id,),
            )
            conn.commit()
        finally:
            conn.close()


def _parse_datetime(dt_str):
    """Parse ISO datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        dt_str = dt_str.replace("Z", "+00:00")
        if "+" in dt_str[10:]:
            dt_str = dt_str[:dt_str.index("+", 10)]
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


# --- Tool functions (called from chief_of_staff_tools.py) ---

def create_watch(artist, venue=None, city="Denver"):
    """Create a new ticket watch and do an immediate search."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO gigi_ticket_watches (artist, venue, city) VALUES (%s, %s, %s) RETURNING id",
            (artist, venue, city),
        )
        watch_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    # Immediate search
    monitor = TicketMonitorService()
    events = monitor._search_ticketmaster(artist, city)
    bit_events = monitor._search_bandsintown(artist)
    events.extend(bit_events)
    sg_events = monitor._search_seatgeek(artist, city)
    events.extend(sg_events)

    if venue:
        venue_lower = venue.lower()
        events = [e for e in events if venue_lower in e.get("venue", "").lower()]

    # Cache found events
    if events:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            events_json = json.dumps([
                {k: v for k, v in e.items() if k != "sales"}
                for e in events[:20]
            ])
            cur.execute(
                "UPDATE gigi_ticket_watches SET found_events = %s::jsonb, last_checked_at = NOW() WHERE id = %s",
                (events_json, watch_id),
            )
            conn.commit()
        finally:
            conn.close()

    return {
        "watch_id": watch_id,
        "artist": artist,
        "venue": venue,
        "city": city,
        "events_found": len(events),
        "events": [
            {
                "name": e.get("name", ""),
                "date": e.get("date", ""),
                "venue": e.get("venue", ""),
                "source": e.get("source", ""),
                "url": e.get("url", ""),
                "sales": e.get("sales", []),
            }
            for e in events[:5]
        ],
    }


def list_watches():
    """List all active ticket watches."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, artist, venue, city, status, created_at, last_checked_at, "
            "last_notified_at, found_events FROM gigi_ticket_watches "
            "WHERE status = 'active' ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return {
            "watches": [
                {
                    "id": r[0],
                    "artist": r[1],
                    "venue": r[2],
                    "city": r[3],
                    "status": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                    "last_checked": r[6].isoformat() if r[6] else "never",
                    "last_notified": r[7].isoformat() if r[7] else "never",
                    "events_found": len(r[8]) if r[8] else 0,
                }
                for r in rows
            ],
            "count": len(rows),
        }
    finally:
        conn.close()


def remove_watch(watch_id):
    """Deactivate a ticket watch."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE gigi_ticket_watches SET status = 'inactive' WHERE id = %s RETURNING artist",
            (watch_id,),
        )
        row = cur.fetchone()
        conn.commit()
        if row:
            return {"success": True, "message": f"Stopped watching for '{row[0]}' tickets."}
        return {"success": False, "error": f"Watch #{watch_id} not found."}
    finally:
        conn.close()
