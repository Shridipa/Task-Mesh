"""Public submit/read endpoints for JSON and CSV analysis jobs."""
from __future__ import annotations
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from ...engine import engine
from ...models import JobCreate
from ...json_validation import JSON_JOB_TYPE,MAX_JSON_LENGTH
from ...csv_analysis import CSV_JOB_TYPE,MAX_CSV_LENGTH
router=APIRouter()
class MultiTaskRequest(BaseModel):
    task_type:str
    content:str=Field(min_length=1)
@router.post('/jobs',status_code=201)
async def submit(payload:MultiTaskRequest):
    limits={JSON_JOB_TYPE:MAX_JSON_LENGTH,CSV_JOB_TYPE:MAX_CSV_LENGTH}
    if payload.task_type not in limits: raise HTTPException(422,'Unsupported task type')
    if not payload.content.strip(): raise HTTPException(422,'Input must not be empty')
    if len(payload.content)>limits[payload.task_type]: raise HTTPException(422,'Input exceeds size limit')
    key='json_text' if payload.task_type==JSON_JOB_TYPE else 'csv_text'
    try: return await engine.create_job(JobCreate(job_type=payload.task_type,payload={key:payload.content},tenant_id='demo',priority=5,max_retries=3))
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
@router.get('/jobs/{job_id}')
async def get_job(job_id:str):
    job=await engine.get_job(job_id)
    if not job or job.get('job_type') not in {JSON_JOB_TYPE,CSV_JOB_TYPE}: raise HTTPException(404,'Task not found')
    return job
