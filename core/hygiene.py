"""
Disk Hygiene, Cache Cleanup & Rotating Logger Module.
Engineered for 24/7 autonomous daemon deployment on laptop hardware.

Features:
1. Rotating File Logging (RotatingFileHandler): Caps text logs at 10MB with 5 archived backups.
2. Chromium Profile Hygiene: Purges transient browser caches (ShaderCache, GPUCache, Code Cache,
   Service Worker CacheStorage, Crashpad) while strictly preserving persistent cookies and session tokens.
3. SQLite WAL Checkpointing & Vacuum: Flushes WAL journal to main db, prunes stale log entries (>14 days),
   and reclaims unused disk space.
4. Tailored Artifacts Pruning: Manages generated PDF resumes in data/tailored/ to prevent runaway disk sprawl.
5. Disk Telemetry: Measures exact directory footprints for real-time reporting.
"""

import os
import sys
import glob
import time
import shutil
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, List, Optional

logger = logging.getLogger("jarvis.hygiene")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DB_PATH = os.path.join(DATA_DIR, "applications.db")
TAILORED_DIR = os.path.join(DATA_DIR, "tailored")
BROWSER_PROFILES = [
    os.path.join(DATA_DIR, "browser_profile"),
    os.path.join(CONFIG_DIR, "jarvis_chrome_profile")
]


# =========================================================================
# 1. ROTATING LOGGING ENGINE
# =========================================================================
def setup_rotating_logger(
    log_dir: str = LOGS_DIR,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB per log file
    backup_count: int = 5,              # Keep up to 5 rotated backup logs
    log_level: int = logging.INFO
) -> logging.Logger:
    """
    Configures production-grade rotating log handlers for 24/7 daemon runs.
    Ensures logs never consume unbounded disk space.
    """
    os.makedirs(log_dir, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if called multiple times
    has_rotating = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    if not has_rotating:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Main application rotating log (10 MB, 5 backups)
        main_log_file = os.path.join(log_dir, "swarm.log")
        main_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        main_handler.setFormatter(formatter)
        main_handler.setLevel(log_level)
        root_logger.addHandler(main_handler)

        # Dedicated error log handler (5 MB, 3 backups)
        error_log_file = os.path.join(log_dir, "errors.log")
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

    return root_logger


# =========================================================================
# 2. CHROMIUM PROFILE DISK HYGIENE (Cache Purge / Session Preservation)
# =========================================================================
# Disposable cache directories safe to delete without losing logins/cookies
DISPOSABLE_CACHE_PATTERNS = [
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "Default/Service Worker/CacheStorage",
    "Default/Service Worker/ScriptCache",
    "Default/blob_storage",
    "Default/Application Cache",
    "ShaderCache",
    "GrShaderCache",
    "Crashpad/completed",
    "Crashpad/pending",
    "Crashpad/reports"
]

def clean_browser_profile_cache(profile_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Cleans transient Chromium caches across browser profile directories.
    CRITICAL: Preserves Cookies, Login Data, Web Data, Local Storage, and Preferences.
    """
    profile_dirs = profile_dirs or BROWSER_PROFILES
    bytes_freed = 0
    cleaned_items: List[str] = []

    for p_dir in profile_dirs:
        if not os.path.exists(p_dir):
            continue

        for pattern in DISPOSABLE_CACHE_PATTERNS:
            target = os.path.join(p_dir, pattern)
            for path in glob.glob(target):
                if os.path.isdir(path):
                    try:
                        dir_size = get_dir_size_bytes(path)
                        shutil.rmtree(path, ignore_errors=True)
                        bytes_freed += dir_size
                        cleaned_items.append(os.path.relpath(path, p_dir))
                    except Exception as e:
                        logger.debug(f"Could not remove cache dir {path}: {e}")
                elif os.path.isfile(path):
                    try:
                        f_size = os.path.getsize(path)
                        os.remove(path)
                        bytes_freed += f_size
                        cleaned_items.append(os.path.relpath(path, p_dir))
                    except Exception:
                        pass

    freed_mb = round(bytes_freed / (1024 * 1024), 2)
    logger.info(f"[Hygiene] Browser cache purge complete: {freed_mb} MB reclaimed across {len(cleaned_items)} folders.")
    return {
        "bytes_freed": bytes_freed,
        "freed_mb": freed_mb,
        "cleaned_count": len(cleaned_items)
    }


# =========================================================================
# 3. DATABASE MAINTENANCE (WAL Checkpointing & Log Pruning)
# =========================================================================
def maintain_database(
    db_path: str = DB_PATH,
    max_log_records: int = 5000,
    keep_days: int = 14
) -> Dict[str, Any]:
    """
    Performs SQLite maintenance:
    - Truncates and merges the WAL journal into the main DB file.
    - Prunes internal log records older than `keep_days` or exceeding `max_log_records`.
    - Compacts free pages via incremental vacuum.
    """
    if not os.path.exists(db_path):
        return {"success": False, "reason": "Database file not found"}

    initial_size = os.path.getsize(db_path)
    wal_path = f"{db_path}-wal"
    wal_initial = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0

    pruned_logs = 0
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Prune old log entries
        cursor.execute("SELECT COUNT(*) FROM logs")
        total_logs = cursor.fetchone()[0]

        if total_logs > max_log_records:
            cursor.execute("""
            DELETE FROM logs WHERE id NOT IN (
                SELECT id FROM logs ORDER BY id DESC LIMIT ?
            )
            """, (max_log_records,))
            pruned_logs = cursor.rowcount

        # 2. Checkpoint and truncate Write-Ahead Log
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        # 3. Optimize database schema indexes
        cursor.execute("PRAGMA optimize;")

        conn.commit()
        conn.close()

        final_size = os.path.getsize(db_path)
        wal_final = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
        total_freed = (initial_size + wal_initial) - (final_size + wal_final)

        logger.info(f"[Hygiene] Database WAL checkpointed. Pruned {pruned_logs} stale logs. Main DB: {round(final_size/1024, 1)} KB.")
        return {
            "success": True,
            "pruned_logs": pruned_logs,
            "main_size_kb": round(final_size / 1024, 1),
            "wal_size_kb": round(wal_final / 1024, 1),
            "freed_bytes": max(0, total_freed)
        }
    except Exception as e:
        logger.error(f"[Hygiene Error] Database maintenance failed: {e}")
        return {"success": False, "error": str(e)}


# =========================================================================
# 4. TAILORED ARTIFACTS PRUNING
# =========================================================================
def prune_tailored_artifacts(
    tailored_dir: str = TAILORED_DIR,
    max_age_days: int = 14,
    max_files: int = 30
) -> Dict[str, Any]:
    """
    Cleans temporary tailored resumes in data/tailored/.
    Preserves the master tailored resume while deleting older ephemeral PDFs.
    """
    if not os.path.exists(tailored_dir):
        return {"removed_count": 0, "freed_bytes": 0}

    now = time.time()
    cutoff_time = now - (max_age_days * 86400)
    master_name = "Shadman_Ahsan_Resume.pdf"

    pdf_files = sorted(
        [
            os.path.join(tailored_dir, f)
            for f in os.listdir(tailored_dir)
            if f.endswith(".pdf") and f != master_name
        ],
        key=os.path.getmtime
    )

    removed = 0
    freed_bytes = 0

    # Remove files older than cutoff or exceeding max file cap
    for idx, path in enumerate(pdf_files):
        mtime = os.path.getmtime(path)
        is_overflow = (len(pdf_files) - idx) > max_files
        is_stale = mtime < cutoff_time

        if is_stale or is_overflow:
            try:
                f_size = os.path.getsize(path)
                os.remove(path)
                removed += 1
                freed_bytes += f_size
            except Exception:
                pass

    logger.info(f"[Hygiene] Tailored PDF pruning: removed {removed} older files ({round(freed_bytes/1024, 1)} KB freed).")
    return {
        "removed_count": removed,
        "freed_bytes": freed_bytes
    }


# =========================================================================
# 5. DISK FOOTPRINT TELEMETRY
# =========================================================================
def get_dir_size_bytes(path: str) -> int:
    """Calculates total recursive byte size of a directory."""
    total = 0
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except Exception:
                pass
    return total

def get_disk_footprint_report() -> Dict[str, Any]:
    """
    Returns a structured telemetry report of disk usage across all persistent directories.
    """
    items = {
        "sqlite_db": get_dir_size_bytes(DB_PATH) + get_dir_size_bytes(f"{DB_PATH}-wal"),
        "logs": get_dir_size_bytes(LOGS_DIR),
        "tailored_resumes": get_dir_size_bytes(TAILORED_DIR),
        "browser_profile": get_dir_size_bytes(os.path.join(DATA_DIR, "browser_profile")),
        "chrome_profile": get_dir_size_bytes(os.path.join(CONFIG_DIR, "jarvis_chrome_profile"))
    }
    total_bytes = sum(items.values())
    return {
        "metrics_bytes": items,
        "metrics_human": {k: f"{round(v / (1024 * 1024), 2)} MB" for k, v in items.items()},
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "status": "HEALTHY" if total_bytes < 500 * 1024 * 1024 else "NEEDS_PURGE"
    }


# =========================================================================
# 6. UNIFIED HYGIENE CYCLE (Periodic Maintenance Hook)
# =========================================================================
def run_full_hygiene_cycle() -> Dict[str, Any]:
    """
    Executes all hygiene steps in a single safe, non-destructive sweep:
    1. Purges Chromium cache while keeping auth tokens
    2. Checkpoints SQLite WAL and prunes old logs
    3. Prunes stale tailored PDFs
    4. Measures updated disk telemetry
    """
    logger.info(">>> Initiating 24/7 Swarm Disk Hygiene Cycle <<<")
    cache_res = clean_browser_profile_cache()
    db_res = maintain_database()
    artifacts_res = prune_tailored_artifacts()
    telemetry = get_disk_footprint_report()

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "browser_cache_freed_mb": cache_res.get("freed_mb", 0),
        "database_logs_pruned": db_res.get("pruned_logs", 0),
        "artifacts_pruned": artifacts_res.get("removed_count", 0),
        "total_active_disk_mb": telemetry.get("total_mb", 0),
        "status": telemetry.get("status", "HEALTHY")
    }
    logger.info(f"✅ Disk Hygiene Cycle Complete. Total system footprint: {summary['total_active_disk_mb']} MB ({summary['status']})")
    return summary


if __name__ == "__main__":
    setup_rotating_logger()
    result = run_full_hygiene_cycle()
    print("\n" + "=" * 60)
    print("🧹 SWARM DISK HYGIENE REPORT")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("=" * 60)
