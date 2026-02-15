import asyncio, websockets, json, time

async def test_tool(tool_name, tool_input, description):
    uri = f"ws://localhost:8765/llm-websocket/test_{tool_name}_{int(time.time())}"
    try:
        async with websockets.connect(uri, open_timeout=30) as ws:
            await ws.recv()
            await ws.send(json.dumps({"interaction_type": "call_details", "call": {"from_number": "+13035551234", "call_id": f"test_{tool_name}"}}))
            greeting = json.loads(await ws.recv())
            await ws.send(json.dumps({"interaction_type": "response_required", "response_id": 1, "transcript": [{"role": "assistant", "content": greeting.get("content", "Hi")}, {"role": "user", "content": tool_input}]}))
            responses = []
            for _ in range(5):
                try:
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    responses.append(resp)
                    if resp.get("content_complete"): break
                except asyncio.TimeoutError: break
            final = responses[-1] if responses else {}
            content = final.get("content", "NO RESPONSE")
            status = "PASS" if len(content) > 10 and "error" not in content.lower() else "CHECK"
            print(f"  {status} | {description}: {content[:150]}")
            return status
    except Exception as e:
        print(f"  FAIL | {description}: {e}")
        return "FAIL"

async def main():
    print("=== Voice Brain Tool Tests (Post-Fix) ===")
    print()
    tests = [
        ("weather", "What is the weather in Denver?", "get_weather"),
        ("client", "Who is with Preston Hill right now?", "get_client_current_status"),
        ("clients", "Search for clients named Hill", "get_wellsky_clients"),
        ("caregivers", "Search for caregivers named Garcia", "get_wellsky_caregivers"),
        ("stock", "What is the price of AAPL stock?", "get_stock_price"),
        ("crypto", "What is the price of Bitcoin?", "get_crypto_price"),
        ("search", "Search the web for Colorado home care agencies", "web_search"),
        ("calendar", "What is on my calendar today?", "get_calendar_events"),
        ("email", "Check my unread emails", "search_emails"),
        ("task", "Check on the latest Claude Code task", "check_claude_task"),
    ]
    results = {"PASS": 0, "CHECK": 0, "FAIL": 0}
    for tool, query, desc in tests:
        status = await test_tool(tool, query, desc)
        results[status] = results.get(status, 0) + 1
        await asyncio.sleep(1)
    p, c, f = results["PASS"], results["CHECK"], results["FAIL"]
    print()
    print(f"=== Results: {p} PASS, {c} CHECK, {f} FAIL ===")

asyncio.run(main())
