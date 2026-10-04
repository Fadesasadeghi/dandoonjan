"""Opt-in private synthetic cluster only; never read a shared database URL."""
from verification.test_rc_postgres import pg_url, migrate
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
import pytest


def test_postgres_auth_migration_and_constraints(pg_url):
    from app.security.authentication import hash_password
    from .helpers import PASSWORD
    migrate(pg_url, '83b20cd5e702')
    engine = create_engine(pg_url, hide_parameters=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (id,public_id,display_name,created_at) VALUES (1,'USR-legacy','synthetic','2026-01-01')"))
            conn.execute(text("INSERT INTO cases (id,public_id,user_id,status,version,question_text,context_text,dentist_recommendation_text,ontology_version,created_at,updated_at) VALUES (1,'CASE-synthetic',1,'CREATED',9,'synthetic','','','synthetic','2026-01-01','2026-01-01')"))
        migrate(pg_url)
        with engine.connect() as conn:
            assert conn.execute(text('SELECT kind,status,email,password_hash FROM users')).one() == ('LEGACY','DISABLED',None,None)
            assert conn.execute(text('SELECT user_id,version FROM cases')).one() == (1,9)
        encoded = hash_password(PASSWORD)
        statement=text("INSERT INTO users (id,public_id,display_name,created_at,kind,status,email,normalized_email,password_hash) VALUES (:id,:public,'synthetic','2026-01-01','ACCOUNT','ACTIVE','Synthetic@example.com','synthetic@example.com',:hash)")
        with engine.begin() as conn: conn.execute(statement, {'id':2,'public':'USR-account','hash':encoded})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn: conn.execute(statement, {'id':3,'public':'USR-duplicate','hash':encoded})
        assert {'auth_sessions','preauth_contexts','auth_rate_limits'} <= set(inspect(engine).get_table_names())
    finally: engine.dispose()
