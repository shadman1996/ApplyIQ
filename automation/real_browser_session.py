import os
import sys
import json
import time
import asyncio
import logging
import urllib.request
import subprocess
import shutil
import glob
from typing import Dict, Any, Tuple, Optional
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.matcher import load_profile
from automation.ats_form_filler import ATSFormFiller

logger = logging.getLogger("jarvis.browser")

STORAGE_STATE_PATH = os.path.join(PROJECT_ROOT, "config", "storage_state.json")
CHROME_USER_DATA_DIR = os.path.expanduser("~/.config/google-chrome")
JARVIS_CHROME_DIR = os.path.join(PROJECT_ROOT, "config", "jarvis_chrome_profile")
CDP_URL = "http://127.0.0.1:9222"

PORTAL_URLS = {
    "google": "https://accounts.google.com",
    "gmail": "https://mail.google.com",
    "linkedin": "https://www.linkedin.com/login",
    "indeed": "https://secure.indeed.com/account/login",
    "handshake": "https://app.joinhandshake.com/login",
    "migratemate": "https://migratemate.co/login",
    "workday": "https://www.myworkday.com",
    "glassdoor": "https://www.glassdoor.com/profile/login_input.htm",
    "wellfound": "https://wellfound.com/login"
}

def find_chrome_executable() -> Optional[str]:
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

def kill_process_on_port(port: int = 9222) -> None:
    """Kill any zombie process listening on the CDP debugging port (absorbed from ApplyPilot)."""
    try:
        res = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        for pid_str in res.stdout.strip().splitlines():
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                try:
                    os.kill(pid, 9)
                    logger.info(f"[Process Manager] Terminated zombie process {pid} on port {port}")
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"[Process Manager] Port sweep for {port}: {e}")

def suppress_chrome_restore_nag(profile_dir: str) -> None:
    """Suppress Chrome's 'Restore pages?' crash recovery popup (absorbed from ApplyPilot)."""
    prefs_file = os.path.join(profile_dir, "Default", "Preferences")
    if not os.path.exists(prefs_file):
        return
    try:
        with open(prefs_file, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        prefs.setdefault("profile", {})["exit_type"] = "Normal"
        prefs.setdefault("session", {})["restore_on_startup"] = 4
        prefs.setdefault("session", {}).pop("startup_urls", None)
        prefs["credentials_enable_service"] = False
        prefs.setdefault("password_manager", {})["saving_enabled"] = False
        prefs.setdefault("autofill", {})["profile_enabled"] = False
        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception as e:
        logger.debug(f"[Process Manager] Could not patch preferences: {e}")

def cleanup_profile_locks(profile_dir: str) -> None:
    """Clean up dangling singleton lock files if Chrome exited unexpectedly."""
    for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        lock_path = os.path.join(profile_dir, lock_name)
        if os.path.exists(lock_path) or os.path.islink(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass

def is_cdp_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_cdp_chrome_running() -> bool:
    if is_cdp_ready():
        return True

    # Sweep dead processes holding port 9222 and clean locks (absorbed from ApplyPilot)
    kill_process_on_port(9222)
    cleanup_profile_locks(JARVIS_CHROME_DIR)

    os.makedirs(os.path.join(JARVIS_CHROME_DIR, "Default"), exist_ok=True)
    suppress_chrome_restore_nag(JARVIS_CHROME_DIR)

    # Sync Login Data (saved passwords) from main Chrome profile if available
    src_login = os.path.expanduser("~/.config/google-chrome/Default/Login Data")
    dst_login = os.path.join(JARVIS_CHROME_DIR, "Default", "Login Data")
    if os.path.exists(src_login):
        try:
            shutil.copy2(src_login, dst_login)
            logger.info("[Real Chrome Bridge] Synced real Chrome Login Data (saved passwords).")
        except Exception as e:
            logger.warning(f"Could not copy Login Data: {e}")

    chrome_bin = find_chrome_executable()
    if not chrome_bin:
        logger.warning("[Real Chrome Bridge] No Google Chrome or Chromium executable found for CDP.")
        return False

    logger.info(f"[Real Chrome Bridge] Spawning {chrome_bin} with CDP port 9222 on desktop...")
    cmd = [
        chrome_bin,
        f"--user-data-dir={JARVIS_CHROME_DIR}",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--password-store=basic",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble"
    ]
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        cmd.append("--headless=new")

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        logger.warning(f"[Real Chrome Bridge] Failed to spawn Chrome process: {e}")
        return False

    # Wait up to 5 seconds for port 9222
    for _ in range(10):
        time.sleep(0.5)
        if is_cdp_ready():
            logger.info("[Real Chrome Bridge] Chrome CDP port 9222 successfully established.")
            return True

    return False

class RealBrowserSessionManager:
    """
    Directly attaches to Google Chrome via CDP (port 9222).
    Guarantees:
    1. Saved Chrome passwords autofill automatically.
    2. Google SSO / LinkedIn active sessions are shared.
    3. Live application forms are populated and kept visible on screen for candidate review.
    """

    @classmethod
    def get_auth_status(cls) -> Dict[str, Any]:
        """
        Inspects config/storage_state.json to check for authenticated sessions.
        """
        status = {
            "google": {"connected": False, "user": None, "label": "NOT DETECTED"},
            "linkedin": {"connected": False, "user": None, "label": "NOT DETECTED"},
            "workday": {"connected": False, "user": None, "label": "AUTOFILL ON OPEN"},
            "indeed": {"connected": False, "user": None, "label": "NOT DETECTED"},
            "handshake": {"connected": False, "user": None, "label": "NOT DETECTED"},
            "migratemate": {"connected": False, "user": None, "label": "NOT DETECTED"},
        }

        if not os.path.exists(STORAGE_STATE_PATH):
            return status

        try:
            with open(STORAGE_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            cookies = data.get("cookies", [])
            for c in cookies:
                domain = c.get("domain", "").lower()
                name = c.get("name", "")

                # Google Auth check (SID, OSID, or __Secure-1PSID)
                if ("google.com" in domain) and name in ("OSID", "SID", "__Secure-1PSID", "SAPISID"):
                    status["google"]["connected"] = True
                    status["google"]["user"] = "Google Account (Active SSO)"
                    status["google"]["label"] = "CONNECTED (Active Session)"

                # LinkedIn Auth check (li_at, liap)
                if ("linkedin.com" in domain) and name in ("li_at", "liap"):
                    status["linkedin"]["connected"] = True
                    status["linkedin"]["user"] = "LinkedIn Member (Feed Active)"
                    status["linkedin"]["label"] = "CONNECTED (Active Session)"

                # Indeed Auth check
                if ("indeed.com" in domain) and name in ("CTK", "SURF", "LV"):
                    status["indeed"]["connected"] = True
                    status["indeed"]["user"] = "Indeed Member Session"
                    status["indeed"]["label"] = "CONNECTED (Active Session)"

                # Workday cookies
                if "workday" in domain or "myworkdayjobs" in domain:
                    status["workday"]["connected"] = True
                    status["workday"]["user"] = "Workday Candidate Session"
                    status["workday"]["label"] = "CONNECTED (Active Session)"

                # Handshake cookies
                if "joinhandshake.com" in domain:
                    status["handshake"]["connected"] = True
                    status["handshake"]["user"] = "Handshake Student Session"
                    status["handshake"]["label"] = "CONNECTED (Collegiate Active)"

                # Migrate Mate cookies
                if "migratemate" in domain:
                    status["migratemate"]["connected"] = True
                    status["migratemate"]["user"] = "Migrate Mate Active Session"
                    status["migratemate"]["label"] = "CONNECTED (Sponsorship Portal)"

        except Exception as e:
            logger.warning(f"Failed to parse storage state: {e}")

        # Check Gmail IMAP configured status
        try:
            from core.gmail_tracker import GmailTrackerAgent
            gt = GmailTrackerAgent()
            status["gmail"] = {
                "connected": bool(gt.email_password),
                "user": gt.email_user if gt.email_password else "Not configured",
                "label": "CONFIGURED (Ready to Sync)" if gt.email_password else "CREDENTIALS NEEDED"
            }
        except Exception:
            status["gmail"] = {"connected": False, "user": None, "label": "NOT CONFIGURED"}

        return status

    @classmethod
    async def _inject_storage_cookies(cls, context):
        if os.path.exists(STORAGE_STATE_PATH):
            try:
                with open(STORAGE_STATE_PATH, "r", encoding="utf-8") as f:
                    state = json.load(f)
                raw_cookies = state.get("cookies", [])
                clean_cookies = []
                for c in raw_cookies:
                    cc = {k: v for k, v in c.items() if k not in ["partitionKey", "_crHasCrossSiteAncestor"]}
                    if cc.get("sameSite") not in ["Strict", "Lax", "None"]:
                        cc.pop("sameSite", None)
                    clean_cookies.append(cc)
                if clean_cookies:
                    await context.add_cookies(clean_cookies)
            except Exception as e:
                logger.warning(f"Cookie injection notice: {e}")

    @classmethod
    async def get_active_context(cls, playwright):
        """
        Connects to user's real running Chrome instance via CDP (port 9222).
        Automatically ensures Chrome is running with CDP enabled.
        Falls back to launch_persistent_context if CDP is unavailable.
        """
        cdp_ok = ensure_cdp_chrome_running()
        if cdp_ok:
            try:
                logger.info(f"[Real Chrome Bridge] Connecting over CDP to real Chrome at {CDP_URL}...")
                browser = await playwright.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                await cls._inject_storage_cookies(context)
                return browser, context, True
            except Exception as e:
                logger.warning(f"[Real Chrome Bridge] CDP connect failed: {e}. Falling back to persistent launch.")

        # Fallback to direct persistent context
        chrome_bin = find_chrome_executable()
        launch_args = ["--no-sandbox", "--disable-dev-shm-usage"]
        is_headless = not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        launch_kwargs = {
            "user_data_dir": JARVIS_CHROME_DIR,
            "headless": is_headless,
            "args": launch_args
        }
        if chrome_bin:
            launch_kwargs["executable_path"] = chrome_bin

        context = await playwright.chromium.launch_persistent_context(**launch_kwargs)
        await cls._inject_storage_cookies(context)
        return None, context, False

    @classmethod
    async def open_portal_login_window(cls, portal_name: str) -> Dict[str, Any]:
        """
        Opens a real tab directly inside Google Chrome on desktop.
        Saved passwords and Google accounts autofill naturally.
        """
        portal_key = portal_name.lower().split()[0].replace("/", "")
        target_url = PORTAL_URLS.get(portal_key, "https://accounts.google.com")

        playwright = await async_playwright().start()
        try:
            browser, context, is_cdp = await cls.get_active_context(playwright)
            page = await context.new_page()

            logger.info(f"[Real Chrome Bridge] Navigating user's Chrome to {target_url}...")
            await page.goto(target_url, timeout=45000)

            # Inject J.A.R.V.I.S. notification banner in user's Chrome safely
            try:
                await page.evaluate(f"""() => {{
                    const banner = document.createElement('div');
                    banner.id = 'jarvis-auth-banner';
                    banner.style.cssText = 'position:fixed; top:12px; left:50%; transform:translateX(-50%); z-index:99999999; background:#030712; border:2px solid #00f3ff; box-shadow:0 0 25px rgba(0,243,255,0.6); color:#fff; padding:10px 20px; border-radius:8px; font-family:sans-serif; font-size:13px; pointer-events:none;';
                    banner.textContent = '🤖 J.A.R.V.I.S. AUTH BRIDGE: Connected to Chrome for {portal_name}. Saved passwords & session tokens active.';
                    document.body.appendChild(banner);
                }}""")
            except Exception:
                pass

            # Sync active cookies into storage_state.json safely
            try:
                await context.storage_state(path=STORAGE_STATE_PATH)
                logger.info(f"[Real Chrome Bridge] Synced real Chrome cookies to {STORAGE_STATE_PATH}")
            except Exception as e:
                logger.debug(f"Notice saving storage state: {e}")

            # Keep syncing over a short interval to capture post-login redirects
            for _ in range(3):
                await asyncio.sleep(2)
                try:
                    await context.storage_state(path=STORAGE_STATE_PATH)
                except Exception:
                    pass

            return {"success": True, "message": f"Opened {portal_name} in your active Google Chrome. Saved passwords will autofill."}

        except Exception as e:
            logger.error(f"[Real Chrome Bridge Error] {e}")
            return {"success": False, "message": f"Chrome bridge error: {e}"}
        finally:
            try:
                await playwright.stop()
            except Exception:
                pass

    @classmethod
    async def execute_real_application_fill(cls, job_url: str, job_title: str, company: str) -> Tuple[bool, str]:
        """
        Launches the application directly in Google Chrome on desktop.
        Handles Workday, Greenhouse, and standard portals, autofilling candidate info.
        """
        profile = load_profile()
        p_info = profile.get("personal_info", {})
        first_name = p_info.get("first_name", "Shadman")
        last_name = p_info.get("last_name", "Ahsan")
        email = p_info.get("email", "shadman_ahsan@yahoo.com")
        phone = p_info.get("phone", "+1 (507) 850-3155")
        linkedin_url = p_info.get("linkedin", "https://linkedin.com/in/shadman-ahsan")
        github_url = p_info.get("github", "https://github.com/shadman1996")
        website_url = p_info.get("website", "https://shadman1996.github.io")
        location_str = f"{p_info.get('location', {}).get('city', 'Marshall')}, {p_info.get('location', {}).get('state', 'MN')}"

        playwright = await async_playwright().start()
        try:
            browser, context, is_cdp = await cls.get_active_context(playwright)
            page = await context.new_page()

            logger.info(f"[Live Application] Opening tab in real Chrome for {job_title} at {company}: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)

            fields_filled = []
            resume_path = os.path.join(PROJECT_ROOT, "config", "resume.pdf")
            has_resume = os.path.exists(resume_path)

            # Helper for Resume Upload
            async def try_upload_resume():
                if not has_resume:
                    return False
                try:
                    file_loc = page.locator('input[type="file"], input[accept*="pdf" i]').first
                    if await file_loc.count() > 0:
                        await file_loc.set_input_files(resume_path)
                        fields_filled.append("Resume PDF")
                        logger.info(f"[Autofill] Attached resume PDF: {resume_path}")
                        return True
                except Exception as ex:
                    logger.debug(f"Resume upload attempt notice: {ex}")
                return False

            # =========================================================================
            # CASE A: WORKDAY PORTAL (*.myworkdayjobs.com)
            # =========================================================================
            if "myworkdayjobs.com" in page.url or "myworkday.com" in page.url:
                logger.info("[Workday Handler] Detected Workday tenant. Handling Apply modal...")

                # Accept cookie banner if present
                cookie_btn = page.locator('[data-automation-id="legalNoticeAcceptButton"], button:has-text("Accept Cookies")').first
                if await cookie_btn.count() > 0:
                    try:
                        await cookie_btn.click()
                        await asyncio.sleep(1)
                    except Exception:
                        pass

                # If on job overview page, click Apply button
                apply_workday = page.locator('[data-automation-id="adventureButton"], a[href*="/apply"], button:has-text("Apply")').first
                if await apply_workday.count() > 0:
                    try:
                        await apply_workday.click()
                        await asyncio.sleep(3)
                    except Exception:
                        pass

                # Check if "Apply Manually" exists
                apply_manual = page.locator('[data-automation-id="applyManually"], button:has-text("Apply Manually")').first
                if await apply_manual.count() > 0:
                    logger.info("[Workday Handler] Clicking 'Apply Manually'...")
                    try:
                        await apply_manual.click()
                        await asyncio.sleep(2)
                    except Exception:
                        pass

                # Check for Workday Sign In / Create Account prompt
                creds_path = os.path.join(PROJECT_ROOT, "config", "credentials.json")
                wd_email = "shadman.ahsan.us@gmail.com"
                wd_password = "Temp@2025!!"
                if os.path.exists(creds_path):
                    try:
                        with open(creds_path) as f:
                            creds = json.load(f)
                            w_creds = creds.get("workday") or creds.get("external_portals") or {}
                            wd_email = w_creds.get("username", wd_email)
                            wd_password = w_creds.get("password", wd_password)
                    except Exception:
                        pass

                create_acc_btn = page.locator('a[data-automation-id="createAccountLink"], button:has-text("Create Account"), a:has-text("Create Account")').first
                email_f = page.locator('input[data-automation-id="email"], input[type="email"]').first
                pwd_f = page.locator('input[data-automation-id="password"], input[type="password"]').first
                v_pwd_f = page.locator('input[data-automation-id="verifyPassword"]').first
                sign_in_b = page.locator('button:has-text("Sign In"), div[data-automation-id="click_filter"]:has-text("Sign In")').first

                if await v_pwd_f.count() > 0:
                    logger.info("[Workday Handler] Registering new candidate account...")
                    await email_f.fill(wd_email)
                    await pwd_f.fill(wd_password)
                    await v_pwd_f.fill(wd_password)
                    cb = page.locator('input[type="checkbox"]').first
                    if await cb.count() > 0:
                        try:
                            await cb.check()
                        except Exception:
                            pass
                    sub_acc = page.locator('button[data-automation-id="createAccountSubmitButton"], button:has-text("Create Account")').first
                    if await sub_acc.count() > 0:
                        await sub_acc.click()
                        await asyncio.sleep(5)
                elif await email_f.count() > 0 and await pwd_f.count() > 0:
                    logger.info("[Workday Handler] Logging into candidate portal...")
                    await email_f.fill(wd_email)
                    await pwd_f.fill(wd_password)
                    if await sign_in_b.count() > 0:
                        await sign_in_b.click()
                        await asyncio.sleep(4)
                    has_login_err = await page.evaluate('''() => Array.from(document.querySelectorAll('[data-automation-id*="error" i], .alert')).some(e => (e.innerText || '').toLowerCase().includes('invalid'))''')
                    if has_login_err and await create_acc_btn.count() > 0:
                        await create_acc_btn.click()
                        await asyncio.sleep(2)
                        ef = page.locator('input[data-automation-id="email"], input[type="email"]').first
                        pf = page.locator('input[data-automation-id="password"], input[type="password"]').first
                        vpf = page.locator('input[data-automation-id="verifyPassword"]').first
                        if await ef.count() > 0 and await vpf.count() > 0:
                            await ef.fill(wd_email)
                            await pf.fill(wd_password)
                            await vpf.fill(wd_password)
                            cb = page.locator('input[type="checkbox"]').first
                            if await cb.count() > 0:
                                try:
                                    await cb.check()
                                except Exception:
                                    pass
                            sub_acc = page.locator('button[data-automation-id="createAccountSubmitButton"], button:has-text("Create Account")').first
                            if await sub_acc.count() > 0:
                                await sub_acc.click()
                                await asyncio.sleep(5)

                # Try filling Workday standard input fields
                workday_inputs = [
                    ('input[data-automation-id*="legalNameSection_firstName" i], input[data-automation-id*="firstName" i]', first_name, "First Name"),
                    ('input[data-automation-id*="legalNameSection_lastName" i], input[data-automation-id*="lastName" i]', last_name, "Last Name"),
                    ('input[data-automation-id*="email" i], input[type="email"]', email, "Email"),
                    ('input[data-automation-id*="phone" i], input[type="tel"]', phone, "Phone"),
                    ('input[data-automation-id*="addressSection_city" i]', "Marshall", "City"),
                    ('input[data-automation-id*="addressSection_postalCode" i]', "56258", "Postal Code")
                ]
                for selector, val, label in workday_inputs:
                    inp = page.locator(selector).first
                    if await inp.count() > 0:
                        try:
                            await inp.fill(val)
                            fields_filled.append(label)
                        except Exception:
                            pass

                await try_upload_resume()

            # =========================================================================
            # CASE B: GREENHOUSE PORTAL (job-boards.greenhouse.io / boards.greenhouse.io)
            # =========================================================================
            elif "greenhouse.io" in page.url:
                logger.info("[Greenhouse Handler] Detected Greenhouse job board. Filling form...")
                greenhouse_inputs = [
                    ('#first_name, input[name*="first_name" i]', first_name, "First Name"),
                    ('#last_name, input[name*="last_name" i]', last_name, "Last Name"),
                    ('#email, input[name*="email" i]', email, "Email"),
                    ('#phone, input[name*="phone" i]', phone, "Phone"),
                    ('#candidate-location, input[id*="location" i]', location_str, "Location"),
                    ('input[name*="linkedin" i], input[id*="linkedin" i]', linkedin_url, "LinkedIn URL"),
                    ('input[name*="website" i], input[id*="website" i]', website_url, "Website URL"),
                    ('input[name*="github" i], input[id*="github" i]', github_url, "GitHub URL")
                ]
                for selector, val, label in greenhouse_inputs:
                    inp = page.locator(selector).first
                    if await inp.count() > 0:
                        try:
                            await inp.fill(val)
                            fields_filled.append(label)
                        except Exception:
                            pass

                await try_upload_resume()

            # =========================================================================
            # CASE C: LEVER PORTAL (jobs.lever.co)
            # =========================================================================
            elif "lever.co" in page.url:
                logger.info("[Lever Handler] Detected Lever job board. Filling form...")
                apply_lever = page.locator('a[href*="/apply"], button:has-text("Apply")').first
                if await apply_lever.count() > 0:
                    try:
                        await apply_lever.click()
                        await asyncio.sleep(2)
                    except Exception:
                        pass

                lever_inputs = [
                    ('input[name="name"]', f"{first_name} {last_name}", "Full Name"),
                    ('input[name="email"]', email, "Email"),
                    ('input[name="phone"]', phone, "Phone"),
                    ('input[name="org"]', "Southwest Minnesota State University", "Current School"),
                    ('input[name="urls[LinkedIn]"]', linkedin_url, "LinkedIn URL"),
                    ('input[name="urls[GitHub]"]', github_url, "GitHub URL"),
                    ('input[name="urls[Portfolio]"], input[name="urls[Other]"]', website_url, "Portfolio URL")
                ]
                for selector, val, label in lever_inputs:
                    inp = page.locator(selector).first
                    if await inp.count() > 0:
                        try:
                            await inp.fill(val)
                            fields_filled.append(label)
                        except Exception:
                            pass

                await try_upload_resume()

            # =========================================================================
            # CASE D: ASHBY PORTAL (jobs.ashbyhq.com)
            # =========================================================================
            elif "ashbyhq.com" in page.url:
                logger.info("[Ashby Handler] Detected Ashby job board. Filling form...")
                ashby_inputs = [
                    ('input[name*="_system_field_name" i], input[name*="name" i]', f"{first_name} {last_name}", "Full Name"),
                    ('input[name*="_system_field_email" i], input[type="email"]', email, "Email"),
                    ('input[name*="_system_field_phone" i], input[type="tel"]', phone, "Phone"),
                    ('input[name*="linkedin" i]', linkedin_url, "LinkedIn URL"),
                    ('input[name*="github" i]', github_url, "GitHub URL")
                ]
                for selector, val, label in ashby_inputs:
                    inp = page.locator(selector).first
                    if await inp.count() > 0:
                        try:
                            await inp.fill(val)
                            fields_filled.append(label)
                        except Exception:
                            pass

                await try_upload_resume()

            # =========================================================================
            # CASE E: iCIMS ENTERPRISE ATS (icims.com / careers-*.icims.com)
            # =========================================================================
            elif "icims.com" in page.url or await page.locator("#icims_content_iframe").count() > 0:
                logger.info("[iCIMS Handler] Detected iCIMS enterprise portal. Executing autonomous engine...")
                from automation.icims_automation import ICIMSAutomation
                icims_auto = ICIMSAutomation(profile=profile)
                icims_success, icims_msg = await icims_auto.handle_icims_page(page)
                if icims_success:
                    return True, f"Application fully submitted via iCIMS Engine for {company}: {icims_msg}"

            # =========================================================================
            # CASE F: UKG / ULTIPRO ENTERPRISE ATS (ultipro.com / recruiting2.ultipro.com)
            # =========================================================================
            elif "ultipro.com" in page.url:
                logger.info("[UltiPro Handler] Detected UKG / UltiPro enterprise portal. Executing autonomous engine...")
                from automation.ultipro_automation import UltiProAutomation
                ultipro_auto = UltiProAutomation(profile=profile)
                ulti_success, ulti_msg = await ultipro_auto.handle_ultipro_page(page)
                if ulti_success:
                    return True, f"Application fully submitted via UltiPro Engine for {company}: {ulti_msg}"

            # =========================================================================
            # CASE G: ADVANCED ATS FORM FILLER & UNIVERSAL COMBOBOX/DROPDOWN SOLVER
            # Absorbed and expanded from torontodeveloper/job-application-agent
            # =========================================================================
            logger.info("[ATS Form Filler] Running structural DOM analyzer for comboboxes, dropdowns, and form controls...")
            form_filler = ATSFormFiller(profile=profile)
            try:
                fill_res = await form_filler.fill_form(page, resume_path=resume_path)
                for f_label in fill_res.get("filled_labels", []):
                    if f_label not in fields_filled:
                        fields_filled.append(f_label)
                logger.info(f"[ATS Form Filler] Populated {fill_res['filled_count']} fields ({fill_res['total_fields']} total detected).")
            except Exception as e:
                logger.debug(f"ATS Form Filler scan notice: {e}")

            await try_upload_resume()

            # Inject Smart Human-in-the-Loop Checkpoint HUD into Chrome tab
            try:
                await form_filler.inject_human_in_the_loop_hud(
                    page,
                    company=company,
                    job_title=job_title,
                    filled_count=len(fields_filled),
                    total_count=max(len(fields_filled), 1),
                    resume_attached=bool(resume_path and os.path.exists(resume_path))
                )
            except Exception as e:
                logger.debug(f"HUD injection notice: {e}")

            # Sync active session state safely
            try:
                await context.storage_state(path=STORAGE_STATE_PATH)
            except Exception as e:
                logger.debug(f"Notice syncing storage state: {e}")

            summary_msg = f"Live tab opened in Chrome for {company}! Autofilled: {', '.join(fields_filled) if fields_filled else 'Navigated to application'}. Tab remains open for your review."
            logger.info(f"[Live Application] {summary_msg}")
            return True, summary_msg

        except Exception as e:
            logger.error(f"[Live Application Error] {e}")
            return False, f"Chrome automation error: {e}"
        finally:
            try:
                await playwright.stop()
            except Exception:
                pass
