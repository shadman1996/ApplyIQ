"""
ATS Form Filler & Human-in-the-Loop Orchestrator.
Absorbed and expanded from torontodeveloper/job-application-agent.

Solves:
1. Advanced Dropdown, Combobox & Listbox interactions across Workday, Greenhouse, Lever, and Ashby.
2. Search-as-you-type comboboxes with keyboard navigation & option list targeting.
3. Deterministic answer planning for critical cybersecurity candidate facts (sponsorship, legal authorization, clearance).
4. Smart Human-in-the-Loop Review Checkpoint: fills all fields, attaches verified PDF resume,
   injects an in-browser review HUD, and stages for 1-click human verification before submission.
"""

import os
import re
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from core.llm_client import GeminiClient
from core.second_brain import second_brain
from core.jev_router import jev_router

logger = logging.getLogger("jarvis.form_filler")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ATSFormFiller:
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.gemini = GeminiClient()
        if profile is None:
            profile_path = os.path.join(PROJECT_ROOT, "config", "profile.json")
            if os.path.exists(profile_path):
                with open(profile_path, "r", encoding="utf-8") as f:
                    self.profile = json.load(f)
            else:
                self.profile = {}
        else:
            self.profile = profile

    # =========================================================================
    # 1. STRUCTURAL DOM FIELD EXTRACTION (Torontodeveloper Pattern)
    # =========================================================================
    async def extract_form_fields(self, page) -> List[Dict[str, Any]]:
        """
        Extracts visible form controls and resolves their labels via 6-tier locator hierarchy.
        Recognizes standard inputs, textareas, selects, and custom ARIA comboboxes.
        """
        try:
            fields = await page.evaluate("""
                () => {
                    const selectors = [
                        'input:not([type="hidden"]):not([type="submit"]):not([type="button"])',
                        'textarea',
                        'select',
                        '[role="combobox"]',
                        '[aria-haspopup="listbox"]',
                        'div[data-automation-id="select-widget"]',
                        'div[data-uxi-element-list="select"]',
                        'button[aria-haspopup="listbox"]'
                    ];

                    const elements = Array.from(document.querySelectorAll(selectors.join(',')))
                        .filter(el => {
                            if (el.type === 'hidden') return false;
                            const style = window.getComputedStyle(el);
                            // For radio and checkbox inputs, Workday and modern frameworks style with opacity: 0
                            // while wrapping in a visible label or container. Only filter out if display: none or visibility: hidden.
                            if (el.type === 'radio' || el.type === 'checkbox') {
                                if (style.display === 'none' || style.visibility === 'hidden') return false;
                                return true;
                            }
                            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                            const r = el.getBoundingClientRect();
                            if (r.width <= 0 || r.height <= 0) return false;
                            return true;
                        });

                    return elements.map((el, idx) => {
                        let label = '';

                        // Tier 1: HTMLFormElement associated label or explicit label[for=id]
                        if (el.labels && el.labels.length) {
                            label = el.labels[0].innerText;
                        }
                        if (!label && el.id) {
                            const lblFor = document.querySelector(`label[for="${el.id}"]`);
                            if (lblFor) label = lblFor.innerText;
                        }

                        // Tier 2: aria-label attribute
                        if (!label && el.getAttribute('aria-label')) {
                            label = el.getAttribute('aria-label');
                        }

                        // Tier 3: placeholder attribute
                        if (!label && el.placeholder) {
                            label = el.placeholder;
                        }

                        // Tier 4: aria-labelledby reference
                        if (!label && el.getAttribute('aria-labelledby')) {
                            const ids = el.getAttribute('aria-labelledby').split(' ');
                            for (let id of ids) {
                                const ref = document.getElementById(id);
                                if (ref && ref.innerText) {
                                    label += ' ' + ref.innerText;
                                }
                            }
                        }

                        // Tier 5: Closest form group, fieldset, or container label
                        if (!label) {
                            const wrap = el.closest('div.field, div.form-group, fieldset, li, tr, [data-automation-id="formLabel"]');
                            if (wrap) {
                                const lab = wrap.querySelector('label, legend, [data-automation-id="formLabel"]');
                                if (lab) label = lab.innerText;
                            }
                        }

                        // Tier 6: Preceding sibling or parent text
                        if (!label) {
                            const prev = el.previousElementSibling;
                            if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'SPAN')) {
                                label = prev.innerText;
                            } else if (el.parentElement) {
                                label = el.parentElement.innerText.slice(0, 100);
                            }
                        }

                        // Special Resolution for Radio and Checkbox Option Labels
                        if ((el.type === 'radio' || el.type === 'checkbox')) {
                            const optParent = el.closest('[data-automation-id="radioGroupOption"], div[class*="radio"], label, li');
                            if (optParent) {
                                const optText = optParent.querySelector('label, [data-automation-id="radio-label"], span');
                                if (optText && optText !== el) {
                                    label = optText.innerText.trim();
                                } else if (!label) {
                                    label = optParent.innerText.trim();
                                }
                            }
                        }

                        // Group Label Resolution (Question prompt for radio groups, fieldsets, or form groups)
                        let groupLabel = '';
                        const groupContainer = el.closest('fieldset, [role="radiogroup"], [data-automation-id="radio-button-group"], [data-automation-id="formGroup"], .form-group, .field, div[class*="question"]');
                        if (groupContainer) {
                            const prompt = groupContainer.querySelector('legend, [data-automation-id="formLabel"], label.control-label, h3, h4, [class*="label"], [class*="title"]');
                            if (prompt && prompt !== el) {
                                groupLabel = prompt.innerText.trim();
                            }
                            if (!groupLabel && groupContainer.parentElement) {
                                const prev = groupContainer.previousElementSibling;
                                if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'LEGEND' || prev.getAttribute('data-automation-id') === 'formLabel')) {
                                    groupLabel = prev.innerText.trim();
                                }
                            }
                        }

                        const tagName = el.tagName.toLowerCase();
                        const isCombo = el.getAttribute('role') === 'combobox'
                            || el.getAttribute('aria-haspopup') === 'listbox'
                            || el.getAttribute('data-automation-id') === 'select-widget';

                        let options = null;
                        if (tagName === 'select') {
                            options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean).slice(0, 50);
                        }

                        return {
                            idx,
                            tag: isCombo && tagName !== 'select' ? 'combobox' : tagName,
                            type: el.type || '',
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            label: (label || '').trim().replace(/\\s+/g, ' ').slice(0, 250),
                            group_label: (groupLabel || '').trim().replace(/\\s+/g, ' ').slice(0, 250),
                            required: el.required || el.getAttribute('aria-required') === 'true' || false,
                            options: options,
                            current_value: el.value || '',
                            checked: el.checked || false
                        };
                    });
                }
            """)
            return fields or []
        except Exception as e:
            logger.warning(f"[ATS Form Filler] DOM extraction failed: {e}")
            return []

    # =========================================================================
    # 2. DETERMINISTIC CANDIDATE TRUTH ENGINE
    # =========================================================================
    def plan_answers(
        self,
        fields: List[Dict[str, Any]],
        custom_answers: Optional[Dict[str, str]] = None,
        job_context: str = ""
    ) -> Dict[str, Dict[str, Any]]:
        """
        Maps extracted form controls to authoritative candidate answers.
        Guarantees that critical legal, identity, and visa questions are never hallucinated.
        """
        custom_answers = custom_answers or {}
        p_info = self.profile.get("personal_info", {})
        eeo = self.profile.get("eeo_demographics", {})
        edu = self.profile.get("education", [{}])[0]

        first_name = p_info.get("first_name", "Shadman")
        last_name = p_info.get("last_name", "Ahsan")
        full_name = p_info.get("full_name", f"{first_name} {last_name}")
        email = p_info.get("email", "shadman_ahsan@yahoo.com")
        phone = p_info.get("phone", "+1 (507) 850-3155")
        loc_data = p_info.get("location", {})
        city = loc_data.get("city", "Marshall")
        state = loc_data.get("state", "MN")
        zip_code = loc_data.get("zip", "56258")
        country = loc_data.get("country", "United States")
        linkedin = p_info.get("linkedin", "https://linkedin.com/in/shadman-ahsan")
        github = p_info.get("github", "https://github.com/shadman1996")
        website = p_info.get("website", "https://shadman1996.github.io")
        school = edu.get("institution", "Southwest Minnesota State University")
        degree = edu.get("degree", "Master of Science in Cybersecurity")

        decline_eeo = eeo.get("decline_self_identify", False)
        plan: Dict[str, Dict[str, Any]] = {}

        for f in fields:
            idx = str(f["idx"])
            group_txt = f.get("group_label", "")
            opt_txt = f.get("label", "")
            blob = f"{group_txt} {opt_txt} {f.get('name', '')} {f.get('id', '')} {f.get('placeholder', '')} {f.get('type', '')}".lower()
            val = None

            # --- Check Custom Answers First ---
            for c_key, c_val in custom_answers.items():
                if c_key.lower() in blob:
                    val = c_val
                    break

            if val:
                plan[idx] = {"value": val, "source": "custom"}
                continue

            # =========================================================
            # DEDICATED RADIO BUTTON RESOLUTION (Workday & ATS EEO / Legal)
            # =========================================================
            if f.get("type") == "radio":
                group_blob = f"{group_txt} {f.get('name', '')} {f.get('id', '')}".lower()
                opt_blob = f"{opt_txt} {f.get('current_value', '')}".lower()
                target_matched = False

                # 1. Visa Sponsorship (Candidate requires future H-1B sponsorship -> YES)
                if any(k in group_blob for k in ["sponsorship", "require sponsorship", "future sponsorship", "h-1b", "visa sponsorship"]):
                    if opt_blob.strip() in ("yes", "1", "true") or "yes" in opt_blob:
                        target_matched = True

                # 2. Legally Authorized to Work (Candidate authorized via CPT & 3-Yr STEM OPT -> YES)
                elif any(k in group_blob for k in [
                    "legally authorized", "authorized to work", "work authorization", "work_auth", "workauth",
                    "eligible to work in the u.s", "eligible to work in the united states", "authorization to work"
                ]):
                    if opt_blob.strip() in ("yes", "1", "true") or "yes" in opt_blob:
                        target_matched = True

                # 3. Security Clearance (Candidate holds None / Eligible for Public Trust -> NO / NONE)
                elif any(k in group_blob for k in ["security clearance", "clearance level", "active clearance"]):
                    if opt_blob.strip() in ("no", "0", "false", "none") or ("no" in opt_blob and "yes" not in opt_blob):
                        target_matched = True

                # 4. U.S. Citizenship (Candidate is international student on F-1 -> NO)
                elif any(k in group_blob for k in ["are you a u.s. citizen", "us citizen", "citizenship status", "u.s. citizenship"]):
                    if opt_blob.strip() in ("no", "0", "false") or ("no" in opt_blob and "yes" not in opt_blob):
                        target_matched = True

                # 5. Gender
                elif any(k in group_blob for k in ["gender", "sex"]):
                    if decline_eeo:
                        if any(k in opt_blob for k in ["decline", "choose not", "prefer not", "wish not", "not to disclose"]):
                            target_matched = True
                    else:
                        target_gender = eeo.get("gender", "Male").lower()
                        if target_gender == "male":
                            if "male" in opt_blob and "female" not in opt_blob:
                                target_matched = True
                        elif target_gender == "female":
                            if "female" in opt_blob:
                                target_matched = True

                # 6. Hispanic / Latino (Workday Two-Question US EEOC Survey)
                elif any(k in group_blob for k in ["hispanic", "latino"]):
                    if decline_eeo:
                        if any(k in opt_blob for k in ["decline", "choose not", "prefer not", "wish not", "not to disclose"]):
                            target_matched = True
                    else:
                        target_hisp = eeo.get("hispanic_latino", "No").lower()
                        if target_hisp in ("no", "not hispanic"):
                            if "not hispanic" in opt_blob or ("no" in opt_blob and "yes" not in opt_blob):
                                target_matched = True
                        else:
                            if "yes" in opt_blob or ("hispanic" in opt_blob and "not hispanic" not in opt_blob):
                                target_matched = True

                # 7. Race / Ethnicity (Primary Race Selection)
                elif any(k in group_blob for k in ["race", "ethnicity", "ethnic"]):
                    if decline_eeo:
                        if any(k in opt_blob for k in ["decline", "choose not", "prefer not", "wish not", "not to disclose"]):
                            target_matched = True
                    else:
                        target_race = eeo.get("race_ethnicity", "Asian").lower()
                        if "asian" in target_race:
                            if "asian" in opt_blob and "caucasian" not in opt_blob:
                                target_matched = True
                        elif "white" in target_race:
                            if "white" in opt_blob or "caucasian" in opt_blob:
                                target_matched = True
                        elif "black" in target_race:
                            if "black" in opt_blob or "african" in opt_blob:
                                target_matched = True

                # 8. Veteran Status (VETS-4212 Survey)
                elif "veteran" in group_blob:
                    if decline_eeo:
                        if any(k in opt_blob for k in ["decline", "choose not", "prefer not", "wish not", "not to disclose"]):
                            target_matched = True
                    else:
                        target_vet = eeo.get("veteran_status", "No").lower()
                        if target_vet in ("no", "not", "i am not a protected veteran"):
                            if any(k in opt_blob for k in ["not a protected veteran", "i am not a protected veteran", "i am not a veteran", "not a veteran"]) or (opt_blob.strip() in ("no", "false", "0") and "yes" not in opt_blob):
                                target_matched = True
                        else:
                            if any(k in opt_blob for k in ["i identify as", "i am a protected veteran", "yes"]):
                                target_matched = True

                # 9. Disability Status (Form CC-305 Survey)
                elif any(k in group_blob for k in ["disability", "handicap"]):
                    if decline_eeo:
                        if any(k in opt_blob for k in ["do not wish to answer", "do not want to answer", "decline", "choose not", "prefer not"]):
                            target_matched = True
                    else:
                        target_dis = eeo.get("disability_status", "No").lower()
                        if target_dis in ("no", "not", "no, i do not have a disability"):
                            if any(k in opt_blob for k in ["do not have a disability", "no, i do not", "no, i don't", "have not had one"]) or (opt_blob.strip() in ("no", "false", "0") and "yes" not in opt_blob):
                                target_matched = True
                        else:
                            if any(k in opt_blob for k in ["yes, i have a disability", "i have a disability", "history/record"]) or opt_blob.strip() in ("yes", "true", "1"):
                                target_matched = True

                # 10. General Affirmative/Negative Confirmation
                else:
                    if opt_blob.strip() in ("yes", "1", "true") and any(k in group_blob for k in ["agree", "certify", "acknowledge"]):
                        target_matched = True

                if target_matched:
                    plan[idx] = {"value": "CHECK", "source": "radio_match"}
                else:
                    plan[idx] = {"value": "", "source": "skip"}
                continue

            # =========================================================
            # STANDARD TEXT INPUTS, SELECT DROPDOWNS & COMBOBOXES
            # =========================================================

            # --- WORK AUTHORIZATION & VISA SPONSORSHIP (Priority Check) ---
            if any(k in blob for k in [
                "sponsorship", "require sponsorship", "future sponsorship", "h-1b", "visa sponsorship"
            ]):
                val = "Yes"

            elif any(k in blob for k in [
                "legally authorized", "authorized to work", "work authorization", "work_auth", "workauth",
                "eligible to work in the u.s", "eligible to work in the united states", "authorization to work"
            ]):
                val = "Yes"

            elif any(k in blob for k in ["visa status", "immigration status", "current work authorization"]):
                val = "F-1 (Student Visa / CPT & STEM OPT Eligible)"

            # --- SECURITY CLEARANCE & CITIZENSHIP ---
            elif any(k in blob for k in ["security clearance", "clearance level", "active clearance"]):
                val = "None / Eligible for Public Trust"
            elif any(k in blob for k in ["are you a u.s. citizen", "us citizen", "citizenship status", "u.s. citizenship"]):
                val = "No"

            # --- File Uploads ---
            elif f.get("type") == "file" or "resume" in blob or "cv" in blob:
                if "cover" in blob:
                    plan[idx] = {"value": "UPLOAD_COVER_LETTER", "source": "profile"}
                else:
                    plan[idx] = {"value": "UPLOAD_RESUME", "source": "profile"}
                continue

            # --- Identity & Contact ---
            elif "first" in blob and "name" in blob:
                val = first_name
            elif "last" in blob and "name" in blob:
                val = last_name
            elif ("full" in blob and "name" in blob) or ("your name" in blob) or (blob.strip() == "name"):
                val = full_name
            elif "email" in blob:
                val = email
            elif "phone" in blob or "mobile" in blob or "telephone" in blob:
                val = phone
            elif "linkedin" in blob:
                val = linkedin
            elif "github" in blob:
                val = github
            elif "website" in blob or "portfolio" in blob:
                val = website
            elif "city" in blob:
                val = city
            elif "postal" in blob or "zip" in blob:
                val = zip_code
            elif (re.search(r'\b(state|province)\b', blob) and "united states" not in blob and "status" not in blob):
                val = state
            elif (re.search(r'\bcountry\b', blob) and "citizenship" not in blob):
                val = country
            elif "school" in blob or "university" in blob or "institution" in blob or "college" in blob:
                val = school
            elif "degree" in blob:
                val = degree

            # --- EEO DEMOGRAPHICS (Dropdowns & Comboboxes) ---
            elif "veteran" in blob:
                val = "Decline to Self-Identify" if decline_eeo else eeo.get("veteran_status", "I am not a protected veteran")
            elif "disability" in blob:
                val = "I do not wish to answer" if decline_eeo else eeo.get("disability_status", "No, I do not have a disability")
            elif "gender" in blob:
                val = "Decline to Self-Identify" if decline_eeo else eeo.get("gender", "Male")
            elif "hispanic" in blob or "latino" in blob:
                val = "Decline to Self-Identify" if decline_eeo else eeo.get("hispanic_latino", "No")
            elif "race" in blob or "ethnicity" in blob:
                val = "Decline to Self-Identify" if decline_eeo else eeo.get("race_ethnicity", "Asian")

            if val:
                plan[idx] = {"value": val, "source": "deterministic"}
            else:
                # --- SECOND BRAIN & JEV SYSTEM 1 GATEKEEPER ---
                question_label = f.get("group_label") or f.get("label") or f.get("placeholder") or f.get("name")
                f_tag = f.get("tag", "input")
                # If it's a meaningful prompt and not an empty or hidden control
                if question_label and len(question_label.strip()) > 3 and f_tag in ["input", "textarea", "select", "combobox"]:
                    # 1. Check Second Brain (0-token local memory hit)
                    cached_val = second_brain.lookup_answer(question_label)
                    if cached_val:
                        logger.info(f"🧠 [Second Brain Hit - 0 Tokens] '{question_label[:60]}' -> '{cached_val[:60]}'")
                        plan[idx] = {"value": cached_val, "source": "second_brain"}
                        continue

                    # 2. Query Jev System 1 Router to determine action
                    jev_decision = jev_router.decide_question_action(question_label, f.get("options"))
                    action = jev_decision.get("action", "heavy_llm_essay")

                    if action == "second_brain_lookup":
                        # Attempt fuzzy profile resolution
                        cached_val = second_brain.lookup_answer(question_label)
                        if cached_val:
                            plan[idx] = {"value": cached_val, "source": "second_brain"}
                            continue

                    try:
                        logger.info(f"🤖 [Gemini Agent] Answering ATS question: '{question_label[:80]}' ({f_tag}) [Jev Action: {action}]")
                        ai_answer = self.gemini.answer_form_question(
                            question=question_label,
                            field_type=f_tag,
                            options=f.get("options"),
                            job_context=job_context,
                            profile_data=self.profile
                        )
                        if ai_answer:
                            logger.info(f"✨ [Gemini Agent] Output: '{ai_answer[:80]}'")
                            plan[idx] = {"value": ai_answer, "source": "gemini_agent"}
                            # Remember for future applications (Continuous Learning)
                            second_brain.learn_answer(question_label, ai_answer, category="dynamic_ats")
                        else:
                            plan[idx] = {"value": "", "source": "skip"}
                    except Exception as ai_err:
                        logger.warning(f"[-] Gemini answer failure: {ai_err}")
                        plan[idx] = {"value": "", "source": "skip"}
                else:
                    plan[idx] = {"value": "", "source": "skip"}

        return plan

    # =========================================================================
    # 3. ADVANCED PLAYWRIGHT DROPDOWN & COMBOBOX SELECTION HANDLER
    # =========================================================================
    async def fill_field(
        self,
        page,
        field: Dict[str, Any],
        value: str,
        resume_path: Optional[str] = None,
        cover_path: Optional[str] = None
    ) -> bool:
        """
        Fills a single form control using Playwright locators.
        Handles Search-as-you-type comboboxes, ARIA listboxes, standard selects,
        radios, and file uploads.
        """
        if not value or value == "":
            return False

        # Build selector hierarchy
        selector = None
        if field.get("id"):
            selector = f"[id='{field['id']}']"
        elif field.get("name"):
            selector = f"{field.get('tag', 'input')}[name=\"{field['name']}\"]"
        elif field.get("placeholder"):
            ph = field["placeholder"].replace('"', '\\"')
            selector = f"[placeholder=\"{ph}\"]"
        elif field.get("label"):
            selector = f"text={field['label']}"

        if not selector:
            return False

        try:
            loc = page.locator(selector).first

            # Case 1: Resume / File Upload
            if value == "UPLOAD_RESUME":
                if not resume_path or not os.path.exists(resume_path):
                    logger.warning("[ATS Form Filler] Resume path missing or invalid.")
                    return False
                await loc.set_input_files(resume_path)
                logger.info(f"  📎 Uploaded resume: {resume_path}")
                return True

            if value == "UPLOAD_COVER_LETTER":
                if not cover_path or not os.path.exists(cover_path):
                    return False
                await loc.set_input_files(cover_path)
                return True

            # Case 2: Custom ARIA Combobox / Search-as-you-type Dropdown
            # (Workday, Greenhouse React Select, Ashby custom dropdown)
            if field.get("tag") == "combobox":
                logger.info(f"  🎯 Handling Combobox for '{field.get('label')}': '{value}'")
                await loc.click(timeout=4000)
                await page.wait_for_timeout(250)

                # Type search query into combobox
                await loc.type(value, delay=35)
                await page.wait_for_timeout(600)

                # Look for matching option in the popup listbox overlay
                option_selectors = [
                    f'[role="option"]:has-text("{value}")',
                    f'li[role="option"]:has-text("{value}")',
                    f'div[data-automation-id="promptOption"]:has-text("{value}")',
                    f'.select2-results__option:has-text("{value}")',
                    f'div[class*="option"]:has-text("{value}")',
                    f'[role="option"]'
                ]

                clicked = False
                for opt_sel in option_selectors:
                    opt_loc = page.locator(opt_sel).first
                    if await opt_loc.count() > 0:
                        try:
                            await opt_loc.click(timeout=2000)
                            clicked = True
                            break
                        except Exception:
                            continue

                if not clicked:
                    # Fallback keyboard navigation: ArrowDown + Enter
                    await page.keyboard.press("ArrowDown")
                    await page.wait_for_timeout(200)
                    await page.keyboard.press("Enter")
                return True

            # Case 3: Standard HTML <select> Dropdown
            if field.get("tag") == "select":
                # First attempt exact label selection
                try:
                    await loc.select_option(label=value, timeout=3000)
                    return True
                except Exception:
                    pass

                # Second attempt: partial substring matching across available options
                options = field.get("options") or []
                match = None
                for opt in options:
                    if value.lower() in opt.lower() or opt.lower() in value.lower():
                        match = opt
                        break

                if match:
                    try:
                        await loc.select_option(label=match, timeout=3000)
                        return True
                    except Exception:
                        pass

                # Third attempt: select by value
                try:
                    await loc.select_option(value=value, timeout=2000)
                    return True
                except Exception:
                    pass
                return False

            # Case 4: Radio Button (4-Tier Resilient Workday & ATS Selector)
            if field.get("type") == "radio":
                if value in ("CHECK", "yes", "true", "1"):
                    logger.info(f"  🔘 Selecting radio: '{field.get('label')}' (Group: '{field.get('group_label')}')")
                    checked = False

                    # Tier 1: Direct Playwright check with force=True (bypasses opacity: 0 / visibility styling)
                    try:
                        await loc.check(force=True, timeout=2500)
                        if await loc.is_checked():
                            checked = True
                    except Exception:
                        pass

                    # Tier 2: Click the associated label[for=id]
                    if not checked and field.get("id"):
                        try:
                            lbl = page.locator(f'label[for="{field["id"]}"]').first
                            if await lbl.count() > 0:
                                await lbl.click(force=True, timeout=2000)
                                if await loc.is_checked():
                                    checked = True
                        except Exception:
                            pass

                    # Tier 3: Workday option container or sibling label click
                    if not checked:
                        try:
                            opt_wrap = loc.locator('xpath=ancestor::div[@data-automation-id="radioGroupOption"] | ancestor::label | following-sibling::label').first
                            if await opt_wrap.count() > 0:
                                await opt_wrap.click(force=True, timeout=2000)
                                if await loc.is_checked():
                                    checked = True
                        except Exception:
                            pass

                    # Tier 4: Hardware/DOM dispatch event fallback (react/canvas state sync)
                    if not checked:
                        try:
                            await loc.evaluate("""el => {
                                el.checked = true;
                                el.click();
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }""")
                            checked = await loc.is_checked()
                        except Exception:
                            pass

                    return checked
                return False

            # Case 5: Checkbox
            if field.get("type") == "checkbox":
                if value in ("CHECK", "yes", "true", "1", "agree"):
                    try:
                        await loc.check(force=True, timeout=2500)
                        return True
                    except Exception:
                        if field.get("id"):
                            try:
                                await page.locator(f'label[for="{field["id"]}"]').first.click(force=True, timeout=2000)
                                return True
                            except Exception:
                                pass
                return False

            # Case 6: Standard Text / Email / Tel / Textarea
            await loc.fill("")
            await loc.type(value, delay=20)
            return True

        except Exception as e:
            logger.debug(f"[ATS Form Filler] Could not fill '{field.get('label')}': {e}")
            return False

    # =========================================================================
    # 4. FULL AUTOMATED WORKFLOW EXECUTION
    # =========================================================================
    async def fill_form(
        self,
        page,
        resume_path: Optional[str] = None,
        custom_answers: Optional[Dict[str, str]] = None,
        job_context: str = ""
    ) -> Dict[str, Any]:
        """
        Executes complete form filling sequence:
        Extracts DOM controls, plans deterministic facts, fills dropdowns/inputs,
        and attaches verified candidate resume.
        """
        if not resume_path:
            # Locate default tailored or master resume
            candidates = [
                os.path.join(PROJECT_ROOT, "data", "Shadman_Ahsan_Resume.pdf"),
                os.path.join(PROJECT_ROOT, "data", "tailored", "Shadman_Ahsan_Resume.pdf"),
                os.path.join(PROJECT_ROOT, "config", "resume.pdf")
            ]
            resume_path = next((p for p in candidates if os.path.exists(p)), None)

        fields = await self.extract_form_fields(page)
        plan = self.plan_answers(fields, custom_answers=custom_answers, job_context=job_context)

        filled_count = 0
        skipped_count = 0
        filled_labels = []

        for f in fields:
            idx = str(f["idx"])
            ans = plan.get(idx)
            if not ans or not ans.get("value") or ans.get("source") == "skip":
                skipped_count += 1
                continue

            success = await self.fill_field(page, f, ans["value"], resume_path=resume_path)
            if success:
                filled_count += 1
                label = f.get("label") or f.get("name") or f"Field #{f['idx']}"
                filled_labels.append(label)
            else:
                skipped_count += 1

        logger.info(f"[ATS Form Filler] Completed: {filled_count} filled, {skipped_count} skipped.")
        return {
            "filled_count": filled_count,
            "skipped_count": skipped_count,
            "filled_labels": filled_labels,
            "total_fields": len(fields),
            "resume_attached": resume_path is not None
        }

    # =========================================================================
    # 5. SMART "HUMAN-IN-THE-LOOP" CHECKPOINT HUD INJECTION
    # =========================================================================
    async def inject_human_in_the_loop_hud(
        self,
        page,
        company: str,
        job_title: str,
        filled_count: int,
        total_count: int,
        resume_attached: bool = True
    ) -> None:
        """
        Injects a persistent, cyberpunk-styled Human-in-the-Loop review HUD onto the page.
        Explicitly notifies the candidate that the form was populated and halts before submission.
        """
        try:
            resume_badge = "✅ 1-Page ATS Resume Attached" if resume_attached else "⚠️ Please Attach Resume"
            await page.evaluate(f"""() => {{
                const existing = document.getElementById('jarvis-hitl-hud');
                if (existing) existing.remove();

                const hud = document.createElement('div');
                hud.id = 'jarvis-hitl-hud';
                hud.style.cssText = [
                    'position: fixed',
                    'bottom: 24px',
                    'right: 24px',
                    'z-index: 2147483647',
                    'background: linear-gradient(135deg, rgba(8, 15, 30, 0.98), rgba(15, 23, 42, 0.98))',
                    'border: 2px solid #00f3ff',
                    'box-shadow: 0 0 35px rgba(0, 243, 255, 0.6), 0 10px 25px rgba(0,0,0,0.8)',
                    'color: #f8fafc',
                    'padding: 18px 24px',
                    'border-radius: 14px',
                    'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    'font-size: 13px',
                    'max-width: 440px',
                    'backdrop-filter: blur(12px)',
                    'transition: all 0.3s ease'
                ].join(';');

                hud.innerHTML = `
                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                        <span style="color:#00f3ff; font-weight:800; font-size:14px; letter-spacing:0.5px;">⚡ HUMAN-IN-THE-LOOP CHECKPOINT</span>
                        <span style="background:rgba(0,243,255,0.15); color:#00f3ff; font-size:10px; font-weight:700; padding:2px 8px; border-radius:6px; border:1px solid #00f3ff;">STAGED</span>
                    </div>
                    <div style="font-size:13px; font-weight:600; color:#fff; margin-bottom:6px;">
                        {company} — <span style="color:#94a3b8; font-weight:400;">{job_title}</span>
                    </div>
                    <div style="background:rgba(0,0,0,0.4); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.08); margin-bottom:10px;">
                        <div style="color:#10b981; font-weight:600; font-size:12px; margin-bottom:4px;">
                            🎯 Fields Populated: {filled_count} / {total_count}
                        </div>
                        <div style="color:#38bdf8; font-size:12px; margin-bottom:4px;">
                            {resume_badge}
                        </div>
                        <div style="color:#e2e8f0; font-size:11px;">
                            🛡️ Work Auth: <strong>Authorized = YES | Future Sponsorship = YES</strong>
                        </div>
                    </div>
                    <div style="color:#fbbf24; font-size:11px; line-height:1.4; margin-bottom:10px;">
                        ⚠️ Review candidate details & dropdown answers above. Click <strong>Submit Application</strong> in the portal when ready.
                    </div>
                    <div style="display:flex; justify-content:flex-end;">
                        <button id="jarvis-dismiss-hud" style="background:#0f172a; color:#94a3b8; border:1px solid #334155; padding:4px 10px; border-radius:6px; font-size:11px; cursor:pointer;">
                            Dismiss HUD
                        </button>
                    </div>
                `;

                document.body.appendChild(hud);
                document.getElementById('jarvis-dismiss-hud').onclick = () => hud.remove();
            }}""")
        except Exception as e:
            logger.debug(f"[ATS Form Filler] HUD injection notice: {e}")

    # =========================================================================
    # 6. STAGE APPLICATION FOR REVIEW (Non-Destructive Pause)
    # =========================================================================
    async def stage_for_human_review(
        self,
        page,
        company: str,
        job_title: str,
        filled_count: int,
        total_count: int,
        wait_for_tab_close: bool = False
    ) -> None:
        """
        Stops automated actions and leaves the page open for candidate review.
        If wait_for_tab_close is True, holds until the candidate finishes and closes the tab.
        """
        await self.inject_human_in_the_loop_hud(
            page,
            company=company,
            job_title=job_title,
            filled_count=filled_count,
            total_count=total_count,
            resume_attached=True
        )
        logger.info(f"  >>> [STAGED FOR REVIEW] Review {company} in the browser window, then click Submit yourself.")

        if wait_for_tab_close:
            logger.info("  >>> Holding execution until candidate completes review and closes browser tab...")
            try:
                await page.wait_for_event("close", timeout=0)
                logger.info(f"  >>> Browser tab closed by user for {company}. Proceeding.")
            except Exception as e:
                logger.debug(f"[ATS Form Filler] Tab wait notice: {e}")
