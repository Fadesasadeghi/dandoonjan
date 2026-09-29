"""Add append-only dossier history without changing existing source data."""
from alembic import op
import sqlalchemy as sa

revision = '72a19bc4d601'
down_revision = '4f2c9d7e1a10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('dossier_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(64), nullable=False, unique=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('case_version', sa.Integer(), nullable=False),
        *[sa.Column(name, sa.Text(), nullable=False) for name in
          ('symptoms', 'duration', 'medical_history', 'medications', 'allergies',
           'treatment_plan', 'previous_reports', 'previous_treatments')],
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('case_id', 'case_version'))
    op.create_index('ix_dossier_revisions_case_id', 'dossier_revisions', ['case_id'])


def downgrade():
    raise RuntimeError('Preserve dossier history: restore a paired backup instead of destructive downgrade')
