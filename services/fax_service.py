"""
RingCentral Fax Service
Send and receive faxes via RingCentral API (free with existing RingEX plan).
Uses 719-428-3999 as fax number (ext 101, admin).

Fax service using RingCentral API (included free with RingEX plan).
"""
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import psycopg2

logger = logging.getLogger(__name__)

RC_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID", "")
RC_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET", "")
RC_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN", "")
RC_SERVER = os.getenv("RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com")
RC_FAX_NUMBER = "+17194283999"  # 719-428-3999 — company fax line
RC_FAX_EXT_ID = "262740009"    # Extension 101 (Jason) — where faxes arrive

DB_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

FAX_DIR = Path.home() / "logs" / "faxes"
FAX_DIR.mkdir(parents=True, exist_ok=True)
(FAX_DIR / "inbound").mkdir(exist_ok=True)
(FAX_DIR / "outbound").mkdir(exist_ok=True)

# Token cache
_token_cache = {"token": None, "expires_at": None}


async def _get_access_token() -> str:
    """Exchange JWT for RC access token (cached)."""
    global _token_cache
    if _token_cache["token"] and _token_cache["expires_at"] and datetime.now() < _token_cache["expires_at"]:
        return _token_cache["token"]

    if not RC_CLIENT_ID or not RC_JWT_TOKEN:
        logger.error("RingCentral credentials not configured for fax")
        return ""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{RC_SERVER}/restapi/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": RC_JWT_TOKEN,
                },
                auth=(RC_CLIENT_ID, RC_CLIENT_SECRET),
            )
            if resp.status_code == 200:
                data = resp.json()
                _token_cache["token"] = data["access_token"]
                _token_cache["expires_at"] = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 60)
                return _token_cache["token"]
            else:
                logger.error(f"RC JWT exchange failed: {resp.status_code} {resp.text}")
                return ""
    except Exception as e:
        logger.error(f"RC auth error: {e}")
        return ""


def _db():
    return psycopg2.connect(DB_URL)


def _guess_content_type(filename: str) -> str:
    """Guess MIME type from file extension."""
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff", ".tif": "image/tiff",
    }.get(ext, "application/octet-stream")


def _build_cover_page_html(to: str, note: str) -> str:
    """Build a simple HTML cover page for faxing."""
    from datetime import datetime as _dt
    now = _dt.now().strftime("%B %d, %Y  %I:%M %p")
    note_html = note.replace("\n", "<br>")
    return f"""<html><body style="font-family:Arial,sans-serif;padding:60px 50px;color:#222;">
<div style="border-bottom:3px solid #1e40af;padding-bottom:16px;margin-bottom:24px;">
<h1 style="margin:0;font-size:28px;color:#1e40af;">Colorado CareAssist</h1>
<p style="margin:4px 0 0;font-size:13px;color:#666;">719-428-3999 &bull; coloradocareassist.com</p>
</div>
<h2 style="font-size:20px;margin-bottom:20px;">Fax Cover Page</h2>
<table style="font-size:15px;margin-bottom:24px;border-collapse:collapse;">
<tr><td style="padding:4px 16px 4px 0;font-weight:bold;">To:</td><td>{to}</td></tr>
<tr><td style="padding:4px 16px 4px 0;font-weight:bold;">From:</td><td>(719) 428-3999</td></tr>
<tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Date:</td><td>{now}</td></tr>
</table>
<hr style="border:none;border-top:1px solid #ccc;margin:20px 0;">
<div style="font-size:15px;line-height:1.6;">{note_html}</div>
</body></html>"""


async def send_fax(to: str, media_url: str = "", file_path: str = "",
                   file_paths: list = None, cover_note: str = "",
                   from_number: str = "") -> dict:
    """Send a fax via RingCentral API.

    Supports multiple attachments and an optional cover page note.
    - file_path: single file (legacy, for Gigi tools)
    - file_paths: list of (filename, file_bytes) tuples (for portal multi-file)
    - cover_note: text to render as an HTML cover page (first page of fax)
    - media_url: public URL to a document (for Gigi tools)
    """
    import json as _json

    token = await _get_access_token()
    if not token:
        return {"success": False, "error": "RingCentral auth failed — check credentials"}

    to_clean = _normalize_phone(to)
    from_num = from_number or RC_FAX_NUMBER

    try:
        boundary = f"----RCFax{uuid.uuid4().hex[:12]}"
        text_parts = []    # string parts (headers)
        binary_parts = []  # list of (header_str, file_bytes)

        # Part 1: JSON metadata
        metadata = {
            "to": [{"phoneNumber": to_clean}],
            "faxResolution": "High",
        }
        text_parts.append(
            f'--{boundary}\r\n'
            f'Content-Type: application/json\r\n'
            f'\r\n'
            f'{_json.dumps(metadata)}\r\n'
        )

        # Part 2 (optional): Cover page note as HTML
        if cover_note and cover_note.strip():
            html = _build_cover_page_html(to_clean, cover_note.strip())
            html_bytes = html.encode("utf-8")
            binary_parts.append((
                f'--{boundary}\r\n'
                f'Content-Type: text/html\r\n'
                f'Content-Disposition: form-data; name="attachment"; filename="cover-page.html"\r\n'
                f'\r\n',
                html_bytes,
            ))

        # Part 3+: File attachments
        if file_paths:
            for fname, fbytes in file_paths:
                ctype = _guess_content_type(fname)
                binary_parts.append((
                    f'--{boundary}\r\n'
                    f'Content-Type: {ctype}\r\n'
                    f'Content-Disposition: form-data; name="attachment"; filename="{fname}"\r\n'
                    f'\r\n',
                    fbytes,
                ))
        elif file_path and Path(file_path).exists():
            file_bytes = Path(file_path).read_bytes()
            fname = Path(file_path).name
            ctype = _guess_content_type(fname)
            binary_parts.append((
                f'--{boundary}\r\n'
                f'Content-Type: {ctype}\r\n'
                f'Content-Disposition: form-data; name="attachment"; filename="{fname}"\r\n'
                f'\r\n',
                file_bytes,
            ))
        elif media_url:
            async with httpx.AsyncClient(timeout=30) as client:
                dl_resp = await client.get(media_url)
                dl_resp.raise_for_status()
            binary_parts.append((
                f'--{boundary}\r\n'
                f'Content-Type: application/pdf\r\n'
                f'Content-Disposition: form-data; name="attachment"; filename="document.pdf"\r\n'
                f'\r\n',
                dl_resp.content,
            ))

        if not binary_parts:
            return {"success": False, "error": "No file, URL, or note provided"}

        # Assemble full body
        chunks = []
        chunks.append("".join(text_parts).encode("utf-8"))
        for header_str, fbytes in binary_parts:
            chunks.append(header_str.encode("utf-8"))
            chunks.append(fbytes)
            chunks.append(b"\r\n")
        chunks.append(f'--{boundary}--\r\n'.encode("utf-8"))
        full_body = b"".join(chunks)

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{RC_SERVER}/restapi/v1.0/account/~/extension/~/fax",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": f"multipart/mixed; boundary={boundary}",
                },
                content=full_body,
            )

        if resp.status_code in (200, 201, 202):
            data = resp.json()
            fax_id = str(data.get("id", ""))
            status = data.get("messageStatus", "Queued")

            # Log to database
            conn = _db()
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO fax_log (direction, rc_message_id, from_number, to_number, status, media_url)
                    VALUES ('outbound', %s, %s, %s, %s, %s)
                    RETURNING id
                """, (fax_id, from_num, to_clean, status.lower(), media_url or file_path))
                conn.commit()
                log_id = cur.fetchone()[0]
            finally:
                conn.close()

            return {"success": True, "fax_id": fax_id, "status": status, "log_id": log_id}
        else:
            error_msg = f"RC Fax API error: {resp.status_code} {resp.text[:200]}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    except Exception as e:
        logger.error(f"Failed to send fax: {e}")
        return {"success": False, "error": str(e)}


async def get_fax_status(fax_id: str) -> dict:
    """Get fax message status from RingCentral."""
    token = await _get_access_token()
    if not token:
        return {"success": False, "error": "RingCentral auth failed"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{RC_SERVER}/restapi/v1.0/account/~/extension/~/message-store/{fax_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        status = data.get("messageStatus", "unknown").lower()
        page_count = data.get("pgCnt")

        # Update DB
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE fax_log SET status = %s, updated_at = NOW(),
                    page_count = COALESCE(%s, page_count)
                WHERE rc_message_id = %s
            """, (status, page_count, fax_id))
            conn.commit()
        finally:
            conn.close()

        return {
            "success": True,
            "fax_id": fax_id,
            "status": status,
            "direction": data.get("direction", ""),
            "from": data.get("from", {}).get("phoneNumber", ""),
            "to": (data.get("to", [{}])[0].get("phoneNumber", "") if data.get("to") else ""),
            "page_count": page_count,
            "created_at": data.get("creationTime", ""),
        }
    except Exception as e:
        logger.error(f"Failed to get fax status: {e}")
        return {"success": False, "error": str(e)}


async def sync_outbound_statuses():
    """Update status of outbound faxes that are still queued/sending."""
    token = await _get_access_token()
    if not token:
        return

    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, rc_message_id FROM fax_log WHERE direction = 'outbound' AND status IN ('queued', 'sending')")
        pending = cur.fetchall()
        if not pending:
            return

        async with httpx.AsyncClient(timeout=15) as client:
            for log_id, fax_id in pending:
                try:
                    resp = await client.get(
                        f"{RC_SERVER}/restapi/v1.0/account/~/extension/~/message-store/{fax_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        new_status = data.get("messageStatus", "").lower()
                        page_count = data.get("pgCnt")
                        if new_status and new_status != "queued":
                            cur.execute(
                                "UPDATE fax_log SET status = %s, page_count = COALESCE(%s, page_count), updated_at = NOW() WHERE id = %s",
                                (new_status, page_count, log_id),
                            )
                            conn.commit()
                except Exception as e:
                    logger.warning(f"Status check for fax {fax_id} failed: {e}")
    finally:
        conn.close()


async def poll_received_faxes() -> list:
    """Poll RingCentral message-store for received faxes not yet in our DB.
    Also syncs outbound fax statuses."""
    token = await _get_access_token()
    if not token:
        return []

    # Sync outbound statuses first
    try:
        await sync_outbound_statuses()
    except Exception as e:
        logger.warning(f"Outbound status sync failed (non-fatal): {e}")

    new_faxes = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{RC_SERVER}/restapi/v1.0/account/~/extension/{RC_FAX_EXT_ID}/message-store",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "messageType": "Fax",
                    "direction": "Inbound",
                    "dateFrom": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "perPage": 50,
                },
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])

        conn = _db()
        try:
            cur = conn.cursor()
            for rec in records:
                msg_id = str(rec.get("id", ""))
                # Check if already logged
                cur.execute("SELECT 1 FROM fax_log WHERE rc_message_id = %s", (msg_id,))
                if cur.fetchone():
                    continue

                from_num = rec.get("from", {}).get("phoneNumber", "")
                to_num = (rec.get("to", [{}])[0].get("phoneNumber", "") if rec.get("to") else "")
                page_count = rec.get("pgCnt")
                created = rec.get("creationTime", "")

                # Download the fax PDF
                local_path = ""
                attachments = rec.get("attachments", [])
                if attachments and token:
                    att_uri = attachments[0].get("uri", "")
                    if att_uri:
                        local_path = await _download_rc_attachment(att_uri, token)

                cur.execute("""
                    INSERT INTO fax_log (direction, rc_message_id, from_number, to_number, status, page_count, local_path, created_at)
                    VALUES ('inbound', %s, %s, %s, 'received', %s, %s, %s)
                """, (msg_id, from_num, to_num, page_count, local_path, created))
                conn.commit()
                new_faxes.append({"fax_id": msg_id, "from": from_num, "pages": page_count})
                logger.info(f"New inbound fax from {from_num}, {page_count} pages")

                # Send notifications
                try:
                    _notify_fax_received(from_num, page_count)
                except Exception as ne:
                    logger.warning(f"Fax notification failed (non-fatal): {ne}")
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to poll RC faxes: {e}")

    return new_faxes


def _notify_fax_received(from_number: str, page_count: int):
    """Send Telegram + email notifications for a received fax."""
    pages_str = f"{page_count} page{'s' if page_count != 1 else ''}" if page_count else "unknown pages"

    # 1) Telegram
    try:
        import requests
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            text = f"📠 *Inbound Fax Received*\nFrom: `{from_number}`\nPages: {pages_str}\n\n[View in Portal](https://portal.coloradocareassist.com/fax)"
            requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
    except Exception as e:
        logger.warning(f"Telegram fax notify failed: {e}")

    # 2) Email via Gmail
    try:
        from gigi.google_service import GoogleService
        gs = GoogleService()
        subject = f"Fax received from {from_number} ({pages_str})"
        body = (
            f"A new fax has been received.\n\n"
            f"From: {from_number}\n"
            f"Pages: {pages_str}\n\n"
            f"View and download: https://portal.coloradocareassist.com/fax"
        )
        gs.send_email("jason@coloradocareassist.com", subject, body)
    except Exception as e:
        logger.warning(f"Email fax notify failed: {e}")


async def _download_rc_attachment(uri: str, token: str) -> str:
    """Download a fax attachment from RingCentral."""
    filename = f"{uuid.uuid4().hex}.pdf"
    save_path = FAX_DIR / "inbound" / filename
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(uri, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            save_path.write_bytes(resp.content)
        return str(save_path)
    except Exception as e:
        logger.error(f"Failed to download fax attachment: {e}")
        return ""


def list_faxes(direction: str = None, limit: int = 20) -> dict:
    """List faxes from the database. Returns dict with 'faxes' list."""
    conn = _db()
    try:
        cur = conn.cursor()
        if direction and direction in ("inbound", "outbound"):
            cur.execute("""
                SELECT id, direction, rc_message_id, from_number, to_number, status,
                       page_count, local_path, created_at, error_message
                FROM fax_log WHERE direction = %s
                ORDER BY created_at DESC LIMIT %s
            """, (direction, limit))
        else:
            cur.execute("""
                SELECT id, direction, rc_message_id, from_number, to_number, status,
                       page_count, local_path, created_at, error_message
                FROM fax_log ORDER BY created_at DESC LIMIT %s
            """, (limit,))
        rows = cur.fetchall()
        faxes = [
            {
                "id": r[0], "direction": r[1], "fax_id": r[2],
                "from": r[3], "to": r[4], "status": r[5],
                "pages": r[6], "has_pdf": bool(r[7]),
                "created_at": r[8].isoformat() if r[8] else None,
                "error": r[9],
            }
            for r in rows
        ]
        return {"faxes": faxes, "count": len(faxes)}
    finally:
        conn.close()


def _normalize_phone(phone: str) -> str:
    """Normalize to E.164 format."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if phone.startswith("+"):
        return phone
    return f"+{digits}"


# ---------------------------------------------------------------------------
# Gemini config for fax parsing
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

FAX_PARSE_PROMPT = """Analyze this fax document and extract structured information.

First, classify the document type as one of:
- "facesheet" — Patient face sheet from a hospital, nursing home, or VA facility
- "referral" — Physician or facility referral for home care services
- "authorization" — Insurance or VA authorization for care hours
- "other" — Any other type of fax

Then extract ALL available information into this JSON structure:
{
    "document_type": "facesheet|referral|authorization|other",
    "patient": {
        "first_name": "",
        "last_name": "",
        "full_name": "",
        "date_of_birth": "YYYY-MM-DD or null",
        "phone": "",
        "address": "",
        "city": "",
        "state": "",
        "zip": ""
    },
    "insurance": {
        "payer": "",
        "payer_type": "medicare|medicaid|va|private|ltc_insurance|other",
        "member_id": "",
        "group_number": ""
    },
    "referral_source": {
        "facility_name": "",
        "physician_name": "",
        "phone": "",
        "fax": ""
    },
    "diagnosis": [],
    "medications": [],
    "care_needs": "",
    "authorization": {
        "auth_number": "",
        "hours_weekly": null,
        "start_date": "",
        "end_date": "",
        "service_type": ""
    },
    "emergency_contact": {
        "name": "",
        "phone": "",
        "relationship": ""
    },
    "summary": "One paragraph natural language summary of what this fax is about"
}

Return ONLY valid JSON. No markdown, no explanation. Fill in what you can find, leave empty strings for missing fields."""


def _call_gemini_for_fax(pdf_bytes: bytes) -> dict:
    """Parse a fax PDF using Gemini Vision API. Returns parsed data dict."""
    import base64
    import json

    if not GEMINI_API_KEY:
        return {"error": "No Gemini API key configured"}

    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    for model in GEMINI_MODELS:
        try:
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{
                        "parts": [
                            {"text": FAX_PARSE_PROMPT},
                            {"inline_data": {"mime_type": "application/pdf", "data": b64}},
                        ]
                    }]
                },
                timeout=60.0,
            )

            if resp.status_code == 404:
                continue
            if resp.status_code != 200:
                logger.warning(f"Gemini {model} returned {resp.status_code}: {resp.text[:300]}")
                continue

            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text:
                continue

            # Extract JSON from response
            import re
            text = text.strip()
            text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"```$", "", text.strip())

            parsed = json.loads(text)
            logger.info(f"Gemini ({model}) successfully parsed fax document")
            return parsed

        except json.JSONDecodeError:
            logger.warning(f"Gemini {model} returned non-JSON response")
            continue
        except Exception as e:
            logger.debug(f"Gemini {model} failed: {e}")
            continue

    return {"error": "All Gemini models failed to parse fax"}


async def read_fax(fax_id: int) -> dict:
    """Read and AI-parse a fax PDF. Returns document type + structured data."""
    import json

    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT local_path, from_number, page_count, created_at, parsed_data FROM fax_log WHERE id = %s",
            (fax_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return {"error": f"Fax ID {fax_id} not found"}

    local_path, from_number, page_count, created_at, cached_parsed = row

    # Return cached parse if available
    if cached_parsed:
        result = cached_parsed if isinstance(cached_parsed, dict) else json.loads(cached_parsed)
        result["fax_id"] = fax_id
        result["from"] = from_number
        result["pages"] = page_count
        result["cached"] = True
        return result

    if not local_path or not Path(local_path).exists():
        return {"error": f"No PDF file available for fax ID {fax_id}"}

    # Read and parse
    pdf_bytes = Path(local_path).read_bytes()
    parsed = _call_gemini_for_fax(pdf_bytes)

    if "error" not in parsed:
        # Cache the parsed result
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE fax_log SET parsed_data = %s WHERE id = %s",
                (json.dumps(parsed), fax_id),
            )
            conn.commit()
        finally:
            conn.close()

    parsed["fax_id"] = fax_id
    parsed["from"] = from_number
    parsed["pages"] = page_count
    parsed["created_at"] = created_at.isoformat() if created_at else None
    return parsed


async def file_fax_referral(fax_id: int) -> dict:
    """Parse fax, match/create WellSky prospect, upload PDF to Google Drive."""

    # 1) Parse the fax
    parsed = await read_fax(fax_id)
    if "error" in parsed:
        return parsed

    doc_type = parsed.get("document_type", "other")
    patient = parsed.get("patient", {})
    first_name = patient.get("first_name", "").strip()
    last_name = patient.get("last_name", "").strip()
    full_name = patient.get("full_name", "").strip()
    referral = parsed.get("referral_source", {})
    insurance = parsed.get("insurance", {})

    if not last_name and not full_name:
        return {"error": "Could not extract patient name from fax", "parsed": parsed}

    result = {
        "fax_id": fax_id,
        "document_type": doc_type,
        "patient_name": full_name or f"{first_name} {last_name}".strip(),
        "summary": parsed.get("summary", ""),
    }

    # 2) Search cached_patients for existing ACTIVE client match
    conn = _db()
    try:
        cur = conn.cursor()
        search_last = last_name.lower() if last_name else full_name.split()[-1].lower()
        search_first = first_name.lower() if first_name else (full_name.split()[0].lower() if full_name else "")

        # Priority 1: Exact first+last name match on active clients
        best = None
        if search_first and search_last:
            cur.execute(
                "SELECT id, full_name, first_name, last_name FROM cached_patients "
                "WHERE is_active = true AND lower(first_name) = %s AND lower(last_name) = %s LIMIT 1",
                (search_first, search_last),
            )
            row = cur.fetchone()
            if row:
                best = row

        # Priority 2: Last name match on active clients only
        if not best:
            cur.execute(
                "SELECT id, full_name, first_name, last_name FROM cached_patients "
                "WHERE is_active = true AND lower(last_name) = %s ORDER BY full_name LIMIT 5",
                (search_last,),
            )
            matches = cur.fetchall()
            if matches:
                # If multiple active clients share the last name, prefer first-name match
                for m in matches:
                    if m[2] and m[2].lower() == search_first:
                        best = m
                        break
                if not best:
                    best = matches[0]
    finally:
        conn.close()

    if best:
        result["action"] = "matched_client"
        result["client"] = {"id": best[0], "name": best[1]}
        filed_to = str(best[0])
    else:
        # Create WellSky prospect
        try:
            from services.wellsky_service import wellsky_service

            prospect_data = {
                "first_name": first_name or full_name.split()[0] if full_name else "",
                "last_name": last_name or (full_name.split()[-1] if full_name else ""),
                "phone": patient.get("phone", ""),
                "address": patient.get("address", ""),
                "city": patient.get("city", ""),
                "state": patient.get("state", "CO"),
                "zip_code": patient.get("zip", ""),
                "referral_source": referral.get("facility_name", "") or referral.get("physician_name", ""),
                "payer_type": insurance.get("payer_type", ""),
                "care_needs": [parsed.get("care_needs", "")] if parsed.get("care_needs") else [],
                "notes": f"Filed from fax (ID {fax_id}). {parsed.get('summary', '')}",
            }

            auth_info = parsed.get("authorization", {})
            if auth_info.get("hours_weekly"):
                prospect_data["estimated_hours_weekly"] = float(auth_info["hours_weekly"])

            prospect = wellsky_service.create_prospect(prospect_data)
            if prospect:
                result["action"] = "created_prospect"
                result["prospect"] = {"id": prospect.id, "name": prospect.full_name}
                filed_to = prospect.id
            else:
                result["action"] = "prospect_creation_failed"
                filed_to = None
        except Exception as e:
            logger.error(f"WellSky prospect creation failed: {e}")
            result["action"] = "prospect_creation_failed"
            result["wellsky_error"] = str(e)
            filed_to = None

    # 3) Upload PDF to WellSky DocumentReference (so it appears in client's Files tab)
    if filed_to:
        try:
            import base64 as _b64

            from services.wellsky_service import wellsky_service

            local_path_ws = None
            conn = _db()
            try:
                cur = conn.cursor()
                cur.execute("SELECT local_path FROM fax_log WHERE id = %s", (fax_id,))
                ws_row = cur.fetchone()
                if ws_row:
                    local_path_ws = ws_row[0]
            finally:
                conn.close()

            if local_path_ws and Path(local_path_ws).exists():
                pdf_bytes_ws = Path(local_path_ws).read_bytes()
                pdf_b64 = _b64.b64encode(pdf_bytes_ws).decode("utf-8")

                ws_description = f"Fax {doc_type} from {parsed.get('from_number', 'unknown')} — {parsed.get('summary', '')[:200]}"
                # Human-readable type name for WellSky
                ws_type_map = {
                    "facesheet": "Facesheet",
                    "referral": "Referral",
                    "authorization": "Authorization",
                }
                ws_doc_type = ws_type_map.get(doc_type, "Fax Document")
                patient_name = result.get("patient_name", "unknown").replace(" ", "_")
                ws_filename = f"{patient_name}_{doc_type}.pdf"

                success, ws_resp = wellsky_service.create_document_reference(
                    patient_id=str(filed_to),
                    document_type=ws_doc_type,
                    content_type="application/pdf",
                    data_base64=pdf_b64,
                    description=ws_description,
                    filename=ws_filename,
                )
                if success:
                    ws_doc_id = ws_resp.get("id", "unknown") if isinstance(ws_resp, dict) else "unknown"
                    result["wellsky_document_id"] = ws_doc_id
                    logger.info(f"Uploaded fax {fax_id} to WellSky DocumentReference {ws_doc_id} for patient {filed_to}")
                else:
                    result["wellsky_upload_error"] = str(ws_resp)
                    logger.error(f"WellSky DocumentReference upload failed for fax {fax_id}: {ws_resp}")
            else:
                result["wellsky_upload_error"] = "PDF file not found on disk"
        except Exception as e:
            logger.error(f"WellSky document upload failed: {e}")
            result["wellsky_upload_error"] = str(e)

    # 4) Upload copy to Google Drive
    gdrive_url = None
    try:
        local_path_row = None
        conn = _db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT local_path FROM fax_log WHERE id = %s", (fax_id,))
            row = cur.fetchone()
            if row:
                local_path_row = row[0]
        finally:
            conn.close()

        if local_path_row and Path(local_path_row).exists():
            from sales.google_drive_service import GoogleDriveService
            gdrive = GoogleDriveService()

            if gdrive.enabled:
                faxes_folder_id = os.getenv("GOOGLE_DRIVE_FAXES_FOLDER_ID", "")
                if faxes_folder_id:
                    pdf_bytes = Path(local_path_row).read_bytes()
                    # Build organized filename
                    name_part = f"{last_name}_{first_name}" if last_name else full_name.replace(" ", "_")
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    month_folder = datetime.now().strftime("%Y-%m")
                    safe_name = f"{name_part}_{date_str}_{doc_type}.pdf"

                    # Get or create Inbound subfolder
                    inbound_id = gdrive.create_folder_if_not_exists(faxes_folder_id, "Inbound")
                    if inbound_id:
                        # Get or create monthly subfolder
                        month_id = gdrive.create_folder_if_not_exists(inbound_id, month_folder)
                        target_folder = month_id or inbound_id
                    else:
                        target_folder = faxes_folder_id

                    upload_result = gdrive.upload_file(
                        file_bytes=pdf_bytes,
                        filename=safe_name,
                        folder_id=target_folder,
                        mime_type="application/pdf",
                    )
                    if upload_result:
                        gdrive_url = upload_result.get("webViewLink") or upload_result.get("url")
                        result["gdrive_url"] = gdrive_url
                        result["gdrive_filename"] = safe_name
                else:
                    result["gdrive_note"] = "GOOGLE_DRIVE_FAXES_FOLDER_ID not configured"
            else:
                result["gdrive_note"] = "Google Drive service not enabled"
    except Exception as e:
        logger.error(f"Google Drive upload failed: {e}")
        result["gdrive_error"] = str(e)

    # 5) Update fax_log with filing info
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE fax_log SET filed_to = %s, gdrive_url = %s, filed_at = NOW() WHERE id = %s",
            (filed_to, gdrive_url, fax_id),
        )
        conn.commit()
    finally:
        conn.close()

    return result
