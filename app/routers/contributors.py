from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.commit import Commit
from app.models.developer import Developer
from app.models.repository import Repository

router = APIRouter(prefix="/contributors", tags=["contributors"])


@router.get("")
async def list_contributors(
    repo_full_name: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Developer.login,
            func.sum(Commit.effort_score_v1).label("total_effort"),
        )
        .join(Commit, Commit.developer_id == Developer.id)
        .join(Repository, Commit.repo_id == Repository.id)
        .where(Repository.full_name == repo_full_name)
        .group_by(Developer.login)
        .order_by(func.sum(Commit.effort_score_v1).desc())
    )

    result = await db.execute(stmt)

    return [
        {
            "developer": row.login,
            "total_effort": round(row.total_effort or 0, 2),
        }
        for row in result.all()
    ]
