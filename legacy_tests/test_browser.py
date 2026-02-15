import asyncio
from playwright.async_api import async_playwright
import os

async def test_browser():
    print("🚀 TESTING GIGI BROWSER ENGINE...")
    async with async_playwright() as p:
        # Use Chromium
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("🌍 Navigating to Google...")
        await page.goto("https://www.google.com")
        
        # Take a test screenshot
        screenshot_path = "/Users/shulmeister/browser_test.png"
        await page.screenshot(path=screenshot_path)
        
        print(f"📸 Screenshot saved to {screenshot_path}")
        await browser.close()
        print("✅ BROWSER TEST SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(test_browser())
