from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.repo_context import (
    RepoContextFetchRequest,
    RepoContextFetchResponse,
    RepoContextResponse,
)
from app.services.github_service import GitHubService
from app.services.repo_context_service import RepoContextService

router = APIRouter(prefix="/repo-context", tags=["repo-context"])


@router.post("/fetch", response_model=RepoContextFetchResponse)
async def fetch_repo_context(
    payload: RepoContextFetchRequest,
    db: AsyncSession = Depends(get_db),
):
    github = GitHubService(settings.GITHUB_TOKEN)
    service = RepoContextService(github)

    return await service.fetch_and_store(db, payload.repo_full_name)


@router.get("", response_model=RepoContextResponse)
async def get_repo_context(
    repo_full_name: str,
    db: AsyncSession = Depends(get_db),
):
    github = GitHubService(settings.GITHUB_TOKEN)
    service = RepoContextService(github)

    context = await service.get_context(db, repo_full_name)

    if not context:
        raise HTTPException(status_code=404, detail="Repo context not found")

    return {
        "repo_full_name": repo_full_name,
        "description": context.description,
        "topics": context.topics,
        "languages": context.languages,
        "readme_excerpt": (context.readme_text or "")[:500],
    }
