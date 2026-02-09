#!/usr/bin/env python3
"""
Automated Gigi Voice Brain Test Suite

Simulates Retell's WebSocket protocol to test Gigi's voice brain end-to-end.
Sends the exact same message format Retell uses — ping/pong, call_details,
response_required — and validates responses.

Usage:
    python3 scripts/test_voice_brain.py                    # Test production (8765)
    python3 scripts/test_voice_brain.py --port 8766        # Test staging
    python3 scripts/test_voice_brain.py --test shifts      # Run specific test
    python3 scripts/test_voice_brain.py --all              # Run all tests
    python3 scripts/test_voice_brain.py --stress           # Stress test (ping/pong during tools)
"""

import asyncio
import json
import time
import sys
import argparse

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
# TEST DEFINITIONS
# ═══════════════════════════════════════════════════════════

TESTS = {
    # ── Greeting & Basics ──
    "greeting": {
        "question": None,
        "expect_tools": [],
        "expect_in_response": ["Gigi", "Colorado Care Assist"],
        "description": "Initial greeting with caller ID lookup",
    },
    "simple": {
        "question": "What's 2 plus 2?",
        "expect_tools": [],
        "expect_in_response": ["four"],
        "description": "Simple math (no tools)",
    },

    # ── WellSky / Operations ──
    "shifts": {
        "question": "Who's got shifts scheduled for today?",
        "expect_tools": ["get_wellsky_shifts"],
        "expect_in_response": [],
        "description": "Today's WellSky shifts",
    },
    "caregiver": {
        "question": "Which caregiver is with Richard Tompkins right now?",
        "expect_tools": ["get_client_current_status", "get_wellsky_clients"],
        "expect_in_response": [],
        "description": "Client's current caregiver lookup",
    },
    "unassigned": {
        "question": "Are there any unassigned shifts today?",
        "expect_tools": ["get_wellsky_shifts"],
        "expect_in_response": [],
        "description": "Find unassigned/open shifts",
    },
    "hours": {
        "question": "How many total hours are scheduled today?",
        "expect_tools": ["get_wellsky_shifts"],
        "expect_in_response": [],
        "description": "Total scheduled hours",
    },
    "clients": {
        "question": "How many active clients do we have?",
        "expect_tools": ["get_wellsky_clients"],
        "expect_in_response": [],
        "description": "Active client count from WellSky",
    },
    "caregivers_list": {
        "question": "Can you list our active caregivers?",
        "expect_tools": ["get_wellsky_caregivers"],
        "expect_in_response": [],
        "description": "Active caregiver list from WellSky",
    },

    # ── Web Search / Knowledge ──
    "concerts": {
        "question": "Are there any good concerts in Denver this weekend?",
        "expect_tools": ["search_concerts"],
        "expect_in_response": [],
        "description": "Concert search via Brave/DDG",
    },
    "weather": {
        "question": "What's the weather in Denver right now?",
        "expect_tools": ["get_weather"],
        "expect_in_response": [],
        "description": "Current weather via wttr.in",
    },
    "weather_vail": {
        "question": "What's the weather like in Vail tonight?",
        "expect_tools": ["get_weather"],
        "expect_in_response": [],
        "description": "Weather for different location",
    },
    "ski": {
        "question": "How are the ski conditions at Eldora today?",
        "expect_tools": ["web_search"],
        "expect_in_response": [],
        "description": "Ski conditions search",
    },
    "flights": {
        "question": "Can you find me a cheap flight from Denver to Tokyo?",
        "expect_tools": ["web_search"],
        "expect_in_response": [],
        "description": "Flight price search",
    },
    "stock": {
        "question": "What's the price of Bitcoin right now?",
        "expect_tools": ["get_stock_price", "get_crypto_price"],
        "expect_in_response": [],
        "description": "Crypto/stock price lookup",
    },
    "news": {
        "question": "What's the latest news about home care in Colorado?",
        "expect_tools": ["web_search"],
        "expect_in_response": [],
        "description": "News search",
    },

    # ── Google Calendar / Email ──
    "calendar": {
        "question": "What's on my calendar today?",
        "expect_tools": ["get_calendar_events"],
        "expect_in_response": [],
        "description": "Today's calendar events",
    },
    "email": {
        "question": "Do I have any unread emails?",
        "expect_tools": ["search_emails"],
        "expect_in_response": [],
        "description": "Unread email check",
    },

    # ── Communication ──
    "sms": {
        "question": "Send a text to the team saying the morning meeting is at 9 AM",
        "expect_tools": ["send_team_message", "send_sms"],
        "expect_in_response": [],
        "description": "Send SMS or team message",
    },

    # ── Local Search / Lifestyle ──
    "dog_park": {
        "question": "Are there any good dog parks near me in Denver?",
        "expect_tools": ["web_search"],
        "expect_in_response": [],
        "description": "Local dog park search",
    },
    "restaurant": {
        "question": "Can you find a nice restaurant for my wife and I tonight in Denver?",
        "expect_tools": ["web_search"],
        "expect_in_response": [],
        "description": "Restaurant recommendation",
    },
    "diner": {
        "question": "Is there a greasy diner near me? I'm in downtown Denver.",
        "expect_tools": ["web_search"],
        "expect_in_response": [],
        "description": "Casual diner search",
    },
    "concert_tickets": {
        "question": "Can you help me find tickets to a show at Red Rocks this month?",
        "expect_tools": ["web_search", "search_concerts"],
        "expect_in_response": [],
        "description": "Concert ticket search",
    },

    # ── Edge Cases ──
    "vague": {
        "question": "Hey, what's going on?",
        "expect_tools": [],
        "expect_in_response": [],
        "description": "Vague question (should ask for clarification)",
    },
    "multi_part": {
        "question": "What's the weather and who has shifts today?",
        "expect_tools": ["get_weather", "get_wellsky_shifts"],
        "expect_in_response": [],
        "description": "Multi-part question needing multiple tools",
    },
    "followup": {
        "question": "Tell me about Susan Duchin's schedule this week",
        "expect_tools": ["get_wellsky_shifts", "get_wellsky_clients", "search_wellsky_clients"],
        "expect_in_response": [],
        "description": "Client-specific schedule lookup",
    },
    "transfer": {
        "question": "Can you transfer me to the office?",
        "expect_tools": ["transfer_call"],
        "expect_in_response": [],
        "description": "Call transfer request",
    },
}


# ═══════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════

async def run_test(test_name: str, test_config: dict, port: int, verbose: bool = True):
    """Run a single test against the voice brain WebSocket."""
    url = f"ws://127.0.0.1:{port}/llm-websocket/test_{test_name}_{int(time.time())}"
    result = {"name": test_name, "passed": False, "time": 0, "error": None, "tools": [], "response": ""}

    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            # 1. Receive config
            config = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if config.get("response_type") != "config":
                result["error"] = f"Expected config, got {config.get('response_type')}"
                return result

            # 2. Send call_details
            await ws.send(json.dumps({
                "interaction_type": "call_details",
                "call": {"from_number": "+13074598220", "to_number": "+17208176600"}
            }))

            # 3. Get greeting
            greeting_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            greeting = greeting_msg.get("content", "")

            if test_config["question"] is None:
                # Greeting-only test
                result["response"] = greeting
                result["time"] = 0
                result["passed"] = True
                for expected in test_config.get("expect_in_response", []):
                    if expected.lower() not in greeting.lower():
                        result["passed"] = False
                        result["error"] = f"Expected '{expected}' in greeting: {greeting}"
                        break
                return result

            # 4. Send question
            t0 = time.time()
            await ws.send(json.dumps({
                "interaction_type": "response_required",
                "response_id": 1,
                "transcript": [
                    {"role": "agent", "content": greeting},
                    {"role": "user", "content": test_config["question"]}
                ]
            }))

            # 5. Collect response (handle pings inline)
            tools_seen = []
            intermediates = []
            final_response = ""
            done = False

            while not done:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    result["error"] = f"TIMEOUT after {round(time.time()-t0,1)}s"
                    return result

                msg = json.loads(raw)
                rt = msg.get("response_type")

                if rt == "ping_pong":
                    await ws.send(json.dumps({
                        "response_type": "ping_pong",
                        "timestamp": msg.get("timestamp")
                    }))
                elif rt == "tool_call_invocation":
                    tools_seen.append(msg.get("name"))
                elif rt == "tool_call_result":
                    pass
                elif rt == "response":
                    if msg.get("content_complete"):
                        final_response = msg.get("content", "")
                        done = True
                    else:
                        intermediates.append(msg.get("content", ""))

            elapsed = round(time.time() - t0, 2)
            result["time"] = elapsed
            result["tools"] = tools_seen
            result["response"] = final_response
            result["intermediates"] = intermediates

            # 6. Validate
            passed = True
            errors = []

            # Check tools
            expected_tools = test_config.get("expect_tools", [])
            if expected_tools:
                for et in expected_tools:
                    if et not in tools_seen:
                        # Allow partial match (any one expected tool is fine)
                        pass
                if not any(et in tools_seen for et in expected_tools) and expected_tools:
                    passed = False
                    errors.append(f"Expected tools {expected_tools}, got {tools_seen}")

            # Check response content
            if not final_response or len(final_response) < 10:
                passed = False
                errors.append(f"Response too short: '{final_response}'")

            # Check expected phrases
            for expected in test_config.get("expect_in_response", []):
                if expected.lower() not in final_response.lower():
                    passed = False
                    errors.append(f"Expected '{expected}' in response")

            # Check timeout (voice should respond within 15s)
            if elapsed > 15:
                errors.append(f"Slow: {elapsed}s (>15s)")

            result["passed"] = passed
            if errors:
                result["error"] = "; ".join(errors)

    except Exception as e:
        result["error"] = str(e)

    return result


async def run_stress_test(port: int):
    """Stress test: Send pings every 2s during a slow tool call."""
    url = f"ws://127.0.0.1:{port}/llm-websocket/stress_{int(time.time())}"

    async with websockets.connect(url, ping_interval=None) as ws:
        config = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        await ws.send(json.dumps({
            "interaction_type": "call_details",
            "call": {"from_number": "+13074598220", "to_number": "+17208176600"}
        }))
        greeting = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))

        t0 = time.time()
        await ws.send(json.dumps({
            "interaction_type": "response_required",
            "response_id": 1,
            "transcript": [
                {"role": "agent", "content": greeting.get("content", "")},
                {"role": "user", "content": "Search for concerts in Denver this weekend"}
            ]
        }))

        pings_sent = 0
        pongs_received = 0
        final_received = False

        async def send_pings():
            nonlocal pings_sent
            while not final_received:
                await asyncio.sleep(2)
                if final_received:
                    break
                await ws.send(json.dumps({"interaction_type": "ping_pong", "timestamp": int(time.time()*1000)}))
                pings_sent += 1

        async def receive_msgs():
            nonlocal pongs_received, final_received
            while not final_received:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=25)
                except asyncio.TimeoutError:
                    break
                msg = json.loads(raw)
                if msg.get("response_type") == "ping_pong":
                    pongs_received += 1
                elif msg.get("response_type") == "response" and msg.get("content_complete"):
                    final_received = True

        await asyncio.gather(send_pings(), receive_msgs())
        elapsed = round(time.time() - t0, 2)

        passed = pongs_received == pings_sent and final_received
        print(f"  Pings: {pongs_received}/{pings_sent} answered | Response: {'YES' if final_received else 'NO'} | {elapsed}s")
        return passed


async def run_cancellation_test(port: int):
    """Test stale response cancellation."""
    url = f"ws://127.0.0.1:{port}/llm-websocket/cancel_{int(time.time())}"

    async with websockets.connect(url, ping_interval=None) as ws:
        config = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        await ws.send(json.dumps({
            "interaction_type": "call_details",
            "call": {"from_number": "+13074598220", "to_number": "+17208176600"}
        }))
        greeting = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        g = greeting.get("content", "")

        # Send slow question (id=1)
        await ws.send(json.dumps({
            "interaction_type": "response_required", "response_id": 1,
            "transcript": [{"role": "agent", "content": g}, {"role": "user", "content": "Search for concerts in Denver"}]
        }))

        # Wait 0.5s then send simple question (id=2)
        await asyncio.sleep(0.5)
        await ws.send(json.dumps({
            "interaction_type": "response_required", "response_id": 2,
            "transcript": [
                {"role": "agent", "content": g},
                {"role": "user", "content": "Search for concerts in Denver"},
                {"role": "agent", "content": "Let me find that."},
                {"role": "user", "content": "Never mind. What's 2 plus 2?"}
            ]
        }))

        # Collect responses
        id1_final = False
        id2_final = False
        while not id2_final:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            if msg.get("response_type") == "response" and msg.get("content_complete"):
                if msg.get("response_id") == 1:
                    id1_final = True
                elif msg.get("response_id") == 2:
                    id2_final = True

        passed = id2_final and not id1_final
        print(f"  id=1 cancelled: {'YES' if not id1_final else 'NO'} | id=2 answered: {'YES' if id2_final else 'NO'}")
        return passed


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Test Gigi Voice Brain")
    parser.add_argument("--port", type=int, default=8765, help="Port (8765=prod, 8766=staging)")
    parser.add_argument("--test", type=str, help="Run specific test (concerts, weather, shifts, etc.)")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--stress", action="store_true", help="Run stress test (ping/pong)")
    parser.add_argument("--cancel", action="store_true", help="Run cancellation test")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    port = args.port
    verbose = not args.quiet

    print(f"═══ Gigi Voice Brain Test Suite ═══")
    print(f"Target: ws://127.0.0.1:{port}/llm-websocket/")
    print()

    if args.stress:
        print("▶ Stress Test (ping/pong during slow tool call)")
        passed = await run_stress_test(port)
        print(f"  Result: {'PASS' if passed else 'FAIL'}")
        return

    if args.cancel:
        print("▶ Cancellation Test (stale response)")
        passed = await run_cancellation_test(port)
        print(f"  Result: {'PASS' if passed else 'FAIL'}")
        return

    # Determine which tests to run
    if args.test:
        test_names = [args.test]
    elif args.all:
        test_names = list(TESTS.keys())
    else:
        # Default: run all tests
        test_names = list(TESTS.keys())

    results = []
    for name in test_names:
        if name not in TESTS:
            print(f"Unknown test: {name}. Available: {', '.join(TESTS.keys())}")
            continue

        test_config = TESTS[name]
        desc = test_config["description"]
        print(f"▶ {name}: {desc}")

        result = await run_test(name, test_config, port, verbose)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        tools = ", ".join(result["tools"]) if result["tools"] else "none"
        response_preview = (result["response"] or "")[:80]

        if result["passed"]:
            print(f"  ✓ {status} ({result['time']}s) tools=[{tools}]")
            if verbose and response_preview:
                print(f"    \"{response_preview}...\"")
        else:
            print(f"  ✗ {status} ({result['time']}s) tools=[{tools}]")
            print(f"    Error: {result.get('error', 'unknown')}")
            if verbose and response_preview:
                print(f"    Response: \"{response_preview}...\"")
        print()

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    avg_time = round(sum(r["time"] for r in results) / total, 2) if total else 0

    print(f"═══ Results: {passed}/{total} passed | Avg time: {avg_time}s ═══")
    if passed < total:
        print("FAILED tests:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['name']}: {r.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
