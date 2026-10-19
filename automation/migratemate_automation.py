"""
Migrate Mate (migratemate.co) Visa Sponsorship Application Router.
Coordinates application submissions to verified visa-sponsoring employers,
ensuring F-1 CPT/OPT work authorization and future H-1B sponsorship fields are correctly answered.
"""

import os
import json
import logging
from typing import Dict, Any, Tuple
from automation.workday import WorkdayAutomation
from automation.direct_api import DirectAPISubmitter
from automation.real_browser_session import RealBrowserSessionManager
from core.matcher import load_profile

logger = logging.getLogger("jarvis.migratemate")


class MigrateMateAutomation:
    def __init__(self):
        self.profile = load_profile()
        self.workday = WorkdayAutomation()
        self.direct_api = DirectAPISubmitter()

    async def apply_to_job(self, job_url: str, ats_type: str = "OTHER") -> Tuple[bool, str]:
        """
        Dispatches application to appropriate employer ATS with verified visa sponsorship answers.
        """
        logger.info(f"[MigrateMate] Processing verified sponsorship application: {job_url} ({ats_type})")

        url_lower = job_url.lower()

        # Custom answers for international students (SMSU TRC Graduate Assistant)
        sponsorship_answers = {
            "work_authorization": "Yes",
            "sponsorship_required": "Yes",
            "visa_type": "F-1 (Eligible for CPT & 3-Year STEM OPT with future H-1B transition)",
            "start_availability": "Immediate / Summer 2026",
        }

        if "myworkdayjobs.com" in url_lower or ats_type == "WORKDAY":
            logger.info("[MigrateMate] Routing to Workday automation engine...")
            return await self.workday.fill_and_submit(job_url, self.profile, custom_answers=sponsorship_answers)

        elif "greenhouse.io" in url_lower or ats_type == "GREENHOUSE":
            logger.info("[MigrateMate] Routing to Greenhouse Direct API...")
            return self.direct_api.submit_greenhouse(job_url)

        elif "lever.co" in url_lower or ats_type == "LEVER":
            logger.info("[MigrateMate] Routing to Lever Direct API...")
            return self.direct_api.submit_lever(job_url)

        else:
            logger.info("[MigrateMate] Routing to Real Chrome Browser Session for live autofill...")
            res = await RealBrowserSessionManager.execute_real_session_fill(job_url, job_id=None)
            return res.get("success", False), res.get("message", "Processed via real browser session")
