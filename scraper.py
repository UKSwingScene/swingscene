import asyncio
import json
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

CUTOFF = datetime.now() + timedelta(days=365)

MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
}

MONTH_SHORT = {1:'jan',2:'feb',3:'mar',4:'apr',5:'may',6:'jun',
               7:'jul',8:'aug',9:'sep',10:'oct',11:'nov',12:'dec'}

DAY_NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

def ordinal(n):
    s = str(n)
    if s.endswith('11') or s.endswith('12') or s.endswith('13'):
        return s + 'th'
    if s.endswith('1'): return s + 'st'
    if s.endswith('2'): return s + 'nd'
    if s.endswith('3'): return s + 'rd'
    return s + 'th'

def parse_date(text):
    text = text.strip()
    patterns = [
        r'(\d{1,2})[a-z]{0,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})',
        r'(\d{1,2})[a-z]{0,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})[a-z]{0,2}\s+(\d{4})',
        r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
        r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            g = m.groups()
            try:
                if g[0].isdigit() and not g[1].isdigit():
                    day, month, year = int(g[0]), MONTH_MAP[g[1].lower()], int(g[2])
                elif not g[0].isdigit():
                    month, day, year = MONTH_MAP[g[0].lower()], int(g[1]), int(g[2])
                elif len(g[0]) == 4:
                    year, month, day = int(g[0]), int(g[1]), int(g[2])
                else:
                    day, month, year = int(g[0]), int(g[1]), int(g[2])
                    if month > 12: day, month = month, day
                dt = datetime(year, month, day)
                if datetime.now() <= dt <= CUTOFF:
                    return dt
            except:
                pass
    return None

def make_event(dt, club, city, cls, event_name, url):
    day_name = DAY_NAMES[dt.weekday()]
    month_name = dt.strftime('%B')
    return {
        "d": dt.strftime("%Y-%m-%d"),
        "m": MONTH_SHORT[dt.month],
        "day": f"{day_name} {dt.day} {month_name}",
        "club": club,
        "city": city,
        "cls": cls,
        "event": event_name[:100],
        "desc": f"{event_name} at {club} in {city}. Visit the website for full details and booking.",
        "url": url
    }

async def get_page_text(page, url, wait_ms=3000):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(wait_ms)
        return await page.inner_text('body')
    except Exception as e:
        print(f"  Failed to load {url}: {e}")
        return ""

async def scrape_wordpress_events(page, club, city, cls, url):
    """For WordPress sites using The Events Calendar plugin"""
    events = []
    text = await get_page_text(page, url, 3000)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    seen_dates = set()
    for i, line in enumerate(lines):
        dt = parse_date(line)
        if dt:
            # Look for event name nearby
            name = ""
            for j in range(max(0,i-3), min(len(lines), i+5)):
                if j != i and len(lines[j]) > 8 and not parse_date(lines[j]):
                    candidate = lines[j]
                    if not any(x in candidate.lower() for x in ['cookie','privacy','copyright','menu','home','contact','login','register','search']):
                        name = candidate
                        break
            if not name:
                name = f"{club} Event"
            key = (dt.strftime("%Y-%m-%d"), name[:30])
            if key not in seen_dates:
                seen_dates.add(key)
                events.append(make_event(dt, club, city, cls, name, url))
    return events

async def scrape_tickettailor(page, club, city, cls, url):
    """Tickettailor specific scraper"""
    events = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        
        # Tickettailor event cards
        cards = await page.query_selector_all('.event-listing, .event-card, [data-event-id], .tt-event')
        if not cards:
            # Fall back to text parsing
            text = await page.inner_text('body')
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            seen = set()
            for i, line in enumerate(lines):
                dt = parse_date(line)
                if dt:
                    name = ""
                    for j in range(max(0,i-2), min(len(lines), i+4)):
                        if j != i and len(lines[j]) > 8 and not parse_date(lines[j]):
                            if lines[j].isupper() or len(lines[j]) < 80:
                                name = lines[j]
                                break
                    if not name:
                        name = f"{club} Event"
                    key = dt.strftime("%Y-%m-%d")
                    if key not in seen:
                        seen.add(key)
                        events.append(make_event(dt, club, city, cls, name, url))
        else:
            for card in cards:
                text = await card.inner_text()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                dt = None
                name = None
                for line in lines:
                    if not dt:
                        dt = parse_date(line)
                    elif not name and len(line) > 5:
                        name = line
                if dt:
                    events.append(make_event(dt, club, city, cls, name or f"{club} Event", url))
    except Exception as e:
        print(f"  Tickettailor error: {e}")
    return events

CLUBS = [
    {"name":"No.3 Club",       "cls":"no3",        "city":"Chorley, Lancashire",      "url":"https://theno3club.co.uk/events/",            "type":"wordpress"},
    {"name":"Cupids",          "cls":"cupids",     "city":"Swinton, Manchester",      "url":"https://cupidsswingers.co.uk/events/",        "type":"wordpress"},
    {"name":"Partners",        "cls":"partners",   "city":"East of England",          "url":"https://www.partnersswingers.co.uk/",         "type":"generic"},
    {"name":"Pandoras",        "cls":"pandora",    "city":"South East",               "url":"https://www.pandorasswingers.co.uk/events/",  "type":"wordpress"},
    {"name":"Club Play",       "cls":"clubplay",   "city":"Blackpool",                "url":"https://www.clubplayblackpool.co.uk/events/", "type":"wordpress"},
    {"name":"Xtasia",          "cls":"xtasia",     "city":"West Bromwich",            "url":"https://www.xtasia.co.uk/events/",            "type":"wordpress"},
    {"name":"Naughty Pineapple","cls":"pineapple", "city":"UK",                       "url":"https://thenaughtypineapple.co.uk/all-events/","type":"wordpress"},
    {"name":"The Attic",       "cls":"attic",      "city":"East Midlands",            "url":"https://www.theatticadultclub.co.uk/events/", "type":"wordpress"},
    {"name":"Townhouse",       "cls":"townhouse",  "city":"Birkenhead, Wirral",       "url":"https://www.tickettailor.com/events/townhousewirral","type":"tickettailor"},
    {"name":"Swindon SC",      "cls":"swindon",    "city":"Swindon",                  "url":"https://swindonswingers.com/events/",         "type":"wordpress"},
    {"name":"Club Alchemy",    "cls":"alchemy",    "city":"UK",                       "url":"https://www.clubalchemy.co.uk/events",        "type":"wordpress"},
    {"name":"Infusion",        "cls":"infusion",   "city":"North West",               "url":"https://www.infusionclub.co.uk/events/",      "type":"wordpress"},
    {"name":"Quest",           "cls":"quest",      "city":"Darlington",               "url":"https://www.questswingersclub.co.uk/events/", "type":"wordpress"},
    {"name":"Liberty Elite",   "cls":"liberty",    "city":"Midlands",                 "url":"https://www.libertyelite.co.uk/events/",      "type":"wordpress"},
    {"name":"Purple Mamba",    "cls":"mamba",      "city":"Nottingham",               "url":"https://www.purplemambaclub.com/events/",     "type":"wordpress"},
    {"name":"Shhh",            "cls":"shhh",       "city":"Newcastle",                "url":"https://www.shhhclub.co.uk/events/",          "type":"wordpress"},
    {"name":"Decadance",       "cls":"decadance",  "city":"Rochdale",                 "url":"https://www.decadanceswingersclub.com/events/","type":"wordpress"},
    {"name":"New Gatehouse",   "cls":"gatehouse",  "city":"Bolton",                   "url":"https://www.thenewgatehousebolton.co.uk/whats-on","type":"generic"},
    {"name":"Le Boudoir",      "cls":"leboudoir",  "city":"UK",                       "url":"https://www.leboudoir.co.uk/events/",         "type":"wordpress"},
    {"name":"Chameleons",      "cls":"chameleons", "city":"Darlaston, West Midlands", "url":"https://www.chameleons.cc/events/",           "type":"wordpress"},
]

async def main():
    all_events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            viewport={'width': 390, 'height': 844},
            locale='en-GB',
            extra_http_headers={
                'Accept-Language': 'en-GB,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )

        # Hide webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        page = await context.new_page()

        for club in CLUBS:
            print(f"Scraping {club['name']}...")
            try:
                if club['type'] == 'tickettailor':
                    events = await scrape_tickettailor(page, club['name'], club['city'], club['cls'], club['url'])
                else:
                    events = await scrape_wordpress_events(page, club['name'], club['city'], club['cls'], club['url'])
                print(f"  Found {len(events)} events")
                all_events.extend(events)
            except Exception as e:
                print(f"  Error: {e}")

            await asyncio.sleep(1)

        await browser.close()

    # Deduplicate and sort
    seen = set()
    unique = []
    for e in all_events:
        key = (e['d'], e['club'])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    unique.sort(key=lambda x: x['d'])

    with open('events_scraped.json', 'w') as f:
        json.dump(unique, f, indent=2)

    print(f"\nTotal: {len(unique)} events scraped")

if __name__ == "__main__":
    asyncio.run(main())
