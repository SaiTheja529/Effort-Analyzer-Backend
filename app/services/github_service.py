from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from fastapi import HTTPException
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from app.core.config import settings

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


@dataclass
class GitHubChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None
    previous_filename: str | None = None


@dataclass
class GitHubCommitDetails:
    additions: int
    deletions: int
    files: list[GitHubChangedFile]


def _is_github_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, HTTPException):
        return exc.status_code in {429, 500, 502, 503, 504}
    return False


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

    @staticmethod
    def normalize_repo_full_name(repo_full_name: str) -> str:
        """
        Accepts:
        - owner/repo
        - github.com/owner/repo
        - https://github.com/owner/repo(.git)
        """
        raw = unquote((repo_full_name or "").strip())
        if not raw:
            raise HTTPException(400, "Repository is required (format: owner/repo).")

        if raw.startswith(("http://", "https://")):
            parsed = urlparse(raw)
            host = parsed.netloc.lower()
            if "github.com" not in host:
                raise HTTPException(
                    400,
                    "Repository URL must be from github.com (format: owner/repo).",
                )
            raw = parsed.path

        raw = raw.strip().strip("/")
        if raw.lower().startswith("github.com/"):
            raw = raw.split("/", 1)[1]

        raw = raw.split("?", 1)[0].split("#", 1)[0]
        if raw.endswith(".git"):
            raw = raw[:-4]

        parts = [p for p in raw.split("/") if p]
        if len(parts) < 2:
            raise HTTPException(400, "Invalid repository. Use format: owner/repo.")

        normalized = f"{parts[0]}/{parts[1]}"
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", normalized):
            raise HTTPException(
                400,
                "Invalid repository name. Use format: owner/repo.",
            )

        return normalized

    # -----------------
    # Internal GET
    # -----------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_github_retryable_exception),
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
            raise HTTPException(
                401,
                "Invalid GitHub token. Update GITHUB_TOKEN and retry.",
            )

        if response.status_code == 404:
            # GitHub returns 404 for missing repos and private repos without access.
            raise HTTPException(
                404,
                "GitHub repository not found or token has no access to it.",
            )

        if response.status_code in (403, 429):
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining == "0" or response.status_code == 429:
                raise HTTPException(429, "GitHub rate limit exceeded")
            raise HTTPException(
                403,
                "GitHub access forbidden. Check token permissions for this repository.",
            )

        if response.status_code >= 400:
            raise HTTPException(
                500 if response.status_code >= 500 else 400,
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
        repo = self.normalize_repo_full_name(repo_full_name)
        data = await self._get(f"/repos/{repo}")

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
        repo = self.normalize_repo_full_name(repo_full_name)
        try:
            data = await self._get(f"/repos/{repo}/readme")
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
        repo = self.normalize_repo_full_name(repo_full_name)
        return await self._get(f"/repos/{repo}/languages")

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
        repo = self.normalize_repo_full_name(repo_full_name)

        params = {"per_page": limit}

        if since:
            params["since"] = since

        data = await self._get(
            f"/repos/{repo}/commits",
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

    async def get_commit_details(
        self,
        repo_full_name: str,
        sha: str,
        *,
        max_files: int = 25,
        max_patch_chars: int = 16000,
    ) -> GitHubCommitDetails:
        repo = self.normalize_repo_full_name(repo_full_name)
        data = await self._get(f"/repos/{repo}/commits/{sha}")

        stats = data.get("stats") or {}
        files_payload = data.get("files") or []

        parsed_files: list[GitHubChangedFile] = []
        patch_budget = max(0, int(max_patch_chars))

        for file_data in files_payload[: max(0, int(max_files))]:
            patch = file_data.get("patch")
            if patch:
                patch = patch.strip()
                if patch_budget <= 0:
                    patch = None
                elif len(patch) > patch_budget:
                    patch = patch[:patch_budget].rstrip() + "\n... [patch truncated]"
                    patch_budget = 0
                else:
                    patch_budget -= len(patch)

            parsed_files.append(
                GitHubChangedFile(
                    filename=file_data.get("filename") or "unknown",
                    status=file_data.get("status") or "modified",
                    additions=int(file_data.get("additions", 0) or 0),
                    deletions=int(file_data.get("deletions", 0) or 0),
                    patch=patch,
                    previous_filename=file_data.get("previous_filename"),
                )
            )

        return GitHubCommitDetails(
            additions=int(stats.get("additions", 0) or 0),
            deletions=int(stats.get("deletions", 0) or 0),
            files=parsed_files,
        )

    async def get_commit_stats(self, repo_full_name: str, sha: str) -> GitHubCommitStats:
        details = await self.get_commit_details(
            repo_full_name,
            sha,
            max_files=0,
            max_patch_chars=0,
        )
        return GitHubCommitStats(
            additions=details.additions,
            deletions=details.deletions,
        )
