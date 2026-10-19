import asyncio
import os
import sys
import json
from playwright.async_api import async_playwright

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
sys.path.insert(0, PROJECT_ROOT)

from core.matcher import load_profile

async def run_ameriprise():
    email = "shadman.ahsan.us@gmail.com"
    password = "Temp@2025!!"
    resume_path = os.path.join(PROJECT_ROOT, "config", "resume.pdf")

    url = "https://ameriprise.wd5.myworkdayjobs.com/en-US/Ameriprise/job/Technology-Intern_R26_3537/apply"

    print(f"Connecting to Chrome CDP at 127.0.0.1:9222...")
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        # Check if Sign In button is on top
        sign_in_top = page.locator('button[data-automation-id="utilityButtonSignIn"], button:has-text("Sign In")').first
        # Check if Autofill with Resume exists
        autofill_btn = page.locator('a[data-automation-id="autofillWithResume"], button:has-text("Autofill with Resume"), a:has-text("Autofill with Resume")').first

        if await autofill_btn.count() > 0:
            print("Clicking 'Autofill with Resume'...")
            await autofill_btn.click()
            await asyncio.sleep(3)

        print(f"URL after click: {page.url}")

        # Check if on Sign In modal/page
        email_inp = page.locator('input[data-automation-id="email"], input[type="email"]').first
        pwd_inp = page.locator('input[data-automation-id="password"], input[type="password"]').first
        sign_in_submit = page.locator('button[data-automation-id="signInSubmitButton"], button:has-text("Sign In"), div[data-automation-id="click_filter"]:has-text("Sign In")').first

        if await email_inp.count() > 0 and await pwd_inp.count() > 0:
            print(f"Entering credentials: {email}")
            await email_inp.fill(email)
            await pwd_inp.fill(password)
            await asyncio.sleep(1)

            print("Submitting login...")
            if await sign_in_submit.count() > 0:
                await sign_in_submit.click(force=True)
            else:
                await page.keyboard.press("Enter")
            await asyncio.sleep(5)

        print(f"Current URL after login check: {page.url}")
        print(f"Page title: {await page.title()}")

        # Check if resume upload is requested
        file_input = page.locator('input[type="file"]').first
        if await file_input.count() > 0:
            print(f"Uploading resume: {resume_path}")
            await file_input.set_input_files(resume_path)
            await asyncio.sleep(5)
            print("Resume uploaded!")

        # Check for Next / Continue button on Resume upload screen
        next_btn = page.locator('button[data-automation-id="pageFooterNextButton"], button[data-automation-id="bottom-navigation-next-button"], button:has-text("Continue"), button:has-text("Next")').first
        if await next_btn.count() > 0:
            print("Clicking Next/Continue button...")
            await next_btn.click(force=True)
            await asyncio.sleep(5)

        print(f"Step URL: {page.url}")
        body_text = await page.evaluate("() => document.body ? document.body.innerText.substring(0, 1000).replace(/\\s+/g, ' ') : ''")
        print(f"Body snippet: {body_text[:400]}")

if __name__ == '__main__':
    asyncio.run(run_ameriprise())
