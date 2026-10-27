from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base
from app.database.tables import now


class GmailConnection(Base):
    """The one connected mailbox. The refresh token is stored encrypted."""
    __tablename__ = 'gmail_connection'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    email: Mapped[str] = mapped_column(String(255), default='')
    refresh_token: Mapped[str] = mapped_column(Text, default='')
    connected_by: Mapped[str] = mapped_column(String(32), default='')
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GmailMessage(Base):
    """Gmail message IDs already handled, so an email is never imported twice."""
    __tablename__ = 'gmail_messages'
    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class JobMatch(Base):
    """One row per (job, candidate): the score plus matched and missing skills."""
    __tablename__ = 'job_matches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(32), index=True)
    candidate_id: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='BELOW')
    semantic: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
