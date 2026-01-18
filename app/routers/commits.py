from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.commit import Commit
from app.models.repository import Repository

router = APIRouter(prefix="/commits", tags=["commits"])


@router.get("")
async def list_commits(
    repo_full_name: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Commit)
        .join(Repository)
        .where(Repository.full_name == repo_full_name)
        .order_by(Commit.committed_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    commits = result.scalars().all()

    return [
        {
            "sha": c.sha,
            "message": c.message,
            "committed_at": c.committed_at,
            "lines_added": c.lines_added,
            "lines_deleted": c.lines_deleted,
            "effort_score": round(c.effort_score_v1, 2),
            "ai_summary": c.ai_summary,
        }
        for c in commits
    ]
