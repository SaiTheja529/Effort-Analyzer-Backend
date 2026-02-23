import asyncio
from datetime import datetime
import traceback

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.commit import Commit
from app.models.developer import Developer
from app.models.repository import Repository
from app.models.job import Job
from app.services.github_service import GitHubService, GitHubCommitLite, GitHubCommitDetails
from app.services.gemini_service import GeminiService
from app.services.effort_scoring_service import EffortScoringResult, EffortScoringService
from app.services.job_service import JobService
from app.db.session import get_background_db


class AnalysisService:
    """
    Performs effort-based commit analysis in background.
    """

    def __init__(self):
        self.github = GitHubService(settings.GITHUB_TOKEN)
        self.ai_error_reason: str | None = None
        try:
            self.gemini = GeminiService()
        except Exception as exc:
            # Keep analysis jobs functional even when Gemini is unavailable.
            print(f"Gemini initialization failed in AnalysisService: {exc}")
            self.gemini = None
            self.ai_error_reason = str(exc)
        self.effort_scoring = EffortScoringService(self.gemini, self.ai_error_reason)
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

                needs_ai_backfill = await self._repo_has_ai_gaps(db, repo.id)
                fetch_limit = max_commits
                if needs_ai_backfill:
                    existing_commit_count = await self._repo_commit_count(db, repo.id)
                    fetch_limit = max(max_commits, existing_commit_count)

                # ✅ ALWAYS use repo.full_name (canonical)
                commits: list[GitHubCommitLite] = await self.github.list_commits(
                    repo_full_name=repo.full_name,
                    branch=repo.default_branch,
                    limit=fetch_limit,
                    # If previous runs stored "AI unavailable", re-fetch recent history
                    # so existing commits can be backfilled with real summaries.
                    since=None
                    if needs_ai_backfill
                    else (
                        repo.last_synced_at.isoformat()
                        if repo.last_synced_at
                        else None
                    ),
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

            except HTTPException as exc:
                error_message = f"{exc.status_code}: {exc.detail}"
                print("BACKGROUND JOB ERROR:")
                print(error_message)
                await self.job_service.update_status(
                    db,
                    job,
                    "failed",
                    error=error_message,
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
        normalized_repo_full_name = self.github.normalize_repo_full_name(repo_full_name)

        # 🔹 First check DB using ANY stored canonical name
        result = await db.execute(
            select(Repository).where(
                func.lower(Repository.full_name) == normalized_repo_full_name.lower()
            )
        )
        repo = result.scalar_one_or_none()
        if repo:
            return repo

        # 🔹 Fetch from GitHub to resolve canonical repo name
        data = await self.github.get_repository(normalized_repo_full_name)

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
        existing_commit = result.scalar_one_or_none()
        if existing_commit:
            needs_summary_refresh = self._summary_missing(existing_commit.ai_summary)
            needs_effort_refresh = self._effort_missing(existing_commit)
            if not needs_summary_refresh and not needs_effort_refresh:
                return

            changed = False

            if needs_effort_refresh:
                details = await self._get_commit_details(repo.full_name, commit.sha)
                scored = await self._score_commit_effort(commit.message, details)
                existing_commit.lines_added = details.additions
                existing_commit.lines_deleted = details.deletions
                existing_commit.effort_score_v1 = scored.effort_score
                existing_commit.ai_type = scored.score_source
                existing_commit.ai_difficulty = scored.difficulty
                existing_commit.ai_confidence = scored.confidence
                existing_commit.ai_reason_short = scored.reason_short
                if needs_summary_refresh and scored.summary:
                    existing_commit.ai_summary = scored.summary
                changed = True

            elif needs_summary_refresh:
                refreshed_summary = await self._generate_commit_summary_only(commit.message)
                if refreshed_summary:
                    existing_commit.ai_summary = refreshed_summary
                    changed = True

            if changed:
                db.add(existing_commit)
                await db.commit()
            return

        details = await self._get_commit_details(repo.full_name, commit.sha)
        scored = await self._score_commit_effort(commit.message, details)

        committed_dt = self._parse_commit_datetime(commit.committed_at)

        new_commit = Commit(
            repo_id=repo.id,
            developer_id=dev.id,
            sha=commit.sha,
            message=commit.message,
            committed_at=committed_dt,
            lines_added=details.additions,
            lines_deleted=details.deletions,
            effort_score_v1=scored.effort_score,
            ai_summary=scored.summary,
            ai_type=scored.score_source,
            ai_difficulty=scored.difficulty,
            ai_confidence=scored.confidence,
            ai_reason_short=scored.reason_short,
        )

        db.add(new_commit)
        await db.commit()

    async def _repo_has_ai_gaps(self, db: AsyncSession, repo_id: int) -> bool:
        result = await db.execute(
            select(Commit.id)
            .where(
                Commit.repo_id == repo_id,
                or_(
                    Commit.ai_summary.is_(None),
                    Commit.ai_summary == "",
                    func.lower(Commit.ai_summary).like("ai unavailable%"),
                ),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _repo_commit_count(self, db: AsyncSession, repo_id: int) -> int:
        result = await db.execute(
            select(func.count(Commit.id)).where(Commit.repo_id == repo_id)
        )
        return int(result.scalar_one() or 0)

    def _summary_missing(self, text: str | None) -> bool:
        if text is None:
            return True
        normalized = text.strip().lower()
        return normalized == "" or normalized.startswith("ai unavailable")

    def _effort_missing(self, commit: Commit) -> bool:
        # Keep existing historical scores intact; only fill truly missing/invalid values.
        score = float(commit.effort_score_v1 or 0.0)
        return score <= 0.0

    async def _get_commit_details(self, repo_full_name: str, sha: str) -> GitHubCommitDetails:
        return await self.github.get_commit_details(
            repo_full_name,
            sha,
            max_files=settings.EFFORT_V2_MAX_FILES_FOR_LLM,
            max_patch_chars=settings.EFFORT_V2_MAX_PATCH_CHARS,
        )

    async def _score_commit_effort(
        self,
        message: str,
        details: GitHubCommitDetails,
    ) -> EffortScoringResult:
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self.effort_scoring.score_commit,
                    message,
                    details,
                ),
                timeout=settings.EFFORT_V2_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"Effort scoring failed; using deterministic fallback: {exc}")
            return self.effort_scoring.score_commit_deterministic(
                message,
                details,
                llm_error=str(exc),
            )

    async def _generate_commit_summary_only(self, message: str) -> str:
        summary_fallback = f"{(message or '').strip().splitlines()[0][:180]}."
        if not self.gemini:
            return summary_fallback

        prompt = (
            "Summarize this git commit message in 1 concise sentence for an engineering dashboard.\n"
            "Focus on what changed and why it matters.\n\n"
            f"Commit message:\n{message}"
        )

        loop = asyncio.get_running_loop()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, self.gemini.generate, prompt),
                timeout=settings.AI_SUMMARY_TIMEOUT_SECONDS,
            )
            normalized = (response or "").strip()
            return normalized[:320] if normalized else summary_fallback
        except Exception:
            return summary_fallback

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
