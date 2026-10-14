"""Synthetic upload contract and pre-ingestion resource regressions."""
import hashlib

import pytest
from app.domain.models import Artifact, AuditEvent


@pytest.fixture(params=['account', 'demo'])
def upload_context(api_client, request):
    client, sessions, store = api_client
    prefix = '/api/cases'
    if request.param == 'demo':
        response = client.post('/api/demo/session')
        assert response.status_code == 200
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        prefix = '/api/demo/cases'
    response = client.post(prefix, data={'question': 'Synthetic upload boundary'})
    assert response.status_code == 201
    path = prefix + '/' + response.json()['case_id']
    return client, sessions, store, path


def files_snapshot(store):
    return {p.relative_to(store).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in store.rglob('*') if p.is_file()}


def watch_spools(monkeypatch):
    import starlette.formparsers as parsers
    real = parsers.SpooledTemporaryFile
    observed = []
    def tracked(*args, **kwargs):
        stream = real(*args, **kwargs)
        original_write = stream.write
        record = {'stream': stream, 'written': 0}
        def write(data):
            record['written'] += len(data)
            return original_write(data)
        stream.write = write
        observed.append(record)
        return stream
    monkeypatch.setattr(parsers, 'SpooledTemporaryFile', tracked)
    return observed


@pytest.mark.parametrize('extra,status', [(0, 201), (1, 422), (4096, 422)])
def test_configured_boundary_before_spooling(upload_context, regression_settings, monkeypatch, extra, status):
    client, sessions, store, path = upload_context
    # Exercise the existing configurable limit, not a new production limit.
    monkeypatch.setattr(regression_settings, 'max_upload_bytes', 128)
    observed = watch_spools(monkeypatch)
    response = client.post(path + '/artifacts', files={'file': ('sample.txt', b'x'*(128+extra), 'text/plain')})
    assert response.status_code == status
    with sessions() as db:
        assert db.query(Artifact).count() == int(status == 201)
    assert len(files_snapshot(store)) == int(status == 201)
    assert observed and all(r['stream'].closed for r in observed)
    # Existing reader uses limit+1 as the oversize sentinel. The spool should
    # not retain arbitrary rejected bytes before that reader can enforce it.
    assert max(r['written'] for r in observed) <= 129


@pytest.mark.parametrize('name,data,mime', [
    ('empty.txt', b'', 'text/plain'),
    ('blank.txt', b' \n\t', 'text/plain'),
    ('bom.txt', b'\xef\xbb\xbf', 'text/plain'),
    ('binary.txt', b'hello\x00world', 'text/plain'),
    ('bad.txt', b'\xff', 'text/plain'),
    ('bad.pdf', b'%PDF-1.4 broken', 'application/pdf'),
    ('bad.png', b'\x89PNG\r\n\x1a\ninvalid', 'image/png'),
    ('bad.exe', b'Synthetic text', 'application/octet-stream'),
    ('no-extension', b'Synthetic text', 'text/plain'),
    ('wrong.txt', b'Synthetic text', 'image/png'),
])
def test_rejection_preserves_existing_evidence(upload_context, name, data, mime):
    client, sessions, store, path = upload_context
    assert client.post(path + '/artifacts', files={'file': ('valid.txt', b'Synthetic original', 'text/plain')}).status_code == 201
    before = client.get(path).json(), files_snapshot(store)
    responses = [client.post(path + '/artifacts', files={'file': (name, data, mime)}) for _ in range(2)]
    assert [r.status_code for r in responses] == [422, 422]
    assert responses[0].json() == responses[1].json()
    assert set(responses[0].json()['detail']) == {'code', 'message_fa'}
    assert (client.get(path).json(), files_snapshot(store)) == before
    with sessions() as db:
        assert db.query(Artifact).count() == 1
        assert db.query(AuditEvent).filter_by(event_type='artifact_rejected').count() == 2


@pytest.mark.parametrize('name', ['../sample.txt', '/absolute/sample.txt', r'C:\folder\sample.txt', 'a'*600+'.txt'])
def test_names_are_labels_and_never_replace(upload_context, name):
    client, sessions, store, path = upload_context
    def post(data):
        return client.post(path + '/artifacts', files={'file': (name, data, 'text/plain')})
    first = post(b'Synthetic first')
    assert first.status_code == 201
    initial = files_snapshot(store)
    duplicate = post(b'Synthetic first')
    assert duplicate.status_code == 201
    assert duplicate.json()['duplicate_of'] == first.json()['artifact_id']
    assert files_snapshot(store) == initial
    second = post(b'Synthetic second')
    assert second.status_code == 201 and second.json()['duplicate_of'] is None
    assert second.json()['artifact_id'] != first.json()['artifact_id']
    assert initial.items() <= files_snapshot(store).items()
    assert client.get(path).json()['version'] == 3
    with sessions() as db:
        assert db.query(Artifact).count() == 2
        for artifact in db.query(Artifact):
            target = (store / artifact.storage_key).resolve()
            assert target.is_relative_to(store.resolve()) and target.is_file()
            assert len(artifact.safe_filename) <= 180
            assert len(artifact.original_filename) <= 500


@pytest.mark.parametrize('body,content_type,status', [
    (b'', 'multipart/form-data', 400),
    (b'--x\r\nContent-Disposition: form-data; name="file"\r\n\r\ntext\r\n--x--\r\n', 'multipart/form-data; boundary=x', 422),
    (b'--x\r\nContent-Disposition: form-data; name="file"; filename=""\r\n\r\ntext\r\n--x--\r\n', 'multipart/form-data; boundary=x', 422),
    (b'--x\r\nContent-Disposition: form-data; filename="a.txt"\r\n\r\ntext\r\n--x--\r\n', 'multipart/form-data; boundary=x', 400),
])
def test_malformed_metadata_cleanup(upload_context, monkeypatch, body, content_type, status):
    client, sessions, store, path = upload_context
    observed = watch_spools(monkeypatch)
    response = client.post(path + '/artifacts', content=body, headers={'Content-Type': content_type})
    assert response.status_code == status
    assert all(r['stream'].closed for r in observed)
    assert not files_snapshot(store)
    assert client.get(path).json()['version'] == 1
    with sessions() as db:
        assert db.query(Artifact).count() == 0


def test_csrf_precedes_multipart_read(upload_context, monkeypatch):
    client, _, store, path = upload_context
    observed = watch_spools(monkeypatch)
    response = client.post(path + '/artifacts', headers={'X-CSRF-Token': 'invalid'},
                           files={'file': ('a.txt', b'Synthetic', 'text/plain')})
    assert response.status_code == 403
    assert not observed and not files_snapshot(store)


def test_incomplete_multipart_closes_spool(upload_context, monkeypatch):
    client, sessions, store, path = upload_context
    observed = watch_spools(monkeypatch)
    response = client.post(path + '/artifacts', headers={'Content-Type': 'multipart/form-data; boundary=x'},
        content=b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\nContent-Type: text/plain\r\n\r\nunfinished')
    assert response.status_code == 422
    assert not files_snapshot(store)
    with sessions() as db:
        assert db.query(Artifact).count() == 0
    assert observed and all(r['stream'].closed for r in observed)


def test_repeated_parts_characterization(upload_context, regression_settings, monkeypatch):
    """Single UploadFile currently selects the last file field; not a batch API.

    Preserve that observed compatibility; additional-part policy is unspecified.
    Every part still needs bounded temporary storage, including ignored fields.
    """
    client, sessions, store, path = upload_context
    monkeypatch.setattr(regression_settings, 'max_upload_bytes', 128)
    observed = watch_spools(monkeypatch)
    response = client.post(path + '/artifacts', files=[
        ('ignored', ('ignored.txt', b'i'*1024, 'text/plain')),
        ('file', ('first.txt', b'a'*1024, 'text/plain')),
        ('file', ('last.txt', b'Synthetic selected', 'text/plain')),
    ])
    assert response.status_code == 201
    with sessions() as db:
        artifact = db.query(Artifact).one()
        assert artifact.original_filename == 'last.txt'
        assert (store / artifact.storage_key).read_bytes() == b'Synthetic selected'
    assert len(observed) == 3 and all(r['stream'].closed for r in observed)
    assert all(r['written'] <= 129 for r in observed)


@pytest.mark.parametrize('chunk_size', [1, 17, 65536])
def test_fragmented_parser_retains_only_existing_sentinel(monkeypatch, regression_settings, chunk_size):
    import asyncio
    from starlette.requests import Request
    from app.security.upload_form import with_bounded_upload_form
    monkeypatch.setattr(regression_settings, 'max_upload_bytes', 128)
    observed = watch_spools(monkeypatch)
    body = (b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n\r\n'
            + b'x'*4096 + b'\r\n--x--\r\n')
    chunks = iter([body[i:i+chunk_size] for i in range(0, len(body), chunk_size)] + [b''])
    async def receive():
        chunk = next(chunks)
        return {'type': 'http.request', 'body': chunk, 'more_body': bool(chunk)}
    request = Request({'type': 'http', 'headers': [(b'content-type', b'multipart/form-data; boundary=x')]}, receive)
    async def handler(request):
        form = await request.form()
        assert await form['file'].read() == b'x'*129
        return 'observed'
    assert asyncio.run(with_bounded_upload_form(request, handler)) == 'observed'
    assert observed[0]['written'] == 129 and observed[0]['stream'].closed


def test_disconnect_closes_partial_spool(monkeypatch, regression_settings):
    import asyncio
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.security.upload_form import with_bounded_upload_form
    observed = watch_spools(monkeypatch)
    messages = iter([
        {'type': 'http.request', 'body': b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n\r\npartial', 'more_body': True},
        {'type': 'http.disconnect'},
    ])
    async def receive():
        return next(messages)
    async def handler(request):
        pytest.fail('Disconnected upload reached handler')
    request = Request({'type': 'http', 'headers': [(b'content-type', b'multipart/form-data; boundary=x')]}, receive)
    with pytest.raises(HTTPException) as error:
        asyncio.run(with_bounded_upload_form(request, handler))
    assert error.value.status_code == 400
    assert error.value.detail == 'There was an error parsing the body'
    assert observed and all(r['stream'].closed for r in observed)


def test_oversize_disk_spool_preserves_report_and_artifacts(upload_context, regression_settings, monkeypatch):
    from starlette.formparsers import MultiPartParser
    client, sessions, store, path = upload_context
    assert client.put(path + '/dossier', json={}).status_code == 200
    assert client.post(path + '/artifacts', files={'file': ('plan.txt', b'Synthetic Treatment Plan\nTooth 46: RCT recommended', 'text/plain')}).status_code == 201
    assert client.post(path + '/process').status_code == 200
    report = client.get(path + '/report')
    assert report.status_code == 200
    before = client.get(path).json(), client.get(path + '/dossier').json(), files_snapshot(store)
    monkeypatch.setattr(regression_settings, 'max_upload_bytes', 128)
    # Force the disk path without allocating a large test fixture.
    monkeypatch.setattr(MultiPartParser, 'spool_max_size', 64)
    observed = watch_spools(monkeypatch)
    response = client.post(path + '/artifacts', files={'file': ('oversize.txt', b'x'*4096, 'text/plain')})
    assert response.status_code == 422
    assert observed[0]['written'] == 129
    assert observed[0]['stream']._rolled and observed[0]['stream'].closed
    assert (client.get(path).json(), client.get(path + '/dossier').json(), files_snapshot(store)) == before
    assert client.get(path + '/report').json() == report.json()
    with sessions() as db:
        assert db.query(Artifact).count() == 1
        assert db.query(AuditEvent).filter_by(event_type='artifact_rejected').count() == 1
