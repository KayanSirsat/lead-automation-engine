"""
routes/jobs.py

POST /jobs          — start a new pipeline job
GET  /jobs          — list all jobs
GET  /jobs/{id}     — get single job status (used for polling)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from job_runner import create_job, get_job, list_jobs, start_job

logger = logging.getLogger(__name__)
router = APIRouter()


class StartJobRequest(BaseModel):
    niche: str = Field(..., examples=["cafe"], description="Business niche to search")
    city: str = Field(..., examples=["Ahmedabad"], description="Target city")
    areas: list[str] = Field(
        default_factory=list,
        examples=[["Satellite", "Bopal"]],
        description="Specific areas within the city (optional)",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of leads to generate",
    )


@router.post("", status_code=201)
def start_pipeline_job(body: StartJobRequest):
    """
    Launch a new lead generation + audit pipeline job.
    Returns immediately with a job_id you can use to poll status.
    """
    job = create_job(
        niche=body.niche,
        city=body.city,
        areas=body.areas,
        limit=body.limit,
    )
    start_job(job)
    logger.info(f"Job {job.job_id} created: {body.niche} / {body.city} / limit={body.limit}")
    return job.to_dict()


@router.get("")
def get_all_jobs():
    """List all jobs, newest first."""
    return list_jobs()


@router.get("/{job_id}")
def get_job_status(job_id: str):
    """
    Get the current status of a job.
    Poll this every 2 seconds from the frontend to show live progress.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.to_dict()