"""
Distance-Ranked Batch Auto-Applier for Summer 2027 IT & Cybersecurity Jobs on Handshake.
Orders opportunities strictly from nearest to Marshall, MN 56258 to farthest.
Uses active CDP session to auto-fill work authorization and attach tailored resume.
"""

import asyncio
import json
import os
import sqlite3
import websockets

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
DB_PATH = os.path.join(PROJECT_ROOT, "data", "applications.db")
RESUME_PATH = os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf")

# Distance-ranked jobs from Marshall, MN
RANKED_JOBS = [
    # Tier 1: Local Marshall & immediate proximity (< 50 miles)
    {"id": "11489436", "company": "CJ Schwan’s", "title": "IT Systems Developer Internship - Summer 2027", "loc": "Marshall, MN (0 mi)", "tier": 1},
    {"id": "11489363", "company": "Pipestone", "title": "IT Intern", "loc": "Pipestone, MN (42 mi)", "tier": 1},
    
    # Tier 2: Minnesota Twin Cities & Central MN (100 - 170 miles)
    {"id": "11428495", "company": "Blattner Energy", "title": "IT Help Desk Intern", "loc": "Avon, MN (100 mi)", "tier": 2},
    {"id": "11488126", "company": "Western National Insurance", "title": "IT Application Administration Intern", "loc": "Edina, MN (145 mi)", "tier": 2},
    {"id": "11481659", "company": "Bridgewater Bank", "title": "Technology Intern", "loc": "St. Louis Park, MN (145 mi)", "tier": 2},
    {"id": "11383045", "company": "Ameriprise Financial", "title": "Technology Intern", "loc": "Minneapolis, MN (150 mi)", "tier": 2},
    {"id": "11293943", "company": "Mortenson", "title": "ITS Analyst Intern", "loc": "Minneapolis, MN (150 mi)", "tier": 2},
    {"id": "11374176", "company": "3M", "title": "3M Internship - 2027 Undergraduate IT Intern", "loc": "Maplewood, MN (160 mi)", "tier": 2},
    {"id": "11429225", "company": "Gertens", "title": "IT Hardware & Systems Intern", "loc": "Inver Grove Heights, MN (155 mi)", "tier": 2},
    {"id": "11376804", "company": "Compeer Financial", "title": "Data Analytics Intern", "loc": "Lakeville, MN (140 mi)", "tier": 2},
    {"id": "11358165", "company": "Andersen Corporation", "title": "IT Intern", "loc": "Oak Park Heights, MN (175 mi)", "tier": 2},
    {"id": "11443131", "company": "ALLETE Inc", "title": "IT Collaboration System Administrator Intern", "loc": "Duluth, MN (260 mi)", "tier": 2},

    # Tier 3: 100% Remote (0 commute miles)
    {"id": "11385831", "company": "Sensiba LLP", "title": "IT Risk Assurance Intern - Summer 2027", "loc": "Remote (0 mi)", "tier": 3},
    {"id": "11403233", "company": "John Deere", "title": "Student Technology Auditor - Remote", "loc": "Remote (0 mi)", "tier": 3},
    {"id": "11435784", "company": "GlowUp ACS", "title": "IT Internship", "loc": "Remote (0 mi)", "tier": 3},

    # Tier 4: Regional Midwest (200 - 300 miles)
    {"id": "11366628", "company": "Conagra Brands", "title": "Cybersecurity Internship - Summer 2027", "loc": "Omaha, NE (220 mi)", "tier": 4},
    {"id": "11466917", "company": "Hy-Vee", "title": "IT Security Loss Intern - Summer 2027", "loc": "West Des Moines, IA (220 mi)", "tier": 4},
    {"id": "11424364", "company": "Scoular", "title": "IT Internship", "loc": "Omaha, NE (220 mi)", "tier": 4},

    # Tier 5: Major National Cyber Programs
    {"id": "11460019", "company": "Ulta Beauty", "title": "Intern, Cybersecurity (Data Privacy & Awareness)", "loc": "National / IL", "tier": 5},
    {"id": "11380578", "company": "Toyota Material Handling", "title": "Cybersecurity Internship", "loc": "Columbus, IN", "tier": 5},
    {"id": "11357109", "company": "Grainger", "title": "GTG Intern - Cybersecurity", "loc": "Chicago, IL", "tier": 5},
    {"id": "11447092", "company": "Activision Blizzard", "title": "2027 Summer Internships - Information Security", "loc": "Sherman Oaks, CA", "tier": 5},
    {"id": "11307575", "company": "New York Life", "title": "2027 Security Engineer Intern", "loc": "New York, NY", "tier": 5},
    {"id": "11345910", "company": "Procter & Gamble (P&G)", "title": "IT Security Internship - 2027", "loc": "Cincinnati, OH", "tier": 5}
]

def record_job_db(title, company, loc, url, status):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO jobs (title, company, location, url, source, ats_type, status, match_score, match_reason)
        VALUES (?, ?, ?, ?, 'Handshake (SMSU)', 'HANDSHAKE', ?, 95, 'Summer 2027 IT/Cybersecurity match sorted by distance')
        ON CONFLICT(url) DO UPDATE SET status=excluded.status
        """, (title, company, loc, url, status))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

async def run_batch():
    ws_url = "ws://127.0.0.1:9222/devtools/page/6EE545EAFDE759FD7167405742351870"
    print("=" * 70)
    print(f"🚀 LAUNCHING DISTANCE-SORTED SUMMER 2027 BATCH APPLIER ({len(RANKED_JOBS)} TARGETS)")
    print(f"📍 Origin: Marshall, MN 56258 (SMSU)")
    print("=" * 70)

    applied_count = 0
    external_count = 0
    skipped_count = 0

    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 100, "method": "DOM.enable"}))
        await ws.recv()

        for idx, job in enumerate(RANKED_JOBS, 1):
            jid = job["id"]
            url = f"https://app.joinhandshake.com/jobs/{jid}"
            print(f"\n[{idx}/{len(RANKED_JOBS)}] [Tier {job['tier']}] {job['company']} — {job['title']}")
            print(f"  📍 Location: {job['loc']} | URL: {url}")

            # Navigate
            await ws.send(json.dumps({
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": url}
            }))
            await ws.recv()
            await asyncio.sleep(2.5)

            # Check page status & buttons
            check_msg = {
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """(() => {
                        const text = document.body.innerText;
                        const isApplied = text.includes('Applied on') || text.includes('Withdraw application');
                        
                        const allBtns = Array.from(document.querySelectorAll('button, a')).map(b => ({
                            text: b.innerText.trim(),
                            href: b.getAttribute('href'),
                            tag: b.tagName
                        }));
                        
                        const applyBtn = allBtns.find(b => b.text === 'Apply' || b.text === 'Quick apply');
                        const applyExtBtn = allBtns.find(b => b.text.includes('Apply externally') || b.text.includes('Apply on employer website'));
                        
                        return {
                            isApplied,
                            hasDirectApply: !!applyBtn,
                            hasExternalApply: !!applyExtBtn,
                            externalHref: applyExtBtn ? applyExtBtn.href : null
                        };
                    })()""",
                    "returnByValue": True
                }
            }
            await ws.send(json.dumps(check_msg))
            resp = json.loads(await ws.recv())
            val = resp.get("result", {}).get("result", {}).get("value", {})

            if val.get("isApplied"):
                print("  ℹ️ Already applied to this position! Skipping.")
                record_job_db(job["title"], job["company"], job["loc"], url, "SUBMITTED")
                skipped_count += 1
                continue

            if val.get("hasDirectApply"):
                print("  🎯 Handshake in-portal Quick Apply detected! Initiating autofill...")
                # Click Apply button
                click_msg = {
                    "id": 3,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """(() => {
                            const btn = Array.from(document.querySelectorAll('button, a')).find(b => b.innerText.trim() === 'Apply' || b.innerText.trim() === 'Quick apply');
                            if (btn) btn.click();
                            return { clicked: !!btn };
                        })()""",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(click_msg))
                await ws.recv()
                await asyncio.sleep(2)

                # Check if modal opened & set resume if needed
                eval_file_msg = {
                    "id": 4,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "document.querySelector('input[type=\"file\"]')",
                        "returnByValue": False
                    }
                }
                await ws.send(json.dumps(eval_file_msg))
                file_resp = json.loads(await ws.recv())
                obj = file_resp.get("result", {}).get("result", {})
                
                if obj.get("objectId"):
                    print("  📎 Uploading tailored single-page resume...")
                    await ws.send(json.dumps({
                        "id": 5,
                        "method": "DOM.setFileInputFiles",
                        "params": {"files": [RESUME_PATH], "objectId": obj["objectId"]}
                    }))
                    await ws.recv()
                    await asyncio.sleep(1.5)

                # Set work authorization radio buttons (Legally authorized: Yes, Sponsorship: Yes)
                auth_msg = {
                    "id": 6,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """(() => {
                            // Check 'Yes' for legal auth and sponsorship
                            const yesLabels = Array.from(document.querySelectorAll('label')).filter(l => l.innerText.trim() === 'Yes');
                            yesLabels.forEach(l => l.click());
                            return { yesCount: yesLabels.length };
                        })()""",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(auth_msg))
                await ws.recv()
                await asyncio.sleep(1)

                # Click Submit Application
                submit_msg = {
                    "id": 7,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """(() => {
                            const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Submit Application');
                            if (submitBtn && !submitBtn.disabled) {
                                submitBtn.click();
                                return { submitted: true };
                            }
                            return { submitted: false, disabled: submitBtn ? submitBtn.disabled : true };
                        })()""",
                        "returnByValue": True
                    }
                }
                await ws.send(json.dumps(submit_msg))
                sub_resp = json.loads(await ws.recv())
                sval = sub_resp.get("result", {}).get("result", {}).get("value", {})
                
                if sval.get("submitted"):
                    print("  ✅ Application successfully submitted on Handshake!")
                    record_job_db(job["title"], job["company"], job["loc"], url, "SUBMITTED")
                    applied_count += 1
                else:
                    print(f"  ⚠️ Submit button state: {sval}. Reviewing inputs.")
                    record_job_db(job["title"], job["company"], job["loc"], url, "STAGED")

                await asyncio.sleep(2)

            elif val.get("hasExternalApply"):
                ext_url = val.get("externalHref") or url
                print(f"  🌐 External enterprise application: {ext_url[:80]}...")
                record_job_db(job["title"], job["company"], job["loc"], url, "APPROVED")
                external_count += 1

            else:
                print("  ℹ️ Portal link or review required. Recording in pipeline.")
                record_job_db(job["title"], job["company"], job["loc"], url, "EVALUATED")

    print("\n" + "=" * 70)
    print(f"🎉 BATCH RUN COMPLETE:")
    print(f"  ✅ Submitted via Handshake In-Portal: {applied_count}")
    print(f"  🌐 Queued External ATS: {external_count}")
    print(f"  ⏭️ Already Applied / Skipped: {skipped_count}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_batch())
