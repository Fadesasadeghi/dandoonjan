"""Synthetic credentials and CSRF-aware request helpers; never production data."""
PASSWORD = 'عبارت عبور ساختگی و طولانی 123'


def csrf(client):
    response = client.get('/api/auth/csrf')
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json()['csrf_token'], 'Origin': str(client.base_url).rstrip('/')}


def register(client, email='Synthetic@example.com', password=PASSWORD):
    return client.post('/api/auth/register', json={'email': email, 'password': password}, headers=csrf(client))


def login(client, email='Synthetic@example.com', password=PASSWORD):
    return client.post('/api/auth/login', json={'email': email, 'password': password}, headers=csrf(client))
