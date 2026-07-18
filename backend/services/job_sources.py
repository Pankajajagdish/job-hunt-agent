"""Free real-time job sources — no API key required."""

import hashlib
import re
import os
from datetime import datetime, timezone
import httpx
import xml.etree.ElementTree as ET


def _job_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}|{title}".encode()).hexdigest()[:12]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


async def fetch_remotive(category: str = "devops") -> list[dict]:
    jobs = []
    url = f"https://remotive.com/api/remote-jobs?category={category}&limit=50"
    async with httpx.AsyncClient(timeout=25) as client:
        try:
            r = await client.get(url, headers={"User-Agent": "JobHuntAgent/1.0"})
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
            print(f"Remotive error: {e}")
    return jobs


async def fetch_arbeitnow() -> list[dict]:
    jobs = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    async with httpx.AsyncClient(timeout=25) as client:
        try:
            r = await client.get(url, headers={"User-Agent": "JobHuntAgent/1.0"})
            r.raise_for_status()
            for item in r.json().get("data", [])[:80]:
                link = item.get("url", "")
                title = item.get("title", "")
                jobs.append({
                    "id": _job_id(link, title),
                    "title": title,
                    "company": item.get("company_name", "Unknown"),
                    "location": item.get("location", "Remote"),
                    "description": _strip_html(item.get("description", ""))[:4000],
                    "url": link,
                    "source": "arbeitnow",
                    "posted_at": datetime.fromtimestamp(
                        item.get("created_at", 0), tz=timezone.utc
                    ).isoformat() if item.get("created_at") else datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"Arbeitnow error: {e}")
    return jobs


async def fetch_remoteok(tags: str = "devops") -> list[dict]:
    jobs = []
    url = f"https://remoteok.com/api?tags={tags}"
    async with httpx.AsyncClient(timeout=25) as client:
        try:
            r = await client.get(url, headers={"User-Agent": "JobHuntAgent/1.0"})
            r.raise_for_status()
            data = r.json()
            for item in data[1:51] if isinstance(data, list) and len(data) > 1 else []:
                if not isinstance(item, dict):
                    continue
                link = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
                if not link.startswith("http"):
                    link = f"https://remoteok.com{link}"
                title = item.get("position") or item.get("title") or "Remote Role"
                jobs.append({
                    "id": _job_id(link, title),
                    "title": title,
                    "company": item.get("company", "Unknown"),
                    "location": "Remote",
                    "description": _strip_html(item.get("description", ""))[:4000],
                    "url": link,
                    "source": "remoteok",
                    "posted_at": item.get("date") or datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"RemoteOK error: {e}")
    return jobs


async def fetch_jsearch(query: str, location: str = "India") -> list[dict]:
    """RapidAPI JSearch — set RAPIDAPI_KEY in .env for LinkedIn/Indeed aggregated jobs."""
    import os
    key = os.getenv("RAPIDAPI_KEY", "")
    if not key:
        return []
    jobs = []
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    params = {"query": f"{query} in {location}", "date_posted": "today", "num_pages": "2"}
    async with httpx.AsyncClient(timeout=30) as client:
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
                    "description": item.get("job_description", "")[:4000],
                    "url": link,
                    "source": "jsearch",
                    "posted_at": item.get("job_posted_at_datetime_utc") or datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"JSearch error: {e}")
    return jobs


async def fetch_rss_feeds(feed_urls: list[str]) -> list[dict]:
    """Parse job RSS feeds (LinkedIn alert RSS, company feeds, etc.)."""
    jobs = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for feed_url in feed_urls:
            try:
                r = await client.get(feed_url, headers={"User-Agent": "JobHuntAgent/1.0"})
                r.raise_for_status()
                root = ET.fromstring(r.content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//item") or root.findall(".//atom:entry", ns)
                for item in items[:30]:
                    title = (item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "").strip()
                    link = (item.findtext("link") or "")
                    if not link:
                        el = item.find("atom:link", ns)
                        link = el.get("href", "") if el is not None else ""
                    desc = (item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "")
                    pub = (item.findtext("pubDate") or item.findtext("atom:updated", namespaces=ns)
                           or datetime.now(timezone.utc).isoformat())
                    if title and link:
                        jobs.append({
                            "id": _job_id(link, title),
                            "title": title[:200],
                            "company": title.split(" at ")[-1][:80] if " at " in title else "See posting",
                            "location": "India",
                            "description": _strip_html(desc)[:4000],
                            "url": link.strip(),
                            "source": "rss",
                            "posted_at": pub,
                        })
            except Exception as e:
                print(f"RSS error ({feed_url}): {e}")
    return jobs


async def fetch_all_free_sources(queries: list[str]) -> list[dict]:
    """Aggregate all free real-time sources in parallel."""
    import asyncio
    from services.job_search import search_adzuna, search_serpapi_google_jobs

    tasks = [
        fetch_remotive("devops"),
        fetch_remotive("software-dev"),
        fetch_arbeitnow(),
        fetch_remoteok("devops"),
        fetch_remoteok("cloud"),
    ]
    for q in queries[:3]:
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
    for batch in results:
        if isinstance(batch, Exception):
            continue
        for job in batch:
            all_jobs[job["id"]] = job
    return list(all_jobs.values())
