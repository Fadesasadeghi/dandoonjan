"""Recognize explicit unstamped schema versions, never a guessed partial schema.

preauth_schema.json freezes committed pre-auth metadata at 83b20cd5e702.
Do not redefine that historical shape when adding future ORM models.
"""
import json
from pathlib import Path


def metadata_shape(metadata):
    return {name: {
        'columns': {c.name: [c.type._type_affinity.__name__, c.nullable, getattr(c.type, 'length', None)] for c in table.columns},
        'primary_key': sorted(c.name for c in table.primary_key.columns),
        'fks': sorted([[fk.parent.name, fk.column.table.name, fk.column.name, fk.ondelete or 'NO ACTION'] for fk in table.foreign_keys]),
        'unique': sorted([sorted(c.name for c in constraint.columns)
                          for constraint in table.constraints if constraint.__class__.__name__ == 'UniqueConstraint'] +
                         [[c.name] for c in table.columns if c.unique and c.index]),
        'indexes': sorted([sorted(c.name for c in index.columns) for index in table.indexes]),
    } for name, table in metadata.tables.items()}


def reflected_shape(inspector):
    result = {}
    for name in inspector.get_table_names():
        if name == 'alembic_version':
            continue
        indexes = [index for index in inspector.get_indexes(name) if not index.get('duplicates_constraint')]
        result[name] = {
            'columns': {c['name']: [c['type']._type_affinity.__name__, c['nullable'], getattr(c['type'], 'length', None)] for c in inspector.get_columns(name)},
            'primary_key': sorted(inspector.get_pk_constraint(name)['constrained_columns']),
            'fks': sorted([[column, fk['referred_table'], target, fk.get('options', {}).get('ondelete') or 'NO ACTION']
                           for fk in inspector.get_foreign_keys(name)
                           for column, target in zip(fk['constrained_columns'], fk['referred_columns'])]),
            'unique': sorted([sorted(c['column_names']) for c in inspector.get_unique_constraints(name)] +
                             [sorted(i['column_names']) for i in indexes if i['unique']]),
            'indexes': sorted([sorted(index['column_names']) for index in indexes]),
        }
    return result


def adoption_revision(inspector, metadata, head):
    actual = reflected_shape(inspector)
    current = metadata_shape(metadata)
    def matches(shape):
        if actual == shape:
            return True
        # Initial migration retained this historical uniqueness; create_all
        # schemas never had it. Preserve both exact known variants.
        migrated = {name: dict(table) for name, table in shape.items()}
        migrated['knowledge_packs']['unique'] = sorted(shape['knowledge_packs']['unique'] + [['knowledge_pack_id']])
        return actual == migrated

    if matches(current):
        # Auth credential checks must exist before an auth schema can be adopted.
        checks_valid = True
        for name, table in metadata.tables.items():
            expected_checks = {c.name: ''.join(str(c.sqltext).split()) for c in table.constraints
                               if c.__class__.__name__ == 'CheckConstraint'}
            actual_checks = {c['name']: ''.join(c['sqltext'].split()) for c in inspector.get_check_constraints(name)}
            checks_valid = checks_valid and expected_checks.items() <= actual_checks.items()
        if checks_valid:
            return head
    preauth = json.loads(Path(__file__).with_name('preauth_schema.json').read_text(encoding='utf-8'))
    if matches(preauth):
        return '83b20cd5e702'
    rc = {name: {**shape, 'columns': dict(shape['columns'])} for name, shape in preauth.items()
          if name not in {'dossier_revisions','review_runs','diagnostic_hypotheses','hypothesis_evidence'}}
    rc['artifacts']['columns'].pop('document_role')
    if matches(rc):
        return '4f2c9d7e1a10'
    raise RuntimeError('refusing Alembic adoption: database is not a complete recognized application schema')
