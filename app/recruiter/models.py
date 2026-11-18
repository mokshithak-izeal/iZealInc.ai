from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database.db import Base


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class RecruiterJob(Base, TimestampMixin):
    __tablename__ = 'recruiter_jobs'

    id = Column(Integer, primary_key=True)
    owner_key = Column(String(255), nullable=False, index=True)
    title = Column(String(200), nullable=False, index=True)
    company = Column(String(200), nullable=False, index=True)
    location = Column(String(200), default='Remote', nullable=False)
    employment_type = Column(String(80), default='Full Time', nullable=False)
    description = Column(Text, default='', nullable=False)
    required_skills = Column(Text, default='', nullable=False)
    source = Column(String(80), default='Manual', nullable=False)
    external_id = Column(String(255), nullable=True)
    minimum_experience_years = Column(Float, nullable=True)
    status = Column(String(40), default='active', nullable=False, index=True)


class RecruiterCandidate(Base, TimestampMixin):
    __tablename__ = 'recruiter_candidates'
    __table_args__ = (
        UniqueConstraint(
            'owner_key',
            'email',
            name='uq_recruiter_candidate_owner_email',
        ),
    )

    id = Column(Integer, primary_key=True)
    owner_key = Column(String(255), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    location = Column(String(200), default='', nullable=False)
    years_experience = Column(Float, default=0, nullable=False)
    skills = Column(Text, default='', nullable=False)
    availability = Column(String(50), default='Available', nullable=False)
    resume_id = Column(Integer, nullable=True)
    resume_candidate_id = Column(String(32), nullable=True, index=True)
    current_role = Column(String(255), default='', nullable=False)
    profile = Column(JSON, default=dict, nullable=False)
    work_authorization = Column(String(120), default='', nullable=False)
    notes = Column(Text, default='', nullable=False)


class RecruiterMatch(Base, TimestampMixin):
    __tablename__ = 'recruiter_matches'
    __table_args__ = (
        UniqueConstraint('job_id', 'candidate_id', name='uq_recruiter_job_candidate_match'),
        Index('ix_recruiter_matches_v2_job_id', 'job_id'),
        Index('ix_recruiter_matches_v2_candidate_id', 'candidate_id'),
    )

    id = Column(Integer, primary_key=True)
    owner_key = Column(String(255), nullable=False, index=True)
    job_id = Column(
        Integer,
        ForeignKey('recruiter_jobs.id', ondelete='CASCADE'),
        nullable=False,
    )
    candidate_id = Column(
        Integer,
        ForeignKey('recruiter_candidates.id', ondelete='CASCADE'),
        nullable=False,
    )
    score = Column(Float, nullable=False)
    matched_skills = Column(Text, default='', nullable=False)
    missing_skills = Column(Text, default='', nullable=False)
    explanation = Column(Text, default='', nullable=False)
    shortlisted = Column(Boolean, default=False, nullable=False)


class RecruiterSubmission(Base, TimestampMixin):
    __tablename__ = 'recruiter_submissions'
    __table_args__ = (
        Index('ix_recruiter_submissions_v2_job_id', 'job_id'),
        Index('ix_recruiter_submissions_v2_candidate_id', 'candidate_id'),
    )

    id = Column(Integer, primary_key=True)
    owner_key = Column(String(255), nullable=False, index=True)
    job_id = Column(
        Integer,
        ForeignKey('recruiter_jobs.id', ondelete='CASCADE'),
        nullable=False,
    )
    candidate_id = Column(
        Integer,
        ForeignKey('recruiter_candidates.id', ondelete='CASCADE'),
        nullable=False,
    )
    vendor = Column(String(200), nullable=False)
    consent_share = Column(Boolean, default=False, nullable=False)
    consent_contact = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, default='', nullable=False)
    status = Column(String(40), default='submitted', nullable=False, index=True)


class RecruiterIntegration(Base, TimestampMixin):
    __tablename__ = 'recruiter_integrations'
    __table_args__ = (
        UniqueConstraint(
            'owner_key',
            'provider',
            name='uq_recruiter_integration_owner_provider',
        ),
    )

    id = Column(Integer, primary_key=True)
    owner_key = Column(String(255), nullable=False, index=True)
    provider = Column(String(80), nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    config_json = Column(Text, default='{}', nullable=False)
    last_sync_at = Column(DateTime, nullable=True)


class RecruiterSetting(Base, TimestampMixin):
    __tablename__ = 'recruiter_settings'

    id = Column(Integer, primary_key=True)
    owner_key = Column(String(255), nullable=False, unique=True, index=True)
    ai_model = Column(String(100), default='gemini-2.5-flash', nullable=False)
    match_threshold = Column(Integer, default=70, nullable=False)


__all__ = [
    'RecruiterCandidate',
    'RecruiterIntegration',
    'RecruiterJob',
    'RecruiterMatch',
    'RecruiterSetting',
    'RecruiterSubmission',
    'TimestampMixin',
]
