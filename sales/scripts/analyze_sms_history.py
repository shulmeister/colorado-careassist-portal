#!/usr/bin/env python3
"""
Analyze RingCentral SMS History for Shift Filling Training

Pulls SMS messages from 719-428-3999 and analyzes:
- Response patterns (how caregivers accept/decline)
- Response timing
- Common phrases and language
- Caregiver response rates
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dotenv import load_dotenv
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RingCentral credentials
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")

# Target phone number for caregiver communications
TARGET_PHONE = "7194283999"


class RingCentralSMSAnalyzer:
    def __init__(self):
        self.access_token = None
        self.messages = []

    def authenticate(self):
        """Get access token using JWT"""
        try:
            response = requests.post(
                f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
                auth=(RINGCENTRAL_CLIENT_ID, RINGCENTRAL_CLIENT_SECRET),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": RINGCENTRAL_JWT_TOKEN
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                logger.info("Authentication successful")
                return True
            else:
                logger.error(f"Auth failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False

    def fetch_sms_messages(self, days_back=180):
        """Fetch SMS messages from the last N days"""
        if not self.access_token:
            if not self.authenticate():
                return []

        all_messages = []
        date_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Fetch from account-level message store
        page = 1
        while True:
            try:
                response = requests.get(
                    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params={
                        "dateFrom": date_from,
                        "messageType": "SMS",
                        "perPage": 250,
                        "page": page
                    },
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    records = data.get("records", [])

                    if not records:
                        break

                    all_messages.extend(records)
                    logger.info(f"Fetched page {page}: {len(records)} messages (total: {len(all_messages)})")

                    # Check for more pages
                    paging = data.get("paging", {})
                    if page >= paging.get("totalPages", 1):
                        break
                    page += 1
                else:
                    logger.error(f"Fetch failed: {response.status_code} - {response.text[:200]}")
                    break

            except Exception as e:
                logger.error(f"Fetch error: {e}")
                break

        logger.info(f"Total messages fetched: {len(all_messages)}")
        return all_messages

    def filter_target_messages(self, messages):
        """Filter messages to/from target phone number"""
        filtered = []

        for msg in messages:
            from_number = msg.get("from", {}).get("phoneNumber", "")
            to_numbers = [t.get("phoneNumber", "") for t in msg.get("to", [])]

            # Clean numbers for comparison
            from_clean = re.sub(r'[^\d]', '', from_number)[-10:]
            to_clean = [re.sub(r'[^\d]', '', t)[-10:] for t in to_numbers]

            # Check if target number is involved
            if TARGET_PHONE in from_clean or TARGET_PHONE in to_clean:
                filtered.append(msg)

        logger.info(f"Messages involving {TARGET_PHONE}: {len(filtered)}")
        return filtered

    def analyze_messages(self, messages):
        """Analyze message patterns"""
        analysis = {
            "total_messages": len(messages),
            "inbound": 0,
            "outbound": 0,
            "conversations": defaultdict(list),
            "response_phrases": Counter(),
            "acceptance_phrases": [],
            "decline_phrases": [],
            "ambiguous_phrases": [],
            "shift_related": [],
            "response_times": [],
            "caregiver_stats": defaultdict(lambda: {"responses": 0, "accepts": 0, "declines": 0})
        }

        # Keywords that indicate shift-related messages
        shift_keywords = [
            "shift", "cover", "work", "available", "today", "tomorrow",
            "morning", "afternoon", "evening", "client", "patient",
            "hours", "time", "can you", "need", "urgent", "asap",
            "call off", "calloff", "sick", "cancel"
        ]

        # Acceptance indicators
        acceptance_words = [
            "yes", "yep", "yeah", "sure", "ok", "okay", "i can", "i will",
            "on my way", "omw", "be there", "got it", "i'll do it",
            "count me in", "sounds good", "works for me", "i'm in",
            "absolutely", "definitely", "no problem", "np"
        ]

        # Decline indicators
        decline_words = [
            "no", "nope", "can't", "cannot", "unable", "sorry",
            "not available", "busy", "working", "already have",
            "pass", "decline", "won't work", "not today"
        ]

        for msg in messages:
            direction = msg.get("direction", "")
            subject = msg.get("subject", "")  # SMS text is in subject
            from_number = msg.get("from", {}).get("phoneNumber", "")
            to_info = msg.get("to", [{}])[0] if msg.get("to") else {}
            creation_time = msg.get("creationTime", "")

            if direction == "Inbound":
                analysis["inbound"] += 1
                other_party = from_number
            else:
                analysis["outbound"] += 1
                other_party = to_info.get("phoneNumber", "")

            # Clean the other party number
            other_clean = re.sub(r'[^\d]', '', other_party)[-10:]

            # Store in conversations
            analysis["conversations"][other_clean].append({
                "direction": direction,
                "text": subject,
                "time": creation_time
            })

            # Analyze inbound messages (caregiver responses)
            if direction == "Inbound" and subject:
                text_lower = subject.lower().strip()

                # Check if shift-related
                is_shift_related = any(kw in text_lower for kw in shift_keywords)

                # Categorize response
                is_acceptance = any(word in text_lower for word in acceptance_words)
                is_decline = any(word in text_lower for word in decline_words)

                if is_acceptance and not is_decline:
                    analysis["acceptance_phrases"].append(subject)
                    analysis["caregiver_stats"][other_clean]["accepts"] += 1
                elif is_decline and not is_acceptance:
                    analysis["decline_phrases"].append(subject)
                    analysis["caregiver_stats"][other_clean]["declines"] += 1
                else:
                    analysis["ambiguous_phrases"].append(subject)

                analysis["caregiver_stats"][other_clean]["responses"] += 1

                # Count all phrases
                analysis["response_phrases"][text_lower] += 1

                if is_shift_related:
                    analysis["shift_related"].append({
                        "text": subject,
                        "from": other_clean,
                        "time": creation_time,
                        "category": "accept" if is_acceptance else "decline" if is_decline else "ambiguous"
                    })

        return analysis

    def generate_training_patterns(self, analysis):
        """Generate improved regex patterns from real data"""

        # Get most common acceptance phrases
        accept_phrases = [p.lower().strip() for p in analysis["acceptance_phrases"]]
        decline_phrases = [p.lower().strip() for p in analysis["decline_phrases"]]

        # Extract unique patterns
        acceptance_patterns = set()
        decline_patterns = set()

        for phrase in accept_phrases:
            # Extract key words/phrases
            words = phrase.split()
            if len(words) <= 3:
                acceptance_patterns.add(phrase)
            else:
                # Extract first few words if short response
                acceptance_patterns.add(' '.join(words[:3]))

        for phrase in decline_phrases:
            words = phrase.split()
            if len(words) <= 3:
                decline_patterns.add(phrase)
            else:
                decline_patterns.add(' '.join(words[:3]))

        return {
            "acceptance_patterns": list(acceptance_patterns)[:50],
            "decline_patterns": list(decline_patterns)[:50],
            "top_responses": dict(analysis["response_phrases"].most_common(100))
        }

    def run_analysis(self, days_back=180):
        """Run full analysis"""
        logger.info(f"Starting SMS analysis for last {days_back} days...")

        # Fetch messages
        all_messages = self.fetch_sms_messages(days_back)

        if not all_messages:
            logger.warning("No messages fetched")
            return None

        # Filter for target number
        target_messages = self.filter_target_messages(all_messages)

        if not target_messages:
            logger.warning(f"No messages found for {TARGET_PHONE}")
            # Return all messages analysis anyway
            target_messages = all_messages

        # Analyze
        analysis = self.analyze_messages(target_messages)

        # Generate training patterns
        patterns = self.generate_training_patterns(analysis)

        return {
            "analysis": {
                "total_messages": analysis["total_messages"],
                "inbound": analysis["inbound"],
                "outbound": analysis["outbound"],
                "unique_conversations": len(analysis["conversations"]),
                "shift_related_count": len(analysis["shift_related"]),
                "acceptance_count": len(analysis["acceptance_phrases"]),
                "decline_count": len(analysis["decline_phrases"]),
                "ambiguous_count": len(analysis["ambiguous_phrases"])
            },
            "patterns": patterns,
            "sample_acceptances": analysis["acceptance_phrases"][:20],
            "sample_declines": analysis["decline_phrases"][:20],
            "sample_ambiguous": analysis["ambiguous_phrases"][:20],
            "shift_related_messages": analysis["shift_related"][:50],
            "top_responders": dict(sorted(
                [(k, v) for k, v in analysis["caregiver_stats"].items()],
                key=lambda x: x[1]["responses"],
                reverse=True
            )[:20])
        }


def main():
    analyzer = RingCentralSMSAnalyzer()

    print("=" * 60)
    print("RINGCENTRAL SMS HISTORY ANALYSIS")
    print("Target: 719-428-3999 (Caregiver Communications)")
    print("=" * 60)

    result = analyzer.run_analysis(days_back=180)

    if result:
        print("\n📊 ANALYSIS RESULTS")
        print("-" * 40)
        print(f"Total Messages: {result['analysis']['total_messages']}")
        print(f"Inbound (from caregivers): {result['analysis']['inbound']}")
        print(f"Outbound (to caregivers): {result['analysis']['outbound']}")
        print(f"Unique Conversations: {result['analysis']['unique_conversations']}")
        print(f"Shift-Related Messages: {result['analysis']['shift_related_count']}")

        print("\n📝 RESPONSE CATEGORIZATION")
        print("-" * 40)
        print(f"Acceptances: {result['analysis']['acceptance_count']}")
        print(f"Declines: {result['analysis']['decline_count']}")
        print(f"Ambiguous: {result['analysis']['ambiguous_count']}")

        print("\n✅ SAMPLE ACCEPTANCE PHRASES")
        print("-" * 40)
        for phrase in result["sample_acceptances"][:10]:
            print(f"  • \"{phrase}\"")

        print("\n❌ SAMPLE DECLINE PHRASES")
        print("-" * 40)
        for phrase in result["sample_declines"][:10]:
            print(f"  • \"{phrase}\"")

        print("\n❓ SAMPLE AMBIGUOUS PHRASES")
        print("-" * 40)
        for phrase in result["sample_ambiguous"][:10]:
            print(f"  • \"{phrase}\"")

        print("\n📱 TOP RESPONDERS")
        print("-" * 40)
        for phone, stats in list(result["top_responders"].items())[:10]:
            print(f"  {phone}: {stats['responses']} responses ({stats['accepts']} accepts, {stats['declines']} declines)")

        print("\n🎯 LEARNED PATTERNS")
        print("-" * 40)
        print(f"Acceptance patterns: {len(result['patterns']['acceptance_patterns'])}")
        print(f"Decline patterns: {len(result['patterns']['decline_patterns'])}")

        # Save results
        output_file = "/Users/shulmeister/Documents/GitHub/careassist-unified-portal/sales/shift_filling/training_data.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {output_file}")

        return result
    else:
        print("❌ Analysis failed")
        return None


if __name__ == "__main__":
    main()
