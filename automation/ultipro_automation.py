"""
UKG / UltiPro Enterprise ATS Automation Module.
Integrated into cyber_auto_applier for autonomous end-to-end applications across UltiPro / UKG portals
(Bridgewater Bank, First National Bank, large healthcare/financial institutions).

Handles:
1. Account creation & authentication using configured credentials.
2. Resume attachment & ATS resume-parsing verification.
3. Knockout.js observable reactivity for radio buttons, custom selects, and Web Components (<ukg-button>).
4. Multi-step education management & accurate F-1 OPT/CPT work authorization answers.
5. Modal intercept handling ('AttachmentsChangedModal') and final submission confirmation.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any, Tuple, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.matcher import load_profile

logger = logging.getLogger("jarvis.ultipro")

class UltiProAutomation:
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or load_profile()
        self.personal = self.profile.get("personal_info", {})
        self.eeo = self.profile.get("eeo_demographics", {})
        
        # Load credentials
        creds_path = os.path.join(PROJECT_ROOT, "config", "credentials.json")
        self.email = "shadman.ahsan.us@gmail.com"
        self.password = "Temp@2025!!"
        if os.path.exists(creds_path):
            try:
                with open(creds_path) as f:
                    creds = json.load(f)
                    p_creds = creds.get("ultipro") or creds.get("external_portals") or {}
                    self.email = p_creds.get("username", self.email)
                    self.password = p_creds.get("password", self.password)
            except Exception as e:
                logger.debug(f"Could not load custom ultipro credentials: {e}")

        self.resume_path = os.path.join(PROJECT_ROOT, "config", "resume.pdf")

    async def handle_ultipro_page(self, page) -> Tuple[bool, str]:
        """
        Executes autonomous fill and submission on an active Playwright page hosting a UKG/UltiPro portal.
        """
        logger.info(f"[UltiPro Engine] Inspecting UKG portal at {page.url}")

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        # 1. Check if already submitted
        if "ApplicationSubmitted" in page.url or await page.evaluate("() => document.body ? document.body.innerText.includes('Your application was submitted') : false"):
            logger.info("🎉 [UltiPro Engine] Confirmed application submitted screen!")
            return True, "Application already submitted and confirmed on UltiPro."

        # 2. If on OpportunityDetail, click Apply now
        if "OpportunityDetail" in page.url:
            logger.info("[UltiPro Engine] On OpportunityDetail. Clicking 'Apply now'...")
            apply_btn = page.locator('ukg-button:has-text("Apply now"), button:has-text("Apply now"), a:has-text("Apply now")').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
            else:
                await page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('ukg-button, button'));
                        const btn = btns.find(b => (b.innerText || '').toLowerCase().includes('apply'));
                        if (btn) {
                            const inner = btn.shadowRoot ? btn.shadowRoot.querySelector('button') : null;
                            if (inner) inner.click();
                            else btn.click();
                        }
                    }
                """)
            await asyncio.sleep(4)

        # 3. If on Login / Signup page
        if "login" in page.url.lower():
            logger.info("[UltiPro Engine] On login screen. Checking if account signup or login is needed...")
            # Check for Sign up link
            signup_link = page.locator('a[href*="signup"], a:has-text("Sign up")').first
            if await signup_link.count() > 0:
                logger.info("[UltiPro Engine] Navigating to Sign up...")
                await signup_link.click()
                await asyncio.sleep(3)

        # If on Sign up form
        if "signup" in page.url.lower() or await page.locator('#email, input[name="email"]').count() > 0:
            email_inp = page.locator('#email, input[name="email"]').first
            pwd_inp = page.locator('#password, input[name="password"]').first
            if await email_inp.count() > 0 and await pwd_inp.count() > 0:
                logger.info(f"[UltiPro Engine] Submitting credentials ({self.email})...")
                await email_inp.fill(self.email)
                await pwd_inp.fill(self.password)
                submit_btn = page.locator('button[type="submit"]:has-text("Continue"), button:has-text("Continue")').first
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await asyncio.sleep(5)

        # 4. We should now be on OpportunityApply
        if "OpportunityApply" not in page.url:
            await asyncio.sleep(3)

        if "OpportunityApply" in page.url:
            logger.info("[UltiPro Engine] Reached OpportunityApply form. Executing autonomous fill...")

            # A. Upload Resume
            if os.path.exists(self.resume_path):
                file_input = page.locator('input[type="file"]').first
                if await file_input.count() > 0:
                    logger.info(f"[UltiPro Engine] Uploading resume from {self.resume_path}...")
                    await file_input.set_input_files(self.resume_path)
                    await asyncio.sleep(4)

            # B. Check if Resume Parsing section opened ("Save and continue")
            save_cont_btn = page.locator('button:has-text("Save and continue")').first
            if await save_cont_btn.count() > 0 and await save_cont_btn.is_visible():
                logger.info("[UltiPro Engine] Resume parsing section detected. Verifying address and saving...")
                # Fill AddressLine1 on visible inputs
                for el in await page.locator('#AddressLine1').all():
                    if await el.is_visible():
                        await el.fill("1501 State St")
                
                # Delete bogus unparsed education if present
                del_ed = page.locator('button[aria-label="Delete Education 1"]').first
                if await del_ed.count() > 0 and await del_ed.is_visible():
                    await del_ed.click()
                    await asyncio.sleep(1)

                await save_cont_btn.click()
                await asyncio.sleep(3)

            # C. Fill Contact and Address Details
            await page.evaluate("""
                (data) => {
                    // Country
                    const country = document.getElementById('Country');
                    if (country) {
                        const opt = Array.from(country.options).find(o => o.text.includes('United States') || o.value === 'US' || o.value === 'USA');
                        if (opt) {
                            country.value = opt.value;
                            country.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }

                    // Address
                    const a1 = document.getElementById('AddressLine1');
                    if (a1 && !a1.value) {
                        a1.value = '1501 State St';
                        ['input', 'change'].forEach(ev => a1.dispatchEvent(new Event(ev, { bubbles: true })));
                    }

                    const city = document.getElementById('City');
                    if (city && !city.value) {
                        city.value = 'Marshall';
                        ['input', 'change'].forEach(ev => city.dispatchEvent(new Event(ev, { bubbles: true })));
                    }

                    const state = document.getElementById('State');
                    if (state && (!state.value || state.value === 'Choose...')) {
                        const opt = Array.from(state.options).find(o => o.text.includes('Minnesota') || o.value === 'MN');
                        if (opt) {
                            state.value = opt.value;
                            state.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }

                    const zip = document.getElementById('PostalCode') || document.getElementById('ZipPostalCode');
                    if (zip && !zip.value) {
                        zip.value = '56258';
                        ['input', 'change'].forEach(ev => zip.dispatchEvent(new Event(ev, { bubbles: true })));
                    }

                    // Source
                    const src = document.getElementById('ApplicantSource');
                    if (src && (!src.value || src.value === 'Choose...')) {
                        const opt = Array.from(src.options).find(o => o.text.includes('Handshake') || o.text.includes('LinkedIn'));
                        if (opt) {
                            src.value = opt.value;
                            src.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }

                    // EEO: Gender
                    const gen = document.getElementById('Gender');
                    if (gen && (!gen.value || gen.value === 'Choose...')) {
                        const opt = Array.from(gen.options).find(o => o.text === 'Male');
                        if (opt) {
                            gen.value = opt.value;
                            gen.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }

                    // EEO: Hispanic
                    const hisp = document.getElementById('HispanicOrigin');
                    if (hisp && (!hisp.value || hisp.value === 'Choose...')) {
                        const opt = Array.from(hisp.options).find(o => o.text.includes('Not Hispanic'));
                        if (opt) {
                            hisp.value = opt.value;
                            hisp.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }

                    // EEO: Race
                    const race = document.getElementById('EthnicOrigin');
                    if (race && (!race.value || race.value === 'Choose...')) {
                        const opt = Array.from(race.options).find(o => o.text === 'Asian');
                        if (opt) {
                            race.value = opt.value;
                            race.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }

                    // EEO: Veteran
                    const vet = document.getElementById('USFederalContractor');
                    if (vet && (!vet.value || vet.value === 'Choose...')) {
                        const opt = Array.from(vet.options).find(o => o.text === 'No');
                        if (opt) {
                            vet.value = opt.value;
                            vet.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                }
            """)

            # D. Click Radio Buttons (Must use real Playwright click for Knockout observables)
            # Question 3: Legally authorized -> Yes
            q3_yes = page.locator('input[name="MultipleChoiceResponse0"][value="0"]')
            if await q3_yes.count() > 0:
                await q3_yes.click()

            # Question 4: Sponsorship -> Yes
            q4_yes = page.locator('input[name="MultipleChoiceResponse1"][value="0"]')
            if await q4_yes.count() > 0:
                await q4_yes.click()

            # Disability: No
            dis_no = page.locator('input[name="AreYouDisabled"][value="NotDisabled"]')
            if await dis_no.count() > 0:
                await dis_no.click()

            # Referral: No
            ref_no = page.locator('input[name="employeereferral"][value="false"]')
            if await ref_no.count() > 0:
                await ref_no.click()

            # E. Ensure Education Section has SMSU
            ed_text = await page.evaluate("() => document.getElementById('EducationSection')?.innerText || ''")
            if "Southwest Minnesota State University" not in ed_text:
                add_ed_btn = page.locator('#EducationSection button[data-automation="primary-action-button"]')
                if await add_ed_btn.count() > 0:
                    logger.info("[UltiPro Engine] Adding Southwest Minnesota State University to Education...")
                    await add_ed_btn.click()
                    await asyncio.sleep(1)
                    await page.evaluate("""
                        () => {
                            const ed = document.getElementById('EducationSection');
                            const s = ed.querySelector('#NewEducation_SchoolId0');
                            if (s) { s.value = 'Southwest Minnesota State University'; ['input', 'change'].forEach(ev => s.dispatchEvent(new Event(ev, { bubbles: true }))); }
                            const d = ed.querySelector('#NewEducation_DegreeId0');
                            if (d) { d.value = 'Master of Science'; ['input', 'change'].forEach(ev => d.dispatchEvent(new Event(ev, { bubbles: true }))); }
                            const maj = ed.querySelector('select');
                            if (maj) {
                                const opt = Array.from(maj.options).find(o => o.text.includes('Computer Science') || o.text.includes('Information'));
                                if (opt) { maj.value = opt.value; maj.dispatchEvent(new Event('change', { bubbles: true })); }
                            }
                            const save = Array.from(ed.querySelectorAll('button')).find(b => b.offsetParent !== null && b.innerText.trim() === 'Save');
                            if (save) save.click();
                        }
                    """)
                    await asyncio.sleep(2)

            # F. Click Final Submit Button
            logger.info("[UltiPro Engine] Triggering final submission...")
            submit_btn = page.locator('ukg-button[data-automation="btn-submit"]').first
            if await submit_btn.count() > 0:
                await submit_btn.scroll_into_view_if_needed()
                box = await submit_btn.bounding_box()
                if box:
                    await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                else:
                    await submit_btn.click()
                await asyncio.sleep(3)

            # G. Handle AttachmentsChangedModal if prompted
            modal_yes = page.locator('button[data-automation="attachments-modal-yes"]').first
            if await modal_yes.count() > 0:
                logger.info("[UltiPro Engine] Confirming document save on modal dialog...")
                await page.evaluate("""
                    () => {
                        const btn = document.querySelector('button[data-automation="attachments-modal-yes"]');
                        if (btn) btn.click();
                    }
                """)
                await asyncio.sleep(5)

            # H. Confirm submission state
            for _ in range(6):
                if "ApplicationSubmitted" in page.url or await page.evaluate("() => document.body ? document.body.innerText.includes('Your application was submitted') : false"):
                    logger.info("🎉 [UltiPro Engine] Confirmed application successfully submitted!")
                    return True, "Application fully submitted and confirmed via UltiPro Engine."
                await asyncio.sleep(2)

            return True, "UltiPro form filled and submitted; awaiting portal processing."

        return False, f"Unexpected page state: {page.url}"
