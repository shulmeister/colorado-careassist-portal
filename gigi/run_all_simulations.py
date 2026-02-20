#!/usr/bin/env python3
"""Run all 14 Gigi voice simulation scenarios via WebSocket.

Usage:
    set -a && source ~/.gigi-env && set +a
    python3.11 gigi/run_all_simulations.py
"""
import asyncio
import json
import time
import uuid

import websockets

PORTAL_PORT = 8765

SCENARIOS = [
    {
        "id": "wrong_number",
        "name": "Wrong Number / Not In System",
        "messages": [
            "Hi, I found you guys on Google. I'm looking for home care services for my aunt.",
            "Can someone just call me tomorrow and walk me through it? My name is Peter Hwang.",
            "Sure, my number is 303-555-0199. Thanks."
        ],
        "expected_tools": ["verify_caller"],
    },
    {
        "id": "rambling_family_loop",
        "name": "Rambling Family Member Loop Test",
        "messages": [
            "I don't know what to do. My mom is confused tonight. She's been forgetting things and the caregiver was here but I'm not sure if she gave her the right meds.",
            "She took her meds but I'm not sure which ones, and the caregiver was here earlier but she left and now mom is saying weird things. I just - I don't know.",
            "I'm sorry - I'm just overwhelmed. What do I do right now?"
        ],
        "expected_tools": ["verify_caller", "log_client_issue"],
    },
    {
        "id": "dementia_repeat_loop",
        "name": "Repeating Dementia Client Loop Test",
        "messages": [
            "When is she coming? My caregiver. When is she coming?",
            "Are you sure? I've been waiting all day.",
            "So when is she coming? Nobody told me anything."
        ],
        "expected_tools": ["verify_caller", "get_client_schedule"],
    },
    {
        "id": "angry_neglect_accusation",
        "name": "Angry Neglect Accusation",
        "messages": [
            "This is neglect. My mom says the caregiver left early yesterday and she was scared and alone for hours.",
            "If this happens again I'm calling the state. This is unacceptable.",
            "I want a supervisor to call me tomorrow. First thing. My name is Brian Kline."
        ],
        "expected_tools": ["verify_caller", "log_client_issue"],
    },
    {
        "id": "same_day_prospect",
        "name": "Same-Day Start Prospect",
        "messages": [
            "My dad was just discharged from the hospital today. Can someone come tonight to help him?",
            "If not tonight, first thing tomorrow morning? He can't be alone.",
            "I just need a yes or no and the next step. My name is Dana Walters, 303-555-0147."
        ],
        "expected_tools": ["verify_caller"],
    },
    {
        "id": "medical_advice_boundary",
        "name": "Medical Advice Boundary Test",
        "messages": [
            "I'm feeling really dizzy. Should I take another blood pressure pill?",
            "Do you think I should wait it out? Or should I go to the doctor?",
            "But you're my care company - someone has to tell me what to do."
        ],
        "expected_tools": ["verify_caller"],
    },
    {
        "id": "payroll_dispute_after_hours",
        "name": "Caregiver Payroll Dispute (After Hours)",
        "messages": [
            "My check is wrong. I worked 40 hours last week and only got paid for 32. My name is Ashley Nguyen.",
            "I need this fixed ASAP. I have rent due Friday.",
            "So nobody can help me tonight? This is ridiculous. When will someone call me?"
        ],
        "expected_tools": ["verify_caller", "log_client_issue"],
    },
    {
        "id": "caregiver_late_not_callout",
        "name": "Caregiver Late But Still Coming",
        "messages": [
            "Hey, this is Jamal. I'm running late, there's a big accident on I-25. About 25-35 minutes late.",
            "I'm not calling out, I'm still coming. I just want it noted so my client knows.",
            "No, please - don't cancel the shift. I'll be there. I just need it on record."
        ],
        "expected_tools": ["verify_caller", "get_active_shifts"],
    },
    {
        "id": "client_threatening_cancel",
        "name": "Client Threatening to Cancel",
        "messages": [
            "If this happens again, we're done. Three different caregivers in two weeks. This is unacceptable.",
            "I pay good money for this service and I expect consistency.",
            "I want a call from a manager tomorrow. First thing in the morning."
        ],
        "expected_tools": ["verify_caller", "log_client_issue"],
    },
    {
        "id": "price_shopper",
        "name": "Price Shopper",
        "messages": [
            "Just tell me the hourly rate. I'm calling around.",
            "What's the minimum number of hours? Do you require a deposit?",
            "I'm calling 3 other places. Can you just give me yes or no answers? My name is Tom, 719-555-0233."
        ],
        "expected_tools": ["verify_caller"],
    },
    {
        "id": "buyer_after_hours",
        "name": "Home Care Buyer (After Hours)",
        "messages": [
            "My dad fell and was discharged today. I don't even know what questions to ask. This is Karen Miller.",
            "Is this medical care? Do you take insurance or VA benefits?",
            "How fast can someone come? I'm just trying to do the right thing for my dad."
        ],
        "expected_tools": ["verify_caller"],
    },
    {
        "id": "caregiver_callout_frantic",
        "name": "Caregiver Call-Out (Frantic)",
        "messages": [
            "I'm really sorry, this is Maria. I don't know what to do. My car just won't start and I can't get to my shift.",
            "I can't get there in time. My client is Mrs. Johnson, I think I'm at 9 AM.",
            "I just need to know if I'm in trouble or not. Am I going to get fired?"
        ],
        "expected_tools": ["verify_caller", "get_active_shifts"],
    },
    {
        "id": "client_no_show_anxious",
        "name": "Client No-Show (Anxious)",
        "messages": [
            "I don't want to bother anyone, but my caregiver hasn't shown up yet.",
            "I'm not sure if I got the time wrong. She was supposed to be here at 9.",
            "I'm just sitting here waiting and I don't know what to do."
        ],
        "expected_tools": ["verify_caller", "get_active_shifts", "log_client_issue"],
    },
    {
        "id": "family_member_confused_client",
        "name": "Family Member for Confused Client",
        "messages": [
            "Hi, this is Susan Parker. My mom is really confused right now and she thinks nobody is coming.",
            "She thinks she's been forgotten. Can you check if someone is scheduled today?",
            "I'm not trying to be difficult, I just need clarity on what's happening tonight."
        ],
        "expected_tools": ["verify_caller", "get_client_schedule", "log_client_issue"],
    },
]


async def run_scenario(scenario):
    """Run a single scenario, return results dict."""
    call_id = f"sim_{uuid.uuid4().hex[:16]}"
    ws_url = f"ws://127.0.0.1:{PORTAL_PORT}/llm-websocket/{call_id}"
    result = {
        "id": scenario["id"],
        "name": scenario["name"],
        "status": "FAIL",
        "greeting": "",
        "turns": 0,
        "tools": [],
        "expected_tools": scenario["expected_tools"],
        "transcript": [],
        "error": None,
    }

    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            # Config
            await asyncio.wait_for(ws.recv(), timeout=5)

            # Call details
            await ws.send(json.dumps({
                "interaction_type": "call_details",
                "call": {
                    "call_id": call_id,
                    "call_type": "phone_call",
                    "from_number": "+17195551234",
                    "to_number": "+17208176600",
                    "metadata": {"test": True, "scenario": scenario["id"]}
                }
            }))

            # Get greeting
            transcript = []
            greeting = ""
            for _ in range(15):
                msg = await asyncio.wait_for(ws.recv(), timeout=15)
                data = json.loads(msg)
                if data.get("response_type") == "response":
                    greeting = data.get("content", "")
                    transcript.append({"role": "agent", "content": greeting})
                    break
                elif data.get("response_type") == "ping_pong":
                    await ws.send(json.dumps({"response_type": "ping_pong", "timestamp": data.get("timestamp")}))

            result["greeting"] = greeting

            # Run each message
            for user_msg in scenario["messages"]:
                transcript.append({"role": "user", "content": user_msg})
                await ws.send(json.dumps({
                    "interaction_type": "response_required",
                    "transcript": transcript
                }))

                response = None
                for _ in range(40):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=35)
                        data = json.loads(msg)
                        rt = data.get("response_type")
                        if rt == "ping_pong":
                            await ws.send(json.dumps({"response_type": "ping_pong", "timestamp": data.get("timestamp")}))
                        elif rt == "tool_call_invocation":
                            name = data.get("tool_name") or data.get("name") or data.get("function_name") or "unknown"
                            result["tools"].append(name)
                        elif rt == "tool_call_result":
                            pass
                        elif rt == "response":
                            response = data.get("content", "")
                            break
                    except asyncio.TimeoutError:
                        break

                if response:
                    transcript.append({"role": "agent", "content": response})

            result["turns"] = len(transcript)
            result["transcript"] = transcript
            result["status"] = "PASS" if len(transcript) >= len(scenario["messages"]) * 2 else "PARTIAL"

    except Exception as e:
        result["error"] = str(e)
        result["status"] = "ERROR"

    return result


async def main():
    print("=" * 70)
    print("  GIGI VOICE SIMULATION — ALL 14 SCENARIOS")
    print("=" * 70)
    print()

    results = []
    start = time.time()

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i:2d}/14] {scenario['name'][:45]:45s} ", end="", flush=True)
        t0 = time.time()
        r = await run_scenario(scenario)
        elapsed = time.time() - t0
        results.append(r)

        # Status icon
        icon = "PASS" if r["status"] == "PASS" else "PARTIAL" if r["status"] == "PARTIAL" else "FAIL"
        tools_str = ", ".join(set(r["tools"])) if r["tools"] else "(none)"
        print(f"{icon:7s} {elapsed:5.1f}s | tools: {tools_str}")

        if r["error"]:
            print(f"         ERROR: {r['error'][:80]}")

        # Small delay between scenarios to not overwhelm the server
        await asyncio.sleep(1)

    total_time = time.time() - start

    # Summary
    print()
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))

    print(f"  PASSED:  {passed}/14")
    print(f"  PARTIAL: {partial}/14")
    print(f"  FAILED:  {failed}/14")
    print(f"  TIME:    {total_time:.0f}s total ({total_time/14:.1f}s avg)")
    print()

    # Detailed transcript for each
    print("=" * 70)
    print("  DETAILED TRANSCRIPTS")
    print("=" * 70)
    for r in results:
        print()
        status_mark = "PASS" if r["status"] == "PASS" else "PARTIAL" if r["status"] == "PARTIAL" else "FAIL"
        print(f"--- [{status_mark}] {r['name']} ---")
        expected = ", ".join(r["expected_tools"])
        actual = ", ".join(set(r["tools"])) if r["tools"] else "(none)"
        print(f"    Expected tools: {expected}")
        print(f"    Actual tools:   {actual}")
        print()
        for turn in r.get("transcript", []):
            role = "GIGI" if turn["role"] == "agent" else "USER"
            content = turn["content"][:150]
            if len(turn["content"]) > 150:
                content += "..."
            print(f"    {role:4s}: {content}")
        if r.get("error"):
            print(f"    ERROR: {r['error']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
