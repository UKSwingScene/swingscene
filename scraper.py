import asyncio, json, re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

CUTOFF = datetime.now() + timedelta(days=365)
MONTH_MAP = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
MONTH_SHORT = {1:"jan",2:"feb",3:"mar",4:"apr",5:"may",6:"jun",7:"jul",8:"aug",9:"sep",10:"oct",11:"nov",12:"dec"}
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
JUNK = ["cookie","privacy","copyright","menu","home","contact","login","register","search","loading","javascript","please enable","click here","read more","view all","no events","coming soon","sign up","subscribe","follow us","share","tweet","facebook","instagram","terms","conditions","basket","checkout","cart","book now","find out","learn more","get tickets","buy ticket","events found","event name","results found","showing","filter","sort by","clear","back to","next page","previous page","more info","more information","view event","event details","buy now","sold out","free entry","powered by","copyright","all rights"]
TIME_PAT = re.compile(r"^\d{1,2}:\d{2}\s*(am|pm|AM|PM)", re.I)

def parse_date(text):
    text = text.strip()
    pats = [
        r"(\d{1,2})[a-z]{0,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
        r"(\d{1,2})[a-z]{0,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})",
        r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4})",
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
    ]
    for pat in pats:
        m = re.search(pat, text, re.I)
        if m:
            g = m.groups()
            try:
                if g[0].isdigit() and g[1].isdigit():
                    day, month, year = int(g[0]), int(g[1]), int(g[2])
                    if month > 12: day, month = month, day
                elif g[0].isdigit():
                    day, month, year = int(g[0]), MONTH_MAP[g[1].lower()], int(g[2])
                else:
                    month, day, year = MONTH_MAP[g[0].lower()], int(g[1]), int(g[2])
                dt = datetime(year, month, day)
                if datetime.now() <= dt <= CUTOFF:
                    return dt
            except:
                pass
    return None

def make_event(dt, club, city, cls, name, url):
    month_name = dt.strftime("%B")
    day_name = DAYS[dt.weekday()]
    return {
        "d": dt.strftime("%Y-%m-%d"),
        "m": MONTH_SHORT[dt.month],
        "day": f"{day_name} {dt.day} {month_name} {dt.year}",
        "club": club, "city": city, "cls": cls,
        "event": name[:100], "url": url,
        "desc": f"{name} at {club}, {city}. Visit the website for full details."
    }

def is_junk(text):
    t = text.lower().strip()
    if len(t) < 6 or len(t) > 120: return True
    if any(j in t for j in JUNK): return True
    if re.match(r"^[\d\s\-\/\|\.,]+$", t): return True
    if re.match(r"^\d{1,2}:\d{2}", t): return True  # filter time strings
    if re.match(r"^\d{1,2}\/\d{1,2}\/\d{4}", t): return True  # filter date strings
    return False

async def try_wp_api(page, base_url, club, city, cls, events_url):
    try:
        api = base_url.rstrip("/") + "/wp-json/tribe/events/v1/events?per_page=50&start_date=" + datetime.now().strftime("%Y-%m-%d")
        result = await page.evaluate(f'fetch("{api}").then(r=>r.ok?r.json():null).catch(()=>null)')
        if result and isinstance(result, dict) and "events" in result:
            found = []
            for ev in result["events"]:
                try:
                    dt = datetime.fromisoformat(ev["start_date"][:10])
                    if datetime.now() <= dt <= CUTOFF:
                        title = ev.get("title", "").strip()
                        if title and not is_junk(title):
                            found.append(make_event(dt, club, city, cls, title, events_url))
                except:
                    pass
            if found:
                return found
    except:
        pass
    return []

async def scrape_single_page(page, club, city, cls, url):
    """Scrape events from a single already-loaded page."""
    events = []
    try:
        # Try WP API first
        base = re.match(r"(https?://[^/]+)", url)
        if base:
            api_events = await try_wp_api(page, base.group(1), club, city, cls, url)
            if api_events:
                return api_events

        # Try structured event selectors
        for sel in ["article.type-tribe_events", ".tribe-event-url", ".event-item", ".event-card", "[class*='event']"]:
            try:
                items = await page.query_selector_all(sel)
                if 0 < len(items) < 50:
                    for item in items:
                        text = await item.inner_text()
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        dt = None
                        name = None
                        for line in lines:
                            if not dt:
                                dt = parse_date(line)
                            elif not name and not is_junk(line):
                                name = line
                        if dt and name:
                            events.append(make_event(dt, club, city, cls, name, url))
                    if events:
                        return events
            except:
                pass

        # Fall back to full text parse
        text = await page.inner_text("body")
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
        seen = set()
        for i, line in enumerate(lines):
            dt = parse_date(line)
            if not dt:
                continue
            candidates = []
            for j in list(range(max(0,i-5), i)) + list(range(i+1, min(len(lines),i+6))):
                if not parse_date(lines[j]) and not is_junk(lines[j]) and len(lines[j]) > 10:
                    candidates.append(lines[j])
            if not candidates:
                continue
            name = max(candidates, key=len)
            key = (dt.strftime("%Y-%m-%d"), name[:20])
            if key not in seen:
                seen.add(key)
                events.append(make_event(dt, club, city, cls, name, url))
    except Exception as e:
        print(f"  Error on {url}: {e}")
    return events

async def get_next_page_url(page, current_url):
    """Find the next page URL if pagination exists."""
    try:
        # Common pagination patterns
        for sel in [
            "a[rel='next']",
            ".next a", "a.next",
            "[class*='next'] a",
            "a:has-text('Next')",
            "a:has-text('>')",
            ".tribe-events-nav-next a",
            "[class*='pagination'] a[href*='pno=']",
            "[class*='pagination'] a[href*='page=']",
            "[class*='pagination'] a[href*='/page/']",
        ]:
            try:
                el = await page.query_selector(sel)
                if el:
                    href = await el.get_attribute("href")
                    if href and href != current_url and href != "#":
                        if href.startswith("http"):
                            return href
                        base = re.match(r"(https?://[^/]+)", current_url)
                        if base:
                            return base.group(1) + href
            except:
                pass

        # Also check for pno= style pagination in page links
        links = await page.query_selector_all("a[href*='pno='], a[href*='page='], a[href*='/page/']")
        current_page_num = None
        m = re.search(r"pno=(\d+)|page[=/](\d+)", current_url)
        if m:
            current_page_num = int(m.group(1) or m.group(2))
        else:
            current_page_num = 1

        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            m2 = re.search(r"pno=(\d+)|page[=/](\d+)", href)
            if m2:
                page_num = int(m2.group(1) or m2.group(2))
                if page_num == current_page_num + 1:
                    return href if href.startswith("http") else re.match(r"(https?://[^/]+)", current_url).group(1) + href

    except Exception as e:
        print(f"  Pagination check error: {e}")
    return None

async def scrape_page(page, club, city, cls, url):
    """Scrape events from a URL, following pagination automatically."""
    all_events = []
    current_url = url
    pages_visited = 0
    max_pages = 5  # Safety limit

    while current_url and pages_visited < max_pages:
        try:
            print(f"  Page {pages_visited + 1}: {current_url}")
            await page.goto(current_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(3000)

            page_events = await scrape_single_page(page, club, city, cls, current_url)
            print(f"    -> {len(page_events)} events on this page")

            if not page_events and pages_visited > 0:
                # No events on this page, stop paginating
                break

            all_events.extend(page_events)
            pages_visited += 1

            # Look for next page
            next_url = await get_next_page_url(page, current_url)
            if next_url and next_url != current_url:
                current_url = next_url
            else:
                break

        except Exception as e:
            print(f"  Error on page {pages_visited + 1}: {e}")
            break

    return all_events

async def scrape_tickettailor(page, club, city, cls, url):
    events = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(4000)
        text = await page.inner_text("body")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        seen = set()
        for i, line in enumerate(lines):
            dt = parse_date(line)
            if not dt:
                continue
            name = ""
            for j in list(range(i-2, i)) + list(range(i+1, i+5)):
                if 0 <= j < len(lines) and not parse_date(lines[j]) and not is_junk(lines[j]) and len(lines[j]) > 8:
                    name = lines[j]
                    break
            if not name:
                continue
            key = dt.strftime("%Y-%m-%d")
            if key not in seen:
                seen.add(key)
                events.append(make_event(dt, club, city, cls, name, url))
    except Exception as e:
        print(f"  Tickettailor error: {e}")
    return events

CLUBS = [
    ("No.3 Club",        "no3",        "Chorley, Lancashire",      "https://theno3club.co.uk/events/",                   "wp"),
    ("Cupids",           "cupids",     "Swinton, Manchester",      "https://www.cupidsswingersclub.co.uk/events",        "wp"),
    ("Partners",         "partners",   "Manchester/Bury",          "https://www.partnersswingersclub.co.uk/events/",      "wp"),
    ("Pandoras",         "pandora",    "Leeds, West Yorkshire",    "https://www.pandoraswingers.com/",             "wp"),
    ("Club Play",        "clubplay",   "Blackpool",                "https://clubplay.net/events/",         "wp"),
    ("Xtasia",           "xtasia",     "West Bromwich",            "https://www.xtasia.co.uk/page/2-months-diary",                   "wp"),
    ("Naughty Pineapple","pineapple",  "UK",                       "https://thenaughtypineapple.co.uk/all-events/",       "wp"),
    ("The Attic",        "attic",      "Derby",                    "https://theatticexperience.com/events-prices-2/",          "wp"),
    ("Townhouse",        "townhouse",  "Birkenhead, Wirral",       "https://www.tickettailor.com/events/townhousewirral", "tt"),
    ("Swindon SC",       "swindon",    "Swindon",                  "https://swindonswingers.com/events/",                 "wp"),
    ("Club Alchemy",     "alchemy",    "UK",                       "https://www.clubalchemy.co.uk/events",                "wp"),
    ("Infusion",         "infusion",   "Blackpool",                "https://www.infusionblackpool.co.uk/8.html",         "wp"),
    ("Quest",            "quest",      "Darlington",               "https://questswingersclub.co.uk/upcoming-events/",         "wp"),
    ("Liberty Elite",    "liberty",    "Midlands",                 "https://libertyelite.co.uk/events/list/?tribe-bar-date=2026-05-22",              "wp"),
    ("Purple Mamba",     "mamba",      "Nottingham",               "https://www.purplemambaclub.com/events/",             "wp"),
    ("Shhh",             "shhh",       "Newcastle",                "https://www.shhhclub.co.uk/events",                  "wp"),
    ("Decadance",        "decadance",  "Rochdale",                 "https://www.decadanceswingersclub.com/what-s-on-at-decadance",       "wp"),
    ("New Gatehouse",    "gatehouse",  "Bolton",                   "https://www.thenewgatehousebolton.co.uk/about-1",    "wp"),
    ("Le Boudoir",       "leboudoir",  "London",                   "https://www.leboudoir.co.uk/events/",                 "wp"),
    ("Chameleons",       "chameleons", "Darlaston, West Midlands", "https://www.chameleons.cc/darlaston-events/",                   "wp"),
]

async def main():
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage","--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            viewport={"width":390,"height":844},
            locale="en-GB",
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = await ctx.new_page()

        for name, cls, city, url, mode in CLUBS:
            print(f"Scraping {name}...")
            if mode == "tt":
                evs = await scrape_tickettailor(page, name, city, cls, url)
            elif mode == "xtasia":
                # Xtasia needs longer wait for their diary page
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(5000)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)
                    evs = await scrape_page(page, name, city, cls, url)
                except Exception as e:
                    print(f"  Xtasia error: {e}")
                    evs = []
            else:
                evs = await scrape_page(page, name, city, cls, url)
            results[name] = evs
            print(f"  -> {len(evs)} events")
            await asyncio.sleep(1.5)

        await browser.close()

    all_events = []
    for evs in results.values():
        all_events.extend(evs)
    seen = set()
    unique = []
    for e in sorted(all_events, key=lambda x: x["d"]):
        k = (e["d"], e["club"])
        if k not in seen:
            seen.add(k)
            unique.append(e)

    with open("events_scraped.json", "w") as f:
        json.dump(unique, f, indent=2)

    print("\n=== RESULTS ===")
    for name, evs in results.items():
        status = f"YES {len(evs)} events" if evs else "NO 0 events"
        print(f"  {name}: {status}")
    print(f"Total: {len(unique)}")

asyncio.run(main())
