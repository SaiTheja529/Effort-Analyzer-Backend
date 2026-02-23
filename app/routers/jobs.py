from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import CurrentActor, get_current_actor
from app.db.session import get_db
from app.schemas.job import JobStatusResponse
from app.models.job import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(
            Job.id == job_id,
            Job.owner_key == current_actor.owner_key,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
    }


@router.delete("/{job_id}")
async def delete_job_history(
    job_id: int,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(
            Job.id == job_id,
            Job.owner_key == current_actor.owner_key,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    input_data = job.input or {}
    if job.job_type != "analyze_repo" and "repo_full_name" not in input_data:
        raise HTTPException(status_code=400, detail="Only analysis history can be deleted")
    if job.status != "succeeded":
        raise HTTPException(status_code=400, detail="Only completed history can be deleted")

    await db.delete(job)
    await db.commit()

    return {"deleted": True, "job_id": job_id}


@router.delete("/history/all")
async def clear_history(
    current_actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.owner_key == current_actor.owner_key))
    jobs = result.scalars().all()

    deleted_count = 0
    for job in jobs:
        input_data = job.input or {}
        if (
            job.status == "succeeded"
            and (job.job_type == "analyze_repo" or "repo_full_name" in input_data)
        ):
            await db.delete(job)
            deleted_count += 1

    await db.commit()
    return {"deleted": True, "deleted_count": deleted_count}
