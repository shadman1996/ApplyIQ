"""
Workday ATS direct API scraper for cyber_auto_applier.
Discovers jobs directly via Workday's undocumented CXS JSON API.
Zero LLM tokens, zero browser overhead, pure HTTP.
Absorbed and enhanced from ApplyPilot for high performance.
"""

import os
import json
import logging
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPLOYERS_FILE = os.path.join(PROJECT_ROOT, "config", "employers.yaml")

DEFAULT_CYBER_KEYWORDS = [
    "cyber",
    "cybersecurity",
    "security intern",
    "information security",
    "soc analyst",
    "security engineer",
    "devsecops",
    "threat intelligence",
]

# Curated fallback employers if employers.yaml is not present
FALLBACK_EMPLOYERS = {
    "motorola": {
        "name": "Motorola Solutions",
        "tenant": "motorolasolutions",
        "site_id": "Careers",
        "base_url": "https://motorolasolutions.wd5.myworkdayjobs.com",
    },
    "cisco": {
        "name": "Cisco",
        "tenant": "cisco",
        "site_id": "Cisco_Careers",
        "base_url": "https://cisco.wd5.myworkdayjobs.com",
    },
    "nvidia": {
        "name": "NVIDIA",
        "tenant": "nvidia",
        "site_id": "NVIDIAExternalCareerSite",
        "base_url": "https://nvidia.wd5.myworkdayjobs.com",
    },
    "salesforce": {
        "name": "Salesforce",
        "tenant": "salesforce",
        "site_id": "External_Career_Site",
        "base_url": "https://salesforce.wd12.myworkdayjobs.com",
    },
    "blackberry": {
        "name": "BlackBerry",
        "tenant": "bb",
        "site_id": "BlackBerry",
        "base_url": "https://bb.wd3.myworkdayjobs.com",
    },
    "td": {
        "name": "TD Bank",
        "tenant": "td",
        "site_id": "TD_Bank_Careers",
        "base_url": "https://td.wd3.myworkdayjobs.com",
    },
    "servicenow": {
        "name": "ServiceNow",
        "tenant": "servicenow",
        "site_id": "ServiceNowCareers",
        "base_url": "https://servicenow.wd1.myworkdayjobs.com",
    },
    "mastercard": {
        "name": "Mastercard",
        "tenant": "mastercard",
        "site_id": "CorporateCareers",
        "base_url": "https://mastercard.wd1.myworkdayjobs.com",
    },
}


class _HTMLStripper(HTMLParser):
    """Strip HTML tags and preserve text content."""

    def __init__(self):
        super().__init__()
        self._parts: List[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        elif tag in ("p", "div", "li", "tr"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def strip_html(html: str) -> str:
    """Convert HTML job descriptions to clean plain text."""
    if not html:
        return ""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def load_employers() -> Dict[str, Any]:
    """Load Workday employer registry from config/employers.yaml or fallback."""
    if os.path.exists(EMPLOYERS_FILE) and yaml:
        try:
            with open(EMPLOYERS_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                employers = data.get("employers", {})
                if employers:
                    return employers
        except Exception as e:
            logger.warning(f"Error loading employers.yaml: {e}")
    return FALLBACK_EMPLOYERS


def workday_search(
    employer: Dict[str, Any], search_text: str, limit: int = 20, offset: int = 0
) -> Dict[str, Any]:
    """Execute a search query against the Workday CXS JSON API."""
    url = f"{employer['base_url']}/wday/cxs/{employer['tenant']}/{employer['site_id']}/jobs"
    payload = json.dumps({
        "appliedFacets": {},
        "limit": limit,
        "offset": offset,
        "searchText": search_text,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")

    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def workday_detail(employer: Dict[str, Any], external_path: str) -> Dict[str, Any]:
    """Fetch full job detail (description, external URL, req ID) from CXS API."""
    url = f"{employer['base_url']}/wday/cxs/{employer['tenant']}/{employer['site_id']}{external_path}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")

    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def fetch_job_detail_safe(employer: Dict[str, Any], posting: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch detail for a posting, catching exceptions gracefully."""
    ext_path = posting.get("externalPath", "")
    full_desc = ""
    apply_url = ""

    if ext_path:
        try:
            detail = workday_detail(employer, ext_path)
            info = detail.get("jobPostingInfo", {})
            full_desc = strip_html(info.get("jobDescription", ""))
            apply_url = info.get("externalUrl", "")
        except Exception as e:
            logger.debug(f"Failed to fetch detail for {ext_path}: {e}")

    # Fallback to direct URL if externalUrl is empty
    if not apply_url and ext_path:
        apply_url = f"{employer['base_url']}/{employer['site_id']}{ext_path}"

    return {
        "title": posting.get("title", "Cybersecurity Specialist"),
        "company": employer.get("name", "Enterprise Corp"),
        "location": posting.get("locationsText", "Remote / Multiple Locations"),
        "url": apply_url,
        "ats_type": "WORKDAY",
        "raw_description": full_desc or f"Role: {posting.get('title')}. Located at {posting.get('locationsText', 'N/A')}.",
        "source": f"Workday CXS ({employer.get('name')})",
        "posted_on": posting.get("postedOn", ""),
    }


def search_employer_cyber_jobs(
    employer_key: str,
    employer: Dict[str, Any],
    keywords: List[str],
    max_per_employer: int = 5,
) -> List[Dict[str, Any]]:
    """Search a single employer across cyber keywords and fetch full job details."""
    discovered: List[Dict[str, Any]] = []
    seen_paths = set()

    for kw in keywords:
        try:
            res = workday_search(employer, kw, limit=10, offset=0)
            postings = res.get("jobPostings", [])
            for p in postings:
                ext_path = p.get("externalPath", "")
                if ext_path and ext_path not in seen_paths:
                    seen_paths.add(ext_path)
                    detail = fetch_job_detail_safe(employer, p)
                    discovered.append(detail)
                    if len(discovered) >= max_per_employer:
                        return discovered
        except Exception as e:
            logger.debug(f"Error searching {employer.get('name')} for '{kw}': {e}")
            break

    return discovered


def scrape_workday_employers(
    keywords: Optional[List[str]] = None,
    employer_keys: Optional[List[str]] = None,
    max_total: int = 25,
    max_workers: int = 4,
) -> List[Dict[str, Any]]:
    """
    Scrapes Workday CXS APIs across top enterprise tech/cyber employers in parallel.
    Returns structured job dictionaries compatible with cyber_auto_applier.
    """
    if keywords is None:
        keywords = ["cyber", "security", "security intern", "information security"]

    all_employers = load_employers()

    # If specific employers requested, filter down; otherwise pick high-relevance tech/defense targets
    if employer_keys:
        targets = {k: all_employers[k] for k in employer_keys if k in all_employers}
    else:
        # Prioritize top cybersecurity / tech / defense enterprise employers
        preferred = [
            "motorola", "cisco", "nvidia", "salesforce", "blackberry",
            "servicenow", "mastercard", "paypal", "td", "adobe"
        ]
        targets = {k: all_employers[k] for k in preferred if k in all_employers}
        if not targets:
            targets = dict(list(all_employers.items())[:8])

    results: List[Dict[str, Any]] = []
    logger.info(f"[WorkdayCXS] Querying {len(targets)} enterprise employers with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(search_employer_cyber_jobs, k, emp, keywords): k
            for k, emp in targets.items()
        }
        for future in as_completed(futures):
            k = futures[future]
            try:
                emp_jobs = future.result()
                results.extend(emp_jobs)
                logger.info(f"[WorkdayCXS] {targets[k]['name']}: found {len(emp_jobs)} cyber postings.")
            except Exception as e:
                logger.warning(f"[WorkdayCXS] Error processing {k}: {e}")

    logger.info(f"[WorkdayCXS] Harvested {len(results)} total enterprise Workday positions.")
    return results[:max_total]
