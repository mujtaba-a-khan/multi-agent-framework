"""
API server to expose MADLab runs for the frontend.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict

from src.madlab.api import run_baseline


class RunRequest(BaseModel):
    config: str
    prompt: str | None = None
    model_name: str | None = None


app = FastAPI(title="MADLab API")

jobs: Dict[str, dict] = {}
stop_events: Dict[str, threading.Event] = {}
_FAVICON_PATH = Path(__file__).resolve().parent / "frontend" / "images" / "multi-agent-favicon.svg"

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
    return run_baseline(
        req.config,
        prompt_override=req.prompt,
        target_override=req.model_name,
    )


@app.post("/start")
def start(req: RunRequest):
    """
    Start an async run and return a job_id for progress polling.
    """
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "processed": 0, "total": None, "summary": None, "error": None}
    stop_events[job_id] = threading.Event()

    def _progress(processed, total):
        jobs[job_id]["processed"] = processed
        jobs[job_id]["total"] = total

    def _worker():
        try:
            summary = run_baseline(
                req.config,
                on_progress=_progress,
                stop_event=stop_events[job_id],
                prompt_override=req.prompt,
                target_override=req.model_name,
            )
            jobs[job_id]["summary"] = summary
            if stop_events[job_id].is_set():
                jobs[job_id]["status"] = "stopped"
                jobs[job_id]["error"] = "stopped by user"
            else:
                jobs[job_id]["status"] = "done"
        except Exception as exc:  # pragma: no cover
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(exc)
        finally:
            stop_events.pop(job_id, None)

    threading.Thread(target=_worker, daemon=True).start()
    return {"job_id": job_id}


@app.get("/")
def root():
    return {"status": "ok", "message": "MADLab API", "docs": "/docs", "health": "/health"}


@app.get("/favicon.ico")
def favicon():
    return FileResponse(_FAVICON_PATH, media_type="image/svg+xml")


@app.get("/progress/{job_id}")
def progress(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {k: v for k, v in job.items() if k not in {"_stop_event"}}


@app.post("/stop/{job_id}")
def stop(job_id: str):
    """
    Signal a running job to stop.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    ev = stop_events.get(job_id)
    if ev:
        ev.set()
    job["status"] = "stopped"
    job["error"] = "stopped by user"
    return {"job_id": job_id, "status": "stopped"}


@app.get("/health")
def health():
    return {"status": "ok"}
