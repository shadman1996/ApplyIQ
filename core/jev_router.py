"""
core/jev_router.py - TypeSafe AI / Jev System 1 Decision Router.
Provides ultra-low-latency (~15ms), low-token non-autoregressive decision routing
between candidate/application tasks, local Second Brain, and heavy LLM workflows.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("jev_router")

# Decision log path
DECISION_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "jev_decisions.jsonl"
DECISION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

class JevRouter:
    """
    TypeSafe AI Jev Router (LLM -> JEV -> AGENT).
    Evaluates state and returns typed Choice, Score, or Noul answers.
    Supports:
      - 'shadow' mode: Logs proposed Jev decisions alongside heuristics without blocking.
      - 'active' mode: Directs execution based on live Jev System 1 decisions.
      - 'offline' mode: Fallback when TYPESAFE_API_KEY is not configured.
    """

    def __init__(self, mode: str = "shadow"):
        self.api_key = os.getenv("TYPESAFE_API_KEY")
        self.mode = os.getenv("JEV_MODE", mode).lower()
        self.client = None
        
        if self.api_key and self.api_key.strip():
            try:
                import typesafe_sdk
                self.client = typesafe_sdk.TypeSafeClient(api_key=self.api_key.strip())
                logger.info("TypeSafe SDK client initialized for live Jev routing.")
            except Exception as e:
                logger.warning(f"Could not initialize TypeSafeClient: {e}. Defaulting to offline heuristics.")
                self.client = None
        else:
            logger.info("No TYPESAFE_API_KEY detected. Running in offline/shadow mode.")

    def log_decision(self, task_name: str, state: Any, decision: Dict[str, Any], latency_ms: float = 0.0):
        """Persist decision audit trail to logs/jev_decisions.jsonl."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_name": task_name,
            "mode": self.mode,
            "has_live_client": self.client is not None,
            "latency_ms": latency_ms,
            "state_summary": str(state)[:250],
            "decision": decision
        }
        try:
            with open(DECISION_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log Jev decision: {e}")

    def decide_triage(self, url: str, portal_type: str = "") -> Dict[str, Any]:
        """
        Situation 1: Route external job application portal triage.
        Decides whether to use Workday Fast Path, Handshake, Custom DOM filler, or Skip.
        """
        start_time = datetime.utcnow()
        state = {"url": url, "portal_type": portal_type}
        
        # If live client is active
        if self.client:
            try:
                import typesafe_sdk
                result = self.client.system_one(
                    state=state,
                    questions={
                        "route": typesafe_sdk.Choice(
                            instructions="What execution engine should handle this job application URL?",
                            criteria={
                                "workday_fast_path": "URL contains myworkdayjobs.com or workday portal",
                                "handshake_apply": "URL is on joinhandshake.com",
                                "direct_ats_filler": "URL is greenhouse, lever, or custom company portal",
                                "skip_unsupported": "URL is unsupported, login-walled, or expired"
                            }
                        )
                    }
                )
                choice = result.choices["route"].choice
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                res = {"route": choice, "source": "typesafe_live"}
                self.log_decision("triage_portal", state, res, duration)
                return res
            except Exception as e:
                logger.warning(f"TypeSafe live call failed ({e}), falling back to deterministic heuristic.")

        # Offline / heuristic decision
        lower_url = url.lower()
        if "myworkdayjobs.com" in lower_url or portal_type.lower() == "workday":
            route = "workday_fast_path"
        elif "joinhandshake.com" in lower_url:
            route = "handshake_apply"
        elif any(k in lower_url for k in ["greenhouse.io", "lever.co", "smartrecruiters.com", "icims.com"]):
            route = "direct_ats_filler"
        else:
            route = "direct_ats_filler"

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        res = {"route": route, "source": "offline_heuristic"}
        self.log_decision("triage_portal", state, res, duration)
        return res

    def decide_question_action(self, question: str, options: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Situation 2: Dynamic Question Answering Gatekeeper.
        Decides if question is a boolean/choice question, a standard F-1/EEO query,
        or requires heavy LLM essay generation.
        """
        start_time = datetime.utcnow()
        state = {"question": question, "options_count": len(options) if options else 0}
        
        if self.client:
            try:
                import typesafe_sdk
                result = self.client.system_one(
                    state=state,
                    questions={
                        "action": typesafe_sdk.Choice(
                            instructions="How should this job application question be handled?",
                            criteria={
                                "second_brain_lookup": "Standard profile, visa, degree, address, or EEO question",
                                "direct_choice_match": "Question provides standard multiple choice options",
                                "heavy_llm_essay": "Open-ended essay, cover letter, or bespoke subjective question"
                            }
                        )
                    }
                )
                choice = result.choices["action"].choice
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                res = {"action": choice, "source": "typesafe_live"}
                self.log_decision("question_gatekeeper", state, res, duration)
                return res
            except Exception as e:
                logger.warning(f"TypeSafe live call failed ({e}), falling back to heuristic.")

        lower_q = question.lower()
        if any(k in lower_q for k in ["sponsorship", "authorized", "visa", "gpa", "degree", "school", "phone", "gender", "race", "veteran", "disability"]):
            action = "second_brain_lookup"
        elif options and len(options) > 0 and len(question) < 150:
            action = "direct_choice_match"
        else:
            action = "heavy_llm_essay"

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        res = {"action": action, "source": "offline_heuristic"}
        self.log_decision("question_gatekeeper", state, res, duration)
        return res

    def decide_failure_recovery(self, error: str, retry_count: int) -> Dict[str, Any]:
        """
        Situation 3: Automation Failure & Obstacle Recovery Routing.
        Decides whether to bypass DOM overlay, refresh session, try alternative selector, or abort/escalate.
        """
        start_time = datetime.utcnow()
        state = {"error": error, "retry_count": retry_count}
        
        if retry_count >= 3:
            res = {"action": "abort_and_notify_user", "reason": "Max consecutive retries exceeded", "source": "circuit_breaker"}
            self.log_decision("failure_recovery", state, res, 0.5)
            return res

        if self.client:
            try:
                import typesafe_sdk
                result = self.client.system_one(
                    state=state,
                    questions={
                        "recovery_action": typesafe_sdk.Choice(
                            instructions="What recovery strategy should be applied for this automation error?",
                            criteria={
                                "dom_filter_bypass": "Click intercepted by overlay or backdrop element",
                                "auth_reconnect": "Session expired, 401/403, or redirected to login",
                                "retry_alt_selector": "Element not found or timed out",
                                "abort_and_notify_user": "Unrecoverable captcha, blocked account, or internal failure"
                            }
                        )
                    }
                )
                choice = result.choices["recovery_action"].choice
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                res = {"action": choice, "source": "typesafe_live"}
                self.log_decision("failure_recovery", state, res, duration)
                return res
            except Exception as e:
                logger.warning(f"TypeSafe live call failed ({e}), falling back to heuristic.")

        lower_err = error.lower()
        if "intercepted" in lower_err or "overlay" in lower_err or "click_filter" in lower_err:
            action = "dom_filter_bypass"
        elif "unauthorized" in lower_err or "session" in lower_err or "login" in lower_err:
            action = "auth_reconnect"
        elif "timeout" in lower_err or "not found" in lower_err:
            action = "retry_alt_selector" if retry_count < 2 else "abort_and_notify_user"
        else:
            action = "abort_and_notify_user"

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        res = {"action": action, "source": "offline_heuristic"}
        self.log_decision("failure_recovery", state, res, duration)
        return res

# Global instance
jev_router = JevRouter()
