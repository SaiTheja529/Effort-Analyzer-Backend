from fastapi import APIRouter, Depends, Header, HTTPException

from app.schemas.auth import (
    GitHubTokenRequest,
    GitHubTokenResponse,
    GitHubUserResponse,
)
from app.services.github_service import GitHubService

router = APIRouter(prefix="/auth/github", tags=["auth"])


@router.post("/token", response_model=GitHubTokenResponse)
async def exchange_github_token(payload: GitHubTokenRequest):
    token = await GitHubService.exchange_code_for_token(
        payload.code,
        payload.redirect_uri,
    )
    return token


@router.get("/me", response_model=GitHubUserResponse)
async def get_github_user(authorization: str | None = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(400, "Missing Bearer token in Authorization header")

    access_token = authorization.split(" ", 1)[1]
    gh = GitHubService(access_token)
    return await gh.get_user()
