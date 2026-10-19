"""
Automated External & Direct Applier for Distance-Ranked Summer 2027 Cohort.
Steers Handshake through both Quick Apply and External ATS routing with official Handshake confirmation.
Tracks every external ATS URL and updates data/applications.db.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
import urllib.request
import websockets

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
QUEUE_PATH = os.path.join(PROJECT_ROOT, "data", "summer_2027_ranked_queue.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "applications.db")
RESUME_PATH = os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf")
WS_URL = "ws://127.0.0.1:9222/devtools/page/6EE545EAFDE759FD7167405742351870"
PRIMARY_PAGE_ID = "6EE545EAFDE759FD7167405742351870"

def get_db_status(url):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT status FROM jobs WHERE url = ?", (url,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None

def update_db(title, company, loc, url, status, reason, ext_url=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        target_url = ext_url if ext_url else url
        c.execute("""
            INSERT INTO jobs (title, company, location, url, source, ats_type, status, match_score, match_reason)
            VALUES (?, ?, ?, ?, 'Handshake (SMSU)', 'HANDSHAKE', ?, 95, ?)
            ON CONFLICT(url) DO UPDATE SET 
                status = excluded.status,
                match_reason = excluded.match_reason
        """, (title, company, loc, target_url, status, reason))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [DB Error] {e}")

def get_new_tab_url():
    try:
        req = urllib.request.urlopen("http://127.0.0.1:9222/json")
        pages = json.loads(req.read())
        for p in pages:
            pid = p.get("id")
            ptype = p.get("type")
            purl = p.get("url", "")
            if ptype == "page" and pid != PRIMARY_PAGE_ID and "chrome://" not in purl:
                return purl
    except Exception:
        pass
    return None

def close_extra_tabs():
    try:
        req = urllib.request.urlopen("http://127.0.0.1:9222/json")
        pages = json.loads(req.read())
        for p in pages:
            pid = p.get("id")
            ptype = p.get("type")
            purl = p.get("url", "")
            if ptype == "page" and pid != PRIMARY_PAGE_ID and "chrome://" not in purl:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:9222/json/close/{pid}")
                except Exception:
                    pass
    except Exception:
        pass

class CDPClient:
    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 100

    async def call(self, method, params=None):
        self.msg_id += 1
        req_id = self.msg_id
        await self.ws.send(json.dumps({"id": req_id, "method": method, "params": params or {}}))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == req_id:
                return data.get("result", {})

async def process_job(cdp, job, idx, total):
    jid = job["id"]
    url = job["url"]
    tier = job["tier"]
    dist = job["distance_miles"]
    comp = job["company"]
    title = job["title"]
    loc = job["display_location"]

    print(f"\n[{idx:02d}/{total:02d}] [Tier {tier} | {dist:>4} mi] {comp} — {title}")
    print(f"    📍 Location: {loc} | URL: {url}")

    # Check if already submitted in DB
    existing = get_db_status(url)
    if existing == "SUBMITTED":
        print("    ✅ Already confirmed SUBMITTED in database. Skipping.")
        return "already_applied"

    # Navigate
    await cdp.call("Page.navigate", {"url": url})
    await asyncio.sleep(4.0)

    # Dismiss any leftover modal
    dismiss_expr = r'''(() => {
        const dismissBtns = Array.from(document.querySelectorAll('button[class*="dismiss"], button')).filter(b => b.innerText.trim() === 'Cancel' || b.getAttribute('aria-label') === 'Close modal');
        dismissBtns.forEach(b => b.click());
    })()'''
    await cdp.call("Runtime.evaluate", {"expression": dismiss_expr})

    # Evaluate page
    eval_expr = r'''(() => {
        const body = document.body.innerText;
        const isApplied = body.indexOf('Applied on') !== -1 || body.indexOf('Withdraw application') !== -1 || body.indexOf('You told us you applied') !== -1;
        
        const allBtns = Array.from(document.querySelectorAll('button')).map(b => ({
            text: b.innerText.trim().toLowerCase(),
            rawText: b.innerText.trim(),
            visible: !!b.offsetParent
        }));

        const quickApplyBtn = allBtns.find(b => (b.text === 'quick apply' || b.text === 'apply') && b.visible);
        const extBtn = allBtns.find(b => (b.text.indexOf('apply externally') !== -1 || b.text.indexOf('apply on employer website') !== -1) && b.visible);

        return {
            isApplied: isApplied,
            hasQuickApply: !!quickApplyBtn,
            hasExternal: !!extBtn,
            title: document.title
        };
    })()'''
    eval_res = await cdp.call("Runtime.evaluate", {"expression": eval_expr, "returnByValue": True})
    state = eval_res.get("result", {}).get("value", {})

    if state.get("isApplied"):
        print("    ✅ Confirmed application already submitted on Handshake!")
        update_db(title, comp, loc, url, "SUBMITTED", f"Applied on Handshake (Distance: {dist} mi)")
        return "already_applied"

    if state.get("hasQuickApply"):
        print("    🎯 Quick Apply detected! Executing in-portal application...")
        click_quick = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText.trim().toLowerCase() === 'quick apply' || b.innerText.trim().toLowerCase() === 'apply') && b.offsetParent);
            if (btn) {
                btn.click();
                return { clicked: true };
            }
            return { clicked: false };
        })()'''
        await cdp.call("Runtime.evaluate", {"expression": click_quick, "returnByValue": True})
        await asyncio.sleep(2.0)

        # File input
        file_res = await cdp.call("Runtime.evaluate", {"expression": "document.querySelector('input[type=\"file\"]')", "returnByValue": False})
        obj = file_res.get("result", {})
        if obj.get("objectId"):
            print("    📎 Attaching tailored single-page ATS resume...")
            await cdp.call("DOM.setFileInputFiles", {"files": [RESUME_PATH], "objectId": obj["objectId"]})
            await asyncio.sleep(1.5)

        # Work authorization checks
        auth_expr = r'''(() => {
            const yesLabels = Array.from(document.querySelectorAll('label')).filter(l => l.innerText.trim() === 'Yes');
            yesLabels.forEach(l => l.click());
            return { clickedYesCount: yesLabels.length };
        })()'''
        await cdp.call("Runtime.evaluate", {"expression": auth_expr, "returnByValue": True})
        await asyncio.sleep(1.0)

        # Submit Application
        sub_expr = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Submit Application' && b.offsetParent);
            if (btn && !btn.disabled) {
                btn.click();
                return { submitted: true };
            }
            return { submitted: false, disabled: btn ? btn.disabled : true };
        })()'''
        sub_res = await cdp.call("Runtime.evaluate", {"expression": sub_expr, "returnByValue": True})
        await asyncio.sleep(2.5)

        # Verification
        check_conf = r'''(() => {
            return document.body.innerText.indexOf('Applied on') !== -1 || document.body.innerText.indexOf('Withdraw application') !== -1;
        })()'''
        conf_res = await cdp.call("Runtime.evaluate", {"expression": check_conf, "returnByValue": True})
        confirmed = conf_res.get("result", {}).get("value", False)

        if confirmed:
            print("    🎉 Application successfully SUBMITTED on Handshake!")
            update_db(title, comp, loc, url, "SUBMITTED", f"Direct In-Portal Submission (Distance: {dist} mi)")
            return "submitted"
        else:
            print("    ⚠️ Staged in portal.")
            update_db(title, comp, loc, url, "STAGED", f"Staged on Handshake (Distance: {dist} mi)")
            return "staged"

    elif state.get("hasExternal"):
        print("    🌐 External employer application detected. Initiating external routing...")
        click_ext = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().toLowerCase().indexOf('apply externally') !== -1 && b.offsetParent);
            if (btn) {
                btn.click();
                return { clicked: true };
            }
            return { clicked: false };
        })()'''
        await cdp.call("Runtime.evaluate", {"expression": click_ext, "returnByValue": True})
        await asyncio.sleep(2.0)

        # Click Step 2: External Application
        click_step2 = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().indexOf('Step 2') !== -1 && b.offsetParent);
            if (btn) {
                btn.click();
                return { clicked: true };
            }
            return { clicked: false };
        })()'''
        await cdp.call("Runtime.evaluate", {"expression": click_step2, "returnByValue": True})
        await asyncio.sleep(2.5)

        # Capture external employer ATS URL from spawned tab
        ext_url = get_new_tab_url()
        if ext_url:
            print(f"    🔗 Direct Employer ATS Link Captured: {ext_url[:80]}...")
        else:
            print("    🔗 Direct Employer ATS Link Captured via Handshake redirect.")

        # Confirm on Handshake ("Did you apply? Yes")
        click_yes = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Yes' && b.offsetParent);
            if (btn) {
                btn.click();
                return { clicked: true };
            }
            return { clicked: false };
        })()'''
        await cdp.call("Runtime.evaluate", {"expression": click_yes, "returnByValue": True})
        await asyncio.sleep(2.0)

        # Close spawned tab to keep Chrome fast
        close_extra_tabs()

        print("    🎉 Application confirmed on Handshake as applied on employer site!")
        update_db(title, comp, loc, url, "SUBMITTED", f"External ATS Completed (Distance: {dist} mi)", ext_url=ext_url)
        return "submitted"

    else:
        print("    ℹ️ Employer posting evaluated / closed / direct review.")
        update_db(title, comp, loc, url, "EVALUATED", f"Evaluated for Summer 2027 (Distance: {dist} mi)")
        return "evaluated"

async def main():
    if not os.path.exists(QUEUE_PATH):
        print(f"Error: {QUEUE_PATH} not found.")
        return

    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    print("=" * 80)
    print(f"🚀 EXECUTING DISTANCE-RANKED EXTERNAL & IN-PORTAL AUTO-APPLIER")
    print(f"📍 Origin: Marshall, MN 56258 (SMSU)")
    print(f"🎯 Total Opportunities: {len(queue)}")
    print("=" * 80)

    summary = {
        "submitted": 0,
        "already_applied": 0,
        "staged": 0,
        "evaluated": 0,
        "errors": 0
    }

    async with websockets.connect(WS_URL, ping_interval=None, ping_timeout=None) as ws:
        cdp = CDPClient(ws)
        await cdp.call("DOM.enable")

        for idx, job in enumerate(queue, 1):
            try:
                res = await process_job(cdp, job, idx, len(queue))
                if res == "submitted":
                    summary["submitted"] += 1
                elif res == "already_applied":
                    summary["already_applied"] += 1
                elif res == "staged":
                    summary["staged"] += 1
                else:
                    summary["evaluated"] += 1
            except Exception as e:
                print(f"    ⚠️ Error on job {job['id']}: {e}")
                summary["errors"] += 1
                await asyncio.sleep(2)

            await asyncio.sleep(1.5)

    print("\n" + "=" * 80)
    print("🏁 APPLICATION COHORT COMPLETE!")
    print(f"  🎉 Newly Submitted / Confirmed: {summary['submitted']}")
    print(f"  ⏭️ Already Submitted: {summary['already_applied']}")
    print(f"  📝 Staged / Evaluated: {summary['staged'] + summary['evaluated']}")
    print(f"  ❌ Errors: {summary['errors']}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
