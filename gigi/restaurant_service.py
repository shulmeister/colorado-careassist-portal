"""Restaurant reservation service — Resy API + OpenTable Playwright.

Replaces browse_with_claude ($2/call, 120s timeout) with:
  - Resy: Direct REST API (fast, ~1s, fully automated booking)
  - OpenTable: Deterministic Playwright navigation (~10-15s, booking URL)
"""

import asyncio
import json
import logging
import os
from urllib.parse import quote_plus

import requests

from gigi.browser_automation import (
    NAV_TIMEOUT,
    _extract_text,
    _get_cdp_ws_url,
    _MCPClient,
)

logger = logging.getLogger("gigi.restaurant")

RESY_BASE = "https://api.resy.com"
DENVER = {"lat": 39.7392, "lng": -104.9903}
OT_DENVER_METRO = 5


# ── Resy REST API ──────────────────────────────────────────────────────────


class ResyClient:
    """Resy REST API — search, availability, booking."""

    def __init__(self):
        self.api_key = os.getenv("RESY_API_KEY")
        self.auth_token = os.getenv("RESY_AUTH_TOKEN")

    def _headers(self):
        h = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Origin": "https://resy.com",
            "Referer": "https://resy.com/",
        }
        if self.api_key:
            h["Authorization"] = f'ResyAPI api_key="{self.api_key}"'
        if self.auth_token:
            h["x-resy-auth-token"] = self.auth_token
            h["x-resy-universal-auth"] = self.auth_token
        return h

    def search(self, query: str, date: str, party_size: int = 2) -> list[dict]:
        """Search Resy for restaurants near Denver."""
        if not self.api_key:
            return []
        try:
            r = requests.get(
                f"{RESY_BASE}/4/find",
                headers=self._headers(),
                params={
                    "lat": DENVER["lat"],
                    "long": DENVER["lng"],
                    "day": date,
                    "party_size": party_size,
                    "query": query,
                },
                timeout=10,
            )
            r.raise_for_status()
            hits = r.json().get("search", {}).get("hits", [])
            return [
                {
                    "id": h.get("id", {}).get("resy"),
                    "name": h.get("name", ""),
                    "neighborhood": h.get("location", {}).get("name", ""),
                    "cuisine": (
                        ", ".join(h["cuisine"])
                        if isinstance(h.get("cuisine"), list)
                        else str(h.get("cuisine", ""))
                    ),
                    "price_range": h.get("price_range", 0),
                }
                for h in hits
            ]
        except Exception as e:
            logger.warning(f"Resy search failed: {e}")
            return []

    def availability(self, venue_id: int, date: str, party_size: int) -> list[dict]:
        """Get time slots for a Resy venue."""
        if not self.api_key:
            return []
        try:
            r = requests.get(
                f"{RESY_BASE}/4/find",
                headers=self._headers(),
                params={
                    "lat": 0,
                    "long": 0,
                    "day": date,
                    "party_size": party_size,
                    "venue_id": venue_id,
                },
                timeout=10,
            )
            r.raise_for_status()
            venues = r.json().get("results", {}).get("venues", [])
            if not venues or not venues[0].get("slots"):
                return []
            return [
                {
                    "slot_id": str(s["config"]["id"]),
                    "time": s["date"]["start"],
                    "end_time": s["date"].get("end", ""),
                    "type": s["config"].get("type", ""),
                }
                for s in venues[0]["slots"]
            ]
        except Exception as e:
            logger.warning(f"Resy availability failed: {e}")
            return []

    def book(self, slot_id: str, date: str, party_size: int) -> dict:
        """Book a Resy reservation (requires auth token)."""
        if not self.auth_token:
            return {"success": False, "error": "Resy auth token not configured"}
        try:
            # Step 1: get book token
            r = requests.get(
                f"{RESY_BASE}/3/details",
                headers=self._headers(),
                params={
                    "config_id": slot_id,
                    "day": date,
                    "party_size": party_size,
                },
                timeout=10,
            )
            r.raise_for_status()
            d = r.json()
            token = d.get("book_token", {}).get("value")
            if not token:
                return {"success": False, "error": "No book token returned"}

            # Default payment method
            pmt = next(
                (
                    p
                    for p in d.get("user", {}).get("payment_methods", [])
                    if p.get("is_default")
                ),
                None,
            )
            data = {"book_token": token}
            if pmt:
                data["struct_payment_method"] = json.dumps({"id": pmt["id"]})

            # Step 2: book
            r2 = requests.post(
                f"{RESY_BASE}/3/book",
                headers=self._headers(),
                data=data,
                timeout=10,
            )
            r2.raise_for_status()
            res = r2.json()
            return {
                "success": True,
                "reservation_id": str(res.get("reservation_id", "")),
            }
        except Exception as e:
            logger.error(f"Resy booking failed: {e}")
            return {"success": False, "error": str(e)}


# ── OpenTable Playwright ───────────────────────────────────────────────────


def opentable_search_url(query: str, date: str, time: str, party_size: int) -> str:
    """Build OpenTable search URL for Denver."""
    dt = f"{date}T{time}" if ":" in time else f"{date}T{time}:00"
    return (
        f"https://www.opentable.com/s?"
        f"covers={party_size}&dateTime={dt}"
        f"&term={quote_plus(query)}&metroId={OT_DENVER_METRO}"
    )


async def _opentable_snapshot(
    query: str, date: str, time: str, party_size: int
) -> dict:
    """Navigate to OpenTable search via Chrome CDP and return accessibility snapshot.

    OpenTable uses Akamai bot detection that blocks headless browsers.
    We connect to a running Chrome instance (with user session) via CDP instead.
    Falls back to headless if CDP is unavailable (will likely fail for OpenTable).
    """
    url = opentable_search_url(query, date, time, party_size)
    logger.info(f"OpenTable browser search: {url}")

    # Try CDP first (required for OpenTable — Akamai blocks headless)
    ws_url = _get_cdp_ws_url()
    if ws_url:
        logger.info("Using Chrome CDP for OpenTable (Akamai bypass)")
        client = _MCPClient(cdp_endpoint=ws_url)
    else:
        logger.warning(
            "Chrome CDP not available — headless fallback (OpenTable may block)"
        )
        client = _MCPClient()

    try:
        await client.start()
        await client.call_tool(
            "browser_navigate", {"url": url}, timeout=NAV_TIMEOUT + 5
        )
        await asyncio.sleep(3)  # Let JS render search results
        result = await client.call_tool("browser_snapshot", {})
        snapshot = _extract_text(result, 6000)
        return {"success": True, "snapshot": snapshot, "url": url}
    except Exception as e:
        logger.error(f"OpenTable browser failed: {e}")
        return {"success": False, "error": str(e), "url": url}
    finally:
        await client.close()


# ── Public API ─────────────────────────────────────────────────────────────

_resy = ResyClient()


async def search_restaurant(
    restaurant: str, date: str, time: str, party_size: int
) -> dict:
    """Search for restaurant availability — Resy API first, then OpenTable browser.

    Returns dict with: platform, name, summary (human-readable), and booking data.
    """
    # 1. Resy API (fast, ~1s)
    hits = await asyncio.to_thread(_resy.search, restaurant, date, party_size)
    if hits:
        top = hits[0]
        logger.info(f"Found '{top['name']}' on Resy (ID: {top['id']})")
        slots = await asyncio.to_thread(_resy.availability, top["id"], date, party_size)

        if slots:
            times_str = ", ".join(s["time"] for s in slots[:10])
            return {
                "platform": "resy",
                "venue_id": top["id"],
                "name": top["name"],
                "neighborhood": top.get("neighborhood", ""),
                "slots": slots,
                "summary": (
                    f"Found {top['name']} on Resy"
                    f" ({top.get('neighborhood') or 'Denver'})\n"
                    f"Available times for {party_size} on {date}:\n{times_str}\n\n"
                    f"I can book directly — just confirm which time."
                ),
            }
        return {
            "platform": "resy",
            "venue_id": top["id"],
            "name": top["name"],
            "slots": [],
            "summary": (
                f"Found {top['name']} on Resy but no availability"
                f" for {party_size} on {date}."
            ),
        }

    # 2. OpenTable browser (~10-15s)
    logger.info(f"Not on Resy, trying OpenTable for '{restaurant}'")
    ot = await _opentable_snapshot(restaurant, date, time, party_size)
    if ot.get("success"):
        return {
            "platform": "opentable",
            "name": restaurant,
            "search_url": ot["url"],
            "summary": (
                f"OpenTable results for '{restaurant}'"
                f" ({party_size} guests, {date} at {time}):\n\n"
                f"{ot['snapshot'][:800]}\n\n"
                f"Book here: {ot['url']}"
            ),
        }

    # 3. Neither worked — provide fallback URL
    fallback = opentable_search_url(restaurant, date, time, party_size)
    return {
        "platform": "none",
        "name": restaurant,
        "summary": (
            f"Couldn't find '{restaurant}' automatically.\nTry OpenTable: {fallback}"
        ),
    }


async def confirm_restaurant_booking(session: dict) -> dict:
    """Complete restaurant booking after user confirms via 2FA.

    For Resy: books via API (fully automated).
    For OpenTable: returns booking URL (user completes on site).
    """
    platform = session.get("platform", "")

    if platform == "resy":
        slots = session.get("slots", [])
        if not slots:
            return {"success": False, "error": "No available slots to book"}

        # Pick the slot closest to requested time
        target = session.get("time", "19:00")
        best = min(slots, key=lambda s: _time_diff(s["time"], target))

        result = await asyncio.to_thread(
            _resy.book, best["slot_id"], session["date"], session["party_size"]
        )
        if result.get("success"):
            return {
                "success": True,
                "message": (
                    f"Resy reservation at {best['time']} confirmed! "
                    f"ID: {result['reservation_id']}"
                ),
            }
        return {"success": False, "error": result.get("error", "Resy booking failed")}

    # OpenTable or fallback — provide booking URL
    url = opentable_search_url(
        session.get("restaurant", ""),
        session.get("date", ""),
        session.get("time", "19:00"),
        session.get("party_size", 2),
    )
    return {
        "success": True,
        "message": f"Complete your reservation here: {url}",
        "booking_url": url,
    }


def _time_diff(time_str: str, target: str) -> int:
    """Absolute difference in minutes between two time strings."""

    def to_min(t):
        if "T" in t:
            t = t.split("T")[1]
        parts = t.replace(" ", "").split(":")
        return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)

    try:
        return abs(to_min(time_str) - to_min(target))
    except Exception:
        return 999
