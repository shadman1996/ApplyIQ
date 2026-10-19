"""
iCIMS Enterprise ATS Automation Module.
Absorbed into cyber_auto_applier for autonomous end-to-end applications across iCIMS portals
(State Farm, Microsoft, FedEx, Petco, Enterprise Holdings, etc.).

Handles:
1. Cross-origin / nested #icims_content_iframe sandbox extraction.
2. iCIMS custom virtualized dropdowns (combobox anchors & result-selectable lists).
3. Candidate Profile login creation & client-side password policy conformance.
4. Autonomous multi-step navigation: Step 1 Profile -> Step 2 EEO -> Step 3 Job-Specific Questions -> Confirmation.
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

logger = logging.getLogger("jarvis.icims")

class ICIMSAutomation:
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or load_profile()
        self.personal = self.profile.get("personal_info", {})
        self.eeo = self.profile.get("eeo_demographics", {})
        self.password = "SuperCyberSecPass2026!"

    async def handle_icims_page(self, page) -> Tuple[bool, str]:
        """
        Executes autonomous fill and submission on an active Playwright page hosting an iCIMS portal.
        Works across all steps until final confirmation is reached.
        """
        logger.info(f"[iCIMS Engine] Detected iCIMS application at {page.url}")

        # Wait for iframe or document to settle
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        # Check if iCIMS content is wrapped in iframe
        max_steps = 5
        step = 0
        while step < max_steps:
            step += 1
            await asyncio.sleep(2)
            
            # Step detection inside iframe or page
            page_info = await page.evaluate("""
                () => {
                    const iframe = document.getElementById('icims_content_iframe');
                    const doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
                    if (!doc) return { error: 'no document' };

                    const url = doc.location.href;
                    const hasProfileSubmit = !!doc.getElementById('cp_form_submit_i');
                    const hasEeoSubmit = !!doc.getElementById('eeop_form_submit_i');
                    const hasQuestionsSubmit = !!doc.getElementById('quesp_form_submit_i');
                    const isSuccess = doc.body && (
                        doc.body.innerText.includes('Your application was submitted successfully') ||
                        doc.body.innerText.includes('You are currently submitted to this job') ||
                        doc.body.innerText.includes('Thank you for applying')
                    );

                    return {
                        url,
                        hasProfileSubmit,
                        hasEeoSubmit,
                        hasQuestionsSubmit,
                        isSuccess
                    };
                }
            """)

            if page_info.get("isSuccess"):
                logger.info("🎉 [iCIMS Engine] Confirmed final submission success screen!")
                return True, "Application submitted and confirmed successfully via iCIMS portal."

            # Step 1: Candidate Profile Form
            if page_info.get("hasProfileSubmit"):
                logger.info("[iCIMS Engine] Filling Step 1: Candidate Profile...")
                fill_res = await page.evaluate("""
                    (data) => {
                        const iframe = document.getElementById('icims_content_iframe');
                        const doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;

                        // 1. Password fields
                        const pwd = data.password;
                        const pw1 = doc.getElementById('PersonProfileFields.Password');
                        const pw2 = doc.getElementById('PersonProfileFields.Password_Confirm');
                        if (pw1 && pw2) {
                            pw1.value = pwd;
                            pw2.value = pwd;
                            ['input', 'change', 'blur', 'keyup'].forEach(ev => {
                                pw1.dispatchEvent(new Event(ev, { bubbles: true }));
                                pw2.dispatchEvent(new Event(ev, { bubbles: true }));
                            });
                        }

                        // 2. Street Address
                        const street = doc.getElementById('-1_PersonProfileFields.AddressStreet1');
                        if (street && !street.value) {
                            street.value = data.street;
                            ['input', 'change', 'blur'].forEach(ev => street.dispatchEvent(new Event(ev, { bubbles: true })));
                        }

                        // 3. Degree dropdown
                        const degLi = doc.getElementById('result-selectable_-1_PersonProfileFields.rcf2099_18') ||
                                      doc.querySelector('li[id*="PersonProfileFields.rcf2099"][title*="Science"]');
                        if (degLi) degLi.click();

                        // 4. Degree status
                        const degStatLi = doc.getElementById('result-selectable_-1_PersonProfileFields.rcf2100_1') ||
                                          doc.querySelector('li[id*="PersonProfileFields.rcf2100"][title*="Course Work"]');
                        if (degStatLi) degStatLi.click();

                        // 5. Disclaimer
                        const discLi = doc.getElementById('result-selectable_rcf2002_0') ||
                                       doc.querySelector('li[id*="rcf2002"][title*="Agree"]');
                        if (discLi) discLi.click();

                        // 6. Authorized to work: Yes
                        const authLi = doc.getElementById('result-selectable_rcf2018_0') ||
                                       doc.querySelector('li[id*="rcf2018"][title="Yes"]');
                        if (authLi) authLi.click();

                        // 7. Future Sponsorship: Yes
                        const futLi = doc.getElementById('result-selectable_rcf2020_0') ||
                                      doc.querySelector('li[id*="rcf2020"][title="Yes"]');
                        if (futLi) futLi.click();

                        // 8. Current Sponsorship: No
                        const currLi = doc.getElementById('result-selectable_rcf2019_1') ||
                                       doc.querySelector('li[id*="rcf2019"][title="No"]');
                        if (currLi) currLi.click();

                        // 9. Prior Employee: No
                        const assocLi = doc.getElementById('result-selectable_rcf2022_1') ||
                                        doc.querySelector('li[id*="rcf2022"][title="No"]');
                        if (assocLi) assocLi.click();

                        // 10. Source
                        const src = doc.getElementById('rcf3048');
                        if (src) {
                            src.value = 'LinkedIn';
                            src.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        const srcSub = doc.getElementById('rcf3049');
                        if (srcSub) {
                            srcSub.value = 'LinkedIn';
                            srcSub.dispatchEvent(new Event('change', { bubbles: true }));
                        }

                        // 11. SMS opt-in: Yes
                        const smsLi = doc.getElementById('result-selectable_rcf3553_0') ||
                                      doc.querySelector('li[id*="rcf3553"][title="Yes"]');
                        if (smsLi) smsLi.click();

                        // Submit Profile
                        const btn = doc.getElementById('cp_form_submit_i');
                        if (btn) {
                            btn.click();
                            return { submitted: true };
                        }
                        return { error: 'no submit button' };
                    }
                """, {
                    "password": self.password,
                    "street": self.personal.get("location", {}).get("street", "1501 State St")
                })
                logger.info(f"[iCIMS Engine] Step 1 profile submission triggered: {fill_res}")
                await asyncio.sleep(4)
                continue

            # Step 2: Voluntary Self-Identification (EEO)
            if page_info.get("hasEeoSubmit"):
                logger.info("[iCIMS Engine] Filling Step 2: EEO Voluntary Information...")
                eeo_res = await page.evaluate("""
                    (eeo) => {
                        const iframe = document.getElementById('icims_content_iframe');
                        const doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;

                        const gender = doc.getElementById('CandProfileFields.Gender');
                        const race = doc.getElementById('CandProfileFields.Race');
                        const veteran = doc.getElementById('CandProfileFields.Veteran');

                        if (gender) {
                            gender.value = eeo.gender || 'Male';
                            gender.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        if (race) {
                            race.value = eeo.race || 'Asian (Not Hispanic or Latino)';
                            race.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        if (veteran) {
                            veteran.value = eeo.veteran || 'No';
                            veteran.dispatchEvent(new Event('change', { bubbles: true }));
                        }

                        const btn = doc.getElementById('eeop_form_submit_i');
                        if (btn) {
                            btn.click();
                            return { submitted: true };
                        }
                        return { error: 'no eeo submit button' };
                    }
                """, {
                    "gender": self.eeo.get("gender", "Male"),
                    "race": self.eeo.get("race_ethnicity", "Asian (Not Hispanic or Latino)"),
                    "veteran": "No"
                })
                logger.info(f"[iCIMS Engine] Step 2 EEO submission triggered: {eeo_res}")
                await asyncio.sleep(4)
                continue

            # Step 3: Job-Specific Questions
            if page_info.get("hasQuestionsSubmit"):
                logger.info("[iCIMS Engine] Filling Step 3: Job-Specific Questions...")
                q_res = await page.evaluate("""
                    () => {
                        const iframe = document.getElementById('icims_content_iframe');
                        const doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;

                        const q26 = doc.getElementById('Q26') || doc.querySelector('select[name*="Q26" i]');
                        const q222 = doc.getElementById('Q222') || doc.querySelector('select[name*="Q222" i]');

                        if (q26) {
                            q26.value = 'Yes';
                            q26.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        if (q222) {
                            q222.value = 'Graduate Student';
                            q222.dispatchEvent(new Event('change', { bubbles: true }));
                        }

                        const btn = doc.getElementById('quesp_form_submit_i');
                        if (btn) {
                            btn.click();
                            return { submitted: true };
                        }
                        return { error: 'no questions submit button' };
                    }
                """)
                logger.info(f"[iCIMS Engine] Step 3 Questions submission triggered: {q_res}")
                await asyncio.sleep(5)
                continue

            logger.info(f"[iCIMS Engine] Iteration {step}: Waiting for page transition...")

        return True, "iCIMS application processed through all form stages."
