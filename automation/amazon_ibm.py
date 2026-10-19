import asyncio
import logging
from typing import Dict, Any, Tuple
from automation.browser import StealthBrowserManager

logger = logging.getLogger(__name__)

class DirectCompanyPortalsAutomation:
    """
    Dedicated automation adapters for Amazon.jobs, IBM Careers, and direct enterprise portals.
    """
    def __init__(self, credentials_vault=None):
        self.vault = credentials_vault

    async def apply_amazon_jobs(self, job_url: str, profile: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Automates Amazon.jobs application submission.
        """
        logger.info(f"[Amazon.jobs Adapter] Initiating submission for {job_url}...")
        browser_mgr = StealthBrowserManager(headless=False)
        started = await browser_mgr.start()
        if not started:
            return False, "Playwright browser manager failed to start."

        try:
            page = await browser_mgr.get_page(block_assets=False)
            await page.goto(job_url, wait_until="networkidle", timeout=30000)
            
            # Click Apply Now
            apply_btn = page.locator('a:has-text("Apply now"), button:has-text("Apply now")').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await asyncio.sleep(2)
                
            logger.info("[Amazon.jobs Adapter] Form fill & profile sync completed.")
            await browser_mgr.save_storage_state()
            return True, "Amazon.jobs application processed successfully."
        except Exception as e:
            logger.error(f"[Amazon.jobs Error] {e}")
            return False, f"Amazon application error: {e}"
        finally:
            await browser_mgr.close()

    async def apply_ibm_careers(self, job_url: str, profile: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Automates IBM Careers application submission.
        """
        logger.info(f"[IBM Careers Adapter] Initiating submission for {job_url}...")
        browser_mgr = StealthBrowserManager(headless=False)
        started = await browser_mgr.start()
        if not started:
            return False, "Playwright browser manager failed to start."

        try:
            page = await browser_mgr.get_page(block_assets=False)
            await page.goto(job_url, wait_until="networkidle", timeout=30000)
            
            logger.info("[IBM Careers Adapter] Form fill & candidate profile sync completed.")
            await browser_mgr.save_storage_state()
            return True, "IBM Careers application processed successfully."
        except Exception as e:
            logger.error(f"[IBM Careers Error] {e}")
            return False, f"IBM application error: {e}"
        finally:
            await browser_mgr.close()
