from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

from contextlib import asynccontextmanager


@asynccontextmanager
async def get_background_db():
    async with AsyncSessionLocal() as session:
        yield session



# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# Dependency for FastAPI routes
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_background_db():
    async with AsyncSessionLocal() as session:
        yield session
