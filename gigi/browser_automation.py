"""
Gigi Browser Automation — redirects to Claude Code + Chrome.

Legacy Playwright code has been removed. All browser tasks now route through
browse_with_claude (claude_code_tools.py) which uses Claude Code CLI + --chrome flag.

The get_browser() / BrowserAutomation interface is preserved as a thin shim
so any remaining callers don't crash on import.
"""

import logging

logger = logging.getLogger("gigi.browser")


class BrowserAutomation:
    """Shim that redirects browse/screenshot calls to browse_with_claude."""

    async def browse_webpage(self, url: str, extract_links: bool = False,
                              max_length: int = 4000) -> dict:
        from gigi.claude_code_tools import browse_with_claude
        result = await browse_with_claude(
            task=f"Navigate to {url} and extract the main text content of the page.",
            url=url,
        )
        return result

    async def take_screenshot(self, url: str, full_page: bool = False) -> dict:
        from gigi.claude_code_tools import browse_with_claude
        result = await browse_with_claude(
            task=f"Navigate to {url} and take a screenshot. Describe what the page looks like.",
            url=url,
        )
        return result

    async def close(self):
        pass


_browser = None


def get_browser() -> BrowserAutomation:
    """Get the shared browser automation instance."""
    global _browser
    if _browser is None:
        _browser = BrowserAutomation()
    return _browser
