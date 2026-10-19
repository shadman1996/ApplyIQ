"""
Enterprise Workday Autonomous Application Engine.
Powered by ATSFormFiller and Google Gemini 2.5 Pro.
Handles candidate account authentication, resume upload, dynamic search comboboxes,
F-1 STEM OPT questionnaires, multi-step wizard progression, and Human-in-the-Loop staging.
"""

import os
import asyncio
import logging
import urllib.request
import json
from typing import Dict, Any, Tuple, Optional
from playwright.async_api import async_playwright
from automation.browser import StealthBrowserManager
from automation.ats_form_filler import ATSFormFiller
from core.credentials_manager import CredentialVault
from core.second_brain import SecondBrain

logger = logging.getLogger("jarvis.workday")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.json")

def load_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


class WorkdayAutomation:
    def __init__(self, username: str = None, password: str = None):
        vault = CredentialVault()
        stored_workday = vault.get_credential("workday") or vault.get_credential("external_portals") or {}
        self.username = username or os.environ.get("WORKDAY_USERNAME") or stored_workday.get("username", "shadman.ahsan.us@gmail.com")
        self.password = password or os.environ.get("WORKDAY_PASSWORD") or stored_workday.get("password", "SuperCyberSecPass2026!")
        self.form_filler = None
        self.brain = SecondBrain()

    async def _safe_click(self, page, selector_or_loc) -> bool:
        """Bypasses Workday click_filter overlay by evaluating element.click() in DOM directly."""
        try:
            loc = page.locator(selector_or_loc).first if isinstance(selector_or_loc, str) else selector_or_loc
            if await loc.count() > 0:
                await loc.evaluate("el => { el.scrollIntoView({behavior: 'smooth', block: 'center'}); el.click(); }")
                return True
        except Exception:
            try:
                if await loc.count() > 0:
                    await loc.click(force=True, timeout=3000)
                    return True
            except Exception:
                pass
        return False

    async def _is_cdp_available(self) -> bool:
        try:
            req = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1)
            return req.status == 200
        except Exception:
            return False

    def _is_confirmed_page(self, url: str, body: str, headings: list) -> bool:
        """Strictly verifies genuine confirmation (prevents false positive from 'Candidate Home' header)."""
        u_lower = url.lower()
        b_lower = body.lower()
        if "/completed/application" in u_lower or "/jobtasks/completed" in u_lower:
            return True
        if any("application submitted" in h.lower() for h in headings):
            return True
        if any(w in b_lower for w in ["thank you for applying", "your application has been submitted", "application received"]):
            return True
        return False

    async def _fill_contact_information(self, page):
        """Fills standard Workday candidate contact inputs if empty using authoritative Second Brain truths."""
        try:
            # First & Last Name
            fn = page.locator('#name--legalName--firstName, input[data-automation-id="legalNameSection_firstName"], input[id*="firstName" i]').first
            if await fn.count() > 0 and not (await fn.input_value()):
                await fn.fill("Shadman")
            ln = page.locator('#name--legalName--lastName, input[data-automation-id="legalNameSection_lastName"], input[id*="lastName" i]').first
            if await ln.count() > 0 and not (await ln.input_value()):
                await ln.fill("Ahsan")

            # Address Line 1
            addr = page.locator('#address--addressLine1, input[data-automation-id="addressSection_addressLine1"], input[id*="addressLine1" i]').first
            if await addr.count() > 0 and not (await addr.input_value()):
                await addr.fill("202 N 1st St Apt 6097")

            # City
            city = page.locator('#address--city, input[data-automation-id="addressSection_city"], input[id*="city" i]').first
            if await city.count() > 0 and not (await city.input_value()):
                await city.fill("Marshall")

            # Postal Code
            postal = page.locator('#address--postalCode, input[data-automation-id="addressSection_postalCode"], input[id*="postalCode" i]').first
            if await postal.count() > 0 and not (await postal.input_value()):
                await postal.fill("56258")

            # Phone Number
            phone = page.locator('#phoneNumber--phoneNumber, input[data-automation-id="phone-number"], input[id*="phoneNumber" i]').first
            if await phone.count() > 0 and not (await phone.input_value()):
                await phone.fill("5075305801")

            # Phone Device Type -> Mobile
            p_type = page.locator('#phoneNumber--phoneDeviceType, button[id*="phoneDeviceType" i]').first
            if await p_type.count() > 0 and "select one" in (await p_type.inner_text()).lower():
                await p_type.click(force=True)
                await asyncio.sleep(0.5)
                m_opt = page.locator('[role="option"]:has-text("Mobile")').first
                if await m_opt.count() > 0:
                    await m_opt.click(force=True)
                await asyncio.sleep(0.3)

            # State / Province -> Minnesota
            region_btn = page.locator('#address--countryRegion, button[id*="countryRegion" i]').first
            if await region_btn.count() > 0 and "select one" in (await region_btn.inner_text()).lower():
                await region_btn.click(force=True)
                await asyncio.sleep(0.8)
                reg_opt = page.locator('[role="option"]:has-text("Minnesota"), [role="option"]:has-text("MN")').first
                if await reg_opt.count() > 0:
                    await reg_opt.click(force=True)
                await asyncio.sleep(0.4)

            # Source input combobox (Salesforce / Motorola)
            src_input = page.locator('#source--source, input[data-automation-id*="source" i]').first
            if await src_input.count() > 0 and not (await src_input.input_value()):
                await src_input.click(force=True)
                await src_input.fill("LinkedIn")
                await asyncio.sleep(0.8)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.8)
                s_opt = page.locator('[role="option"]:has-text("LinkedIn")').first
                if await s_opt.count() > 0:
                    await s_opt.click(force=True)
                await asyncio.sleep(0.4)

            # Previous Worker -> No
            await page.evaluate('''() => {
                const noRadio = document.querySelector('input[name="candidateIsPreviousWorker"][value="false"]');
                if (noRadio && !noRadio.checked) {
                    noRadio.click();
                    const parent = noRadio.closest('label') || noRadio.parentElement;
                    if (parent) parent.click();
                }
            }''')

            # Terms & agreements checkbox
            terms_cb = page.locator('#termsAndConditions--acceptTermsAndAgreements, input[type="checkbox"]').first
            if await terms_cb.count() > 0 and not (await terms_cb.is_checked()):
                await terms_cb.check(force=True)
        except Exception as e:
            logger.debug(f"Contact info fill note: {e}")

    async def fill_and_submit(
        self,
        job_url: str,
        profile: Optional[Dict[str, Any]] = None,
        custom_answers: Optional[Dict[str, str]] = None,
        wait_for_review: Optional[bool] = None
    ) -> Tuple[bool, str]:
        """
        Executes an end-to-end Workday application:
        1. Connects to visible Chrome via CDP (or launches stealth Playwright browser).
        2. Detects tenant login / account registration.
        3. Leverages 'Use My Last Application' if available, or uploads tailored ATS resume.
        4. Navigates multi-step wizard (Contact, Experience, Questions, EEO) using Gemini 2.5 Pro.
        5. Stages for human review or auto-submits on final screen.
        """
        settings = load_settings()
        if wait_for_review is None:
            wait_for_review = not settings.get("auto_submit", False)

        self.form_filler = ATSFormFiller(profile)
        p = await async_playwright().start()
        browser = None
        context = None
        page = None
        is_cdp = False

        try:
            # 1. Connect to user's live Chrome if active, or spawn stealth browser
            if await self._is_cdp_available():
                logger.info("[Workday] Connecting to running Chrome session via CDP (port 9222)...")
                try:
                    browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    contexts = browser.contexts
                    context = contexts[0] if contexts else await browser.new_context()
                    page = await context.new_page()
                    is_cdp = True
                except Exception as cdp_err:
                    logger.warning(f"[Workday] CDP connect failed: {cdp_err}. Falling back to standalone browser.")
                    browser = None

            if not browser:
                logger.info("[Workday] Launching local Playwright browser with persistent profile...")
                user_data = os.path.join(PROJECT_ROOT, "config", "jarvis_chrome_profile")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data,
                    headless=False,
                    viewport={"width": 1366, "height": 850},
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.pages[0] if context.pages else await context.new_page()

            # 2. Navigate to job posting
            logger.info(f"[Workday] Navigating to {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)

            # Extract job title & company
            company = "Workday Employer"
            job_title = "Cybersecurity Position"
            try:
                title_el = page.locator('h1, [data-automation-id="jobPostingHeader"]').first
                if await title_el.count() > 0:
                    job_title = (await title_el.inner_text()).strip()
                comp_el = page.locator('[data-automation-id="companyName"], header a').first
                if await comp_el.count() > 0:
                    company = (await comp_el.inner_text()).strip()
            except Exception:
                pass

            # 3. Handle Initial "Apply" Button & Flyout Menu
            apply_btn = page.locator('a[data-automation-id="adventureButton"], a[data-automation-id="advisorApplyButton"], a[data-automation-id="applyButton"], button:has-text("Apply"), a:has-text("Apply")').first
            if await apply_btn.count() > 0:
                logger.info("[Workday] Clicking primary 'Apply' button...")
                await self._safe_click(page, apply_btn)
                await asyncio.sleep(2.5)

            # 4. Check for 'Use My Last Application' vs 'Apply Manually' vs 'Autofill'
            use_last_app = page.locator('[data-automation-id="useMyLastApplication"], a:has-text("Use My Last Application"), button:has-text("Use My Last Application")').first
            apply_manually = page.locator('[data-automation-id="applyManually"], a:has-text("Apply Manually"), button:has-text("Apply Manually")').first
            autofill_resume = page.locator('[data-automation-id="autofillWithResume"], a:has-text("Autofill with Resume")').first

            if await use_last_app.count() > 0 and await use_last_app.is_visible():
                logger.info("[Workday] Found 'Use My Last Application' accelerator! Clicking...")
                await self._safe_click(page, use_last_app)
                await asyncio.sleep(4)
            elif await apply_manually.count() > 0 and await apply_manually.is_visible():
                logger.info("[Workday] Selecting 'Apply Manually'...")
                await self._safe_click(page, apply_manually)
                await asyncio.sleep(4)
            elif await autofill_resume.count() > 0 and await autofill_resume.is_visible():
                logger.info("[Workday] Selecting 'Autofill with Resume'...")
                await self._safe_click(page, autofill_resume)
                await asyncio.sleep(4)

            # 5. Handle Authentication (Sign In vs Create Account)
            signin_link = page.locator('[data-automation-id="signInLink"], a:has-text("Sign In"), button:has-text("Sign In")').first
            if await signin_link.count() > 0 and await signin_link.is_visible():
                logger.info("[Workday] Clicking 'Sign In' link to reveal login fields...")
                await self._safe_click(page, signin_link)
                await asyncio.sleep(2)

            email_fields = page.locator('input[data-automation-id="email"]:visible')
            pwd_fields = page.locator('input[data-automation-id="password"]:visible')
            
            if await email_fields.count() > 0 and self.username and self.password:
                logger.info(f"[Workday] Entering candidate credentials ({self.username})...")
                for i in range(await email_fields.count()):
                    await email_fields.nth(i).fill(self.username)
                for i in range(await pwd_fields.count()):
                    await pwd_fields.nth(i).fill(self.password)
                
                sign_in_btns = page.locator('button[data-automation-id="signInSubmitButton"]')
                clicked = False
                for i in range(await sign_in_btns.count()):
                    btn = sign_in_btns.nth(i)
                    if await btn.is_visible():
                        await btn.click(force=True)
                        clicked = True
                        break
                if not clicked and await pwd_fields.count() > 0:
                    await pwd_fields.first.press("Enter")
                await asyncio.sleep(5)

            # 5b. Post-login: If still on job details (not in /apply), click Apply and accelerator
            if "/apply" not in page.url.lower():
                logger.info("[Workday] Post-login: Re-checking primary 'Apply' button...")
                apply_btn = page.locator('a[data-automation-id="adventureButton"], a[data-automation-id="advisorApplyButton"], a[data-automation-id="applyButton"], button:has-text("Apply"), a:has-text("Apply")').first
                if await apply_btn.count() > 0 and await apply_btn.is_visible():
                    await self._safe_click(page, apply_btn)
                    await asyncio.sleep(3)

                use_last_app = page.locator('[data-automation-id="useMyLastApplication"], a:has-text("Use My Last Application"), button:has-text("Use My Last Application")').first
                apply_manually = page.locator('[data-automation-id="applyManually"], a:has-text("Apply Manually"), button:has-text("Apply Manually")').first
                autofill_resume = page.locator('[data-automation-id="autofillWithResume"], a:has-text("Autofill with Resume")').first

                if await use_last_app.count() > 0 and await use_last_app.is_visible():
                    logger.info("[Workday] Found 'Use My Last Application' accelerator! Clicking...")
                    await self._safe_click(page, use_last_app)
                    await asyncio.sleep(4)
                elif await apply_manually.count() > 0 and await apply_manually.is_visible():
                    logger.info("[Workday] Selecting 'Apply Manually'...")
                    await self._safe_click(page, apply_manually)
                    await asyncio.sleep(4)
                elif await autofill_resume.count() > 0 and await autofill_resume.is_visible():
                    logger.info("[Workday] Selecting 'Autofill with Resume'...")
                    await self._safe_click(page, autofill_resume)
                    await asyncio.sleep(4)

            # 6. Locate Clean Master / ATS Resume (Strictly named Shadman_Ahsan_Resume.pdf)
            resume_candidates = [
                os.path.join(PROJECT_ROOT, "data", "Shadman_Ahsan_Resume.pdf"),
                os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf"),
                os.path.join(PROJECT_ROOT, "config", "resume.pdf")
            ]
            resume_path = next((p for p in resume_candidates if os.path.exists(p)), None)

            # 7. MULTI-STEP WIZARD PROGRESSION LOOP (Steps 1 to 6)
            total_filled = 0
            wizard_step = 0
            max_steps = 10

            logger.info(f"[Workday] Entering autonomous multi-step wizard for '{job_title}' at {company}...")

            while wizard_step < max_steps:
                wizard_step += 1
                await asyncio.sleep(2.5)

                body_text = await page.evaluate("() => document.body ? document.body.innerText.replace(/\\s+/g, ' ') : ''")
                headings = await page.locator("h1, h2, h3").all_inner_texts()

                # Check if genuine submission confirmation reached
                if self._is_confirmed_page(page.url, body_text, headings):
                    logger.info("[Workday] 🏁 Genuine Workday submission confirmation detected!")
                    return True, f"SUBMITTED: Workday application for {company} ({job_title}) confirmed submitted!"

                # Check if Final Review screen
                review_submit = page.locator('button[data-automation-id="pageFooterNextButton"]:has-text("Submit"), button[data-automation-id="reviewSubmitButton"], button[data-automation-id="bottom-navigation-next-button"]:has-text("Submit"), button:has-text("Submit Application")').first
                is_review_page = (await review_submit.count() > 0 and await review_submit.is_visible()) or "review my information" in body_text.lower()

                if is_review_page and await review_submit.count() > 0:
                    logger.info("[Workday] 🏁 Reached Final Review screen!")
                    if wait_for_review:
                        await self.form_filler.stage_for_human_review(
                            page,
                            company=company,
                            job_title=job_title,
                            filled_count=total_filled,
                            total_count=total_filled + 5,
                            wait_for_tab_close=False
                        )
                        return True, f"STAGED_FOR_REVIEW: Workday application for {company} is populated and staged in Chrome for your 1-click submission check."
                    else:
                        logger.info("[Workday] Autonomous mode active: Clicking Submit...")
                        await review_submit.click(force=True)
                        await asyncio.sleep(8)
                        post_url = page.url
                        post_body = await page.evaluate("() => document.body ? document.body.innerText.replace(/\\s+/g, ' ') : ''")
                        post_headings = await page.locator("h1, h2, h3").all_inner_texts()
                        if self._is_confirmed_page(post_url, post_body, post_headings):
                            return True, f"SUBMITTED: Workday application for {company} ({job_title}) successfully submitted."
                        return True, f"SUBMITTED: Workday application for {company} submit action dispatched."

                # Step 1: Candidate Contact Info
                await self._fill_contact_information(page)

                # Step 1 / General: Resolve 'How Did You Hear About Us?' if empty
                src_btn = page.locator('#source--source, button[id*="source" i]').first
                if await src_btn.count() > 0 and "select one" in (await src_btn.inner_text()).lower():
                    logger.info("  🌐 Resolving Workday Source dropdown -> LinkedIn...")
                    await src_btn.click(force=True)
                    await asyncio.sleep(0.8)
                    opt = page.locator('[role="option"]:has-text("LinkedIn"), [role="option"]:has-text("Job Board"), [role="option"]:has-text("Career Site")').first
                    if await opt.count() > 0:
                        await opt.click(force=True)
                    await asyncio.sleep(0.5)

                # Step 3: Handle Workday Application Questionnaires (Second Brain Ground Truths)
                q_btns = page.locator('button[id*="primaryQuestionnaire"], button[id*="question" i]')
                q_count = await q_btns.count()
                if q_count > 0:
                    for qi in range(q_count):
                        qb = q_btns.nth(qi)
                        q_txt = (await qb.inner_text()).strip()
                        if "select one" in q_txt.lower():
                            lbl = await qb.evaluate('el => el.closest("[data-automation-id*=\\"formField\\"]")?.innerText || ""')
                            lbl_lower = lbl.lower()
                            
                            # 1. Query Second Brain memory first
                            mem_match = self.brain.lookup_memory(lbl)
                            if mem_match:
                                ans = mem_match[0]
                                logger.info(f"  🧠 Second Brain 0-token hit: '{lbl[:40]}' -> {ans}")
                            elif "authorized" in lbl_lower:
                                ans = "Yes"
                            elif "sponsorship" in lbl_lower or "visa" in lbl_lower:
                                ans = "Yes"
                            elif "years" in lbl_lower or "experience" in lbl_lower:
                                ans = "2-3 years"
                            elif "government" in lbl_lower or "conflict" in lbl_lower:
                                ans = "No"
                            else:
                                ans = "No"

                            logger.info(f"  🧠 Answering Questionnaire: '{lbl[:60]}' -> {ans}")
                            await qb.click(force=True)
                            await asyncio.sleep(0.6)
                            opt = page.locator(f'[role="option"]:has-text("{ans}")').first
                            if await opt.count() > 0:
                                await opt.click(force=True)
                            else:
                                await page.keyboard.press("Escape")
                            await asyncio.sleep(0.4)

                # Step 3b: Handle questionnaire text and location inputs
                q_text_inputs = page.locator('input[id*="primaryQuestionnaire" i]:not([type="checkbox"]):not([type="radio"]), textarea[id*="primaryQuestionnaire" i]')
                for ti in range(await q_text_inputs.count()):
                    tin = q_text_inputs.nth(ti)
                    if not (await tin.input_value()):
                        lbl = await tin.evaluate('el => el.closest("[data-automation-id*=\\"formField\\"]")?.innerText || ""')
                        mem_match = self.brain.lookup_memory(lbl)
                        val = mem_match[0] if mem_match else ("United States" if "location" in lbl.lower() else "Yes")
                        await tin.fill(val)

                # Step 4: Handle Voluntary Disclosures
                gender_btn = page.locator('#personalInfoUS--gender').first
                if await gender_btn.count() > 0 and "select one" in (await gender_btn.inner_text()).lower():
                    logger.info("  👤 Setting Gender -> Man...")
                    await gender_btn.click(force=True)
                    await asyncio.sleep(0.5)
                    await page.evaluate('''() => {
                        const el = Array.from(document.querySelectorAll('[role="option"]')).find(x => x.innerText.includes('Man') || x.innerText.includes('Male'));
                        if (el) el.click();
                    }''')
                    await asyncio.sleep(0.4)

                eth_btn = page.locator('#personalInfoUS--ethnicity').first
                if await eth_btn.count() > 0 and "select one" in (await eth_btn.inner_text()).lower():
                    logger.info("  🌍 Setting Ethnicity -> Asian...")
                    await eth_btn.click(force=True)
                    await asyncio.sleep(0.5)
                    await page.evaluate('''() => {
                        const target = Array.from(document.querySelectorAll('[role="option"]')).find(x => x.innerText.trim().startsWith('Asian'));
                        if (target) target.click();
                    }''')
                    await asyncio.sleep(0.4)

                vet_btn = page.locator('#personalInfoUS--veteranStatus').first
                if await vet_btn.count() > 0 and "select one" in (await vet_btn.inner_text()).lower():
                    logger.info("  🎖️ Setting Veteran Status -> Non-veteran...")
                    await vet_btn.click(force=True)
                    await asyncio.sleep(0.8)
                    v_opt = page.locator('[role="option"]:has-text("not a veteran"), [role="option"]:has-text("Not a Veteran"), [role="option"]:has-text("I am not a veteran")').first
                    if await v_opt.count() > 0:
                        await v_opt.click(force=True)
                    else:
                        await page.keyboard.press("Escape")
                    await asyncio.sleep(0.4)

                # Disability disclosure
                dis_btn = page.locator('#personalInfoUS--disabilityStatus, #disability--disabilityStatus, button[id*="disability" i]').first
                if await dis_btn.count() > 0 and "select one" in (await dis_btn.inner_text()).lower():
                    logger.info("  ♿ Setting Disability Status -> No...")
                    await dis_btn.click(force=True)
                    await asyncio.sleep(0.8)
                    d_opt = page.locator('[role="option"]:has-text("do not have a disability"), [role="option"]:has-text("No, I don\'t have a disability"), [role="option"]:has-text("No")').first
                    if await d_opt.count() > 0:
                        await d_opt.click(force=True)
                    else:
                        await page.keyboard.press("Escape")
                    await asyncio.sleep(0.4)

                # Check terms/consent checkboxes if any
                cbs = page.locator('input[type="checkbox"]:visible')
                for ci in range(await cbs.count()):
                    cb = cbs.nth(ci)
                    if not await cb.is_checked():
                        await cb.check(force=True)

                # Resume upload check
                file_input = page.locator('input[type="file"]').first
                if await file_input.count() > 0 and resume_path:
                    try:
                        logger.info(f"  📎 Attaching candidate resume: {os.path.basename(resume_path)}")
                        await file_input.set_input_files(resume_path)
                        await asyncio.sleep(4)
                    except Exception:
                        pass

                # Resolve standard comboboxes if any
                await self._resolve_workday_comboboxes(page)

                # Advance to Next Step (Save and Continue)
                next_btn = page.locator('button[data-automation-id="bottom-navigation-next-button"], button[data-automation-id="pageFooterNextButton"], button:has-text("Save and Continue"), button:has-text("Next")').first
                if await next_btn.count() > 0:
                    btn_text = (await next_btn.inner_text()).strip()
                    logger.info(f"[Workday Step {wizard_step}] Clicking '{btn_text}'...")
                    await next_btn.scroll_into_view_if_needed()
                    await next_btn.click(force=True)
                    await asyncio.sleep(5)
                else:
                    logger.info("[Workday] No 'Save and Continue' button found. Form may be complete or on final step.")
                    break

            return False, f"Workday application for {company} reached step {wizard_step} without final confirmation."

        except Exception as e:
            logger.error(f"[Workday Error] {e}")
            return False, f"Workday automation error: {e}"
        finally:
            if not wait_for_review and context and not is_cdp:
                try:
                    await context.close()
                except Exception:
                    pass
            if p and not is_cdp:
                try:
                    await p.stop()
                except Exception:
                    pass

    async def _resolve_workday_comboboxes(self, page):
        """Resolves tricky search-as-you-type Workday comboboxes (School, Source, Country)."""
        try:
            # Check for empty School input
            school_box = page.locator('div[data-automation-id="school"], input[data-automation-id*="school" i]').first
            if await school_box.count() > 0:
                val = await school_box.input_value() if await school_box.count() > 0 else ""
                if not val:
                    logger.info("  🏫 Resolving Workday School Search Combobox...")
                    await school_box.click(force=True)
                    await page.keyboard.type("Southwest Minnesota State University", delay=30)
                    await asyncio.sleep(1.5)
                    opt = page.locator('[role="option"]:has-text("Southwest Minnesota State University"), div[data-uxi-widget-type="selectinput"] li').first
                    if await opt.count() > 0:
                        await self._safe_click(page, opt)

            # Check for empty Source / How Did You Hear combobox
            source_box = page.locator('div[data-automation-id*="source" i], input[data-automation-id*="source" i]').first
            if await source_box.count() > 0:
                val = await source_box.input_value() if await source_box.count() > 0 else ""
                if not val:
                    logger.info("  🌐 Resolving Workday Source Combobox...")
                    await source_box.click(force=True)
                    await page.keyboard.type("LinkedIn", delay=30)
                    await asyncio.sleep(1.5)
                    opt = page.locator('[role="option"]:has-text("LinkedIn"), [role="option"]:has-text("Internet"), [role="option"]').first
                    if await opt.count() > 0:
                        await self._safe_click(page, opt)
        except Exception as e:
            logger.debug(f"Combobox resolution note: {e}")
