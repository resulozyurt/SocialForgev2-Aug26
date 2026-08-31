"""
core/job_status.py
Tiny in-memory job-status registry so background runs (research, calendar, copy)
can report REAL, human-readable steps to the pipeline UI instead of the UI faking
progress. Single-instance admin tool (replicas = 1), so process memory is fine;
it resets on restart, which only clears the last run's step log.

Key convention: "<stage>:<brand_id>", e.g. "research:<uuid>".
"""

from __future__ import annotations

from datetime import datetime, timezone

_JOBS: dict[str, dict] = {}
_MAX_STEPS = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_job(key: str, message: str = "") -> None:
    job = {"status": "running", "message": message, "log": []}
    if message:
        job["log"].append({"t": _now(), "text": message})
    _JOBS[key] = job


def log_step(key: str, text: str) -> None:
    job = _JOBS.get(key)
    if job is None:
        job = {"status": "running", "message": "", "log": []}
        _JOBS[key] = job
    job["message"] = text
    job["log"].append({"t": _now(), "text": text})
    if len(job["log"]) > _MAX_STEPS:
        job["log"] = job["log"][-_MAX_STEPS:]


def finish_job(key: str, message: str = "Done.") -> None:
    job = _JOBS.setdefault(key, {"status": "running", "message": "", "log": []})
    job["status"] = "done"
    job["message"] = message
    job["log"].append({"t": _now(), "text": message})


def fail_job(key: str, message: str) -> None:
    job = _JOBS.setdefault(key, {"status": "running", "message": "", "log": []})
    job["status"] = "error"
    job["message"] = message
    job["log"].append({"t": _now(), "text": message})


def get_job(key: str) -> dict | None:
    return _JOBS.get(key)
