"""
API server to expose MADLab runs for the frontend.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path
import re
import csv
import json

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
    upload_name: str | None = None
    upload_content: str | None = None


app = FastAPI(title="MADLab API")

jobs: Dict[str, dict] = {}
stop_events: Dict[str, threading.Event] = {}
_FAVICON_PATH = Path(__file__).resolve().parent / "frontend" / "images" / "multi-agent-favicon.svg"
_UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _save_upload(upload_name: str, upload_content: str) -> Path:
    """
    Save uploaded prompt content to disk. If CSV, convert to JSONL with prompt/label fields.
    """
    safe_name = _sanitize_filename(upload_name) or f"upload_{uuid.uuid4().hex}.txt"
    raw_path = _UPLOAD_DIR / safe_name
    raw_path.write_text(upload_content, encoding="utf-8")

    if safe_name.lower().endswith(".csv"):
        jsonl_path = raw_path.with_suffix(".jsonl")
        with raw_path.open(newline="", encoding="utf-8") as f_in, jsonl_path.open("w", encoding="utf-8") as f_out:
            reader = csv.DictReader(f_in)
            for idx, row in enumerate(reader, start=1):
                prompt = row.get("prompt") or row.get("text") or ""
                label_raw = row.get("label")
                try:
                    is_harmful = bool(float(label_raw)) if label_raw is not None else False
                except Exception:
                    is_harmful = False
                rec = {
                    "id": row.get("id") or f"upload_{idx}",
                    "prompt": prompt,
                    "is_harmful": is_harmful,
                    "_suite": "upload",
                }
                f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return jsonl_path

    # Assume JSONL/JSON with prompt field; if plain text, wrap lines.
    if safe_name.lower().endswith(".json") or safe_name.lower().endswith(".jsonl"):
        return raw_path

    # For txt or other, treat each line as a prompt.
    jsonl_path = raw_path.with_suffix(".jsonl")
    with raw_path.open(encoding="utf-8") as f_in, jsonl_path.open("w", encoding="utf-8") as f_out:
        for idx, line in enumerate(f_in, start=1):
            text = line.strip()
            if not text:
                continue
            rec = {"id": f"upload_{idx}", "prompt": text, "is_harmful": False, "_suite": "upload"}
            f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return jsonl_path

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
    prompts_path = None
    if req.upload_content and req.upload_name:
        prompts_path = _save_upload(req.upload_name, req.upload_content)
    return run_baseline(
        req.config,
        prompt_override=req.prompt,
        target_override=req.model_name,
        prompts_path=prompts_path,
    )


@app.post("/start")
def start(req: RunRequest):
    """
    Start an async run and return a job_id for progress polling.
    """
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "processed": 0, "total": None, "summary": None, "error": None}
    stop_events[job_id] = threading.Event()
    prompts_path = None
    if req.upload_content and req.upload_name:
        prompts_path = _save_upload(req.upload_name, req.upload_content)

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
                prompts_path=prompts_path,
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
