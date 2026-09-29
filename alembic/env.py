import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

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
        target_revision = context.get_revision_argument()
        current_head = context.script.get_current_head()
        if ("alembic_version" not in tables and tables and
                target_revision == current_head):
            expected = set(target_metadata.tables)
            required_markers = {
                "findings": {"predicate", "treatment_item_id", "derivation_status"},
                "processing_runs": {"authority", "derivation_run_id"},
                "treatment_items": {"id", "treatment_id"},
            }
            required_fks = {
                ("findings", "treatment_item_id", "treatment_items", "id"),
            }
            actual_fks = {
                (table, constrained, fk["referred_table"], referred)
                for table in inspector.get_table_names()
                for fk in inspector.get_foreign_keys(table)
                for constrained, referred in zip(fk["constrained_columns"], fk["referred_columns"])
            }
            valid = (expected <= tables and all(
                {column["name"] for column in inspector.get_columns(table)} >=
                {column.name for column in target_metadata.tables[table].columns}
                for table in expected) and all(
                markers <= {column["name"] for column in inspector.get_columns(table)}
                for table, markers in required_markers.items()) and
                required_fks <= actual_fks)
            adoption_revision = current_head
            if not valid:
                # Recognize only the exact known RC table/column/type shape.
                # Never stamp an unknown or partial database as current.
                added = {'dossier_revisions', 'review_runs', 'diagnostic_hypotheses', 'hypothesis_evidence'}
                rc_tables = expected - added
                def matches_rc(table):
                    columns = {c['name']: c for c in inspector.get_columns(table)}
                    expected_columns = {c.name: c for c in target_metadata.tables[table].columns
                                        if not (table == 'artifacts' and c.name == 'document_role')}
                    return (set(columns) == set(expected_columns) and all(
                        columns[name]['type']._type_affinity == column.type._type_affinity
                        for name, column in expected_columns.items()))
                valid = (tables == rc_tables and all(matches_rc(t) for t in rc_tables)
                         and required_fks <= actual_fks)
                adoption_revision = '4f2c9d7e1a10'
            if not valid:
                raise RuntimeError(
                    "refusing Alembic adoption: database is not a complete current application schema")
            connection.execute(text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            connection.execute(text(
                "INSERT INTO alembic_version (version_num) VALUES (:head)"),
                {"head": adoption_revision})
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
