from pydantic import BaseModel


class JobCreateResponse(BaseModel):
    job_id: int
    status: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    progress: dict
    result: dict | None
    error: str | None
