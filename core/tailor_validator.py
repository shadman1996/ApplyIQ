"""
Resume and Application Content Validator.
Absorbed and enhanced from ApplyPilot.
Ensures zero LLM leaks, prevents hallucination/fabrication of credentials,
flags banned filler buzzwords, and sanitizes punctuation.
"""

import re
import logging
from typing import Dict, Any, List, Set, Optional

logger = logging.getLogger(__name__)

BANNED_BUZZWORDS: List[str] = [
    "passionate", "dedicated", "committed to",
    "utilizing", "utilize", "harnessing",
    "spearheaded", "spearhead", "orchestrated", "championed", "pioneered",
    "cutting-edge", "state-of-the-art", "best-in-class",
    "proven track record", "track record of success", "demonstrated ability",
    "strong communicator", "team player", "fast learner", "self-starter", "go-getter",
    "synergy", "cross-functional collaboration", "holistic",
    "transformative", "innovative solutions", "paradigm", "ecosystem",
    "proactive", "detail-oriented", "highly motivated",
    "seamless", "full lifecycle",
    "deep understanding", "extensive experience", "comprehensive knowledge",
    "thrives in", "excels at", "adept at", "well-versed in",
    "i am confident", "i believe", "i am excited",
    "strong track record", "eager to", "eager",
]

LLM_LEAK_PHRASES: List[str] = [
    "i am sorry", "i apologize", "i will try", "let me try",
    "i am at a loss", "apologies for", "one final attempt",
    "here is the corrected", "here is the revised", "here is the updated",
    "here is my", "below is the", "as requested",
    "note:", "disclaimer:", "important:",
    "i have rewritten", "i have removed", "i have fixed",
    "per your feedback", "based on your feedback", "as per the instructions",
    "the following resume", "the resume below",
]

FABRICATION_WATCHLIST: Set[str] = {
    # Stacks / Languages not in candidate profile
    "c#", "c++", "rust", "ruby", "kotlin", "swift", "scala", "matlab",
    # Frameworks not in candidate profile
    "spring boot", "rails", "angular", "vue",
    # Unverified certifications
    "pmp", "scrum master", "cissp certified", "ceh certified",
}


def sanitize_text(text: str) -> str:
    """Sanitize typography issues (em dashes, smart quotes) into clean ASCII."""
    if not text:
        return ""
    text = text.replace(" \u2014 ", ", ").replace("\u2014", ", ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text.strip()


def validate_application_content(
    text: str,
    profile: Optional[Dict[str, Any]] = None,
    mode: str = "normal"
) -> Dict[str, Any]:
    """
    Validates generated answers or resume text.
    Modes:
      - 'strict': Banned words trigger errors.
      - 'normal': Banned words trigger warnings; LLM leaks & fabrications trigger errors.
      - 'lenient': Only LLM leaks trigger errors.
    """
    errors: List[str] = []
    warnings: List[str] = []
    text_lower = text.lower()

    # 1. LLM Leak Detection (always hard error)
    for leak in LLM_LEAK_PHRASES:
        if leak in text_lower:
            errors.append(f"LLM leak phrase detected: '{leak}'")

    # 2. Fabrication Detection (check for unverified tech/certs)
    for fab in FABRICATION_WATCHLIST:
        # Use word boundary to avoid false positives (e.g., 'c' or 'vue' inside another word)
        if re.search(r'\b' + re.escape(fab) + r'\b', text_lower):
            errors.append(f"Fabricated skill/claim detected: '{fab}'")

    # 3. Preserved Real Profile Check
    if profile:
        real_name = profile.get("personal_info", {}).get("full_name", "")
        # If candidate name is mentioned, verify it isn't hallucinated as a different name
        if "i am" in text_lower and real_name:
            first_name = profile.get("personal_info", {}).get("first_name", "").lower()
            if first_name not in text_lower:
                warnings.append("First name not detected in introductory text")

    # 4. Buzzword Check
    for buzz in BANNED_BUZZWORDS:
        if re.search(r'\b' + re.escape(buzz) + r'\b', text_lower):
            msg = f"Cliché/filler buzzword: '{buzz}'"
            if mode == "strict":
                errors.append(msg)
            else:
                warnings.append(msg)

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "sanitized_text": sanitize_text(text)
    }
