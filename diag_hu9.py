#!/usr/bin/env python3
"""Diagnostic: test HU9 URLs from this environment."""
import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        await ctx.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
        page = await ctx.new_page()

        urls = [
            "https://my-site-nek40ye0-swingerspridegc.wix-vibe-site.com/events",
            "https://hu9swingersclub.co.uk/events",
            "https://www.skiddle.com/whats-on/Hull/Hu9-Club/",
            "https://www.purplemambaclub.com/what-s-on-tickets",
        ]

        results = {}
        for url in urls:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
            html = await page.content()
            text = await page.inner_text("body")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            results[url] = {
                "status": resp.status if resp else "none",
                "html_len": len(html),
                "text_lines": len(lines),
                "first_300": text[:300],
            }
            print(f"\n=== {url} ===")
            print(f"  Status: {resp.status if resp else 'none'}")
            print(f"  HTML: {len(html)} chars, text lines: {len(lines)}")
            print(f"  First 300: {text[:300]}")
            sys.stdout.flush()

        await browser.close()

asyncio.run(main())
