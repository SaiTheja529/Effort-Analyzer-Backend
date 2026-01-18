from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RepoContext(Base):
    """
    Stores repository-level context used for AI explanations.
    """
    __tablename__ = "repo_context"

    __table_args__ = (
        # One-to-one with repository
        UniqueConstraint("repo_id", name="uq_repo_context"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        index=True,
    )

    description: Mapped[str | None] = mapped_column(String, nullable=True)
    topics: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    languages: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    readme_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional key files snapshot (package.json, requirements.txt, etc.)
    key_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
