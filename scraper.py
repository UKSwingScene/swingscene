import asyncio
import json
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

CLUBS = [
    {"name": "No.3 Club",        "cls": "no3",        "url": "https://theno3club.co.uk/events/",           "city": "Chorley, Lancashire"},
    {"name": "Cupids",           "cls": "cupids",     "url": "https://cupidsswingers.co.uk/events/",       "city": "Swinton, Manchester"},
    {"name": "Partners",         "cls": "partners",   "url": "https://www.partnersswingers.co.uk/events/", "city": "East of England"},
    {"name": "Pandoras",         "cls": "pandora",    "url": "https://www.pandorasswingers.co.uk/events/", "city": "South East"},
    {"name": "Club Play",        "cls": "clubplay",   "url": "https://www.clubplayblackpool.co.uk/events/","city": "Blackpool"},
    {"name": "Xtasia",           "cls": "xtasia",     "url": "https://www.xtasia.co.uk/events/",           "city": "West Bromwich"},
    {"name": "Naughty Pineapple","cls": "pineapple",  "url": "https://thenaughtypineapple.co.uk/all-events/","city": "UK"},
    {"name": "The Attic",        "cls": "attic",      "url": "https://www.theatticadultclub.co.uk/events/","city": "East Midlands"},
    {"name": "Townhouse",        "cls": "townhouse",  "url": "https://www.tickettailor.com/events/townhousewirral","city": "Birkenhead, Wirral"},
    {"name": "Swindon SC",       "cls": "swindon",    "url": "https://swindonswingers.com/events/",        "city": "Swindon"},
    {"name": "Club Alchemy",     "cls": "alchemy",    "url": "https://www.clubalchemy.co.uk/events",       "city": "UK"},
    {"name": "Infusion",         "cls": "infusion",   "url": "https://www.infusionclub.co.uk/events/",     "city": "North West"},
    {"name": "Quest",            "cls": "quest",      "url": "https://www.questswingersclub.co.uk/events/","city": "Darlington"},
    {"name": "Liberty Elite",    "cls": "liberty",    "url": "https://www.libertyelite.co.uk/events/",     "city": "Midlands"},
    {"name": "Purple Mamba",     "cls": "mamba",      "url": "https://www.purplemambaclub.com/events/",    "city": "Nottingham"},
    {"name": "Shhh",             "cls": "shhh",       "url": "https://www.shhhclub.co.uk/events/",         "city": "Newcastle"},
    {"name": "Decadance",        "cls": "decadance",  "url": "https://www.decadanceswingersclub.com/events/","city": "Rochdale"},
    {"name": "New Gatehouse",    "cls": "gatehouse",  "url": "https://www.thenewgatehousebolton.co.uk/whats-on","city": "Bolton"},
    {"name": "Le Boudoir",       "cls": "leboudoir",  "url": "https://www.leboudoir.co.uk/events/",        "city": "UK"},
    {"name": "Chameleons",       "cls": "chameleons", "url": "https://www.chameleons.cc/events/",          "city": "Darlaston, West Midlands"},
]

CUTOFF = datetime.now() + timedelta(days=365)

DATE_PATTERNS = [
    r'\b(\d{1,2})[a-z]{0,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b',
    r'\b(\d{1,2})[a-z]{0,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b',
    r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4})\b',
]

MONTHS = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
}

def parse_date(text):
    for pat in DATE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            g = m.groups()
            try:
                if g[0].isdigit():
                    day, month, year = int(g[0]), MONTHS[g[1].lower()], int(g[2])
                else:
                    month, day, year = MONTHS[g[0].lower()], int(g[1]), int(g[2])
                return datetime(year, month, day)
            except:
                pass
    return None

async def scrape_club(page, club):
    events = []
    try:
        await page.goto(club["url"], wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)
        
        # Try common event selectors
        selectors = [
            'article', '.event', '.event-item', '.event-card',
            '.tribe-event', '.tribe_events_cat', '[class*="event"]',
            '.wp-block-group', 'li', '.post'
        ]
        
        content = await page.content()
        text = await page.inner_text('body')
        
        # Extract date+title pairs from visible text
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            date = parse_date(line)
            if date and datetime.now() <= date <= CUTOFF:
                # Look for event name in nearby lines
                title = ""
                for j in range(max(0, i-2), min(len(lines), i+4)):
                    if j != i and len(lines[j]) > 5 and not parse_date(lines[j]):
                        title = lines[j]
                        break
                if not title:
                    title = f"{club['name']} Event"
                
                month_map = {1:'jan',2:'feb',3:'mar',4:'apr',5:'may',6:'jun',
                             7:'jul',8:'aug',9:'sep',10:'oct',11:'nov',12:'dec'}
                
                events.append({
                    "d": date.strftime("%Y-%m-%d"),
                    "m": month_map[date.month],
                    "day": date.strftime("%A %-d %B"),
                    "club": club["name"],
                    "city": club["city"],
                    "cls": club["cls"],
                    "event": title[:80],
                    "desc": f"{club['name']} event in {club['city']}. Visit the website for full details.",
                    "url": club["url"]
                })
            i += 1
            
    except Exception as e:
        print(f"  Error scraping {club['name']}: {e}")
    
    # Deduplicate by date
    seen = set()
    unique = []
    for ev in events:
        key = (ev['d'], ev['club'])
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    
    return sorted(unique, key=lambda x: x['d'])

async def main():
    all_events = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        for club in CLUBS:
            print(f"Scraping {club['name']}...")
            events = await scrape_club(page, club)
            print(f"  Found {len(events)} events")
            all_events.extend(events)
        
        await browser.close()
    
    all_events.sort(key=lambda x: x['d'])
    
    with open('events.json', 'w') as f:
        json.dump(all_events, f, indent=2)
    
    print(f"\nTotal events found: {len(all_events)}")
    print("Saved to events.json")

if __name__ == "__main__":
    asyncio.run(main())
