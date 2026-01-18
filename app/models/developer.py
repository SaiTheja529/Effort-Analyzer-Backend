from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Developer(Base):
    """
    Represents a GitHub contributor.
    """
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    login: Mapped[str] = mapped_column(String, unique=True, index=True)
