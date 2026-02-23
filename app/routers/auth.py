from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas.auth import (
    GitHubTokenRequest,
    GitHubTokenResponse,
    GitHubUserResponse,
    LocalAuthResponse,
    LocalLoginRequest,
    LocalRegisterRequest,
    LocalUserResponse,
)
from app.db.session import get_db
from app.models.user import User
from app.services.github_service import GitHubService
from app.services.local_auth_service import LocalAuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(400, "Missing Bearer token in Authorization header")
    return authorization.split(" ", 1)[1]


def _to_local_user_response(user: User) -> LocalUserResponse:
    return LocalUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        login=user.email.split("@", 1)[0],
        provider="local",
    )


@router.post("/register", response_model=LocalAuthResponse, status_code=status.HTTP_201_CREATED)
async def register_local_user(
    payload: LocalRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    email = LocalAuthService.normalize_email(payload.email)
    LocalAuthService.validate_password(payload.password)

    name = (payload.name or "").strip() or None
    if name and len(name) > 120:
        raise HTTPException(400, "Name must be 120 characters or fewer")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email is already registered")

    user = User(
        email=email,
        name=name,
        password_hash=LocalAuthService.hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return LocalAuthResponse(
        access_token=LocalAuthService.create_access_token(user.id),
        user=_to_local_user_response(user),
    )


@router.post("/login", response_model=LocalAuthResponse)
async def login_local_user(
    payload: LocalLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    email = LocalAuthService.normalize_email(payload.email)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not LocalAuthService.verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    return LocalAuthResponse(
        access_token=LocalAuthService.create_access_token(user.id),
        user=_to_local_user_response(user),
    )


@router.get("/me", response_model=LocalUserResponse)
async def get_local_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    token = _extract_bearer_token(authorization)
    user_id = LocalAuthService.parse_access_token(token)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found for token")
    return _to_local_user_response(user)


@router.post("/github/token", response_model=GitHubTokenResponse)
async def exchange_github_token(payload: GitHubTokenRequest):
    token = await GitHubService.exchange_code_for_token(
        payload.code,
        payload.redirect_uri,
    )
    return token


@router.get("/github/me", response_model=GitHubUserResponse)
async def get_github_user(authorization: str | None = Header(None)):
    access_token = _extract_bearer_token(authorization)
    gh = GitHubService(access_token)
    return await gh.get_user()
