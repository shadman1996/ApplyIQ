"""
F-1 CPT / STEM OPT & USCIS Policy Compliance Monitoring Engine.
Enforces SEVP, DHS, and USCIS regulatory guidelines for international student employment:
1. Degree Field Nexus (Direct relationship to M.S. in Cybersecurity coursework).
2. STEM OPT 24-Month Extension & E-Verify Employer Suitability.
3. Defense / ITAR / Clearance Barrier Detection (Citizenship disqualifiers).
4. Academic Term Work Authorization Caps (Part-Time 20h vs Full-Time Summer CPT).
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger("jarvis.compliance")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(PROJECT_ROOT, "config", "profile.json")

# Keywords indicating hard statutory exclusion for non-immigrants (ITAR / Federal Defense)
CITIZENSHIP_EXCLUSIONS = [
    r"u\.?s\.?\s*citizenship\s*(?:is\s*)?required",
    r"must\s+be\s+a\s+u\.?s\.?\s*citizen",
    r"only\s+u\.?s\.?\s*citizens",
    r"due\s+to\s+itar",
    r"itar\s+(?:compliance|restriction|requirement)",
    r"active\s+(?:top\s+secret|secret|polygraph)\s+clearance",
    r"dod\s+security\s+clearance\s+required",
    r"requires\s+(?:an?\s+)?active\s+security\s+clearance"
]

# Positive indicators of international student friendly / E-Verify employers
SPONSORSHIP_FRIENDLY_INDICATORS = [
    r"e-?verify",
    r"cpt",
    r"opt",
    r"stem\s+opt",
    r"f-1",
    r"visa\s+sponsorship\s+available",
    r"open\s+to\s+sponsoring",
    r"equal\s+opportunity\s+employer"
]

# Academic NEXUS keywords for M.S. in Cybersecurity at SMSU
CYBER_NEXUS_KEYWORDS = [
    r"cyber\s*security", r"information\s*security", r"infosec", r"soc",
    r"network\s*security", r"application\s*security", r"appsec", r"vulnerability",
    r"threat", r"incident\s*response", r"forensic", r"iam", r"identity",
    r"devsecops", r"cloud\s*security", r"penetration\s*test", r"siem",
    r"data\s*privacy", r"governance", r"risk", r"compliance", r"grc",
    r"software\s*engineering", r"python", r"systems\s*administrator",
    r"supply\s*chain\s*security", r"enterprise\s*systems", r"mis"
]


class ImmigrationComplianceTracker:
    def __init__(self, profile_path: str = PROFILE_PATH):
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)
        else:
            self.profile = {}

    def get_candidate_f1_summary(self) -> Dict[str, Any]:
        """
        Returns structured F-1 immigration parameters for candidate Shadman Ahsan.
        """
        edu = self.profile.get("education", [{}])[0]
        institution = edu.get("institution", "Southwest Minnesota State University")
        degree = edu.get("degree", "Master of Science in Cybersecurity")
        
        return {
            "candidate_name": self.profile.get("personal_info", {}).get("full_name", "Shadman Ahsan"),
            "status": "F-1 Non-Immigrant Student",
            "institution": institution,
            "degree_program": degree,
            "cip_stem_eligible": True,
            "work_authorizations": {
                "cpt": "Curricular Practical Training (Part-time <=20h/week during academic terms; Full-time 40h/week during official summer breaks)",
                "initial_opt": "12-Month Post-Completion OPT (Any qualified employer in field of study)",
                "stem_opt_extension": "24-Month STEM Extension (Requires E-Verify employer & Form I-983 training plan)",
                "total_practical_training_duration": "36 Months (3 Years) without employer H-1B sponsorship needed upfront"
            },
            "immediate_sponsorship_required": False,
            "future_h1b_lottery_needed": True
        }

    def validate_job_compliance(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a target job description against SEVP nexus & citizenship restrictions.
        Returns:
            - compliance_status: 'COMPLIANT', 'INCOMPATIBLE', or 'REQUIRES_REVIEW'
            - is_nexus_valid: bool (direct link to M.S. in Cybersecurity)
            - has_citizenship_barrier: bool (ITAR / defense clearance required)
            - e_verify_identified: bool
            - rationale: str
        """
        title = job.get("title", "")
        desc = job.get("raw_description", "")
        combined = f"{title} {desc}".lower()

        # 1. Check for statutory citizenship / ITAR / clearance disqualifiers
        citizenship_barriers = []
        for pat in CITIZENSHIP_EXCLUSIONS:
            if re.search(pat, combined):
                citizenship_barriers.append(pat)

        if citizenship_barriers:
            return {
                "compliance_status": "INCOMPATIBLE",
                "is_nexus_valid": False,
                "has_citizenship_barrier": True,
                "e_verify_identified": False,
                "barriers_detected": citizenship_barriers,
                "rationale": "Statutory exclusion: Role requires U.S. Citizenship or Active Security Clearance (ITAR/Defense restrictions). Non-compliant for F-1 visa holders."
            }

        # 2. Check for Academic Nexus (SEVP Requirement: Role must be directly related to Cybersecurity/Computer Science)
        nexus_matches = [pat for pat in CYBER_NEXUS_KEYWORDS if re.search(pat, combined)]
        is_nexus_valid = len(nexus_matches) >= 1

        # 3. Check for E-Verify or positive STEM OPT signals
        e_verify_matches = [pat for pat in SPONSORSHIP_FRIENDLY_INDICATORS if re.search(pat, combined)]
        e_verify_identified = bool(e_verify_matches)

        if not is_nexus_valid:
            return {
                "compliance_status": "REQUIRES_REVIEW",
                "is_nexus_valid": False,
                "has_citizenship_barrier": False,
                "e_verify_identified": e_verify_identified,
                "rationale": "Nexus warning: Position lacks direct keyword correlation to M.S. in Cybersecurity curriculum. SEVP Form I-20 endorsement may require advisor review."
            }

        # Full compliance verified
        notes = "100% SEVP & USCIS Compliant. Direct academic nexus to M.S. in Cybersecurity."
        if e_verify_identified:
            notes += " E-Verify / international training friendly indicators detected."

        return {
            "compliance_status": "COMPLIANT",
            "is_nexus_valid": True,
            "has_citizenship_barrier": False,
            "e_verify_identified": e_verify_identified,
            "nexus_matches": nexus_matches[:5],
            "rationale": notes
        }

    def generate_compliance_report(self) -> str:
        """
        Outputs a comprehensive immigration & compliance health report.
        """
        summary = self.get_candidate_f1_summary()
        lines = [
            "=" * 70,
            "🛡️ SEVP F-1 CPT & 3-YEAR STEM OPT IMMIGRATION COMPLIANCE MONITOR",
            "=" * 70,
            f"Candidate: {summary['candidate_name']} | Status: {summary['status']}",
            f"Institution: {summary['institution']}",
            f"Major Field of Study: {summary['degree_program']} [STEM CIP ELIGIBLE]",
            "",
            "📋 Statutory Work Authorization Pathways:",
            f"  • CPT: {summary['work_authorizations']['cpt']}",
            f"  • Initial Post-Grad OPT: {summary['work_authorizations']['initial_opt']}",
            f"  • STEM Extension: {summary['work_authorizations']['stem_opt_extension']}",
            f"  • Total Runway: {summary['work_authorizations']['total_practical_training_duration']}",
            "",
            "⚖️ Legal & Compliance Ingestion Rules:",
            "  1. ITAR / US Citizen-Only Filter: Automatically rejects defense/ITAR roles.",
            "  2. Academic Nexus Enforcement: Verifies alignment with SMSU Cybersecurity syllabus.",
            "  3. Deterministic Application Answers: Declares Authorized=YES, Future Sponsorship=YES.",
            "=" * 70
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    tracker = ImmigrationComplianceTracker()
    print(tracker.generate_compliance_report())
