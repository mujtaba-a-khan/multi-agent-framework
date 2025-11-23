"""
API server to expose MADLab runs for the frontend.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import uuid
from typing import Dict

from src.madlab.api import run_baseline


class RunRequest(BaseModel):
    config: str


app = FastAPI(title="MADLab API")

jobs: Dict[str, dict] = {}

# Allow local frontend dev by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/run")
def run(req: RunRequest):
    """
    Execute a baseline run for the given config path and return the summary.
    """
    return run_baseline(req.config)


@app.post("/start")
def start(req: RunRequest):
    """
    Start an async run and return a job_id for progress polling.
    """
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "processed": 0, "total": None, "summary": None, "error": None}

    def _progress(processed, total):
        jobs[job_id]["processed"] = processed
        jobs[job_id]["total"] = total

    def _worker():
        try:
            summary = run_baseline(req.config, on_progress=_progress)
            jobs[job_id]["summary"] = summary
            jobs[job_id]["status"] = "done"
        except Exception as exc:  # pragma: no cover
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(exc)

    threading.Thread(target=_worker, daemon=True).start()
    return {"job_id": job_id}


@app.get("/progress/{job_id}")
def progress(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/health")
def health():
    return {"status": "ok"}
