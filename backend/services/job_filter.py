"""Filter jobs: last 24 hours + India-based or Remote only."""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

INDIAN_LOCATIONS = [
    "india", "indian", "bharat",
    "bangalore", "bengaluru", "mumbai", "delhi", "new delhi",
    "gurgaon", "gurugram", "noida", "pune", "hyderabad",
    "chennai", "kolkata", "jaipur", "ahmedabad", "chandigarh",
    "kochi", "trivandrum", "thiruvananthapuram", "indore",
    "coimbatore", "nagpur", "mysore", "mysuru",
]

REMOTE_MARKERS = [
    "remote", "work from home", "wfh", "work-from-home",
    "worldwide", "anywhere", "distributed", "fully remote",
    "100% remote", "remote-first", "remote first",
]

# Explicit non-India onsite locations to reject when not remote
EXCLUDE_COUNTRY_MARKERS = [
    "germany", "deutschland", "nuremberg", "nürnberg", "berlin", "munich",
    "münchen", "hamburg", "frankfurt", "united kingdom", "uk only",
    "london", "manchester", "france", "paris", "netherlands", "amsterdam",
    "poland", "warsaw", "spain", "madrid", "italy", "rome", "sweden",
    "stockholm", "canada only", "australia only", "japan", "tokyo",
    "singapore only", "dubai only", "uae only",
]

# Sources that are remote job boards by design
REMOTE_SOURCES = {"remotive", "remoteok", "jobicy", "himalayas", "linkedin"}


def parse_posted_at(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
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
    posted = parse_posted_at(job.get("posted_at"))
    if posted is None:
        trusted = {"adzuna", "jsearch", "google_jobs"}
        return job.get("source", "") in trusted

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc) + timedelta(hours=1)
    if posted > now:
        return False
    return posted >= cutoff


def filter_last_24h(jobs: list[dict]) -> list[dict]:
    recent = [j for j in jobs if is_within_hours(j, 24)]
    print(f"Last-24h filter: {len(recent)}/{len(jobs)} jobs kept")
    return recent


def _blob(job: dict) -> str:
    return " ".join(
        str(job.get(k) or "")
        for k in ("location", "title", "description", "company")
    ).lower()


def is_india_or_remote(job: dict) -> bool:
    """Keep only India-based or Remote openings. Drop EU/US-only onsite roles."""
    location = (job.get("location") or "").lower().strip()
    source = (job.get("source") or "").lower()
    text = _blob(job)

    # Clear India signal
    if any(c in location for c in INDIAN_LOCATIONS) or any(c in text for c in ("india", "indian")):
        # Still drop if it's "India NOT allowed" style — rare; keep by default
        return True

    # Clear remote signal in location or description
    if any(m in location for m in REMOTE_MARKERS) or any(m in text for m in REMOTE_MARKERS):
        # Reject remote jobs that explicitly say India not eligible
        blocked = (
            "not available in india",
            "india not eligible",
            "except india",
            "us citizens only",
            "must be located in the us",
            "must be based in the united states",
            "uk only",
            "eu only",
            "europe only",
            "must be in germany",
        )
        if any(b in text for b in blocked):
            return False
        return True

    # Known remote boards → treat as remote unless location is a hard onsite country
    if source in REMOTE_SOURCES:
        if location and any(x in location for x in EXCLUDE_COUNTRY_MARKERS):
            # e.g. "Germany" with no remote word — still remote board, allow
            # unless it says "onsite" / "office only"
            if "onsite" in text or "on-site" in text or "office only" in text:
                return False
        return True

    # Empty location from India-focused APIs
    if not location and source in {"adzuna", "jsearch", "google_jobs", "rss"}:
        return True

    # Explicit foreign onsite without remote → reject
    if any(x in location for x in EXCLUDE_COUNTRY_MARKERS):
        return False
    if any(x in text[:500] for x in EXCLUDE_COUNTRY_MARKERS) and "remote" not in text:
        return False

    # Unknown location without remote/india signal → reject (strict)
    return False


def filter_india_or_remote(jobs: list[dict]) -> list[dict]:
    kept = [j for j in jobs if is_india_or_remote(j)]
    print(f"India/Remote filter: {len(kept)}/{len(jobs)} jobs kept")
    return kept
