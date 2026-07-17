"""Application tracker — JSON file persistence."""

import json
from pathlib import Path
from datetime import datetime, date

STORE = Path(__file__).parent.parent / "data" / "applications.json"
STORE.parent.mkdir(exist_ok=True)


def _load() -> list[dict]:
    if not STORE.exists():
        return []
    with open(STORE, encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]) -> None:
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_application(job_id: str, title: str, company: str, url: str,
                    status: str = "applied", resume_file: str = "") -> dict:
    apps = _load()
    entry = {
        "job_id": job_id,
        "title": title,
        "company": company,
        "url": url,
        "status": status,
        "resume_file": resume_file,
        "applied_at": datetime.now().isoformat(),
    }
    apps.append(entry)
    _save(apps)
    return entry


def get_stats(daily_goal: int = 50) -> dict:
    apps = _load()
    today = date.today().isoformat()
    today_apps = [a for a in apps if a.get("applied_at", "").startswith(today)]
    return {
        "daily_goal": daily_goal,
        "applied_today": len(today_apps),
        "remaining_today": max(0, daily_goal - len(today_apps)),
        "total_applied": len(apps),
        "recent": today_apps[-10:][::-1],
    }


def list_all(limit: int = 100) -> list[dict]:
    apps = _load()
    return apps[-limit:][::-1]
