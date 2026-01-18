import asyncio
from datetime import datetime
import traceback

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.commit import Commit
from app.models.developer import Developer
from app.models.repository import Repository
from app.models.job import Job
from app.services.github_service import GitHubService, GitHubCommitLite
from app.services.gemini_service import GeminiService
from app.services.job_service import JobService
from app.db.session import get_background_db


class AnalysisService:
    """
    Performs effort-based commit analysis in background.
    """

    def __init__(self):
        self.github = GitHubService(settings.GITHUB_TOKEN)
        self.gemini = GeminiService()
        self.job_service = JobService()

    async def analyze_repo(
        self,
        job_id: int,
        repo_full_name: str,   # user input
        max_commits: int,
    ):
        async with get_background_db() as db:
            job = await db.get(Job, job_id)

            try:
                # 🔹 IMPORTANT: repo returned has CANONICAL full_name
                repo = await self._get_or_create_repo(db, repo_full_name)

                await self.job_service.update_status(
                    db, job, "running", {"stage": "fetching_commits"}
                )

                # ✅ ALWAYS use repo.full_name (canonical)
                commits: list[GitHubCommitLite] = await self.github.list_commits(
                    repo_full_name=repo.full_name,
                    branch=repo.default_branch,
                    limit=max_commits,
                    since=repo.last_synced_at.isoformat()
                    if repo.last_synced_at
                    else None,
                )

                processed = 0

                for commit in commits:
                    await self._process_commit(db, repo, commit)
                    processed += 1

                    await self.job_service.update_status(
                        db,
                        job,
                        "running",
                        {"processed_commits": processed},
                    )

                repo.last_synced_at = datetime.utcnow()
                db.add(repo)
                await db.commit()

                await self.job_service.update_status(
                    db,
                    job,
                    "succeeded",
                    result={"total_commits_processed": processed},
                )

            except Exception:
                error_details = traceback.format_exc()
                print("BACKGROUND JOB ERROR:")
                print(error_details)

                await self.job_service.update_status(
                    db,
                    job,
                    "failed",
                    error=error_details,
                )

    async def _get_or_create_repo(
        self,
        db: AsyncSession,
        repo_full_name: str,   # user input
    ) -> Repository:

        # 🔹 First check DB using ANY stored canonical name
        result = await db.execute(
            select(Repository).where(Repository.full_name == repo_full_name)
        )
        repo = result.scalar_one_or_none()
        if repo:
            return repo

        # 🔹 Fetch from GitHub to resolve canonical repo name
        data = await self.github.get_repository(repo_full_name)

        # ✅ STORE CANONICAL NAME, NOT USER INPUT
        repo = Repository(
            full_name=data["full_name"],   # 🔥 FIX
            default_branch=data.get("default_branch", "main"),
        )

        db.add(repo)
        await db.commit()
        await db.refresh(repo)
        return repo

    async def _process_commit(
        self,
        db: AsyncSession,
        repo: Repository,
        commit: GitHubCommitLite,
    ):
        # Developer
        result = await db.execute(
            select(Developer).where(Developer.login == commit.author_login)
        )
        dev = result.scalar_one_or_none()

        if not dev:
            dev = Developer(login=commit.author_login)
            db.add(dev)
            await db.commit()
            await db.refresh(dev)

        # Duplicate check
        result = await db.execute(
            select(Commit).where(
                Commit.repo_id == repo.id,
                Commit.sha == commit.sha,
            )
        )
        if result.scalar_one_or_none():
            return

        # Commit stats (canonical repo name already stored)
        stats = await self.github.get_commit_stats(
            repo.full_name,
            commit.sha,
        )

        effort_score = stats.additions + (0.5 * stats.deletions)

        ai_summary = await self._generate_ai_summary(commit.message)

        committed_dt = self._parse_commit_datetime(commit.committed_at)

        new_commit = Commit(
            repo_id=repo.id,
            developer_id=dev.id,
            sha=commit.sha,
            message=commit.message,
            committed_at=committed_dt,
            lines_added=stats.additions,
            lines_deleted=stats.deletions,
            effort_score_v1=effort_score,
            ai_summary=ai_summary,
        )

        db.add(new_commit)
        await db.commit()

    async def _generate_ai_summary(self, message: str) -> str:
        """
        Run Gemini classification with a short timeout so jobs never hang on AI.
        """
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self.gemini.generate,
                    f"Classify this commit message: {message}",
                ),
                timeout=8.0,
            )
        except Exception:
            return "AI unavailable"

    def _parse_commit_datetime(self, committed_at: str | None) -> datetime:
        """
        GitHub returns ISO 8601 strings (often ending with 'Z'); convert to datetime.
        """
        if not committed_at:
            return datetime.utcnow()

        ts = committed_at.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            # Fallback to now if parsing ever fails to avoid dropping the commit
            return datetime.utcnow()
