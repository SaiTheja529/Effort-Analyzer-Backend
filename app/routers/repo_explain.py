from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.repo_explain import RepoExplainRequest, RepoExplainResponse
from app.services.gemini_service import GeminiService
from app.services.repo_explain_service import RepoExplainService

router = APIRouter(prefix="/repo-explain", tags=["repo-explain"])


@router.post("", response_model=RepoExplainResponse)
async def explain_repo(
    payload: RepoExplainRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        service = RepoExplainService(GeminiService())
        explanation = await service.explain_repo(
            db,
            payload.repo_full_name,
            payload.detail_level,
        )
        return {
            "repo_full_name": payload.repo_full_name,
            "explanation": explanation,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
