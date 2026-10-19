import os
import asyncio
import logging
import json
import time
import random
from typing import List, Dict, Any

from core.db import init_db, save_job, get_jobs_by_status, update_job_evaluation, log_application
from core.matcher import JobMatcher
from scrapers.github_internships import scrape_github_internships
from automation.direct_api import DirectAPISubmitter
from automation.workday import WorkdayAutomation
from scrapers.google_jobs import scrape_google_jobs
from scrapers.workday_direct import scrape_workday_employers
from scrapers.multi_board_scraper import scrape_multi_board_jobs
from scrapers.migratemate_scraper import scrape_migratemate_jobs
from scrapers.handshake_scraper import scrape_handshake_jobs
from automation.linkedin_automation import LinkedInAutomation
from automation.indeed_automation import IndeedAutomation
from automation.handshake_automation import HandshakeAutomation
from automation.migratemate_automation import MigrateMateAutomation
from core.hygiene import run_full_hygiene_cycle, get_disk_footprint_report
from core.compliance_tracker import ImmigrationComplianceTracker

logger = logging.getLogger(__name__)

class ScoutAgent:
    """Agent 1: Discovers 24/7 new cybersecurity internship postings across Workday, Indeed, LinkedIn, Handshake, Migrate Mate, & GitHub."""
    def __init__(self):
        self.name = "ScoutAgent"

    async def run(self) -> List[Dict[str, Any]]:
        logger.info(f"[{self.name}] Initiating unified multi-portal crawl (Workday, Indeed, LinkedIn, Handshake, Migrate Mate, GitHub)...")
        all_jobs: List[Dict[str, Any]] = []

        try:
            github_jobs = scrape_github_internships()
            all_jobs.extend(github_jobs)
        except Exception as e:
            logger.warning(f"[{self.name}] GitHub scraper note: {e}")

        try:
            google_jobs = scrape_google_jobs()
            all_jobs.extend(google_jobs)
        except Exception as e:
            logger.warning(f"[{self.name}] Google Jobs scraper note: {e}")

        try:
            workday_jobs = scrape_workday_employers(max_total=15, max_workers=4)
            all_jobs.extend(workday_jobs)
        except Exception as e:
            logger.warning(f"[{self.name}] Workday direct scraper note: {e}")

        try:
            multiboard_jobs = scrape_multi_board_jobs(sites=["indeed", "linkedin"], search_term="cybersecurity intern", results_per_site=5)
            all_jobs.extend(multiboard_jobs)
        except Exception as e:
            logger.warning(f"[{self.name}] Indeed/LinkedIn scraper note: {e}")

        try:
            migratemate_jobs = scrape_migratemate_jobs(limit=5)
            all_jobs.extend(migratemate_jobs)
        except Exception as e:
            logger.warning(f"[{self.name}] Migrate Mate scraper note: {e}")

        try:
            handshake_jobs = scrape_handshake_jobs(limit=5)
            all_jobs.extend(handshake_jobs)
        except Exception as e:
            logger.warning(f"[{self.name}] Handshake scraper note: {e}")

        # Ingest verified distance-ranked Summer 2027 Handshake cohort
        ranked_queue_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "summer_2027_ranked_queue.json")
        if os.path.exists(ranked_queue_path):
            try:
                with open(ranked_queue_path, "r", encoding="utf-8") as f:
                    q_jobs = json.load(f)
                for qj in q_jobs:
                    all_jobs.append({
                        "title": qj["title"],
                        "company": qj["company"],
                        "location": qj.get("display_location", qj.get("raw_location", "Marshall, MN")),
                        "url": qj["url"],
                        "ats_type": "HANDSHAKE",
                        "raw_description": f"Summer 2027 collegiate internship at {qj['company']} ({qj.get('distance_miles', 0)} mi from SMSU Marshall, MN).",
                        "source": f"Handshake Distance Tier {qj.get('tier', 1)}"
                    })
                logger.info(f"[{self.name}] Loaded {len(q_jobs)} distance-ranked Summer 2027 collegiate positions.")
            except Exception as e:
                logger.debug(f"[{self.name}] Ranked queue ingest note: {e}")
        
        saved_count = 0
        for job in all_jobs:
            job_id = save_job(job)
            if job_id:
                saved_count += 1
        logger.info(f"[{self.name}] Harvested {len(all_jobs)} jobs ({saved_count} new entries saved to DB).")
        return all_jobs

class AnalystAgent:
    """Agent 2: Evaluates job match (0-100%), enforces F-1 CPT/OPT compliance, and generates tailored answers."""
    def __init__(self):
        self.name = "AnalystAgent"
        self.matcher = JobMatcher()
        self.compliance_tracker = ImmigrationComplianceTracker()

    async def run(self):
        logger.info(f"[{self.name}] Evaluating DISCOVERED jobs with F-1 compliance guardrails & Gemini 2.5 Pro...")
        discovered_jobs = get_jobs_by_status("DISCOVERED")
        
        for job in discovered_jobs:
            # 1. Statutory F-1 CPT/OPT and ITAR/Citizenship Barrier Check
            comp = self.compliance_tracker.validate_job_compliance(job)
            if comp["compliance_status"] == "INCOMPATIBLE":
                logger.info(f"[{self.name}] Job #{job['id']} screened out by compliance: {comp['rationale']}")
                update_job_evaluation(job["id"], 0, comp["rationale"], "REJECTED")
                continue

            eval_res = self.matcher.evaluate_job(
                job_title=job["title"],
                company=job["company"],
                job_description=job["raw_description"]
            )
            score = eval_res.get("match_score", eval_res.get("score", 0))
            reason = eval_res.get("reason", "")
            rec = eval_res.get("recommendation", "REJECT")
            status = "APPROVED" if rec == "APPROVE" and score >= 65 else "REJECTED"
            
            update_job_evaluation(job["id"], score, reason, status)
            logger.info(f"[{self.name}] Job #{job['id']} ({job['title']} at {job['company']}) -> Score: {score}% [{status}]")
            await asyncio.sleep(0.5)

class SubmitterAgent:
    """Agent 3: Automates credential login and application submissions via Direct API, Workday, LinkedIn, Indeed, Handshake, & Migrate Mate."""
    def __init__(self):
        self.name = "SubmitterAgent"
        self.direct_api = DirectAPISubmitter()
        self.workday_auto = WorkdayAutomation()
        self.linkedin_auto = LinkedInAutomation()
        self.indeed_auto = IndeedAutomation()
        self.handshake_auto = HandshakeAutomation()
        self.migratemate_auto = MigrateMateAutomation()

    async def run(self):
        logger.info(f"[{self.name}] Executing submission pipeline for APPROVED jobs...")
        approved_jobs = get_jobs_by_status("APPROVED")
        
        for job in approved_jobs:
            ats_type = job.get("ats_type", "OTHER")
            url = job.get("url", "")
            
            logger.info(f"[{self.name}] Processing application for {job['company']} - {job['title']} ({ats_type})")
            
            if ats_type in ["GREENHOUSE", "LEVER"]:
                if ats_type == "GREENHOUSE":
                    success, msg = self.direct_api.submit_greenhouse(url)
                else:
                    success, msg = self.direct_api.submit_lever(url)
                log_application(job["id"], f"DIRECT_API_{ats_type}", "SUBMITTED" if success else "FAILED", error=msg)
                
            elif ats_type == "WORKDAY":
                profile = self.direct_api.profile
                success, msg = await self.workday_auto.fill_and_submit(url, profile, wait_for_review=True)
                status_val = "STAGED_FOR_REVIEW" if "STAGED" in msg else ("SUBMITTED" if success else "FAILED")
                log_application(job["id"], "PLAYWRIGHT_WORKDAY", status_val, error=msg)

            elif ats_type == "LINKEDIN":
                success, msg = await self.linkedin_auto.apply_to_job(url)
                log_application(job["id"], "PLAYWRIGHT_LINKEDIN", "SUBMITTED" if success else "FAILED", error=msg)

            elif ats_type == "INDEED":
                success, msg = await self.indeed_auto.apply_to_job(url)
                log_application(job["id"], "PLAYWRIGHT_INDEED", "SUBMITTED" if success else "FAILED", error=msg)

            elif ats_type == "HANDSHAKE":
                success, msg = await self.handshake_auto.apply_to_job(url)
                log_application(job["id"], "PLAYWRIGHT_HANDSHAKE", "SUBMITTED" if success else "FAILED", error=msg)

            elif ats_type == "MIGRATE_MATE":
                success, msg = await self.migratemate_auto.apply_to_job(url, ats_type="MIGRATE_MATE")
                log_application(job["id"], "MIGRATE_MATE_ROUTER", "SUBMITTED" if success else "FAILED", error=msg)

            else:
                logger.info(f"[{self.name}] External employer portal {url} ({ats_type}). Launching real browser autofill...")
                from automation.real_browser_session import RealBrowserSessionManager
                success, msg = await RealBrowserSessionManager.execute_real_application_fill(url, job["title"], job["company"])
                status_val = "STAGED_FOR_REVIEW" if ("STAGED" in msg or "staged" in msg.lower()) else ("SUBMITTED" if success else "FAILED")
                log_application(job["id"], f"PLAYWRIGHT_{ats_type}", status_val, error=msg)
                
            await asyncio.sleep(1)

class SentinelAgent:
    """Agent 4: 24/7 Monitor, rate-limiting guard, disk hygiene, and daily activity reporter."""
    def __init__(self):
        self.name = "SentinelAgent"

    def report(self):
        discovered = len(get_jobs_by_status("DISCOVERED"))
        approved = len(get_jobs_by_status("APPROVED"))
        staged = len(get_jobs_by_status("STAGED_FOR_REVIEW"))
        submitted = len(get_jobs_by_status("SUBMITTED"))
        interviews = len(get_jobs_by_status("INTERVIEW_INVITATION"))
        rejected = len(get_jobs_by_status("REJECTED"))
        disk = get_disk_footprint_report()
        
        logger.info(f"[{self.name}] === 24/7 AUTONOMOUS SWARM STATUS ===")
        logger.info(f"[{self.name}] Interviews: {interviews} | Submitted: {submitted} | Staged For Review: {staged} | Approved: {approved} | Pending: {discovered} | Rejected: {rejected}")
        logger.info(f"[{self.name}] Disk Footprint: {disk['total_mb']} MB ({disk['status']}) | Profiles: {disk['metrics_human']['browser_profile']}")

    def run_hygiene(self) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Executing periodic laptop disk & cache maintenance...")
        return run_full_hygiene_cycle()

class AutonomousSwarmOrchestrator:
    def __init__(self, interval_seconds: int = 3600):
        init_db()
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.submitter = SubmitterAgent()
        self.sentinel = SentinelAgent()
        from core.gmail_tracker import MailTrackerAgent
        self.mail_tracker = MailTrackerAgent()
        self.interval_seconds = interval_seconds

    async def apply_target_job(self, job_id: int, wait_for_review: bool = True):
        import sqlite3
        from core.db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            logger.error(f"Job #{job_id} not found in database.")
            return False, f"Job #{job_id} not found"
        
        job = dict(row)
        ats_type = (job.get("ats_type") or "OTHER").upper()
        url = job.get("url", "")
        logger.info(f"🎯 Target Launch: Job #{job_id} ({job['company']} - {job['title']} [{ats_type}])")
        
        if ats_type == "WORKDAY":
            profile = self.submitter.direct_api.profile
            success, msg = await self.submitter.workday_auto.fill_and_submit(url, profile, wait_for_review=wait_for_review)
            status_val = "STAGED_FOR_REVIEW" if "STAGED" in msg else ("SUBMITTED" if success else "FAILED")
            log_application(job["id"], "PLAYWRIGHT_WORKDAY", status_val, error=msg)
            return success, msg
        elif ats_type == "LINKEDIN":
            success, msg = await self.submitter.linkedin_auto.apply_to_job(url)
            log_application(job["id"], "PLAYWRIGHT_LINKEDIN", "SUBMITTED" if success else "FAILED", error=msg)
            return success, msg
        elif ats_type == "INDEED":
            success, msg = await self.submitter.indeed_auto.apply_to_job(url)
            log_application(job["id"], "PLAYWRIGHT_INDEED", "SUBMITTED" if success else "FAILED", error=msg)
            return success, msg
        elif ats_type == "HANDSHAKE":
            success, msg = await self.submitter.handshake_auto.apply_to_job(url)
            log_application(job["id"], "PLAYWRIGHT_HANDSHAKE", "SUBMITTED" if success else "FAILED", error=msg)
            return success, msg
        elif ats_type == "MIGRATE_MATE":
            success, msg = await self.submitter.migratemate_auto.apply_to_job(url, ats_type="MIGRATE_MATE")
            log_application(job["id"], "MIGRATE_MATE_ROUTER", "SUBMITTED" if success else "FAILED", error=msg)
            return success, msg
        elif ats_type in ["GREENHOUSE", "LEVER"]:
            if ats_type == "GREENHOUSE":
                success, msg = self.submitter.direct_api.submit_greenhouse(url)
            else:
                success, msg = self.submitter.direct_api.submit_lever(url)
            log_application(job["id"], f"DIRECT_API_{ats_type}", "SUBMITTED" if success else "FAILED", error=msg)
            return success, msg
        else:
            logger.info(f"🎯 Targeted external ATS launch for {job['company']}: {url}")
            from automation.real_browser_session import RealBrowserSessionManager
            success, msg = await RealBrowserSessionManager.execute_real_application_fill(url, job["title"], job["company"])
            status_val = "STAGED_FOR_REVIEW" if ("STAGED" in msg or "staged" in msg.lower()) else ("SUBMITTED" if success else "FAILED")
            log_application(job["id"], f"PLAYWRIGHT_{ats_type}", status_val, error=msg)
            return success, msg

    async def run_once(self):
        logger.info(">>> Starting Autonomous Multi-Agent Swarm Cycle <<<")
        # 1. Scout across Handshake, LinkedIn, Indeed, Google, GitHub, Workday, Migrate Mate
        await self.scout.run()
        # 2. Analyst: Evaluate CPT/OPT compliance & distance ordering
        await self.analyst.run()
        # 3. Submitter: Apply across Handshake, LinkedIn, Workday, iCIMS, Greenhouse, Lever, etc.
        await self.submitter.run()
        # 4. Mail Sentinel: Scan candidate's inboxes (Yahoo & Gmail) for application receipts and interview invites
        mail_updates = self.mail_tracker.check_inbox()
        interviews = [u for u in mail_updates if u.get("status") == "INTERVIEW_INVITATION"]
        if interviews:
            logger.info("🎉🚨 [Mail Sentinel] HIGH PRIORITY: INTERVIEW INVITATION DETECTED! 🚨🎉")
            for iv in interviews:
                logger.info(f"   Employer: {iv['company']} | Subject: {iv['subject']}")
            logger.info("💡 Launch AI Mock Interview Coach via: python main.py mock-interview")
        # 5. Sentinel: Telemetry report & disk hygiene
        self.sentinel.report()
        self.sentinel.run_hygiene()

    async def start_247_daemon(self, randomized: bool = True):
        logger.info("Starting 24/7 Autonomous Multi-Agent Swarm with organic timing...")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"[Swarm Daemon Error] {e}")
            
            # Intelligent Backoff Delay: 15 to 30 mins (900-1800s) to keep memory down and simulate human patterns
            delay = random.randint(900, 1800) if randomized else self.interval_seconds
            logger.info(f"Sleeping for {delay}s (~{delay // 60} minutes) until next patrol cycle...")
            await asyncio.sleep(delay)
