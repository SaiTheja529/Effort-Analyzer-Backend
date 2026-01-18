from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Commit(Base):
    """
    Represents a single GitHub commit with effort & AI analysis.
    """
    __tablename__ = "commits"

    __table_args__ = (
        # Prevent duplicate commits per repo
        UniqueConstraint("repo_id", "sha", name="uq_repo_commit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relations
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        index=True,
    )

    developer_id: Mapped[int] = mapped_column(
        ForeignKey("developers.id"),
        index=True,
    )

    # GitHub data
    sha: Mapped[str] = mapped_column(String, index=True)
    message: Mapped[str] = mapped_column(String)
    committed_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    # Diff stats
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0)

    # Effort score (versioned)
    effort_score_v1: Mapped[float] = mapped_column(Float, default=0.0)

    # Gemini AI outputs
    ai_type: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_difficulty: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(String, nullable=True)

    # Explainability & trust
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_reason_short: Mapped[str | None] = mapped_column(String, nullable=True)
