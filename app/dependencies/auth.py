from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.github_service import GitHubService
from app.services.local_auth_service import LocalAuthService


@dataclass
class CurrentActor:
    provider: str
    subject: str
    display: str | None = None

    @property
    def owner_key(self) -> str:
        return f"{self.provider}:{self.subject}"


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing Bearer token in Authorization header")
    return authorization.split(" ", 1)[1]


async def get_current_actor(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> CurrentActor:
    token = _extract_bearer_token(authorization)

    # First try local auth token.
    try:
        local_user_id = LocalAuthService.parse_access_token(token)
        user = await db.get(User, local_user_id)
        if not user:
            raise HTTPException(401, "User not found for token")
        return CurrentActor(
            provider="local",
            subject=str(user.id),
            display=user.email,
        )
    except HTTPException:
        pass

    # Fallback: treat as GitHub token.
    try:
        gh_user = await GitHubService(token).get_user()
        return CurrentActor(
            provider="github",
            subject=str(gh_user["id"]),
            display=gh_user.get("login"),
        )
    except HTTPException:
        raise HTTPException(401, "Invalid authentication token")
