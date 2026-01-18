from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analyze import AnalyzeRepoRequest, AnalyzeRepoResponse
from app.services.analysis_service import AnalysisService
from app.services.job_service import JobService

router = APIRouter(prefix="/analyze-repo", tags=["analysis"])


@router.post("", response_model=AnalyzeRepoResponse)
async def analyze_repo(
    payload: AnalyzeRepoRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService()
    job = await job_service.create_job(
        db,
        job_type="analyze_repo",
        input_data=payload.dict(),
    )

    service = AnalysisService()

    background_tasks.add_task(
    service.analyze_repo,
    job.id,
    payload.repo_full_name,
    payload.max_commits,
   )


    return {
        "job_id": job.id,
        "status": job.status,
    }
