from pydantic import BaseModel


class RepoExplainRequest(BaseModel):
    repo_full_name: str
    detail_level: str = "deep"  # shallow | deep


class RepoExplainResponse(BaseModel):
    repo_full_name: str
    explanation: dict
