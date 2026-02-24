"""
GAM (Google Admin Manager) tools for Gigi — READ-ONLY.

Gigi can query Google Workspace admin data via GAM CLI.
All commands are strictly read-only (print, info, show, report).
Write operations (create, update, delete, suspend) are BLOCKED.

Claude Code has full GAM access — only Gigi is restricted.
"""

import asyncio
import logging

logger = logging.getLogger("gigi.gam_tools")

GAM_PATH = "/Users/shulmeister/bin/gam7/gam"

# Only these GAM verbs are allowed — everything else is blocked
ALLOWED_VERBS = frozenset({
    "info", "print", "show", "report", "check", "count",
    "list", "version",
})

# Explicit blocklist for safety — these can never run
BLOCKED_VERBS = frozenset({
    "create", "update", "delete", "remove", "suspend", "unsuspend",
    "deprovision", "modify", "add", "set", "wipe", "move",
    "transfer", "undelete", "approve", "deny", "revoke",
    "reset", "changepassword", "oauth",
})

MAX_OUTPUT_LEN = 4000
TIMEOUT = 30  # seconds


def _validate_command(command: str) -> str | None:
    """Validate a GAM command is read-only. Returns error message or None if OK."""
    parts = command.strip().split()
    if not parts:
        return "Empty command"

    # Strip leading "gam" if user included it
    if parts[0].lower() == "gam":
        parts = parts[1:]
    if not parts:
        return "Empty command after 'gam'"

    # Find the verb — skip target specifiers like "user x@y.com" or "all users"
    verb = None
    i = 0
    while i < len(parts):
        word = parts[i].lower()
        # Skip target specifiers
        if word in ("user", "users", "group", "groups", "ou", "org",
                     "domain", "domains", "cros", "mobile", "resource",
                     "all", "customer"):
            i += 2 if word != "all" else 1
            continue
        verb = word
        break

    if not verb:
        return f"Could not identify verb in: {command}"

    if verb in BLOCKED_VERBS:
        return f"BLOCKED: '{verb}' is a write operation. Gigi has read-only GAM access."

    if verb not in ALLOWED_VERBS:
        return f"BLOCKED: '{verb}' is not in the allowed read-only verb list."

    return None


async def query_workspace(command: str) -> dict:
    """
    Run a read-only GAM command and return the output.

    Args:
        command: GAM command WITHOUT the leading 'gam' (e.g. 'info user jacob@coloradocareassist.com')

    Returns:
        dict with 'success' and 'result' or 'error'
    """
    # Validate read-only
    error = _validate_command(command)
    if error:
        logger.warning(f"GAM blocked: {error} | command: {command}")
        return {"success": False, "error": error}

    # Strip leading "gam" if included
    parts = command.strip().split()
    if parts and parts[0].lower() == "gam":
        parts = parts[1:]

    cmd = [GAM_PATH] + parts
    logger.info(f"GAM query: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=TIMEOUT
        )

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        # GAM often writes progress to stderr even on success
        output = stdout_text or stderr_text
        if len(output) > MAX_OUTPUT_LEN:
            output = output[:MAX_OUTPUT_LEN] + "\n\n[truncated]"

        if process.returncode == 0:
            return {"success": True, "result": output}
        else:
            return {
                "success": False,
                "error": stderr_text[:1000] if stderr_text else f"Exit code {process.returncode}",
                "partial_output": stdout_text[:1000] if stdout_text else None,
            }

    except asyncio.TimeoutError:
        logger.warning(f"GAM timed out after {TIMEOUT}s: {command}")
        return {"success": False, "error": f"Timed out after {TIMEOUT}s"}
    except Exception as e:
        logger.error(f"GAM error: {e}")
        return {"success": False, "error": str(e)}
