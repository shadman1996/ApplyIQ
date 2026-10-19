import os
import sys
import time
import socket
import subprocess
import threading
import urllib.request
import logging
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("jarvis.launcher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PORT = 8000
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0

def run_fastapi_server():
    import uvicorn
    logger.info(f"[J.A.R.V.I.S. Core] Starting FastAPI server on {URL}...")
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="warning")

def wait_for_server(timeout: int = 10) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(f"{URL}/api/status", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def find_browser_executable() -> Optional[str]:
    import glob
    import shutil
    candidates = [
        "/opt/google/chrome/google-chrome",
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for c in ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser"]:
        p = shutil.which(c)
        if p and p not in candidates:
            candidates.append(p)

    pw_matches = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")), reverse=True)
    candidates.extend(pw_matches)

    for cand in candidates:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None

def launch_desktop_window():
    print("\n" + "=" * 75)
    print("🤖 INITIALIZING J.A.R.V.I.S. CYBERSECURITY SWARM DESKTOP COMMAND CENTER")
    print("=" * 75)

    # 1. Start backend server if not running
    if not is_port_in_use(PORT):
        server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
        server_thread.start()
        print(f"[*] Booting neural server on {URL}...")
        if not wait_for_server():
            print("[!] Failed to verify server health. Exiting.")
            return False
    else:
        print(f"[*] Neural server already active on {URL}")

    # 2. Locate browser for Standalone Desktop App Mode
    browser_bin = find_browser_executable()
    user_data_dir = os.path.join(PROJECT_ROOT, "config", "jarvis_browser_profile")
    os.makedirs(user_data_dir, exist_ok=True)

    print(f"[*] J.A.R.V.I.S. HUD available at: {URL}")
    print("[*] Launching standalone holographic desktop window...")

    if browser_bin:
        # Chrome / Chromium standalone app mode (no browser chrome, pure desktop app experience)
        cmd = [
            browser_bin,
            f"--app={URL}",
            "--window-size=1520,950",
            "--window-position=50,50",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check"
        ]
        try:
            proc = subprocess.Popen(cmd)
            print("[*] J.A.R.V.I.S. Desktop Command Window is now open.")
            print("    Press Ctrl+C to close desktop interface.\n")
            proc.wait()
            return True
        except KeyboardInterrupt:
            print("\n[*] Shutting down J.A.R.V.I.S. Desktop Window.")
            proc.terminate()
            return True
        except Exception as e:
            logger.error(f"Failed to launch standalone app mode: {e}")

    # Fallback to python webbrowser
    import webbrowser
    webbrowser.open(URL)
    print(f"[*] Opened J.A.R.V.I.S. in default desktop browser: {URL}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] J.A.R.V.I.S. stopped.")

if __name__ == "__main__":
    launch_desktop_window()
