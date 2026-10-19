"""
Second Brain: High-Efficiency Memory & Token-Optimization Engine.
Inspired by Antigravity Brain architecture.
Caches verified candidate truths, behavioral narratives, and ATS question answers.
Guarantees 0-token instant resolution for known questions and ultra-lean isolated prompts for novel queries.
"""

import os
import re
import json
import sqlite3
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("jarvis.second_brain")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "applications.db")


class SecondBrain:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecondBrain, cls).__new__(cls)
            cls._instance._init_db()
            cls._instance._seed_authoritative_memory()
        return cls._instance

    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS second_brain_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                question_key TEXT UNIQUE NOT NULL,
                original_prompt TEXT NOT NULL,
                field_type TEXT,
                answer_content TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                tokens_saved INTEGER DEFAULT 0,
                source TEXT DEFAULT 'PRE_SEEDED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[Second Brain Init Error] {e}")

    def _normalize_key(self, text: str) -> str:
        """Converts raw question prompt to normalized semantic key."""
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
        words = [w for w in clean.split() if w not in ["the", "a", "an", "is", "are", "do", "you", "your", "please", "to", "in", "for", "of", "and"]]
        return " ".join(words[:12])

    def _seed_authoritative_memory(self):
        """Pre-seeds candidate ground truth so common questions cost 0 tokens."""
        seeds = [
            # Work Authorization (Strict F-1 CPT/OPT Compliance)
            ("WORK_AUTH", "legally authorized to work in the united states", "Are you legally authorized to work in the United States?", "Yes", "select"),
            ("WORK_AUTH", "require sponsorship now or future h1b", "Will you now or in the future require visa sponsorship?", "Yes", "select"),
            ("WORK_AUTH", "current visa or immigration status", "What is your current visa status?", "F-1 (Eligible for CPT & 3-Year STEM OPT)", "select"),
            ("WORK_AUTH", "security clearance level", "Do you hold an active U.S. Security Clearance?", "None / Eligible for Public Trust", "select"),
            ("WORK_AUTH", "us citizen or permanent resident", "Are you a U.S. Citizen or Lawful Permanent Resident?", "No", "select"),

            # Academic & Institution Grounding (SMSU Transcript 4.00 GPA)
            ("EDUCATION", "institution university college school name", "School / University Name", "Southwest Minnesota State University", "combobox"),
            ("EDUCATION", "degree level highest degree", "Degree Level", "Master's Degree", "select"),
            ("EDUCATION", "major field of study", "Major / Program of Study", "Cybersecurity", "text"),
            ("EDUCATION", "cumulative gpa grade point average", "Cumulative GPA", "4.00", "text"),
            ("EDUCATION", "graduation date completion date", "Anticipated Graduation Date", "05/2027", "text"),
            ("EDUCATION", "student identification campus id", "Student ID", "17280072", "text"),

            # Contact & Location Grounding (SMSU Campus Address)
            ("IDENTITY", "home address street line 1", "Street Address", "202 N 1st St Apt 6097", "text"),
            ("IDENTITY", "city state zip postal code", "Location", "Marshall, MN 56258", "text"),
            ("IDENTITY", "phone mobile telephone number", "Phone Number", "+1 (507) 530-5801", "text"),
            ("IDENTITY", "primary email address", "Email", "shadman.ahsan.us@gmail.com", "text"),
            ("IDENTITY", "linkedin profile url link", "LinkedIn Profile", "https://linkedin.com/in/shadman-ahsan", "text"),
            ("IDENTITY", "github portfolio code profile", "GitHub Profile", "https://github.com/shadman1996", "text"),

            # Voluntary EEO Demographics
            ("EEO", "veteran protected veteran status", "Veteran Status", "I am not a protected veteran", "select"),
            ("EEO", "disability form cc305 physical mental", "Disability Status", "No, I do not have a disability", "select"),
            ("EEO", "gender identity sex", "Gender", "Male", "select"),
            ("EEO", "race ethnicity origin", "Race / Ethnicity", "Asian", "select"),
            ("EEO", "hispanic latino origin", "Hispanic or Latino", "No", "select"),

            # Standard Operational Preferences
            ("OPERATIONS", "willing to relocate for position", "Are you willing to relocate?", "Yes", "select"),
            ("OPERATIONS", "earliest start date notice period", "Earliest Start Date", "May 2027 (Summer Internship Window)", "text"),
            ("OPERATIONS", "years of python experience", "Years of experience with Python?", "3", "text"),
            ("OPERATIONS", "years of security engineering experience", "Years of Cybersecurity experience?", "2", "text"),
        ]

        try:
            conn = self._get_connection()
            c = conn.cursor()
            for cat, q_key, prompt, ans, f_type in seeds:
                c.execute("""
                INSERT OR IGNORE INTO second_brain_memory (category, question_key, original_prompt, field_type, answer_content, source)
                VALUES (?, ?, ?, ?, ?, 'PRE_SEEDED')
                """, (cat, q_key, prompt, f_type, ans))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Seed note: {e}")

    def lookup_memory(self, question: str, options: Optional[List[str]] = None) -> Optional[Tuple[str, str]]:
        """
        Fast local memory lookup.
        Returns (answer_content, source_label) or None if question is unseen.
        Costs 0 tokens.
        """
        if not question or len(question.strip()) < 3:
            return None

        q_lower = question.lower()
        key = self._normalize_key(question)

        try:
            conn = self._get_connection()
            c = conn.cursor()

            # 1. Exact Key Match
            c.execute("SELECT id, answer_content, source, hit_count, tokens_saved FROM second_brain_memory WHERE question_key = ?", (key,))
            row = c.fetchone()

            if not row:
                # 2. Anchor Keyword & Overlap Matching
                c.execute("SELECT id, question_key, answer_content, source, hit_count, tokens_saved FROM second_brain_memory")
                all_rows = c.fetchall()
                best_match = None
                max_score = 0

                q_words = set(key.split())

                for r in all_rows:
                    r_key = r["question_key"]
                    r_words = set(r_key.split())
                    common = r_words.intersection(q_words)
                    score = len(common)

                    # Critical domain keyword anchors
                    if "gpa" in q_words and "gpa" in r_words:
                        score += 5
                    if ("university" in q_words or "school" in q_words) and ("university" in r_words or "school" in r_words):
                        score += 4
                    if "sponsorship" in q_words and "sponsorship" in r_words:
                        score += 5
                    if "authorized" in q_words and "authorized" in r_words:
                        score += 5
                    if "relocate" in q_words and "relocate" in r_words:
                        score += 5
                    if "veteran" in q_words and "veteran" in r_words:
                        score += 5
                    if "disability" in q_words and "disability" in r_words:
                        score += 5

                    if score > max_score and score >= 2:
                        max_score = score
                        best_match = r

                if best_match:
                    row = best_match

            if row:
                m_id = row["id"]
                raw_ans = row["answer_content"]
                new_hits = (row["hit_count"] or 0) + 1
                new_saved = (row["tokens_saved"] or 0) + 350  # ~350 tokens saved per hit

                c.execute("""
                UPDATE second_brain_memory
                SET hit_count = ?, tokens_saved = ?, last_used_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (new_hits, new_saved, m_id))
                conn.commit()
                conn.close()

                # If options are provided, select exact matching choice
                if options:
                    for opt in options:
                        if opt.lower() == raw_ans.lower():
                            return opt, "SECOND_BRAIN_EXACT"
                        if raw_ans.lower() in opt.lower() or opt.lower() in raw_ans.lower():
                            return opt, "SECOND_BRAIN_FUZZY"
                    # Semantic yes/no fallback
                    if raw_ans.lower() in ("yes", "true", "1"):
                        for opt in options:
                            if "yes" in opt.lower() or "authorized" in opt.lower() or "require" in opt.lower():
                                return opt, "SECOND_BRAIN_AFFIRMATIVE"
                    return options[0], "SECOND_BRAIN_FALLBACK"

                return raw_ans, "SECOND_BRAIN_0_TOKEN"

            conn.close()
            return None

        except Exception as e:
            logger.debug(f"Lookup error: {e}")
            return None

    def store_memory(
        self,
        question: str,
        answer: str,
        category: str = "DYNAMIC_QA",
        field_type: str = "text",
        source: str = "GEMINI_FLASH"
    ):
        """
        Stores newly generated answer from Gemini into Second Brain.
        Ensures the same question will cost 0 tokens next time it is encountered.
        """
        if not question or not answer:
            return

        key = self._normalize_key(question)
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("""
            INSERT INTO second_brain_memory (category, question_key, original_prompt, field_type, answer_content, source)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(question_key) DO UPDATE SET
                answer_content = excluded.answer_content,
                last_used_at = CURRENT_TIMESTAMP
            """, (category, key, question, field_type, answer, source))
            conn.commit()
            conn.close()
            logger.info(f"🧠 [Second Brain] Memorized answer for '{question[:60]}' (Tokens saved for future runs).")
        except Exception as e:
            logger.debug(f"Store error: {e}")

    def lookup_answer(self, question: str, options: Optional[List[str]] = None) -> Optional[str]:
        """Convenience method returning just the answer string if found in Second Brain."""
        res = self.lookup_memory(question, options)
        return res[0] if res else None

    def learn_answer(
        self,
        question: str,
        answer: str,
        category: str = "DYNAMIC_QA",
        field_type: str = "text"
    ):
        """Convenience method to memorize a newly generated answer."""
        return self.store_memory(
            question=question,
            answer=answer,
            category=category,
            field_type=field_type,
            source="LEARNED_DYNAMIC"
        )


    def get_telemetry(self) -> Dict[str, Any]:
        """Returns Second Brain token savings and cache statistics."""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("SELECT COUNT(*), SUM(hit_count), SUM(tokens_saved) FROM second_brain_memory")
            total_items, total_hits, total_saved = c.fetchone()
            conn.close()

            hits = total_hits or 0
            saved_tokens = total_saved or 0
            # Approx cost saved ($0.075 per 1M input tokens on Gemini Flash)
            cost_saved = (saved_tokens / 1_000_000) * 0.10

            return {
                "total_memories": total_items or 0,
                "zero_token_hits": hits,
                "total_tokens_saved": saved_tokens,
                "cost_saved_usd": round(cost_saved, 5),
                "status": "ONLINE",
                "mode": "ANTIGRAVITY_SECOND_BRAIN"
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """Returns all persisted ground truths and learned responses."""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("""
                SELECT id, category, question_key, original_prompt, field_type, answer_content, 
                       hit_count, tokens_saved, source, created_at, last_used_at 
                FROM second_brain_memory 
                ORDER BY hit_count DESC, id ASC
            """)
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch memories: {e}")
            return []

    def upsert_memory(self, category: str, prompt: str, answer: str, field_type: str = "text") -> bool:
        """Manually adds or edits a ground truth memory item."""
        try:
            key = self._normalize_key(prompt)
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("""
            INSERT INTO second_brain_memory (category, question_key, original_prompt, field_type, answer_content, source)
            VALUES (?, ?, ?, ?, ?, 'USER_ADMIN')
            ON CONFLICT(question_key) DO UPDATE SET
                category = excluded.category,
                answer_content = excluded.answer_content,
                field_type = excluded.field_type,
                last_used_at = CURRENT_TIMESTAMP
            """, (category, key, prompt, field_type, answer))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert memory: {e}")
            return False

# Global singleton instance
second_brain = SecondBrain()

