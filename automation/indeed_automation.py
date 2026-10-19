"""
Indeed Apply & Direct Application Automation.
Integrates directly with RealBrowserSessionManager via CDP (port 9222).
Handles Indeed Apply modals, contact auto-fill, resume upload, and screener progression.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Tuple
from automation.real_browser_session import RealBrowserSessionManager
from core.matcher import load_profile

logger = logging.getLogger("jarvis.indeed")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class IndeedAutomation:
    def __init__(self):
        self.profile = load_profile()

    async def apply_to_job(self, job_url: str, auto_submit: bool = False) -> Tuple[bool, str]:
        """
        Navigates to an Indeed job posting in the user's active Chrome session,
        executes Indeed Apply, fills contact info, attaches resume, and stages for review.
        """
        logger.info(f"[Indeed] Initiating application process for: {job_url}")

        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            context, is_cdp = await RealBrowserSessionManager.get_active_context(playwright)
            page = await context.new_page()

            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Look for Indeed Apply button
                apply_btn = page.locator('button#indeedApplyButton, span:has-text("Apply now"), button:has-text("Apply now"), a:has-text("Apply now")').first

                if await apply_btn.count() > 0:
                    logger.info("[Indeed] Found Indeed Apply button. Clicking to open application flow...")
                    await apply_btn.click()
                    await asyncio.sleep(3)

                    p_info = self.profile.get("personal_info", {})

                    # 1. Fill Name & Phone if empty
                    phone_input = page.locator('input[id*="phone"], input[name*="phone"], input[type="tel"]').first
                    if await phone_input.count() > 0 and p_info.get("phone"):
                        val = await phone_input.input_value()
                        if not val:
                            await phone_input.fill(p_info["phone"])

                    # 2. Attach Tailored Resume
                    resume_candidates = [
                        os.path.join(PROJECT_ROOT, "data", "Shadman_Ahsan_Resume.pdf"),
                        os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf"),
                        os.path.join(PROJECT_ROOT, "config", "resume.pdf"),
                    ]
                    resume_file = next((p for p in resume_candidates if os.path.exists(p)), None)
                    file_input = page.locator('input[type="file"]').first
                    if resume_file and await file_input.count() > 0:
                        logger.info(f"[Indeed] Attaching resume: {resume_file}")
                        await file_input.set_input_files(resume_file)
                        await asyncio.sleep(1)

                    # 3. Advance through steps
                    for step in range(4):
                        continue_btn = page.locator('button:has-text("Continue"), button:has-text("Next")').first
                        submit_btn = page.locator('button:has-text("Submit your application"), button:has-text("Submit application")').first

                        if await submit_btn.count() > 0:
                            if auto_submit:
                                await submit_btn.click()
                                await asyncio.sleep(2)
                                logger.info("[Indeed] Application successfully submitted!")
                                return True, "Indeed application submitted successfully."
                            else:
                                logger.info("[Indeed] Staged at review screen for candidate confirmation.")
                                return True, "Indeed application staged at review screen."

                        if await continue_btn.count() > 0:
                            await continue_btn.click()
                            await asyncio.sleep(1.5)
                        else:
                            break

                    return True, "Indeed application workflow processed."
                else:
                    # External employer redirection
                    ext_btn = page.locator('a:has-text("Apply on company site"), button:has-text("Apply on company site")').first
                    if await ext_btn.count() > 0:
                        logger.info("[Indeed] External employer link detected.")
                        return True, "Redirected to employer ATS portal from Indeed."
                    return False, "No recognized Indeed Apply button found."

            except Exception as e:
                logger.error(f"[Indeed Error] {e}")
                return False, f"Indeed automation error: {e}"
            finally:
                await RealBrowserSessionManager.save_session_state(context)
