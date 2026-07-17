"""Job cache for real-time polling and new-job detection."""

import json
from pathlib import Path
from datetime import datetime, timezone
from services.job_sources import fetch_all_free_sources
from services.job_search import search_all
from services.matcher import filter_and_rank
from services.profile import load_profile

CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = CACHE_DIR / "job_cache.json"
SEEN_FILE = CACHE_DIR / "seen_jobs.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_seen_ids() -> set[str]:
    return set(_load_json(SEEN_FILE, []))


def mark_seen(job_ids: list[str]) -> None:
    seen = get_seen_ids()
    seen.update(job_ids)
    _save_json(SEEN_FILE, list(seen)[-5000:])


async def refresh_live_jobs(min_score: int = 35, include_demo: bool = False) -> list[dict]:
    """Fetch real jobs from all sources, rank, cache."""
    profile = load_profile()
    queries = profile["target_roles"]

    free_jobs = await fetch_all_free_sources(queries)
    if free_jobs:
        ranked = filter_and_rank(free_jobs, min_score=min_score)
    else:
        ranked = await search_all(min_score=min_score, include_demo=include_demo)

    cache = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": ranked,
    }
    _save_json(CACHE_FILE, cache)
    return ranked


def get_cached_jobs() -> list[dict]:
    data = _load_json(CACHE_FILE, {"jobs": []})
    return data.get("jobs", [])


async def poll_new_jobs(min_score: int = 35, mark_as_seen: bool = False) -> dict:
    """Refresh sources and return only jobs not seen before."""
    fresh = await refresh_live_jobs(min_score=min_score, include_demo=False)
    seen = get_seen_ids()
    new_jobs = [j for j in fresh if j["id"] not in seen]

    if mark_as_seen and new_jobs:
        mark_seen([j["id"] for j in new_jobs])

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_cached": len(fresh),
        "new_count": len(new_jobs),
        "new_jobs": new_jobs,
        "all_jobs": fresh,
    }
