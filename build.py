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
merged = {}
for e in manual:
    merged[(e['d'], e['club'])] = e
for e in scraped:
    ev = e.get('event', '')
    bad = ['found', 'event name', 'pm -', 'am -', '8:00', '7:00', '9:00', '10:00']
    if ev and len(ev) > 8 and not any(x in ev.lower() for x in bad):
        merged[(e['d'], e['club'])] = e
    elif (e['d'], e['club']) not in merged:
        merged[(e['d'], e['club'])] = e

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
