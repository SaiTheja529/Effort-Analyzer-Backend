from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository
from app.models.repo_context import RepoContext
from app.services.github_service import GitHubService


class RepoContextService:
    """
    Fetches and stores repository-level context from GitHub.
    """

    def __init__(self, github: GitHubService):
        self.github = github

    async def fetch_and_store(
        self,
        db: AsyncSession,
        repo_full_name: str,
    ) -> dict:
        # 1️⃣ Get or create repository
        result = await db.execute(
            select(Repository).where(Repository.full_name == repo_full_name)
        )
        repo = result.scalar_one_or_none()

        if not repo:
            repo_data = await self.github.get_repository(repo_full_name)
            repo = Repository(
                full_name=repo_data["full_name"],
                default_branch=repo_data["default_branch"],
            )
            db.add(repo)
            await db.flush()

        # 2️⃣ Fetch repo context from GitHub
        repo_data = await self.github.get_repository(repo_full_name)
        readme = await self.github.get_readme(repo_full_name)
        languages = await self.github.get_languages(repo_full_name)

        # 3️⃣ Upsert repo context
        result = await db.execute(
            select(RepoContext).where(RepoContext.repo_id == repo.id)
        )
        context = result.scalar_one_or_none()

        if not context:
            context = RepoContext(repo_id=repo.id)

        context.description = repo_data.get("description")
        context.topics = repo_data.get("topics")
        context.languages = languages
        context.readme_text = readme

        db.add(context)
        await db.commit()

        return {
            "repo_full_name": repo.full_name,
            "stored": True,
            "readme_chars": len(readme or ""),
            "topics": repo_data.get("topics") or [],
        }

    async def get_context(
        self,
        db: AsyncSession,
        repo_full_name: str,
    ) -> RepoContext | None:
        result = await db.execute(
            select(RepoContext)
            .join(Repository)
            .where(Repository.full_name == repo_full_name)
        )
        return result.scalar_one_or_none()
