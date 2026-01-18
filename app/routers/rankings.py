import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.commit import Commit
from app.models.developer import Developer
from app.models.repository import Repository

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("")
async def get_rankings(
    repo_full_name: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Developer.login.label("developer"),
            Commit.effort_score_v1.label("effort"),
        )
        .join(Commit, Commit.developer_id == Developer.id)
        .join(Repository, Commit.repo_id == Repository.id)
        .where(Repository.full_name == repo_full_name)
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return []

    df = pd.DataFrame(rows, columns=["developer", "effort"])

    rankings = (
        df.groupby("developer")["effort"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )

    return rankings.to_dict(orient="records")
