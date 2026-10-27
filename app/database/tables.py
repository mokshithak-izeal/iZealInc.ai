from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.database.db import Base

def now(): return datetime.now(timezone.utc)
def new_id(): return uuid4().hex
def pk(): return mapped_column(String(32), primary_key=True, default=new_id)
def when(): return mapped_column(DateTime(timezone=True), default=now)
def text(): return mapped_column(Text, default='')
def jlist(): return mapped_column(JSON, default=list)
def jdict(): return mapped_column(JSON, default=dict)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default='')
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='recruiter')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = when()

class UserSession(Base):
    __tablename__ = 'user_sessions'
    id: Mapped[str] = pk()
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str] = mapped_column(String(512), default='')
    ip_address: Mapped[str] = mapped_column(String(45), default='')
    created_at: Mapped[datetime] = when()
    last_seen_at: Mapped[datetime] = when()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Candidate(Base):
    __tablename__ = 'candidates'
    id: Mapped[str] = pk()
    name: Mapped[str] = mapped_column(String(200), default='')
    profile: Mapped[dict] = jdict()
    original_filename: Mapped[str] = mapped_column(String(255), default='')
    storage_key: Mapped[str] = mapped_column(String(300), default='')
    uploaded_by: Mapped[str] = mapped_column(String(32), default='')
    created_at: Mapped[datetime] = when()

class JobDescription(Base):
    __tablename__ = 'job_descriptions'
    id: Mapped[str] = pk()
    title: Mapped[str] = mapped_column(String(255), default='')
    experience: Mapped[str] = mapped_column(String(120), default='')
    description: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(255), default='')
    uploaded_by: Mapped[str] = mapped_column(String(32), default='')
    created_at: Mapped[datetime] = when()

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = pk()
    source: Mapped[str] = mapped_column(String(50), default='LinkedIn')
    job_url: Mapped[str] = text()
    title: Mapped[str] = text()
    company: Mapped[str] = text()
    location: Mapped[str] = text()
    work_mode: Mapped[str] = text()
    required_skills: Mapped[list] = jlist()
    preferred_skills: Mapped[list] = jlist()
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(60), nullable=True)
    required_skill_matches: Mapped[list] = jlist()
    preferred_skill_matches: Mapped[list] = jlist()
    experience_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score_breakdown: Mapped[dict] = jdict()
    weights_used: Mapped[dict] = jdict()
    status: Mapped[str] = mapped_column(String(20), default='NEW')
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyzed_at: Mapped[datetime] = when()

class Preference(Base):
    __tablename__ = 'preferences'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict] = jdict()

class StoredFile(Base):
    __tablename__ = 'stored_files'
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(100), default='')
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = when()
    
class Application(Base):
    __tablename__ = 'applications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_url: Mapped[str] = text()
    data: Mapped[dict] = jdict()
    applied_at: Mapped[datetime] = when()

class ImportRecord(Base):
    __tablename__ = 'import_records'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(300), index=True)
    job_url: Mapped[str] = text()
    title: Mapped[str] = text()
    status: Mapped[str] = mapped_column(String(20), default='')
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    processed_at: Mapped[datetime] = when()

class AuditLog(Base):
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), default='')
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = text()
    at: Mapped[datetime] = when()