import asyncio
import os
import sys
import json
from playwright.async_api import async_playwright

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
sys.path.insert(0, PROJECT_ROOT)

from core.matcher import load_profile

async def run_bridgewater_apply():
    profile = load_profile()
    p_info = profile.get("personal_info", {})
    email = p_info.get("email", "shadman_ahsan@yahoo.com")
    first_name = p_info.get("first_name", "Shadman")
    last_name = p_info.get("last_name", "Ahsan")
    phone = p_info.get("phone", "+1 507 850-3155")
    password = "SuperCyberSecPass2026!"
    resume_path = os.path.join(PROJECT_ROOT, "config", "resume.pdf")

    url = "https://recruiting2.ultipro.com/BRI1025BRIDG/JobBoard/c03155e6-0f7c-455b-8f80-d95807d74e0c/OpportunityDetail?opportunityId=d1bffcf7-cde1-4578-bb35-6a5a7d30f4a0"

    print(f"Connecting to CDP Chrome for Bridgewater Bank: {url}")
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        print("Navigating to Bridgewater Bank opportunity page...")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(3)

        print(f"Current page title: {await page.title()}")

        # Click Apply Now
        apply_btn = page.locator('ukg-button:has-text("Apply now"), button:has-text("Apply now"), a:has-text("Apply now")').first
        if await apply_btn.count() > 0:
            print("Found 'Apply now' button. Clicking...")
            await apply_btn.click()
            await asyncio.sleep(4)
        else:
            print("Trying JavaScript click on Apply now...")
            clicked = await page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('ukg-button'));
                    const apply = btns.find(b => (b.innerText || '').toLowerCase().includes('apply'));
                    if (apply) {
                        const inner = apply.shadowRoot ? apply.shadowRoot.querySelector('button') : null;
                        if (inner) inner.click();
                        else apply.click();
                        return true;
                    }
                    return false;
                }
            """)
            print(f"JS click result: {clicked}")
            await asyncio.sleep(4)

        print(f"After click, page URL: {page.url}")
        print(f"After click, page title: {await page.title()}")

        # Check if we are on Login page
        if "login" in page.url.lower():
            print("Detected login page. Checking for Sign up link...")
            signup_link = page.locator('a[href*="signup"], a:has-text("Sign up")').first
            if await signup_link.count() > 0:
                print("Clicking 'Sign up' link...")
                await signup_link.click()
                await asyncio.sleep(4)
                print(f"Signup URL: {page.url}")

        # Inspect inputs on current page
        inputs_info = await page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea, button'));
                return els.map(e => ({
                    tag: e.tagName,
                    type: e.type,
                    id: e.id,
                    name: e.name,
                    placeholder: e.placeholder,
                    text: (e.innerText || e.value || '').trim()
                }));
            }
        """)
        print(f"Current form controls ({len(inputs_info)}):")
        for inp in inputs_info[:15]:
            print(f"  [{inp['tag']} {inp['type']}] id='{inp['id']}' name='{inp['name']}' placeholder='{inp['placeholder']}' text='{inp['text']}'")

if __name__ == '__main__':
    asyncio.run(run_bridgewater_apply())
