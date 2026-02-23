"""
Simulation Evaluation Engine

Analyzes simulation results and generates scores by:
1. Comparing expected vs actual tool usage
2. Using Claude to evaluate conversation behavior
3. Generating comprehensive reports

Author: Colorado Care Assist
Date: February 6, 2026
"""

import json
import logging
import os
from typing import Any, Dict, List

import anthropic
import psycopg2

logger = logging.getLogger(__name__)


async def evaluate_simulation(
    scenario: Dict,
    transcript: List[Dict],
    tool_calls: List[Dict],
    tools_used: List[str]
) -> Dict[str, Any]:
    """
    Evaluate simulation against scenario expectations.

    Returns:
        {
            "tool_score": 0-100,
            "behavior_score": 0-100,
            "overall_score": 0-100,
            "details": {
                "tools_expected": [...],
                "tools_used": [...],
                "tools_missing": [...],
                "tools_extra": [...],
                "behavior_analysis": "...",
                "strengths": [...],
                "weaknesses": [...],
                "pass_fail": bool
            }
        }
    """

    # Tool Score: Matching with partial credit for related tools
    expected_tools = set(scenario.get("expected_tools", []))
    actual_tools = set(tools_used)

    # Related tool groups — using a related tool earns partial credit
    _RELATED_TOOLS = {
        "get_wellsky_clients": {"get_wellsky_caregivers", "get_client_current_status", "get_wellsky_shifts"},
        "get_wellsky_caregivers": {"get_wellsky_clients", "get_wellsky_shifts"},
        "get_client_current_status": {"get_wellsky_clients", "get_wellsky_shifts"},
        "get_wellsky_shifts": {"get_wellsky_clients", "get_wellsky_caregivers"},
    }
    # Lookup-only tools (don't penalize for proactive use)
    _LOOKUP_TOOLS = {"get_wellsky_clients", "get_wellsky_caregivers", "get_client_current_status", "get_wellsky_shifts"}

    if expected_tools:
        matched = len(expected_tools & actual_tools)
        total_expected = len(expected_tools)

        # Give partial credit for related tools used instead of expected ones
        partial_credit = 0.0
        for missing_tool in (expected_tools - actual_tools):
            related = _RELATED_TOOLS.get(missing_tool, set())
            if actual_tools & related:
                partial_credit += 0.25  # 25% credit per related tool match

        match_score = (matched + partial_credit) / total_expected
        tool_score = min(int(match_score * 100), 100)
    else:
        # No tools expected — only penalize action tools, not lookups
        if not actual_tools:
            tool_score = 100
        elif actual_tools <= _LOOKUP_TOOLS:
            tool_score = 85  # Proactive lookup is fine
        else:
            tool_score = 50  # Action tools used when none expected

    tools_missing = list(expected_tools - actual_tools)
    tools_extra = list(actual_tools - expected_tools)

    logger.info(f"Tool evaluation: {len(expected_tools & actual_tools)}/{len(expected_tools)} expected tools used")

    # Behavior Score: Claude evaluation
    behavior_score, behavior_analysis = await _evaluate_behavior(
        scenario=scenario,
        transcript=transcript
    )

    # Overall Score: Weighted average (tools 40%, behavior 60%)
    overall_score = int(tool_score * 0.4 + behavior_score * 0.6)

    return {
        "tool_score": tool_score,
        "behavior_score": behavior_score,
        "overall_score": overall_score,
        "details": {
            "tools_expected": list(expected_tools),
            "tools_used": list(actual_tools),
            "tools_missing": tools_missing,
            "tools_extra": tools_extra,
            "behavior_analysis": behavior_analysis["analysis"],
            "strengths": behavior_analysis["strengths"],
            "weaknesses": behavior_analysis["weaknesses"],
            "pass_fail": overall_score >= 70
        }
    }


async def _evaluate_behavior(scenario: Dict, transcript: List[Dict]) -> tuple[int, Dict]:
    """
    Use Claude to evaluate conversation behavior.

    Returns (score, analysis_dict)
    """

    # Format transcript
    transcript_text = "\n\n".join([
        f"{'Agent' if t['role'] == 'assistant' else 'Caller'}: {t['content']}"
        for t in transcript
    ])

    # Build evaluation prompt
    expected_behaviors = "\n".join([f"- {b}" for b in scenario.get("expected_behavior", [])])

    evaluation_prompt = f"""Evaluate this voice AI agent conversation against the following criteria:

SCENARIO: {scenario['name']}
DESCRIPTION: {scenario['description']}

EXPECTED BEHAVIORS:
{expected_behaviors}

TRANSCRIPT:
{transcript_text}

Please evaluate the agent's performance on a 0-100 scale based on:
1. Did the agent demonstrate the expected behaviors?
2. Was the conversation professional and helpful?
3. Did the agent stay on track and avoid loops?
4. Was the resolution appropriate for the scenario?

Provide your response in JSON format:
{{
    "score": <0-100>,
    "analysis": "<2-3 sentence overall analysis>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "weaknesses": ["<weakness 1>", "<weakness 2>"],
    "met_expectations": <true/false>
}}"""

    # Call Claude
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not set, using conservative fallback score")
        return 50, {
            "score": 50,
            "analysis": "Evaluation unavailable (API key not configured)",
            "strengths": [],
            "weaknesses": ["Cannot evaluate - API key missing"],
            "met_expectations": False
        }

    try:
        claude = anthropic.Anthropic(api_key=anthropic_api_key)

        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": evaluation_prompt
            }]
        )

        # Parse response
        response_text = response.content[0].text

        # Extract JSON (Claude might wrap it in markdown)
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            # Try to extract any code block
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        analysis = json.loads(response_text)

        return analysis["score"], analysis

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude evaluation response: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        # Fallback to conservative score
        return 50, {
            "score": 50,
            "analysis": "Evaluation parsing failed",
            "strengths": [],
            "weaknesses": ["Unable to parse evaluation"],
            "met_expectations": False
        }

    except Exception as e:
        logger.error(f"Claude evaluation error: {e}")
        # Fallback to conservative score
        return 50, {
            "score": 50,
            "analysis": f"Evaluation error: {str(e)}",
            "strengths": [],
            "weaknesses": ["Evaluation failed"],
            "met_expectations": False
        }


async def generate_simulation_report(simulation_id: int) -> str:
    """Generate a human-readable markdown report for a simulation"""

    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT scenario_name, call_id, turn_count, tool_score,
                   behavior_score, overall_score, evaluation_details, transcript
            FROM gigi_simulations WHERE id = %s
        """, (simulation_id,))

        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return "Simulation not found"

    scenario_name, call_id, turns, tool_score, behavior_score, overall_score, details_raw, transcript = row
    # psycopg2 auto-parses JSONB columns — only json.loads() if it's still a string
    if details_raw is None:
        details = {}
    elif isinstance(details_raw, dict):
        details = details_raw
    else:
        details = json.loads(details_raw)

    # Generate report
    status_emoji = "✅" if overall_score >= 70 else "⚠️" if overall_score >= 50 else "❌"
    pass_fail = "PASS" if overall_score >= 70 else "FAIL"

    report = f"""# Simulation Report: {scenario_name}

{status_emoji} **Overall Score: {overall_score}/100** {'(PASS)' if overall_score >= 70 else '(FAIL)'}

## Metrics
- **Conversation Length**: {turns} turns
- **Tool Score**: {tool_score}/100
- **Behavior Score**: {behavior_score}/100

## Tool Usage
- **Expected**: {', '.join(details.get('tools_expected', [])) or 'None'}
- **Used**: {', '.join(details.get('tools_used', [])) or 'None'}
{f"- **Missing**: {', '.join(details.get('tools_missing', []))}" if details.get('tools_missing') else ''}
{f"- **Extra**: {', '.join(details.get('tools_extra', []))}" if details.get('tools_extra') else ''}

## Behavior Analysis
{details.get('behavior_analysis', 'N/A')}

### Strengths
{chr(10).join(['- ' + s for s in details.get('strengths', [])]) if details.get('strengths') else '- None identified'}

### Weaknesses
{chr(10).join(['- ' + w for w in details.get('weaknesses', [])]) if details.get('weaknesses') else '- None identified'}

## Transcript
{transcript or 'Not available'}

---

**Call ID**: {call_id}
**Generated**: {os.environ.get('TZ', 'UTC')} - {chr(169)} Colorado Care Assist 2026
"""

    return report
