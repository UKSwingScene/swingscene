import asyncio, json, re, urllib.request as _urllib
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

CUTOFF = datetime.now() + timedelta(days=366)
NOW = datetime.now()
MKS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
MMAP = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,
        'august':8,'september':9,'october':10,'november':11,'december':12,
        'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

def mk(dt): return MKS[dt.month-1]

def make_event(dt, club, city, cls, name, url, desc=None):
    name = re.sub(r'[\U0001F000-\U0001FFFF\U00002600-\U000027FF\U0000200D\uFE0F]+', '', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()

    M  = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    DF = r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
    DA = r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)'  # 3-char abbreviations only

    # --- PREFIX CLEANING ---
    name = re.sub(r'^(BOOK TICKETS|GUEST LIST ONLY|COMING SOON|SOLD OUT|BUY TICKETS)\s*', '', name, flags=re.I).strip()
    name = re.sub(r'^CLUB PLAY\s*[-\u2013]\s*', '', name, flags=re.I).strip()
    name = re.sub(r'^CLUB PLAY\s+', '', name, flags=re.I).strip()
    name = re.sub(rf'^{DA}\s+\d{{1,2}}(?:ST|ND|RD|TH)?\s+{M}(?:\s+\d{{4}})?\s*[-\u2013:]*\s*', '', name, flags=re.I).strip()
    name = re.sub(rf'^{DF}\s+\d{{1,2}}[a-z]{{0,2}}\s+{M}(?:\s+\d{{4}})?\s*[-\u2013:]*\s*', '', name, flags=re.I).strip()
    name = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4}\s*[-\u2013:]*\s*', '', name).strip()
    name = re.sub(r'^\d{1,2}-\d{1,2}\s+', '', name).strip()

    # --- SUFFIX JUNK (before date stripping to expose trailing dates) ---
    name = re.sub(r'\s*[-\u2013]\s*FREE\s+(?:ENTRY|BAR|LICENSED BAR|BUFFET|PLAY).*$', '', name, flags=re.I).strip()
    name = re.sub(r'\s+FREE\s+ENTRY.*$', '', name, flags=re.I).strip()
    name = re.sub(r'\s*LICEN[SC]ED\s+BAR.*$', '', name, flags=re.I).strip()
    name = re.sub(r'\s*FULLY\s+LICEN[SC]ED.*$', '', name, flags=re.I).strip()
    name = re.sub(r'\s*\([^)]{20,}\)$', '', name).strip()
    # Lone trailing digit (truncated "8" from "8pm")
    name = re.sub(r'\s+\d$', '', name).strip()

    # --- DATE+TIME STRIPPING FROM END ---
    # "Saturday, 6 June 2026 19:30–01:30..." (Club Alchemy)
    name = re.sub(rf'\s*,?\s*{DF},?\s+\d{{1,2}}[a-z]{{0,2}}\s+{M}\s+\d{{4}}.*$', '', name, flags=re.I).strip()
    # Time from end: "8pm till 3am"
    name = re.sub(r'\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:till|until|to|-)?.*$', '', name, flags=re.I).strip()
    # *** "DDth Month" at end FIRST — preserves "FILTHY FRIDAY" ***
    name = re.sub(rf'\s+\d{{1,2}}(?:st|nd|rd|th)?\s+{M}(?:\s+\d{{4}})?$', '', name, flags=re.I).strip()
    # "Day DDth Month" at end: "FRIDAY 5th JUNE", "Saturday 8th August"
    name = re.sub(rf'\s+{DF}\s+\d{{1,2}}[a-z]{{0,2}}\s+{M}(?:\s+\d{{4}})?$', '', name, flags=re.I).strip()
    # Abbreviated 3-char day at end (left over from stripped date): "FRI", "SAT"
    # Safe: won't strip "FILTHY FRIDAY" since DA only matches 3-char abbrevs, not full "FRIDAY"
    name = re.sub(rf'\s+{DA}$', '', name, flags=re.I).strip()

    # --- VENUE AT END ---
    name = re.sub(r'\s*[-\u2013]?\s*CLUB PLAY\s*$', '', name, flags=re.I).strip()

    name = name.strip(' \xb7\u2013\u2014-&').strip()
    name = re.sub(r'\s+', ' ', name).strip()
    if not name or len(name) < 3: return None
    if not desc:
        desc = f"{name} at {club}, {city}. Visit the website for full details and booking."
    return {
        "d": dt.strftime("%Y-%m-%d"),
        "m": mk(dt),
        "day": f"{DAYS[dt.weekday()]} {dt.day} {dt.strftime('%B')} {dt.year}",
        "club": club, "city": city, "cls": cls,
        "event": name[:100], "url": url, "desc": desc
    }


def in_range(dt):
    # Compare dates only so today's events are included regardless of time
    return dt.date() >= NOW.date() and dt <= CUTOFF

def parse_date_text(text):
    """Parse various date formats from text, return datetime or None."""
    text = text.strip()
    patterns = [
        (r'(\d{1,2})[a-z]{0,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})', 'dmy_long'),
        (r'(\d{1,2})[a-z]{0,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})', 'dmy_short'),
        (r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4})', 'mdy'),
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', 'dmy_slash'),
        (r'(mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})', 'dow_dmy'),
        (r'(mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})[a-z]*,?\s+(\d{4})', 'dow_mdy'),
        (r'(fri|sat|sun)\s+(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', 'dow_dm_noyear'),
    ]
    cur_year = NOW.year
    for pat, fmt in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        g = m.groups()
        try:
            if fmt == 'dmy_long' or fmt == 'dmy_short':
                day, month, year = int(g[0]), MMAP[g[1].lower()], int(g[2])
            elif fmt == 'mdy':
                month, day, year = MMAP[g[0].lower()], int(g[1]), int(g[2])
            elif fmt == 'dmy_slash':
                day, month, year = int(g[0]), int(g[1]), int(g[2])
                if month > 12: day, month = month, day
            elif fmt == 'dow_dmy':
                day, month, year = int(g[1]), MMAP[g[2].lower()], int(g[3])
            elif fmt == 'dow_mdy':
                month, day, year = MMAP[g[1].lower()], int(g[2]), int(g[3])
            elif fmt == 'dow_dm_noyear':
                day, month = int(g[1]), MMAP[g[2].lower()]
                year = cur_year
                dt = datetime(year, month, day)
                if dt < NOW - timedelta(days=7):
                    year += 1
                    dt = datetime(year, month, day)
                if in_range(dt): return dt
                continue
            else:
                continue
            dt = datetime(year, month, day)
            if in_range(dt): return dt
        except:
            pass
    return None


# ─────────────────────────────────────────────
# CLUB-SPECIFIC SCRAPERS
# ─────────────────────────────────────────────

async def scrape_wp_api(page, base_url, club, city, cls, events_url):
    """Try WordPress/Tribe Events REST API."""
    api = base_url.rstrip('/') + '/wp-json/tribe/events/v1/events?per_page=50&start_date=' + NOW.strftime('%Y-%m-%d')
    try:
        result = await page.evaluate(f'fetch("{api}").then(r=>r.ok?r.json():null).catch(()=>null)')
        if result and isinstance(result, dict) and 'events' in result:
            events = []
            for ev in result['events']:
                try:
                    dt = datetime.fromisoformat(ev['start_date'][:10])
                    if in_range(dt):
                        title = re.sub(r'<[^>]+>', '', ev.get('title', '')).strip()
                        if title:
                            e = make_event(dt, club, city, cls, title, events_url)
                            if e: events.append(e)
                except:
                    pass
            if events:
                return events
    except:
        pass
    return []

# STANDARD NIGHT filters per club
ATTIC_STANDARD = {'greedy girls','tv & admirers','tv and admirers','tv admirers','daytime cinema',
                  'cinema','humpday evening cinema','frisky friday after dark','club night',
                  'standard club night','frisky friday','friday night','saturday night',
                  'cinema event','afternoon cinema','monday tv','wednesday cinema'}

QUEST_STANDARD = {'afternoon fun','evening sexy fun','evening naughtiness','funday sunday',
                  "m&n party night",'bi tuesdays','bi tuesday','t-girls cds & admirers',
                  't-girls, cds & admirers','greedy girls','couples & singles party night at quest',
                  'couples & singles afternoon fun','wednesday hump day hotness','couples and singles party night'}

MAMBA_STANDARD = {'play space','sunday sinners','bottomless munch social','singles night'}

HU9_STANDARD = {'frisky friday','sexy saturday'}

CHAMELEONS_STANDARD = {
    'club night', 'couples night', 'couples and singles night',
    'open night', 'members night', 'friday night', 'saturday night',
}

IGNITE_STANDARD = {'couples & singles friday','couples & singles saturday',
                   'silks & skins spa day','half off friday'}

DECADANCE_STANDARD = {'sexxxy saturday','monday funday','friday night madness','spicy sunday',
                      'friday night madness 2.0'}

async def scrape_clubplay(page, url):
    """Club Play: h3 a = title, date is DD/MM/YYYY below it."""
    events = []
    pages_done = set()
    cur = url
    while cur and cur not in pages_done and len(pages_done) < 5:
        pages_done.add(cur)
        await page.goto(cur, wait_until='domcontentloaded', timeout=25000)
        await page.wait_for_timeout(3000)
        items = await page.query_selector_all('h3 a')
        for item in items:
            title = (await item.inner_text()).strip()
            title = re.sub(r'[\U0001F000-\U0001FFFF\U00002600-\U000027FF]+', '', title).strip()
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 5: continue
            # Get the date from the container
            container = await item.evaluate_handle('el => el.closest("li") || el.parentElement.parentElement')
            try:
                container_text = await container.inner_text()
            except:
                container_text = ''
            dt = parse_date_text(container_text)
            if dt:
                href = await item.get_attribute('href') or url
                e = make_event(dt, 'Club Play', 'Blackpool', 'clubplay', title, href)
                if e: events.append(e)
        # Check for next page
        next_el = await page.query_selector('a[href*="pno="]')
        next_url = None
        if next_el:
            href = await next_el.get_attribute('href')
            m = re.search(r'pno=(\d+)', href)
            cur_pno = re.search(r'pno=(\d+)', cur)
            cur_num = int(cur_pno.group(1)) if cur_pno else 1
            if m and int(m.group(1)) > cur_num:
                next_url = href if href.startswith('http') else 'https://clubplay.net' + href
        cur = next_url
    return events

async def scrape_naughtypineapple(page, url):
    """Naughty Pineapple: Tribe Events Calendar, try API then h3 a."""
    api_events = await scrape_wp_api(page, 'https://thenaughtypineapple.co.uk', 'Naughty Pineapple', 'Leicester', 'pineapple', url)
    if api_events: return api_events
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(3000)
    events = []
    items = await page.query_selector_all('h3 a, h2 a')
    for item in items:
        title = (await item.inner_text()).strip()
        href = await item.get_attribute('href') or url
        if not title or 'event' not in href: continue
        parent = await item.evaluate_handle('el => el.closest("article") || el.parentElement.parentElement.parentElement')
        try:
            ptext = await parent.inner_text()
        except:
            ptext = title
        dt = parse_date_text(ptext)
        if dt:
            e = make_event(dt, 'Naughty Pineapple', 'Leicester', 'pineapple', title, href)
            if e: events.append(e)
    return events

async def scrape_purplemamba(page, url):
    """Purple Mamba: Wix — wait for JS, find event items."""
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(5000)
    events = []
    # Wix events list structure
    items = await page.query_selector_all('[data-hook="event-list-item"], .eventContainer, [class*="EventListItem"]')
    if not items:
        # fallback: parse text
        text = await page.inner_text('body')
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            dt = parse_date_text(line)
            if dt:
                # look for event name in nearby lines
                for j in [i-1, i-2, i+1, i+2]:
                    if 0 <= j < len(lines):
                        candidate = lines[j].strip()
                        if len(candidate) > 5 and not parse_date_text(candidate):
                            nl = candidate.lower()
                            if not any(s in nl for s in MAMBA_STANDARD):
                                e = make_event(dt, 'Purple Mamba', 'Nottingham', 'mamba', candidate, url)
                                if e: events.append(e)
                            break
        return events
    for item in items:
        try:
            title_el = await item.query_selector('[data-hook="event-title"], [class*="title"], a')
            if not title_el: continue
            title = (await title_el.inner_text()).strip()
            if not title: continue
            if any(s in title.lower() for s in MAMBA_STANDARD): continue
            item_text = await item.inner_text()
            dt = parse_date_text(item_text)
            if dt:
                e = make_event(dt, 'Purple Mamba', 'Nottingham', 'mamba', title, url)
                if e: events.append(e)
        except:
            pass
    return events

async def scrape_hu9(page, url):
    """HU9 Hull: Skiddle API (venue ID 87332) — picks up all ticketed special events.
    Requires SKIDDLE_API_KEY env var (free key from skiddle.com/api/join.php).
    Wix Vibe site blocks cloud IPs, so direct scraping is not possible.
    """
    import os, sys

    api_key = os.environ.get('SKIDDLE_API_KEY', '')
    if not api_key:
        print("HU9: SKIDDLE_API_KEY not set — skipping", file=sys.stderr)
        return []

    events = []
    try:
        api_url = (
            f"https://www.skiddle.com/api/v1/events/search/"
            f"?api_key={api_key}&venueid=87332"
            f"&minDate={NOW.strftime('%Y-%m-%d')}&limit=100"
        )
        req = _urllib.Request(api_url, headers={'User-Agent': 'SwingScene/1.0'})
        with _urllib.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())

        result_count = len(data.get('results', []))
        print(f"HU9 Skiddle API: {result_count} events returned", file=sys.stderr)
        if data.get('error') not in (0, None, '0', ''):
            print(f"HU9 Skiddle API error code: {data.get('error')} — {data.get('errormsg', '')}", file=sys.stderr)

        for ev in data.get('results', []):
            name = (ev.get('eventname') or ev.get('headline') or ev.get('EventTitle') or '').strip()
            date_str = (ev.get('date') or ev.get('startdate') or '')[:10]
            event_url = ev.get('link') or url

            if not name or not date_str:
                continue
            if any(s in name.lower() for s in HU9_STANDARD):
                continue

            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue

            if not in_range(dt):
                continue

            e = make_event(dt, 'HU9', 'Hull', 'hu9', name, event_url)
            if e:
                events.append(e)

    except Exception as ex:
        print(f"HU9 Skiddle API error: {ex}", file=sys.stderr)

    return events

async def scrape_libertyelite(page, url):
    """Liberty Elite: Tribe Events Calendar with WP API."""
    api_events = await scrape_wp_api(page, 'https://libertyelite.co.uk', 'Liberty Elite', 'Midlands', 'liberty', url)
    if api_events: return api_events
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(3500)
    events = []
    for sel in ['.tribe-events-calendar-list__event-title a', 'h2.tribe-events-list-event-title a', 'h2 a']:
        items = await page.query_selector_all(sel)
        if items:
            for item in items:
                title = (await item.inner_text()).strip()
                href = await item.get_attribute('href') or url
                parent = await item.evaluate_handle('el => el.closest("article") || el.parentElement.parentElement')
                try:
                    ptext = await parent.inner_text()
                except:
                    ptext = ''
                dt = parse_date_text(ptext)
                if dt:
                    e = make_event(dt, 'Liberty Elite', 'Midlands', 'liberty', title, href)
                    if e: events.append(e)
            if events: return events
    return events

async def scrape_chameleons(page, url):
    """Chameleons Darlaston: TEC REST API (urllib first), Playwright scroll fallback.
    Page lazy-loads events on scroll — API is much more reliable.
    """
    import sys

    # Try TEC API first
    api = 'https://www.chameleons.cc/wp-json/tribe/events/v1/events?per_page=100&start_date=' + NOW.strftime('%Y-%m-%d')
    try:
        req = _urllib.Request(api, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        with _urllib.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        events = []
        for ev in data.get('events', []):
            try:
                dt = datetime.fromisoformat(ev['start_date'][:10])
                if in_range(dt):
                    title = re.sub(r'<[^>]+>', '', ev.get('title', '')).strip()
                    if title and title.lower() not in CHAMELEONS_STANDARD:
                        e = make_event(dt, 'Chameleons', 'Darlaston, West Midlands', 'chameleons', title, url)
                        if e: events.append(e)
            except: pass
        if events:
            print(f"Chameleons (API): {len(events)} events", file=sys.stderr)
            return events
    except Exception as ex:
        print(f"Chameleons API error: {ex} — trying Playwright", file=sys.stderr)

    # Playwright fallback — scroll to bottom to trigger lazy loading
    events = []
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)

        # Scroll down repeatedly to trigger lazy load
        for _ in range(8):
            await page.evaluate("window.scrollBy(0, 1200)")
            await page.wait_for_timeout(800)

        text = await page.inner_text('body')
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        seen = set()
        for i, line in enumerate(lines):
            dt = parse_date_text(line)
            if not dt or not in_range(dt): continue
            title = None
            for j in [i-1, i-2, i+1]:
                if 0 <= j < len(lines):
                    candidate = lines[j].strip()
                    if (candidate and not parse_date_text(candidate)
                            and 4 < len(candidate) < 100
                            and candidate.lower() not in CHAMELEONS_STANDARD):
                        title = candidate
                        break
            if title:
                key = (dt.date(), title.lower())
                if key not in seen:
                    seen.add(key)
                    e = make_event(dt, 'Chameleons', 'Darlaston, West Midlands', 'chameleons', title, url)
                    if e: events.append(e)
    except Exception as ex:
        print(f"Chameleons Playwright error: {ex}", file=sys.stderr)

    print(f"Chameleons (scroll): {len(events)} events", file=sys.stderr)
    return events

async def scrape_attic(page, url):
    """The Attic: text-based calendar, filter standard nights."""
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(3000)
    events = []
    text = await page.inner_text('body')
    # Pattern: "Sat 30th May : Uniforms Party" or "Sun 7th June : Cumfest"
    pattern = re.compile(
        r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})[a-z]{0,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s*[:\-–]\s*(.+?)(?=\n|$)', re.I
    )
    cur_year = NOW.year
    for m in pattern.finditer(text):
        day_num = int(m.group(1))
        month_name = m.group(2)
        event_name = m.group(3).strip()
        if any(s in event_name.lower() for s in ATTIC_STANDARD): continue
        if len(event_name) < 4: continue
        month = MMAP[month_name.lower()]
        year = cur_year
        try:
            dt = datetime(year, month, day_num)
            if dt < NOW - timedelta(days=1): dt = datetime(year+1, month, day_num)
            if in_range(dt):
                e = make_event(dt, 'The Attic', 'Derby', 'attic', event_name, url)
                if e: events.append(e)
        except:
            pass
    return events

async def scrape_quest(page, url):
    """Quest: Long text page, blocks separated by *** lines.
    Date + event name on same line OR name in subsequent line.
    Filter all standard recurring nights."""
    QUEST_STANDARD = {
        'afternoon fun', 'evening sexy fun', 'evening naughtiness',
        'funday sunday', 'funday sunday – couples & singles',
        'm&n party night', 'bi tuesdays', 'bi tuesday',
        't-girls, cds & admirers', 't-girls cds & admirers',
        't-girls, cds & admirers event', 'greedy girls',
        'couples & singles party night at quest',
        'couples and singles party night at quest',
        'day event', 'night event', 'day/night event', 'evening event',
        'afternoon even', 'couples & singles afternoon fun',
    }
    # Site blocks urllib — use Playwright first (real browser bypasses 403), curl fallback
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(4000)
        text = await page.inner_text('body')
    except Exception as ex:
        print(f"  Quest Playwright failed: {ex}, trying curl")
        try:
            import subprocess, html as _html
            result = subprocess.run([
                'curl', '-s', '-L', '--max-time', '20',
                '-H', 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
                '-H', 'Accept: text/html,*/*;q=0.8',
                url
            ], capture_output=True, timeout=25)
            raw = result.stdout.decode('utf-8', errors='replace')
            import html as _html2
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = _html2.unescape(text)
        except Exception as ex2:
            print(f"  Quest all methods failed: {ex2}")
            return []

    for ch in ['\u2013', '\u2014']:
        text = text.replace(ch, '-')

    events = []
    seen = set()
    # Split into blocks on lines of asterisks
    blocks = re.split(r'\*{5,}', text)
    date_pattern = re.compile(
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+'
        r'(\d{1,2})[a-z]{0,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{4})',
        re.I
    )
    for block in blocks:
        block = block.strip()
        if not block: continue
        dm = date_pattern.search(block)
        if not dm: continue
        day_num = int(dm.group(1))
        month = MMAP[dm.group(2).lower()]
        year = int(dm.group(3))
        try:
            dt = datetime(year, month, day_num)
            if not in_range(dt): continue
        except: continue

        # Get the part of the date line after the last dash
        date_line = block[dm.start():block.find('\n', dm.start())].strip()
        # Extract event name: text after final '-' on the date line
        after_dash = re.split(r'\s*-\s*', date_line)
        candidate = after_dash[-1].strip() if after_dash else ''

        # If candidate is generic, scan block lines for a better name
        if not candidate or candidate.lower() in QUEST_STANDARD or len(candidate) < 5:
            lines_in_block = [l.strip() for l in block.split('\n') if l.strip()]
            candidate = None
            for line in lines_in_block:
                # Skip the date line itself and pricing/door info
                if date_pattern.search(line): continue
                ln = line.lower()
                if any(s in ln for s in QUEST_STANDARD): continue
                if re.search(r'£\d|doors open|entrance|per couple|per single|members entrance', ln, re.I): continue
                if re.search(r'join us for|end your week|for all couples|all bisexual', ln, re.I): continue
                if len(line) < 5 or len(line) > 100: continue
                candidate = line.strip()
                break

        if not candidate: continue
        event_name = candidate[:80].strip()
        if event_name.lower() in QUEST_STANDARD: continue
        if any(s in event_name.lower() for s in QUEST_STANDARD): continue
        if len(event_name) < 5: continue

        key = dt.strftime('%Y-%m-%d') + event_name[:15]
        if key in seen: continue
        seen.add(key)
        e = make_event(dt, 'Quest', 'Leeds', 'quest', event_name,
                       'https://questswingersclub.co.uk/upcoming-events/')
        if e: events.append(e)

    print(f"  Quest: {len(events)} events")
    return events


async def scrape_decadance(page, url):
    """Decadance: Scrape special events via 'Events Coming Soon' nav links.

    Strategy:
      1. Load the main events page.
      2. Find all nav links whose href contains /events-coming-soon/ and whose
         text matches DD/MM Event Name — this is how Decadance lists upcoming
         special events in their site navigation.
      3. Visit each detail page to extract a proper description from the body.
      4. Parse date from the DD/MM prefix in the link text.
      5. Skip standard/filtered nights.

    This approach is robust to image-only date sections on the main page —
    the nav links are always text, and the detail pages always have descriptions.
    """
    BASE = 'https://www.decadanceswingersclub.com'
    nav_pattern = re.compile(r'^(\d{2})/(\d{2})\s+(.+)$')
    cur_year = NOW.year
    events = []

    # Step 1: load main events page and collect all Events Coming Soon links
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(4000)

    detail_links = []  # list of (day, month, name, href)
    anchors = await page.query_selector_all('a')
    for anchor in anchors:
        try:
            href = (await anchor.get_attribute('href') or '').strip()
            link_text = (await anchor.inner_text()).strip()
        except:
            continue
        if '/events-coming-soon/' not in href:
            continue
        nm = nav_pattern.match(link_text)
        if not nm:
            continue
        day_num, month_num = int(nm.group(1)), int(nm.group(2))
        name = nm.group(3).strip()
        # Strip emoji
        name = re.sub(r'[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF]+', '', name).strip()
        if not name or len(name) < 4:
            continue
        if any(s in name.lower() for s in DECADANCE_STANDARD):
            continue
        if not href.startswith('http'):
            href = BASE + href
        detail_links.append((day_num, month_num, name, href))

    # Step 2: visit each detail page to get a proper description
    for day_num, month_num, name, detail_url in detail_links:
        try:
            dt = datetime(cur_year, month_num, day_num)
            if dt < NOW - timedelta(days=1):
                dt = datetime(cur_year + 1, month_num, day_num)
            if not in_range(dt):
                continue
        except:
            continue

        # Fetch the detail page for description
        desc = f'{name} at Decadance, Rochdale.'
        try:
            await page.goto(detail_url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(2000)
            body_text = await page.inner_text('body')
            # Find the first substantive paragraph after the nav block
            # (skip short lines, nav items, and image-only lines)
            para_lines = [l.strip() for l in body_text.split('\n') if len(l.strip()) > 60]
            # Skip nav/header lines that are link text
            skip_phrases = ['what\'s on', 'events coming soon', 'regular weekly', 'find us on',
                            'facebook', 'instagram', 'copyright', 'privacy policy']
            for para in para_lines:
                if any(s in para.lower() for s in skip_phrases):
                    continue
                desc = para[:300]
                break
        except:
            pass  # fallback to default desc

        e = make_event(dt, 'Decadance', 'Rochdale', 'decadance', name, detail_url)
        if e:
            # Inject the richer description
            e['desc'] = desc
            events.append(e)

    return events

async def scrape_shhh(page, url):
    """Shhh: Squarespace events list."""
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(4000)
    events = []
    for sel in ['.eventlist-title a', 'h1.eventlist-title a', 'h2.eventlist-title a',
                '.event-title a', '.summary-title a']:
        items = await page.query_selector_all(sel)
        if items:
            for item in items:
                title = (await item.inner_text()).strip()
                href = await item.get_attribute('href') or url
                if not href.startswith('http'):
                    href = 'https://www.shhhclub.co.uk' + href
                parent = await item.evaluate_handle('el => el.closest("article") || el.parentElement.parentElement.parentElement')
                try:
                    ptext = await parent.inner_text()
                except:
                    ptext = title
                dt = parse_date_text(ptext)
                if dt:
                    e = make_event(dt, 'Shhh', 'Newcastle', 'shhh', title, href)
                    if e: events.append(e)
            if events: return events
    return events

async def fetch_bypass(url, timeout=20):
    """Fetch a bot-blocked URL using curl - different TLS fingerprint bypasses most blocks."""
    import subprocess
    result = subprocess.run([
        'curl', '-s', '-L', '--max-time', str(timeout), '--compressed',
        '-H', 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        '-H', 'Accept-Language: en-GB,en;q=0.9',
        '-H', 'Connection: keep-alive',
        '-H', 'Upgrade-Insecure-Requests: 1',
        '-H', 'Sec-Fetch-Dest: document',
        '-H', 'Sec-Fetch-Mode: navigate',
        '-H', 'Sec-Fetch-Site: none',
        url
    ], capture_output=True, timeout=timeout+5)
    if result.returncode != 0:
        raise Exception(f"curl exit {result.returncode}")
    content = result.stdout.decode('utf-8', errors='replace')
    if len(content) < 200:
        raise Exception(f"curl too short: {len(content)} chars")
    return content

async def scrape_no3(page, url):
    """No.3 Club: bot-blocked site. Use Jina Reader as primary fetch method.
    Events are plain text on homepage. Show ALL events."""
    events = []
    seen = set()
    raw = ''
    # Strategy 1: Jina Reader (most reliable for blocked sites)
    try:
        raw = await fetch_bypass(url)
        print(f"  No.3 Club: curl fetched {len(raw)} chars")
    except Exception as ex:
        print(f"  No.3 curl failed: {ex}, trying direct fetch")
        # Strategy 2: Direct fetch with proper browser headers
        try:
            import urllib.request as _ul
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.9',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            req = _ul.Request(url, headers=headers)
            with _ul.urlopen(req, timeout=15) as r:
                raw = r.read().decode('utf-8', errors='replace')
            print(f"  No.3 direct fetch: {len(raw)} chars")
        except Exception as ex2:
            print(f"  No.3 direct fetch failed: {ex2}, trying Playwright")
            # Strategy 3: Playwright fallback
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=25000)
                await page.wait_for_timeout(3000)
                raw = await page.content()
                print(f"  No.3 Playwright: {len(raw)} chars")
            except Exception as ex3:
                print(f"  No.3 all methods failed: {ex3}")
                return []
    
    import html as _html
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = _html.unescape(text)
    # Normalise all dash types to hyphen
    for ch in ['–', '—', '‒', '‑']:
        text = text.replace(ch, '-')
    # Collapse whitespace but keep newlines
    text = re.sub(r'[ 	]+', ' ', text)
    pattern = re.compile(
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[a-z]*\s+'
        r'(\d{1,2})[a-z]{0,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s*[-]+\s*(.+?)(?:\n|\r|$)',
        re.I | re.UNICODE
    )
    cur_year = NOW.year
    for m in pattern.finditer(text):
        day_num = int(m.group(1))
        month_name = m.group(2)
        raw_name = m.group(3).strip()
        # Strip trailing time info like "8:30 - 1:30am"
        event_name = re.sub(r'\s*-\s*\d{1,2}[:.]\d{2}.*$', '', raw_name).strip()
        event_name = re.sub(r'\s+from\s+\d.*$', '', event_name, flags=re.I).strip()
        event_name = re.sub(r'\s+\d{1,2}[:.]\d{2}.*$', '', event_name).strip()
        # Strip leading emoji
        event_name = re.sub(r'^[𐀀-􏿿☀-⟿\s]+', '', event_name).strip()
        if not event_name or len(event_name) < 4: continue
        event_name = event_name[:80].strip()
        month = MMAP[month_name.lower()]
        try:
            dt = datetime(cur_year, month, day_num)
            if dt < NOW - timedelta(days=1):
                dt = datetime(cur_year + 1, month, day_num)
            if not in_range(dt): continue
            key = dt.strftime('%Y-%m-%d') + event_name[:10]
            if key in seen: continue
            seen.add(key)
            e = make_event(dt, 'No.3 Club', 'Chorley, Lancashire', 'no3', event_name, 'https://theno3club.co.uk/')
            if e: events.append(e)
        except:
            pass
    print(f"  No.3 Club parsed {len(events)} events from text")
    return events


async def scrape_cupids(page, url):
    """Cupids: Squarespace site. All events named. Filter only the generic
    weekly Wednesday 'couples & single females only night'."""
    CUPIDS_STANDARD = {
        'couples & single females only night', 'couples & single females only',
        'tits out tuesday', 'm.o.t.d', 'motd',
    }
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(4000)
    events = []
    seen = set()
    # Squarespace: event titles in h1 tags with links to /events/slug
    # Dates in Google Calendar links: dates=YYYYMMDDTHHMMSSZ
    links = await page.query_selector_all('h1 a[href*="/events/"], h2 a[href*="/events/"]')
    for link in links:
        title = (await link.inner_text()).strip()
        if not title or len(title) < 3: continue
        if title.lower().rstrip() in CUPIDS_STANDARD: continue
        if 'couples & single females only' in title.lower(): continue
        href = await link.get_attribute('href') or url
        if not href.startswith('http'):
            href = 'https://www.cupidsswingersclub.co.uk' + href
        # Get parent container for date
        container = await link.evaluate_handle(
            'el => el.closest("article") || el.closest(".eventlist-event") || el.parentElement.parentElement.parentElement'
        )
        dt = None
        try:
            # Look for Google Calendar link with ISO date
            gcal = await container.query_selector('a[href*="dates="]')
            if gcal:
                gcal_href = await gcal.get_attribute('href') or ''
                m = re.search(r'dates=(\d{8})T', gcal_href)
                if m:
                    ds = m.group(1)
                    dt = datetime(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        except: pass
        if not dt:
            try:
                ptext = await container.inner_text()
                dt = parse_date_text(ptext)
            except: pass
        if dt and in_range(dt):
            key = dt.strftime('%Y-%m-%d') + title[:15]
            if key not in seen:
                seen.add(key)
                e = make_event(dt, 'Cupids', 'Swinton, Manchester', 'cupids', title, href)
                if e: events.append(e)
    return events


async def scrape_clubalchemy(page, url):
    """Club Alchemy: custom JS-rendered site. Extract date from URL slug."""
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(6000)
    events = []
    seen = set()
    links = await page.query_selector_all('a[href*="/events/"]')
    for link in links:
        href = await link.get_attribute('href') or ''
        if not href or href.rstrip('/') == url.rstrip('/'): continue
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', href)
        if m:
            try:
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if not in_range(dt): continue
                # Try to get a clean title from a heading element inside the link
                heading = await link.query_selector('h1, h2, h3, h4, h5, strong, .title, .event-title, .name')
                if heading:
                    title = (await heading.inner_text()).strip()
                else:
                    title = (await link.inner_text()).strip()
                # If no title, derive from URL slug
                if not title or len(title) < 3:
                    slug = href.split('/events/')[-1].strip('/')
                    slug = re.sub(r'-\d{4}-\d{2}-\d{2}.*', '', slug)
                    title = slug.replace('-', ' ').title()
                # Strip description text — keep only first line
                title = title.split('\n')[0].strip()
                # Strip "Saturday, DD Month YYYY HH:MM" and anything after
                title = re.sub(r'\s*,?\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+\d{1,2}.*$', '', title, flags=re.I).strip()
                full_url = href if href.startswith('http') else 'https://www.clubalchemy.co.uk' + href
                key = dt.strftime('%Y-%m-%d') + title[:10]
                if key not in seen:
                    seen.add(key)
                    e = make_event(dt, 'Club Alchemy', 'UK', 'alchemy', title, full_url)
                    if e: events.append(e)
            except: pass
    return events


async def scrape_tickettailor(page, url, club, city, cls):
    """Tickettailor events page — uses h2/h3 selectors with bad-title filtering,
    falls back to line-by-line text parse."""
    import sys
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(5000)

    BAD_TITLES = {'events list', 'event list', 'upcoming events', 'all events',
                  'buy tickets', 'sold out', 'more info', 'no events found'}

    events = []
    # Try selectors — specific first, generic fallback
    for sel in [
        '[data-event-id] h3', '[data-event-id] h2',
        '.tc-event__name', '.event-name',
        '.event-item h2', '.event-item h3',
        '.tt-event-title',
        'h3', 'h2',
    ]:
        items = await page.query_selector_all(sel)
        if not items: continue
        found = []
        for item in items:
            title = (await item.inner_text()).strip()
            if not title or len(title) < 4: continue
            if title.lower() in BAD_TITLES: continue
            parent = await item.evaluate_handle(
                'el => el.closest("[data-event-id]") || el.closest(".event-item") || el.closest("article") || el.parentElement.parentElement'
            )
            try:    ptext = await parent.inner_text()
            except: ptext = title
            dt = parse_date_text(ptext)
            if dt and in_range(dt):
                e = make_event(dt, club, city, cls, title, url)
                if e: found.append(e)
        if found:
            print(f"{club} (selector '{sel}'): {len(found)} events", file=sys.stderr)
            return found

    # Text-parsing fallback
    text = await page.inner_text('body')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    seen = set()
    for i, line in enumerate(lines):
        dt = parse_date_text(line)
        if not dt or not in_range(dt): continue
        for j in [i-1, i-2, i+1, i+2]:
            if 0 <= j < len(lines):
                candidate = lines[j]
                if (len(candidate) > 5
                        and not parse_date_text(candidate)
                        and candidate.lower() not in BAD_TITLES):
                    key = (dt.date(), candidate.lower())
                    if key not in seen:
                        e = make_event(dt, club, city, cls, candidate, url)
                        if e:
                            events.append(e)
                            seen.add(key)
                    break

    print(f"{club} (text parse): {len(events)} events", file=sys.stderr)
    return events


async def scrape_wp_tribe_generic(page, base, club, city, cls, url, standard_filter=None):
    """Generic WordPress/Tribe Events scraper."""
    api_events = await scrape_wp_api(page, base, club, city, cls, url)
    if api_events:
        if standard_filter:
            api_events = [e for e in api_events if not any(s in e['event'].lower() for s in standard_filter)]
        return api_events
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(3500)
    events = []
    for sel in ['.tribe-events-calendar-list__event-title a', 'h2.tribe-events-list-event-title a',
                'h3 a', 'h2 a', '.event-title a', '.eventlist-title a']:
        items = await page.query_selector_all(sel)
        if items:
            for item in items:
                title = (await item.inner_text()).strip()
                if not title or len(title) < 4: continue
                if standard_filter and any(s in title.lower() for s in standard_filter): continue
                href = await item.get_attribute('href') or url
                parent = await item.evaluate_handle('el => el.closest("article") || el.parentElement.parentElement')
                try: ptext = await parent.inner_text()
                except: ptext = title
                dt = parse_date_text(ptext)
                if dt and in_range(dt):
                    e = make_event(dt, club, city, cls, title, href)
                    if e: events.append(e)
            if events: return events
    return events


async def scrape_leboudoir(page):
    """Le Boudoir: use browser fetch() with session cookies to hit JS API.
    First visit main page to get cookies, then fetch each gallery page."""
    import html as _html
    BASE = 'https://leboudoir.club'
    MON_MAP = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
               'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
    events = []
    seen = set()
    cur_year = NOW.year

    try:
        # Visit main page first to establish session
        await page.goto(f'{BASE}/events?venue_id=1773', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)

        # Fetch all pages via browser's fetch() (has session cookies)
        all_content = ''
        for pg in range(1, 6):
            url = f'{BASE}/events?browse=future&event_type=visible&venue_id=1773&view=gallery&page={pg}'
            try:
                result = await page.evaluate(f"""
                    fetch('{url}', {{
                        headers: {{
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'text/javascript, application/javascript'
                        }}
                    }}).then(r => r.text())
                """)
                if not result or 'event_name' not in result:
                    break
                all_content += result
            except Exception as ex:
                print(f"  Le Boudoir page {pg} fetch failed: {ex}")
                break

        if not all_content:
            print("  Le Boudoir: no content fetched")
            return []

        # Parse event names from JS response
        # Format: <div class='event_name notranslate'><a ...>NAME<\/a>
        names = re.findall(r"class=\\'event_name notranslate\\'><a[^>]+>(.+?)<\\/a>", all_content)
        # Dates format: \nFri, May 22\n
        dates = re.findall(r'\\n(\w{3}),\s+(\w{3})\s+(\d{1,2})\\n', all_content)
        # Event URLs: href=\"/events/12345\"  or href=\\"/events/12345\\"
        urls  = re.findall(r'href=\\"(/events/\d+)\\"', all_content)

        print(f"  Le Boudoir: {len(names)} names, {len(dates)} dates")

        for i, name in enumerate(names):
            name = _html.unescape(name).strip()
            if not name or i >= len(dates): continue
            _, mon, day = dates[i]
            month = MON_MAP.get(mon.lower())
            if not month: continue
            try:
                dt = datetime(cur_year, month, int(day))
                if dt.date() < NOW.date():
                    dt = datetime(cur_year + 1, month, int(day))
                if not in_range(dt): continue
            except: continue
            evt_url = BASE + urls[i] if i < len(urls) else f'{BASE}/events'
            key = dt.strftime('%Y-%m-%d') + name[:15]
            if key in seen: continue
            seen.add(key)
            e = make_event(dt, 'Le Boudoir', 'City of London', 'leboudoir', name, evt_url)
            if e: events.append(e)

    except Exception as ex:
        print(f"  Le Boudoir failed: {ex}")

    print(f"  Le Boudoir total: {len(events)} events")
    return events


async def scrape_swindon(page):
    """Swindon Swingers: multiple event-type pages (WICKED, REMIX, KINKY, POWER, COITUS, SPIRIT, LUST).
    Each page lists dates as plain text. Fetch all pages, parse dates + themes."""
    import urllib.request as _ul, html as _html

    # Each entry: (event_type_name, url)
    EVENT_PAGES = [
        ("WICKED",  "https://swindonswingers.com/swindon-swingers-club-wicked-couples-event/"),
        ("REMIX",   "https://swindonswingers.com/swindon-swingers-club-remix-gay-straight-bi-bisexual-event-couples-singles/"),
        ("KINKY",   "https://swindonswingers.com/swindon-swingers-club-bdsm-kinky-fetish/"),
        ("POWER",   "https://swindonswingers.com/swindon-swingers-club-t-girls-admirers-tgirls/"),
        ("COITUS",  "https://swindonswingers.com/swindon-swingers-club-coitus/"),
        ("SPIRIT",  "https://swindonswingers.com/spirit/"),
        ("LUST",    "https://swindonswingers.com/lust/"),
    ]

    events = []
    seen = set()
    cur_year = NOW.year

    # Matches: "JUNE 6TH", "July 11th", "OCTOBER 31ST", "DECEMBER 5TH"
    date_pat = re.compile(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
        r'(\d{1,2})[a-z]{0,2}',
        re.I
    )

    for event_type, url in EVENT_PAGES:
        try:
            req = _ul.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.9',
            })
            with _ul.urlopen(req, timeout=15) as r:
                raw = r.read().decode('utf-8', errors='replace')
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = _html.unescape(text)
        except Exception as ex:
            print(f"  Swindon {event_type} failed: {ex}")
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(2000)
                text = await page.inner_text('body')
            except:
                continue

        lines = [l.strip() for l in text.split('\n') if l.strip()]

        for i, line in enumerate(lines):
            dm = date_pat.search(line)
            if not dm: continue
            month = MMAP[dm.group(1).lower()]
            day_num = int(dm.group(2))
            try:
                dt = datetime(cur_year, month, day_num)
                if dt.date() < NOW.date():
                    dt = datetime(cur_year + 1, month, day_num)
                if not in_range(dt): continue
            except: continue

            # Get theme: rest of line after date, or next non-empty line
            after_date = line[dm.end():].strip().strip('–-—').strip()
            # Clean junk like "(This one is on the second weekend...)"
            after_date = re.sub(r'\(.*?\)', '', after_date).strip()
            after_date = re.sub(r'^\*+|\*+$', '', after_date).strip()
            # Stop if after_date itself contains another date (it's not a theme name)
            if re.search(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}', after_date, re.I):
                after_date = ''

            theme = None
            if after_date and len(after_date) > 2 and after_date.upper() not in ('TBA', 'TBC', 'TB'):
                theme = after_date[:60].strip()
            else:
                # Look at next line for theme
                for j in range(i+1, min(i+4, len(lines))):
                    candidate = lines[j].strip().strip('"').strip()
                    if not candidate or len(candidate) < 3: continue
                    cu = candidate.upper()
                    if cu in ('TBA', 'TBC', '21:00', '02:30', 'RSVP'): continue
                    if re.match(r'^[£\d]', candidate): continue
                    if re.search(r'membership|pay on|door|tickets|mailing', candidate, re.I): continue
                    # Skip if candidate is just more dates
                    if re.search(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}', candidate, re.I): continue
                    theme = candidate[:60].strip()
                    break

            # Build event name
            if theme:
                event_name = f"{event_type}: {theme}"
            else:
                event_name = event_type  # Just the series name if no theme

            key = dt.strftime('%Y-%m-%d') + event_type
            if key in seen: continue
            seen.add(key)
            e = make_event(dt, 'Swindon SC', 'Swindon', 'swindon', event_name, url)
            if e: events.append(e)

    print(f"  Swindon SC: {len(events)} events")
    return events


async def scrape_infusion(page):
    """Infusion Blackpool: separate page per month, events separated by ●♡●♡●
    Format: 'Day DDth EVENT NAME description'
    Fetches current + next month pages."""
    MONTH_PAGES = {1:3,2:4,3:5,4:7,5:8,6:11,7:13,8:14,9:15,10:17,11:20,12:24}
    INFUSION_STANDARD = {
        'wicked wednesday', 'greedy girls', 'pure',
        'chillout sunday', 'chill zone sunday', 'sexy sunday',
        'seductive sunday', 'thirsty thursday',
    }
    BASE = 'https://www.infusionblackpool.co.uk'
    events = []
    seen = set()

    # Fetch current month + next month
    months_to_fetch = []
    cur_month = NOW.month
    cur_year = NOW.year
    for offset in [0, 1]:
        m = ((cur_month - 1 + offset) % 12) + 1
        y = cur_year + ((cur_month - 1 + offset) // 12)
        page_num = MONTH_PAGES.get(m)
        if page_num:
            months_to_fetch.append((m, y, page_num))

    for month_num, year, page_num in months_to_fetch:
        url = f'{BASE}/{page_num}.html'
        try:
            import urllib.request as _ul
            import html as _html
            req = _ul.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.9',
            })
            with _ul.urlopen(req, timeout=15) as r:
                raw = r.read().decode('utf-8', errors='replace')
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = _html.unescape(text)
        except Exception as ex:
            print(f"  Infusion fetch {url} failed: {ex}")
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(2000)
                text = await page.inner_text('body')
            except:
                continue

        # Validate year — skip if page still shows old year
        if str(year) not in text and str(year-1) in text:
            print(f"  Infusion {url} still showing {year-1} data, skipping")
            continue

        # Split on separator
        parts = re.split(r'●♡●♡●|●|♡', text)
        day_pattern = re.compile(
            r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+'
            r'(\d{1,2})[a-z]{0,2}\s*(.+)',
            re.I
        )
        for part in parts:
            part = part.strip()
            if not part: continue
            m = day_pattern.match(part)
            if not m: continue
            day_num = int(m.group(1))
            rest = m.group(2).strip()
            # Extract event name — all-caps portion at start
            name_match = re.match(r'^([A-Z][A-Z\s\':&!\-\.0-9]+?)(?:\s+[a-z]|\s*$)', rest)
            if name_match:
                event_name = name_match.group(1).strip().rstrip('-').strip()
            else:
                # Take first sentence / up to first lowercase word continuation
                event_name = rest.split('.')[0].strip()[:80]
            event_name = re.sub(r'\s+', ' ', event_name).strip()
            if not event_name or len(event_name) < 4: continue
            if event_name.lower() in INFUSION_STANDARD: continue
            try:
                dt = datetime(year, month_num, day_num)
                if dt < NOW - timedelta(days=1): continue
                if not in_range(dt): continue
                key = dt.strftime('%Y-%m-%d') + event_name[:15]
                if key in seen: continue
                seen.add(key)
                e = make_event(dt, 'Infusion', 'Blackpool', 'infusion',
                               event_name, f'{BASE}/{page_num}.html')
                if e: events.append(e)
            except:
                pass
    print(f"  Infusion: {len(events)} events")
    return events


async def scrape_xtasia(page, url):
    """Xtasia: plain text diary, format 'Day DDth Month: Event Name (times)'
    Site returns 403 to simple fetches — use Playwright with longer wait.
    Keep all named events."""
    XTASIA_STANDARD = {'guys and gals', 'ladies and couples night', 'open night',
                       'standard club night', 'club night'}
    # Try Playwright first
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        text = await page.inner_text('body')
    except Exception as ex:
        print(f"  Xtasia Playwright failed: {ex}")
        # Fallback: curl
        try:
            import subprocess
            result = subprocess.run([
                'curl', '-s', '-L', '--max-time', '20',
                '-H', 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
                '-H', 'Accept: text/html,application/xhtml+xml,*/*;q=0.8',
                '-H', 'Accept-Language: en-GB,en;q=0.9',
                url
            ], capture_output=True, timeout=25)
            import html as _html
            raw = result.stdout.decode('utf-8', errors='replace')
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = _html.unescape(text)
        except Exception as ex2:
            print(f"  Xtasia curl also failed: {ex2}")
            return []
    # Normalise dashes
    for ch in ['\u2013', '\u2014']:
        text = text.replace(ch, '-')
    events = []
    seen = set()
    # Format: "Day DDth Month: Event Name (times)" all on one line
    pattern = re.compile(
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+'
        r'(\d{1,2})[a-z]{0,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s*:\s*(.+?)(?:\n|\r|$)',
        re.I
    )
    cur_year = NOW.year
    for m in pattern.finditer(text):
        day_num = int(m.group(1))
        month = MMAP[m.group(2).lower()]
        raw_name = m.group(3).strip()
        # Strip times like "(8pm - 3am)"
        event_name = re.sub(r'\s*\(\d.*?\)\s*$', '', raw_name).strip()
        event_name = re.sub(r'\s*\d{1,2}pm.*$', '', event_name, flags=re.I).strip()
        event_name = event_name[:80].strip()
        if not event_name or len(event_name) < 4: continue
        if event_name.lower() in XTASIA_STANDARD: continue
        try:
            dt = datetime(cur_year, month, day_num)
            if dt < NOW - timedelta(days=1):
                dt = datetime(cur_year + 1, month, day_num)
            if not in_range(dt): continue
            key = dt.strftime('%Y-%m-%d') + event_name[:15]
            if key in seen: continue
            seen.add(key)
            e = make_event(dt, 'Xtasia', 'West Bromwich', 'xtasia', event_name, url)
            if e: events.append(e)
        except:
            pass
    print(f"  Xtasia parsed {len(events)} events")
    return events


async def scrape_pandoras(page, url):
    """Pandoras: 123-reg static site, plain text diary.
    Filter: Biphoria (every Thu), Relaxed Sunday, generic open nights."""
    PANDORA_STANDARD = {'biphoria', 'relaxed sunday', 'open to all members'}
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(3000)
    text = await page.inner_text('body')
    for ch in ['\u2013', '\u2014']:
        text = text.replace(ch, '-')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    events = []
    seen = set()
    day_pattern = re.compile(
        r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+'
        r'(\d{1,2})[a-z]{0,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)',
        re.I
    )
    SKIP_LINES = {
        'open to all members', 'all members welcome', 'event night',
        'before 7pm', 'after 7pm', 'per couple', 'per single male',
        'single female', 'trans', '8pm', '11am', 'midnight', '2am',
        'free shots', 'dj', 'guest list', 'fabswingers', 'add onto',
        'more information', 'membership required', 'relaxed sunday',
    }
    cur_year = NOW.year
    i = 0
    while i < len(lines):
        line = lines[i]
        dm = day_pattern.match(line)
        if dm:
            day_num = int(dm.group(1))
            month = MMAP[dm.group(2).lower()]
            try:
                dt = datetime(cur_year, month, day_num)
                if dt < NOW - timedelta(days=1):
                    dt = datetime(cur_year + 1, month, day_num)
                if not in_range(dt):
                    i += 1
                    continue
            except:
                i += 1
                continue
            # Scan next lines for event name
            event_name = None
            for j in range(i+1, min(i+10, len(lines))):
                candidate = lines[j].strip('*').strip()
                if not candidate or len(candidate) < 4: continue
                if day_pattern.match(candidate): break
                cl = candidate.lower()
                if any(sk in cl for sk in SKIP_LINES): continue
                if re.match(r'^\d', candidate): continue
                if re.match(r'^£', candidate): continue
                # Skip "X is hosting..." lines — get the name after
                if re.search(r'\bis hosting\b', candidate, re.I):
                    continue
                if cl in PANDORA_STANDARD: continue
                event_name = candidate[:80]
                break
            if event_name and event_name.lower() not in PANDORA_STANDARD:
                key = dt.strftime('%Y-%m-%d') + event_name[:15]
                if key not in seen:
                    seen.add(key)
                    e = make_event(dt, 'Pandoras', 'Armley, Leeds', 'pandora',
                                   event_name, 'https://www.pandoraswingers.com/event-diary')
                    if e: events.append(e)
        i += 1
    return events


async def scrape_partners(page, url):
    """Partners Swingers Club: custom WordPress weekly layout.
    Format: day + date line, then h3 event name.
    Filter: Biphoria Bisexual Day & Night (every Thu), Swing Sunday (every Sun)."""
    PARTNERS_STANDARD = {'biphoria bisexual day & night', 'swing sunday'}
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    await page.wait_for_timeout(3500)
    events = []
    seen = set()
    text = await page.inner_text('body')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    # Pattern: "Thursday 21st May" or "Friday 22nd May" etc
    day_pattern = re.compile(
        r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+'
        r'(\d{1,2})[a-z]{0,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)',
        re.I
    )
    cur_year = NOW.year
    for i, line in enumerate(lines):
        dm = day_pattern.match(line)
        if not dm: continue
        day_num = int(dm.group(1))
        month = MMAP[dm.group(2).lower()]
        try:
            dt = datetime(cur_year, month, day_num)
            if dt < NOW - timedelta(days=1):
                dt = datetime(cur_year + 1, month, day_num)
            if not in_range(dt): continue
        except: continue
        # Event name is in next few lines — skip label lines, find the name
        event_name = None
        for j in range(i+1, min(i+6, len(lines))):
            candidate = lines[j].strip()
            if not candidate or len(candidate) < 4: continue
            if day_pattern.match(candidate): break  # hit next date
            # Skip label lines like "Partners weekly event", "Hosted event", times, guest list
            if candidate.lower() in ('partners weekly event','hosted event','partners event',
                                     'partners special event','hosted by partners',
                                     'no guest list required','check event details before travelling',
                                     'times','guest list'): continue
            if re.match(r'^\d{1,2}(AM|PM)', candidate, re.I): continue
            if re.match(r'^hosted by ', candidate, re.I): continue
            if re.match(r'^guest list only', candidate, re.I): continue
            event_name = candidate
            break
        if not event_name: continue
        if event_name.lower() in PARTNERS_STANDARD: continue
        if event_name.lower() == 'swing sunday': continue
        key = dt.strftime('%Y-%m-%d') + event_name[:15]
        if key in seen: continue
        seen.add(key)
        e = make_event(dt, 'Partners', 'Bury, Manchester', 'partners', event_name, url)
        if e: events.append(e)
    return events


async def scrape_penthouse(page, url):
    """Penthouse Playrooms Dunstable: custom Laravel app, Playwright.
    Tries JSON data-page (Inertia), window state, then DOM selectors.
    """
    import sys, json as _json
    events = []
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # Log what we can see for debugging
        text = await page.evaluate("document.body.innerText")
        print(f"Penthouse body text (first 500): {text[:500]}", file=sys.stderr)

        # Try Inertia.js data-page JSON
        inertia = await page.evaluate("""
            (() => {
                const el = document.querySelector('[data-page]');
                if (el) return el.getAttribute('data-page');
                return null;
            })()
        """)
        if inertia:
            try:
                data = _json.loads(inertia)
                print(f"Penthouse Inertia data keys: {list(data.keys())}", file=sys.stderr)
                # Walk props for events
                props = data.get('props', {})
                for key in ['events', 'upcomingEvents', 'data']:
                    if key in props:
                        for ev in props[key]:
                            name = ev.get('title') or ev.get('name') or ''
                            date_str = ev.get('date') or ev.get('start_date') or ev.get('starts_at') or ''
                            ev_url = ev.get('url') or ev.get('slug') or url
                            if not ev_url.startswith('http'):
                                ev_url = 'https://penthouse-playrooms.co.uk/' + ev_url.lstrip('/')
                            if name and date_str:
                                try:
                                    dt = datetime.fromisoformat(str(date_str)[:10])
                                    if in_range(dt):
                                        e = make_event(dt, 'Penthouse Playrooms', 'Dunstable', 'penthouse', name, ev_url)
                                        if e: events.append(e)
                                except: pass
                if events:
                    print(f"Penthouse: {len(events)} events via Inertia", file=sys.stderr)
                    return events
            except Exception as ex:
                print(f"Penthouse Inertia parse error: {ex}", file=sys.stderr)

        # Try window.__page__ or similar state
        for js_var in ['window.__page__', 'window.__INERTIA__', 'window.events', 'window.pageData']:
            try:
                val = await page.evaluate(f"JSON.stringify({js_var})")
                if val and val != 'undefined':
                    print(f"Penthouse {js_var}: {val[:200]}", file=sys.stderr)
            except: pass

        # DOM selectors — try common event card patterns
        for sel in [
            'article.event', '.event-card', '.event-item',
            '[class*="event"] h2', '[class*="event"] h3',
            'h2.event-title', 'h3.event-title',
            '.events-list h2', '.events-list h3',
            'main h2', 'main h3',
        ]:
            items = await page.query_selector_all(sel)
            if not items:
                continue
            print(f"Penthouse selector '{sel}' matched {len(items)}", file=sys.stderr)
            for item in items:
                title = (await item.inner_text()).strip()
                # Find nearest date text
                parent = await item.evaluate_handle(
                    "el => el.closest('article') || el.closest('section') || el.parentElement"
                )
                ptext = ''
                try: ptext = await parent.inner_text()
                except: pass
                dt = parse_date_text(ptext) or parse_date_text(title)
                href = url
                try:
                    a = await item.query_selector('a')
                    if not a:
                        a = await item.evaluate_handle("el => el.closest('a')")
                    if a: href = await a.get_attribute('href') or url
                except: pass
                if not href.startswith('http'):
                    href = 'https://penthouse-playrooms.co.uk/' + href.lstrip('/')
                if dt:
                    e = make_event(dt, 'Penthouse Playrooms', 'Dunstable', 'penthouse', title, href)
                    if e: events.append(e)
            if events: break

    except Exception as ex:
        print(f"Penthouse scraper error: {ex}", file=sys.stderr)

    print(f"Penthouse: {len(events)} events", file=sys.stderr)
    return events


async def scrape_atlantis(page, url):
    """atlantisEVOLUTION Stoke-on-Trent: static HTML calendar, urllib.
    Standard nights filtered: MEGA Fridays, The NEW Saturdays, Evolutionfetish.
    """
    import sys
    try:
        req = _urllib.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with _urllib.urlopen(req, timeout=20) as r:
            html = r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"atlantisEVOLUTION fetch error: {e}", file=sys.stderr)
        return []

    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\s+', ' ', text)

    MONTHS_PAT = 'January|February|March|April|May|June|July|August|September|October|November|December'
    DAYS_PAT   = 'Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday'
    MMAP_L = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
               'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}

    dpat = re.compile(rf'({DAYS_PAT})\s+(\d{{1,2}})\s+({MONTHS_PAT})(?:\s+(\d{{4}}))?', re.I)
    matches = list(dpat.finditer(text))

    ATLANTIS_STD = {
        'mega friday', 'mega fridays', 'the new saturday', 'evolutionfetish',
        'closed', 'christmas day', 'boxing day'
    }

    events = []
    for i, m in enumerate(matches):
        dname, dnum, mname, ystr = m.groups()
        year  = int(ystr) if ystr else NOW.year
        month = MMAP_L[mname.lower()]
        try:
            dt = datetime(year, month, int(dnum))
            if not ystr and dt.date() < (NOW - timedelta(days=30)).date():
                dt = datetime(year + 1, month, int(dnum))
        except ValueError:
            continue
        if not in_range(dt):
            continue

        seg_start = m.end()
        seg_end   = matches[i+1].start() if i+1 < len(matches) else len(text)
        segment   = text[seg_start:seg_end].strip()

        # Remove "Singles and Couples Friday 9pm-2am ... Bring Proper ID to Join" boilerplate
        segment = re.sub(
            r'(?:Singles and Couples|Couples and Single Fems).*?(?:Bring Proper ID to Join)',
            '', segment, flags=re.I|re.S).strip()
        segment = re.sub(r'\s+', ' ', segment).strip()

        name = re.split(r'\s{2,}', segment)[0].strip()[:120].strip(" '|.")

        # Strip Atlantis-specific trailing taglines
        name = re.sub(r'\s+BOUNCY\b.*',           '', name, flags=re.I).strip()
        name = re.sub(r'\s+Dress-up if you.*',      '', name, flags=re.I).strip()
        name = re.sub(r'\s+\d+ Years of.*',         '', name, flags=re.I).strip()
        name = re.sub(r'\s+Hot Diggity.*',           '', name, flags=re.I).strip()
        name = re.sub(r'\s+All the Clubland.*',      '', name, flags=re.I).strip()
        name = re.sub(r"\s+Meet \|.*",              '', name, flags=re.I).strip()
        name = re.sub(r"\s+A proper fun-filled.*",   '', name, flags=re.I).strip()
        name = name.strip(" '|.")

        if not name or len(name) < 4:
            continue
        nl = name.lower()
        if any(s in nl for s in ATLANTIS_STD):
            continue
        if re.match(r'^(extended|visit friday|bring proper)', nl, re.I):
            continue

        e = make_event(dt, 'atlantisEVOLUTION', 'Stoke-on-Trent', 'atlantis', name, url)
        if e:
            events.append(e)

    print(f"atlantisEVOLUTION: {len(events)} events", file=sys.stderr)
    return events


async def scrape_ignite(page, url):
    """Club Ignite West Drayton: TEC REST API (urllib first, Playwright DOM fallback).
    Their security plugin blocks the API from some IPs — fall back to page scraping.
    """
    import sys

    # Try urllib API first
    api = 'https://club-ignite.co.uk/wp-json/tribe/events/v1/events?per_page=50&start_date=' + NOW.strftime('%Y-%m-%d')
    try:
        req = _urllib.Request(api, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        with _urllib.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        events = []
        for ev in data.get('events', []):
            try:
                dt = datetime.fromisoformat(ev['start_date'][:10])
                if in_range(dt):
                    title = re.sub(r'<[^>]+>', '', ev.get('title', '')).strip()
                    if title and title.lower() not in IGNITE_STANDARD:
                        e = make_event(dt, 'Club Ignite', 'West Drayton', 'ignite', title, url)
                        if e: events.append(e)
            except: pass
        if events:
            print(f"Club Ignite (API): {len(events)} events", file=sys.stderr)
            return events
    except Exception as ex:
        print(f"Club Ignite API error: {ex} — trying Playwright", file=sys.stderr)

    # Playwright DOM fallback — load events page, parse TEC event cards
    events = []
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(4000)

        # Also try browser-side API fetch from within page context
        api_result = await page.evaluate(
            f'fetch("{api}",{{headers:{{"Accept":"application/json"}}}}).then(r=>r.ok?r.json():null).catch(()=>null)'
        )
        if api_result and isinstance(api_result, dict) and api_result.get('events'):
            for ev in api_result['events']:
                try:
                    dt = datetime.fromisoformat(ev['start_date'][:10])
                    if in_range(dt):
                        title = re.sub(r'<[^>]+>', '', ev.get('title', '')).strip()
                        if title and title.lower() not in IGNITE_STANDARD:
                            e = make_event(dt, 'Club Ignite', 'West Drayton', 'ignite', title, url)
                            if e: events.append(e)
                except: pass
            if events:
                print(f"Club Ignite (in-page fetch): {len(events)} events", file=sys.stderr)
                return events

        # DOM scraping — TEC event titles + date text
        for sel in [
            '.tribe-events-calendar-list__event-title a',
            '.tribe-event-url', 'h2.tribe-events-list-event-title a',
            '.tribe-common-h6 a', 'h2 a', 'h3 a',
        ]:
            items = await page.query_selector_all(sel)
            if not items:
                continue
            for item in items:
                title = (await item.inner_text()).strip()
                href  = await item.get_attribute('href') or url
                parent = await item.evaluate_handle(
                    "el => el.closest('article') || el.closest('.tribe-events-calendar-list__event') || el.parentElement.parentElement"
                )
                try:    ptext = await parent.inner_text()
                except: ptext = title
                dt = parse_date_text(ptext)
                if dt and in_range(dt) and title.lower() not in IGNITE_STANDARD:
                    e = make_event(dt, 'Club Ignite', 'West Drayton', 'ignite', title, href)
                    if e: events.append(e)
            if events: break

    except Exception as ex:
        print(f"Club Ignite Playwright error: {ex}", file=sys.stderr)

    print(f"Club Ignite (DOM): {len(events)} events", file=sys.stderr)
    return events


async def scrape_all(page):
    results = {}

    async def run(name, coro):
        print(f"Scraping {name}...")
        try:
            evs = await coro
            seen = set()
            uniq = []
            for e in evs:
                k = (e['d'], e['event'][:20])
                if k not in seen:
                    seen.add(k)
                    uniq.append(e)
            results[name] = uniq
            print(f"  -> {len(uniq)} events")
        except Exception as ex:
            print(f"  ERROR {name}: {ex}")
            results[name] = []
        finally:
            # Reset page after each club to prevent corrupted state from affecting next scraper
            try:
                await page.goto("about:blank", timeout=5000)
            except:
                pass

    await run("No.3 Club",        scrape_no3(page, "https://theno3club.co.uk/"))
    await run("Cupids",           scrape_cupids(page, "https://www.cupidsswingersclub.co.uk/events"))
    await run("Partners",         scrape_partners(page, "https://partnersswingersclub.com/events/"))
    await run("Pandoras",         scrape_pandoras(page, "https://www.pandoraswingers.com/event-diary"))
    await run("Club Play",        scrape_clubplay(page, "https://clubplay.net/events/"))
    await run("Xtasia",           scrape_xtasia(page, "https://www.xtasia.co.uk/page/2-months-diary"))
    await run("Naughty Pineapple",scrape_naughtypineapple(page, "https://thenaughtypineapple.co.uk/all-events/"))
    await run("The Attic",        scrape_attic(page, "https://theatticexperience.com/events-prices-2/"))
    await run("Townhouse",        scrape_tickettailor(page, "https://www.tickettailor.com/events/townhousewirralltd", "Townhouse", "Birkenhead, Wirral", "townhouse"))
    await run("Swindon SC",       scrape_swindon(page))
    await run("Club Alchemy",     scrape_clubalchemy(page, "https://www.clubalchemy.co.uk/events"))
    await run("Infusion",         scrape_infusion(page))
    await run("Quest",            scrape_quest(page, "https://questswingersclub.co.uk/upcoming-events/"))
    await run("Liberty Elite",    scrape_libertyelite(page, "https://libertyelite.co.uk/events/list/?tribe-bar-date=" + NOW.strftime('%Y-%m-%d')))
    await run("Purple Mamba",     scrape_purplemamba(page, "https://www.purplemambaclub.com/what-s-on-tickets"))
    await run("HU9",              scrape_hu9(page, "https://hu9swingersclub.co.uk/events"))
    await run("Shhh",             scrape_shhh(page, "https://www.shhhclub.co.uk/events"))
    await run("Decadance",        scrape_decadance(page, "https://www.decadanceswingersclub.com/what-s-on-at-decadance"))
    await run("New Gatehouse",    scrape_wp_tribe_generic(page, "https://www.thenewgatehousebolton.co.uk", "New Gatehouse", "Bolton", "gatehouse", "https://www.thenewgatehousebolton.co.uk/about-1"))
    await run("Le Boudoir",       scrape_leboudoir(page))
    await run("Penthouse Playrooms", scrape_penthouse(page, "https://penthouse-playrooms.co.uk/events"))
    await run("Club Ignite", scrape_ignite(page, "https://club-ignite.co.uk/events-new/"))
    await run("atlantisEVOLUTION", scrape_atlantis(page, "http://www.atlantisevolution.co.uk/calendar.htm"))
    await run("Chameleons",       scrape_chameleons(page, "https://www.chameleons.cc/darlaston-events/"))

    return results


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled']
        )
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
            viewport={'width': 390, 'height': 844},
            locale='en-GB',
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = await ctx.new_page()
        results = await scrape_all(page)
        await browser.close()

    all_events = []
    for evs in results.values():
        all_events.extend(evs)

    seen = set()
    unique = []
    for e in sorted(all_events, key=lambda x: x['d']):
        k = (e['d'], e['club'])
        if k not in seen:
            seen.add(k)
            unique.append(e)

    with open('events_scraped.json', 'w') as f:
        json.dump(unique, f, indent=2)

    print("\n=== RESULTS ===")
    total = 0
    for name, evs in results.items():
        status = f"YES {len(evs)}" if evs else "NO"
        print(f"  {name}: {status}")
        total += len(evs)
    print(f"\nTotal scraped: {total}")


asyncio.run(main())

