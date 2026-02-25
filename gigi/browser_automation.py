"""
Gigi Browser Automation — @playwright/mcp via JSON-RPC stdio.

Replaces the old browse_with_claude shim ($2/call, 120s timeout) with
a direct Playwright MCP subprocess. Each call spawns @playwright/mcp,
does the MCP handshake, runs the task, then exits.

Tools provided to Gigi:
  browse_webpage(url)  → navigate + accessibility snapshot (text)
  take_screenshot(url) → navigate + screenshot description
"""

import asyncio
import json
import logging
import os

logger = logging.getLogger("gigi.browser")

NPX_PATH = "/opt/homebrew/bin/npx"
MAX_CONTENT = 4000
STARTUP_TIMEOUT = 20   # seconds to wait for MCP handshake
TOOL_TIMEOUT = 30      # seconds per tool call
NAV_TIMEOUT = 60       # seconds for page navigation


class _MCPClient:
    """Single-use @playwright/mcp subprocess client (per request)."""

    def __init__(self):
        self._proc = None
        self._reader_task = None
        self._pending: dict[int, asyncio.Future] = {}
        self._seq = 0

    def _new_id(self) -> int:
        self._seq += 1
        loop = asyncio.get_running_loop()
        self._pending[self._seq] = loop.create_future()
        return self._seq

    async def start(self):
        """Spawn @playwright/mcp and complete MCP handshake."""
        self._proc = await asyncio.create_subprocess_exec(
            NPX_PATH, "@playwright/mcp",
            "--headless",
            "--isolated",
            "--no-sandbox",
            "--snapshot-mode", "full",
            "--timeout-navigation", str(NAV_TIMEOUT * 1000),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,  # PIPE would block if stderr fills up
            env=os.environ.copy(),
        )
        self._reader_task = asyncio.create_task(self._read_loop())

        req_id = self._new_id()
        await self._write({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gigi", "version": "1.0"},
            },
        })
        await asyncio.wait_for(self._pending[req_id], timeout=STARTUP_TIMEOUT)

        # Send initialized notification (no id — it's a notification)
        await self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def call_tool(self, name: str, arguments: dict, timeout: float = TOOL_TIMEOUT) -> dict:
        req_id = self._new_id()
        await self._write({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        try:
            result = await asyncio.wait_for(self._pending[req_id], timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)  # clean up leaked future
            raise
        return result or {}

    async def _write(self, obj: dict):
        line = (json.dumps(obj) + "\n").encode()
        self._proc.stdin.write(line)
        await self._proc.stdin.drain()

    async def _read_loop(self):
        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode().strip())
                except (json.JSONDecodeError, ValueError):
                    continue
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        if "error" in msg:
                            fut.set_exception(
                                RuntimeError(msg["error"].get("message", "MCP error"))
                            )
                        else:
                            fut.set_result(msg.get("result"))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"MCP reader loop exited: {e}")

    async def close(self):
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._proc:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=3)
            except (asyncio.TimeoutError, Exception):
                try:
                    self._proc.kill()
                    await self._proc.wait()  # reap zombie
                except Exception:
                    pass


def _extract_text(result: dict, max_length: int = MAX_CONTENT) -> str:
    """Pull text content from a tools/call result."""
    content = result.get("content", [])
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    text = "\n".join(parts).strip()
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[truncated]"
    return text


async def _run_browser_task(task_fn) -> dict:
    """Helper: start client, run task_fn(client), close client."""
    client = _MCPClient()
    try:
        await client.start()
        return await task_fn(client)
    except asyncio.TimeoutError:
        logger.warning("Browser task timed out")
        return {"success": False, "error": "Timed out"}
    except Exception as e:
        logger.error(f"Browser task error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await client.close()


class BrowserAutomation:
    """Playwright-backed browser automation via @playwright/mcp."""

    async def browse_webpage(self, url: str, extract_links: bool = False,
                              max_length: int = MAX_CONTENT) -> dict:
        async def task(client: _MCPClient) -> dict:
            await client.call_tool("browser_navigate", {"url": url}, timeout=NAV_TIMEOUT + 5)
            result = await client.call_tool("browser_snapshot", {})
            content = _extract_text(result, max_length)
            return {"success": True, "content": content, "url": url}

        logger.info(f"browse_webpage: {url}")
        return await _run_browser_task(task)

    async def take_screenshot(self, url: str, full_page: bool = False) -> dict:
        async def task(client: _MCPClient) -> dict:
            await client.call_tool("browser_navigate", {"url": url}, timeout=NAV_TIMEOUT + 5)
            result = await client.call_tool("browser_take_screenshot", {})
            description = _extract_text(result)
            return {"success": True, "description": description, "url": url}

        logger.info(f"take_screenshot: {url}")
        return await _run_browser_task(task)

    async def close(self):
        pass  # Clients are per-call, nothing persistent to close


_browser = None


def get_browser() -> BrowserAutomation:
    """Get the shared browser automation instance."""
    global _browser
    if _browser is None:
        _browser = BrowserAutomation()
    return _browser
