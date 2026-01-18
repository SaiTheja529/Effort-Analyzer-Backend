from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


class JobService:
    """
    Manages background jobs lifecycle.
    """

    async def create_job(
        self,
        db: AsyncSession,
        job_type: str,
        input_data: dict,
    ) -> Job:
        job = Job(
            job_type=job_type,
            status="queued",
            input=input_data,
            progress={},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def update_status(
        self,
        db: AsyncSession,
        job: Job,
        status: str,
        progress: dict | None = None,
        result: dict | None = None,
        error: str | None = None,
    ):
        job.status = status
        if progress is not None:
            job.progress = progress
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error

        db.add(job)
        await db.commit()
