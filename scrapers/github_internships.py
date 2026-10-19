import urllib.request
import re
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

RAW_REPOS = [
    {
        "name": "SimplifyJobs 2025 Tech & Security Internships",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/README.md"
    },
    {
        "name": "SimplifyJobs 2026 Tech & Security Internships",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
    }
]

def detect_ats_type(url: str) -> str:
    url_lower = url.lower()
    if "greenhouse.io" in url_lower:
        return "GREENHOUSE"
    elif "lever.co" in url_lower:
        return "LEVER"
    elif "myworkdayjobs.com" in url_lower or "workday" in url_lower:
        return "WORKDAY"
    elif "icims.com" in url_lower:
        return "ICIMS"
    elif "taleo.net" in url_lower:
        return "TALEO"
    elif "linkedin.com" in url_lower:
        return "LINKEDIN"
    elif "oraclecloud.com" in url_lower:
        return "ORACLE_HCM"
    else:
        return "OTHER"

def scrape_github_internships() -> List[Dict[str, Any]]:
    """
    Parses live cybersecurity and security internship listings directly from
    active GitHub internship repositories (SimplifyJobs HTML tables).
    """
    discovered_jobs = []
    
    for repo in RAW_REPOS:
        try:
            req = urllib.request.Request(
                repo["url"],
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                
            # SimplifyJobs tables use HTML <tr><td>...</td></tr>
            rows = re.findall(r'<tr>(.*?)</tr>', content, re.DOTALL)
            last_company = "Tech Enterprise"
            
            for r in rows:
                cols = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
                if not cols:
                    continue
                
                # Extract and clean company name (resolving child rows marked with ↳)
                raw_comp = re.sub(r'<[^>]+>', '', cols[0]).strip()
                if raw_comp and '↳' not in raw_comp:
                    last_company = raw_comp
                company = last_company if '↳' in raw_comp or not raw_comp else raw_comp
                
                # Check entire row text for cybersecurity keywords
                row_text = ' '.join(re.sub(r'<[^>]+>', ' ', c) for c in cols)
                if re.search(r'security|cyber|soc\b|infosec|iam\b|cloud\s*sec|appsec|detection|incident', row_text, re.I):
                    role = re.sub(r'<[^>]+>', '', cols[1]).strip() if len(cols) > 1 else "Security Intern"
                    location = re.sub(r'<[^>]+>', '', cols[2]).strip() if len(cols) > 2 else "USA / Remote"
                    
                    # Extract application URL
                    link_match = re.search(r'href=[\"\'](https?://[^\"\']+)[\"\']', r)
                    app_url = link_match.group(1) if link_match else ""
                    
                    if app_url and "simplify.jobs/p/" not in app_url and "github.com" not in app_url:
                        ats_type = detect_ats_type(app_url)
                        discovered_jobs.append({
                            "company": company,
                            "title": role,
                            "location": location,
                            "url": app_url,
                            "ats_type": ats_type,
                            "source": repo["name"],
                            "raw_description": f"Live {role} role at {company} ({location}). ATS Portal: {ats_type}. Direct application URL: {app_url}"
                        })
        except Exception as e:
            logger.warning(f"[Scraper Warning] Could not fetch from {repo['name']}: {e}")
            
    logger.info(f"[Scraper] Successfully harvested {len(discovered_jobs)} REAL live cybersecurity internship listings.")
    return discovered_jobs

if __name__ == "__main__":
    jobs = scrape_github_internships()
    print(f"Total live jobs harvested: {len(jobs)}")
    for j in jobs[:5]:
        print(f"[{j['ats_type']}] {j['company']} - {j['title']} -> {j['url']}")
