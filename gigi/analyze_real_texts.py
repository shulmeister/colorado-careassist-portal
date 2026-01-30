#!/usr/bin/env python3
"""
Analyze Real Caregiver Text Messages from RingCentral & BeeTexting

Pulls actual conversation data via APIs and tests if Gigi can handle them.
"""
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
import httpx
from collections import Counter

# API credentials
RINGCENTRAL_TOKEN = os.getenv("RINGCENTRAL_ACCESS_TOKEN")
BEETEXTING_TOKEN = os.getenv("BEETEXTING_ACCESS_TOKEN")
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "http://localhost:8000")

# Main business number
BUSINESS_NUMBER = "+17194283999"  # 719-428-3999


async def fetch_ringcentral_messages(days_back: int = 7) -> List[Dict[str, Any]]:
    """
    Fetch text messages from RingCentral API for the past N days.

    API Docs: https://developers.ringcentral.com/api-reference/SMS/listMessages
    """
    if not RINGCENTRAL_TOKEN:
        print("⚠️ RINGCENTRAL_ACCESS_TOKEN not set - skipping RingCentral")
        return []

    messages = []
    date_from = (datetime.now() - timedelta(days=days_back)).isoformat()

    print(f"\n📱 Fetching RingCentral messages from {BUSINESS_NUMBER}...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~/message-store",
                headers={
                    "Authorization": f"Bearer {RINGCENTRAL_TOKEN}",
                    "Accept": "application/json"
                },
                params={
                    "messageType": "SMS",
                    "dateFrom": date_from,
                    "perPage": 100
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("records", [])
                print(f"✅ Fetched {len(messages)} RingCentral messages")
            else:
                print(f"❌ RingCentral API error: {response.status_code}")
                print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Error fetching RingCentral messages: {e}")

    return messages


async def fetch_beetexting_messages(days_back: int = 7) -> List[Dict[str, Any]]:
    """
    Fetch text messages from BeeTexting API for the past N days.

    API Docs: Check BeeTexting dashboard for actual endpoint
    """
    if not BEETEXTING_TOKEN:
        print("⚠️ BEETEXTING_ACCESS_TOKEN not set - skipping BeeTexting")
        return []

    messages = []

    print(f"\n🐝 Fetching BeeTexting messages from {BUSINESS_NUMBER}...")

    try:
        async with httpx.AsyncClient() as client:
            # BeeTexting API endpoint (adjust based on actual API docs)
            response = await client.get(
                "https://api.beetexting.com/2.0/messages",
                headers={
                    "Authorization": f"Bearer {BEETEXTING_TOKEN}",
                    "Accept": "application/json"
                },
                params={
                    "phone_number": BUSINESS_NUMBER,
                    "days": days_back,
                    "limit": 100
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                # Adjust based on actual API response structure
                messages = data.get("messages", data.get("data", []))
                print(f"✅ Fetched {len(messages)} BeeTexting messages")
            else:
                print(f"❌ BeeTexting API error: {response.status_code}")
                print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Error fetching BeeTexting messages: {e}")

    return messages


def normalize_message(msg: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Normalize message format from different APIs"""
    if source == "ringcentral":
        return {
            "source": "ringcentral",
            "from": msg.get("from", {}).get("phoneNumber", ""),
            "to": msg.get("to", [{}])[0].get("phoneNumber", ""),
            "text": msg.get("subject", ""),
            "direction": msg.get("direction", ""),
            "timestamp": msg.get("creationTime", ""),
            "raw": msg
        }
    elif source == "beetexting":
        return {
            "source": "beetexting",
            "from": msg.get("from_number", ""),
            "to": msg.get("to_number", ""),
            "text": msg.get("message", msg.get("text", "")),
            "direction": msg.get("direction", ""),
            "timestamp": msg.get("created_at", msg.get("timestamp", "")),
            "raw": msg
        }
    return msg


async def test_gigi_can_handle(message_text: str) -> Dict[str, Any]:
    """
    Send message to Gigi's intent detection and see if she can handle it.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}/gigi/internal/analyze-sms",
                json={"message": message_text},
                timeout=10.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}

    except Exception as e:
        return {"error": str(e)}


def categorize_intent(intent: str) -> str:
    """Map intent to handling capability"""
    if intent in ("shift_accept", "shift_decline"):
        return "FULLY_HANDLED"
    elif intent in ("callout",):
        return "MOSTLY_HANDLED"
    elif intent in ("clock_out", "clock_in", "schedule", "payroll"):
        return "PARTIALLY_HANDLED"
    else:
        return "ESCALATE_TO_HUMAN"


async def analyze_conversations():
    """
    Main analysis function: Pull messages and test Gigi's handling capability
    """
    print("="*70)
    print("GIGI TEXT HANDLING ANALYSIS - REAL DATA")
    print("="*70)
    print(f"\nAnalyzing messages to/from: {BUSINESS_NUMBER}")
    print(f"Period: Last 7 days")

    # Fetch from both sources
    rc_messages = await fetch_ringcentral_messages(days_back=7)
    bt_messages = await fetch_beetexting_messages(days_back=7)

    # Normalize all messages
    all_messages = []
    all_messages.extend([normalize_message(m, "ringcentral") for m in rc_messages])
    all_messages.extend([normalize_message(m, "beetexting") for m in bt_messages])

    # Filter: Only INBOUND messages (from caregivers)
    inbound = [m for m in all_messages if m.get("direction") == "Inbound"]

    print(f"\n📊 TOTAL INBOUND TEXTS: {len(inbound)}")

    if len(inbound) == 0:
        print("\n⚠️ No inbound messages found.")
        print("\nPossible reasons:")
        print("1. API tokens not set or invalid")
        print("2. No messages in past 7 days")
        print("3. API endpoint or parameter mismatch")
        print("\nTo fix:")
        print("  export RINGCENTRAL_ACCESS_TOKEN='your_token'")
        print("  export BEETEXTING_ACCESS_TOKEN='your_token'")
        return

    # Analyze each message
    print("\n" + "="*70)
    print("MESSAGE ANALYSIS")
    print("="*70)

    results = {
        "FULLY_HANDLED": [],
        "MOSTLY_HANDLED": [],
        "PARTIALLY_HANDLED": [],
        "ESCALATE_TO_HUMAN": []
    }

    for i, msg in enumerate(inbound[:20], 1):  # Limit to first 20 for demo
        text = msg.get("text", "")
        from_number = msg.get("from", "Unknown")

        print(f"\n[{i}] From: {from_number}")
        print(f"    Text: \"{text[:80]}{'...' if len(text) > 80 else ''}\"")

        # Test with Gigi's intent detector (using local function from main.py)
        # For now, just use simple pattern matching
        intent = detect_simple_intent(text)
        category = categorize_intent(intent)

        print(f"    Intent: {intent}")
        print(f"    Handling: {category}")

        results[category].append({
            "from": from_number,
            "text": text,
            "intent": intent
        })

    # Summary statistics
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)

    total = sum(len(v) for v in results.values())

    for category, messages in results.items():
        pct = (len(messages) / total * 100) if total > 0 else 0
        emoji = {
            "FULLY_HANDLED": "✅",
            "MOSTLY_HANDLED": "⚠️",
            "PARTIALLY_HANDLED": "🔶",
            "ESCALATE_TO_HUMAN": "❌"
        }.get(category, "❓")

        print(f"\n{emoji} {category}: {len(messages)} messages ({pct:.1f}%)")

        if messages and len(messages) <= 3:
            for msg in messages:
                print(f"   - \"{msg['text'][:60]}...\"")

    # Overall capability score
    fully = len(results["FULLY_HANDLED"])
    mostly = len(results["MOSTLY_HANDLED"])
    partial = len(results["PARTIALLY_HANDLED"])
    escalate = len(results["ESCALATE_TO_HUMAN"])

    autonomous_score = ((fully * 1.0) + (mostly * 0.9) + (partial * 0.5)) / total * 100 if total > 0 else 0

    print("\n" + "="*70)
    print("FINAL SCORE")
    print("="*70)
    print(f"\n📊 Gigi can AUTONOMOUSLY handle: {autonomous_score:.1f}% of texts")
    print(f"   - Fully handled: {fully} messages")
    print(f"   - Mostly handled: {mostly} messages (minor human follow-up)")
    print(f"   - Partially handled: {partial} messages (requires coordinator)")
    print(f"   - Must escalate: {escalate} messages")

    print("\n💡 RECOMMENDATION:")
    if autonomous_score >= 90:
        print("   ✅ READY FOR FULL ZINGAGE REPLACEMENT")
    elif autonomous_score >= 70:
        print("   ⚠️ READY FOR SOFT LAUNCH (with coordinator backup)")
    elif autonomous_score >= 50:
        print("   🔶 NEEDS IMPROVEMENT (2-3 weeks development)")
    else:
        print("   ❌ NOT READY (significant gaps remain)")

    # Save results to file
    output_file = f"gigi_text_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump({
            "total_messages": total,
            "autonomous_score": autonomous_score,
            "breakdown": {k: len(v) for k, v in results.items()},
            "sample_messages": {k: v[:5] for k, v in results.items()}  # Save first 5 of each
        }, f, indent=2)

    print(f"\n📄 Full results saved to: {output_file}")


def detect_simple_intent(message: str) -> str:
    """
    Simple intent detection (mirrors gigi/main.py logic)
    """
    msg_lower = message.lower().strip()

    # Shift acceptance
    if msg_lower in ["yes", "yes!", "yep", "yeah", "yea", "y", "sure", "ok", "okay"]:
        return "shift_accept"
    if any(phrase in msg_lower for phrase in ["yes i can", "i'll take it", "i can take it"]):
        return "shift_accept"

    # Shift decline
    if msg_lower in ["no", "no!", "nope", "n", "can't", "cant", "pass"]:
        return "shift_decline"
    if any(phrase in msg_lower for phrase in ["no i can't", "not available", "sorry no"]):
        return "shift_decline"

    # Call out
    if any(phrase in msg_lower for phrase in [
        "call out", "callout", "can't make it", "sick", "emergency",
        "not going to be able to work", "can't come in", "need to cancel"
    ]):
        return "callout"

    # Clock issues
    if any(phrase in msg_lower for phrase in ["clock out", "clock in", "forgot to clock"]):
        return "clock_out"

    # Schedule
    if any(phrase in msg_lower for phrase in ["my schedule", "when do i work", "what shifts"]):
        return "schedule"

    # Payroll
    if any(phrase in msg_lower for phrase in ["pay stub", "paycheck", "paid", "payroll"]):
        return "payroll"

    return "general"


if __name__ == "__main__":
    print("\n" + "="*70)
    print("REAL TEXT MESSAGE ANALYSIS")
    print("="*70)
    print("\nThis script will:")
    print("1. Pull actual texts from RingCentral & BeeTexting")
    print("2. Test each one against Gigi's intent detection")
    print("3. Score her ability to handle real caregiver messages")
    print("\nRequired environment variables:")
    print("  - RINGCENTRAL_ACCESS_TOKEN")
    print("  - BEETEXTING_ACCESS_TOKEN")

    input("\nPress ENTER to start analysis...")

    asyncio.run(analyze_conversations())
