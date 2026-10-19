"""
AI Mock Interview Coach for Cyber & IT Job Applications.
Generates tailored interview questions based on Job Description & Candidate Background,
evaluates responses using the STAR framework, and scores technical readiness.
"""

import json
import logging
import os
import sqlite3
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "applications.db")
PROFILE_PATH = os.path.join(PROJECT_ROOT, "config", "profile.json")
INTERVIEWS_DIR = os.path.join(PROJECT_ROOT, "data", "interviews")

class MockInterviewCoach:
    def __init__(self, profile_data: Optional[Dict[str, Any]] = None):
        self.profile = profile_data or self._load_profile()
        os.makedirs(INTERVIEWS_DIR, exist_ok=True)

    def _load_profile(self) -> Dict[str, Any]:
        if os.path.exists(PROFILE_PATH):
            try:
                with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[InterviewCoach] Could not load profile: {e}")
        return {}

    def get_job_details(self, job_id: Optional[int] = None, company_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if job_id:
            c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        elif company_name:
            c.execute("SELECT * FROM jobs WHERE company LIKE ? ORDER BY id DESC LIMIT 1", (f"%{company_name}%",))
        else:
            c.execute("""
                SELECT * FROM jobs 
                WHERE status IN ('INTERVIEW_INVITATION', 'CONFIRMED_BY_EMAIL', 'SUBMITTED') 
                ORDER BY 
                    CASE 
                        WHEN status = 'INTERVIEW_INVITATION' THEN 1 
                        WHEN status = 'CONFIRMED_BY_EMAIL' THEN 2 
                        ELSE 3 
                    END, 
                    id DESC 
                LIMIT 1
            """)
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def generate_interview_questions(self, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        title = job.get("title", "IT / Cybersecurity Position")
        company = job.get("company", "Target Employer")
        title_lower = title.lower()

        # Categorize role focus
        is_cyber = any(k in title_lower for k in ["cyber", "security", "infosec", "soc", "analyst"])
        is_it_ops = any(k in title_lower for k in ["operations", "systems", "support", "infrastructure", "network", "help desk", "admin"])
        is_dev = any(k in title_lower for k in ["developer", "software", "engineer", "cloud"])

        questions = []

        # 1. Opening & Candidate Positioning
        questions.append({
            "id": 1,
            "type": "Introduction & Fit",
            "question": f"Walk me through your background and what motivated you to apply for the {title} position at {company}?",
            "eval_criteria": "Focus on candidate's M.S. Cybersecurity at SMSU, TRC hands-on operations experience, and alignment with company goals.",
            "star_guidance": "Highlight Current Role (SMSU TRC Graduate Assistant) -> Key Prior Experience (Helen Keller International MIS Specialist) -> Clear bridge to why this specific role."
        })

        # 2. Behavioral / STAR Question 1: Operational Problem Solving
        questions.append({
            "id": 2,
            "type": "Behavioral (STAR)",
            "question": "Tell me about a time when you identified a critical technical issue or vulnerability that other team members overlooked. How did you resolve it?",
            "eval_criteria": "Clear STAR structure (Situation, Task, Action, Result). Action must detail candidate's direct technical contribution.",
            "star_guidance": "S: System/network outage or security misconfiguration. T: Need for zero downtime or SLA compliance. A: Diagnostic steps, logs checked, script or config applied. R: Measurable outcome (e.g. 99.9% uptime restored, risk mitigated)."
        })

        # 3. Role-Specific Technical Scenario 1
        if is_cyber:
            questions.append({
                "id": 3,
                "type": "Technical Scenario (Cybersecurity)",
                "question": "An alert flags an anomalous outbound beacon from an internal workstation communicating with an unknown external IP over port 443. Walk me step-by-step through your triage, containment, and incident response process.",
                "eval_criteria": "Incident response lifecycle: Triage/Verification -> Host Isolation -> Memory/Process/Network Artifact analysis -> Root cause & Remediation -> Documentation.",
                "star_guidance": "Emphasize network isolation, preserving volatile memory, analyzing endpoint processes/PowerShell execution, and correlating SIEM/EDR logs."
            })
        elif is_it_ops:
            questions.append({
                "id": 3,
                "type": "Technical Scenario (IT Operations)",
                "question": "Several users report that their workstations cannot authenticate against Active Directory after a network maintenance window. How do you troubleshoot and isolate whether the issue is DNS, replication, firewall rules, or service accounts?",
                "eval_criteria": "Systematic root cause analysis: ping/traceroute -> nslookup/DNS resolution -> netdom / dcdiag tests -> Kerberos/LDAP port checks (88, 389).",
                "star_guidance": "Demonstrate calm, methodical diagnostic methodology starting from physical/network layer up to identity and application services."
            })
        else:
            questions.append({
                "id": 3,
                "type": "Technical Scenario (Software & Systems)",
                "question": "When building an internal automation script or pipeline that interacts with sensitive enterprise databases, what principles and security practices do you enforce to ensure data integrity and least privilege?",
                "eval_criteria": "Parameterization, secrets management (no hardcoded credentials), least privilege RBAC, error handling, audit logging.",
                "star_guidance": "Mention environment variables, credential vaults, prepared statements, and transaction boundaries."
            })

        # 4. Role-Specific Technical Deep-Dive 2
        if is_cyber:
            questions.append({
                "id": 4,
                "type": "Technical Knowledge (Threats & Defense)",
                "question": "How do you evaluate and implement the Principle of Least Privilege across multi-tiered enterprise systems, especially regarding Active Directory, Group Policies, and administrative access?",
                "eval_criteria": "Tiered administration models, eliminating domain admin sprawl, privileged access management (PAM), and regular privilege auditing.",
                "star_guidance": "Cite your experience managing enterprise user permissions, RBAC policies, and auditing access logs."
            })
        else:
            questions.append({
                "id": 4,
                "type": "Technical Knowledge (Infrastructure & Automation)",
                "question": "How do you approach automating repetitive IT administration tasks (such as account provisioning, system patch deployment, or backup verification)? Share a specific script or tool you implemented.",
                "eval_criteria": "Scripting language (Python/Bash/PowerShell), scheduling/monitoring, error handling, and reliability.",
                "star_guidance": "Discuss Python automation scripts built to handle scheduled syncs, automated reporting, or system health telemetry."
            })

        # 5. Behavioral / Collaboration & Pressure
        questions.append({
            "id": 5,
            "type": "Behavioral (Pressure & Conflict)",
            "question": "Describe a situation where you had to support a non-technical stakeholder or executive who was frustrated by a strict security policy or system downtime. How did you handle the communication and outcome?",
            "eval_criteria": "Empathy, clear non-technical explanation, finding secure compromise or expedited remediation without violating security posture.",
            "star_guidance": "Highlight customer service and stakeholder management from your Technology Resource Center (TRC) support role."
        })

        # 6. Candidate Reverse Interview Questions
        questions.append({
            "id": 6,
            "type": "Candidate Questions for Employer",
            "question": "What questions do you have for us regarding the team's roadmap, current infrastructure initiatives, or mentorship during the internship?",
            "eval_criteria": "Insightful questions showing candidate did research on company tech stack, culture, and long-term project impact.",
            "star_guidance": "Ask about tech stack modernization, incident response workflow maturity, or typical intern project ownership."
        })

        return questions

    def evaluate_response(self, question: Dict[str, Any], candidate_answer: str) -> Dict[str, Any]:
        """
        Evaluates candidate's answer against criteria and provides instant scoring & coaching feedback.
        """
        ans_len = len(candidate_answer.strip().split())
        score = 60 # Baseline
        feedback = []
        strengths = []
        improvements = []

        ans_lower = candidate_answer.lower()

        # Length / Depth check
        if ans_len < 25:
            score -= 20
            improvements.append("Answer is too brief. Provide concrete context, technical actions taken, and the final measurable outcome.")
        elif ans_len > 60:
            score += 15
            strengths.append("Comprehensive response with substantive detail.")

        # Check for STAR indicators in behavioral questions
        if "Behavioral" in question["type"]:
            has_star = any(w in ans_lower for w in ["situation", "when i was", "task", "goal", "action", "i implemented", "i configured", "result", "outcome", "consequently", "reduced", "improved"])
            if has_star:
                score += 15
                strengths.append("Structured narrative follows the STAR problem-solving framework.")
            else:
                score -= 10
                improvements.append("Use the STAR framework explicitly: Situation -> Task -> Action -> Result.")

        # Check for technical keywords
        tech_keywords = ["active directory", "log", "siem", "firewall", "patch", "python", "script", "backup", "server", "linux", "windows", "vulnerability", "isolate", "dns", "uptime", "sla", "rbac", "least privilege", "packet", "audit"]
        matched_tech = [k for k in tech_keywords if k in ans_lower]
        if matched_tech:
            score += min(len(matched_tech) * 5, 20)
            strengths.append(f"Demonstrated domain depth by referencing key technologies: {', '.join(matched_tech[:4])}.")
        else:
            improvements.append("Incorporate specific technical tools, command names, protocols, or architecture concepts to demonstrate hands-on mastery.")

        final_score = max(min(score, 100), 20)

        # Rating tier
        if final_score >= 85:
            rating = "Excellent (Ready for Onsite)"
        elif final_score >= 70:
            rating = "Strong (Minor Refinements Recommended)"
        elif final_score >= 50:
            rating = "Developing (Needs Clearer Structure & Metrics)"
        else:
            rating = "Needs Practice (Review STAR Guidelines)"

        return {
            "score": final_score,
            "rating": rating,
            "strengths": strengths,
            "improvements": improvements,
            "star_guidance": question.get("star_guidance", ""),
            "ideal_response_summary": f"A strong response should clearly reference the candidate's active experience (SMSU TRC Graduate Assistant or Helen Keller International MIS Specialist), explicitly state the technical tools used, and conclude with the business impact (e.g. 99.9% uptime, reduced ticket turnaround, zero security breaches)."
        }

    def run_interactive_session(self, job_id: Optional[int] = None, company_name: Optional[str] = None):
        """
        Runs a live, interactive terminal mock interview session with the candidate.
        """
        job = self.get_job_details(job_id, company_name)
        if not job:
            job = {
                "id": 999,
                "title": "Summer 2027 IT & Cybersecurity Intern",
                "company": "Enterprise Tech Partner",
                "location": "Marshall, MN / Minneapolis, MN"
            }

        print("=" * 80)
        print(f"🎙️ J.A.R.V.I.S. AI MOCK INTERVIEW SIMULATOR")
        print(f"🏢 Target Company: {job['company']}")
        print(f"💼 Target Role:    {job['title']}")
        print(f"👤 Candidate:      {self.profile.get('name', 'Shadman Ahsan')} (SMSU M.S. Cybersecurity)")
        print("=" * 80)
        print("Instructions: Answer each question naturally as you would in a real interview.")
        print("Type your answer and press Enter. Type 'skip' to move to next question, or 'quit' to exit.\n")

        questions = self.generate_interview_questions(job)
        session_results = []
        total_score = 0

        for q in questions:
            print("-" * 80)
            print(f"📋 Question {q['id']}/{len(questions)} [{q['type']}]:")
            print(f"❓ \"{q['question']}\"")
            print(f"💡 STAR Tip: {q['star_guidance']}\n")

            user_answer = input("👉 Your Answer: ").strip()
            if user_answer.lower() == 'quit':
                print("\nSession aborted by candidate.")
                break
            if user_answer.lower() == 'skip' or not user_answer:
                print("⏭️ Question skipped.\n")
                continue

            evaluation = self.evaluate_response(q, user_answer)
            total_score += evaluation["score"]

            print(f"\n📊 Score: {evaluation['score']}/100 — {evaluation['rating']}")
            if evaluation["strengths"]:
                print(f"  ✅ Strengths: {' '.join(evaluation['strengths'])}")
            if evaluation["improvements"]:
                print(f"  ⚠️ Improvement: {' '.join(evaluation['improvements'])}")
            print(f"  🎯 Coaching Advice: {evaluation['ideal_response_summary']}\n")

            session_results.append({
                "question": q,
                "answer": user_answer,
                "evaluation": evaluation
            })

        answered_count = len(session_results)
        avg_score = int(total_score / answered_count) if answered_count > 0 else 0

        print("=" * 80)
        print(f"🏁 MOCK INTERVIEW COMPLETE!")
        print(f"📊 Overall Performance: {avg_score}/100 ({answered_count}/{len(questions)} answered)")
        print("=" * 80)

        # Save session file
        timestamp = int(time.time())
        save_path = os.path.join(INTERVIEWS_DIR, f"mock_interview_{job['company'].replace(' ', '_')}_{timestamp}.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump({
                "job": job,
                "timestamp": timestamp,
                "average_score": avg_score,
                "results": session_results
            }, f, indent=2)

        print(f"💾 Interview report saved to: {save_path}")
        return save_path

if __name__ == "__main__":
    coach = MockInterviewCoach()
    coach.run_interactive_session()
