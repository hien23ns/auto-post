"""Database ORM models for jobs, revisions, and platform posts."""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    ANALYZING = "ANALYZING"
    REVIEW_READY = "REVIEW_READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PlatformType(str, enum.Enum):
    YOUTUBE = "YOUTUBE"
    FACEBOOK = "FACEBOOK"
    TIKTOK = "TIKTOK"


class PostStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    BLOCKED_MISSING_CREDENTIALS = "BLOCKED_MISSING_CREDENTIALS"
    CANCELLED = "CANCELLED"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    source_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_checksum: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    video_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    video_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_fps: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=JobStatus.PENDING.value, index=True)
    uncertain_warning: Mapped[bool] = mapped_column(Boolean, default=False)

    # JSON storage compatible with SQLite and Postgres
    analysis_raw: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evidence_log: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    content_draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    selected_cover_index: Mapped[int] = mapped_column(Integer, default=0)
    cover_paths: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    platforms_enabled: Mapped[list[str] | None] = mapped_column(
        JSON, default=lambda: [PlatformType.YOUTUBE.value, PlatformType.FACEBOOK.value, PlatformType.TIKTOK.value]
    )

    scheduled_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Concurrency and anti-double-post lock
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    revisions: Mapped[list["JobRevision"]] = relationship("JobRevision", back_populates="job", cascade="all, delete-orphan")
    platform_posts: Mapped[list["PlatformPost"]] = relationship("PlatformPost", back_populates="job", cascade="all, delete-orphan")


class JobRevision(Base):
    __tablename__ = "job_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped["Job"] = relationship("Job", back_populates="revisions")


class PlatformPost(Base):
    __tablename__ = "platform_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default=PostStatus.PENDING.value, index=True)

    remote_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_audit_info: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    job: Mapped["Job"] = relationship("Job", back_populates="platform_posts")


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    worker_name: Mapped[str] = mapped_column(String(128))
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
