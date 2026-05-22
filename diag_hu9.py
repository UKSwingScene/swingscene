#!/usr/bin/env python3
"""Diagnostic 3: expand future months in HU9 calendar."""
import asyncio, re, sys
from playwright.async_api import async_playwright

async def get_lines(page):
    text = await page.inner_text("body")
    return [l.strip() for l in text.split("\n") if l.strip()]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        await page.goto("https://my-site-nek40ye0-swingerspridegc.wix-vibe-site.com/events",
                        wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        # Click age gate
        try:
            await page.get_by_text("I Confirm").first.click()
            await page.wait_for_timeout(3000)
            print("Age gate clicked")
        except Exception as e:
            print(f"Age gate: {e}")

        lines = await get_lines(page)
        months_seen = [l for l in lines if re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$", l, re.I)]
        print(f"Months visible: {months_seen}")

        # Try clicking each future month header
        for month_text in months_seen:
            try:
                els = await page.get_by_text(month_text, exact=True).all()
                print(f"\nClicking '{month_text}' ({len(els)} elements)")
                for el in els:
                    try:
                        await el.click()
                        await page.wait_for_timeout(2000)
                        break
                    except: pass
            except Exception as e:
                print(f"  click error: {e}")

        # Also try clicking "next month" arrow buttons
        for sel in ["button[aria-label*='next']", "button[aria-label*='Next']",
                    "[class*='next']", "[class*='arrow']", "button:has-text('>')"]:
            btns = await page.query_selector_all(sel)
            if btns:
                print(f"\nFound {len(btns)} buttons with {sel!r}")
                for b in btns[:1]:
                    print(f"  text: {await b.inner_text()}")

        # After clicking, get all lines
        await page.wait_for_timeout(2000)
        lines2 = await get_lines(page)
        print(f"\n=== FULL TEXT AFTER CLICKS ({len(lines2)} lines) ===")
        for i, l in enumerate(lines2):
            print(f"[{i:03d}] {l}")

        await browser.close()

asyncio.run(main())
