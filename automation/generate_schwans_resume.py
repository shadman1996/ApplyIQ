import os
import asyncio
from playwright.async_api import async_playwright

PROJECT_ROOT = "/home/shadman/Documents/cyber_auto_applier"
TAILORED_DIR = os.path.join(PROJECT_ROOT, "data", "tailored")
OUTPUT_PDF = os.path.join(TAILORED_DIR, "Shadman_Ahsan_Schwans_IT_Operations_Resume.pdf")
MASTER_TAILORED_PDF = os.path.join(TAILORED_DIR, "Shadman_Ahsan_Resume.pdf")

RESUME_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
    size: letter;
    margin: 0.30in 0.42in;
}
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}
body {
    font-family: 'Calibri', 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    font-size: 8.8pt;
    line-height: 1.25;
    color: #1a1a1a;
}
.header {
    text-align: center;
    margin-bottom: 4px;
    padding-bottom: 3px;
    border-bottom: 2px solid #003366;
}
.name {
    font-size: 18.5pt;
    font-weight: 700;
    color: #003366;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.title {
    font-size: 10pt;
    font-weight: 600;
    color: #b33924;
    margin: 1.5px 0;
    letter-spacing: 0.2px;
}
.contact {
    font-size: 8.2pt;
    color: #333333;
}
.section {
    margin-top: 4.5px;
}
.section-title {
    font-size: 9.2pt;
    font-weight: 700;
    color: #003366;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #003366;
    padding-bottom: 1px;
    margin-bottom: 3px;
}
.summary {
    font-size: 8.5pt;
    color: #222222;
    line-height: 1.28;
    text-align: justify;
}
.skills-grid {
    font-size: 8.5pt;
    line-height: 1.30;
}
.skills-row {
    margin-bottom: 1.5px;
}
.skills-label {
    font-weight: 700;
    color: #003366;
}
.entry {
    margin-bottom: 4.5px;
    page-break-inside: avoid;
}
.entry-header {
    display: flex;
    justify-content: space-between;
    font-size: 8.8pt;
    margin-bottom: 1px;
}
.entry-title {
    font-weight: 700;
    color: #111111;
}
.entry-company {
    font-weight: 600;
    color: #003366;
}
.entry-location-dates {
    font-size: 8.2pt;
    color: #444444;
    font-weight: 500;
    text-align: right;
}
ul {
    margin-left: 14px;
    padding: 0;
}
li {
    font-size: 8.4pt;
    margin-bottom: 1.5px;
    line-height: 1.24;
    color: #262626;
}
li b {
    color: #003366;
}
</style>
</head>
<body>

<div class="header">
    <div class="name">Shadman Ahsan</div>
    <div class="title">IT Operations & Systems Administration Specialist · M.S. Candidate</div>
    <div class="contact">
        Marshall, MN 56258 &nbsp;•&nbsp; 
        +1 (507) 850-3155 &nbsp;•&nbsp; 
        shadman_ahsan@yahoo.com &nbsp;•&nbsp; 
        shadman.ahsan.us@gmail.com &nbsp;•&nbsp; 
        linkedin.com/in/shadman-ahsan &nbsp;•&nbsp; 
        github.com/shadman1996
    </div>
</div>

<div class="section">
    <div class="section-title">Professional Summary</div>
    <div class="summary">
        Results-driven Enterprise Systems and IT Operations Specialist with 5+ years of hands-on technical experience spanning Microsoft Windows Server administration, endpoint provisioning, production SQL database maintenance, and network troubleshooting. Currently pursuing an M.S. in Cybersecurity at Southwest Minnesota State University (SMSU) in Marshall, MN, while serving as Graduate Assistant at the university Technology Resource Center (TRC). Proven track record diagnosing tier-2/tier-3 hardware and software anomalies, optimizing Mean Time to Resolution (MTTR) through structured ITSM workflows, and maintaining 99.9% system availability. Local to Marshall, MN with immediate availability for the Summer 2027 IT Operations Internship at CJ Schwan's.
    </div>
</div>

<div class="section">
    <div class="section-title">Technical Competencies & Systems Expertise</div>
    <div class="skills-grid">
        <div class="skills-row"><span class="skills-label">Systems & Servers:</span> Microsoft Windows Server (2016/2019/2022), Active Directory (AD), Group Policy Objects (GPO), Hyper-V, VMware ESXi, Linux (RHEL, Ubuntu), macOS, Endpoint Provisioning & Automated OS Imaging</div>
        <div class="skills-row"><span class="skills-label">Infrastructure & Networking:</span> TCP/IP, DNS, DHCP, LAN/WAN Configuration, VPN Tunnels, Subnetting, VLANs, Wireshark Packet Analysis, Network Switch/Router Configuration, Hardware Diagnostics</div>
        <div class="skills-row"><span class="skills-label">Identity & Access (IAM):</span> Microsoft Entra ID (Azure AD), Multi-Factor Authentication (MFA), Role-Based Access Control (RBAC), Single Sign-On (SSO), Account Lifecycle Provisioning</div>
        <div class="skills-row"><span class="skills-label">ITSM & Operational Governance:</span> ITIL Framework, ServiceNow, Jira Service Desk, Incident & Change Management, SLA Compliance, Technical Runbooks & SOP Authoring, MTTR Optimization</div>
        <div class="skills-row"><span class="skills-label">Databases & Automation:</span> PowerShell Scripting, Bash, Python, SQL (MySQL, PostgreSQL, Oracle), Automated System Backups, Disaster Recovery Failover, System Performance & Alert Monitoring</div>
    </div>
</div>

<div class="section">
    <div class="section-title">Professional & Technical Experience</div>

    <div class="entry">
        <div class="entry-header">
            <div><span class="entry-title">Graduate Assistant — Technology Resource Center (TRC)</span> · <span class="entry-company">Southwest Minnesota State University</span></div>
            <div class="entry-location-dates">Marshall, MN &nbsp;|&nbsp; Jan 2026 – Present</div>
        </div>
        <ul>
            <li>Lead <b>tier-2 technical support escalations</b> and hardware/software troubleshooting across 100+ campus computer labs, faculty workstations, and classroom AV infrastructure, ensuring zero disruption to academic operations.</li>
            <li>Administer campus <b>Identity & Access Management (IAM)</b> and endpoint security via Active Directory and Azure AD, managing account provisioning, MFA compliance, and Group Policy permissions for thousands of users.</li>
            <li>Support deployment and maintenance of <b>Windows Server environments</b>, managing network shared drives, automated workstation imaging, and patch deployment schedules.</li>
            <li>Utilize enterprise <b>ITSM ticketing systems</b> to monitor support trends, perform QA on ticket resolution workflows, and systematically drive down Mean Time to Resolution (MTTR).</li>
            <li>Author and audit <b>Standard Operating Procedures (SOPs)</b> and technical runbooks for hardware repairs, OS reimaging, and network switch port diagnostics, eliminating operational downtime.</li>
        </ul>
    </div>

    <div class="entry">
        <div class="entry-header">
            <div><span class="entry-title">Management Information System (MIS) Specialist</span> · <span class="entry-company">Helen Keller International</span></div>
            <div class="entry-location-dates">Dhaka, Bangladesh &nbsp;|&nbsp; Sep 2023 – Mar 2025</div>
        </div>
        <ul>
            <li>Directed enterprise <b>systems administration and IT operations for 700+</b> corporate and remote personnel across multiple branch offices, configuring VPN tunnels, resolving complex hardware anomalies, and standardizing OS builds.</li>
            <li>Maintained <b>99.9% system availability</b> across production SQL databases and enterprise application servers, executing scheduled automated backups, integrity tests, and disaster recovery failover protocols.</li>
            <li>Engineered automated data pipelines and performance monitoring dashboards, tracking server uptime, network traffic, and system error rates to proactively address infrastructure bottlenecks.</li>
            <li>Supervised IT hardware lifecycle management, auditing physical network infrastructure, server racks, and peripheral equipment to ensure regulatory compliance and operational readiness.</li>
            <li>Conducted root-cause analysis on recurring IT incidents and delivered structured technical trainings, reducing monthly helpdesk escalations by <b>25%</b>.</li>
        </ul>
    </div>

    <div class="entry">
        <div class="entry-header">
            <div><span class="entry-title">Assistant Coordinator — MIS & IT Operations</span> · <span class="entry-company">Sajida Foundation</span></div>
            <div class="entry-location-dates">Dhaka, Bangladesh &nbsp;|&nbsp; Jun 2022 – Aug 2023</div>
        </div>
        <ul>
            <li>Administered enterprise Salesforce CRM and localized IT systems for <b>1,000+ distributed users</b>, enforcing Role-Based Access Control (RBAC) and strict data governance policies.</li>
            <li>Configured and maintained local area networks (LAN), Wi-Fi access points, network switches, and peripheral hardware for enterprise program operations across 12 field facilities.</li>
            <li>Managed regional LAN/WAN network infrastructure, secure enterprise VPN tunnels, and endpoint security across district offices, resolving escalated systems issues.</li>
            <li>Automated weekly data backups, verified system logs, and implemented security controls preventing unauthorized access.</li>
        </ul>
    </div>
</div>

<div class="section">
    <div class="section-title">Education & Academic Appointments</div>

    <div class="entry">
        <div class="entry-header">
            <div><span class="entry-title">Master of Science (MS) in Cybersecurity</span> · <span class="entry-company">Southwest Minnesota State University</span></div>
            <div class="entry-location-dates">Marshall, MN &nbsp;|&nbsp; Expected Graduation: Dec 2027</div>
        </div>
        <ul>
            <li><b>Graduate Assistantship:</b> Technology Resource Center (TRC) Management & Systems Support.</li>
            <li><b>Relevant Coursework:</b> Network Security & Protocols, Operating Systems Architecture, Secure Software Engineering, Digital Forensics, Cybersecurity Strategy & Governance.</li>
        </ul>
    </div>

    <div class="entry">
        <div class="entry-header">
            <div><span class="entry-title">Bachelor of Science in Computer Science and Engineering</span> · <span class="entry-company">Independent University, Bangladesh</span></div>
            <div class="entry-location-dates">Dhaka, Bangladesh &nbsp;|&nbsp; Conferred: May 2021</div>
        </div>
        <ul>
            <li><b>Relevant Coursework:</b> Computer Networks, Operating Systems, Database Management Systems (DBMS), Systems Analysis & Design, Data Structures & Algorithms, Object-Oriented Programming (OOP).</li>
        </ul>
    </div>
</div>

</body>
</html>
"""

async def generate():
    os.makedirs(TAILORED_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(RESUME_HTML, wait_until="load")
        
        # Render to specific Schwans PDF
        await page.pdf(
            path=OUTPUT_PDF,
            format="Letter",
            margin={"top": "0.30in", "right": "0.42in", "bottom": "0.30in", "left": "0.42in"},
            print_background=True
        )
        print(f"Generated CJ Schwan's PDF: {OUTPUT_PDF} ({os.path.getsize(OUTPUT_PDF)} bytes)")
        
        # Also copy / render to MASTER_TAILORED_PDF
        await page.pdf(
            path=MASTER_TAILORED_PDF,
            format="Letter",
            margin={"top": "0.30in", "right": "0.42in", "bottom": "0.30in", "left": "0.42in"},
            print_background=True
        )
        print(f"Updated Master Tailored PDF: {MASTER_TAILORED_PDF} ({os.path.getsize(MASTER_TAILORED_PDF)} bytes)")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(generate())
