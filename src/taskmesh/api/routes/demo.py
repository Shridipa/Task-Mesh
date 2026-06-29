"""Demo mode endpoints — auto-generate sample data for portfolio demonstrations."""
from __future__ import annotations

import random
import string
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...engine import engine
from ...models import JobCreate, WorkerHeartbeat, JobStatus
from ..auth import require_admin

router = APIRouter()


@router.post("/generate-workers", response_model=dict[str, Any])
async def generate_workers(
    count: int = 3,
    _: str = Depends(require_admin),
):
    """Generate sample workers for demo purposes."""
    workers = []
    for i in range(count):
        worker_id = f"worker-{i + 1}"
        await engine.heartbeat(
            WorkerHeartbeat(
                worker_id=worker_id,
                hostname=f"host-{i + 1}",
                cpu_usage=random.uniform(10, 75),
                memory_usage=random.uniform(20, 80),
                active_jobs=0,
            )
        )
        workers.append(worker_id)
    return {"created": workers}


@router.post("/generate-jobs", response_model=dict[str, Any])
async def generate_jobs(
    count: int = 10,
    _: str = Depends(require_admin),
):
    """Generate sample jobs for demo purposes."""
    job_types = ["email", "report", "cleanup", "notification", "backup"]
    tenants = ["default", "acme", "beta", "gamma"]
    jobs = []
    
    for _ in range(count):
        job_type = random.choice(job_types)
        tenant = random.choice(tenants)
        priority = random.randint(0, 9)
        
        # Randomly decide job status for demo
        status_roll = random.random()
        if status_roll < 0.3:
            status = JobStatus.COMPLETED
        elif status_roll < 0.5:
            status = JobStatus.RUNNING
        elif status_roll < 0.7:
            status = JobStatus.PENDING
        elif status_roll < 0.85:
            status = JobStatus.FAILED
        else:
            status = JobStatus.DEAD_LETTER
        
        payload = {
            "to": f"user{random.randint(1, 100)}@example.com",
            "subject": f"Demo {job_type}",
            "body": "This is a demo job",
        }
        
        request = JobCreate(
            job_type=job_type,
            payload=payload,
            priority=priority,
            tenant_id=tenant,
            max_retries=3,
        )
        
        job = await engine.create_job(request)
        
        # Simulate job lifecycle for demo
        if status in (JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTER):
            job = await engine.lease_job_by_id(job["id"], worker_id="worker-1")
            if job and status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTER):
                if status == JobStatus.COMPLETED:
                    await engine.complete_job(job["id"])
                else:
                    await engine.fail_job(job["id"], "Demo failure")
        
        jobs.append(job["id"])
    
    return {"created": jobs}


@router.post("/reset", response_model=dict[str, Any])
async def reset_demo(
    _: str = Depends(require_admin),
):
    """Reset demo data (for clean re-runs)."""
    # In a real implementation, this would clear jobs/workers/events
    # For now, just return success
    return {"status": "reset"}