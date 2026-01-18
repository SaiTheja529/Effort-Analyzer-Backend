from pydantic import BaseModel


class RepoContextFetchRequest(BaseModel):
    repo_full_name: str


class RepoContextFetchResponse(BaseModel):
    repo_full_name: str
    stored: bool
    readme_chars: int
    topics: list[str]


class RepoContextResponse(BaseModel):
    repo_full_name: str
    description: str | None
    topics: list[str] | None
    languages: dict | None
    readme_excerpt: str | None
