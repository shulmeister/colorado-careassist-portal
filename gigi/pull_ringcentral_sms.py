#!/usr/bin/env python3
"""
Pull Real SMS Messages from RingCentral API
Show exactly what texts Gigi needs to handle
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from collections import Counter

# RingCentral credentials from env vars
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID", "")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET", "")
RINGCENTRAL_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN", "")
RINGCENTRAL_SERVER = "https://platform.ringcentral.com"


def get_access_token():
    """Get RingCentral OAuth access token using JWT"""
    print("🔐 Authenticating with RingCentral...")

    try:
        response = requests.post(
            f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": RINGCENTRAL_JWT_TOKEN
            },
            auth=(RINGCENTRAL_CLIENT_ID, RINGCENTRAL_CLIENT_SECRET),
            timeout=30
        )

        if response.status_code == 200:
            token_data = response.json()
            print("✅ Authenticated successfully")
            return token_data["access_token"]
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(response.text)
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def fetch_sms_messages(access_token, days_back=14):
    """Fetch SMS messages from RingCentral"""
    print(f"\n📱 Fetching SMS messages from last {days_back} days...")

    date_from = (datetime.now() - timedelta(days=days_back)).isoformat()

    try:
        response = requests.get(
            f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={
                "messageType": "SMS",
                "dateFrom": date_from,
                "perPage": 100,
                "page": 1
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            messages = data.get("records", [])
            print(f"✅ Found {len(messages)} SMS messages")
            return messages
        else:
            print(f"❌ Failed to fetch messages: {response.status_code}")
            print(response.text)
            return []

    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        return []


def detect_intent(message_text):
    """Detect intent using same logic as Gigi"""
    msg_lower = message_text.lower().strip()

    # Shift acceptance
    if msg_lower in ["yes", "yes!", "yep", "yeah", "yea", "y", "sure", "ok", "okay"]:
        return "shift_accept"
    if any(phrase in msg_lower for phrase in [
        "yes i can", "i'll take it", "i can take it", "i can do it", "im available"
    ]):
        return "shift_accept"

    # Shift decline
    if msg_lower in ["no", "no!", "nope", "n", "can't", "cant", "pass"]:
        return "shift_decline"
    if any(phrase in msg_lower for phrase in ["no i can't", "not available", "sorry no"]):
        return "shift_decline"

    # Call out - CHECK FOR PARTIAL AVAILABILITY FIRST
    if any(phrase in msg_lower for phrase in ["could do", "can do", "available from", "available until"]):
        return "callout_partial_availability"  # NEW: Different from simple callout

    # Simple call out
    if any(phrase in msg_lower for phrase in [
        "call out", "callout", "can't make it", "sick", "emergency",
        "not going to be able to work", "can't come in", "need to cancel",
        "won't make it", "wont make it"
    ]):
        return "callout"

    # Clock issues
    if any(phrase in msg_lower for phrase in ["clock out", "clock in", "forgot to clock"]):
        return "clock_issue"

    # Schedule
    if any(phrase in msg_lower for phrase in ["my schedule", "when do i work", "what shifts"]):
        return "schedule"

    # Payroll
    if any(phrase in msg_lower for phrase in ["pay stub", "paycheck", "paid", "payroll"]):
        return "payroll"

    return "general"


def categorize_handling(intent):
    """Determine if Gigi can handle this"""
    if intent in ("shift_accept", "shift_decline"):
        return "✅ FULLY_HANDLED"
    elif intent == "callout":
        return "⚠️ MOSTLY_HANDLED"
    elif intent == "callout_partial_availability":
        return "❌ NEEDS_FIX"  # This is the gap!
    elif intent in ("clock_issue", "schedule", "payroll"):
        return "🔶 PARTIAL"
    else:
        return "❓ ESCALATE"


def analyze_messages(messages):
    """Analyze all messages and show what Gigi can/can't handle"""
    print("\n" + "="*80)
    print("ANALYZING CAREGIVER TEXT MESSAGES")
    print("="*80)

    # Filter to inbound only (from caregivers)
    inbound = [m for m in messages if m.get("direction") == "Inbound"]
    print(f"\n📊 Total inbound messages (from caregivers): {len(inbound)}")

    if len(inbound) == 0:
        print("\n⚠️ No inbound messages found in this period")
        return

    # Analyze each message
    results = {
        "✅ FULLY_HANDLED": [],
        "⚠️ MOSTLY_HANDLED": [],
        "❌ NEEDS_FIX": [],
        "🔶 PARTIAL": [],
        "❓ ESCALATE": []
    }

    intent_counts = Counter()

    print("\n" + "="*80)
    print("MESSAGE BREAKDOWN")
    print("="*80)

    for i, msg in enumerate(inbound[:30], 1):  # Show first 30
        text = msg.get("subject", "")
        from_num = msg.get("from", {}).get("phoneNumber", "Unknown")
        timestamp = msg.get("creationTime", "")

        if not text:
            continue

        intent = detect_intent(text)
        category = categorize_handling(intent)
        intent_counts[intent] += 1

        print(f"\n[{i}] {timestamp[:10]}")
        print(f"    From: {from_num}")
        print(f"    Text: \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
        print(f"    Intent: {intent}")
        print(f"    {category}")

        results[category].append({
            "from": from_num,
            "text": text,
            "intent": intent,
            "timestamp": timestamp
        })

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total = len(inbound)

    for category, msgs in results.items():
        count = len(msgs)
        pct = (count / total * 100) if total > 0 else 0
        print(f"\n{category}: {count} messages ({pct:.1f}%)")

        if count > 0 and count <= 3:
            for msg in msgs:
                print(f"   • \"{msg['text'][:60]}...\"")

    # Intent breakdown
    print("\n" + "="*80)
    print("INTENT BREAKDOWN")
    print("="*80)

    for intent, count in intent_counts.most_common():
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {intent:30} {count:3} ({pct:5.1f}%)")

    # Calculate autonomous score
    fully = len(results["✅ FULLY_HANDLED"])
    mostly = len(results["⚠️ MOSTLY_HANDLED"])
    partial = len(results["🔶 PARTIAL"])
    needs_fix = len(results["❌ NEEDS_FIX"])
    escalate = len(results["❓ ESCALATE"])

    autonomous_score = ((fully * 1.0) + (mostly * 0.9) + (partial * 0.5)) / total * 100 if total > 0 else 0

    print("\n" + "="*80)
    print("GIGI CAPABILITY SCORE")
    print("="*80)
    print(f"\n🎯 Current: {autonomous_score:.1f}% autonomous handling")
    print(f"\n   ✅ Fully handled: {fully}")
    print(f"   ⚠️ Mostly handled: {mostly}")
    print(f"   🔶 Partial: {partial}")
    print(f"   ❌ NEEDS FIX: {needs_fix} ← CRITICAL GAP")
    print(f"   ❓ Escalate: {escalate}")

    # Show examples of the NEEDS_FIX category
    if results["❌ NEEDS_FIX"]:
        print("\n" + "="*80)
        print("🚨 MESSAGES THAT NEED THE PARTIAL AVAILABILITY FIX")
        print("="*80)
        for msg in results["❌ NEEDS_FIX"][:5]:
            print(f"\n• \"{msg['text']}\"")
            print(f"  Problem: Offers alternative time, but Gigi treats as simple callout")

    # Save to file
    output_file = f"ringcentral_sms_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump({
            "total_messages": total,
            "autonomous_score": autonomous_score,
            "breakdown": {k: len(v) for k, v in results.items()},
            "intent_counts": dict(intent_counts),
            "sample_messages": {k: v[:10] for k, v in results.items()}
        }, f, indent=2)

    print(f"\n📄 Full results saved to: {output_file}")

    return autonomous_score, results


def main():
    print("="*80)
    print("REAL TEXT MESSAGE ANALYSIS - RINGCENTRAL DATA")
    print("="*80)
    print("\nPulling actual caregiver texts from 719-428-3999...")

    # Authenticate
    access_token = get_access_token()
    if not access_token:
        print("\n❌ Failed to authenticate")
        sys.exit(1)

    # Fetch messages
    messages = fetch_sms_messages(access_token, days_back=14)
    if not messages:
        print("\n❌ No messages found")
        sys.exit(1)

    # Analyze
    score, results = analyze_messages(messages)

    # Final recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    if score >= 90:
        print("\n✅ READY FOR FULL CORE PERFORMANCE")
        print("   Gigi can handle 90%+ of texts autonomously")
    elif score >= 70:
        print("\n⚠️ READY FOR SOFT LAUNCH")
        print("   Gigi handles most texts, but keep coordinator backup for complex cases")
        print("   Build the partial availability parser (2-3 days) to reach 95%+")
    else:
        print("\n❌ NEEDS DEVELOPMENT")
        print("   Significant gaps remain. Recommend 2-4 weeks development before launch.")

    print("\n")


if __name__ == "__main__":
    main()
