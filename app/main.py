from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

from app.routers.health import router as health_router
from app.routers.repo_context import router as repo_context_router
from app.routers.repo_explain import router as repo_explain_router
from app.routers.analysis import router as analysis_router
from app.routers.jobs import router as jobs_router
from app.routers.contributors import router as contributors_router
from app.routers.commits import router as commits_router
from app.routers.rankings import router as rankings_router
from app.routers.auth import router as auth_router
from app.routers.data_export import router as data_export_router


def _run_startup_migrations(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "jobs" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("jobs")}
    if "owner_key" not in columns:
        sync_conn.execute(text("ALTER TABLE jobs ADD COLUMN owner_key VARCHAR"))
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_owner_key ON jobs (owner_key)"))


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
    )

    allowed_origins = [
        "http://localhost:5173",
        " http://localhost:5174",
        "http://127.0.0.1:5173",
        "https://effort-analyzer-front-end-ctli.vercel.app",
        "https://effort-analyzer-frontend.onrender.com",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^https://effort-analyzer-front-end-.*\.vercel\.app$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(repo_explain_router)
    app.include_router(analysis_router)
    app.include_router(jobs_router)
    app.include_router(contributors_router)
    app.include_router(commits_router)
    app.include_router(rankings_router)
    app.include_router(auth_router)
    app.include_router(data_export_router)

    @app.on_event("startup")
    async def on_startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_run_startup_migrations)

    # Routers
    app.include_router(health_router)
    app.include_router(repo_context_router)  # ← THIS LINE MUST EXIST

    return app


app = create_app()
