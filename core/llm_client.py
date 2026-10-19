import os
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from core.credentials_manager import CredentialVault

logger = logging.getLogger(__name__)

# Define schema to eliminate verbose conversational tokens
class AdaptationOutput(BaseModel):
    match_score: int = Field(..., description="Score from 0 to 100 on alignment.")
    should_apply: bool = Field(..., description="True if match_score >= 75.")
    tailored_summary: str = Field(..., description="A 3-sentence summary highlighting matching skills.")
    custom_responses: dict = Field(default_factory=dict, description="Key-value pairs answering application specific questions.")

class GeminiMatcherClient:
    def __init__(self, api_key: Optional[str] = None):
        vault = CredentialVault()
        self.api_key = api_key or vault.get_gemini_api_key() or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.model_name = "gemini-3.8-flash"
        
        if GENAI_AVAILABLE and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize google-genai client: {e}")

    def answer_form_question(
        self,
        question: str,
        field_type: str = "text",
        options: Optional[List[str]] = None,
        job_context: str = "",
        profile_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Uses Gemini 2.5 Pro to generate an authentic, ATS-optimized answer for a specific application form question.
        Handles text prompts, essays, and selects best matching option from dropdown/radio choices.
        """
        # STEP 1: SECOND BRAIN LOOKUP (0-TOKEN INSTANT HIT)
        try:
            from core.second_brain import SecondBrain
            brain = SecondBrain()
            cached = brain.lookup_memory(question, options=options)
            if cached:
                ans, src = cached
                logger.info(f"🧠 [Second Brain] 0-Token Hit for '{question[:60]}' -> '{ans}' ({src})")
                return ans
        except Exception as e:
            logger.debug(f"Second Brain lookup error: {e}")

        if not profile_data:
            profile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "profile.json")
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, "r", encoding="utf-8") as f:
                        profile_data = json.load(f)
                except Exception:
                    profile_data = {}
            else:
                profile_data = {}

        # Safe deterministic fallbacks if no client or key
        if not self.client:
            q_lower = question.lower()
            if options:
                for opt in options:
                    ol = opt.lower()
                    if ("sponsor" in q_lower or "future" in q_lower) and "yes" in ol:
                        return opt
                    if "authorized" in q_lower and "yes" in ol:
                        return opt
                    if "veteran" in q_lower and "not" in ol:
                        return opt
                    if "disability" in q_lower and ("no" in ol or "not" in ol or "do not wish" in ol):
                        return opt
                return options[0] if options else ""
            if "why" in q_lower or "interest" in q_lower:
                return "I am excited to apply my cybersecurity, incident response, and cloud engineering background to contribute to high-impact security initiatives."
            if "experience" in q_lower or "project" in q_lower:
                return "My experience includes security engineering, vulnerability management, and implementing secure cloud architectures during my graduate studies at Southwest Minnesota State University."
            return "Yes"

        system_instruction = (
            "You are an elite candidate copilot answering an employer's job application form question. "
            "You must strictly adhere to the candidate's authentic profile facts: "
            "Candidate: Shadman Ahsan, Address: 202 N 1st St Apt 6097, Marshall, MN 56258, Phone: 507-530-5801. "
            "Education: M.S. in Cybersecurity at Southwest Minnesota State University (GPA 4.00, Student ID 17280072), "
            "B.S. in Computer Science & Engineering. "
            "Work Authorization: Eligible for CPT and 3-Year STEM OPT on F-1 Visa; Authorized to work in US = Yes; "
            "Will require sponsorship now or in the future = Yes. "
            "Never hallucinate fake US citizenship, military clearance, or unauthorized credentials. "
            "If options are provided, you MUST reply with the EXACT text of the single best matching option. "
            "If this is an open-ended essay or textarea, keep it concise, impactful, professional, and under 150 words."
        )

        prompt = f"""
CANDIDATE TRUTH PROFILE:
{json.dumps(profile_data, indent=2)}

TARGET JOB CONTEXT:
{job_context}

QUESTION ASKED BY EMPLOYER:
{question}

FIELD TYPE: {field_type}
OPTIONS (if dropdown or radio selection): {json.dumps(options or [])}

Respond ONLY with the final answer string. Do not wrap in markdown quotes.
"""
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2
            )
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
            except Exception:
                response = self.client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt,
                    config=config
                )
            ans = response.text.strip().strip('"').strip("'")
            final_ans = ans
            if options:
                # Match closest option text
                for opt in options:
                    if opt.lower() == ans.lower():
                        final_ans = opt
                        break
                else:
                    for opt in options:
                        if ans.lower() in opt.lower() or opt.lower() in ans.lower():
                            final_ans = opt
                            break

            # Memorize into Second Brain for 0-token future runs
            try:
                from core.second_brain import SecondBrain
                SecondBrain().store_memory(
                    question=question,
                    answer=final_ans,
                    category="DYNAMIC_QA",
                    field_type=field_type,
                    source="GEMINI_FLASH"
                )
            except Exception:
                pass

            return final_ans
        except Exception as e:
            logger.error(f"[-] Gemini application question answering error: {e}")
            if options:
                return options[0]
            return "Yes"

    def analyze_and_tailor(self, profile_data: dict, job_description: str, form_questions: list = None) -> dict:
        """Evaluates a job posting against profile data and extracts targeted form values."""
        
        system_instruction = (
            "You are an elite, highly precise ATS parsing agent. Analyze the provided resume "
            "and candidate profile against the target job description. Identify exact alignment points. "
            "If any specific open-ended application questions are provided, draft tailored, professional "
            "responses highlighting only the candidate's authentic experience that directly answers the query."
        )

        prompt = f"""
        CANDIDATE STRUCTURAL PROFILE:
        {json.dumps(profile_data, indent=2)}

        TARGET JOB DESCRIPTION:
        {job_description}

        APPLICATION FORM QUESTIONS TO ANSWER:
        {json.dumps(form_questions if form_questions else [], indent=2)}
        """

        if not self.client:
            logger.warning("GeminiMatcherClient uninitialized (no API key). Using deterministic fallback.")
            return {
                "match_score": 75,
                "should_apply": True,
                "tailored_summary": "Strong candidate with comprehensive background in systems administration, network security, and secure software engineering.",
                "custom_responses": {}
            }

        try:
            gen_config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,  # Lower temperature guarantees deterministic matching
                response_mime_type="application/json",
                response_schema=AdaptationOutput,
            )
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config,
                )
            except Exception:
                response = self.client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt,
                    config=gen_config,
                )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"[-] Gemini API Operational Error: {e}")
            return {
                "match_score": 0,
                "should_apply": False,
                "tailored_summary": "",
                "custom_responses": {}
            }

class GeminiClient:
    """Backward-compatible general purpose Gemini client."""
    def __init__(self, api_key: Optional[str] = None):
        self.matcher = GeminiMatcherClient(api_key=api_key)
        self.client = self.matcher.client

    def generate_json(self, prompt: str, system_instruction: str = "", model: str = "gemini-2.5-pro") -> Dict[str, Any]:
        if not self.client:
            logger.warning("Gemini Client not initialized. Returning mock/default response.")
            return {"error": "API key missing or client uninitialized"}
            
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2
            )
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error calling Gemini model {model}: {e}")
            if model != "gemini-2.5-flash":
                try:
                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                    response = self.client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=config
                    )
                    return json.loads(response.text)
                except Exception as fallback_err:
                    logger.error(f"Fallback to gemini-2.5-flash failed: {fallback_err}")
            return {"error": str(e)}

    def generate_text(self, prompt: str, system_instruction: str = "", model: str = "gemini-2.5-pro") -> str:
        if not self.client:
            return "Gemini Client uninitialized."
            
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3
            )
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating text with {model}: {e}")
            return f"Error generating text: {e}"

    def answer_form_question(
        self,
        question: str,
        field_type: str = "text",
        options: Optional[List[str]] = None,
        job_context: str = "",
        profile_data: Optional[Dict[str, Any]] = None
    ) -> str:
        return self.matcher.answer_form_question(
            question=question,
            field_type=field_type,
            options=options,
            job_context=job_context,
            profile_data=profile_data
        )
