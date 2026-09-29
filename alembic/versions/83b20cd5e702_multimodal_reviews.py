"""Add review audits and explicit hypothesis/evidence relationships."""
from alembic import op
import sqlalchemy as sa
revision = '83b20cd5e702'
down_revision = '72a19bc4d601'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('artifacts', sa.Column('document_role', sa.String(32), nullable=False, server_default='unspecified'))
    op.create_table('review_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(64), unique=True, nullable=False),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('derivation_run_id', sa.Integer(), sa.ForeignKey('processing_runs.id'), nullable=False),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('model', sa.String(128), nullable=False),
        sa.Column('schema_version', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('runtime_ms', sa.Integer(), nullable=False),
        sa.Column('error_code', sa.String(64)),
        sa.Column('output', sa.JSON()),
        sa.Column('source_index', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('diagnostic_hypotheses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('review_run_id', sa.Integer(), sa.ForeignKey('review_runs.id'), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('confidence_label', sa.String(8), nullable=False),
        sa.Column('insufficient_support', sa.Boolean(), nullable=False))
    op.create_table('hypothesis_evidence',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('hypothesis_id', sa.Integer(), sa.ForeignKey('diagnostic_hypotheses.id'), nullable=False),
        sa.Column('source_ref', sa.String(255), nullable=False),
        sa.Column('artifact_id', sa.Integer(), sa.ForeignKey('artifacts.id')),
        sa.Column('dossier_revision_id', sa.Integer(), sa.ForeignKey('dossier_revisions.id')),
        sa.Column('relationship_type', sa.String(16), nullable=False))
    for table, columns in [('review_runs', ['case_id', 'derivation_run_id']),
                           ('diagnostic_hypotheses', ['review_run_id']),
                           ('hypothesis_evidence', ['hypothesis_id'])]:
        for column in columns:
            op.create_index(f'ix_{table}_{column}', table, [column])


def downgrade():
    raise RuntimeError('Preserve review history: restore paired backup instead')
