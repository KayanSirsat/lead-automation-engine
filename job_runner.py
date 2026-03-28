"""
job_runner.py

Manages background pipeline jobs. Each job runs in a thread so the API
stays responsive while scraping/auditing happens in the background.

Job lifecycle:  queued → running → done | failed
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class JobStatus:
    job_id: str
    status: str                      # queued | running | done | failed
    stage: str                       # current pipeline stage label
    created_at: str
    updated_at: str
    niche: str
    city: str
    areas: list[str]
    limit: int
    leads_found: int = 0
    leads_written: int = 0
    leads_audited: int = 0
    leads_outreached: int = 0
    error: str | None = None
    log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "stage": self.stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "niche": self.niche,
            "city": self.city,
            "areas": self.areas,
            "limit": self.limit,
            "leads_found": self.leads_found,
            "leads_written": self.leads_written,
            "leads_audited": self.leads_audited,
            "leads_outreached": self.leads_outreached,
            "error": self.error,
            "log": self.log[-50:],   # last 50 log lines only
        }


# In-memory store: job_id → JobStatus
# Fine for a 2-person internal tool; no persistence needed
_jobs: dict[str, JobStatus] = {}
_lock = threading.Lock()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _update(job: JobStatus, **kwargs) -> None:
    """Thread-safe field update + timestamp refresh."""
    with _lock:
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = _now()


def _log(job: JobStatus, message: str) -> None:
    logger.info(f"[{job.job_id[:8]}] {message}")
    with _lock:
        job.log.append(f"{_now()} {message}")
        job.updated_at = _now()


def _run_pipeline(job: JobStatus) -> None:
    """The actual pipeline — runs in a background thread."""
    try:
        # ── Stage 1: Lead generation ──────────────────────────────────────
        _update(job, status="running", stage="Scraping Google Maps")
        _log(job, f"Starting lead generation: {job.niche} in {job.city}")

        from lead_generation.engine import generate_leads
        leads = generate_leads(
            niche=job.niche,
            city=job.city,
            areas=job.areas if job.areas else None,
            limit=job.limit,
        )

        _update(job, leads_found=len(leads))
        _log(job, f"Found {len(leads)} leads")

        # ── Stage 2: Write to sheet ───────────────────────────────────────
        _update(job, stage="Writing to Google Sheets")
        _log(job, "Writing leads to Lead Database sheet")

        from workflows.lead_workflow import write_leads_to_sheet
        write_leads_to_sheet(leads)

        _update(job, leads_written=len(leads))
        _log(job, "Lead Database updated")

        # ── Stage 3: Website audit ────────────────────────────────────────
        _update(job, stage="Running website audits")
        _log(job, "Starting website audit workflow")

        from workflows.lead_workflow import run_lead_audit_workflow
        run_lead_audit_workflow()

        _log(job, "Website audits complete")

        # ── Stage 4: Outreach drafts ──────────────────────────────────────
        _update(job, stage="Generating outreach drafts")
        _log(job, "Starting outreach workflow")

        from workflows.lead_workflow import run_outreach_workflow
        drafted = run_outreach_workflow()

        _update(job, leads_outreached=drafted)
        _log(job, f"Outreach workflow complete. {drafted} draft(s) written.")

        # ── Done ──────────────────────────────────────────────────────────
        _update(job, status="done", stage="Complete")
        _log(job, "Pipeline finished successfully")

    except Exception as e:
        logger.exception(f"Job {job.job_id} failed")
        _update(job, status="failed", stage="Failed", error=str(e))
        _log(job, f"Pipeline failed: {e}")


def create_job(niche: str, city: str, areas: list[str], limit: int) -> JobStatus:
    """Creates a new job, stores it, and returns the status object."""
    job_id = str(uuid.uuid4())
    now = _now()
    job = JobStatus(
        job_id=job_id,
        status="queued",
        stage="Queued",
        created_at=now,
        updated_at=now,
        niche=niche,
        city=city,
        areas=areas,
        limit=limit,
    )
    with _lock:
        _jobs[job_id] = job
    return job


def start_job(job: JobStatus) -> None:
    """Launches the pipeline in a background daemon thread."""
    t = threading.Thread(target=_run_pipeline, args=(job,), daemon=True)
    t.start()


def get_job(job_id: str) -> JobStatus | None:
    return _jobs.get(job_id)


def list_jobs() -> list[dict]:
    """Returns all jobs, newest first."""
    with _lock:
        return [j.to_dict() for j in sorted(
            _jobs.values(),
            key=lambda j: j.created_at,
            reverse=True,
        )]