"""
Gigi Shadow Mode Learning Pipeline

Automated learning loop that:
1. Pulls Gigi's shadow SMS drafts from gigi_sms_drafts table
2. Pulls staff's actual replies from RingCentral message-store API
3. Pairs them by phone number and time window
4. Uses Anthropic Haiku to compare draft vs actual reply
5. Creates correction memories when Gigi's draft differs significantly

Runs as a cron (LaunchAgent) every 6 hours.

Author: Colorado Care Assist
Date: February 20, 2026
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import anthropic
import psycopg2
from psycopg2.extras import Json, RealDictCursor

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com")
ANALYSIS_MODEL = "claude-haiku-4-5-20251001"

# How far back to look for staff replies (minutes after Gigi's draft)
PAIRING_WINDOW_MINUTES = 60

# Minimum difference threshold — only create corrections for meaningful differences
MIN_DIFFERENCE_SCORE = 3  # out of 10


def _get_rc_access_token() -> Optional[str]:
    """Get RingCentral access token via JWT exchange."""
    import requests
    client_id = os.getenv("RINGCENTRAL_CLIENT_ID")
    client_secret = os.getenv("RINGCENTRAL_CLIENT_SECRET")
    jwt_token = os.getenv("RINGCENTRAL_JWT_TOKEN")

    if not all([client_id, client_secret, jwt_token]):
        logger.error("RingCentral credentials not configured")
        return None

    try:
        resp = requests.post(
            f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(client_id, client_secret),
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token
            },
            timeout=20
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        else:
            logger.error(f"RC JWT exchange failed: {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"RC auth error: {e}")
        return None


def _fetch_outbound_sms(access_token: str, since: datetime) -> List[Dict]:
    """Fetch outbound SMS messages from RingCentral since a given time."""
    import requests

    messages = []
    date_from = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    try:
        url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"
        params = {
            "messageType": "SMS",
            "direction": "Outbound",
            "dateFrom": date_from,
            "perPage": 250
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for record in data.get("records", []):
                to_numbers = [t.get("phoneNumber", "") for t in record.get("to", [])]
                messages.append({
                    "id": record.get("id"),
                    "to": to_numbers,
                    "text": record.get("subject", ""),
                    "time": record.get("creationTime", ""),
                    "direction": "Outbound"
                })
            logger.info(f"Fetched {len(messages)} outbound SMS from RC")
        else:
            logger.error(f"RC message-store fetch failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"RC SMS fetch error: {e}")

    return messages


def _get_unpaired_drafts(conn) -> List[Dict]:
    """Get shadow drafts that haven't been paired with staff replies yet."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, from_phone, from_name, inbound_text, draft_reply,
                   inbound_time, draft_time, created_at
            FROM gigi_sms_drafts
            WHERE paired = false
              AND created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at ASC
            LIMIT 50
        """)
        return [dict(row) for row in cur.fetchall()]


def _normalize_phone(phone: str) -> str:
    """Normalize phone to last 10 digits for comparison."""
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits


def pair_drafts_with_replies(conn, access_token: str) -> List[Dict]:
    """
    Match Gigi's shadow drafts with staff's actual outbound SMS replies.

    For each unpaired draft, look for an outbound SMS to the same number
    within PAIRING_WINDOW_MINUTES after the draft was created.
    """
    drafts = _get_unpaired_drafts(conn)
    if not drafts:
        logger.info("No unpaired drafts to process")
        return []

    # Find the earliest draft to determine how far back to fetch RC messages
    earliest = min(d["created_at"] for d in drafts)
    rc_messages = _fetch_outbound_sms(access_token, earliest)

    paired = []
    for draft in drafts:
        draft_phone = _normalize_phone(draft["from_phone"])
        draft_time = draft["draft_time"] or draft["created_at"]

        # Find matching outbound SMS: same phone, within time window
        window_end = draft_time + timedelta(minutes=PAIRING_WINDOW_MINUTES)

        best_match = None
        for msg in rc_messages:
            for to_num in msg["to"]:
                if _normalize_phone(to_num) == draft_phone:
                    try:
                        msg_time = datetime.fromisoformat(
                            msg["time"].replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                    except (ValueError, AttributeError):
                        continue

                    # Must be AFTER the draft and within window
                    if draft_time <= msg_time <= window_end:
                        if best_match is None or msg_time < best_match["time_parsed"]:
                            best_match = {
                                "text": msg["text"],
                                "time": msg["time"],
                                "time_parsed": msg_time,
                                "msg_id": msg["id"]
                            }

        if best_match:
            # Update draft with actual reply
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE gigi_sms_drafts
                    SET actual_reply = %s,
                        actual_reply_time = %s,
                        actual_reply_by = 'staff',
                        paired = true
                    WHERE id = %s
                """, (best_match["text"], best_match["time"], draft["id"]))
            conn.commit()

            draft["actual_reply"] = best_match["text"]
            draft["actual_reply_time"] = best_match["time"]
            paired.append(draft)
            logger.info(f"Paired draft {draft['id']} with staff reply to {draft_phone}")
        else:
            # If draft is old enough (>2 hours), mark as paired with no reply
            age = datetime.utcnow() - draft_time
            if age > timedelta(hours=2):
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE gigi_sms_drafts
                        SET paired = true, actual_reply_by = 'no_reply'
                        WHERE id = %s
                    """, (draft["id"],))
                conn.commit()
                logger.info(f"Draft {draft['id']} aged out — no staff reply found")

    logger.info(f"Paired {len(paired)} drafts with staff replies")
    return paired


def analyze_draft_vs_reply(
    inbound_text: str,
    draft_reply: str,
    actual_reply: str,
    from_name: str = "Unknown"
) -> Dict[str, Any]:
    """
    Use Anthropic Haiku to compare Gigi's draft with staff's actual reply.

    Returns analysis with:
    - difference_score (1-10, where 10 = completely different)
    - correction (what Gigi should learn)
    - category (tone, content, action, escalation)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    prompt = f"""Compare an AI assistant's draft SMS reply with what the human staff actually sent.
The AI is "Gigi", a home care agency assistant. The staff member is experienced and their reply is the gold standard.

INBOUND MESSAGE (from {from_name}):
{inbound_text}

GIGI'S DRAFT REPLY:
{draft_reply}

STAFF'S ACTUAL REPLY:
{actual_reply}

Analyze the difference and return ONLY valid JSON:
{{
    "difference_score": <1-10, where 1=nearly identical, 10=completely different>,
    "difference_type": "<tone|content|action|escalation|length|none>",
    "what_gigi_got_wrong": "<specific issue, or 'nothing' if draft was fine>",
    "correction": "<what Gigi should remember for next time, phrased as an instruction>",
    "staff_approach": "<brief description of what the staff did differently>",
    "gigi_was_better": <true if Gigi's draft was actually better than staff reply, false otherwise>
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()

        # Extract JSON
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {"error": "Could not parse analysis", "raw": text[:200]}
    except Exception as e:
        return {"error": str(e)}


def create_correction_memory(conn, analysis: Dict, draft: Dict) -> Optional[str]:
    """Create a correction memory from analysis results."""
    correction_text = analysis.get("correction", "")
    if not correction_text or correction_text.lower() == "nothing":
        return None

    diff_type = analysis.get("difference_type", "general")
    category_map = {
        "tone": "communication",
        "content": "operations",
        "action": "scheduling",
        "escalation": "operations",
        "length": "communication"
    }
    category = category_map.get(diff_type, "communication")

    metadata = {
        "source_type": "shadow_learning",
        "draft_id": str(draft["id"]),
        "from_phone": draft["from_phone"],
        "difference_score": analysis.get("difference_score", 5),
        "difference_type": diff_type,
        "inbound_preview": draft["inbound_text"][:100],
        "created_by": "learning_pipeline"
    }

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gigi_memories (
                    type, content, confidence, source, category,
                    impact_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                "correction",
                f"SMS correction: {correction_text}",
                0.8,
                "correction",
                category,
                "medium",
                Json(metadata)
            ))
            memory_id = str(cur.fetchone()[0])

            # Log to audit
            cur.execute("""
                INSERT INTO gigi_memory_audit_log (
                    memory_id, event_type, new_confidence, reason
                ) VALUES (%s, %s, %s, %s)
            """, (memory_id, "created", 0.8, f"Shadow learning: {diff_type} correction"))

        conn.commit()
        return memory_id
    except Exception as e:
        logger.error(f"Failed to create correction memory: {e}")
        conn.rollback()
        return None


def reinforce_existing_correction(conn, new_correction: str) -> Optional[str]:
    """
    Check if a similar correction already exists. If so, reinforce it
    instead of creating a duplicate.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Search for similar corrections
            cur.execute("""
                SELECT id, content, confidence, reinforcement_count
                FROM gigi_memories
                WHERE type = 'correction'
                  AND source = 'correction'
                  AND status = 'active'
                  AND metadata->>'source_type' = 'shadow_learning'
                ORDER BY created_at DESC
                LIMIT 20
            """)
            existing = cur.fetchall()

        # Simple text similarity check — if >60% word overlap, reinforce
        new_words = set(new_correction.lower().split())
        for mem in existing:
            existing_words = set(mem["content"].lower().split())
            if not new_words or not existing_words:
                continue
            overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
            if overlap > 0.6:
                # Reinforce existing memory
                with conn.cursor() as cur:
                    new_conf = min(0.95, mem["confidence"] + 0.05)
                    cur.execute("""
                        UPDATE gigi_memories
                        SET confidence = %s,
                            reinforcement_count = reinforcement_count + 1,
                            last_reinforced_at = NOW()
                        WHERE id = %s
                    """, (float(new_conf), mem["id"]))
                    cur.execute("""
                        INSERT INTO gigi_memory_audit_log (
                            memory_id, event_type, old_confidence,
                            new_confidence, reason
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        mem["id"], "reinforced",
                        float(mem["confidence"]), float(new_conf),
                        "Shadow learning reinforcement"
                    ))
                conn.commit()
                logger.info(f"Reinforced existing correction {mem['id']} "
                          f"({mem['reinforcement_count']+1} times)")
                return str(mem["id"])

        return None  # No match found
    except Exception as e:
        logger.error(f"Reinforce check failed: {e}")
        return None


def run_learning_pipeline() -> Dict[str, Any]:
    """
    Main entry point. Run the full learning pipeline:
    1. Pair unpaired drafts with staff replies
    2. Analyze each pair with Haiku
    3. Create/reinforce correction memories
    """
    results = {
        "paired": 0,
        "analyzed": 0,
        "corrections_created": 0,
        "corrections_reinforced": 0,
        "skipped_low_diff": 0,
        "skipped_gigi_better": 0,
        "errors": []
    }

    # Get RC access token
    access_token = _get_rc_access_token()
    if not access_token:
        results["errors"].append("Could not get RC access token")
        return results

    conn = psycopg2.connect(DB_URL)
    try:
        # Step 1: Pair drafts with staff replies
        paired = pair_drafts_with_replies(conn, access_token)
        results["paired"] = len(paired)

        # Also get previously paired but unprocessed drafts
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, from_phone, from_name, inbound_text, draft_reply,
                       actual_reply, actual_reply_time, created_at, draft_time
                FROM gigi_sms_drafts
                WHERE paired = true
                  AND processed = false
                  AND actual_reply IS NOT NULL
                  AND actual_reply_by = 'staff'
                ORDER BY created_at ASC
                LIMIT 30
            """)
            to_analyze = [dict(row) for row in cur.fetchall()]

        # Step 2: Analyze each pair
        for draft in to_analyze:
            results["analyzed"] += 1

            analysis = analyze_draft_vs_reply(
                inbound_text=draft["inbound_text"],
                draft_reply=draft["draft_reply"],
                actual_reply=draft["actual_reply"],
                from_name=draft.get("from_name", "Unknown")
            )

            if "error" in analysis:
                results["errors"].append(f"Analysis error for {draft['id']}: {analysis['error']}")
                continue

            # Store analysis result
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE gigi_sms_drafts
                    SET analysis = %s, processed = true
                    WHERE id = %s
                """, (Json(analysis), draft["id"]))
            conn.commit()

            diff_score = analysis.get("difference_score", 0)

            # Skip if Gigi was actually better
            if analysis.get("gigi_was_better"):
                results["skipped_gigi_better"] += 1
                logger.info(f"Draft {draft['id']}: Gigi was better — no correction needed")
                continue

            # Skip low-difference pairs
            if diff_score < MIN_DIFFERENCE_SCORE:
                results["skipped_low_diff"] += 1
                logger.info(f"Draft {draft['id']}: Low difference ({diff_score}/10) — skipping")
                continue

            # Step 3: Create or reinforce correction
            correction_text = analysis.get("correction", "")
            if correction_text and correction_text.lower() != "nothing":
                # Check for existing similar correction first
                reinforced_id = reinforce_existing_correction(conn, correction_text)
                if reinforced_id:
                    results["corrections_reinforced"] += 1
                    # Link draft to reinforced memory
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE gigi_sms_drafts
                            SET correction_memory_id = %s
                            WHERE id = %s
                        """, (reinforced_id, draft["id"]))
                    conn.commit()
                else:
                    # Create new correction memory
                    memory_id = create_correction_memory(conn, analysis, draft)
                    if memory_id:
                        results["corrections_created"] += 1
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE gigi_sms_drafts
                                SET correction_memory_id = %s
                                WHERE id = %s
                            """, (memory_id, draft["id"]))
                        conn.commit()
                        logger.info(f"Created correction memory {memory_id} "
                                  f"for draft {draft['id']} (diff: {diff_score}/10)")

    except Exception as e:
        logger.error(f"Learning pipeline error: {e}")
        results["errors"].append(str(e))
    finally:
        conn.close()

    return results


def get_learning_stats() -> Dict[str, Any]:
    """Get stats about the learning pipeline for API/dashboard."""
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Total drafts
            cur.execute("SELECT COUNT(*) as total FROM gigi_sms_drafts")
            total = cur.fetchone()["total"]

            # Paired
            cur.execute("SELECT COUNT(*) as paired FROM gigi_sms_drafts WHERE paired = true")
            paired = cur.fetchone()["paired"]

            # Processed (analyzed)
            cur.execute("SELECT COUNT(*) as processed FROM gigi_sms_drafts WHERE processed = true")
            processed = cur.fetchone()["processed"]

            # With corrections
            cur.execute("""
                SELECT COUNT(*) as corrections
                FROM gigi_sms_drafts
                WHERE correction_memory_id IS NOT NULL
            """)
            corrections = cur.fetchone()["corrections"]

            # Average difference score
            cur.execute("""
                SELECT AVG((analysis->>'difference_score')::float) as avg_diff
                FROM gigi_sms_drafts
                WHERE analysis IS NOT NULL
                  AND analysis->>'difference_score' IS NOT NULL
            """)
            avg_diff = cur.fetchone()["avg_diff"]

            # Correction memories from learning
            cur.execute("""
                SELECT COUNT(*) as learning_memories
                FROM gigi_memories
                WHERE metadata->>'source_type' = 'shadow_learning'
                  AND status = 'active'
            """)
            learning_memories = cur.fetchone()["learning_memories"]

            # Recent corrections
            cur.execute("""
                SELECT content, confidence, reinforcement_count,
                       metadata->>'difference_type' as diff_type,
                       created_at
                FROM gigi_memories
                WHERE metadata->>'source_type' = 'shadow_learning'
                  AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_corrections = [dict(row) for row in cur.fetchall()]

            return {
                "total_drafts": total,
                "paired": paired,
                "processed": processed,
                "corrections_created": corrections,
                "avg_difference_score": round(avg_diff, 1) if avg_diff else None,
                "active_learning_memories": learning_memories,
                "recent_corrections": recent_corrections
            }
    finally:
        conn.close()


def backfill_from_rc_history(days_back: int = 7) -> Dict[str, Any]:
    """
    One-time backfill: Pull SMS history from RC and create draft records
    for messages that were handled during shadow mode.

    This allows the learning pipeline to analyze historical data.
    """
    import requests

    access_token = _get_rc_access_token()
    if not access_token:
        return {"error": "No RC access token"}

    since = datetime.utcnow() - timedelta(days=days_back)
    date_from = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Fetch inbound SMS
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"

    inbound = []
    outbound = []

    for direction in ["Inbound", "Outbound"]:
        params = {
            "messageType": "SMS",
            "direction": direction,
            "dateFrom": date_from,
            "perPage": 250
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 200:
                records = resp.json().get("records", [])
                for r in records:
                    entry = {
                        "phone": (r.get("from", {}).get("phoneNumber", "")
                                 if direction == "Inbound"
                                 else [t.get("phoneNumber", "") for t in r.get("to", [])]),
                        "text": r.get("subject", ""),
                        "time": r.get("creationTime", ""),
                        "direction": direction
                    }
                    if direction == "Inbound":
                        inbound.append(entry)
                    else:
                        outbound.append(entry)
        except Exception as e:
            logger.error(f"RC history fetch error ({direction}): {e}")

    logger.info(f"Backfill: {len(inbound)} inbound, {len(outbound)} outbound SMS")
    return {
        "inbound_fetched": len(inbound),
        "outbound_fetched": len(outbound),
        "note": "Historical data fetched. Shadow drafts can only be created going forward."
    }


# CLI entry point for cron
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Load env
    env_file = os.path.expanduser("~/.gigi-env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

    logger.info("Starting Gigi Learning Pipeline...")
    results = run_learning_pipeline()

    logger.info(f"Learning pipeline complete: {json.dumps(results, indent=2)}")

    # Send Telegram notification if corrections were created
    corrections = results.get("corrections_created", 0) + results.get("corrections_reinforced", 0)
    if corrections > 0:
        try:
            import requests as req
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            if bot_token and chat_id:
                msg = (
                    f"Learning Pipeline Complete\n"
                    f"Paired: {results['paired']} drafts\n"
                    f"Analyzed: {results['analyzed']}\n"
                    f"New corrections: {results['corrections_created']}\n"
                    f"Reinforced: {results['corrections_reinforced']}\n"
                    f"Skipped (low diff): {results['skipped_low_diff']}\n"
                    f"Skipped (Gigi better): {results['skipped_gigi_better']}"
                )
                req.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg},
                    timeout=10
                )
        except Exception:
            pass

    sys.exit(0 if not results.get("errors") else 1)
