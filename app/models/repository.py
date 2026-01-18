from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Repository(Base):
    """
    Represents a GitHub repository being analyzed.
    """
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # owner/repo
    full_name: Mapped[str] = mapped_column(String, unique=True, index=True)

    default_branch: Mapped[str] = mapped_column(String, default="main")

    # Used for incremental sync (only new commits)
    last_synced_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
