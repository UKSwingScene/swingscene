import json, base64
from datetime import datetime

# Load manually researched events (always present as fallback)
with open('events.json') as f:
    manual = json.load(f)

# Load freshly scraped events
try:
    with open('events_scraped.json') as f:
        scraped = json.load(f)
    print(f"Scraped: {len(scraped)} events")
except:
    scraped = []
    print("No scraped events, using manual only")

# Merge: manual first, scraped overrides only if event name is clean
# Manual events always win — scraped only adds NEW events not in manual
import re as _re
def _is_bad(name):
    if not name or len(name) < 6: return True
    n = name.lower()
    bad = ['more info','google calendar','ics','view event','powered by','events list','event list',
           'sat, ','sun, ','mon, ','tue, ','wed, ','thu, ','fri, ',
           'pm sun','am sun','pm sat','am sat','subscribe','follow',
           'sign up','cookie','found','event name','copyright']
    if any(x in n for x in bad): return True
    if _re.match(r'^[\d\s:apm,\-\/\.]+$', n, _re.I): return True
    return False

merged = {}
for e in manual:
    merged[(e['d'], e['club'])] = e
for e in scraped:
    key = (e['d'], e['club'])
    ev = e.get('event', '')
    # Only add scraped event if: not in manual AND has a clean name
    if key not in merged and not _is_bad(ev):
        merged[key] = e

events = sorted(merged.values(), key=lambda x: x['d'])
print(f"Total merged events: {len(events)}")

with open('gemini_logo.mp4', 'rb') as f:
    vid_b64 = base64.b64encode(f.read()).decode()

video_tag = f'<video src="data:video/mp4;base64,{vid_b64}" autoplay loop muted playsinline style="width:100%;height:100%;object-fit:contain;display:block;"></video>'
updated = datetime.now().strftime("%-d %B %Y")
events_js = json.dumps(events, ensure_ascii=False)

with open('template.html') as f:
    html = f.read()

html = html.replace('VIDEO_TAG_PLACEHOLDER', video_tag)
html = html.replace('UPDATED_PLACEHOLDER', updated)
html = html.replace('EVENTS_JS_PLACEHOLDER', events_js)

with open('index.html', 'w') as f:
    f.write(html)
print(f"Built index.html — {len(html)//1024}KB")
