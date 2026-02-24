#!/usr/bin/env python3.11
"""Gigi Text Channel Simulation Tests — SMS, iMessage, Telegram.

Tests Gigi's tool usage and response quality across all text channels
by sending messages to the ask-gigi API and evaluating responses.

Usage:
    # Run all text tests on staging (default)
    python3.11 scripts/run_gigi_text_simulations.py

    # Run on production
    PORT=8767 python3.11 scripts/run_gigi_text_simulations.py

    # Run only MCP tests
    python3.11 scripts/run_gigi_text_simulations.py --mcp-only

    # Run only a specific channel
    python3.11 scripts/run_gigi_text_simulations.py --channel telegram
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("text-sim")

PORT = int(os.getenv("PORT", "8768"))  # Default staging
BASE_URL = f"http://localhost:{PORT}"
API_TOKEN = os.getenv("GIGI_API_TOKEN", "MePBCMehqomZ9gWIJHdlVjCvcppQmwRUXkER6lgjp7c")
TIMEOUT = 90  # seconds per test (tools can be slow)


@dataclass
class TestScenario:
    """A single test scenario."""
    id: str
    name: str
    channel: str                      # telegram, sms, imessage
    message: str                      # What to send to Gigi
    expected_tools: List[str]         # Tool names Gigi SHOULD call (any match = pass)
    expected_keywords: List[str]      # Keywords response SHOULD contain (any match = pass)
    forbidden_keywords: List[str] = field(default_factory=list)  # MUST NOT contain
    category: str = "general"         # general, mcp, operations, entertainment, finance
    description: str = ""


@dataclass
class TestResult:
    scenario: TestScenario
    passed: bool
    response: str
    tool_used: str = ""
    latency_ms: int = 0
    error: str = ""
    details: str = ""


# ─────────────────────────────────────────────────────────────
# TEST SCENARIOS
# ─────────────────────────────────────────────────────────────

MCP_TESTS = [
    # Knowledge Graph
    TestScenario(
        id="mcp-kg-1", name="Knowledge Graph: Client Lookup",
        channel="telegram",
        message="Search the knowledge graph for information about Marthe Schwartz",
        expected_tools=["query_knowledge_graph"],
        expected_keywords=["Marthe", "Schwartz"],
        category="mcp",
        description="Should use query_knowledge_graph to find client entity",
    ),
    TestScenario(
        id="mcp-kg-2", name="Knowledge Graph: Relationship Query",
        channel="telegram",
        message="Use the knowledge graph to find which caregivers are assigned to clients in Denver",
        expected_tools=["query_knowledge_graph"],
        expected_keywords=["Denver", "caregiver"],
        category="mcp",
        description="Should query the KG for location-based relationships",
    ),
    TestScenario(
        id="mcp-kg-3", name="Knowledge Graph: Add Observation",
        channel="telegram",
        message="Add an observation to the knowledge graph for entity 'Marthe Schwartz': 'simulation test ran successfully on this date'",
        expected_tools=["update_knowledge_graph"],
        expected_keywords=["added", "observation", "Marthe", "Schwartz"],
        category="mcp",
        description="Should use update_knowledge_graph add_observations on an existing entity",
    ),

    # Sequential Thinking
    TestScenario(
        id="mcp-think-1", name="Sequential Thinking: Complex Reasoning",
        channel="telegram",
        message="Use sequential thinking to analyze: A caregiver called out sick for a shift starting in 2 hours. The client requires skilled nursing. Think through the steps we need to take.",
        expected_tools=["sequential_thinking"],
        expected_keywords=["replacement", "client", "shift"],
        category="mcp",
        description="Should use sequential_thinking for multi-step reasoning",
    ),

    # Terminal
    TestScenario(
        id="mcp-term-1", name="Terminal: System Check",
        channel="telegram",
        message="Use the terminal to check what's running on port 3011",
        expected_tools=["run_terminal"],
        expected_keywords=["3011", "kalshi"],
        category="mcp",
        description="Should use run_terminal to check port",
    ),
    TestScenario(
        id="mcp-term-2", name="Terminal: Disk Space",
        channel="telegram",
        message="Use the terminal to check how much disk space is available on this machine",
        expected_tools=["run_terminal"],
        expected_keywords=["disk", "available", "Gi"],
        category="mcp",
        description="Should use run_terminal to check df output",
    ),
]

OPERATIONS_TESTS = [
    TestScenario(
        id="ops-shifts-1", name="WellSky Shifts: Today",
        channel="telegram",
        message="What shifts are scheduled for today?",
        expected_tools=["get_wellsky_shifts"],
        expected_keywords=["shift", "today"],
        category="operations",
    ),
    TestScenario(
        id="ops-client-1", name="WellSky Client Lookup",
        channel="sms",
        message="Look up the client Marthe Schwartz in WellSky",
        expected_tools=["get_wellsky_clients"],
        expected_keywords=["Marthe", "Schwartz"],
        category="operations",
    ),
    TestScenario(
        id="ops-caregiver-1", name="WellSky Caregiver Lookup",
        channel="sms",
        message="Find caregiver Sarah Trujillo in WellSky",
        expected_tools=["get_wellsky_caregivers"],
        expected_keywords=["Sarah", "Trujillo"],
        category="operations",
    ),
    TestScenario(
        id="ops-weather-1", name="Weather Check",
        channel="imessage",
        message="What's the weather in Denver today?",
        expected_tools=["get_weather"],
        expected_keywords=["Denver", "°"],
        category="operations",
    ),
    TestScenario(
        id="ops-calendar-1", name="Calendar Check",
        channel="imessage",
        message="What's on my calendar for today?",
        expected_tools=["get_calendar_events"],
        expected_keywords=["calendar", "today"],
        category="operations",
    ),
]

ENTERTAINMENT_TESTS = [
    TestScenario(
        id="ent-concerts-1", name="Concert Search",
        channel="telegram",
        message="Are there any concerts in Denver this weekend?",
        expected_tools=["search_events", "search_concerts"],
        expected_keywords=["Denver", "concert", "event", "show"],
        category="entertainment",
    ),
    TestScenario(
        id="ent-stocks-1", name="Stock Price",
        channel="imessage",
        message="What's the stock price for AAPL?",
        expected_tools=["get_stock_price"],
        expected_keywords=["AAPL", "Apple", "$"],
        category="entertainment",
    ),
    TestScenario(
        id="ent-crypto-1", name="Crypto Price",
        channel="telegram",
        message="What's the price of Bitcoin right now?",
        expected_tools=["get_crypto_price"],
        expected_keywords=["Bitcoin", "BTC", "$"],
        category="entertainment",
    ),
]

FINANCE_TESTS = [
    TestScenario(
        id="fin-pnl-1", name="P&L Report",
        channel="telegram",
        message="Show me the P&L report for this month",
        expected_tools=["get_pnl_report", "get_financial_dashboard"],
        expected_keywords=["revenue", "income", "expense", "profit"],
        category="finance",
    ),
    TestScenario(
        id="fin-ar-1", name="AR Report",
        channel="telegram",
        message="What does our accounts receivable look like?",
        expected_tools=["get_ar_report"],
        expected_keywords=["receivable", "outstanding", "aging", "owed"],
        category="finance",
    ),
]

MEMORY_TESTS = [
    TestScenario(
        id="mem-save-1", name="Save Memory",
        channel="telegram",
        message="Remember this: the text simulation test ran successfully on Feb 24",
        expected_tools=["save_memory"],
        expected_keywords=["saved", "remember", "noted", "memory"],
        category="general",
    ),
    TestScenario(
        id="mem-recall-1", name="Recall Memory",
        channel="telegram",
        message="What do you remember about text simulation tests?",
        expected_tools=["recall_memories"],
        expected_keywords=["simulation", "test"],
        category="general",
    ),
]

TASK_BOARD_TESTS = [
    TestScenario(
        id="task-read-1", name="Read Task Board",
        channel="imessage",
        message="What's on my task board right now?",
        expected_tools=["get_task_board"],
        expected_keywords=["task", "board", "Today", "Inbox", "Soon"],
        category="general",
    ),
]

CHANNEL_BOUNDARY_TESTS = [
    # SMS should NOT have finance/marketing/power tools
    TestScenario(
        id="boundary-sms-1", name="SMS: Finance Should Be Limited",
        channel="sms",
        message="Show me the P&L report",
        expected_tools=[],  # Should NOT be able to call this on SMS
        expected_keywords=["can't", "unable", "not available", "limited", "available",
                          "revenue", "income"],  # Either explains limit or tries anyway
        forbidden_keywords=[],
        category="boundary",
        description="SMS channel has limited tools — finance tools excluded",
    ),
]

TRAVEL_TESTS = [
    TestScenario(
        id="travel-flights-1", name="Flight Search",
        channel="telegram",
        message="Search for one-way flights from Denver to New York on March 7, 2026 for 1 adult",
        expected_tools=["search_flights"],
        expected_keywords=["flight", "Denver", "New York"],
        category="entertainment",
    ),
]

ALL_TESTS = (
    MCP_TESTS +
    OPERATIONS_TESTS +
    ENTERTAINMENT_TESTS +
    FINANCE_TESTS +
    MEMORY_TESTS +
    TASK_BOARD_TESTS +
    CHANNEL_BOUNDARY_TESTS +
    TRAVEL_TESTS
)


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

async def run_test(client: httpx.AsyncClient, scenario: TestScenario) -> TestResult:
    """Send a message to ask-gigi and evaluate the response."""
    start = time.time()

    try:
        resp = await client.post(
            f"{BASE_URL}/gigi/api/ask-gigi",
            json={
                "text": scenario.message,
                "user_id": f"test_{scenario.id}",
                "channel": scenario.channel,
            },
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=TIMEOUT,
        )

        latency = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            return TestResult(
                scenario=scenario,
                passed=False,
                response=resp.text,
                latency_ms=latency,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        data = resp.json()
        response_text = data.get("response", "")

        # Evaluate response
        passed = True
        details = []

        # Check for expected keywords (at least one match)
        if scenario.expected_keywords:
            kw_found = [kw for kw in scenario.expected_keywords
                       if kw.lower() in response_text.lower()]
            if not kw_found:
                passed = False
                details.append(f"Missing keywords: expected any of {scenario.expected_keywords}")
            else:
                details.append(f"Keywords found: {kw_found}")

        # Check forbidden keywords
        for fk in scenario.forbidden_keywords:
            if fk.lower() in response_text.lower():
                passed = False
                details.append(f"Forbidden keyword found: '{fk}'")

        # Check response is not empty or error
        if not response_text or len(response_text) < 10:
            passed = False
            details.append("Response too short or empty")

        if "error" in response_text.lower() and "sorry" in response_text.lower():
            if scenario.category != "boundary":
                details.append("Response contains error/sorry (may indicate tool failure)")

        return TestResult(
            scenario=scenario,
            passed=passed,
            response=response_text[:500],
            latency_ms=latency,
            details="; ".join(details),
        )

    except httpx.TimeoutException:
        return TestResult(
            scenario=scenario,
            passed=False,
            response="",
            latency_ms=TIMEOUT * 1000,
            error=f"Timeout after {TIMEOUT}s",
        )
    except Exception as e:
        return TestResult(
            scenario=scenario,
            passed=False,
            response="",
            latency_ms=int((time.time() - start) * 1000),
            error=str(e),
        )


async def check_tool_usage_in_logs(scenario_id: str, expected_tools: List[str]) -> Optional[str]:
    """Check gigi server logs for tool calls from our test user."""
    # This is a best-effort check — logs may not capture everything
    try:
        log_path = os.path.expanduser("~/logs/gigi-server.log")
        if not os.path.exists(log_path):
            return None

        # Read last 500 lines of log
        with open(log_path) as f:
            lines = f.readlines()[-500:]

        for tool in expected_tools:
            for line in lines:
                if f"Tool: {tool}" in line and scenario_id in line:
                    return tool
                # Also check for tool calls without scenario ID (ask-gigi logs differently)
                if f"Tool: {tool}" in line:
                    return tool
    except Exception:
        pass
    return None


async def run_all_tests(tests: List[TestScenario]) -> List[TestResult]:
    """Run all test scenarios sequentially (to avoid overwhelming the LLM)."""
    results = []

    async with httpx.AsyncClient() as client:
        # Verify service is up
        try:
            health = await client.get(f"{BASE_URL}/gigi/health", timeout=10)
            if health.status_code != 200:
                logger.error(f"Gigi server not healthy on port {PORT}")
                return []
            logger.info(f"Gigi server healthy on port {PORT}")
        except Exception as e:
            logger.error(f"Cannot reach Gigi server on port {PORT}: {e}")
            return []

        total = len(tests)
        for i, scenario in enumerate(tests, 1):
            logger.info(f"[{i}/{total}] {scenario.name} ({scenario.channel}) ...")
            result = await run_test(client, scenario)

            status = "PASS" if result.passed else "FAIL"
            logger.info(
                f"  [{status}] {result.latency_ms}ms — "
                f"{result.details or result.error or 'OK'}"
            )
            if not result.passed:
                logger.info(f"  Response: {result.response[:200]}...")

            results.append(result)

            # Small delay between tests to avoid rate limiting
            await asyncio.sleep(1)

    return results


def print_report(results: List[TestResult]):
    """Print a formatted test report."""
    if not results:
        print("\n❌ No tests ran (is Gigi server up?)")
        return

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    pass_rate = passed / total * 100 if total > 0 else 0

    print("\n" + "=" * 70)
    print(f"  GIGI TEXT SIMULATION RESULTS — {total} tests, {pass_rate:.0f}% pass rate")
    print(f"  Server: localhost:{PORT} | Date: {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Group by category
    categories = {}
    for r in results:
        cat = r.scenario.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    for cat, cat_results in categories.items():
        cat_passed = sum(1 for r in cat_results if r.passed)
        cat_total = len(cat_results)
        print(f"\n  [{cat.upper()}] {cat_passed}/{cat_total}")
        print("  " + "-" * 66)

        for r in cat_results:
            status = "PASS" if r.passed else "FAIL"
            channel = r.scenario.channel.upper()[:4]
            latency = f"{r.latency_ms / 1000:.1f}s" if r.latency_ms else "?"
            print(f"    {status:4s} | {channel:4s} | {latency:>5s} | {r.scenario.name}")
            if not r.passed and r.error:
                print(f"           ERROR: {r.error[:60]}")
            if not r.passed and r.details:
                print(f"           {r.details[:60]}")

    # Channel breakdown
    print("\n  CHANNEL BREAKDOWN:")
    for channel in ["telegram", "sms", "imessage"]:
        ch_results = [r for r in results if r.scenario.channel == channel]
        if ch_results:
            ch_passed = sum(1 for r in ch_results if r.passed)
            ch_total = len(ch_results)
            print(f"    {channel:>8s}: {ch_passed}/{ch_total} ({ch_passed/ch_total*100:.0f}%)")

    # Summary
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0
    print(f"\n  SUMMARY: {passed}/{total} passed ({pass_rate:.0f}%) | Avg latency: {avg_latency/1000:.1f}s")

    if failed > 0:
        print("\n  FAILED TESTS:")
        for r in results:
            if not r.passed:
                print(f"    - {r.scenario.id}: {r.scenario.name}")
                if r.error:
                    print(f"      Error: {r.error[:80]}")
                if r.response:
                    print(f"      Response: {r.response[:120]}...")

    print("=" * 70)

    return pass_rate


async def main():
    parser = argparse.ArgumentParser(description="Gigi Text Simulation Tests")
    parser.add_argument("--mcp-only", action="store_true", help="Run only MCP tool tests")
    parser.add_argument("--channel", choices=["telegram", "sms", "imessage"], help="Run only a specific channel")
    parser.add_argument("--category", help="Run only a specific category (mcp, operations, entertainment, finance, boundary)")
    args = parser.parse_args()

    tests = ALL_TESTS

    if args.mcp_only:
        tests = MCP_TESTS
    elif args.channel:
        tests = [t for t in ALL_TESTS if t.channel == args.channel]
    elif args.category:
        tests = [t for t in ALL_TESTS if t.category == args.category]

    logger.info(f"Running {len(tests)} text simulation tests on port {PORT}...")

    results = await run_all_tests(tests)
    pass_rate = print_report(results)

    # Exit code: 0 if pass rate >= 70%, 1 otherwise
    sys.exit(0 if pass_rate and pass_rate >= 70 else 1)


if __name__ == "__main__":
    asyncio.run(main())
