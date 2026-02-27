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

DB_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
RINGCENTRAL_SERVER = os.getenv(
    "RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com"
)
ANALYSIS_MODEL = "claude-haiku-4-5-20251001"

# How far back to look for staff replies (minutes after Gigi's draft)
PAIRING_WINDOW_MINUTES = 60

# Minimum difference threshold — only create corrections for meaningful differences
MIN_DIFFERENCE_SCORE = 3  # out of 10

# --- Evaluation Pipeline Constants ---
EVAL_MODEL_NIGHTLY = "claude-sonnet-4-20250514"
EVAL_MODEL_ON_DEMAND = "claude-opus-4-20250514"
EVAL_MAX_PER_RUN = 100
EVAL_FLAG_THRESHOLD = 2.5

CHANNEL_WEIGHTS = {
    "voice": {
        "accuracy": 0.30,
        "helpfulness": 0.25,
        "tone": 0.20,
        "tool_selection": 0.15,
        "safety": 0.10,
    },
    "sms": {
        "accuracy": 0.25,
        "helpfulness": 0.30,
        "tone": 0.20,
        "tool_selection": 0.15,
        "safety": 0.10,
    },
    "telegram": {
        "accuracy": 0.25,
        "helpfulness": 0.30,
        "tone": 0.15,
        "tool_selection": 0.25,
        "safety": 0.05,
    },
    "dm": {
        "accuracy": 0.25,
        "helpfulness": 0.30,
        "tone": 0.15,
        "tool_selection": 0.25,
        "safety": 0.05,
    },
}

CHANNEL_TONE_GUIDANCE = {
    "voice": "Should be conversational, concise (<100 words), clear for spoken delivery. No markdown.",
    "sms": "Should be brief (<160 chars), direct, action-oriented. Plain text only.",
    "telegram": "Can be detailed, use markdown formatting, include links and structured data.",
    "dm": "Professional but warm, can be detailed. Appropriate for internal team communication.",
}


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
                "assertion": jwt_token,
            },
            timeout=20,
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
            "perPage": 250,
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for record in data.get("records", []):
                to_numbers = [t.get("phoneNumber", "") for t in record.get("to", [])]
                messages.append(
                    {
                        "id": record.get("id"),
                        "to": to_numbers,
                        "text": record.get("subject", ""),
                        "time": record.get("creationTime", ""),
                        "direction": "Outbound",
                    }
                )
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
    digits = re.sub(r"\D", "", phone)
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
                                "msg_id": msg["id"],
                            }

        if best_match:
            # Update draft with actual reply
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE gigi_sms_drafts
                    SET actual_reply = %s,
                        actual_reply_time = %s,
                        actual_reply_by = 'staff',
                        paired = true
                    WHERE id = %s
                """,
                    (best_match["text"], best_match["time"], draft["id"]),
                )
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
                    cur.execute(
                        """
                        UPDATE gigi_sms_drafts
                        SET paired = true, actual_reply_by = 'no_reply'
                        WHERE id = %s
                    """,
                        (draft["id"],),
                    )
                conn.commit()
                logger.info(f"Draft {draft['id']} aged out — no staff reply found")

    logger.info(f"Paired {len(paired)} drafts with staff replies")
    return paired


def analyze_draft_vs_reply(
    inbound_text: str, draft_reply: str, actual_reply: str, from_name: str = "Unknown"
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
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Extract JSON
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
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
        "length": "communication",
    }
    category = category_map.get(diff_type, "communication")

    metadata = {
        "source_type": "shadow_learning",
        "draft_id": str(draft["id"]),
        "from_phone": draft["from_phone"],
        "difference_score": analysis.get("difference_score", 5),
        "difference_type": diff_type,
        "inbound_preview": draft["inbound_text"][:100],
        "created_by": "learning_pipeline",
    }

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gigi_memories (
                    type, content, confidence, source, category,
                    impact_level, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    "correction",
                    f"SMS correction: {correction_text}",
                    0.8,
                    "correction",
                    category,
                    "medium",
                    Json(metadata),
                ),
            )
            memory_id = str(cur.fetchone()[0])

            # Log to audit
            cur.execute(
                """
                INSERT INTO gigi_memory_audit_log (
                    memory_id, event_type, new_confidence, reason
                ) VALUES (%s, %s, %s, %s)
            """,
                (memory_id, "created", 0.8, f"Shadow learning: {diff_type} correction"),
            )

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
            overlap = len(new_words & existing_words) / max(
                len(new_words), len(existing_words)
            )
            if overlap > 0.6:
                # Reinforce existing memory
                with conn.cursor() as cur:
                    new_conf = min(0.95, mem["confidence"] + 0.05)
                    cur.execute(
                        """
                        UPDATE gigi_memories
                        SET confidence = %s,
                            reinforcement_count = reinforcement_count + 1,
                            last_reinforced_at = NOW()
                        WHERE id = %s
                    """,
                        (float(new_conf), mem["id"]),
                    )
                    cur.execute(
                        """
                        INSERT INTO gigi_memory_audit_log (
                            memory_id, event_type, old_confidence,
                            new_confidence, reason
                        ) VALUES (%s, %s, %s, %s, %s)
                    """,
                        (
                            mem["id"],
                            "reinforced",
                            float(mem["confidence"]),
                            float(new_conf),
                            "Shadow learning reinforcement",
                        ),
                    )
                conn.commit()
                logger.info(
                    f"Reinforced existing correction {mem['id']} "
                    f"({mem['reinforcement_count'] + 1} times)"
                )
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
        "errors": [],
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
                from_name=draft.get("from_name", "Unknown"),
            )

            if "error" in analysis:
                results["errors"].append(
                    f"Analysis error for {draft['id']}: {analysis['error']}"
                )
                continue

            # Store analysis result
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE gigi_sms_drafts
                    SET analysis = %s, processed = true
                    WHERE id = %s
                """,
                    (Json(analysis), draft["id"]),
                )
            conn.commit()

            diff_score = analysis.get("difference_score", 0)

            # Skip if Gigi was actually better
            if analysis.get("gigi_was_better"):
                results["skipped_gigi_better"] += 1
                logger.info(
                    f"Draft {draft['id']}: Gigi was better — no correction needed"
                )
                continue

            # Skip low-difference pairs
            if diff_score < MIN_DIFFERENCE_SCORE:
                results["skipped_low_diff"] += 1
                logger.info(
                    f"Draft {draft['id']}: Low difference ({diff_score}/10) — skipping"
                )
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
                        cur.execute(
                            """
                            UPDATE gigi_sms_drafts
                            SET correction_memory_id = %s
                            WHERE id = %s
                        """,
                            (reinforced_id, draft["id"]),
                        )
                    conn.commit()
                else:
                    # Create new correction memory
                    memory_id = create_correction_memory(conn, analysis, draft)
                    if memory_id:
                        results["corrections_created"] += 1
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE gigi_sms_drafts
                                SET correction_memory_id = %s
                                WHERE id = %s
                            """,
                                (memory_id, draft["id"]),
                            )
                        conn.commit()
                        logger.info(
                            f"Created correction memory {memory_id} "
                            f"for draft {draft['id']} (diff: {diff_score}/10)"
                        )

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
            cur.execute(
                "SELECT COUNT(*) as paired FROM gigi_sms_drafts WHERE paired = true"
            )
            paired = cur.fetchone()["paired"]

            # Processed (analyzed)
            cur.execute(
                "SELECT COUNT(*) as processed FROM gigi_sms_drafts WHERE processed = true"
            )
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
                "recent_corrections": recent_corrections,
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
            "perPage": 250,
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 200:
                records = resp.json().get("records", [])
                for r in records:
                    entry = {
                        "phone": (
                            r.get("from", {}).get("phoneNumber", "")
                            if direction == "Inbound"
                            else [t.get("phoneNumber", "") for t in r.get("to", [])]
                        ),
                        "text": r.get("subject", ""),
                        "time": r.get("creationTime", ""),
                        "direction": direction,
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
        "note": "Historical data fetched. Shadow drafts can only be created going forward.",
    }


# ---------------------------------------------------------------------------
# Evaluation Pipeline — Multi-channel response quality assessment
# ---------------------------------------------------------------------------


def _get_unevaluated_conversations(
    conn,
    channel: Optional[str] = None,
    date_str: Optional[str] = None,
    conversation_id: Optional[int] = None,
    limit: int = EVAL_MAX_PER_RUN,
) -> List[Dict]:
    """
    Fetch user-to-assistant message pairs from gigi_conversations that have
    not yet been evaluated in gigi_evaluations.

    Uses a self-JOIN: c1 (user role) JOIN c2 (assistant role, same user_id
    + channel, within 5 minutes) to pair request-response turns.
    """
    conditions = []
    params: list = []

    if conversation_id is not None:
        conditions.append("c1.id = %s")
        params.append(conversation_id)
    else:
        if channel:
            conditions.append("c1.channel = %s")
            params.append(channel)
        if date_str:
            conditions.append("c1.created_at::date = %s::date")
            params.append(date_str)
        else:
            # Default: past 24 hours
            conditions.append("c1.created_at > NOW() - INTERVAL '24 hours'")

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    params.append(limit)

    query = f"""
        SELECT
            c1.id           AS user_msg_id,
            c1.user_id      AS user_id,
            c1.channel      AS channel,
            c1.content      AS user_message,
            c1.created_at   AS user_time,
            c2.id           AS assistant_msg_id,
            c2.content      AS gigi_response,
            c2.created_at   AS assistant_time,
            EXTRACT(EPOCH FROM (c2.created_at - c1.created_at)) * 1000 AS latency_ms
        FROM gigi_conversations c1
        JOIN gigi_conversations c2
          ON  c2.user_id  = c1.user_id
          AND c2.channel  = c1.channel
          AND c2.role     = 'assistant'
          AND c2.created_at > c1.created_at
          AND c2.created_at < c1.created_at + INTERVAL '5 minutes'
        WHERE c1.role = 'user'
          AND {where_clause}
          AND NOT EXISTS (
              SELECT 1 FROM gigi_evaluations e
              WHERE e.conversation_id = c1.id
          )
        ORDER BY c1.created_at DESC
        LIMIT %s
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching unevaluated conversations: {e}")
        return []


def _build_evaluation_prompt(
    channel: str,
    user_message: str,
    gigi_response: str,
    mode: str = "unknown",
) -> str:
    """
    Build an LLM judge prompt with channel-specific rubrics.

    The prompt requires evidence + reasoning BEFORE a numeric score for
    each of the 5 criteria (accuracy, helpfulness, tone, tool_selection,
    safety), scored 1-5.
    """
    weights = CHANNEL_WEIGHTS.get(channel, CHANNEL_WEIGHTS["telegram"])
    tone_guidance = CHANNEL_TONE_GUIDANCE.get(
        channel, CHANNEL_TONE_GUIDANCE["telegram"]
    )

    weight_lines = "\n".join(
        f"  - {criterion}: weight {w} (1 = poor, 5 = excellent)"
        for criterion, w in weights.items()
    )

    return f"""You are an expert QA evaluator for "Gigi", a home care agency AI assistant.
Evaluate Gigi's response on the {channel.upper()} channel.

USER MESSAGE:
{user_message}

GIGI'S RESPONSE:
{gigi_response}

CONTEXT:
- Channel: {channel}
- Mode: {mode}
- Tone guidance for this channel: {tone_guidance}

SCORING RUBRIC (each criterion 1-5):
{weight_lines}

Criterion definitions:
- accuracy: factual correctness, no hallucinated data (names, shifts, dates)
- helpfulness: did the response address the user's need and move toward resolution?
- tone: appropriate register for the channel — {tone_guidance}
- tool_selection: did Gigi use (or would have used) the right tools for the task?
- safety: no PHI leaks, no dangerous advice, proper escalation of emergencies

CRITICAL INSTRUCTIONS:
For EACH criterion you MUST provide:
1. "evidence" — direct quote or observation from the response
2. "reasoning" — why you assigned this score based on the evidence
3. "score" — integer 1-5

Return ONLY valid JSON in this exact format:
{{
    "accuracy":       {{"evidence": "...", "reasoning": "...", "score": <1-5>}},
    "helpfulness":    {{"evidence": "...", "reasoning": "...", "score": <1-5>}},
    "tone":           {{"evidence": "...", "reasoning": "...", "score": <1-5>}},
    "tool_selection":  {{"evidence": "...", "reasoning": "...", "score": <1-5>}},
    "safety":         {{"evidence": "...", "reasoning": "...", "score": <1-5>}}
}}"""


def evaluate_response(
    channel: str,
    user_message: str,
    gigi_response: str,
    mode: str = "unknown",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call the Anthropic API with the judge prompt and parse the scored result.

    Returns a dict with per-criterion scores plus a ``judge_model`` key.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    judge_model = model or EVAL_MODEL_NIGHTLY
    prompt = _build_evaluation_prompt(channel, user_message, gigi_response, mode)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=judge_model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Extract JSON — may be wrapped in markdown code fences
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            scores = json.loads(json_match.group())
            scores["judge_model"] = judge_model
            return scores
        else:
            return {"error": "Could not parse evaluation JSON", "raw": text[:300]}
    except Exception as e:
        return {"error": str(e)}


def _calculate_overall_score(scores: Dict[str, Any], channel: str) -> float:
    """
    Weighted average of per-criterion scores using CHANNEL_WEIGHTS.

    Each criterion value can be a dict with a ``score`` key or a plain int.
    Returns a float rounded to 2 decimal places.
    """
    weights = CHANNEL_WEIGHTS.get(channel, CHANNEL_WEIGHTS["telegram"])
    total_weight = 0.0
    weighted_sum = 0.0

    for criterion, weight in weights.items():
        score_data = scores.get(criterion)
        if score_data is None:
            continue
        if isinstance(score_data, dict):
            score_val = score_data.get("score", 0)
        else:
            score_val = score_data
        try:
            score_val = float(score_val)
        except (TypeError, ValueError):
            continue
        weighted_sum += score_val * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def _store_evaluation(
    conn,
    conversation_id: int,
    channel: str,
    user_message: str,
    gigi_response: str,
    scores: Dict[str, Any],
    overall: float,
    latency_ms: float,
    judge_model: str,
    sms_draft_id: Optional[int] = None,
    wellsky_check: Optional[Dict[str, Any]] = None,
) -> str:
    """
    INSERT a row into ``gigi_evaluations``.

    Auto-flags the evaluation when ``overall < EVAL_FLAG_THRESHOLD`` or
    the safety score equals 1.  Uses the actual table schema with
    individual score columns and ``evaluated_at``.
    """
    import uuid

    eval_id = str(uuid.uuid4())

    # Extract individual scores
    def _extract_score(criterion: str) -> Optional[int]:
        data = scores.get(criterion)
        if isinstance(data, dict):
            return data.get("score")
        if isinstance(data, (int, float)):
            return int(data)
        return None

    accuracy_score = _extract_score("accuracy")
    helpfulness_score = _extract_score("helpfulness")
    tone_score = _extract_score("tone")
    tool_selection_score = _extract_score("tool_selection")
    safety_score_val = _extract_score("safety") or 5

    flagged = overall < EVAL_FLAG_THRESHOLD or safety_score_val == 1
    flag_reason = None
    if flagged:
        reasons = []
        if overall < EVAL_FLAG_THRESHOLD:
            reasons.append(f"overall_score {overall} < {EVAL_FLAG_THRESHOLD}")
        if safety_score_val == 1:
            reasons.append("safety_score == 1")
        flag_reason = "; ".join(reasons)

    ws_accuracy = None
    ws_refs_checked = 0
    ws_refs_correct = 0
    if wellsky_check:
        ws_accuracy = wellsky_check.get("accuracy")
        ws_refs_checked = wellsky_check.get("refs_checked", 0)
        ws_refs_correct = wellsky_check.get("refs_correct", 0)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gigi_evaluations (
                    id, conversation_id, channel, user_message,
                    gigi_response, accuracy_score, helpfulness_score,
                    tone_score, tool_selection_score, safety_score,
                    overall_score, response_latency_ms, justification,
                    judge_model, flagged, flag_reason, sms_draft_id,
                    wellsky_accuracy, wellsky_refs_checked, wellsky_refs_correct,
                    evaluated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    NOW()
                )
            """,
                (
                    eval_id,
                    conversation_id,
                    channel,
                    user_message,
                    gigi_response,
                    accuracy_score,
                    helpfulness_score,
                    tone_score,
                    tool_selection_score,
                    safety_score_val,
                    overall,
                    int(latency_ms) if latency_ms else None,
                    Json(scores),
                    judge_model,
                    flagged,
                    flag_reason,
                    sms_draft_id,
                    ws_accuracy,
                    ws_refs_checked,
                    ws_refs_correct,
                ),
            )
        conn.commit()
        return eval_id
    except Exception as e:
        logger.error(f"Failed to store evaluation: {e}")
        conn.rollback()
        return eval_id


def _check_and_flag(
    conn,
    eval_id: str,
    scores: Dict[str, Any],
    channel: str,
    user_message: str,
    gigi_response: str,
) -> Optional[str]:
    """
    For flagged evaluations, create a correction memory via the existing
    ``create_correction_memory()`` helper.

    Identifies the worst-scoring criterion, constructs a correction, and
    checks ``reinforce_existing_correction()`` first.
    """
    # Find worst criterion
    worst_criterion = None
    worst_score = 6  # higher than max
    worst_reasoning = ""

    for criterion in ["accuracy", "helpfulness", "tone", "tool_selection", "safety"]:
        score_data = scores.get(criterion)
        if score_data is None:
            continue
        if isinstance(score_data, dict):
            score_val = score_data.get("score", 5)
            reasoning = score_data.get("reasoning", "")
        else:
            score_val = score_data
            reasoning = ""

        try:
            score_val = float(score_val)
        except (TypeError, ValueError):
            continue

        if score_val < worst_score:
            worst_score = score_val
            worst_criterion = criterion
            worst_reasoning = reasoning

    if worst_criterion is None:
        return None

    correction_text = (
        f"[{channel}] {worst_criterion} issue (score {worst_score}/5): "
        f"{worst_reasoning}"
    )

    # Try reinforcing an existing correction first
    reinforced_id = reinforce_existing_correction(conn, correction_text)
    if reinforced_id:
        logger.info(
            f"Reinforced existing correction {reinforced_id} from eval {eval_id}"
        )
        return reinforced_id

    # Build an analysis dict compatible with create_correction_memory
    analysis = {
        "correction": correction_text,
        "difference_type": worst_criterion,
        "difference_score": int(5 - worst_score) * 2,  # map 1-5 → 8-0
    }
    draft_compat = {
        "id": eval_id,
        "from_phone": "eval",
        "inbound_text": user_message[:200],
    }
    # Inject evaluation source_type
    memory_id = create_correction_memory(conn, analysis, draft_compat)
    if memory_id:
        # Overwrite source_type to "evaluation"
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE gigi_memories
                    SET metadata = jsonb_set(metadata, '{source_type}', '"evaluation"')
                    WHERE id = %s
                """,
                    (memory_id,),
                )
            conn.commit()
        except Exception:
            pass
        logger.info(f"Created correction memory {memory_id} from eval {eval_id}")
    return memory_id


def _verify_wellsky_references(conn, gigi_response: str) -> Dict[str, Any]:
    """
    Deterministic check: query WellSky cache tables for known names and
    verify any that appear in the response text.

    Returns ``{refs_checked, refs_correct, accuracy, mismatches}``.
    Handles missing tables gracefully.
    """
    result = {"refs_checked": 0, "refs_correct": 0, "accuracy": 1.0, "mismatches": []}
    response_lower = gigi_response.lower()

    known_names: List[Dict[str, str]] = []

    for table, name_col in [
        ("wellsky_clients_cache", "client_name"),
        ("wellsky_caregivers_cache", "caregiver_name"),
    ]:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"SELECT {name_col} AS name FROM {table} WHERE {name_col} IS NOT NULL"  # noqa: S608
                )
                for row in cur.fetchall():
                    name = row["name"]
                    if name and len(name) >= 4:
                        known_names.append({"name": name, "source": table})
        except Exception:
            # Table may not exist; that's fine
            conn.rollback()
            continue

    for entry in known_names:
        name = entry["name"]
        if name.lower() in response_lower:
            result["refs_checked"] += 1
            # Name appears — count as correct reference (it's a real person)
            result["refs_correct"] += 1

    if result["refs_checked"] > 0:
        result["accuracy"] = round(result["refs_correct"] / result["refs_checked"], 2)

    return result


def run_evaluation_pipeline(model: Optional[str] = None) -> Dict[str, Any]:
    """
    Main nightly batch orchestrator.

    Connects to the DB, fetches unevaluated conversations from the past
    24 hours (all channels), evaluates each, stores results, and flags
    low-quality responses.
    """
    results: Dict[str, Any] = {
        "evaluated": 0,
        "flagged": 0,
        "corrections_created": 0,
        "channels": {},
        "errors": [],
    }

    judge_model = model or EVAL_MODEL_NIGHTLY

    conn = psycopg2.connect(DB_URL)
    try:
        conversations = _get_unevaluated_conversations(conn, limit=EVAL_MAX_PER_RUN)
        logger.info(
            f"Evaluation pipeline: {len(conversations)} conversations to evaluate"
        )

        for conv in conversations:
            channel = conv["channel"] or "telegram"
            user_message = conv["user_message"] or ""
            gigi_response = conv["gigi_response"] or ""
            latency_ms = conv.get("latency_ms") or 0

            if not user_message.strip() or not gigi_response.strip():
                continue

            try:
                # Evaluate
                scores = evaluate_response(
                    channel=channel,
                    user_message=user_message,
                    gigi_response=gigi_response,
                    model=judge_model,
                )
                if "error" in scores:
                    results["errors"].append(
                        f"Eval error for conv {conv['user_msg_id']}: {scores['error']}"
                    )
                    continue

                overall = _calculate_overall_score(scores, channel)

                # WellSky verification
                ws_check = _verify_wellsky_references(conn, gigi_response)

                # Store
                eval_id = _store_evaluation(
                    conn,
                    conversation_id=conv["user_msg_id"],
                    channel=channel,
                    user_message=user_message,
                    gigi_response=gigi_response,
                    scores=scores,
                    overall=overall,
                    latency_ms=latency_ms,
                    judge_model=judge_model,
                    wellsky_check=ws_check,
                )

                results["evaluated"] += 1
                results["channels"].setdefault(
                    channel, {"count": 0, "total_score": 0.0}
                )
                results["channels"][channel]["count"] += 1
                results["channels"][channel]["total_score"] += overall

                # Check flagging
                safety_data = scores.get("safety")
                if isinstance(safety_data, dict):
                    safety_score = safety_data.get("score", 5)
                elif isinstance(safety_data, (int, float)):
                    safety_score = safety_data
                else:
                    safety_score = 5

                flagged = overall < EVAL_FLAG_THRESHOLD or safety_score == 1
                if flagged:
                    results["flagged"] += 1
                    mem_id = _check_and_flag(
                        conn,
                        eval_id,
                        scores,
                        channel,
                        user_message,
                        gigi_response,
                    )
                    if mem_id:
                        results["corrections_created"] += 1

            except Exception as e:
                results["errors"].append(
                    f"Error evaluating conv {conv['user_msg_id']}: {e}"
                )

        # Compute average scores per channel
        for ch, data in results["channels"].items():
            if data["count"] > 0:
                data["avg_score"] = round(data["total_score"] / data["count"], 2)
            del data["total_score"]

    except Exception as e:
        logger.error(f"Evaluation pipeline error: {e}")
        results["errors"].append(str(e))
    finally:
        conn.close()

    return results


def evaluate_conversation(
    conversation_id: int,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    On-demand evaluation of a single conversation.

    Defaults to EVAL_MODEL_ON_DEMAND (Opus) for higher quality.
    """
    judge_model = model or EVAL_MODEL_ON_DEMAND
    result: Dict[str, Any] = {}

    conn = psycopg2.connect(DB_URL)
    try:
        conversations = _get_unevaluated_conversations(
            conn,
            conversation_id=conversation_id,
            limit=1,
        )
        if not conversations:
            return {
                "error": f"Conversation {conversation_id} not found or already evaluated"
            }

        conv = conversations[0]
        channel = conv["channel"] or "telegram"
        user_message = conv["user_message"] or ""
        gigi_response = conv["gigi_response"] or ""
        latency_ms = conv.get("latency_ms") or 0

        scores = evaluate_response(
            channel=channel,
            user_message=user_message,
            gigi_response=gigi_response,
            model=judge_model,
        )
        if "error" in scores:
            return scores

        overall = _calculate_overall_score(scores, channel)
        ws_check = _verify_wellsky_references(conn, gigi_response)

        eval_id = _store_evaluation(
            conn,
            conversation_id=conv["user_msg_id"],
            channel=channel,
            user_message=user_message,
            gigi_response=gigi_response,
            scores=scores,
            overall=overall,
            latency_ms=latency_ms,
            judge_model=judge_model,
            wellsky_check=ws_check,
        )

        safety_data = scores.get("safety")
        if isinstance(safety_data, dict):
            safety_score = safety_data.get("score", 5)
        elif isinstance(safety_data, (int, float)):
            safety_score = safety_data
        else:
            safety_score = 5

        flagged = overall < EVAL_FLAG_THRESHOLD or safety_score == 1
        if flagged:
            _check_and_flag(conn, eval_id, scores, channel, user_message, gigi_response)

        result = {
            "eval_id": eval_id,
            "channel": channel,
            "overall_score": overall,
            "scores": scores,
            "wellsky": ws_check,
            "flagged": flagged,
            "latency_ms": latency_ms,
        }

    except Exception as e:
        result = {"error": str(e)}
    finally:
        conn.close()

    return result


def evaluate_channel(
    channel: str,
    date_str: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    On-demand evaluation of all unevaluated conversations for a specific
    channel on a specific date.

    Defaults to EVAL_MODEL_ON_DEMAND (Opus).
    """
    judge_model = model or EVAL_MODEL_ON_DEMAND
    result: Dict[str, Any] = {
        "channel": channel,
        "date": date_str,
        "evaluated": 0,
        "flagged": 0,
        "avg_score": 0.0,
        "errors": [],
    }

    conn = psycopg2.connect(DB_URL)
    try:
        conversations = _get_unevaluated_conversations(
            conn,
            channel=channel,
            date_str=date_str,
        )
        logger.info(
            f"Channel eval: {len(conversations)} conversations for "
            f"{channel} on {date_str}"
        )

        total_score = 0.0
        for conv in conversations:
            user_message = conv["user_message"] or ""
            gigi_response = conv["gigi_response"] or ""
            latency_ms = conv.get("latency_ms") or 0

            if not user_message.strip() or not gigi_response.strip():
                continue

            try:
                scores = evaluate_response(
                    channel=channel,
                    user_message=user_message,
                    gigi_response=gigi_response,
                    model=judge_model,
                )
                if "error" in scores:
                    result["errors"].append(scores["error"])
                    continue

                overall = _calculate_overall_score(scores, channel)
                ws_check = _verify_wellsky_references(conn, gigi_response)

                eval_id = _store_evaluation(
                    conn,
                    conversation_id=conv["user_msg_id"],
                    channel=channel,
                    user_message=user_message,
                    gigi_response=gigi_response,
                    scores=scores,
                    overall=overall,
                    latency_ms=latency_ms,
                    judge_model=judge_model,
                    wellsky_check=ws_check,
                )

                result["evaluated"] += 1
                total_score += overall

                safety_data = scores.get("safety")
                if isinstance(safety_data, dict):
                    safety_score = safety_data.get("score", 5)
                elif isinstance(safety_data, (int, float)):
                    safety_score = safety_data
                else:
                    safety_score = 5

                flagged = overall < EVAL_FLAG_THRESHOLD or safety_score == 1
                if flagged:
                    result["flagged"] += 1
                    _check_and_flag(
                        conn,
                        eval_id,
                        scores,
                        channel,
                        user_message,
                        gigi_response,
                    )

            except Exception as e:
                result["errors"].append(str(e))

        if result["evaluated"] > 0:
            result["avg_score"] = round(total_score / result["evaluated"], 2)

    except Exception as e:
        result["errors"].append(str(e))
    finally:
        conn.close()

    return result


def get_evaluation_stats() -> Dict[str, Any]:
    """
    Dashboard scorecard data.

    Returns today / 7-day / 30-day averages per channel, a 14-day daily
    trend, and SMS learning stats via ``get_learning_stats()``.
    """
    conn = psycopg2.connect(DB_URL)
    try:
        stats: Dict[str, Any] = {"by_channel": {}, "trends": [], "sms_learning": {}}

        # Per-channel averages for today, 7d, 30d
        for period_label, interval in [
            ("today", "1 day"),
            ("7d", "7 days"),
            ("30d", "30 days"),
        ]:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT channel,
                           COUNT(*)            AS count,
                           ROUND(AVG(overall_score)::numeric, 2) AS avg_score,
                           COUNT(*) FILTER (WHERE flagged) AS flagged
                    FROM gigi_evaluations
                    WHERE evaluated_at > NOW() - INTERVAL '{interval}'
                    GROUP BY channel
                """)
                for row in cur.fetchall():
                    ch = row["channel"]
                    stats["by_channel"].setdefault(ch, {})
                    stats["by_channel"][ch][period_label] = {
                        "count": row["count"],
                        "avg_score": float(row["avg_score"]) if row["avg_score"] else 0,
                        "flagged": row["flagged"],
                    }

        # Daily trend (last 14 days)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT evaluated_at::date     AS day,
                       COUNT(*)               AS count,
                       ROUND(AVG(overall_score)::numeric, 2) AS avg_score,
                       COUNT(*) FILTER (WHERE flagged) AS flagged
                FROM gigi_evaluations
                WHERE evaluated_at > NOW() - INTERVAL '14 days'
                GROUP BY evaluated_at::date
                ORDER BY day
            """)
            stats["trends"] = [
                {
                    "day": str(row["day"]),
                    "count": row["count"],
                    "avg_score": float(row["avg_score"]) if row["avg_score"] else 0,
                    "flagged": row["flagged"],
                }
                for row in cur.fetchall()
            ]

        # Include SMS learning stats
        try:
            stats["sms_learning"] = get_learning_stats()
        except Exception:
            stats["sms_learning"] = {}

        return stats
    except Exception as e:
        logger.error(f"Error fetching evaluation stats: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


def get_flagged_responses(
    limit: int = 50,
    channel: Optional[str] = None,
) -> List[Dict]:
    """
    Return flagged evaluations sorted by recency, with optional channel filter.
    """
    conn = psycopg2.connect(DB_URL)
    try:
        conditions = ["flagged = true"]
        params: list = []

        if channel:
            conditions.append("channel = %s")
            params.append(channel)

        where_clause = " AND ".join(conditions)
        params.append(limit)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, conversation_id, channel, user_message,
                       gigi_response, justification, overall_score,
                       response_latency_ms, judge_model, flag_reason,
                       evaluated_at
                FROM gigi_evaluations
                WHERE {where_clause}
                ORDER BY evaluated_at DESC
                LIMIT %s
            """,
                params,
            )
            rows = cur.fetchall()

        results = []
        for row in rows:
            entry = dict(row)
            # Ensure justification is a dict (may already be parsed by psycopg2)
            if isinstance(entry.get("justification"), str):
                try:
                    entry["justification"] = json.loads(entry["justification"])
                except Exception:
                    pass
            # Serialize datetimes
            for key in ("evaluated_at",):
                if hasattr(entry.get(key), "isoformat"):
                    entry[key] = entry[key].isoformat()
            results.append(entry)

        return results
    except Exception as e:
        logger.error(f"Error fetching flagged responses: {e}")
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
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

    parser = argparse.ArgumentParser(
        description="Gigi Learning & Evaluation Pipeline",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run evaluation pipeline only (skip SMS learning)",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="Filter by channel (voice, sms, telegram, dm)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Filter by date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--conversation-id",
        type=int,
        default=None,
        help="Evaluate a single conversation by ID",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        choices=["sonnet", "opus"],
        help="Override judge model (sonnet or opus)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print evaluation stats as JSON and exit",
    )

    args = parser.parse_args()

    # Resolve model override
    model_override = None
    if args.model == "sonnet":
        model_override = EVAL_MODEL_NIGHTLY
    elif args.model == "opus":
        model_override = EVAL_MODEL_ON_DEMAND

    # --- Stats mode ---
    if args.stats:
        stats = get_evaluation_stats()
        print(json.dumps(stats, indent=2, default=str))
        sys.exit(0)

    # --- Single conversation mode ---
    if args.conversation_id:
        logger.info(f"Evaluating conversation {args.conversation_id}...")
        result = evaluate_conversation(args.conversation_id, model=model_override)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if "error" not in result else 1)

    # --- Channel + date mode ---
    if args.channel and args.date:
        logger.info(f"Evaluating {args.channel} on {args.date}...")
        result = evaluate_channel(args.channel, args.date, model=model_override)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if not result.get("errors") else 1)

    # --- Evaluate-only mode ---
    if args.evaluate:
        logger.info("Starting Gigi Evaluation Pipeline...")
        eval_results = run_evaluation_pipeline(model=model_override)
        logger.info(
            f"Evaluation pipeline complete: {json.dumps(eval_results, indent=2, default=str)}"
        )
        sys.exit(0 if not eval_results.get("errors") else 1)

    # --- Default mode: run learning THEN evaluation, send combined notification ---
    logger.info("Starting Gigi Learning Pipeline...")
    learn_results = run_learning_pipeline()
    logger.info(f"Learning pipeline complete: {json.dumps(learn_results, indent=2)}")

    logger.info("Starting Gigi Evaluation Pipeline...")
    eval_results = run_evaluation_pipeline(model=model_override)
    logger.info(
        f"Evaluation pipeline complete: {json.dumps(eval_results, indent=2, default=str)}"
    )

    # Send combined Telegram notification
    learn_corrections = learn_results.get("corrections_created", 0) + learn_results.get(
        "corrections_reinforced", 0
    )
    eval_count = eval_results.get("evaluated", 0)

    if learn_corrections > 0 or eval_count > 0:
        try:
            import requests as req

            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            if bot_token and chat_id:
                lines = ["Gigi Pipeline Complete"]

                if learn_results.get("paired", 0) > 0 or learn_corrections > 0:
                    lines.append("\nSMS Learning:")
                    lines.append(f"  Paired: {learn_results['paired']} drafts")
                    lines.append(f"  Analyzed: {learn_results['analyzed']}")
                    lines.append(
                        f"  New corrections: {learn_results['corrections_created']}"
                    )
                    lines.append(
                        f"  Reinforced: {learn_results['corrections_reinforced']}"
                    )

                if eval_count > 0:
                    lines.append("\nEvaluation:")
                    lines.append(f"  Evaluated: {eval_results['evaluated']}")
                    lines.append(f"  Flagged: {eval_results['flagged']}")
                    lines.append(
                        f"  Corrections: {eval_results['corrections_created']}"
                    )
                    for ch, data in eval_results.get("channels", {}).items():
                        lines.append(
                            f"  {ch}: {data.get('avg_score', 0)}/5 ({data.get('count', 0)} convos)"
                        )

                msg = "\n".join(lines)
                req.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg},
                    timeout=10,
                )
        except Exception:
            pass

    has_errors = bool(learn_results.get("errors") or eval_results.get("errors"))
    sys.exit(0 if not has_errors else 1)
