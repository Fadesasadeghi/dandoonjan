import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alembic import context
from sqlalchemy import engine_from_config, pool

# P0-10: alembic uses the SAME canonical database configuration as the app.
# DJ_DATABASE_URL (via app.config) overrides any alembic.ini default.
from app.config import get_settings
from app.db import Base
import app.domain.models  # noqa: F401 register tables

target_metadata = Base.metadata

config = context.config
db_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
