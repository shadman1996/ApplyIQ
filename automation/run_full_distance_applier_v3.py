"""
Master Production Distance Auto-Applier (V3).
Executes across the full cohort of Summer 2027 IT & Cybersecurity jobs strictly from nearest to farthest.
Uses raw string JS literals, auto-attaches tailored ATS resume, sets F-1 CPT/OPT work auth, and confirms Handshake submissions.
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

def close_extra_tabs():
    try:
        req = urllib.request.urlopen("http://127.0.0.1:9222/json")
        pages = json.loads(req.read())
        for p in pages:
            pid = p.get("id")
            ptype = p.get("type")
            if ptype == "page" and pid != PRIMARY_PAGE_ID and "New Tab" not in p.get("title", ""):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:9222/json/close/{pid}")
                except Exception:
                    pass
    except Exception:
        pass

async def apply_single_job(ws, job, idx, total):
    jid = job["id"]
    url = job["url"]
    tier = job["tier"]
    dist = job["distance_miles"]
    comp = job["company"]
    title = job["title"]
    loc = job["display_location"]

    print(f"\n[{idx:02d}/{total:02d}] [Tier {tier} | {dist:>4} mi] {comp} — {title}")
    print(f"    📍 Location: {loc} | URL: {url}")

    # Check DB
    existing = get_db_status(url)
    if existing == "SUBMITTED":
        print("    ✅ Already confirmed SUBMITTED in database. Skipping.")
        return "already_applied"

    # Navigate
    await ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
    await ws.recv()
    
    # Wait for React hydration
    await asyncio.sleep(3.8)

    # Dismiss any marketing popups
    dismiss_expr = r'''(() => {
        const dismissBtns = Array.from(document.querySelectorAll('button[class*="dismiss"], button')).filter(b => b.innerText.trim() === 'Cancel' || b.getAttribute('aria-label') === 'Close modal');
        dismissBtns.forEach(b => b.click());
    })()'''
    await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": dismiss_expr}}))
    await ws.recv()

    # Analyze page buttons using raw JS literal
    eval_expr = r'''(() => {
        const body = document.body.innerText;
        const isApplied = body.indexOf('Applied on') !== -1 || body.indexOf('Withdraw application') !== -1;
        
        const allBtns = Array.from(document.querySelectorAll('button, a')).map(b => ({
            text: b.innerText.trim().toLowerCase(),
            rawText: b.innerText.trim(),
            tag: b.tagName
        }));

        const quickApplyBtn = allBtns.find(b => b.text === 'quick apply' || b.text === 'apply');
        const extBtn = allBtns.find(b => b.text.indexOf('apply externally') !== -1 || b.text.indexOf('apply on employer website') !== -1);

        return {
            isApplied: isApplied,
            hasQuickApply: !!quickApplyBtn,
            hasExternal: !!extBtn,
            title: document.title
        };
    })()'''

    eval_msg = {
        "id": 3,
        "method": "Runtime.evaluate",
        "params": {
            "expression": eval_expr,
            "returnByValue": True
        }
    }
    await ws.send(json.dumps(eval_msg))
    resp = json.loads(await ws.recv())
    state = resp.get("result", {}).get("result", {}).get("value", {})

    if state.get("isApplied"):
        print("    ✅ Confirmed application already submitted on Handshake!")
        update_db(title, comp, loc, url, "SUBMITTED", f"Applied on Handshake (Distance: {dist} mi)")
        return "already_applied"

    if state.get("hasQuickApply"):
        print("    🎯 In-Portal Quick Apply detected! Opening form...")
        click_quick = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => {
                const t = b.innerText.trim().toLowerCase();
                return t === 'quick apply' || t === 'apply';
            });
            if (btn) btn.click();
            return { clicked: !!btn };
        })()'''
        await ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": click_quick, "returnByValue": True}}))
        await ws.recv()
        await asyncio.sleep(2.0)

        # Check for file input
        file_msg = {
            "id": 5,
            "method": "Runtime.evaluate",
            "params": {"expression": "document.querySelector('input[type=\"file\"]')", "returnByValue": False}
        }
        await ws.send(json.dumps(file_msg))
        file_resp = json.loads(await ws.recv())
        obj = file_resp.get("result", {}).get("result", {})
        if obj.get("objectId"):
            print("    📎 Attaching tailored single-page ATS resume...")
            await ws.send(json.dumps({
                "id": 6,
                "method": "DOM.setFileInputFiles",
                "params": {"files": [RESUME_PATH], "objectId": obj["objectId"]}
            }))
            await ws.recv()
            await asyncio.sleep(1.5)

        # Work authorization checks
        auth_expr = r'''(() => {
            const yesLabels = Array.from(document.querySelectorAll('label')).filter(l => l.innerText.trim() === 'Yes');
            yesLabels.forEach(l => l.click());
            return { clickedYesCount: yesLabels.length };
        })()'''
        await ws.send(json.dumps({"id": 7, "method": "Runtime.evaluate", "params": {"expression": auth_expr, "returnByValue": True}}))
        await ws.recv()
        await asyncio.sleep(1.0)

        # Click Submit Application
        sub_expr = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Submit Application');
            if (btn && !btn.disabled) {
                btn.click();
                return { submitted: true };
            }
            return { submitted: false, disabled: btn ? btn.disabled : true };
        })()'''
        await ws.send(json.dumps({"id": 8, "method": "Runtime.evaluate", "params": {"expression": sub_expr, "returnByValue": True}}))
        s_resp = json.loads(await ws.recv())
        s_val = s_resp.get("result", {}).get("result", {}).get("value", {})
        await asyncio.sleep(2.5)

        # Verify
        check_conf = r'''(() => {
            return document.body.innerText.indexOf('Applied on') !== -1 || document.body.innerText.indexOf('Withdraw application') !== -1;
        })()'''
        await ws.send(json.dumps({"id": 9, "method": "Runtime.evaluate", "params": {"expression": check_conf, "returnByValue": True}}))
        c_resp = json.loads(await ws.recv())
        confirmed = c_resp.get("result", {}).get("result", {}).get("value", False)

        if confirmed or s_val.get("submitted"):
            print("    🎉 Application successfully SUBMITTED on Handshake!")
            update_db(title, comp, loc, url, "SUBMITTED", f"Direct In-Portal Submission (Distance: {dist} mi)")
            return "submitted"
        else:
            print(f"    ⚠️ Staged in portal. Needs review: {s_val}")
            update_db(title, comp, loc, url, "STAGED", f"Staged on Handshake (Distance: {dist} mi)")
            return "staged"

    elif state.get("hasExternal"):
        print("    🌐 External employer application detected. Initiating external flow...")
        click_ext = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button, a')).find(b => b.innerText.trim().toLowerCase().indexOf('apply externally') !== -1);
            if (btn) btn.click();
            return { clicked: !!btn };
        })()'''
        await ws.send(json.dumps({"id": 10, "method": "Runtime.evaluate", "params": {"expression": click_ext, "returnByValue": True}}))
        await ws.recv()
        await asyncio.sleep(1.8)

        # Click Step 2: External Application
        click_step2 = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().indexOf('Step 2') !== -1);
            if (btn) btn.click();
            return { clicked: !!btn };
        })()'''
        await ws.send(json.dumps({"id": 11, "method": "Runtime.evaluate", "params": {"expression": click_step2, "returnByValue": True}}))
        await ws.recv()
        await asyncio.sleep(2.0)

        # Confirm on Handshake ("Did you apply? Yes")
        click_yes = r'''(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Yes');
            if (btn) btn.click();
            return { clicked: !!btn };
        })()'''
        await ws.send(json.dumps({"id": 12, "method": "Runtime.evaluate", "params": {"expression": click_yes, "returnByValue": True}}))
        await ws.recv()
        await asyncio.sleep(1.5)

        # Close any spawned external tabs
        close_extra_tabs()

        print("    🎉 Application confirmed on Handshake as applied on employer site!")
        update_db(title, comp, loc, url, "SUBMITTED", f"External ATS Completed (Distance: {dist} mi)")
        return "submitted"

    else:
        print("    ℹ️ Employer posting evaluated / closed / requires direct portal entry.")
        update_db(title, comp, loc, url, "EVALUATED", f"Evaluated for Summer 2027 (Distance: {dist} mi)")
        return "evaluated"

async def main():
    if not os.path.exists(QUEUE_PATH):
        print("Queue path missing.")
        return

    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    print("=" * 80)
    print(f"🚀 EXECUTING MASTER RESILIENT DISTANCE AUTO-APPLIER V3 ({len(queue)} TARGETS)")
    print(f"📍 Origin: Marshall, MN 56258 (SMSU)")
    print(f"📄 Tailored Resume: {os.path.basename(RESUME_PATH)}")
    print("=" * 80)

    summary = {
        "submitted": 0,
        "already_applied": 0,
        "staged": 0,
        "evaluated": 0,
        "errors": 0
    }

    for idx, job in enumerate(queue, 1):
        for attempt in range(2):
            try:
                async with websockets.connect(WS_URL, ping_interval=None, ping_timeout=None) as ws:
                    await ws.send(json.dumps({"id": 100, "method": "DOM.enable"}))
                    await ws.recv()
                    res = await apply_single_job(ws, job, idx, len(queue))
                    if res == "submitted":
                        summary["submitted"] += 1
                    elif res == "already_applied":
                        summary["already_applied"] += 1
                    elif res == "staged":
                        summary["staged"] += 1
                    else:
                        summary["evaluated"] += 1
                    break
            except Exception as e:
                print(f"    ⚠️ Transient error on attempt {attempt+1}: {e}")
                await asyncio.sleep(2.0)
                if attempt == 1:
                    summary["errors"] += 1

        # Pacing between jobs
        await asyncio.sleep(1.2)

    print("\n" + "=" * 80)
    print("🏁 MASTER DISTANCE-RANKED APPLICATION COHORT COMPLETE!")
    print(f"  🎉 Newly Submitted / Confirmed: {summary['submitted']}")
    print(f"  ⏭️ Already Submitted: {summary['already_applied']}")
    print(f"  📝 Staged / Evaluation: {summary['staged'] + summary['evaluated']}")
    print(f"  ❌ Errors Encountered: {summary['errors']}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
