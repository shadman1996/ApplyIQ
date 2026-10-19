"""
Master Harvester & Geographic Distance Ranker for Summer 2027 IT & Cybersecurity Jobs.
Target Origin: Marshall, MN 56258 (SMSU) [Lat: 44.4469, Lon: -95.7883]
"""

import asyncio
import json
import math
import os
import re
import websockets

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
QUEUE_PATH = os.path.join(PROJECT_ROOT, "data", "summer_2027_ranked_queue.json")
MARSHALL_COORDS = (44.4469, -95.7883)

# US city/state coordinates for distance calculation
CITY_COORDS = {
    # Local & MN
    "marshall, mn": (44.4469, -95.7883),
    "pipestone, mn": (44.0041, -96.3181),
    "granite falls, mn": (44.8105, -95.5447),
    "willmar, mn": (45.1219, -95.0433),
    "mankato, mn": (44.1636, -93.9994),
    "st. cloud, mn": (45.5579, -94.1632),
    "avon, mn": (45.6105, -94.4536),
    "hopkins, mn": (44.9250, -93.4130),
    "edina, mn": (44.8897, -93.3499),
    "minneapolis, mn": (44.9778, -93.2650),
    "st. louis park, mn": (44.9472, -93.3566),
    "bloomington, mn": (44.8408, -93.2983),
    "plymouth, mn": (45.0105, -93.4555),
    "minnetonka, mn": (44.9211, -93.4688),
    "st. paul, mn": (44.9537, -93.0900),
    "maplewood, mn": (44.9530, -92.9958),
    "inver grove heights, mn": (44.8480, -93.0583),
    "lakeville, mn": (44.6497, -93.2427),
    "eagan, mn": (44.8041, -93.1669),
    "oak park heights, mn": (45.0319, -92.8024),
    "rochester, mn": (44.0121, -92.4802),
    "duluth, mn": (46.7867, -92.1005),
    
    # Regional
    "sioux falls, sd": (43.5446, -96.7311),
    "fargo, nd": (46.8772, -96.7898),
    "omaha, ne": (41.2565, -95.9345),
    "west des moines, ia": (41.5772, -93.7460),
    "des moines, ia": (41.5868, -93.6250),
    "madison, wi": (43.0731, -89.4012),
    "milwaukee, wi": (43.0389, -87.9065),
    "chicago, il": (41.8781, -87.6298),
    "bolingbrook, il": (41.6986, -88.0684),
    "clayton, mo": (38.6426, -90.3237),
    "st. louis, mo": (38.6270, -90.1994),
    "kansas city, mo": (39.0997, -94.5786),
    "indianapolis, in": (39.7684, -86.1581),
    "columbus, in": (39.2014, -85.9214),
    "cincinnati, oh": (39.1031, -84.5120),
    "columbus, oh": (39.9612, -82.9988),
    "cleveland, oh": (41.4993, -81.6944),
    "detroit, mi": (42.3314, -83.0458),
    
    # National
    "pittsburgh, pa": (40.4406, -79.9959),
    "philadelphia, pa": (39.9526, -75.1652),
    "bethlehem, pa": (40.6259, -75.3705),
    "new york, ny": (40.7128, -74.0060),
    "new york city, ny": (40.7128, -74.0060),
    "jersey city, nj": (40.7178, -74.0431),
    "boston, ma": (42.3601, -71.0589),
    "washington, dc": (38.9072, -77.0369),
    "mclean, va": (38.9339, -77.1773),
    "alexandria, va": (38.8048, -77.0469),
    "charlotte, nc": (35.2271, -80.8431),
    "raleigh, nc": (35.7796, -78.6382),
    "atlanta, ga": (33.7490, -84.3880),
    "tampa, fl": (27.9506, -82.4572),
    "miami, fl": (25.7617, -80.1918),
    "dallas, tx": (32.7767, -96.7970),
    "austin, tx": (30.2672, -97.7431),
    "houston, tx": (29.7604, -95.3698),
    "denver, co": (39.7392, -104.9903),
    "phoenix, az": (33.4484, -112.0740),
    "salt lake city, ut": (40.7608, -111.8910),
    "seattle, wa": (47.6062, -122.3321),
    "san francisco, ca": (37.7749, -122.4194),
    "san jose, ca": (37.3382, -121.8863),
    "los angeles, ca": (34.0522, -118.2437),
    "sherman oaks, ca": (34.1508, -118.4489),
    "san diego, ca": (32.7157, -117.1611)
}

STATE_COORDS = {
    "mn": (45.0, -94.0),
    "sd": (44.0, -99.0),
    "nd": (47.0, -100.0),
    "ia": (42.0, -93.5),
    "wi": (44.5, -89.5),
    "ne": (41.5, -99.5),
    "il": (40.0, -89.0),
    "mo": (38.5, -92.5),
    "in": (40.0, -86.0),
    "oh": (40.0, -82.5),
    "mi": (44.0, -85.0),
    "tx": (31.0, -99.0),
    "ny": (42.0, -75.0),
    "ca": (37.0, -120.0),
    "fl": (28.0, -82.0),
    "nc": (35.5, -80.0),
    "va": (37.5, -78.5),
    "pa": (40.5, -77.5),
    "ga": (32.5, -83.5),
    "co": (39.0, -105.5),
    "wa": (47.5, -120.5)
}

def haversine(c1, c2):
    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return int(3958.8 * c) # Miles

def estimate_distance(loc_str):
    loc_clean = loc_str.lower().strip()
    if not loc_clean:
        return 9999, "National"
    if "remote" in loc_clean:
        return 0, "Remote (0 mi commute)"
    if "marshall" in loc_clean:
        return 0, "Marshall, MN (0 mi)"
    
    # Exact city match
    for city, coords in CITY_COORDS.items():
        if city in loc_clean:
            d = haversine(MARSHALL_COORDS, coords)
            return d, f"{loc_str} ({d} mi)"
            
    # State match fallback
    for st, coords in STATE_COORDS.items():
        pattern = r'\b' + st + r'\b'
        if re.search(pattern, loc_clean):
            d = haversine(MARSHALL_COORDS, coords)
            return d, f"{loc_str} (~{d} mi)"
            
    return 800, f"{loc_str} (~800 mi)"

def is_it_or_cyber_role(title, employer=""):
    t = (title + " " + employer).lower()
    keywords = [
        "cyber", "security", "infosec", "information security",
        "information technology", "it intern", "it support", "it operations",
        "systems", "system admin", "network", "infrastructure", "cloud",
        "technology intern", "software", "analyst", "developer", "data",
        "risk", "auditor", "technical", "engineering"
    ]
    return any(k in t for k in keywords)

async def harvest():
    ws_url = "ws://127.0.0.1:9222/devtools/page/6EE545EAFDE759FD7167405742351870"
    
    search_urls = [
        # Query 1: Summer 2027 IT
        "https://app.joinhandshake.com/job-search?query=summer+2027+IT&page=1&per_page=25",
        "https://app.joinhandshake.com/job-search?query=summer+2027+IT&page=2&per_page=25",
        # Query 2: Summer 2027 Cybersecurity
        "https://app.joinhandshake.com/job-search?query=summer+2027+cybersecurity&page=1&per_page=25",
        "https://app.joinhandshake.com/job-search?query=summer+2027+cybersecurity&page=2&per_page=25",
        # Query 3: Summer 2027 Information Technology
        "https://app.joinhandshake.com/job-search?query=summer+2027+information+technology&page=1&per_page=25",
        # Query 4: 2027 IT Intern
        "https://app.joinhandshake.com/job-search?query=2027+IT+intern&page=1&per_page=25",
        # Query 5: Summer 2027 (broad tech)
        "https://app.joinhandshake.com/job-search?query=summer+2027&page=1&per_page=25",
        "https://app.joinhandshake.com/job-search?query=summer+2027&page=2&per_page=25"
    ]

    all_harvested = {}

    print("=" * 70)
    print("📡 HARVESTING SUMMER 2027 IT & CYBERSECURITY ROLES VIA CDP")
    print("=" * 70)

    async with websockets.connect(ws_url) as ws:
        for s_url in search_urls:
            print(f"\n🔍 Searching: {s_url}")
            await ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": s_url}}))
            await ws.recv()
            await asyncio.sleep(3.5)

            # Dismiss popups
            await ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """(() => {
                        const dismissBtns = Array.from(document.querySelectorAll('button[class*="dismiss"], button')).filter(b => b.innerText.trim() === 'Cancel' || b.getAttribute('aria-label') === 'Close modal');
                        dismissBtns.forEach(b => b.click());
                    })()"""
                }
            }))
            await ws.recv()
            await asyncio.sleep(1)

            # Extract cards
            extract_msg = {
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """(() => {
                        const saveBtns = Array.from(document.querySelectorAll('button')).filter(b => b.getAttribute('aria-label') && b.getAttribute('aria-label').startsWith('Save '));
                        return saveBtns.map(btn => {
                            let p = btn.parentElement;
                            while (p && p.innerText.length < 50) {
                                p = p.parentElement;
                            }
                            const a = p ? p.querySelector('a[href*="/job-search/"], a[href*="/jobs/"]') : null;
                            const fullText = p ? p.innerText : '';
                            const lines = fullText.split('\\n').map(l => l.trim()).filter(Boolean);
                            const label = btn.getAttribute('aria-label').replace('Save ', '').trim();
                            
                            let jid = null;
                            if (a && a.href) {
                                const m = a.href.match(/\\/(jobs|job-search)\\/(\\d+)/);
                                if (m) jid = m[2];
                            }
                            
                            return {
                                id: jid,
                                title: label,
                                rawLines: lines,
                                text: fullText
                            };
                        });
                    })()""",
                    "returnByValue": True
                }
            }
            await ws.send(json.dumps(extract_msg))
            resp = json.loads(await ws.recv())
            cards = resp.get("result", {}).get("result", {}).get("value", [])
            print(f"  Found {len(cards)} cards on page.")

            for c in cards:
                jid = c.get("id")
                title = c.get("title", "")
                lines = c.get("rawLines", [])
                
                # Derive company and location
                company = lines[0] if len(lines) > 0 and lines[0] != title else (lines[1] if len(lines) > 1 else "Unknown")
                # Look for line with location (contains state abbreviation or comma or Remote)
                loc = "United States"
                for l in lines:
                    if "Remote" in l or ", MN" in l or ", IA" in l or ", IL" in l or ", NE" in l or ", SD" in l or ", WI" in l or re.search(r',\s*[A-Z]{2}', l):
                        loc = l
                        break

                if not jid:
                    continue
                if not is_it_or_cyber_role(title, company):
                    continue

                dist_miles, formatted_loc = estimate_distance(loc)
                
                # Assign tier based on distance
                if "marshall" in loc.lower() or dist_miles <= 50 and "remote" not in loc.lower():
                    tier = 1 # Local
                elif dist_miles <= 180 and "remote" not in loc.lower():
                    tier = 2 # Twin Cities & MN Metro
                elif "remote" in loc.lower():
                    tier = 3 # 100% Remote
                elif dist_miles <= 400:
                    tier = 4 # Regional Midwest
                else:
                    tier = 5 # National

                if jid not in all_harvested:
                    all_harvested[jid] = {
                        "id": jid,
                        "title": title,
                        "company": company,
                        "raw_location": loc,
                        "display_location": formatted_loc,
                        "distance_miles": dist_miles,
                        "tier": tier,
                        "url": f"https://app.joinhandshake.com/jobs/{jid}"
                    }
                    print(f"    + [{jid}] Tier {tier} ({dist_miles} mi) | {company} — {title} ({loc})")

    # Sort strictly: Tier first, then distance_miles ascending
    sorted_jobs = sorted(all_harvested.values(), key=lambda x: (x["tier"], x["distance_miles"], x["company"]))
    
    print("\n" + "=" * 70)
    print(f"🎯 HARVEST COMPLETE: {len(sorted_jobs)} QUALIFIED SUMMER 2027 ROLES")
    print("=" * 70)

    for i, j in enumerate(sorted_jobs, 1):
        print(f"#{i:02d} [Tier {j['tier']} | {j['distance_miles']:>4} mi] {j['company']:<25} | {j['title'][:45]:<45} | {j['raw_location']}")

    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    with open(QUEUE_PATH, "w") as f:
        json.dump(sorted_jobs, f, indent=2)
    print(f"\n💾 Saved ranked queue to: {QUEUE_PATH}")

if __name__ == "__main__":
    asyncio.run(harvest())
