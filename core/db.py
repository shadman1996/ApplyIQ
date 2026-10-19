import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "applications.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Enable Write-Ahead Logging (WAL) mode for fast concurrent operations
    conn.execute("PRAGMA journal_mode=WAL;")
    
    cursor = conn.cursor()
    
    # Jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT,
        url TEXT UNIQUE NOT NULL,
        source TEXT,
        ats_type TEXT,
        date_posted TEXT,
        raw_description TEXT,
        match_score INTEGER DEFAULT 0,
        match_reason TEXT,
        status TEXT DEFAULT 'DISCOVERED', -- DISCOVERED, EVALUATED, APPROVED, REJECTED, SUBMITTED, FAILED
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Applications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        submission_method TEXT, -- DIRECT_API, PLAYWRIGHT_STEALTH
        status TEXT DEFAULT 'SUCCESS',
        tailored_answers JSON,
        error_log TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    );
    """)
    
    # Logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level TEXT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()

def save_job(job: Dict[str, Any]) -> Optional[int]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO jobs (title, company, location, url, source, ats_type, raw_description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET title=excluded.title, company=excluded.company
        """, (
            job.get('title'),
            job.get('company'),
            job.get('location'),
            job.get('url'),
            job.get('source', 'GitHub'),
            job.get('ats_type', 'UNKNOWN'),
            job.get('raw_description', ''),
            'DISCOVERED'
        ))
        conn.commit()
        job_id = cursor.lastrowid
        return job_id
    except Exception as e:
        print(f"[DB Error] Failed to save job: {e}")
        return None
    finally:
        conn.close()

def update_job_evaluation(job_id: int, score: int, reason: str, status: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE jobs SET match_score = ?, match_reason = ?, status = ? WHERE id = ?
    """, (score, reason, status, job_id))
    conn.commit()
    conn.close()

def get_jobs_by_status(status: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE status = ?", (status,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def log_application(job_id: int, method: str, status: str, answers: Dict = None, error: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO applications (job_id, submission_method, status, tailored_answers, error_log)
    VALUES (?, ?, ?, ?, ?)
    """, (job_id, method, status, json.dumps(answers or {}), error))
    
    # Also update job status
    cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
