#!/usr/bin/env python3
"""Click all task checkboxes on WellSky dashboard. Tasks disappear when checked."""

import time

from playwright.sync_api import sync_playwright

URL = "https://colcareassist.clearcareonline.com/dashboard/"
PROFILE = "/Users/shulmeister/.wellsky-playwright-profile"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=False, viewport={"width": 1400, "height": 900})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=60000)
    time.sleep(3)

    if "login" in page.url:
        print("Not logged in. Log in manually, then re-run.")
        time.sleep(30)
        ctx.close()
        exit()

    # Debug: what's on the page
    info = page.evaluate("""() => ({
        url: location.href,
        allCB: document.querySelectorAll("input[type='checkbox']").length,
        unchecked: document.querySelectorAll("input[type='checkbox']:not(:checked)").length,
        pTask: document.querySelectorAll("p.task").length,
        pTaskCB: document.querySelectorAll("p.task input[type='checkbox']").length,
        panelPTaskCB: document.querySelectorAll("#tasks-panel p.task input[type='checkbox']").length,
        tasksPanelExists: !!document.querySelector("#tasks-panel"),
        bodySnippet: document.querySelector("#tasks-panel") ? document.querySelector("#tasks-panel").innerHTML.substring(0, 500) : "NO PANEL",
    })""")
    print(f"Debug: {info}")

    total = 0
    while True:
        # Use broadest selector that targets task checkboxes
        cbs = page.query_selector_all("p.task input[type='checkbox']:not(:checked)")
        if not cbs:
            # Try next page
            nxt = page.query_selector("a:has-text('»')")
            if nxt and nxt.is_visible():
                nxt.click()
                time.sleep(1.5)
                continue
            break

        for cb in cbs:
            try:
                cb.click()
                total += 1
                time.sleep(0.3)
            except Exception:
                pass

        print(f"Checked {total} so far...")
        time.sleep(1)

    print(f"Done. {total} tasks checked off.")
    ctx.close()
