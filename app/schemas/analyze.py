from pydantic import BaseModel


class AnalyzeRepoRequest(BaseModel):
    repo_full_name: str
    max_commits: int = 100


class AnalyzeRepoResponse(BaseModel):
    job_id: int
    status: str
