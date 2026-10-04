import io
import pytest
import pymupdf
from PIL import Image
from app.domain.models import Artifact, Case


def png(size=(10, 10)):
    out = io.BytesIO()
    Image.new('RGB', size).save(out, 'PNG')
    return out.getvalue()


def pdf(pages=1, encrypted=False, password='secret'):
    with pymupdf.open() as doc:
        for _ in range(pages):
            doc.new_page()
        return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw=password) if encrypted else doc.tobytes()


def jpeg():
    out = io.BytesIO()
    Image.new('RGB', (10,10)).save(out, 'JPEG')
    return out.getvalue()


def case(client, review=False):
    cid = client.post('/api/cases', data={'question': 'Synthetic question'}).json()['case_id']
    if review:
        assert client.put(f'/api/cases/{cid}/dossier', json={}).status_code == 200
    return cid


def test_unknown_case_preserves_error_contract(api_client):
    client, _, _ = api_client
    response = client.post('/api/cases/missing/artifacts', files={'file': ('a.txt', b'ordinary text', 'text/plain')})
    assert response.status_code == 404
    assert response.json() == {'detail':'CASE_NOT_FOUND'}


@pytest.mark.parametrize('name,data,mime,accepted', [
    ('a.TXT', b'ordinary readable nonclinical text', '', True),
    ('a.png', png(), 'application/octet-stream', True),
    ('a.PNG', png(), 'image/png', True),
    ('a.JPG', jpeg(), 'image/jpeg', True),
    ('a.png', png(), 'image/jpeg', False),
    ('a.txt', png(), 'text/plain', False),
    ('a.jpg', png(), 'image/jpeg', False),
    ('a.heic', b'GIF89a' + b'0'*50, 'image/heic', False),
    ('a.heic', png(), 'image/png', False),
    ('a.txt', b'', 'text/plain', False),
    ('a.txt', b'\xef\xbb\xbf', 'text/plain', False),
    ('a.txt', b' \n\t', 'text/plain', False),
    ('a.txt', b'bad\xff', 'text/plain', False),
    ('a.txt', b'hello\x00world', 'text/plain', False),
    ('a.pdf', pdf(encrypted=True), 'application/pdf', False),
    ('a.pdf', pdf(encrypted=True, password=''), 'application/pdf', False),
    ('a.pdf', pdf(), 'application/pdf', True),
])
def test_validation(api_client, name, data, mime, accepted):
    client, sessions, store = api_client
    cid = case(client)
    response = client.post(f'/api/cases/{cid}/artifacts', files={'file': (name, data, mime)})
    assert response.status_code == (201 if accepted else 422)
    with sessions() as db:
        assert db.query(Artifact).count() == int(accepted)
        assert db.query(Case).one().version == (2 if accepted else 1)
    if not accepted:
        assert not list(store.rglob('*'))


@pytest.mark.parametrize('extra,expected', [(0, 201), (1, 422)])
def test_exact_size(api_client, extra, expected):
    client, _, _ = api_client
    cid = case(client)
    response = client.post(f'/api/cases/{cid}/artifacts', files={'file': ('a.txt', b'x'*(25*1024*1024+extra), 'text/plain')})
    assert response.status_code == expected
    if extra:
        assert '۲۵' in response.json()['detail']['message_fa']


def test_bounded_reader():
    from app.api.routes import read_upload_bounded
    class Reader:
        total = 0
        def read(self, size=-1):
            assert 0 < size <= 65536
            self.total += size
            return b'x'*size
    reader = Reader()
    assert len(read_upload_bounded(reader, 100000)) == 100001
    assert reader.total == 100001


@pytest.mark.parametrize('pages,review,expected', [(8, True, 201), (9, True, 422), (9, False, 201)])
def test_pdf_capacity(api_client, pages, review, expected):
    client, _, _ = api_client
    cid = case(client, review)
    assert client.post(f'/api/cases/{cid}/artifacts', files={'file': ('a.pdf', pdf(pages), 'application/pdf')}).status_code == expected


def test_aggregate_and_duplicate(api_client, monkeypatch):
    from app.ai import multimodal
    monkeypatch.setattr(multimodal, 'MAX_IMAGES', 1)
    client, sessions, _ = api_client
    cid = case(client, True)
    path = f'/api/cases/{cid}/artifacts'
    first = client.post(path, files={'file': ('one.png', png(), 'image/png')}).json()
    duplicate = client.post(path, data={'document_role': 'prescription'}, files={'file': ('renamed.png', png(), 'image/png')})
    assert duplicate.status_code == 201
    assert duplicate.json()['duplicate_of'] == first['artifact_id']
    assert client.post(path, files={'file': ('two.png', png((11, 10)), 'image/png')}).status_code == 422
    with sessions() as db:
        assert db.query(Artifact).count() == 1
        assert db.query(Artifact).one().original_filename == 'one.png'
        assert db.query(Artifact).one().document_role == 'unspecified'
        assert db.query(Case).one().version == 3  # dossier plus one artifact


@pytest.mark.parametrize('excess', [False, True])
def test_pixels(api_client, monkeypatch, excess):
    from app.ai import multimodal
    assert multimodal.MAX_PIXELS == 20_000_000
    client, _, _ = api_client
    cid = case(client, True)
    assert client.post(f'/api/cases/{cid}/artifacts', files={'file': ('a.png', png((4000+int(excess),5000)), 'image/png')}).status_code == (422 if excess else 201)


def test_sixteen_derivatives(api_client):
    client, _, _ = api_client
    cid = case(client, True)
    path = f'/api/cases/{cid}/artifacts'
    for _ in range(2):
        assert client.post(path, files={'file': ('a.pdf', pdf(8), 'application/pdf')}).status_code == 201
    assert client.post(path, files={'file': ('a.png', png(), 'image/png')}).status_code == 422


@pytest.mark.parametrize('count', [100,101])
def test_source_count(monkeypatch, count):
    from types import SimpleNamespace
    from app.core.cases import dossier
    from app.ai.multimodal import bundle
    monkeypatch.setattr(dossier, 'fields', lambda _: {str(i):'ordinary text' for i in range(count)})
    candidate = SimpleNamespace(public_id='synthetic', version=1, question_text='', dentist_recommendation_text='', context_text='', artifacts=[])
    if count == 101:
        with pytest.raises(ValueError, match='OUTBOUND_SOURCE_LIMIT'):
            bundle(candidate)
    else:
        assert len(bundle(candidate)['sources']) == 100


@pytest.mark.parametrize('length', [100000,100001])
def test_text_boundary(monkeypatch, length):
    from types import SimpleNamespace
    from app.core.cases import dossier
    from app.ai.multimodal import bundle
    monkeypatch.setattr(dossier, 'fields', lambda _: {})
    candidate = SimpleNamespace(public_id='synthetic', version=1, question_text='x'*length,
        dentist_recommendation_text='', context_text='', artifacts=[])
    if length == 100001:
        with pytest.raises(ValueError, match='OUTBOUND_TEXT_LIMIT'):
            bundle(candidate)
    else:
        assert len(bundle(candidate)['text'][0]['text']) == 100000


@pytest.mark.parametrize('excess', [False, True])
def test_derivative_bytes(api_client, monkeypatch, excess):
    from app.ai import multimodal
    image = png()
    monkeypatch.setattr(multimodal, 'MAX_BYTES', len(multimodal.prepare_image(image))-int(excess))
    client, _, _ = api_client
    cid = case(client, True)
    assert client.post(f'/api/cases/{cid}/artifacts', files={'file': ('a.png', image, 'image/png')}).status_code == (422 if excess else 201)


def test_text_capacity_preserves_current_report(api_client):
    client, sessions, store = api_client
    cid = case(client, True)
    path = f'/api/cases/{cid}'
    for i in range(4):
        assert client.post(path+'/artifacts', files={'file': (f'{i}.txt', str(i).encode()+b'x'*19999, 'text/plain')}).status_code == 201
    assert client.post(path+'/process').status_code == 200
    report = client.get(path+'/report').json()
    version = client.get(path).json()['version']
    files = sorted(str(p) for p in store.rglob('*'))
    assert client.post(path+'/artifacts', files={'file': ('extra.txt', b'y'*20000, 'text/plain')}).status_code == 422
    assert client.get(path).json()['version'] == version
    assert client.get(path+'/report').json() == report
    assert sorted(str(p) for p in store.rglob('*')) == files


def test_concurrent_capacity(api_client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.ai import multimodal
    monkeypatch.setattr(multimodal, 'MAX_IMAGES', 1)
    client, sessions, _ = api_client
    cid = case(client, True)
    def upload(n):
        return client.post(f'/api/cases/{cid}/artifacts', files={'file': (f'{n}.png', png((n+10,10)), 'image/png')}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(upload, [0,1])) == [201,422]
    with sessions() as db:
        assert db.query(Artifact).count() == 1
