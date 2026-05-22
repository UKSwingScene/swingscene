import json, base64
from datetime import datetime

# Load manually researched events (always present as fallback)
with open('events.json') as f:
    manual = json.load(f)

# Load freshly scraped events (may be empty if scraper found nothing)
try:
    with open('events_scraped.json') as f:
        scraped = json.load(f)
    print(f"Scraped: {len(scraped)} events")
except:
    scraped = []
    print("No scraped events file found, using manual only")

# Merge: scraped takes priority, manual fills gaps
# Key by date+club to deduplicate
merged = {}
for e in manual:
    merged[(e['d'], e['club'])] = e
for e in scraped:
    # Only override manual if scraped has a real event name
    if e.get('event') and 'Event' not in e['event']:
        merged[(e['d'], e['club'])] = e
    elif (e['d'], e['club']) not in merged:
        merged[(e['d'], e['club'])] = e

events = sorted(merged.values(), key=lambda x: x['d'])
print(f"Total merged events: {len(events)}")

# Load logo
with open('gemini_logo.mp4', 'rb') as f:
    vid_b64 = base64.b64encode(f.read()).decode()

video_tag = f'<video src="data:video/mp4;base64,{vid_b64}" autoplay loop muted playsinline style="width:100%;height:100%;object-fit:contain;display:block;"></video>'
updated = datetime.now().strftime("%-d %B %Y")
events_js = json.dumps(events, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>SwingScene – UK Lifestyle Events</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#09090F;--surface:#111118;--surf2:#181825;--border:#22222E;--gold:#C9963A;--text:#E4DFD8;--muted:#6B6580;--dim:#3A3650;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Barlow',sans-serif;min-height:100vh;}}
.site-header{{background:var(--bg);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;}}
.logo-block{{display:flex;flex-direction:column;align-items:center;padding:14px 16px 8px;}}
.logo-container{{width:250px;height:150px;max-width:92vw;max-height:55vw;display:flex;align-items:center;justify-content:center;border-radius:10px;overflow:hidden;background:none;border:none;}}
.filter-row{{display:flex;gap:6px;padding:8px 14px 12px;justify-content:center;flex-wrap:wrap;}}
.filter-btn{{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:7px 18px;border-radius:20px;font-size:15px;font-family:'Barlow Condensed',sans-serif;font-weight:700;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;transition:all .18s;}}
.filter-btn.active,.filter-btn:hover{{background:var(--gold);color:#09090F;border-color:var(--gold);}}
.main{{max-width:600px;margin:0 auto;padding:12px 14px 40px;}}
.date-header{{font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);padding:16px 0 8px;border-bottom:1px solid var(--border);margin-bottom:8px;}}
.event-card{{display:block;background:var(--surface);border:1px solid var(--border);border-left:4px solid;border-radius:10px;padding:14px 16px;margin-bottom:10px;text-decoration:none;color:inherit;transition:transform .15s,box-shadow .15s;}}
.event-card:hover{{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,.4);}}
.card-title{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px;}}
.card-title-left{{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px;flex:1;}}
.event-club{{font-family:'Barlow Condensed',sans-serif;font-size:22px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;}}
.title-sep{{color:var(--muted);font-size:18px;}}
.event-name{{font-size:20px;font-weight:600;color:var(--text);line-height:1.2;}}
.card-arrow{{color:var(--muted);font-size:18px;flex-shrink:0;}}
.event-city{{font-size:14px;color:var(--muted);margin-bottom:7px;}}
.event-desc{{font-size:16px;color:#8a85a0;line-height:1.55;}}
.rec-section{{max-width:600px;margin:0 auto;padding:0 14px 40px;}}
.rec-toggle{{width:100%;background:var(--surface);border:1px solid var(--border);border-radius:10px;color:var(--gold);padding:14px 18px;font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;display:flex;justify-content:space-between;align-items:center;}}
.rec-toggle.open{{border-radius:10px 10px 0 0;}}
.rec-body{{display:none;background:var(--surface);border:1px solid var(--border);border-top:none;border-radius:0 0 10px 10px;padding:8px 10px;}}
.rec-body.open{{display:block;}}
.rec-card{{display:block;text-decoration:none;color:inherit;border-left:4px solid;border-radius:0 8px 8px 0;background:rgba(255,255,255,.02);padding:12px 14px;margin:6px 0;}}
.rec-club{{font-family:'Barlow Condensed',sans-serif;font-size:20px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px;}}
.rec-city{{font-size:14px;color:var(--muted);margin-bottom:6px;}}
.rec-schedule{{font-size:17px;color:#7a7590;line-height:1.6;}}
.rec-line::before{{content:"· ";color:var(--gold);}}
.site-footer{{background:var(--surf2);border-top:1px solid var(--border);padding:18px 16px;font-size:15px;color:var(--muted);line-height:1.7;margin-top:8px;text-align:center;}}
.site-footer strong{{color:var(--gold);}}
.empty{{text-align:center;padding:48px 16px;color:var(--dim);font-size:20px;}}
.c-alchemy{{border-left-color:#8B5CF6;}}.c-alchemy .event-club,.c-alchemy .rec-club{{color:#8B5CF6;}}
.c-liberty{{border-left-color:#D97706;}}.c-liberty .event-club,.c-liberty .rec-club{{color:#D97706;}}
.c-mamba{{border-left-color:#A855F7;}}.c-mamba .event-club,.c-mamba .rec-club{{color:#A855F7;}}
.c-pandora{{border-left-color:#10B981;}}.c-pandora .event-club,.c-pandora .rec-club{{color:#10B981;}}
.c-attic{{border-left-color:#EF4444;}}.c-attic .event-club,.c-attic .rec-club{{color:#EF4444;}}
.c-townhouse{{border-left-color:#6366F1;}}.c-townhouse .event-club,.c-townhouse .rec-club{{color:#6366F1;}}
.c-swindon{{border-left-color:#0EA5E9;}}.c-swindon .event-club,.c-swindon .rec-club{{color:#0EA5E9;}}
.c-infusion{{border-left-color:#06B6D4;}}.c-infusion .event-club,.c-infusion .rec-club{{color:#06B6D4;}}
.c-decadance{{border-left-color:#F472B6;}}.c-decadance .event-club,.c-decadance .rec-club{{color:#F472B6;}}
.c-chameleons{{border-left-color:#34D399;}}.c-chameleons .event-club,.c-chameleons .rec-club{{color:#34D399;}}
.c-pineapple{{border-left-color:#F59E0B;}}.c-pineapple .event-club,.c-pineapple .rec-club{{color:#F59E0B;}}
.c-quest{{border-left-color:#FB923C;}}.c-quest .event-club,.c-quest .rec-club{{color:#FB923C;}}
.c-cupids{{border-left-color:#EC4899;}}.c-cupids .event-club,.c-cupids .rec-club{{color:#EC4899;}}
.c-shhh{{border-left-color:#818CF8;}}.c-shhh .event-club,.c-shhh .rec-club{{color:#818CF8;}}
.c-xtasia{{border-left-color:#F87171;}}.c-xtasia .event-club,.c-xtasia .rec-club{{color:#F87171;}}
.c-clubplay{{border-left-color:#4ADE80;}}.c-clubplay .event-club,.c-clubplay .rec-club{{color:#4ADE80;}}
.c-no3{{border-left-color:#38BDF8;}}.c-no3 .event-club,.c-no3 .rec-club{{color:#38BDF8;}}
.c-partners{{border-left-color:#FBBF24;}}.c-partners .event-club,.c-partners .rec-club{{color:#FBBF24;}}
.c-gatehouse{{border-left-color:#A3E635;}}.c-gatehouse .event-club,.c-gatehouse .rec-club{{color:#A3E635;}}
.c-leboudoir{{border-left-color:#E879F9;}}.c-leboudoir .event-club,.c-leboudoir .rec-club{{color:#E879F9;}}
</style>
</head>
<body>
<header class="site-header">
  <div class="logo-block">
    <div class="logo-container">{video_tag}</div>
  </div>
  <div class="filter-row">
    <button class="filter-btn active" onclick="setFilter('all',this)">All</button>
    <button class="filter-btn" onclick="setFilter('jan',this)">Jan</button>
    <button class="filter-btn" onclick="setFilter('feb',this)">Feb</button>
    <button class="filter-btn" onclick="setFilter('mar',this)">Mar</button>
    <button class="filter-btn" onclick="setFilter('apr',this)">Apr</button>
    <button class="filter-btn" onclick="setFilter('may',this)">May</button>
    <button class="filter-btn" onclick="setFilter('jun',this)">Jun</button>
    <button class="filter-btn" onclick="setFilter('jul',this)">Jul</button>
    <button class="filter-btn" onclick="setFilter('aug',this)">Aug</button>
    <button class="filter-btn" onclick="setFilter('sep',this)">Sep</button>
    <button class="filter-btn" onclick="setFilter('oct',this)">Oct</button>
    <button class="filter-btn" onclick="setFilter('nov',this)">Nov</button>
    <button class="filter-btn" onclick="setFilter('dec',this)">Dec</button>
  </div>
</header>
<main class="main" id="main"></main>
<div class="rec-section">
  <button class="rec-toggle" id="recBtn" onclick="toggleRec()">Regular &amp; Weekly Events<span id="recArrow" style="transition:transform .2s">▼</span></button>
  <div class="rec-body" id="recBody"></div>
</div>
<footer class="site-footer">
  <strong>Last updated:</strong> {updated} · Sources: Club websites &amp; Ticket Tailor<br>
  Always verify before attending — schedules can change. Tap any card to visit the club's website.
</footer>
<script>
const EVENTS={events_js};
const RECURRING=[
  {{club:"No.3 Club",city:"Chorley, Lancashire",cls:"no3",lines:["Sat: Mixed Swing Night 8:30pm–1:30am","Sun (fortnightly): Super Sexy Sunday 4pm–10pm","Wed (1st & 3rd): Greedy Girls Day 1pm–8pm","Fri: Intro Night (2nd Fri) · Black Friday (4th Fri)","⚠️ First visit MUST call Mary — 07835 870772"],url:"https://theno3club.co.uk/"}},
  {{club:"Cupids",city:"Swinton, Manchester",cls:"cupids",lines:["Open 7 nights a week","30+ year heritage","Relaxed dress-down policy","Couples & singles welcome"],url:"https://cupidsswingers.co.uk/"}},
  {{club:"Chameleons",city:"Darlaston, West Midlands",cls:"chameleons",lines:["Open 7 days a week","Hot tub, sauna, themed playrooms","Couples & singles welcome"],url:"https://www.chameleons.cc/"}},
  {{club:"Townhouse",city:"Birkenhead, Wirral",cls:"townhouse",lines:["Regular Fri & Sat events","4 floors · Hot tubs · Dungeon","25,000+ members · LGBTQ+ friendly","Check Tickettailor for full schedule"],url:"https://www.tickettailor.com/events/townhousewirral"}},
  {{club:"Xtasia",city:"West Bromwich",cls:"xtasia",lines:["UK's longest-established lifestyle club","Nightclub · Spa · Pool · Cinema · Hotel","Regular Sat events + themed nights"],url:"https://www.xtasia.co.uk/"}},
  {{club:"Infusion",city:"North West",cls:"infusion",lines:["North West's largest lifestyle venue","Multiple play areas & jacuzzi","Regular Saturday events"],url:"https://www.infusionclub.co.uk/"}},
  {{club:"Purple Mamba",city:"Nottingham",cls:"mamba",lines:["Weekly Saturday events","Premium lifestyle club","Smart dress code"],url:"https://www.purplemambaclub.com/"}},
  {{club:"Shhh",city:"Newcastle",cls:"shhh",lines:["Regular weekend events","Friendly North East club","Easy online membership"],url:"https://www.shhhclub.co.uk/"}},
];
let f='all';
function setFilter(m,btn){{f=m;document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');render();}}
function render(){{
  const main=document.getElementById('main');
  const evts=f==='all'?EVENTS:EVENTS.filter(e=>e.m===f);
  if(!evts.length){{main.innerHTML='<div class="empty">No events found for this month.</div>';return;}}
  const g={{}};evts.forEach(e=>{{if(!g[e.day])g[e.day]=[];g[e.day].push(e);}});
  let h='';
  Object.keys(g).forEach(day=>{{
    h+=`<div class="date-header">${{day}}</div>`;
    g[day].forEach(e=>{{
      h+=`<a class="event-card c-${{e.cls}}" href="${{e.url}}" target="_blank" rel="noopener">
        <div class="card-title"><div class="card-title-left"><span class="event-club">${{e.club}}</span><span class="title-sep">·</span><span class="event-name">${{e.event}}</span></div><span class="card-arrow">→</span></div>
        <div class="event-city">📍 ${{e.city}}</div>
        <div class="event-desc">${{e.desc}}</div></a>`;
    }});
  }});
  main.innerHTML=h;
}}
function toggleRec(){{const btn=document.getElementById('recBtn');const body=document.getElementById('recBody');const arrow=document.getElementById('recArrow');btn.classList.toggle('open');body.classList.toggle('open');arrow.style.transform=body.classList.contains('open')?'rotate(180deg)':'';}}
document.getElementById('recBody').innerHTML=RECURRING.map(r=>`<a class="rec-card c-${{r.cls}}" href="${{r.url}}" target="_blank" rel="noopener"><div class="rec-club">${{r.club}}</div><div class="rec-city">📍 ${{r.city}}</div><div class="rec-schedule">${{r.lines.map(l=>`<div class="rec-line">${{l}}</div>`).join('')}}</div></a>`).join('');
render();
</script>
</body>
</html>"""

with open('index.html', 'w') as f:
    f.write(html)
print(f"Built index.html — {len(html)//1024}KB")
