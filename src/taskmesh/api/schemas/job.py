from ...models import JobCreate, Job


class JobCreateSchema(JobCreate):
    """Alias for request body when creating a job."""

    pass


class JobResponseSchema(Job):
    """Response model for a Job, inheriting all fields from the core model."""

    pass
