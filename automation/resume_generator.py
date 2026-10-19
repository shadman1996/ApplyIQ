"""
ATS-Optimized Resume and PDF Generator.
Absorbed and adapted from ApplyPilot.
Uses Playwright headless Chromium to render pixel-perfect, single-page, ATS-compliant resumes.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(PROJECT_ROOT, "config", "profile.json")
TAILORED_DIR = os.path.join(PROJECT_ROOT, "data", "tailored")


def build_resume_html(profile_data: Dict[str, Any], tailored_title: Optional[str] = None, tailored_summary: Optional[str] = None) -> str:
    """Builds clean, ATS-compliant HTML for PDF rendering."""
    personal = profile_data.get("personal_info", {})
    name = personal.get("full_name", "Shadman Ahsan")
    title = tailored_title or "Cybersecurity Specialist & Enterprise Systems Engineer"
    
    loc = personal.get("location", {})
    loc_str = f"{loc.get('city', 'Marshall')}, {loc.get('state', 'MN')}, {loc.get('country', 'USA')}"
    
    contacts = [
        personal.get("email", ""),
        personal.get("phone", ""),
        personal.get("linkedin", "").replace("https://", ""),
        personal.get("github", "").replace("https://", ""),
    ]
    contact_str = " | ".join(c for c in contacts if c)
    summary_text = tailored_summary or profile_data.get("professional_summary", "")

    # Experience section
    exp_html = ""
    for exp in profile_data.get("work_experience", []):
        bullets = "".join(f"<li>{r}</li>" for r in exp.get("responsibilities", [])[:4])
        dates = f"{exp.get('start_date', '')} – {exp.get('end_date', '')}"
        subtitle = f"{exp.get('location', '')} | {dates}"
        exp_html += f"""
        <div class="entry">
            <div class="entry-header">
                <span class="entry-title">{exp.get('title', '')}</span> – <span class="entry-company">{exp.get('company', '')}</span>
                <span class="entry-dates">{subtitle}</span>
            </div>
            <ul>{bullets}</ul>
        </div>
        """

    # Education section
    edu_html = ""
    for edu in profile_data.get("education", []):
        dates = f"{edu.get('start_date', '')} – {edu.get('end_date', '')}"
        edu_html += f"""
        <div class="entry">
            <div class="entry-header">
                <span class="entry-title">{edu.get('degree', '')}</span> – <span class="entry-company">{edu.get('institution', '')}</span>
                <span class="entry-dates">{dates}</span>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: letter;
    margin: 0.35in 0.5in;
}}
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}
body {{
    font-family: 'Calibri', 'Segoe UI', Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.32;
    color: #1a1a1a;
}}
.header {{
    text-align: center;
    margin-bottom: 6px;
    padding-bottom: 4px;
    border-bottom: 1.5px solid #1a3a5c;
}}
.name {{
    font-size: 18pt;
    font-weight: 700;
    color: #1a3a5c;
    letter-spacing: 0.5px;
}}
.title {{
    font-size: 10.5pt;
    font-weight: 600;
    color: #2a7ab5;
    margin: 2px 0;
}}
.contact {{
    font-size: 8.5pt;
    color: #444;
}}
.section {{
    margin-top: 6px;
}}
.section-title {{
    font-size: 9.5pt;
    font-weight: 700;
    color: #1a3a5c;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    border-bottom: 1px solid #2a7ab5;
    padding-bottom: 1px;
    margin-bottom: 4px;
}}
.summary {{
    font-size: 9pt;
    color: #333;
    line-height: 1.35;
}}
.entry {{
    margin-bottom: 5px;
    page-break-inside: avoid;
}}
.entry-header {{
    display: flex;
    justify-content: space-between;
    font-size: 9.5pt;
    margin-bottom: 2px;
}}
.entry-title {{
    font-weight: 700;
    color: #1a3a5c;
}}
.entry-company {{
    font-weight: 600;
    color: #333;
}}
.entry-dates {{
    font-size: 8.5pt;
    color: #666;
    float: right;
}}
ul {{
    margin-left: 16px;
    padding: 0;
}}
li {{
    font-size: 9pt;
    margin-bottom: 2px;
    line-height: 1.3;
}}
</style>
</head>
<body>
<div class="header">
    <div class="name">{name}</div>
    <div class="title">{title}</div>
    <div class="contact">{loc_str} &nbsp;|&nbsp; {contact_str}</div>
</div>

<div class="section">
    <div class="section-title">Professional Summary</div>
    <div class="summary">{summary_text}</div>
</div>

<div class="section">
    <div class="section-title">Education</div>
    {edu_html}
</div>

<div class="section">
    <div class="section-title">Experience</div>
    {exp_html}
</div>
</body>
</html>"""


async def generate_pdf_resume(
    output_path: Optional[str] = None,
    tailored_title: Optional[str] = None,
    tailored_summary: Optional[str] = None
) -> str:
    """
    Renders an ATS-optimized PDF resume using Playwright async Chromium.
    Returns the absolute file path to the generated PDF.
    """
    from playwright.async_api import async_playwright

    os.makedirs(TAILORED_DIR, exist_ok=True)
    if not output_path:
        output_path = os.path.join(TAILORED_DIR, "Shadman_Ahsan_Resume.pdf")

    profile_data = {}
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

    html_content = build_resume_html(profile_data, tailored_title, tailored_summary)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content, wait_until="load")
        await page.pdf(
            path=output_path,
            format="Letter",
            margin={"top": "0.3in", "right": "0.4in", "bottom": "0.3in", "left": "0.4in"},
            print_background=True,
        )
        await browser.close()

    logger.info(f"[Resume Generator] Successfully compiled PDF to {output_path}")
    return output_path
