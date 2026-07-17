"""Filter jobs to last 24 hours."""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


def parse_posted_at(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        except (OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def is_within_hours(job: dict, hours: int = 24) -> bool:
    """Return True if job was posted within the last N hours."""
    posted = parse_posted_at(job.get("posted_at"))
    if posted is None:
        # Sources that pre-filter by date (Adzuna max_days_old=1, JSearch today)
        trusted = {"adzuna", "jsearch", "google_jobs", "rss"}
        return job.get("source", "") in trusted
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return posted >= cutoff


def filter_last_24h(jobs: list[dict]) -> list[dict]:
    return [j for j in jobs if is_within_hours(j, 24)]
