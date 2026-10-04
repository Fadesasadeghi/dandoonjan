"""Add persistent visitor-scoped Demo identity; no adoption/backfill."""
from alembic import op
import sqlalchemy as sa

revision = 'e72b4c9a6102'
down_revision = 'd81e27a9c401'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite' and connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
        raise RuntimeError('DEMO_MIGRATION_ORPHANED_FOREIGN_KEYS')
    op.create_table('demo_visitors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), unique=True, nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('csrf_token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_demo_visitors_expires_at', 'demo_visitors', ['expires_at'])
    if connection.dialect.name == 'sqlite' and connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
        raise RuntimeError('DEMO_MIGRATION_FOREIGN_KEY_INTEGRITY_FAILED')


def downgrade():
    raise RuntimeError('Preserve Demo visitor identity/history: forward repair or approved paired backup restore required')
