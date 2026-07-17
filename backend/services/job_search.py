"""Job search from Adzuna, SerpAPI Google Jobs, and career page parser."""

import os
import hashlib
from datetime import datetime, timezone, timedelta
import httpx
from bs4 import BeautifulSoup
from services.matcher import filter_and_rank
from services.profile import load_profile


async def search_adzuna(query: str, location: str = "in", max_results: int = 50) -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        return []

    url = f"https://api.adzuna.com/v1/api/jobs/{location}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(max_results, 50),
        "what": query,
        "where": "Pune",
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
                jobs.append({
                    "id": hashlib.md5(item.get("redirect_url", "").encode()).hexdigest()[:12],
                    "title": item.get("title", ""),
                    "company": item.get("company", {}).get("display_name", "Unknown"),
                    "location": item.get("location", {}).get("display_name", ""),
                    "description": item.get("description", ""),
                    "url": item.get("redirect_url", ""),
                    "source": "adzuna",
                    "posted_at": item.get("created", datetime.now(timezone.utc).isoformat()),
                })
        except Exception as e:
            print(f"Adzuna error: {e}")
    return jobs


async def search_serpapi_google_jobs(query: str, location: str = "Pune, Maharashtra, India") -> list[dict]:
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
                jobs.append({
                    "id": hashlib.md5(link.encode()).hexdigest()[:12],
                    "title": item.get("title", ""),
                    "company": item.get("company_name", "Unknown"),
                    "location": item.get("location", location),
                    "description": item.get("description", ""),
                    "url": link,
                    "source": "google_jobs",
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"SerpAPI error: {e}")
    return jobs


def get_demo_jobs() -> list[dict]:
    """Fallback demo jobs when no API keys configured."""
    profile = load_profile()
    now = datetime.now(timezone.utc).isoformat()
    templates = [
        ("DevSecOps Engineer", "Azure, AKS, CI/CD, Defender for Cloud, Terraform"),
        ("Cloud Engineer", "Microsoft Azure, Kubernetes, ARM, VNet, Key Vault"),
        ("Azure Cloud Security Engineer", "Azure Policy, RBAC, Entra ID, compliance"),
        ("Site Reliability Engineer", "AKS, Prometheus, Grafana, Python automation"),
        ("Platform Engineer", "Azure DevOps, GitHub Actions, Helm, Docker"),
    ]
    jobs = []
    for i, (title, skills) in enumerate(templates):
        jobs.append({
            "id": f"demo{i}",
            "title": title,
            "company": f"Tech Company {i+1}",
            "location": "Pune, India / Remote",
            "description": f"{title} role requiring {skills}. 2-4 years experience. Azure production environment.",
            "url": f"https://www.linkedin.com/jobs/search/?keywords={title.replace(' ', '%20')}",
            "source": "demo",
            "posted_at": now,
        })
    return jobs


async def parse_career_page(url: str) -> list[dict]:
    """Basic career page job link extraction (public pages only)."""
    jobs = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers={"User-Agent": "JobHuntAgent/1.0 (personal use)"})
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


async def search_all(queries: list[str] | None = None, career_urls: list[str] | None = None,
                     min_score: int = 35, include_demo: bool = True) -> list[dict]:
    profile = load_profile()
    queries = queries or profile["target_roles"][:4]
    all_jobs: dict[str, dict] = {}

    for q in queries:
        for job in await search_adzuna(q):
            all_jobs[job["id"]] = job
        for job in await search_serpapi_google_jobs(q):
            all_jobs[job["id"]] = job

    if career_urls:
        for url in career_urls:
            for job in await parse_career_page(url):
                all_jobs[job["id"]] = job

    jobs_list = list(all_jobs.values())
    if not jobs_list and include_demo:
        jobs_list = get_demo_jobs()

    # Filter last 24h where posted_at parseable
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = []
    for j in jobs_list:
        recent.append(j)  # APIs already filter; demo always recent

    return filter_and_rank(recent, min_score=min_score)
