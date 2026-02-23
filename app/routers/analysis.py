from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import CurrentActor, get_current_actor
from app.db.session import get_db
from app.schemas.analyze import AnalyzeRepoRequest, AnalyzeRepoResponse
from app.services.analysis_service import AnalysisService
from app.services.github_service import GitHubService
from app.services.job_service import JobService

router = APIRouter(prefix="/analyze-repo", tags=["analysis"])


@router.post("", response_model=AnalyzeRepoResponse)
async def analyze_repo(
    payload: AnalyzeRepoRequest,
    background_tasks: BackgroundTasks,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    try:
        normalized_repo = GitHubService.normalize_repo_full_name(payload.repo_full_name)
    except HTTPException as exc:
        raise exc
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository. Use format: owner/repo.",
        )

    job_service = JobService()
    job = await job_service.create_job(
        db,
        job_type="analyze_repo",
        input_data={
            "repo_full_name": normalized_repo,
            "max_commits": payload.max_commits,
        },
        owner_key=current_actor.owner_key,
    )

    service = AnalysisService()

    background_tasks.add_task(
        service.analyze_repo,
        job.id,
        normalized_repo,
        payload.max_commits,
    )


    return {
        "job_id": job.id,
        "status": job.status,
    }
