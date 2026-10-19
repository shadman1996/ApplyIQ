import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_STATE_PATH = os.path.join(PROJECT_ROOT, "config", "storage_state.json")
BROWSER_PROFILE_DIR = os.path.join(PROJECT_ROOT, "data", "browser_profile")

class StealthBrowserManager:
    def __init__(self, storage_state_path: str = None, headless: Optional[bool] = None):
        self.storage_state_path = storage_state_path or STORAGE_STATE_PATH
        if headless is not None:
            self.headless = headless
        elif os.environ.get("HEADLESS"):
            self.headless = os.environ.get("HEADLESS", "true").lower() == "true"
        elif not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            self.headless = True
        else:
            self.headless = False
        self.playwright = None
        self.browser = None
        self.context = None

    async def init_browser(self, headless: Optional[bool] = None) -> Any:
        """Launches a chromium engine modified to bypass standard webdriver detection layers."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright library is not installed. Install with `pip install playwright`.")
            return None

        if headless is not None:
            self.headless = headless

        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
        self.playwright = await async_playwright().start()

        # Use persistent context to retain Workday/LinkedIn login cookies across runs
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars"
            ]
        )

        # Inject script to completely wipe the webdriver flag from navigator scope
        await self.context.add_init_script(
            "const newProto = navigator.__proto__; delete newProto.webdriver; navigator.__proto__ = newProto;"
        )

        # Inject cached cookies if storage_state exists
        if os.path.exists(self.storage_state_path):
            try:
                with open(self.storage_state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                raw_cookies = state.get("cookies", [])
                clean_cookies = []
                for c in raw_cookies:
                    cc = {k: v for k, v in c.items() if k not in ["partitionKey", "_crHasCrossSiteAncestor"]}
                    if cc.get("sameSite") not in ["Strict", "Lax", "None"]:
                        cc.pop("sameSite", None)
                    clean_cookies.append(cc)
                if clean_cookies:
                    await self.context.add_cookies(clean_cookies)
                logger.info(f"Loaded {len(clean_cookies)} cookies into stealth persistent context.")
            except Exception as e:
                logger.warning(f"Storage state injection notice: {e}")

        return self.context

    async def start(self) -> bool:
        """Alias for init_browser for backward compatibility."""
        ctx = await self.init_browser()
        return ctx is not None

    async def get_page(self, block_assets: bool = False) -> Any:
        page = await self.context.new_page() if self.context else None
        if not page:
            return None

        # Network Asset Blocking to accelerate page loads when desired
        if block_assets:
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font", "media"] else route.continue_()
            )
        return page

    async def autofill_standard_fields(self, page, profile_data: dict, tailored_summary: str = ""):
        """Discovers form components structurally and handles input injection with natural keyboard delays."""
        field_mappings = {
            'input[name*="first" i], input[id*="first" i], input[placeholder*="first name" i]': profile_data.get("first_name", profile_data.get("personal_info", {}).get("first_name", "")),
            'input[name*="last" i], input[id*="last" i], input[placeholder*="last name" i]': profile_data.get("last_name", profile_data.get("personal_info", {}).get("last_name", "")),
            'input[type="email"], input[name*="email" i], input[id*="email" i]': profile_data.get("email", profile_data.get("personal_info", {}).get("email", "")),
            'input[type="tel"], input[name*="phone" i], input[id*="phone" i]': profile_data.get("phone", profile_data.get("personal_info", {}).get("phone", "")),
            'textarea[name*="summary" i], textarea[name*="cover" i], textarea[placeholder*="cover letter" i]': tailored_summary,
            'input[name*="linkedin" i], input[id*="linkedin" i]': profile_data.get("linkedin_url", profile_data.get("personal_info", {}).get("linkedin", "")),
            'input[name*="github" i], input[id*="github" i]': profile_data.get("github_url", profile_data.get("personal_info", {}).get("github", ""))
        }

        for selector, value in field_mappings.items():
            if value:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        if await el.is_visible():
                            await el.fill("")
                            # Simulate natural keyboard delays to mask automated scripts
                            await el.type(value, delay=50)
                except Exception as e:
                    logger.debug(f"Skipping selector field {selector}: {e}")

    async def autofill_with_ats_filler(self, page, profile_data: dict, resume_path: Optional[str] = None, custom_answers: Optional[dict] = None) -> dict:
        """
        Invokes ATSFormFiller for comboboxes, dropdowns, radios, and inputs.
        Absorbed from torontodeveloper/job-application-agent.
        """
        from automation.ats_form_filler import ATSFormFiller
        filler = ATSFormFiller(profile=profile_data)
        return await filler.fill_form(page, resume_path=resume_path, custom_answers=custom_answers)

    async def save_storage_state(self):
        if self.context:
            try:
                os.makedirs(os.path.dirname(self.storage_state_path), exist_ok=True)
                await self.context.storage_state(path=self.storage_state_path)
                logger.info(f"Saved session state to {self.storage_state_path}")
            except Exception as e:
                logger.debug(f"Notice saving storage state: {e}")

    async def close_browser(self):
        """Safely saves session state parameters to storage files before engine shutdown."""
        if self.context:
            await self.save_storage_state()
            try:
                await self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass

    async def close(self):
        """Alias for close_browser for backward compatibility."""
        await self.close_browser()
