import os
from fastapi import APIRouter
from pydantic import BaseModel
from services.tracker import log_application, get_stats, list_all

router = APIRouter()


class LogApply(BaseModel):
    job_id: str
    title: str
    company: str
    url: str
    status: str = "applied"
    resume_file: str = ""


@router.get("/stats")
def stats():
    goal = int(os.getenv("DAILY_APPLY_GOAL", "50"))
    return get_stats(daily_goal=goal)


@router.get("/applications")
def applications(limit: int = 100):
    return {"applications": list_all(limit)}


@router.post("/log")
def log_apply(body: LogApply):
    entry = log_application(
        body.job_id, body.title, body.company, body.url,
        body.status, body.resume_file
    )
    return entry
