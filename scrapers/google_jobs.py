import urllib.request
import urllib.parse
import re
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def parse_ats_from_url(url: str) -> str:
    url_lower = url.lower()
    if "greenhouse.io" in url_lower:
        return "GREENHOUSE"
    elif "lever.co" in url_lower:
        return "LEVER"
    elif "myworkdayjobs.com" in url_lower or "workday" in url_lower:
        return "WORKDAY"
    elif "linkedin.com" in url_lower:
        return "LINKEDIN"
    else:
        return "DIRECT_CAREER_SITE"

def scrape_google_jobs() -> List[Dict[str, Any]]:
    """
    Fetches real live remote cybersecurity, SOC, and information security
    job openings from live remote employment feeds.
    """
    discovered_jobs = []
    
    # 1. Remotive Live Cybersecurity & Security API
    try:
        url = "https://remotive.com/api/remote-jobs?search=security"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for item in data.get("jobs", []):
                title = item.get("title", "")
                # Only include relevant security positions
                if re.search(r'security|cyber|soc\b|infosec|cloud sec|appsec|compliance', title, re.I):
                    apply_url = item.get("url", "")
                    discovered_jobs.append({
                        "company": item.get("company_name", "Tech Company"),
                        "title": title,
                        "location": item.get("candidate_required_location", "Remote"),
                        "url": apply_url,
                        "ats_type": parse_ats_from_url(apply_url),
                        "source": "Remotive Live Security Feed",
                        "raw_description": item.get("description", "")[:1000]
                    })
    except Exception as e:
        logger.warning(f"[Live Security Feed] Remotive fetch error: {e}")

    logger.info(f"[Live Jobs Scraper] Successfully fetched {len(discovered_jobs)} REAL live cybersecurity job postings.")
    return discovered_jobs

if __name__ == "__main__":
    jobs = scrape_google_jobs()
    print(f"Total live jobs returned: {len(jobs)}")
    for j in jobs[:3]:
        print(f"[{j['ats_type']}] {j['company']} - {j['title']} -> {j['url']}")
