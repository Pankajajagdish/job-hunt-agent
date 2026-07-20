"""Job search from Adzuna, SerpAPI Google Jobs, and career page parser.

Finds DevOps / Kubernetes / Cloud / IAM jobs (India + Remote) posted in last 24h.
"""

import os
import hashlib
from datetime import datetime, timezone, timedelta
import httpx
from bs4 import BeautifulSoup
from services.matcher import filter_and_rank
from services.profile import load_profile

ROLE_KEYWORDS = [
    "DevOps",
    "DevSecOps",
    "Kubernetes",
    "Cloud Engineer",
    "IAM",
    "Cloud Security",
    "SRE",
    "Platform Engineer",
    "Azure Engineer",
]

INDIAN_CITIES = [
    "bangalore", "bengaluru", "mumbai", "delhi", "gurgaon", "gurugram",
    "noida", "pune", "hyderabad", "chennai", "kolkata", "jaipur",
    "ahmedabad", "india",
]


def location_is_india_or_remote(location: str | None) -> bool:
    if not location:
        # Many remote boards omit location — keep them
        return True
    l = location.lower()
    if "remote" in l or "worldwide" in l or "anywhere" in l:
        return True
    if "india" in l:
        return True
    return any(c in l for c in INDIAN_CITIES)


def parse_iso_or_fallback(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        s = dt_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        pass
    for f in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(dt_str, f)
        except Exception:
            continue
    return None


async def search_adzuna(query: str, location: str = "in", max_results: int = 50) -> list[dict]:
    """Adzuna India — last 24h (max_days_old=1)."""
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        return []

    url = f"https://api.adzuna.com/v1/api/jobs/{location}/search/1"
    where = os.getenv("ADZUNA_WHERE", "")
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(max_results, 50),
        "what": query,
        "where": where,
        "max_days_old": 1,
        "content-type": "application/json",
    }
    jobs = []
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            for item in data.get("results", []):
                posted = item.get("created") or item.get("created_at")
                jobs.append({
                    "id": hashlib.md5(item.get("redirect_url", "").encode()).hexdigest()[:12],
                    "title": item.get("title", ""),
                    "company": item.get("company", {}).get("display_name", "Unknown"),
                    "location": item.get("location", {}).get("display_name", ""),
                    "description": item.get("description", ""),
                    "url": item.get("redirect_url", ""),
                    "source": "adzuna",
                    "posted_at": posted or datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"Adzuna ({query}) error: {e}")
    return jobs


async def search_serpapi_google_jobs(query: str, location: str = "India") -> list[dict]:
    api_key = os.getenv("SERPAPI_KEY", "")
    if not api_key:
        return []

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": api_key,
        "chips": "date_posted:today",
    }
    jobs = []
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get("https://serpapi.com/search", params=params)
            r.raise_for_status()
            data = r.json()
            for item in data.get("jobs_results", []):
                link = item.get("apply_options", [{}])[0].get("link") or item.get("share_link", "")
                posted = item.get("date_posted") or item.get("posted_at")
                jobs.append({
                    "id": hashlib.md5(link.encode()).hexdigest()[:12],
                    "title": item.get("title", ""),
                    "company": item.get("company_name", "Unknown"),
                    "location": item.get("location", location),
                    "description": item.get("description", ""),
                    "url": link,
                    "source": "google_jobs",
                    "posted_at": posted or datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"SerpAPI error: {e}")
    return jobs


def get_demo_jobs() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    templates = [
        ("DevOps Engineer", "Kubernetes, Terraform, CI/CD, Azure, AWS"),
        ("DevSecOps Engineer", "Azure, AKS, CI/CD, Defender for Cloud, Terraform"),
        ("Cloud Engineer", "Microsoft Azure, Kubernetes, IAM, Key Vault"),
        ("IAM Engineer", "Entra ID, RBAC, PAM, Identity, Azure"),
        ("Site Reliability Engineer", "AKS, Prometheus, Grafana, Python automation"),
    ]
    jobs = []
    for i, (title, skills) in enumerate(templates):
        jobs.append({
            "id": f"demo{i}",
            "title": title,
            "company": f"Tech Company {i+1}",
            "location": "Pune, India / Remote",
            "description": f"{title} role requiring {skills}. 2-4 years experience.",
            "url": f"https://www.linkedin.com/jobs/search/?keywords={title.replace(' ', '%20')}",
            "source": "demo",
            "posted_at": now,
        })
    return jobs


async def parse_career_page(url: str) -> list[dict]:
    jobs = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers={"User-Agent": "JobHuntAgent/2.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.string if soup.title else "Career Page"
            text = soup.get_text(separator=" ", strip=True)[:3000]
            jobs.append({
                "id": hashlib.md5(url.encode()).hexdigest()[:12],
                "title": f"Roles at {title[:60]}",
                "company": title.split("|")[0].strip()[:80],
                "location": "See career site",
                "description": text,
                "url": url,
                "source": "career_site",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"Career page parse error: {e}")
    return jobs


async def search_all(
    queries: list[str] | None = None,
    career_urls: list[str] | None = None,
    min_score: int = 30,
    include_demo: bool = False,
) -> list[dict]:
    """Search providers for DevOps/K8s/Cloud/IAM — last 24h, India or Remote."""
    queries = queries or ROLE_KEYWORDS
    all_jobs: dict[str, dict] = {}

    for q in queries:
        for job in await search_adzuna(q, location="in"):
            all_jobs[job["id"]] = job

    for q in queries:
        for job in await search_serpapi_google_jobs(q, location="India"):
            all_jobs[job["id"]] = job
        for job in await search_serpapi_google_jobs(q, location="Remote"):
            all_jobs[job["id"]] = job

    if career_urls:
        for url in career_urls:
            for job in await parse_career_page(url):
                all_jobs[job["id"]] = job

    jobs_list = list(all_jobs.values())
    if not jobs_list and include_demo:
        jobs_list = get_demo_jobs()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent: list[dict] = []
    for j in jobs_list:
        if j.get("source") == "demo" and not include_demo:
            continue
        posted_raw = j.get("posted_at")
        posted_dt = None
        if isinstance(posted_raw, (int, float)):
            try:
                posted_dt = datetime.fromtimestamp(int(posted_raw), tz=timezone.utc)
            except Exception:
                posted_dt = None
        elif isinstance(posted_raw, str):
            posted_dt = parse_iso_or_fallback(posted_raw)
            if posted_dt and posted_dt.tzinfo is None:
                posted_dt = posted_dt.replace(tzinfo=timezone.utc)

        if not posted_dt:
            if j.get("source") in ("google_jobs", "adzuna", "jsearch"):
                posted_dt = datetime.now(timezone.utc)
            else:
                continue

        if posted_dt < cutoff:
            continue
        if location_is_india_or_remote(j.get("location")):
            recent.append(j)

    return filter_and_rank(recent, min_score=min_score)
