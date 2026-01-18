from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

print(">>> GitHubService LOADED FROM:", __file__)

# =====================
# Data models
# =====================

@dataclass
class GitHubCommitLite:
    sha: str
    author_login: str
    message: str
    committed_at: str


@dataclass
class GitHubCommitStats:
    additions: int
    deletions: int


# =====================
# GitHub Service
# =====================

class GitHubService:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "effort-analyzer-backend",
        }

    # -----------------
    # Internal GET
    # -----------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get(self, path: str, params: dict | None = None) -> Any:
        if not path.startswith("/"):
            raise ValueError("GitHubService._get expects path starting with '/'")

        url = f"{self.BASE_URL}{path}"

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                headers=self.headers,
                params=params,
            )

        if response.status_code == 401:
            raise HTTPException(401, "Invalid GitHub token")

        if response.status_code in (403, 429):
            raise HTTPException(429, "GitHub rate limit exceeded")

        if response.status_code >= 400:
            raise HTTPException(
                502,
                f"GitHub API error: {response.text}",
            )

        return response.json()

    # -----------------
    # Auth helpers
    # -----------------

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def exchange_code_for_token(code: str, redirect_uri: str | None = None) -> dict:
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise HTTPException(500, "GitHub OAuth client not configured")

        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data=payload,
                headers={"Accept": "application/json"},
            )

        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, f"GitHub OAuth error: {resp.text}")

        data = resp.json()
        if "error" in data:
            raise HTTPException(400, f"GitHub OAuth error: {data}")

        # Align response shape for clients
        return {
            "access_token": data.get("access_token"),
            "token_type": data.get("token_type", "bearer"),
            "scope": data.get("scope"),
        }

    # -----------------
    # Repository
    # -----------------

    async def get_repository(self, repo_full_name: str) -> dict:
        data = await self._get(f"/repos/{repo_full_name}")

        return {
            "id": data["id"],
            "full_name": data["full_name"],
            "description": data.get("description"),
            "topics": data.get("topics", []),
            "default_branch": data.get("default_branch", "main"),
            "language": data.get("language"),
            "license": data.get("license", {}).get("name") if data.get("license") else None,
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    # -----------------
    # README
    # -----------------

    async def get_readme(self, repo_full_name: str, max_chars: int = 15000) -> str | None:
        try:
            data = await self._get(f"/repos/{repo_full_name}/readme")
        except HTTPException:
            return None

        content = data.get("content")
        if not content or data.get("encoding") != "base64":
            return None

        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        return decoded[:max_chars]

    # -----------------
    # Languages
    # -----------------

    async def get_languages(self, repo_full_name: str) -> dict:
        return await self._get(f"/repos/{repo_full_name}/languages")

    # -----------------
    # Commits
    # -----------------

    async def list_commits(
        self,
        repo_full_name: str,
        branch: str,
        limit: int,
        since: str | None = None,
    ) -> list[GitHubCommitLite]:

        params = {"per_page": limit}

        if since:
            params["since"] = since

        data = await self._get(
            f"/repos/{repo_full_name}/commits",
            params=params,
        )

        if not isinstance(data, list):
            raise HTTPException(502, f"Unexpected GitHub response: {data}")

        return [
            GitHubCommitLite(
                sha=c["sha"],
                message=c["commit"]["message"],
                committed_at=c["commit"]["author"]["date"],
                author_login=c["author"]["login"] if c.get("author") else "unknown",
            )
            for c in data
        ]

    async def get_user(self) -> dict:
        data = await self._get("/user")
        return {
            "id": data["id"],
            "login": data["login"],
            "avatar_url": data.get("avatar_url"),
            "name": data.get("name"),
            "email": data.get("email"),
            "html_url": data.get("html_url"),
        }

    # -----------------
    # Commit stats
    # -----------------

    async def get_commit_stats(self, repo_full_name: str, sha: str) -> GitHubCommitStats:
        # ✅ Correct endpoint
        data = await self._get(f"/repos/{repo_full_name}/commits/{sha}")

        stats = data.get("stats") or {}
        return GitHubCommitStats(
            additions=int(stats.get("additions", 0)),
            deletions=int(stats.get("deletions", 0)),
        )
