"""Background job poller — keeps cache fresh every N minutes."""

import asyncio
import os
from services.job_cache import refresh_live_jobs

POLL_INTERVAL_MIN = int(os.getenv("JOB_POLL_INTERVAL_MIN", "5"))
_running = False


async def _poll_loop():
    global _running
    _running = True
    while _running:
        try:
            count = len(await refresh_live_jobs(min_score=35, include_demo=False))
            print(f"[poller] Refreshed {count} live jobs")
        except Exception as e:
            print(f"[poller] Error: {e}")
        await asyncio.sleep(POLL_INTERVAL_MIN * 60)


def start_background_poller():
    """Start asyncio background task (call from FastAPI startup)."""
    asyncio.create_task(_poll_loop())


def stop_background_poller():
    global _running
    _running = False
