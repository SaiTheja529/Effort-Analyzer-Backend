from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.commit import Commit
from app.models.developer import Developer
from app.models.repository import Repository

router = APIRouter(prefix="/rankings", tags=["rankings"])


def _bucket_start(day_value: date, bucket: str) -> date:
    if bucket == "day":
        return day_value
    # ISO week starts Monday.
    return day_value - timedelta(days=day_value.weekday())


def _bucket_range(start_day: date, end_day: date, bucket: str) -> list[date]:
    start_bucket = _bucket_start(start_day, bucket)
    end_bucket = _bucket_start(end_day, bucket)
    step = timedelta(days=1 if bucket == "day" else 7)

    values = []
    current = start_bucket
    while current <= end_bucket:
        values.append(current)
        current += step
    return values


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


@router.get("/trends")
async def get_developer_trends(
    repo_full_name: str,
    bucket: str = "week",
    days: int = 84,
    top_n: int = 6,
    db: AsyncSession = Depends(get_db),
):
    selected_bucket = (bucket or "week").strip().lower()
    if selected_bucket not in {"day", "week"}:
        raise HTTPException(400, "bucket must be either 'day' or 'week'")

    bounded_days = max(7, min(int(days), 365))
    bounded_top_n = max(1, min(int(top_n), 12))

    latest_commit_stmt = (
        select(func.max(Commit.committed_at))
        .join(Repository, Commit.repo_id == Repository.id)
        .where(Repository.full_name == repo_full_name)
    )
    latest_commit_at = (await db.execute(latest_commit_stmt)).scalar_one_or_none()

    end_dt = latest_commit_at or datetime.utcnow()
    if getattr(end_dt, "tzinfo", None) is not None:
        end_dt = end_dt.replace(tzinfo=None)
    start_dt = end_dt - timedelta(days=bounded_days)

    stmt = (
        select(
            Developer.login.label("developer"),
            Commit.committed_at.label("committed_at"),
            Commit.effort_score_v1.label("effort"),
        )
        .join(Commit, Commit.developer_id == Developer.id)
        .join(Repository, Commit.repo_id == Repository.id)
        .where(
            Repository.full_name == repo_full_name,
            Commit.committed_at >= start_dt,
            Commit.committed_at <= end_dt,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    bucket_days = _bucket_range(start_dt.date(), end_dt.date(), selected_bucket)
    labels = [day.isoformat() for day in bucket_days]

    if not rows:
        return {
            "repo_full_name": repo_full_name,
            "bucket": selected_bucket,
            "days": bounded_days,
            "window_start": start_dt.date().isoformat(),
            "window_end": end_dt.date().isoformat(),
            "labels": labels,
            "series": [],
            "totals": [],
        }

    per_dev_bucket: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    totals: dict[str, float] = defaultdict(float)

    for row in rows:
        developer = row.developer or "unknown"
        committed_at = row.committed_at
        if not committed_at:
            continue

        bucket_day = _bucket_start(committed_at.date(), selected_bucket)
        effort = float(row.effort or 0.0)
        per_dev_bucket[developer][bucket_day] += effort
        totals[developer] += effort

    top_developers = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:bounded_top_n]

    series = []
    for developer, total_effort in top_developers:
        points = [
            round(per_dev_bucket[developer].get(bucket_day, 0.0), 2)
            for bucket_day in bucket_days
        ]
        series.append(
            {
                "developer": developer,
                "points": points,
                "total_effort": round(total_effort, 2),
            }
        )

    totals_payload = [
        {
            "developer": developer,
            "effort": round(total_effort, 2),
        }
        for developer, total_effort in top_developers
    ]

    return {
        "repo_full_name": repo_full_name,
        "bucket": selected_bucket,
        "days": bounded_days,
        "window_start": start_dt.date().isoformat(),
        "window_end": end_dt.date().isoformat(),
        "labels": labels,
        "series": series,
        "totals": totals_payload,
    }
