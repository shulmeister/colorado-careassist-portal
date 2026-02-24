"""
Headless Terminal tools for Gigi — wraps ht-mcp (JSON-RPC 2.0 over stdio).

Provides direct terminal access for fast, zero-cost command execution.
Use for quick commands (logs, restarts, git, file checks). Heavy tasks
still go through run_claude_code.

All functions are ASYNC. All functions return dicts — callers json.dumps().
"""

import asyncio
import json
import logging
import re
from typing import Optional

logger = logging.getLogger("gigi.terminal")

HT_MCP_PATH = "/opt/homebrew/bin/ht-mcp"
MAX_OUTPUT_LEN = 4000
DEFAULT_TIMEOUT = 30  # seconds
SESSION_IDLE_TIMEOUT = 300  # close session after 5 min idle

# Commands that should never run from Gigi
BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/",         # rm -rf /
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",              # dd if=
    r":\(\)\s*\{",              # fork bomb
    r"\bchmod\s+-R\s+777\s+/",  # chmod -R 777 /
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+reset\s+--hard",
    r"\bop\s+item\s+",          # 1Password CLI (don't leak secrets)
    r"\bcurl\s+.*\|\s*sh",      # curl | sh
    r"\bwget\s+.*\|\s*sh",
]

BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


def _is_blocked(command: str) -> Optional[str]:
    """Check if a command matches a blocked pattern. Returns reason or None."""
    for pattern in BLOCKED_RE:
        if pattern.search(command):
            return f"Blocked: command matches safety pattern '{pattern.pattern}'"
    return None


class HtMcpClient:
    """Async wrapper for ht-mcp headless terminal server (JSON-RPC 2.0 over stdio)."""

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._session_id: Optional[str] = None
        self._request_id: int = 0
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_started(self):
        """Start ht-mcp process and initialize MCP protocol if needed."""
        if self._process and self._process.returncode is None:
            return

        import shutil
        if not shutil.which("ht-mcp") and not __import__("os").path.exists(HT_MCP_PATH):
            raise RuntimeError(f"ht-mcp not found at {HT_MCP_PATH}")

        self._process = await asyncio.create_subprocess_exec(
            HT_MCP_PATH,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._initialized = False
        self._session_id = None

        # MCP initialize handshake
        resp = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "gigi-terminal", "version": "1.0.0"},
        })
        if not resp:
            raise RuntimeError("ht-mcp initialize failed")

        # Send initialized notification (no response expected)
        await self._send_notification("notifications/initialized")
        self._initialized = True
        logger.info("ht-mcp process started and initialized")

    async def _ensure_session(self):
        """Create a terminal session if we don't have one."""
        await self._ensure_started()
        if self._session_id:
            return

        resp = await self._send_request("tools/call", {
            "name": "ht_create_session",
            "arguments": {"command": ["zsh", "--no-rcs"], "enableWebServer": False},
        })

        # Parse session ID from text response
        text = self._extract_text(resp)
        if not text:
            raise RuntimeError("Failed to create ht-mcp session")

        # Session ID is in the text like "Session ID: abc123..."
        for line in text.split("\n"):
            if "Session ID:" in line:
                self._session_id = line.split("Session ID:")[-1].strip()
                break

        if not self._session_id:
            # Try to find UUID pattern
            import re as _re
            match = _re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text)
            if match:
                self._session_id = match.group(0)

        if not self._session_id:
            raise RuntimeError(f"Could not parse session ID from: {text[:200]}")

        logger.info(f"ht-mcp session created: {self._session_id}")

    async def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            return None

        self._request_id += 1
        msg = json.dumps({
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }) + "\n"

        self._process.stdin.write(msg.encode())
        await self._process.stdin.drain()

        # Read response line
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            if not line:
                return None
            return json.loads(line.decode().strip())
        except asyncio.TimeoutError:
            logger.warning(f"ht-mcp request timed out: {method}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"ht-mcp bad JSON response: {e}")
            return None

    async def _send_notification(self, method: str, params: dict = None):
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return

        msg = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            **({"params": params} if params else {}),
        }) + "\n"

        self._process.stdin.write(msg.encode())
        await self._process.stdin.drain()
        # Small delay for server to process
        await asyncio.sleep(0.1)

    @staticmethod
    def _extract_text(resp: Optional[dict]) -> Optional[str]:
        """Extract text content from MCP tool response."""
        if not resp:
            return None
        result = resp.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list):
            raw = content[0].get("text", "")
            return HtMcpClient._clean_output(raw)
        # Check for error
        error = resp.get("error")
        if error:
            return f"Error: {error.get('message', str(error))}"
        return None

    @staticmethod
    def _clean_output(text: str) -> str:
        """Clean terminal snapshot output — strip padding, collapse blanks."""
        lines = text.split("\n")
        # Strip trailing whitespace from each line
        lines = [line.rstrip() for line in lines]
        # Collapse multiple consecutive blank lines into one
        cleaned = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    cleaned.append("")
                prev_blank = True
            else:
                cleaned.append(line)
                prev_blank = False
        # Strip leading/trailing blank lines
        result = "\n".join(cleaned).strip()
        return result

    async def execute_command(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        """Execute a command in the terminal and return output.

        Uses ht_execute_command which sends the command + waits 1s + snapshots.
        For commands that take longer, we do additional snapshots.
        """
        async with self._lock:
            try:
                await self._ensure_session()

                resp = await self._send_request("tools/call", {
                    "name": "ht_execute_command",
                    "arguments": {
                        "sessionId": self._session_id,
                        "command": command,
                    },
                })

                text = self._extract_text(resp)
                if text is None:
                    return {"error": "No response from terminal"}

                # Truncate if too long
                if len(text) > MAX_OUTPUT_LEN:
                    text = text[:MAX_OUTPUT_LEN] + "\n\n[truncated]"

                return {"success": True, "output": text}

            except Exception as e:
                logger.error(f"Terminal execute failed: {e}")
                # Reset session on error
                self._session_id = None
                return {"error": str(e)}

    async def close(self):
        """Close session and terminate ht-mcp process."""
        if self._session_id and self._process:
            try:
                await self._send_request("tools/call", {
                    "name": "ht_close_session",
                    "arguments": {"sessionId": self._session_id},
                })
            except Exception:
                pass
            self._session_id = None

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
            self._initialized = False


# Module-level singleton
_client: Optional[HtMcpClient] = None


async def _get_client() -> HtMcpClient:
    """Get or create the singleton HtMcpClient."""
    global _client
    if _client is None:
        _client = HtMcpClient()
    return _client


async def run_terminal(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Run a terminal command via ht-mcp. Returns dict with output.

    This is the main entry point called from execute_tool().
    """
    if not command or not command.strip():
        return {"error": "No command provided"}

    # Safety check
    blocked = _is_blocked(command)
    if blocked:
        logger.warning(f"Terminal command blocked: {command}")
        return {"error": blocked}

    logger.info(f"Terminal: {command[:200]}")

    try:
        client = await _get_client()
        result = await asyncio.wait_for(
            client.execute_command(command, timeout=timeout),
            timeout=float(timeout + 10),  # extra buffer for ht-mcp overhead
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Terminal timed out after {timeout}s: {command[:100]}")
        return {"error": f"Command timed out after {timeout}s"}
    except Exception as e:
        logger.error(f"Terminal error: {e}")
        # Reset client on fatal error
        global _client
        if _client:
            await _client.close()
            _client = None
        return {"error": str(e)}
