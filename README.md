# 🤖 Autonomous Cybersecurity Internship Application Swarm

An autonomous multi-agent system designed to run **24/7 locally on your laptop** using **Gemini 2.5 Pro** and **Playwright / Direct APIs**.

---

## 🏗 Architecture Overview

The system consists of **4 Specialized Autonomous Agents**:

1. **ScoutAgent (24/7 Discovery):** Continuously scrapes job feeds, GitHub internship lists (SimplifyJobs / PittCSC), and ATS portals for new cybersecurity internship postings.
2. **AnalystAgent (Gemini 2.5 Pro):** Evaluates candidate resume (`config/profile.json`) against job descriptions, calculates a match score (0–100%), and drafts custom responses to application questions.
3. **SubmitterAgent (Direct API + Playwright):** Manages pre-configured credentials to perform fast direct API applications (300ms) for Greenhouse/Lever and automated browser sign-in/submission for Workday.
4. **SentinelAgent (Monitor & Guard):** Tracks applications in a local SQLite WAL database (`data/applications.db`), prevents duplicate submissions, enforces daily application caps, and reports statistics.esu_

---

## 🚀 Quick Start Guide

### 1. Configure Environment Credentials
Copy `.env.example` to `.env` and add your **Gemini API Key** and portal credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key
WORKDAY_USERNAME=your_workday_email@domain.com
WORKDAY_PASSWORD=your_workday_password
```

### 2. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Run the Agents

- **Run Single Execution Cycle:**
  ```bash
  python3 main.py run-once
  ```

- **Run 24/7 Autonomous Background Daemon (with Auto-Hygiene):**
  ```bash
  python3 main.py daemon
  ```

- **Run On-Demand Disk Hygiene & Cache Purge:**
  ```bash
  python3 main.py clean
  ```

- **Launch Cyber J.A.R.V.I.S. Command Center UI:**
  ```bash
  uvicorn server:app --host 127.0.0.1 --port 8000
  ```

- **Run Comprehensive 17-Test Suite:**
  ```bash
  .venv/bin/python tests/test_ui_and_workflow.py
  ```

---

## ⚡ ATS Form Parsing & Smart "Human-in-the-Loop" Checkpoint
*(Absorbed & expanded from `torontodeveloper/job-application-agent`)*

1. **Superior ATS Form Parsing (`automation/ats_form_filler.py`):**
   - **Combobox & Listbox Solver:** Handles search-as-you-type inputs (`role="combobox"`, `aria-haspopup="listbox"`, React-Select, Workday `promptOption`) by clicking, typing with natural delays, scanning DOM option lists, and falling back to keyboard navigation (`ArrowDown` + `Enter`).
   - **Dropdown Handling:** Evaluates native `<select>` options with exact and partial fuzzy substring matching.
   - **6-Tier Label Resolution:** Resolves field labels through `<label>`, `aria-label`, `placeholder`, `aria-labelledby`, parent fieldset/container, and sibling text.
   - **Deterministic Candidate Truths:** Hardcodes critical candidate facts to completely prevent LLM hallucinations:
     - **Visa Sponsorship Required:** `Yes` (F-1 student seeking eventual H-1B sponsorship)
     - **Legally Authorized to Work:** `Yes` (Authorized via CPT and 3-Year STEM OPT)
     - **Security Clearance:** `None / Eligible for Public Trust` | US Citizen: `No`
     - **Personal & Demographics:** Name, Email, Phone, SMSU degree details, EEO disclosures.

2. **Smart "Human-in-the-Loop" Checkpoint:**
   - Populates every input, combobox, and dropdown.
   - Auto-attaches the tailored 1-page ATS PDF resume (`data/tailored/`).
   - Injects a cyberpunk HUD overlay (`#jarvis-hitl-hud`) onto the live browser page summarizing fields filled, work auth status, and resume attachment.
   - Strictly halts on the final review screen so the candidate can inspect answers and click Submit with 1 click.
   - Avoids anti-bot flags, email reputation blocks, or accidental misstatements.

---

## 📁 Directory Structure

```
cyber_auto_applier/
├── config/
│   ├── profile.json            # Authoritative candidate profile (Shadman Ahsan)
│   ├── settings.json           # Model parameters & cybersecurity keywords
│   ├── credentials.json        # Credential vault for automated logins
│   ├── employers.yaml          # 48+ enterprise Workday portals
│   └── storage_state.json      # Cached browser sessions & cookies
├── core/
│   ├── db.py                   # SQLite WAL mode database engine
│   ├── hygiene.py              # Log rotation, Chromium cache purge & disk maintenance
│   ├── llm_client.py           # Token-optimized Gemini 2.5 Pro client
│   ├── matcher.py              # Tier-1 rule filter + Tier-2 Gemini scoring
│   ├── tailor_validator.py     # Content validator & anti-hallucination guard
│   └── credentials_manager.py  # Vault for portal logins
├── scrapers/
│   ├── github_internships.py   # SimplifyJobs & PittCSC markdown table scraper
│   ├── workday_direct.py       # Zero-token pure HTTP Workday CXS JSON scraper
│   ├── multi_board_scraper.py  # Indeed & LinkedIn aggregator with JobSpy + guest API
│   ├── migratemate_scraper.py  # Verified visa sponsorship & LCA scraper
│   └── handshake_scraper.py    # Collegiate internship portal scraper
├── automation/
│   ├── ats_form_filler.py      # Combobox/dropdown parser & HITL checkpoint (TorontoDeveloper)
│   ├── resume_generator.py     # Headless Playwright ATS 1-page PDF compiler
│   ├── direct_api.py           # 300ms Direct HTTP POST submitter (Greenhouse/Lever)
│   ├── browser.py              # Stealth Playwright browser manager
│   ├── workday.py              # Workday automated login & ATSFormFiller submitter
│   ├── real_browser_session.py # Real Chrome automation with live HUD
│   ├── linkedin_automation.py  # LinkedIn Easy Apply modal automation
│   ├── indeed_automation.py    # Indeed Apply 1-click & multi-step automation
│   ├── handshake_automation.py # Handshake collegiate quick apply
│   └── migratemate_automation.py# Visa sponsorship application router
├── agents/
│   └── swarm.py                # 24/7 Autonomous Multi-Agent Swarm (Scout, Analyst, Submitter, Sentinel)
├── static/
│   ├── index.html              # Cyber J.A.R.V.I.S. Command Center UI
│   └── jarvis_app.js           # Real-time state & control matrix
├── tests/
│   └── test_ui_and_workflow.py # 16-test comprehensive automated verification suite
├── data/
│   ├── applications.db         # SQLite application database
│   ├── browser_profile/        # Persistent browser profile
│   └── tailored/               # Generated tailored 1-page PDF resumes
├── server.py                   # FastAPI REST backend & SSE log stream
├── main.py                     # CLI entrypoint
└── requirements.txt
```

