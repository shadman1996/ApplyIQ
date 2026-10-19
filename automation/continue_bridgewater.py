import asyncio
import os
import sys
import json
from playwright.async_api import async_playwright

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
sys.path.insert(0, PROJECT_ROOT)

from core.matcher import load_profile

async def submit_signup_and_continue():
    profile = load_profile()
    p_info = profile.get("personal_info", {})
    email = p_info.get("email", "shadman_ahsan@yahoo.com")
    first_name = p_info.get("first_name", "Shadman")
    last_name = p_info.get("last_name", "Ahsan")
    phone = p_info.get("phone", "+1 507 850-3155")
    password = "SuperCyberSecPass2026!"
    resume_path = os.path.join(PROJECT_ROOT, "config", "resume.pdf")

    print(f"Connecting to Chrome CDP at 127.0.0.1:9222...")
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        # Get active page
        pages = context.pages
        page = pages[-1]
        print(f"Active page: {page.url} ({await page.title()})")

        # Fill Email
        email_inp = page.locator('#email, input[name="email"]')
        if await email_inp.count() > 0:
            print(f"Filling email: {email}")
            await email_inp.fill(email)

        # Fill Password
        pwd_inp = page.locator('#password, input[name="password"]')
        if await pwd_inp.count() > 0:
            print("Filling password...")
            await pwd_inp.fill(password)

        await asyncio.sleep(1)

        # Click Continue
        submit_btn = page.locator('button[type="submit"]:has-text("Continue"), button:has-text("Continue")')
        if await submit_btn.count() > 0:
            print("Clicking 'Continue' submit button...")
            await submit_btn.click()
            await asyncio.sleep(5)

        print(f"Post-submit URL: {page.url}")
        print(f"Post-submit Title: {await page.title()}")

        # Check for error or next screen
        errors = await page.evaluate("""
            () => Array.from(document.querySelectorAll('.error, .alert, [role="alert"], .ulp-input-error-message')).map(e => e.innerText.trim()).filter(Boolean)
        """)
        print(f"Errors detected: {errors}")

        # Check if redirected to application form or email verification
        body_text = await page.evaluate("() => document.body ? document.body.innerText.substring(0, 1000).replace(/\\s+/g, ' ') : ''")
        print(f"Page Text Snippet: {body_text[:300]}")

if __name__ == '__main__':
    asyncio.run(submit_signup_and_continue())
