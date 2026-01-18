from pydantic import BaseModel, Field


class GitHubTokenRequest(BaseModel):
    code: str = Field(..., description="OAuth authorization code from GitHub")
    redirect_uri: str | None = Field(
        default=None,
        description="Redirect URI used in the OAuth app configuration",
    )


class GitHubTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    scope: str | None = None


class GitHubUserResponse(BaseModel):
    id: int
    login: str
    avatar_url: str | None = None
    name: str | None = None
    email: str | None = None
    html_url: str | None = None
