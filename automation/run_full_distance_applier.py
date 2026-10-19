"""
Full Automated Distance-Ranked Summer 2027 IT & Cybersecurity Job Applier.
Executes strictly from nearest to Marshall, MN 56258 outwards to nationwide.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
import websockets

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
QUEUE_PATH = os.path.join(PROJECT_ROOT, "data", "summer_2027_ranked_queue.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "applications.db")
RESUME_PATH = os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf")
WS_URL = "ws://127.0.0.1:9222/devtools/page/6EE545EAFDE759FD7167405742351870"

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

async def run_applier():
    if not os.path.exists(QUEUE_PATH):
        print(f"Error: Queue file {QUEUE_PATH} not found.")
        return

    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    print("=" * 80)
    print(f"🚀 EXECUTING DISTANCE-RANKED AUTO-APPLIER ({len(queue)} SUMMER 2027 OPPORTUNITIES)")
    print(f"📍 Origin: Marshall, MN 56258 (SMSU)")
    print(f"📄 Master Tailored Resume: {os.path.basename(RESUME_PATH)}")
    print("=" * 80)

    stats = {
        "submitted": 0,
        "external_queued": 0,
        "already_applied": 0,
        "review_needed": 0
    }

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"id": 100, "method": "DOM.enable"}))
        await ws.recv()

        for idx, job in enumerate(queue, 1):
            jid = job["id"]
            url = job["url"]
            tier = job["tier"]
            dist = job["distance_miles"]
            comp = job["company"]
            title = job["title"]
            loc = job["display_location"]

            print(f"\n[{idx:02d}/{len(queue):02d}] [Tier {tier} | {dist:>4} mi] {comp} — {title}")
            print(f"    📍 Location: {loc} | URL: {url}")

            # Pre-check database
            existing_status = get_db_status(url)
            if existing_status == "SUBMITTED":
                print("    ✅ Already marked SUBMITTED in database. Skipping.")
                stats["already_applied"] += 1
                continue

            # Navigate to job
            await ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
            await ws.recv()
            await asyncio.sleep(2.8)

            # Dismiss background modals
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

            # Analyze page state
            eval_msg = {
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """(() => {
                        const body = document.body.innerText;
                        const isApplied = body.includes('Applied on') || body.includes('Withdraw application');
                        
                        const allBtns = Array.from(document.querySelectorAll('button, a')).map(b => ({
                            text: b.innerText.trim().toLowerCase(),
                            rawText: b.innerText.trim(),
                            href: b.getAttribute('href'),
                            tag: b.tagName
                        }));

                        const quickApplyBtn = allBtns.find(b => b.text === 'quick apply' || b.text === 'apply');
                        const extBtn = allBtns.find(b => b.text.includes('apply externally') || b.text.includes('apply on employer website'));

                        return {
                            isApplied,
                            hasQuickApply: !!quickApplyBtn,
                            hasExternal: !!extBtn,
                            extHref: extBtn ? extBtn.href : null
                        };
                    })()""",
                    "returnByValue": True
                }
            }
            await ws.send(json.dumps(eval_msg))
            resp = json.loads(await ws.recv())
            state = resp.get("result", {}).get("result", {}).get("value", {})

            if state.get("isApplied"):
                print("    ✅ Confirmed application already submitted on Handshake!")
                update_db(title, comp, loc, url, "SUBMITTED", f"Applied on Handshake (Distance: {dist} mi)")
                stats["already_applied"] += 1
                continue

            if state.get("hasQuickApply"):
                print("    🎯 Handshake in-portal Quick Apply detected! Opening application form...")
                click_quick = {
                    "id": 4,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """(() => {
                            const btn = Array.from(document.querySelectorAll('button')).find(b => {
                                const t = b.innerText.trim().toLowerCase();
                                return t === 'quick apply' || t === 'apply';
                            });
                            if (btn) btn.click();
                            return { clicked: !!btn };
                        })()""",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(click_quick))
                await ws.recv()
                await asyncio.sleep(2.0)

                # Check if file upload is requested
                eval_file = {
                    "id": 5,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "document.querySelector('input[type=\"file\"]')",
                        "returnByValue": False
                    }
                }
                await ws.send(json.dumps(eval_file))
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

                # Auto-check work authorization questions if present
                auth_fill = {
                    "id": 7,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """(() => {
                            const labels = Array.from(document.querySelectorAll('label')).filter(l => l.innerText.trim() === 'Yes');
                            labels.forEach(l => l.click());
                            return { clickedYesCount: labels.length };
                        })()""",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(auth_fill))
                await ws.recv()
                await asyncio.sleep(1.0)

                # Click Submit Application
                submit_eval = {
                    "id": 8,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """(() => {
                            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Submit Application');
                            if (btn && !btn.disabled) {
                                btn.click();
                                return { submitted: true };
                            }
                            return { submitted: false, disabled: btn ? btn.disabled : true, exists: !!btn };
                        })()""",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(submit_eval))
                sub_resp = json.loads(await ws.recv())
                sub_res = sub_resp.get("result", {}).get("result", {}).get("value", {})

                await asyncio.sleep(2.5)

                # Verify submission on page
                verify_eval = {
                    "id": 9,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "document.body.innerText.includes('Applied on') || document.body.innerText.includes('Withdraw application')",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(verify_eval))
                v_resp = json.loads(await ws.recv())
                is_confirmed = v_resp.get("result", {}).get("result", {}).get("value", False)

                if is_confirmed or sub_res.get("submitted"):
                    print("    🎉 Application successfully SUBMITTED on Handshake!")
                    update_db(title, comp, loc, url, "SUBMITTED", f"Direct Handshake Submission (Distance: {dist} mi)")
                    stats["submitted"] += 1
                else:
                    print(f"    ⚠️ Staged in portal. Needs brief manual input: {sub_res}")
                    update_db(title, comp, loc, url, "STAGED", f"Staged on Handshake (Distance: {dist} mi)")
                    stats["review_needed"] += 1

            elif state.get("hasExternal"):
                ext_link = state.get("extHref") or url
                print(f"    🌐 External Enterprise ATS application: {ext_link[:75]}...")
                update_db(title, comp, loc, url, "APPROVED", f"External ATS Queued (Distance: {dist} mi)", ext_url=ext_link)
                stats["external_queued"] += 1

            else:
                print("    ℹ️ Detail view or employer review required.")
                update_db(title, comp, loc, url, "EVALUATED", f"Evaluated for Summer 2027 (Distance: {dist} mi)")
                stats["review_needed"] += 1

    print("\n" + "=" * 80)
    print("🏁 DISTANCE-RANKED SUMMER 2027 APPLICATION RUN FINISHED!")
    print(f"  ✅ In-Portal Applications Submitted: {stats['submitted']}")
    print(f"  🌐 External ATS Opportunities Queued: {stats['external_queued']}")
    print(f"  ⏭️ Already Applied / Confirmed: {stats['already_applied']}")
    print(f"  📝 Under Staging / Review: {stats['review_needed']}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_applier())
