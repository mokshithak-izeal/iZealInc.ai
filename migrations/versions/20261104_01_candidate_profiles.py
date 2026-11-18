"""Add recruiter candidate profile and resume linkage.

Revision ID: 20261104_01
Revises: 20261102_01
"""

from alembic import op
import sqlalchemy as sa


revision = '20261104_01'
down_revision = '20261102_01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'recruiter_candidates',
        sa.Column('resume_candidate_id', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'recruiter_candidates',
        sa.Column('profile', sa.JSON(), nullable=True),
    )
    op.add_column(
        'recruiter_candidates',
        sa.Column('work_authorization', sa.String(length=120), server_default='', nullable=False),
    )
    op.add_column(
        'recruiter_candidates',
        sa.Column('notes', sa.Text(), server_default='', nullable=False),
    )
    op.create_index(
        'ix_recruiter_candidates_resume_candidate_id',
        'recruiter_candidates',
        ['resume_candidate_id'],
    )


def downgrade():
    op.drop_index(
        'ix_recruiter_candidates_resume_candidate_id',
        table_name='recruiter_candidates',
    )
    op.drop_column('recruiter_candidates', 'notes')
    op.drop_column('recruiter_candidates', 'work_authorization')
    op.drop_column('recruiter_candidates', 'profile')
    op.drop_column('recruiter_candidates', 'resume_candidate_id')
