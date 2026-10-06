import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
from schema_adoption import adoption_revision

from alembic import context
from sqlalchemy import engine_from_config, pool, inspect, text

# P0-10: alembic uses the SAME canonical database configuration as the app.
# DJ_DATABASE_URL (via app.config) overrides any alembic.ini default.
from app.config import get_settings
from app.db import Base
import app.domain.models  # noqa: F401 register tables

target_metadata = Base.metadata

config = context.config
db_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))


def run_migrations_online():
    connect_args = {"connect_timeout": 10} if db_url.startswith("postgresql") else {}
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.", poolclass=pool.NullPool, hide_parameters=True,
        connect_args=connect_args)
    with connectable.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        try:
            target_revision = context.get_revision_argument()
        except KeyError as exc:
            # Introspection commands have no destination; never adopt for them.
            if exc.args != ("destination_rev",):
                raise
            target_revision = None
        current_head = context.script.get_current_head()
        if ("alembic_version" not in tables and tables and
                target_revision == current_head):
            recognized_revision = adoption_revision(inspector, target_metadata, current_head)
            connection.execute(text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            connection.execute(text(
                "INSERT INTO alembic_version (version_num) VALUES (:head)"),
                {"head": recognized_revision})
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
