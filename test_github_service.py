import asyncio

from app.services.github_service import GitHubService
from app.core.config import settings


async def test_github_service():
    gh = GitHubService(settings.GITHUB_TOKEN)

    print("\n--- Repository Metadata ---")
    repo = await gh.get_repository("octocat/Hello-World")
    print(repo)

    print("\n--- README ---")
    readme = await gh.get_readme("octocat/Hello-World")
    print("README length:", len(readme or ""))

    print("\n--- Languages ---")
    langs = await gh.get_languages("octocat/Hello-World")
    print(langs)


if __name__ == "__main__":
    asyncio.run(test_github_service())
