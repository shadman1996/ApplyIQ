"""
Handshake (joinhandshake.com) Collegiate Application Automation.
Integrates directly with RealBrowserSessionManager via CDP (port 9222).
Automates collegiate internship applications, student profile verification, and resume submission.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Tuple
from automation.real_browser_session import RealBrowserSessionManager
from core.matcher import load_profile

logger = logging.getLogger("jarvis.handshake")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HandshakeAutomation:
    def __init__(self):
        self.profile = load_profile()

    async def apply_to_job(self, job_url: str, auto_submit: bool = False) -> Tuple[bool, str]:
        """
        Navigates to a Handshake posting in the user's collegiate session,
        executes Quick Apply / Apply on Handshake, attaches candidate resume, and submits.
        """
        logger.info(f"[Handshake] Initiating application process for: {job_url}")

        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            context, is_cdp = await RealBrowserSessionManager.get_active_context(playwright)
            page = await context.new_page()

            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Look for Handshake Apply button
                apply_btn = page.locator('button:has-text("Apply"), button:has-text("Quick Apply"), a:has-text("Apply")').first

                if await apply_btn.count() > 0:
                    logger.info("[Handshake] Found Apply button. Opening modal...")
                    await apply_btn.click()
                    await asyncio.sleep(2)

                    # Check for Resume upload / selection
                    resume_candidates = [
                        os.path.join(PROJECT_ROOT, "data", "Shadman_Ahsan_Resume.pdf"),
                        os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf"),
                        os.path.join(PROJECT_ROOT, "config", "resume.pdf"),
                    ]
                    resume_file = next((p for p in resume_candidates if os.path.exists(p)), None)
                    file_input = page.locator('input[type="file"]').first

                    if resume_file and await file_input.count() > 0:
                        logger.info(f"[Handshake] Uploading tailored resume: {resume_file}")
                        await file_input.set_input_files(resume_file)
                        await asyncio.sleep(1)

                    # Look for Submit / Finish button
                    submit_btn = page.locator('button:has-text("Submit Application"), button:has-text("Finish")').first
                    if await submit_btn.count() > 0:
                        if auto_submit:
                            await submit_btn.click()
                            await asyncio.sleep(2)
                            logger.info("[Handshake] Successfully submitted collegiate application!")
                            return True, "Handshake application submitted successfully."
                        else:
                            logger.info("[Handshake] Application staged at confirmation screen.")
                            return True, "Handshake application ready for student review."

                    return True, "Handshake application form opened and populated."

                # If external employer link
                ext_link = page.locator('a:has-text("Apply externally"), a:has-text("Apply on employer website"), button:has-text("Apply externally")').first
                if await ext_link.count() > 0:
                    logger.info("[Handshake] External application detected. Routing to employer ATS...")
                    ext_url = None
                    try:
                        async with page.expect_popup(timeout=8000) as popup_info:
                            await ext_link.click()
                        popup = await popup_info.value
                        await popup.wait_for_load_state("domcontentloaded")
                        ext_url = popup.url
                        await popup.close()
                    except Exception:
                        href = await ext_link.get_attribute("href")
                        if href and href.startswith("http"):
                            ext_url = href

                    if ext_url and "joinhandshake.com" not in ext_url:
                        logger.info(f"[Handshake] Captured external employer ATS URL: {ext_url[:80]}...")
                        # Delegate to real browser ATS filler
                        success, msg = await RealBrowserSessionManager.execute_real_application_fill(
                            ext_url, "Cybersecurity / IT Intern", "Collegiate Employer"
                        )
                        return success, f"Handshake external application: {msg}"
                    else:
                        return True, "Handshake external application link opened in browser for review."

                return False, "Handshake apply button not found."

            except Exception as e:
                logger.error(f"[Handshake Error] {e}")
                return False, f"Handshake automation error: {e}"
            finally:
                await RealBrowserSessionManager.save_session_state(context)
