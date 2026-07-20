"""Real-time job sources — DevOps, Kubernetes, Cloud, IAM focus. Last 24h preferred."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import os
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import httpx

HEADERS = {"User-Agent": "JobHuntAgent/2.0 (personal job search)"}

# Core search terms — DevOps / K8s / Cloud / IAM
SEARCH_QUERIES = [
    "DevOps Engineer",
    "Kubernetes Engineer",
    "Cloud Engineer",
    "IAM Engineer",
    "DevSecOps Engineer",
    "Site Reliability Engineer",
    "Platform Engineer",
    "Azure Engineer",
    "AWS Cloud Engineer",
    "Cloud Security Engineer",
    "Identity Access Management",
]

REMOTEOK_TAGS = [
    "devops",
    "kubernetes",
    "cloud",
    "aws",
    "azure",
    "sre",
    "security",
    "terraform",
    "docker",
]

REMOTIVE_CATEGORIES = [
    "devops",
    "software-dev",
]

# Title must hit at least one of these (core focus)
TITLE_KEYWORDS = [
    "devops", "devsecops", "dev ops", "kubernetes", "k8s",
    "cloud", "azure", "aws", "gcp", "sre", "site reliability",
    "platform engineer", "iam", "identity", "access management",
    "infrastructure", "terraform", "cloud security", "aks", "eks",
]

DOMAIN_KEYWORDS = TITLE_KEYWORDS + [
    "helm", "docker", "rbac", "entra", "okta", "pam",
    "ansible", "ci/cd", "cloudops",
]


def _job_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}|{title}".encode()).hexdigest()[:12]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def is_domain_relevant(job: dict) -> bool:
    """Keep DevOps / K8s / Cloud / IAM openings — prefer title match."""
    title = (job.get("title") or "").lower()
    if any(k in title for k in TITLE_KEYWORDS):
        return True
    text = f"{title} {job.get('description', '')}".lower()
    strong = (
        "devops", "kubernetes", "k8s", "cloud engineer",
        "iam ", "devsecops", "site reliability",
    )
    return any(k in text for k in strong)


def get_search_queries(extra: list[str] | None = None) -> list[str]:
    queries = list(SEARCH_QUERIES)
    if extra:
        for q in extra:
            if q not in queries:
                queries.append(q)
    return queries


async def fetch_remotive(category: str = "devops") -> list[dict]:
    jobs = []
    url = f"https://remotive.com/api/remote-jobs?category={category}&limit=100"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
            for item in r.json().get("jobs", []):
                pub = item.get("publication_date") or datetime.now(timezone.utc).isoformat()
                jobs.append({
                    "id": _job_id(item.get("url", ""), item.get("title", "")),
                    "title": item.get("title", ""),
                    "company": item.get("company_name", "Unknown"),
                    "location": item.get("candidate_required_location", "Remote"),
                    "description": _strip_html(item.get("description", ""))[:4000],
                    "url": item.get("url", ""),
                    "source": "remotive",
                    "posted_at": pub,
                })
        except Exception as e:
            print(f"Remotive ({category}) error: {e}")
    return jobs


async def fetch_arbeitnow(search: str = "") -> list[dict]:
    jobs = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    params = {}
    if search:
        params["search"] = search
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, headers=HEADERS, params=params or None)
            r.raise_for_status()
            for item in r.json().get("data", [])[:100]:
                link = item.get("url", "")
                title = item.get("title", "")
                created = item.get("created_at")
                if created:
                    posted = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
                else:
                    posted = datetime.now(timezone.utc).isoformat()
                jobs.append({
                    "id": _job_id(link, title),
                    "title": title,
                    "company": item.get("company_name", "Unknown"),
                    "location": item.get("location", "Remote"),
                    "description": _strip_html(item.get("description", ""))[:4000],
                    "url": link,
                    "source": "arbeitnow",
                    "posted_at": posted,
                })
        except Exception as e:
            print(f"Arbeitnow ({search or 'all'}) error: {e}")
    return jobs


async def fetch_remoteok(tags: str = "devops") -> list[dict]:
    jobs = []
    url = f"https://remoteok.com/api?tags={tags}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            for item in data[1:80] if isinstance(data, list) and len(data) > 1 else []:
                if not isinstance(item, dict):
                    continue
                link = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
                if not link.startswith("http"):
                    link = f"https://remoteok.com{link}"
                title = item.get("position") or item.get("title") or "Remote Role"
                # RemoteOK epoch can be in epoch field
                epoch = item.get("epoch") or item.get("date")
                if isinstance(epoch, (int, float)):
                    posted = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                else:
                    posted = str(epoch) if epoch else datetime.now(timezone.utc).isoformat()
                jobs.append({
                    "id": _job_id(link, title),
                    "title": title,
                    "company": item.get("company", "Unknown"),
                    "location": "Remote",
                    "description": _strip_html(item.get("description", ""))[:4000],
                    "url": link,
                    "source": "remoteok",
                    "posted_at": posted,
                })
        except Exception as e:
            print(f"RemoteOK ({tags}) error: {e}")
    return jobs


async def fetch_jobicy(tag: str = "devops") -> list[dict]:
    """Jobicy free API — remote jobs by tag."""
    jobs = []
    url = f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
            for item in r.json().get("jobs", []):
                link = item.get("url", "")
                title = item.get("jobTitle", "")
                jobs.append({
                    "id": _job_id(link, title),
                    "title": title,
                    "company": item.get("companyName", "Unknown"),
                    "location": item.get("jobGeo", "Remote"),
                    "description": _strip_html(item.get("jobDescription", ""))[:4000],
                    "url": link,
                    "source": "jobicy",
                    "posted_at": item.get("pubDate") or datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"Jobicy ({tag}) error: {e}")
    return jobs


async def fetch_himalayas(keyword: str = "devops") -> list[dict]:
    """Himalayas remote jobs API."""
    jobs = []
    url = "https://himalayas.app/jobs/api"
    params = {"limit": 50, "offset": 0}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            data = r.json()
            items = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
            for item in items[:80]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("jobTitle") or ""
                link = item.get("applicationLink") or item.get("url") or item.get("guid") or ""
                if not title:
                    continue
                # Client-side keyword filter (API may not support search)
                blob = f"{title} {item.get('excerpt', '')} {' '.join(item.get('categories', []) or [])}".lower()
                if keyword and keyword.lower() not in blob and not any(
                    k in blob for k in ("devops", "kubernetes", "cloud", "aws", "azure", "sre", "iam")
                ):
                    continue
                pub = item.get("pubDate") or item.get("postedAt") or item.get("createdAt")
                if isinstance(pub, (int, float)):
                    posted = datetime.fromtimestamp(pub / 1000 if pub > 1e12 else pub, tz=timezone.utc).isoformat()
                else:
                    posted = str(pub) if pub else datetime.now(timezone.utc).isoformat()
                jobs.append({
                    "id": _job_id(link or title, title),
                    "title": title,
                    "company": (item.get("companyName") or item.get("company") or "Unknown"),
                    "location": item.get("location") or "Remote",
                    "description": _strip_html(item.get("description") or item.get("excerpt") or "")[:4000],
                    "url": link or f"https://himalayas.app/jobs",
                    "source": "himalayas",
                    "posted_at": posted,
                })
        except Exception as e:
            print(f"Himalayas error: {e}")
    return jobs


async def fetch_jsearch(query: str, location: str = "India") -> list[dict]:
    """RapidAPI JSearch — LinkedIn/Indeed/Glassdoor (needs RAPIDAPI_KEY)."""
    key = os.getenv("RAPIDAPI_KEY", "")
    if not key:
        return []
    jobs = []
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        **HEADERS,
    }
    params = {
        "query": f"{query} in {location}",
        "date_posted": "today",
        "num_pages": "1",
    }
    async with httpx.AsyncClient(timeout=35) as client:
        try:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            for item in r.json().get("data", []):
                link = item.get("job_apply_link") or item.get("job_google_link", "")
                title = item.get("job_title", "")
                jobs.append({
                    "id": _job_id(link, title),
                    "title": title,
                    "company": item.get("employer_name", "Unknown"),
                    "location": item.get("job_location", location),
                    "description": (item.get("job_description") or "")[:4000],
                    "url": link,
                    "source": "jsearch",
                    "posted_at": item.get("job_posted_at_datetime_utc")
                    or datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"JSearch ({query}) error: {e}")
    return jobs


async def fetch_rss_feeds(feed_urls: list[str] | None = None) -> list[dict]:
    """Parse job RSS feeds (LinkedIn alerts, company feeds)."""
    if feed_urls is None:
        raw = os.getenv("RSS_FEED_URLS", "")
        feed_urls = [u.strip() for u in raw.split(",") if u.strip()]
    if not feed_urls:
        return []

    jobs = []
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for feed_url in feed_urls:
            try:
                r = await client.get(feed_url, headers=HEADERS)
                r.raise_for_status()
                root = ET.fromstring(r.content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//item") or root.findall(".//atom:entry", ns)
                for item in items[:40]:
                    title = (
                        item.findtext("title")
                        or item.findtext("atom:title", namespaces=ns)
                        or ""
                    ).strip()
                    link = item.findtext("link") or ""
                    if not link:
                        el = item.find("atom:link", ns)
                        link = el.get("href", "") if el is not None else ""
                    desc = (
                        item.findtext("description")
                        or item.findtext("atom:summary", namespaces=ns)
                        or ""
                    )
                    pub = (
                        item.findtext("pubDate")
                        or item.findtext("atom:updated", namespaces=ns)
                        or datetime.now(timezone.utc).isoformat()
                    )
                    if title and link:
                        jobs.append({
                            "id": _job_id(link, title),
                            "title": title[:200],
                            "company": title.split(" at ")[-1][:80] if " at " in title else "See posting",
                            "location": "See posting",
                            "description": _strip_html(desc)[:4000],
                            "url": link.strip(),
                            "source": "rss",
                            "posted_at": pub,
                        })
            except Exception as e:
                print(f"RSS error ({feed_url}): {e}")
    return jobs


async def fetch_all_free_sources(queries: list[str] | None = None) -> list[dict]:
    """Aggregate ALL sources in parallel for DevOps / K8s / Cloud / IAM."""
    from services.job_search import search_adzuna, search_serpapi_google_jobs

    queries = get_search_queries(queries)

    tasks: list = []

    # Remotive categories
    for cat in REMOTIVE_CATEGORIES:
        tasks.append(fetch_remotive(cat))

    # Arbeitnow — topic searches
    for term in ("devops", "kubernetes", "cloud", "aws", "azure", "sre", "iam"):
        tasks.append(fetch_arbeitnow(term))

    # RemoteOK tags
    for tag in REMOTEOK_TAGS:
        tasks.append(fetch_remoteok(tag))

    # Jobicy tags
    for tag in ("devops", "cloud", "aws", "azure", "kubernetes", "security"):
        tasks.append(fetch_jobicy(tag))

    # Himalayas
    tasks.append(fetch_himalayas("devops"))

    # RSS from env
    tasks.append(fetch_rss_feeds())

    # Paid/optional APIs — top focused queries
    for q in queries[:8]:
        tasks.append(fetch_jsearch(q, "India"))
        tasks.append(search_adzuna(q))
        tasks.append(search_serpapi_google_jobs(q))

    # If RSS feed URLs are provided (e.g., LinkedIn job alert RSS), include them
    rss_env = os.getenv("RSS_FEED_URLS", "")
    if rss_env:
        feed_urls = [u.strip() for u in rss_env.split(",") if u.strip()]
        if feed_urls:
            tasks.append(fetch_rss_feeds(feed_urls))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs: dict[str, dict] = {}
    source_counts: dict[str, int] = {}

    for batch in results:
        if isinstance(batch, Exception):
            print(f"Source task failed: {batch}")
            continue
        for job in batch:
            if not is_domain_relevant(job):
                continue
            all_jobs[job["id"]] = job
            src = job.get("source", "?")
            source_counts[src] = source_counts.get(src, 0) + 1

    print(f"Fetched {len(all_jobs)} domain-relevant jobs from sources: {source_counts}")
    return list(all_jobs.values())
