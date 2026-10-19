"""
LinkedIn Easy Apply & External Application Automation.
Integrates directly with RealBrowserSessionManager via CDP (port 9222).
Automates multi-step Easy Apply dialogs, contact autofill, and tailored PDF resume attachment.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Tuple, Optional
from automation.real_browser_session import RealBrowserSessionManager
from core.matcher import load_profile

logger = logging.getLogger("jarvis.linkedin")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LinkedInAutomation:
    def __init__(self):
        self.profile = load_profile()

    async def apply_to_job(self, job_url: str, auto_submit: bool = False) -> Tuple[bool, str]:
        """
        Navigates to a LinkedIn job posting in the user's active Chrome session,
        executes Easy Apply workflow, fills phone/contact details, attaches resume,
        and either submits or stages at final review.
        """
        logger.info(f"[LinkedIn] Initiating application process for: {job_url}")

        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            context, is_cdp = await RealBrowserSessionManager.get_active_context(playwright)
            page = await context.new_page()

            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Check if this is an Easy Apply job or external employer link
                easy_apply_btn = page.locator('button.jobs-apply-button:has-text("Easy Apply"), button:has-text("Easy Apply")').first
                external_apply_btn = page.locator('button.jobs-apply-button:has-text("Apply"), a:has-text("Apply on company website")').first

                if await easy_apply_btn.count() > 0:
                    logger.info("[LinkedIn] Detected Easy Apply modal button. Launching modal...")
                    await easy_apply_btn.click()
                    await asyncio.sleep(2)

                    # 1. Fill Phone & Contact Info
                    phone = self.profile.get("personal_info", {}).get("phone", "")
                    phone_input = page.locator('input[id*="phoneNumber"], input[name*="phoneNumber"], input[type="tel"]').first
                    if await phone_input.count() > 0 and phone:
                        curr_val = await phone_input.input_value()
                        if not curr_val:
                            await phone_input.fill(phone)

                    # 2. Attach Tailored PDF Resume
                    resume_candidates = [
                        os.path.join(PROJECT_ROOT, "data", "Shadman_Ahsan_Resume.pdf"),
                        os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf"),
                        os.path.join(PROJECT_ROOT, "config", "resume.pdf"),
                    ]
                    resume_file = next((p for p in resume_candidates if os.path.exists(p)), None)
                    file_input = page.locator('input[type="file"]').first
                    if resume_file and await file_input.count() > 0:
                        logger.info(f"[LinkedIn] Attaching tailored resume: {resume_file}")
                        await file_input.set_input_files(resume_file)
                        await asyncio.sleep(1)

                    # 3. Step through multi-page modal (Next / Review)
                    for step in range(5):
                        next_btn = page.locator('button:has-text("Next"), button[aria-label="Continue to next step"]').first
                        review_btn = page.locator('button:has-text("Review"), button[aria-label="Review your application"]').first
                        submit_btn = page.locator('button:has-text("Submit application"), button[aria-label="Submit application"]').first

                        if await submit_btn.count() > 0:
                            if auto_submit:
                                await submit_btn.click()
                                await asyncio.sleep(2)
                                logger.info("[LinkedIn] Successfully submitted Easy Apply!")
                                return True, "LinkedIn Easy Apply application submitted successfully."
                            else:
                                logger.info("[LinkedIn] Application staged at Review screen for candidate confirmation.")
                                return True, "LinkedIn Easy Apply ready at Review screen (Staged for candidate confirmation)."

                        if await review_btn.count() > 0:
                            await review_btn.click()
                            await asyncio.sleep(1.5)
                            continue

                        if await next_btn.count() > 0:
                            await next_btn.click()
                            await asyncio.sleep(1.5)
                        else:
                            break

                    return True, "LinkedIn Easy Apply stepped through successfully."

                elif await external_apply_btn.count() > 0:
                    logger.info("[LinkedIn] External company application link. Directing candidate to employer portal...")
                    ext_url = None
                    try:
                        async with page.expect_popup(timeout=8000) as popup_info:
                            await external_apply_btn.click()
                        popup = await popup_info.value
                        await popup.wait_for_load_state("domcontentloaded")
                        ext_url = popup.url
                        await popup.close()
                    except Exception:
                        href = await external_apply_btn.get_attribute("href")
                        if href and href.startswith("http"):
                            ext_url = href

                    if ext_url and "linkedin.com" not in ext_url:
                        logger.info(f"[LinkedIn] Captured external employer ATS URL: {ext_url[:80]}...")
                        success, msg = await RealBrowserSessionManager.execute_real_application_fill(
                            ext_url, "Cybersecurity Specialist", "LinkedIn Partner Employer"
                        )
                        return success, f"LinkedIn external application: {msg}"
                    else:
                        return True, "Redirected to employer ATS portal from LinkedIn."
                else:
                    return False, "Neither Easy Apply nor direct Apply button detected on LinkedIn posting."

            except Exception as e:
                logger.error(f"[LinkedIn Error] {e}")
                return False, f"LinkedIn automation error: {e}"
            finally:
                await RealBrowserSessionManager.save_session_state(context)
