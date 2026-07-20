#!/usr/bin/env python3
"""
GitHub Actions agent:
  1. Find jobs posted in the last 24 hours
  2. Match to your resume profile
  3. Generate tailored resume (DOCX) + JD-specific cover letter per job
  4. Publish to dashboard + GitHub Issues with download links
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.job_cache import refresh_live_jobs  # noqa: E402
from services.resume_tailor import generate_application_package  # noqa: E402

DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
APPS_DIR = DOCS_DIR / "applications"
SEEN_FILE = DATA_DIR / "seen_jobs.json"
FEED_FILE = DOCS_DIR / "jobs_feed.json"
MIN_SCORE = int(os.getenv("MIN_MATCH_SCORE", "30"))
MAX_ISSUES = int(os.getenv("MAX_ISSUES_PER_RUN", "20"))
ISSUE_MIN_SCORE = int(os.getenv("ISSUE_MIN_SCORE", "40"))
DASHBOARD_BASE = os.getenv(
    "DASHBOARD_URL", "https://pankajajagdish.github.io/job-hunt-agent"
)


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))


def save_seen(seen: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(list(seen)[-8000:], indent=2), encoding="utf-8")


def tailor_job(job: dict) -> dict:
    """Generate tailored resume + cover letter; attach paths to job dict."""
    app_dir = APPS_DIR / job["id"]
    if (app_dir / "resume.docx").exists() and (app_dir / "cover_letter.txt").exists():
        cover = (app_dir / "cover_letter.txt").read_text(encoding="utf-8")
        meta_file = app_dir / "meta.json"
        summary = ""
        if meta_file.exists():
            summary = json.loads(meta_file.read_text(encoding="utf-8")).get("tailored_summary", "")
        base = f"applications/{job['id']}"
        job.update({
            "resume_url": f"{base}/resume.docx",
            "cover_letter_url": f"{base}/cover_letter.txt",
            "cover_letter": cover,
            "tailored_summary": summary,
            "application_ready": True,
        })
        return job
    package = generate_application_package(job, app_dir)
    job.update(package)
    print(f"  Tailored: {job['title']} @ {job['company']}")
    return job


def write_feed(jobs: list[dict], new_jobs: list[dict]) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "profile": os.getenv("PROFILE_NAME", "Pankaja Jagdish Kulkarni"),
        "daily_goal": int(os.getenv("DAILY_APPLY_GOAL", "50")),
        "filter": "last_24_hours_india_or_remote",
        "location_policy": "India or Remote only",
        "total": len(jobs),
        "new_count": len(new_jobs),
        "jobs": jobs[:100],
        "new_jobs": new_jobs[:30],
    }
    FEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEED_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_summary(jobs: list[dict], new_jobs: list[dict]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## Job Hunt Agent — Last 24h",
        "",
        f"- **Jobs (last 24h, tailored):** {len(jobs)}",
        f"- **New this run:** {len(new_jobs)}",
        f"- **Dashboard:** {DASHBOARD_BASE}/",
        "",
    ]
    for j in new_jobs[:10]:
        resume = j.get("resume_url", "")
        link = f"{DASHBOARD_BASE}/{resume}" if resume else j.get("url", "")
        lines.append(
            f"- **{j['match_score']}%** {j['title']} @ {j['company']} — "
            f"[Resume]({link}) | [Apply]({j['url']})"
        )
    Path(summary_path).write_text("\n".join(lines), encoding="utf-8")


def create_issue(job: dict) -> bool:
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        return False

    title = f"[Apply] {job['title']} @ {job['company']} ({job['match_score']}%)"
    skills = ", ".join(job.get("matched_skills") or []) or "—"
    resume_link = f"{DASHBOARD_BASE}/{job.get('resume_url', '')}"
    cover = job.get("cover_letter", "Cover letter not generated.")

    body = f"""## Job posted in last 24 hours — application package ready

| | |
|---|---|
| **Match score** | {job['match_score']}% |
| **Posted** | {job.get('posted_at', '—')} |
| **Location** | {job.get('location', '—')} |
| **Source** | {job.get('source', '—')} |
| **Matched skills** | {skills} |

### Tailored summary
{job.get('tailored_summary', '—')}

---

### Download tailored resume
**[Download DOCX]({resume_link})**

### Apply on company site
{job['url']}

---

### Cover letter (copy & paste)

```
{cover}
```

---
_Close this issue after you apply._
"""
    resp = httpx.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": title[:256], "body": body, "labels": ["job-alert"]},
        timeout=30,
    )
    if resp.status_code == 201:
        print(f"Issue created: {title[:70]}")
        return True
    print(f"Issue failed ({resp.status_code}): {resp.text[:200]}")
    return False


async def run() -> int:
    seen = load_seen()
    raw_jobs = await refresh_live_jobs(min_score=MIN_SCORE, include_demo=False)
    print(f"Found {len(raw_jobs)} matching jobs in last 24h")

    new_jobs = [j for j in raw_jobs if j["id"] not in seen]

    # Tailor resume + cover letter for ALL jobs in feed (new first, then existing without package)
    all_tailored: list[dict] = []
    for job in raw_jobs:
        all_tailored.append(tailor_job(dict(job)))

    new_tailored = [j for j in all_tailored if j["id"] in {n["id"] for n in new_jobs}]

    write_feed(all_tailored, new_tailored)
    write_summary(all_tailored, new_tailored)

    issues_created = 0
    for job in sorted(new_tailored, key=lambda x: x.get("match_score", 0), reverse=True):
        if job.get("match_score", 0) < ISSUE_MIN_SCORE:
            continue
        if issues_created >= MAX_ISSUES:
            break
        if create_issue(job):
            issues_created += 1

    for job in new_jobs:
        seen.add(job["id"])
    save_seen(seen)

    print(
        f"Done: {len(all_tailored)} jobs (24h), {len(new_tailored)} new, "
        f"{issues_created} issues with resume + cover letter"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()) or 0)
