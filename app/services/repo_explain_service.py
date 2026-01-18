from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repo_context import RepoContext
from app.models.repository import Repository
from app.services.gemini_service import GeminiService


class RepoExplainService:
    """
    Generates deep project explanations using Gemini AI.
    """

    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    async def explain_repo(
        self,
        db: AsyncSession,
        repo_full_name: str,
        detail_level: str,
    ) -> dict:
        # ✅ Proper ORM query (NO raw SQL)
        result = await db.execute(
            select(RepoContext)
            .join(Repository)
            .where(Repository.full_name == repo_full_name)
        )
        context: RepoContext | None = result.scalar_one_or_none()

        if not context:
            raise ValueError(
                "Repo context not found. Call /repo-context/fetch first."
            )

        # Build Gemini prompt
        prompt = f"""
You are a senior software architect.

Explain the following project clearly and professionally.

Repository Description:
{context.description}

Topics:
{context.topics}

Languages:
{context.languages}

README:
{(context.readme_text or '')[:4000]}

Provide a {detail_level} explanation with:
1. Overview
2. Architecture
3. Key modules
4. Setup instructions
5. Possible improvements
"""

        # ✅ Safe Gemini call
        try:
            text = self.gemini.generate(prompt)
        except Exception as e:
            raise ValueError(f"Gemini error: {str(e)}")

        return {
            "overview": text
        }
