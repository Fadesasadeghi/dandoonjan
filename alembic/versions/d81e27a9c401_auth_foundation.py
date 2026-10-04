"""Add credential accounts and opaque session foundation; preserve case ownership.

Existing users remain non-authenticating LEGACY principals. SQLite rebuilds only
users to add checks; no clinical table is altered. Verify FKs before/after.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd81e27a9c401'
down_revision = '83b20cd5e702'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('AUTH_MIGRATION_ORPHANED_FOREIGN_KEYS')
        # Alembic's dedicated SQLite connection has enforcement off for its
        # existing batch-rebuild lifecycle. Never disable it on runtime engines.
        if connection.exec_driver_sql('PRAGMA foreign_keys').scalar():
            raise RuntimeError('AUTH_MIGRATION_REQUIRES_DEDICATED_SQLITE_BATCH_CONNECTION')
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('email', sa.String(320), nullable=True))
        batch.add_column(sa.Column('normalized_email', sa.String(320), nullable=True))
        batch.add_column(sa.Column('password_hash', sa.String(512), nullable=True))
        batch.add_column(sa.Column('kind', sa.String(16), nullable=False, server_default='LEGACY'))
        batch.add_column(sa.Column('status', sa.String(16), nullable=False, server_default='DISABLED'))
        batch.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint('uq_users_normalized_email', ['normalized_email'])
        batch.create_check_constraint('ck_users_kind', "kind IN ('ACCOUNT','LEGACY')")
        batch.create_check_constraint('ck_users_status', "status IN ('ACTIVE','DISABLED')")
        batch.create_check_constraint('ck_users_credentials',
            "(kind = 'ACCOUNT' AND email IS NOT NULL AND normalized_email IS NOT NULL "
            "AND password_hash IS NOT NULL AND email <> '' AND normalized_email <> '' "
            "AND password_hash LIKE '$argon2id$%') OR "
            "(kind = 'LEGACY' AND status = 'DISABLED' AND email IS NULL "
            "AND normalized_email IS NULL AND password_hash IS NULL AND email_verified_at IS NULL)")
    op.create_table('auth_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('csrf_token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])
    op.create_table('preauth_contexts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('csrf_token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_preauth_contexts_expires_at', 'preauth_contexts', ['expires_at'])
    op.create_table('auth_rate_limits',
        sa.Column('key_hash', sa.String(64), primary_key=True),
        sa.Column('window_started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.CheckConstraint('attempts > 0', name='ck_auth_rate_attempts'))
    op.create_index('ix_auth_rate_limits_window_started_at', 'auth_rate_limits', ['window_started_at'])
    if connection.dialect.name == 'sqlite' and connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
        raise RuntimeError('AUTH_MIGRATION_FOREIGN_KEY_INTEGRITY_FAILED')


def downgrade():
    raise RuntimeError('Preserve accounts and clinical history: forward repair or approved paired backup restore required')
