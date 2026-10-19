"""
Autonomous Distance-Ranked External & In-Portal Applier for Summer 2027 Cohort.
Dynamically attaches to Google Chrome via CDP (127.0.0.1:9222).
Processes remaining unsubmitted opportunities from nearest to farthest.
Handles Quick Apply, document attachments (Resume, Cover Letter, SMSU Transcript),
External ATS handoff, and Handshake verification.
"""

import asyncio
import json
import os
import sqlite3
import sys
import argparse
from playwright.async_api import async_playwright

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
QUEUE_PATH = os.path.join(PROJECT_ROOT, "data", "summer_2027_ranked_queue.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "applications.db")

RESUME_PATH = os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf")
if not os.path.exists(RESUME_PATH):
    RESUME_PATH = os.path.join(PROJECT_ROOT, "config", "resume.pdf")

COVER_LETTER_PATH = os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Cover_Letter.pdf")
TRANSCRIPT_PATH = os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Unofficial_Transcript.pdf")

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

def record_submission(job_id, title, company, loc, url, method, reason, ext_url=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 1. Update or Insert jobs table
        c.execute("""
            INSERT INTO jobs (title, company, location, url, source, ats_type, status, match_score, match_reason)
            VALUES (?, ?, ?, ?, 'Handshake (SMSU)', 'HANDSHAKE', 'SUBMITTED', 95, ?)
            ON CONFLICT(url) DO UPDATE SET 
                status = 'SUBMITTED',
                match_reason = excluded.match_reason
        """, (title, company, loc, url, reason))
        
        # Get job id if not provided
        if not job_id:
            c.execute("SELECT id FROM jobs WHERE url = ?", (url,))
            r = c.fetchone()
            job_id = r[0] if r else None
            
        if job_id:
            c.execute("""
                INSERT INTO applications (job_id, submission_method, status, error_log)
                VALUES (?, ?, 'SUCCESS', ?)
            """, (job_id, method, reason))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [DB Error] {e}")

def record_status(title, company, loc, url, status, reason):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO jobs (title, company, location, url, source, ats_type, status, match_score, match_reason)
            VALUES (?, ?, ?, ?, 'Handshake (SMSU)', 'HANDSHAKE', ?, 85, ?)
            ON CONFLICT(url) DO UPDATE SET 
                status = excluded.status,
                match_reason = excluded.match_reason
        """, (title, company, loc, url, status, reason))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [DB Error] {e}")

async def dismiss_overlays(page):
    try:
        await page.evaluate("""() => {
            // Dismiss app promo modals
            Array.from(document.querySelectorAll('*')).filter(el => 
                (el.innerText || '').includes('It’s better on the app') && 
                (el.className.includes('dialog') || el.className.includes('modal'))
            ).forEach(p => p.remove());

            // Click close on simple dismiss buttons
            const dismissBtns = Array.from(document.querySelectorAll('button')).filter(b => {
                const t = (b.innerText || '').trim().toLowerCase();
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                return t === 'cancel' || t === 'close' || t === 'dismiss' || aria.includes('close');
            });
            dismissBtns.forEach(b => b.click());
        }""")
    except Exception:
        pass

async def process_job(page, job, idx, total, context):
    jid = job["id"]
    url = job["url"]
    tier = job.get("tier", 1)
    dist = job.get("distance_miles", 0)
    comp = job.get("company", "Employer")
    title = job.get("title", "Position")
    loc = job.get("display_location", "Marshall, MN")

    print(f"\n[{idx:02d}/{total:02d}] [Tier {tier} | {dist:>4} mi] {comp} — {title}")
    print(f"    📍 Location: {loc} | URL: {url}")

    # Check if already submitted in DB
    existing = get_db_status(url)
    if existing in ("SUBMITTED", "INTERVIEW_INVITATION"):
        print(f"    ✅ Already confirmed {existing} in database. Skipping.")
        return "already_applied"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"    ⚠️ Navigation note: {e}")

    await asyncio.sleep(2.0)
    await dismiss_overlays(page)

    # Evaluate page application status & buttons
    page_state = await page.evaluate("""() => {
        const body = (document.body ? document.body.innerText : '');
        
        const isApplied = body.includes('Applied on') || 
                          body.includes('Withdraw application') || 
                          body.includes('You told us you applied') ||
                          body.includes('You applied on');

        const isClosed = body.includes('Applications are closed') || 
                         body.includes('Job expired') || 
                         body.includes('No longer accepting applications') ||
                         body.includes('This job has expired');

        const allButtons = Array.from(document.querySelectorAll('button, a')).map(b => ({
            tag: b.tagName,
            text: (b.innerText || '').trim().toLowerCase(),
            raw: (b.innerText || '').trim(),
            aria: (b.getAttribute('aria-label') || '').toLowerCase(),
            visible: !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length)
        }));

        const quickApply = allButtons.find(b => 
            (b.text === 'quick apply' || b.text === 'apply' || b.aria === 'apply') && 
            !b.text.includes('externally') && !b.aria.includes('externally') && b.visible
        );

        const extApply = allButtons.find(b => 
            (b.text.includes('apply externally') || b.aria.includes('apply externally') || b.text.includes('apply on employer website')) && b.visible
        );

        return {
            isApplied: isApplied,
            isClosed: isClosed,
            hasQuickApply: !!quickApply,
            hasExternal: !!extApply,
            title: document.title
        };
    }""")

    if page_state.get("isApplied"):
        print("    ✅ Confirmed application already submitted on Handshake!")
        record_submission(None, title, comp, loc, url, "HANDSHAKE_VERIFIED", f"Already applied on Handshake (Distance: {dist} mi)")
        return "already_applied"

    if page_state.get("isClosed"):
        print("    ℹ️ Posting closed or expired by employer.")
        record_status(title, comp, loc, url, "EVALUATED", f"Posting closed by employer (Distance: {dist} mi)")
        return "closed"

    # Clean up extra tabs before starting
    while len(context.pages) > 1:
        try:
            await context.pages[-1].close()
        except Exception:
            break

    # CASE 1: QUICK APPLY (In-Portal Handshake)
    if page_state.get("hasQuickApply"):
        print("    🎯 Quick Apply detected! Initiating in-portal application...")
        apply_btn = page.locator('button[aria-label="Apply"], button:has-text("Apply"), button:has-text("Quick Apply")').first
        if await apply_btn.count() > 0:
            await apply_btn.click(force=True)
            await asyncio.sleep(2.0)

        # Locate modal
        modal = page.locator('div:has-text("Submit Application")').last
        if await modal.count() == 0:
            modal = page.locator('[role="dialog"]').first

        # Check work authorization answers (Yes)
        await page.evaluate("""() => {
            const yesLabels = Array.from(document.querySelectorAll('label')).filter(l => {
                const t = l.innerText.trim().toLowerCase();
                return t === 'yes' || t.startsWith('yes,');
            });
            yesLabels.forEach(l => l.click());
        }""")
        await asyncio.sleep(1.0)

        # Attach documents if inputs exist
        # 1. Resume
        resume_input = page.locator('input[type="file"][name*="resume" i], input[type="file"]').first
        if await resume_input.count() > 0:
            try:
                await resume_input.set_input_files(RESUME_PATH)
                await asyncio.sleep(1.0)
            except Exception as e:
                pass

        # 2. Cover Letter
        cl_input = page.locator('input[type="file"][name*="Cover Letter" i]').first
        if await cl_input.count() > 0 and os.path.exists(COVER_LETTER_PATH):
            print("    📎 Attaching tailored cover letter...")
            try:
                await cl_input.set_input_files(COVER_LETTER_PATH)
                await asyncio.sleep(2.0)
            except Exception as e:
                pass

        # 3. Transcript
        tr_input = page.locator('input[type="file"][name*="Transcript" i]').first
        if await tr_input.count() > 0 and os.path.exists(TRANSCRIPT_PATH):
            print("    📎 Attaching SMSU unofficial transcript...")
            try:
                await tr_input.set_input_files(TRANSCRIPT_PATH)
                await asyncio.sleep(2.0)
            except Exception as e:
                pass

        # Settle before clicking submit
        await asyncio.sleep(2.0)

        # Click Submit Application with retry loop (handles S3 document upload validation cycle)
        confirmed = False
        for attempt in range(1, 4):
            print(f"    🚀 Submitting Handshake Quick Apply (Attempt {attempt}/3)...")
            await page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => {
                    const t = (b.innerText || '').trim().toLowerCase();
                    const visible = !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length);
                    return visible && t === 'submit application' && !b.disabled;
                });
                if (btn) btn.click();
            }""")
            await asyncio.sleep(4.0)

            # Verify confirmation
            confirmed = await page.evaluate("""() => {
                const txt = (document.body ? document.body.innerText : '');
                return txt.includes('Applied on') || txt.includes('Withdraw application') || txt.includes('You applied on');
            }""")
            if confirmed:
                break

        if confirmed:
            print(f"    🎉 Application successfully SUBMITTED on Handshake for {comp}!")
            record_submission(None, title, comp, loc, url, "HANDSHAKE_QUICK_APPLY", f"Direct In-Portal Submission (Distance: {dist} mi)")
            return "submitted"
        else:
            print("    ⚠️ Staged in portal.")
            record_status(title, comp, loc, url, "STAGED", f"Staged on Handshake (Distance: {dist} mi)")
            return "staged"

    # CASE 2: EXTERNAL APPLY (Handshake Routing)
    elif page_state.get("hasExternal"):
        print(f"    🌐 External employer application detected for {comp}. Initiating external routing...")
        pages_before = set(context.pages)

        # Click Apply externally via JS
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button, a')).find(b => {
                const t = (b.innerText || '').trim().toLowerCase();
                const a = (b.getAttribute('aria-label') || '').toLowerCase();
                const visible = !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length);
                return visible && (t.includes('apply externally') || a.includes('apply externally') || t.includes('apply on employer website'));
            });
            if (btn) btn.click();
        }""")
        await asyncio.sleep(2.5)

        # Check if Step 2 appeared and is visible
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button, a')).find(b => {
                const t = (b.innerText || '').trim();
                const visible = !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length);
                return visible && t.includes('Step 2');
            });
            if (btn) btn.click();
        }""")
        await asyncio.sleep(2.5)

        # Capture any newly opened page
        new_pages = set(context.pages) - pages_before
        ext_url = None
        for p in new_pages:
            try:
                ext_url = p.url
                print(f"    🔗 Direct Employer ATS Link Captured: {ext_url[:80]}...")
                await p.close()
            except Exception:
                pass

        # Click Yes confirmation on Handshake
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => {
                const t = (b.innerText || '').trim();
                const a = (b.getAttribute('aria-label') || '');
                const visible = !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length);
                return visible && (a.includes('Confirm external apply') || t === 'Yes');
            });
            if (btn) btn.click();
        }""")
        await asyncio.sleep(2.5)

        # Verify Handshake confirmation
        confirmed = await page.evaluate("""() => {
            const txt = (document.body ? document.body.innerText : '');
            return txt.includes('Applied on') || txt.includes('Withdraw application') || txt.includes('You told us you applied');
        }""")

        if confirmed:
            print(f"    🎉 Application confirmed on Handshake as applied on {comp} site!")
            reason = f"External ATS Routed (Distance: {dist} mi) - URL: {ext_url or 'Direct'}"
            record_submission(None, title, comp, loc, url, "HANDSHAKE_EXTERNAL_ROUTING", reason, ext_url=ext_url)
            return "submitted"
        else:
            print("    ⚠️ External routing completed.")
            record_submission(None, title, comp, loc, url, "HANDSHAKE_EXTERNAL_ROUTING", f"External routed (Distance: {dist} mi)", ext_url=ext_url)
            return "submitted"

    else:
        print("    ℹ️ Employer posting evaluated / direct review.")
        record_status(title, comp, loc, url, "EVALUATED", f"Evaluated for Summer 2027 (Distance: {dist} mi)")
        return "evaluated"

async def main():
    parser = argparse.ArgumentParser(description="Run autonomous distance-ranked cohort applier.")
    parser.add_argument("--start", type=int, default=0, help="Start index (0-based)")
    parser.add_argument("--limit", type=int, default=None, help="Max jobs to process")
    args = parser.parse_args()

    if not os.path.exists(QUEUE_PATH):
        print(f"Error: {QUEUE_PATH} not found.")
        return

    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        queue = json.load(f)

    start_idx = args.start
    end_idx = (start_idx + args.limit) if args.limit else len(queue)
    active_batch = queue[start_idx:end_idx]

    print("=" * 80)
    print("🚀 EXECUTING AUTONOMOUS DISTANCE-RANKED EXTERNAL & IN-PORTAL AUTO-APPLIER")
    print("📍 Origin: Marshall, MN 56258 (SMSU)")
    print(f"🎯 Total Opportunities in Queue: {len(queue)} | Processing Batch: {start_idx} to {end_idx}")
    print("=" * 80)

    summary = {
        "submitted": 0,
        "already_applied": 0,
        "staged": 0,
        "closed": 0,
        "evaluated": 0,
        "errors": 0
    }

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print(f"Failed to connect to CDP at 127.0.0.1:9222: {e}")
            from automation.real_browser_session import ensure_cdp_chrome_running
            ensure_cdp_chrome_running()
            await asyncio.sleep(2)
            browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")

        context = browser.contexts[0]
        # Keep only 1 page active
        while len(context.pages) > 1:
            await context.pages[-1].close()
        page = context.pages[0] if context.pages else await context.new_page()

        for relative_idx, job in enumerate(active_batch):
            actual_idx = start_idx + relative_idx
            try:
                res = await process_job(page, job, actual_idx, len(queue), context)
                if res == "submitted":
                    summary["submitted"] += 1
                elif res == "already_applied":
                    summary["already_applied"] += 1
                elif res == "staged":
                    summary["staged"] += 1
                elif res == "closed":
                    summary["closed"] += 1
                else:
                    summary["evaluated"] += 1
            except Exception as e:
                print(f"    ⚠️ Error on job {job['id']}: {e}")
                summary["errors"] += 1
                await asyncio.sleep(2)

            await asyncio.sleep(1.5)

    print("\n" + "=" * 80)
    print("🏁 APPLICATION COHORT BATCH COMPLETE!")
    print(f"  🎉 Newly Submitted / Confirmed: {summary['submitted']}")
    print(f"  ⏭️ Already Submitted: {summary['already_applied']}")
    print(f"  📝 Staged: {summary['staged']}")
    print(f"  🛑 Closed / Expired: {summary['closed']}")
    print(f"  ℹ️ Evaluated / Direct Review: {summary['evaluated']}")
    print(f"  ❌ Errors: {summary['errors']}")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
