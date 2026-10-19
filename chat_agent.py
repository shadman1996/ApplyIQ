import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(__file__))

from agents.swarm import AutonomousSwarmOrchestrator, SentinelAgent
from core.credentials_manager import CredentialVault
from core.matcher import load_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def interactive_chat():
    vault = CredentialVault()
    profile = load_profile()
    orchestrator = AutonomousSwarmOrchestrator(interval_seconds=3600)
    
    print("\n" + "="*70)
    print(f"🤖 WELCOME TO YOUR CYBERSECURITY INTERNSHIP AGENT CHAT")
    print(f"Candidate: {profile['personal_info']['full_name']} | Degree: {profile['education'][0]['degree']}")
    print("="*70)
    print("Commands:")
    print("  'scan'        - Run 24/7 Scout & Gemini Analyst pass to find new jobs")
    print("  'apply'       - Submit all approved applications")
    print("  'login'       - Provide one-time login credentials for a specific portal (e.g. Workday, LinkedIn)")
    print("  'status'      - View application analytics & database status")
    print("  'daemon'      - Start continuous 24/7 background mode")
    print("  'exit'        - Exit chat session\n")
    
    while True:
        try:
            user_input = input("💬 [YOU]: ").strip()
            if not user_input:
                continue
                
            cmd = user_input.lower()
            
            if cmd in ["exit", "quit"]:
                print("👋 Exiting agent chat. Background daemon can continue running.")
                break
            elif cmd == "scan":
                print("🤖 [Agent]: Starting job search and Gemini 2.5 Pro match evaluation...")
                await orchestrator.scout.run()
                await orchestrator.analyst.run()
                print("✅ Scan and evaluation complete.")
            elif cmd == "apply":
                print("🤖 [Agent]: Executing submission pipeline...")
                await orchestrator.submitter.run()
                print("✅ Application submissions complete.")
            elif cmd == "login":
                portal = input("Which portal? (e.g. Workday, LinkedIn, Greenhouse): ").strip()
                vault.prompt_user_for_credential(portal, portal.lower())
            elif cmd == "status":
                SentinelAgent().report()
            elif cmd == "daemon":
                print("🚀 Launching 24/7 Autonomous Daemon loop...")
                await orchestrator.start_247_daemon()
            else:
                print(f"🤖 [Agent]: I heard: '{user_input}'. Running automatic pass...")
                await orchestrator.run_once()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Chat ended.")
            break

if __name__ == "__main__":
    asyncio.run(interactive_chat())
