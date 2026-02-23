"""
Claude Code CLI tools for Gigi — shared async business logic.

Two tools:
  run_claude_code    — code/infra tasks via Claude Code CLI
  browse_with_claude — browser automation via Claude Code + Chrome extension

All functions are ASYNC (asyncio.create_subprocess_exec).
All functions return dicts — callers json.dumps() the result.
"""

import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger("gigi.claude_code")

CLAUDE_PATH = "/Users/shulmeister/.local/bin/claude"

ALLOWED_DIRS = {
    "careassist": "/Users/shulmeister/mac-mini-apps/careassist-staging",
    "staging": "/Users/shulmeister/mac-mini-apps/careassist-staging",
    "production": "/Users/shulmeister/mac-mini-apps/careassist-unified",
    "website": "/Users/shulmeister/mac-mini-apps/coloradocareassist",
    "hesed": "/Users/shulmeister/mac-mini-apps/hesedhomecare",
    "trading": "/Users/shulmeister/mac-mini-apps/elite-trading-mcp",
    "weather-arb": "/Users/shulmeister/mac-mini-apps/weather-arb",
    "kalshi": "/Users/shulmeister/mac-mini-apps/kalshi-weather",
    "powderpulse": "/Users/shulmeister/mac-mini-apps/powderpulse",
    "employee-portal": "/Users/shulmeister/mac-mini-apps/employee-portal",
    "client-portal": "/Users/shulmeister/mac-mini-apps/client-portal",
    "status-dashboard": "/Users/shulmeister/mac-mini-apps/status-dashboard",
    "qbo-dashboard": "/Users/shulmeister/mac-mini-apps/qbo-dashboard",
}

DEFAULT_BUDGET_CODE = 5.0      # USD per run_claude_code invocation
DEFAULT_BUDGET_BROWSE = 2.0    # USD per browse_with_claude invocation
MAX_BUDGET = 10.0              # Hard cap
DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT = 120          # seconds
MAX_RESULT_LEN = 4000          # Truncate result for LLM context

SAFETY_PROMPT = """SAFETY CONSTRAINTS (non-negotiable):
- NEVER send SMS, text messages, emails, or make phone calls.
- NEVER use the RingCentral API. NEVER import or call any SMS/email sending functions.
- If asked to send a message to someone, REFUSE.
- You may READ code, EDIT code, RUN tests, and RESTART services.
- Prefer staging over production unless the prompt explicitly says 'production'.
- When done, provide a clear summary of what you did and the result."""

BROWSER_CREDENTIAL_PROMPT = """CREDENTIAL ACCESS (1Password CLI):
You have access to the 1Password CLI (`op`) for logging into websites on Jason's behalf.
To retrieve credentials for any site:
  op item get "<site name>" --fields username,password --format json
Examples:
  op item get "United Airlines" --fields username,password --format json
  op item get "Hertz" --fields username,password --format json
  op item get "OpenTable" --fields username,password --format json
  op item get "Delta Airlines" --fields username,password --format json
You can also search: op item list --categories Login | grep -i "<keyword>"
Use these credentials to log into sites when the task requires authentication.
NEVER display or echo passwords in output — use them only for form input."""


def _resolve_directory(directory: Optional[str]) -> str:
    """Resolve a directory alias or path to an absolute path."""
    if not directory:
        return ALLOWED_DIRS["careassist"]
    key = directory.lower().strip()
    if key in ALLOWED_DIRS:
        return ALLOWED_DIRS[key]
    # Accept full paths within the allowed parent
    if directory.startswith("/Users/shulmeister/mac-mini-apps/") and os.path.isdir(directory):
        return directory
    return ALLOWED_DIRS["careassist"]


def _clean_env() -> dict:
    """Return os.environ copy with Claude nesting vars stripped."""
    return {k: v for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}


async def _run_cli(
    prompt: str,
    cwd: str,
    budget: float,
    model: str,
    timeout: int,
    chrome: bool = False,
) -> dict:
    """Low-level: invoke Claude Code CLI and return parsed result."""
    if not os.path.exists(CLAUDE_PATH):
        return {"error": f"Claude Code CLI not found at {CLAUDE_PATH}"}

    cmd = [
        CLAUDE_PATH, "-p",
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--max-budget-usd", str(min(budget, MAX_BUDGET)),
        "--model", model,
        "--no-session-persistence",
    ]
    if chrome:
        cmd.append("--chrome")
    cmd.append(prompt)

    logger.info(f"Claude Code: model={model} budget=${budget} chrome={chrome} cwd={cwd}")
    logger.info(f"Claude Code prompt: {prompt[:200]}...")

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_clean_env(),
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if process.returncode == 0 and stdout_text:
            try:
                parsed = json.loads(stdout_text)
                result_text = parsed.get("result", stdout_text)
                if len(result_text) > MAX_RESULT_LEN:
                    result_text = result_text[:MAX_RESULT_LEN] + "\n\n[truncated]"
                return {
                    "success": True,
                    "result": result_text,
                    "cost_usd": parsed.get("cost_usd", 0),
                    "duration_ms": parsed.get("duration_ms", 0),
                    "num_turns": parsed.get("num_turns", 0),
                }
            except json.JSONDecodeError:
                result_text = stdout_text
                if len(result_text) > MAX_RESULT_LEN:
                    result_text = result_text[:MAX_RESULT_LEN] + "\n\n[truncated]"
                return {"success": True, "result": result_text}
        else:
            error_msg = stderr_text or stdout_text or f"Exit code {process.returncode}"
            if len(error_msg) > 1000:
                error_msg = error_msg[:1000] + "..."
            return {"success": False, "error": error_msg}

    except asyncio.TimeoutError:
        if process:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
        logger.warning(f"Claude Code timed out after {timeout}s")
        return {"success": False, "error": f"Timed out after {timeout}s", "timed_out": True}
    except Exception as e:
        logger.error(f"Claude Code error: {e}")
        return {"success": False, "error": str(e)}


async def run_claude_code(
    prompt: str,
    directory: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict:
    """Run a code/infra task via Claude Code CLI. Returns dict with result."""
    cwd = _resolve_directory(directory)
    full_prompt = f"{prompt}\n\n{SAFETY_PROMPT}"
    return await _run_cli(
        prompt=full_prompt,
        cwd=cwd,
        budget=DEFAULT_BUDGET_CODE,
        model=model or DEFAULT_MODEL,
        timeout=timeout or DEFAULT_TIMEOUT,
    )


async def browse_with_claude(
    task: str,
    url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict:
    """Browse a webpage / do browser automation via Claude Code + Chrome."""
    parts = [task]
    if url:
        parts.append(f"\nTarget URL: {url}")
    parts.append("\nUse the Chrome browser to complete this task.")
    parts.append(BROWSER_CREDENTIAL_PROMPT)
    parts.append(SAFETY_PROMPT)

    return await _run_cli(
        prompt="\n".join(parts),
        cwd=ALLOWED_DIRS["careassist"],
        budget=DEFAULT_BUDGET_BROWSE,
        model=DEFAULT_MODEL,
        timeout=timeout or DEFAULT_TIMEOUT,
        chrome=True,
    )
