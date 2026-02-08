"""
Gigi Browser Automation — Playwright-based headless Chromium.

Provides tools for:
- Browsing webpages and extracting content (research, reading articles)
- Taking screenshots of any URL
- WellSky web UI automation (when credentials are configured)

All methods are async-safe and use a shared browser instance.
"""

import os
import asyncio
import logging
import tempfile
from typing import Optional
from datetime import datetime

logger = logging.getLogger("gigi.browser")

# WellSky web credentials (configure when available)
WELLSKY_WEB_URL = os.getenv("WELLSKY_WEB_URL", "")
WELLSKY_WEB_USER = os.getenv("WELLSKY_WEB_USER", "")
WELLSKY_WEB_PASS = os.getenv("WELLSKY_WEB_PASS", "")

# Screenshot storage
SCREENSHOT_DIR = os.path.expanduser("~/logs/screenshots")


class BrowserAutomation:
    """Shared headless browser for Gigi's web automation tasks."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        """Lazy-initialize the browser (first use only)."""
        if self._browser and self._browser.is_connected():
            return
        async with self._lock:
            if self._browser and self._browser.is_connected():
                return
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-gpu"],
                )
                logger.info("Browser automation: Chromium launched")
            except Exception as e:
                logger.error(f"Failed to launch browser: {e}")
                raise

    async def browse_webpage(self, url: str, extract_links: bool = False,
                              max_length: int = 4000) -> dict:
        """
        Navigate to a URL and extract the page content as text.

        Useful for research, reading articles, checking websites.

        Args:
            url: The URL to browse
            extract_links: If True, also extract all links on the page
            max_length: Maximum characters of text to return

        Returns:
            dict with title, text, url, and optionally links
        """
        await self._ensure_browser()
        page = await self._browser.new_page()
        try:
            page.set_default_timeout(15000)
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1000)  # Let JS render

            title = await page.title()

            # Extract main text content (strip nav, scripts, etc.)
            text = await page.evaluate("""() => {
                // Remove script, style, nav, footer, header elements
                const remove = document.querySelectorAll('script, style, nav, footer, header, iframe, noscript');
                remove.forEach(el => el.remove());

                // Try to find main content
                const main = document.querySelector('main, article, [role="main"], .content, #content');
                const source = main || document.body;
                return source ? source.innerText.trim() : '';
            }""")

            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "\n...(truncated)"

            result = {
                "title": title,
                "url": str(page.url),
                "text": text,
                "length": len(text),
            }

            if extract_links:
                links = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({text: a.innerText.trim(), href: a.href}))
                        .filter(l => l.text && l.href.startsWith('http'))
                        .slice(0, 20);
                }""")
                result["links"] = links

            return result

        except Exception as e:
            logger.error(f"Browse error for {url}: {e}")
            return {"error": str(e), "url": url}
        finally:
            await page.close()

    async def take_screenshot(self, url: str, full_page: bool = False) -> dict:
        """
        Take a screenshot of a webpage.

        Args:
            url: The URL to screenshot
            full_page: If True, capture the full scrollable page

        Returns:
            dict with file_path and metadata
        """
        await self._ensure_browser()
        page = await self._browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.set_default_timeout(15000)
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)  # Let page fully render

            # Create screenshot directory
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize URL for filename
            safe_name = url.split("//")[-1].split("/")[0].replace(".", "_")
            file_path = os.path.join(SCREENSHOT_DIR, f"{safe_name}_{timestamp}.png")

            await page.screenshot(path=file_path, full_page=full_page)
            title = await page.title()

            logger.info(f"Screenshot saved: {file_path}")
            return {
                "file_path": file_path,
                "title": title,
                "url": str(page.url),
                "full_page": full_page,
            }

        except Exception as e:
            logger.error(f"Screenshot error for {url}: {e}")
            return {"error": str(e), "url": url}
        finally:
            await page.close()

    async def close(self):
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


# Singleton instance
_browser = None


def get_browser() -> BrowserAutomation:
    """Get the shared browser automation instance."""
    global _browser
    if _browser is None:
        _browser = BrowserAutomation()
    return _browser
