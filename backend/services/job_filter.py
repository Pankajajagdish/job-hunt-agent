"""Filter jobs to last 24 hours — strict for real-time feed."""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


def parse_posted_at(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # RemoteOK / some APIs use seconds; millis if huge
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return parse_posted_at(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def is_within_hours(job: dict, hours: int = 24) -> bool:
    """True if posted within last N hours.

    Sources that already filter by 'today' / max_days_old=1 are trusted
    when posted_at is missing.
    """
    posted = parse_posted_at(job.get("posted_at"))
    if posted is None:
        trusted = {"adzuna", "jsearch", "google_jobs"}
        return job.get("source", "") in trusted

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    # Reject future-dated noise beyond 1 hour clock skew
    now = datetime.now(timezone.utc) + timedelta(hours=1)
    if posted > now:
        return False
    return posted >= cutoff


def filter_last_24h(jobs: list[dict]) -> list[dict]:
    recent = [j for j in jobs if is_within_hours(j, 24)]
    print(f"Last-24h filter: {len(recent)}/{len(jobs)} jobs kept")
    return recent
