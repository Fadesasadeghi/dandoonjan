import importlib.util
from pathlib import Path
import sqlite3

spec = importlib.util.spec_from_file_location('migration_helpers', Path(__file__).parents[1] / 'regression_p0/test_migrations.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def test_populated_rc_upgrade_is_additive(tmp_path):
    path = tmp_path / 'rc.db'
    helpers._upgrade(path, '4f2c9d7e1a10')
    with sqlite3.connect(path) as conn:
        helpers._seed_case(conn)
        original = conn.execute('SELECT * FROM cases').fetchall()
    helpers._upgrade(path)
    helpers._upgrade(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT * FROM cases').fetchall() == original
        assert conn.execute('SELECT count(*) FROM dossier_revisions').fetchone() == (0,)
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
