from fastapi import APIRouter, Query
from pydantic import BaseModel
from services.job_search import search_all, parse_career_page
from services.job_cache import refresh_live_jobs, poll_new_jobs, get_cached_jobs, mark_seen
from services.resume_tailor import generate_tailored_docx, generate_cover_letter_snippet, tailor_summary
from services.tracker import log_application

router = APIRouter()


class SearchRequest(BaseModel):
    queries: list[str] | None = None
    career_urls: list[str] | None = None
    min_score: int = 35


class ApplyAssistRequest(BaseModel):
    job_id: str
    title: str
    company: str
    url: str
    description: str


class QuickApplyRequest(ApplyAssistRequest):
    mark_applied: bool = False


@router.get("/live")
async def live_jobs(min_score: int = Query(35), refresh: bool = Query(True)):
    """Real-time jobs from Remotive, RemoteOK, Arbeitnow, Adzuna, JSearch, etc."""
    if refresh:
        jobs = await refresh_live_jobs(min_score=min_score, include_demo=False)
    else:
        jobs = get_cached_jobs()
    return {
        "count": len(jobs),
        "live": True,
        "sources": ["remotive", "remoteok", "arbeitnow", "adzuna", "jsearch", "google_jobs"],
        "jobs": jobs,
    }


@router.get("/poll")
async def poll_jobs(min_score: int = Query(35), known_ids: str = Query("")):
    """Return NEW matching jobs since last poll (for push notifications)."""
    result = await poll_new_jobs(min_score=min_score, mark_as_seen=False)
    if known_ids:
        known = set(known_ids.split(","))
        result["new_jobs"] = [j for j in result["new_jobs"] if j["id"] not in known]
        result["new_count"] = len(result["new_jobs"])
    return result


@router.post("/seen")
async def mark_jobs_seen(job_ids: list[str]):
    mark_seen(job_ids)
    return {"marked": len(job_ids)}


@router.post("/search")
async def search_jobs(body: SearchRequest | None = None):
    body = body or SearchRequest()
    jobs = await search_all(
        queries=body.queries,
        career_urls=body.career_urls,
        min_score=body.min_score,
        include_demo=False,
    )
    return {"count": len(jobs), "jobs": jobs}


@router.get("/search")
async def search_jobs_get(min_score: int = Query(35)):
    jobs = await refresh_live_jobs(min_score=min_score, include_demo=False)
    return {"count": len(jobs), "jobs": jobs}


@router.post("/quick-apply")
async def quick_apply(body: QuickApplyRequest):
    """ONE STEP: tailor resume + cover letter + apply URL — minimal user effort."""
    job = body.model_dump()
    filename = generate_tailored_docx(job)
    cover = generate_cover_letter_snippet(job)
    log_application(
        job_id=body.job_id,
        title=body.title,
        company=body.company,
        url=body.url,
        status="applied" if body.mark_applied else "ready_to_apply",
        resume_file=filename,
    )
    mark_seen([body.job_id])
    return {
        "resume_file": filename,
        "download_url": f"/output/{filename}",
        "cover_letter": cover,
        "apply_url": body.url,
        "tailored_summary": tailor_summary(job["description"], job["title"]),
        "message": "Resume ready. Open apply link, upload resume, paste cover letter, submit.",
    }


@router.post("/career-url")
async def add_career_url(url: str):
    jobs = await parse_career_page(url)
    return {"jobs": jobs}


@router.post("/apply-assist")
async def apply_assist(body: ApplyAssistRequest):
    job = body.model_dump()
    filename = generate_tailored_docx(job)
    result = {
        "resume_file": filename,
        "download_url": f"/output/{filename}",
        "tailored_summary": tailor_summary(job["description"], job["title"]),
        "cover_letter": generate_cover_letter_snippet(job),
        "apply_url": job["url"],
        "note": "Open apply page, upload tailored resume, submit.",
    }
    log_application(
        job_id=body.job_id, title=body.title, company=body.company,
        url=body.url, status="ready_to_apply", resume_file=filename,
    )
    mark_seen([body.job_id])
    result["tracked"] = True
    return result
