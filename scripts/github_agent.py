#!/usr/bin/env python3
"""GitHub Actions agent — fetch jobs, match resume, update feed, open issues for new matches."""

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

DATA_DIR = ROOT / "data"
SEEN_FILE = DATA_DIR / "seen_jobs.json"
FEED_FILE = ROOT / "docs" / "jobs_feed.json"
MIN_SCORE = int(os.getenv("MIN_MATCH_SCORE", "35"))
MAX_ISSUES = int(os.getenv("MAX_ISSUES_PER_RUN", "8"))
ISSUE_MIN_SCORE = int(os.getenv("ISSUE_MIN_SCORE", "45"))


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))


def save_seen(seen: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    trimmed = list(seen)[-8000:]
    SEEN_FILE.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")


def write_feed(jobs: list[dict], new_jobs: list[dict]) -> None:
    profile_name = os.getenv("PROFILE_NAME", "Pankaja Jagdish Kulkarni")
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile_name,
        "daily_goal": int(os.getenv("DAILY_APPLY_GOAL", "50")),
        "total": len(jobs),
        "new_count": len(new_jobs),
        "jobs": jobs[:100],
        "new_jobs": new_jobs[:20],
    }
    FEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEED_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_summary(jobs: list[dict], new_jobs: list[dict]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## Job Hunt Agent",
        "",
        f"- **Total matches:** {len(jobs)}",
        f"- **New this run:** {len(new_jobs)}",
        f"- **Dashboard:** https://pankajajagdish.github.io/job-hunt-agent/",
        "",
    ]
    if new_jobs:
        lines.append("### New jobs")
        for j in new_jobs[:10]:
            lines.append(f"- **{j['match_score']}%** [{j['title']}]({j['url']}) @ {j['company']}")
    Path(summary_path).write_text("\n".join(lines), encoding="utf-8")


def create_issue(job: dict) -> bool:
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        return False

    title = f"[Job] {job['title']} @ {job['company']} ({job['match_score']}%)"
    skills = ", ".join(job.get("matched_skills") or []) or "—"
    body = f"""## New matching job

| | |
|---|---|
| **Match** | {job['match_score']}% |
| **Location** | {job.get('location', '—')} |
| **Source** | {job.get('source', '—')} |
| **Skills** | {skills} |

### Apply now
{job['url']}

---
_Auto-posted by [Job Hunt Agent](https://github.com/{repo}/actions). Close this issue after you apply._
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
        print(f"Issue created: {title[:60]}")
        return True
    print(f"Issue failed ({resp.status_code}): {resp.text[:200]}")
    return False


async def run() -> int:
    seen = load_seen()
    jobs = await refresh_live_jobs(min_score=MIN_SCORE, include_demo=False)
    new_jobs = [j for j in jobs if j["id"] not in seen]

    write_feed(jobs, new_jobs)
    write_summary(jobs, new_jobs)

    issues_created = 0
    for job in sorted(new_jobs, key=lambda x: x.get("match_score", 0), reverse=True):
        if job.get("match_score", 0) < ISSUE_MIN_SCORE:
            continue
        if issues_created >= MAX_ISSUES:
            break
        if create_issue(job):
            issues_created += 1

    for job in new_jobs:
        seen.add(job["id"])
    save_seen(seen)

    print(f"Done: {len(jobs)} matches, {len(new_jobs)} new, {issues_created} issues")
    return len(new_jobs)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
