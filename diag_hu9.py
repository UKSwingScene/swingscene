#!/usr/bin/env python3
"""Diagnostic 2: click age gate, dump all event text from HU9."""
import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        await page.goto("https://my-site-nek40ye0-swingerspridegc.wix-vibe-site.com/events",
                        wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Click age gate
        try:
            btn = await page.get_by_text("I Confirm").first.element_handle()
            if btn:
                await btn.click()
                print("Clicked I Confirm")
                await page.wait_for_timeout(4000)
        except Exception as e:
            print(f"Age gate click failed: {e}")

        # Try load more
        try:
            more = await page.query_selector('[data-hook="load-more-button"]')
            if more: await more.click(); await page.wait_for_timeout(2000); print("Clicked load-more")
        except: pass

        html = await page.content()
        text = await page.inner_text("body")
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        print(f"\nHTML length: {len(html)}")
        print(f"Text lines: {len(lines)}")
        print("\n=== ALL BODY TEXT ===")
        for i, l in enumerate(lines):
            print(f"[{i:03d}] {l}")

        # Check for event selectors
        for sel in ['[data-hook="event-list-item"]', '[class*="EventListItem"]',
                    '[class*="event-list"]', "article", '[data-hook="events-widget"]']:
            els = await page.query_selector_all(sel)
            if els:
                print(f"\nSelector {sel!r}: {len(els)} elements")
                for el in els[:3]:
                    print(f"  text: {(await el.inner_text())[:200]}")

        await browser.close()

asyncio.run(main())
