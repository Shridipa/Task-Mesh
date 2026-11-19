from ...models import Job, JobCreate


class JobCreateSchema(JobCreate):
    """Alias for request body when creating a job."""



class JobResponseSchema(Job):
    """Response model for a Job, inheriting all fields from the core model."""

