import sys
import os
import asyncio
import logging

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

from agents.swarm import AutonomousSwarmOrchestrator, SentinelAgent
from core.db import init_db
from core.hygiene import setup_rotating_logger, run_full_hygiene_cycle, get_disk_footprint_report
from desktop_launcher import launch_desktop_window

# Configure rotating file logging (10MB cap per file, 5 archives) and console output
setup_rotating_logger()

async def main():
    init_db()
    args = sys.argv[1:]
    cmd = args[0].lower() if args else "desktop"
    
    orchestrator = AutonomousSwarmOrchestrator(interval_seconds=3600)
    
    if cmd in ["desktop", "ui", "hud", "jarvis"]:
        launch_desktop_window()
    elif cmd == "daemon":
        print("Starting 24/7 Autonomous Cybersecurity Internship Application Swarm with Disk Hygiene...")
        await orchestrator.start_247_daemon()
    elif cmd == "report":
        sentinel = SentinelAgent()
        sentinel.report()
    elif cmd in ["clean", "hygiene"]:
        print("Running full system disk hygiene and cache purge...")
        res = run_full_hygiene_cycle()
        print(f"✅ Reclaimed: {res['browser_cache_freed_mb']} MB | Active footprint: {res['total_active_disk_mb']} MB ({res['status']})")
    elif cmd in ["run-once", "cli"]:
        print("Running single agent execution pass...")
        await orchestrator.run_once()
    elif cmd in ["apply", "target", "test-job"]:
        target_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else 163
        print(f"🎯 Launching targeted application for Job #{target_id} with Human-in-the-Loop review...")
        success, msg = await orchestrator.apply_target_job(target_id, wait_for_review=True)
        print(f"[{'SUCCESS' if success else 'NOTICE'}] {msg}")
    elif cmd in ["compliance", "sevp", "visa", "f1"]:
        from core.compliance_tracker import ImmigrationComplianceTracker
        tracker = ImmigrationComplianceTracker()
        print(tracker.generate_compliance_report())
    elif cmd in ["connect", "auth", "login", "status"]:
        from automation.real_browser_session import RealBrowserSessionManager
        target_portal = args[1].lower().strip() if len(args) > 1 else "status"
        if target_portal in ["status", "check", "list"]:
            print("\n📋 J.A.R.V.I.S. Multi-App Connection Status Matrix:")
            statuses = RealBrowserSessionManager.get_auth_status()
            for portal, info in statuses.items():
                icon = "🟢" if info.get("connected") else "⚪"
                print(f"  {icon} {portal.upper():<12}: {info.get('label')} ({info.get('user') or 'No active session'})")
            from core.gmail_tracker import GmailTrackerAgent
            gt = GmailTrackerAgent()
            mail_status = "CONFIGURED (Ready to sync)" if gt.email_password else "CREDENTIALS NEEDED"
            print(f"  📧 GMAIL IMAP  : {mail_status} ({gt.email_user})\n")
        else:
            print(f"🌐 Opening real browser window on desktop for {target_portal.upper()} authentication...")
            res = await RealBrowserSessionManager.open_portal_login_window(target_portal)
            print(f"[{'SUCCESS' if res.get('success') else 'NOTICE'}] {res.get('message')}")
    elif cmd in ["run-all", "all", "full", "patrol"]:
        print("🚀 Executing Unified Autonomous Pipeline across Handshake, LinkedIn, Every Media & Email...")
        await orchestrator.run_once()
    elif cmd in ["inbox", "mail", "sync-mail", "check-mail"]:
        from core.gmail_tracker import MailTrackerAgent
        print("📧 Connecting to candidate inboxes (Yahoo & Gmail) to scan for application receipts & interview invitations...")
        tracker = MailTrackerAgent()
        updates = tracker.check_inbox()
        print(f"✅ Inbox sync complete. Found {len(updates)} status updates.")
        interviews = [u for u in updates if u.get("status") == "INTERVIEW_INVITATION"]
        if interviews:
            print("\n🎉🚨 HIGH PRIORITY: INTERVIEW INVITATION DETECTED! 🚨🎉")
            for iv in interviews:
                print(f"  🏢 Employer: {iv['company']} | Subject: {iv['subject']}")
            print("\n💡 Launch AI Mock Interview Coach via: python main.py mock-interview")
    elif cmd in ["mail-test", "test-mail", "test-inbox"]:
        from core.gmail_tracker import MailTrackerAgent
        print("📧 Running Simulated Email Feed with realistic employer updates...")
        tracker = MailTrackerAgent()
        updates = tracker.check_inbox(mock=True)
        print(f"✅ Simulation complete. Detected {len(updates)} employer events:")
        for u in updates:
            icon = "🎉" if u.get("status") == "INTERVIEW_INVITATION" else "📩"
            print(f"  {icon} [{u.get('status')}] {u['company']} — {u['subject']}")
        
        interviews = [u for u in updates if u.get("status") == "INTERVIEW_INVITATION"]
        if interviews:
            target_comp = interviews[0]["company"]
            print(f"\n💡 Ready to drill interview questions for {target_comp}!")
            print(f"   Run: python main.py mock-interview '{target_comp}'")
    elif cmd in ["interview", "mock-interview", "mock"]:
        from core.interview_coach import MockInterviewCoach
        coach = MockInterviewCoach()
        job_id = None
        comp_name = None
        if len(args) > 1:
            if args[1].isdigit():
                job_id = int(args[1])
            else:
                comp_name = " ".join(args[1:])
        coach.run_interactive_session(job_id=job_id, company_name=comp_name)
    else:
        print(f"Unknown command: '{cmd}'. Launching J.A.R.V.I.S. Desktop Command Center...")
        launch_desktop_window()

if __name__ == "__main__":
    asyncio.run(main())
