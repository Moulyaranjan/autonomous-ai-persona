import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id"),
        nullable=False,
        index=True,
    )

    topic_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    # Normalized source URL – primary identity for deduplication.
    # NULL for posts migrated from v0.1 (they have no stored URL).
    topic_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        index=True,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sources: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------------------------
    # Extended metadata – v0.2.
    # All nullable so rows written by v0.1 remain valid without migration data.
    # -----------------------------------------------------------------------

    # Originating source name (e.g. "Hacker News", "arXiv AI").
    source_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # When the source article was originally published.
    source_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Final editorial score (0-100).
    editorial_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # JSON-encoded score_breakdown dict from EditorialEngine.
    score_breakdown: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # "ollama" or "fallback" – identifies which provider wrote the post text.
    generation_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Model name used during generation (e.g. "llama3.2:3b"); NULL for fallback.
    generation_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )