import json
import re
import os
from typing import Dict, Any, Tuple
from core.llm_client import GeminiClient, GeminiMatcherClient

# Load Shadman's profile
PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "profile.json")

def load_profile() -> Dict[str, Any]:
    with open(PROFILE_PATH, 'r') as f:
        return json.load(f)

# Keywords for instant local pre-filter (Tier-1)
POSITIVE_KEYWORDS = [
    r"cyber\s*security", r"information\s*security", r"sec\s*ops", r"soc",
    r"application\s*security", r"appsec", r"network\s*security", r"devsecops",
    r"cloud\s*security", r"iam", r"identity", r"security\s*engineer", r"vulnerability",
    r"supply\s*chain", r"logistics\s*(?:systems|security|it)", r"erp\s*(?:security|systems|analyst)",
    r"enterprise\s*systems", r"mis\s*(?:specialist|analyst|operations|engineer)"
]

NEGATIVE_KEYWORDS = [
    r"senior\s+director", r"vice\s+president", r"vp", r"lead\s+architect",
    r"10\+\s+years", r"secret\s+clearance\s+required", r"top\s+secret"
]

def fast_local_prefilter(title: str, description: str = "") -> Tuple[bool, str]:
    """
    Tier-1 instant local filter (0ms cost). Returns (should_process, reason).
    """
    combined = (title + " " + description).lower()
    
    # Check for senior/VP/Clearance exclusions
    for neg in NEGATIVE_KEYWORDS:
        if re.search(neg, combined):
            return False, f"Rejected by local filter: contains negative pattern '{neg}'"
            
    # Check for cybersecurity keyword match
    matched = False
    for pos in POSITIVE_KEYWORDS:
        if re.search(pos, combined):
            matched = True
            break
            
    if not matched:
        return False, "Rejected by local filter: missing key cybersecurity role terms"
        
    return True, "Passed Tier-1 local pre-filter"

class JobMatcher:
    def __init__(self):
        self.profile = load_profile()
        self.matcher = GeminiMatcherClient()
        self.llm = GeminiClient()

    def evaluate_job(self, job_title: str, company: str, job_description: str, form_questions: list = None) -> Dict[str, Any]:
        """
        Tier-2 Gemini Evaluation. Scores 0-100% and determines suitability.
        Uses structured AdaptationOutput schema to eliminate extra conversational tokens.
        """
        # First run Tier-1 local prefilter
        passed, reason = fast_local_prefilter(job_title, job_description)
        if not passed:
            return {
                "score": 0,
                "match_score": 0,
                "should_apply": False,
                "reason": reason,
                "recommendation": "REJECT",
                "custom_responses": {}
            }

        target_desc = f"Title: {job_title}\nCompany: {company}\nDescription: {job_description}"
        eval_res = self.matcher.analyze_and_tailor(self.profile, target_desc, form_questions=form_questions)
        
        score = eval_res.get("match_score", 0)
        should_apply = eval_res.get("should_apply", score >= 65)
        tailored_summary = eval_res.get("tailored_summary", f"Passed pre-filter for {job_title} at {company}")

        return {
            "match_score": score,
            "score": score,
            "should_apply": should_apply,
            "reason": tailored_summary,
            "recommendation": "APPROVE" if should_apply else "REJECT",
            "tailored_summary": tailored_summary,
            "custom_responses": eval_res.get("custom_responses", {})
        }

    def generate_custom_answer(self, question: str, company: str, job_title: str) -> str:
        """
        Generates tailored responses for custom application essay questions using Gemini Pro.
        """
        system_instruction = "You are an expert technical resume writer. Answer the job application question concisely, accurately, and compellingly based ONLY on the candidate's actual experience."
        
        prompt = f"""
        Candidate: Shadman Ahsan (MS in Cybersecurity candidate, Graduate Assistant at SMSU TRC, former MIS Specialist at Helen Keller International).
        Company: {company}
        Role: {job_title}
        Question: "{question}"
        
        Write a professional 2-3 sentence answer highlighting relevant experience in IAM, Systems Admin, Python, Security, or SQL.
        """
        return self.llm.generate_text(prompt, system_instruction=system_instruction, model="gemini-2.5-pro")
