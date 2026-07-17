"""Job Hunt Agent — FastAPI backend for job discovery, matching, and resume tailoring."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from routers import jobs, resume, tracker, dashboard

app = FastAPI(
    title="Job Hunt Agent API",
    description="Real-time job discovery, matching, resume tailoring",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(resume.router, prefix="/api/resume", tags=["resume"])
app.include_router(tracker.router, prefix="/api/tracker", tags=["tracker"])

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


@app.on_event("startup")
async def startup():
    from services.poller import start_background_poller
    from services.job_cache import refresh_live_jobs
    start_background_poller()
    try:
        n = len(await refresh_live_jobs(include_demo=False))
        print(f"Initial live job fetch: {n} jobs")
    except Exception as e:
        print(f"Initial fetch error: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "job-hunt-agent", "version": "2.0"}


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    import os
    load_dotenv()
    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)), reload=True)
