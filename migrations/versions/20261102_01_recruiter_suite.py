"""Create recruiter suite tables.

Revision ID: 20261102_01
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = '20261102_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recruiter_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_key', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('company', sa.String(length=200), nullable=False),
        sa.Column('location', sa.String(length=200), server_default='Remote', nullable=False),
        sa.Column('employment_type', sa.String(length=80), server_default='Full Time', nullable=False),
        sa.Column('description', sa.Text(), server_default='', nullable=False),
        sa.Column('required_skills', sa.Text(), server_default='', nullable=False),
        sa.Column('source', sa.String(length=80), server_default='Manual', nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('minimum_experience_years', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=40), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_recruiter_jobs_owner_key', 'recruiter_jobs', ['owner_key'])
    op.create_index('ix_recruiter_jobs_title', 'recruiter_jobs', ['title'])
    op.create_index('ix_recruiter_jobs_company', 'recruiter_jobs', ['company'])
    op.create_index('ix_recruiter_jobs_status', 'recruiter_jobs', ['status'])

    op.create_table(
        'recruiter_candidates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_key', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('location', sa.String(length=200), server_default='', nullable=False),
        sa.Column('years_experience', sa.Float(), server_default='0', nullable=False),
        sa.Column('skills', sa.Text(), server_default='', nullable=False),
        sa.Column('availability', sa.String(length=50), server_default='Available', nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=True),
        sa.Column('current_role', sa.String(length=255), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('owner_key', 'email', name='uq_recruiter_candidate_owner_email'),
    )
    op.create_index('ix_recruiter_candidates_owner_key', 'recruiter_candidates', ['owner_key'])
    op.create_index('ix_recruiter_candidates_name', 'recruiter_candidates', ['name'])
    op.create_index('ix_recruiter_candidates_email', 'recruiter_candidates', ['email'])

    op.create_table(
        'recruiter_matches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_key', sa.String(length=255), nullable=False),
        sa.Column(
            'job_id',
            sa.Integer(),
            sa.ForeignKey('recruiter_jobs.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'candidate_id',
            sa.Integer(),
            sa.ForeignKey('recruiter_candidates.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('matched_skills', sa.Text(), server_default='', nullable=False),
        sa.Column('missing_skills', sa.Text(), server_default='', nullable=False),
        sa.Column('explanation', sa.Text(), server_default='', nullable=False),
        sa.Column('shortlisted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('job_id', 'candidate_id', name='uq_recruiter_job_candidate_match'),
    )
    op.create_index('ix_recruiter_matches_owner_key', 'recruiter_matches', ['owner_key'])
    op.create_index('ix_recruiter_matches_v2_job_id', 'recruiter_matches', ['job_id'])
    op.create_index('ix_recruiter_matches_v2_candidate_id', 'recruiter_matches', ['candidate_id'])

    op.create_table(
        'recruiter_submissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_key', sa.String(length=255), nullable=False),
        sa.Column(
            'job_id',
            sa.Integer(),
            sa.ForeignKey('recruiter_jobs.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'candidate_id',
            sa.Integer(),
            sa.ForeignKey('recruiter_candidates.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('vendor', sa.String(length=200), nullable=False),
        sa.Column('consent_share', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('consent_contact', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('notes', sa.Text(), server_default='', nullable=False),
        sa.Column('status', sa.String(length=40), server_default='submitted', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_recruiter_submissions_owner_key', 'recruiter_submissions', ['owner_key'])
    op.create_index('ix_recruiter_submissions_v2_job_id', 'recruiter_submissions', ['job_id'])
    op.create_index('ix_recruiter_submissions_v2_candidate_id', 'recruiter_submissions', ['candidate_id'])
    op.create_index('ix_recruiter_submissions_status', 'recruiter_submissions', ['status'])

    op.create_table(
        'recruiter_integrations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_key', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=80), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('config_json', sa.Text(), server_default='{}', nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'owner_key',
            'provider',
            name='uq_recruiter_integration_owner_provider',
        ),
    )
    op.create_index('ix_recruiter_integrations_owner_key', 'recruiter_integrations', ['owner_key'])

    op.create_table(
        'recruiter_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_key', sa.String(length=255), nullable=False),
        sa.Column('ai_model', sa.String(length=100), server_default='gemini-2.5-flash', nullable=False),
        sa.Column('match_threshold', sa.Integer(), server_default='70', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_recruiter_settings_owner_key', 'recruiter_settings', ['owner_key'], unique=True)


def downgrade():
    op.drop_table('recruiter_settings')
    op.drop_table('recruiter_integrations')
    op.drop_table('recruiter_submissions')
    op.drop_table('recruiter_matches')
    op.drop_table('recruiter_candidates')
    op.drop_table('recruiter_jobs')
