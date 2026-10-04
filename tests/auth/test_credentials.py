import pytest
from .helpers import register, login


@pytest.mark.parametrize('password,accepted', [('x'*14, False), ('x'*15, True), ('x'*64, True), ('x'*128, True), ('x'*129, False), (' عبور فارسی با فاصله در دو طرف ', True)], ids=['below-minimum','minimum','64-characters','maximum','over-maximum','persian-spaces'])
def test_password_boundaries_and_no_trimming(api_client, password, accepted):
    client, _, _ = api_client
    response = register(client, password=password)
    assert response.status_code == (201 if accepted else 422)
    if accepted:
        assert login(client, password=password).status_code == 200
        if password != password.strip():
            assert login(client, password=password.strip()).status_code == 401


def test_email_policy_preserves_dots_plus_and_idna(api_client):
    client, sessions, _ = api_client
    assert register(client, ' FIRST.Last+Tag@BÜCHER.de ').status_code == 201
    from app.domain.models import User
    with sessions() as db:
        user = db.query(User).filter_by(kind='ACCOUNT').one()
        assert user.normalized_email == 'first.last+tag@xn--bcher-kva.de'


def test_hash_verifies_and_salts_are_independent(api_client):
    from app.security.authentication import hash_password, verify_password
    from .helpers import PASSWORD
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second
    assert verify_password(first, PASSWORD)
    assert not verify_password(first, PASSWORD + 'x')


def test_email_validation_has_no_dns_lookup(monkeypatch):
    import dns.resolver
    from app.security.authentication import normalize_email
    def network_forbidden(*args, **kwargs):
        pytest.fail('DNS lookup forbidden')
    monkeypatch.setattr(dns.resolver, 'resolve', network_forbidden)
    assert normalize_email(' Synthetic@example.com ')[1] == 'synthetic@example.com'


def test_invalid_unicode_password_is_safely_rejected(api_client):
    import json
    from .helpers import csrf
    client, _, _ = api_client
    body = json.dumps({'email':'Synthetic@example.com', 'password':'synthetic-passphrase-' + chr(0xd800)}, ensure_ascii=True)
    response = client.post('/api/auth/register', content=body, headers={**csrf(client), 'Content-Type':'application/json'})
    assert response.status_code == 422
    assert 'synthetic-passphrase' not in response.text
