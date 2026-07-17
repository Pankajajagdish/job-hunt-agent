import os
from fastapi import APIRouter
from services.tracker import get_stats

router = APIRouter()


@router.get("/dashboard")
def dashboard():
    goal = int(os.getenv("DAILY_APPLY_GOAL", "50"))
    stats = get_stats(daily_goal=goal)
    progress_pct = round(stats["applied_today"] / goal * 100, 1) if goal else 0
    return {
        **stats,
        "progress_percent": min(100, progress_pct),
        "message": (
            f"Applied {stats['applied_today']}/{goal} today. "
            f"{stats['remaining_today']} remaining to hit daily goal."
        ),
    }
