from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.repository import Repository
from app.models.developer import Developer
from app.models.commit import Commit
from app.models.job import Job

router = APIRouter(prefix="/data", tags=["data"])


def _dt(value):
    return value.isoformat() if value else None


@router.get("/export")
async def export_all_data(db: AsyncSession = Depends(get_db)):
    repos = (await db.execute(select(Repository))).scalars().all()
    devs = (await db.execute(select(Developer))).scalars().all()
    commits = (await db.execute(select(Commit))).scalars().all()
    jobs = (await db.execute(select(Job))).scalars().all()

    return {
        "repositories": [
            {
                "id": r.id,
                "full_name": r.full_name,
                "default_branch": r.default_branch,
                "last_synced_at": _dt(r.last_synced_at),
                "created_at": _dt(r.created_at),
                "updated_at": _dt(r.updated_at),
            }
            for r in repos
        ],
        "developers": [
            {
                "id": d.id,
                "login": d.login,
            }
            for d in devs
        ],
        "commits": [
            {
                "id": c.id,
                "repo_id": c.repo_id,
                "developer_id": c.developer_id,
                "sha": c.sha,
                "message": c.message,
                "committed_at": _dt(c.committed_at),
                "lines_added": c.lines_added,
                "lines_deleted": c.lines_deleted,
                "effort_score": c.effort_score_v1,
                "ai_type": c.ai_type,
                "ai_difficulty": c.ai_difficulty,
                "ai_summary": c.ai_summary,
                "ai_confidence": c.ai_confidence,
                "ai_reason_short": c.ai_reason_short,
            }
            for c in commits
        ],
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "input": j.input,
                "progress": j.progress,
                "result": j.result,
                "error": j.error,
                "created_at": _dt(j.created_at),
                "updated_at": _dt(j.updated_at),
            }
            for j in jobs
        ],
    }
