"""Real password hashing, account authorization and session lifecycle."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3

from fastapi.testclient import TestClient
import pytest

from forage.webapp.accounts import AccountStore, hash_password, verify_password
from forage.webapp.auth import AuthConfig, AuthConfigError, COOKIE_NAME
from .conftest import ADMIN_PASSWORD, REVIEW_PASSWORD, BOOK_ID, sign_in

PASSWORD = 'a long test passphrase'


def add_user(client, username='bob', role='reviewer'):
    response = client.post('/api/users', json={'username': username, 'password': PASSWORD,
                                             'display_name': 'Bob', 'role': role})
    assert response.status_code == 201, response.text
    return response.json()


def test_salted_scrypt_and_password_bounds():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second
    assert verify_password(PASSWORD, first)
    assert not verify_password('wrong password', first)
    assert not verify_password(PASSWORD, 'broken-hash')
    assert not verify_password(None, first)
    for bad in ('short', 'x' * 129, None, '\ud800' * 15):
        with pytest.raises(ValueError):
            hash_password(bad)
    unicode_password = ' café 🍎 ' * 5
    assert verify_password(unicode_password, hash_password(unicode_password))


@pytest.mark.parametrize('path,method', [('/api/users','get'), ('/api/users','post'), ('/api/users/missing','delete')])
def test_management_is_admin_only(client, path, method):
    assert getattr(client, method)(path).status_code == 401
    sign_in(client)
    assert getattr(client, method)(path).status_code == 403


def test_create_login_delete_revokes_sessions_and_keeps_notes(client):
    sign_in(client, ADMIN_PASSWORD)
    user = add_user(client)
    assert set(user) == {'id', 'username', 'display_name', 'role', 'created_at'}
    reviewer = TestClient(client.app)
    login = reviewer.post('/api/session', json={'username':'BOB', 'password':PASSWORD, 'label':'Impostor', 'role':'admin'})
    assert login.status_code == 200
    assert login.json()['label'] == 'Bob' and login.json()['role'] == 'reviewer'
    note = reviewer.post(f'/api/books/{BOOK_ID}/comments', json={'scope':'book', 'body':'Keep this note.'}).json()
    assert note['author'] == 'Bob'
    cookie = reviewer.cookies.get(COOKIE_NAME)
    with client.app.state.accounts.connect() as conn:
        row = conn.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
        assert PASSWORD not in str(dict(row))
        assert verify_password(PASSWORD, row['password_hash'])
        assert conn.execute('SELECT 1 FROM user_sessions WHERE session_hash=?',
                            (hashlib.sha256(cookie.encode()).hexdigest(),)).fetchone()
        assert not conn.execute('SELECT 1 FROM user_sessions WHERE session_hash=?',(cookie,)).fetchone()
    assert client.delete('/api/users/'+user['id']).status_code == 204
    assert reviewer.get('/api/session').json()['role'] == 'public'
    assert reviewer.post(f'/api/books/{BOOK_ID}/comments',json={'scope':'book','body':'No.'}).status_code == 401
    assert reviewer.post('/api/session',json={'username':'bob','password':PASSWORD}).status_code == 403
    assert client.app.state.reviews.get(note['id'])['body'] == 'Keep this note.'
    replacement = add_user(client)
    assert replacement['id'] != user['id']
    assert reviewer.get('/api/session').json()['role'] == 'public'


def test_last_admin_and_self_deletion_are_blocked(client):
    current = sign_in(client, ADMIN_PASSWORD)
    assert client.delete('/api/users/'+current['user_id']).status_code == 409
    other = add_user(client, username='second-admin', role='admin')
    assert client.delete('/api/users/'+current['user_id']).status_code == 409
    assert client.delete('/api/users/'+other['id']).status_code == 204


@pytest.mark.parametrize('override', [
    {'username':'a'}, {'username':'a/b'}, {'username':None}, {'password':'short'},
    {'password':'x'*129}, {'password':123}, {'role':'superuser'}, {'role':[]},
    {'display_name':'x'*65}, {'display_name': ['bad']}, {'display_name':'bad\nname'},
])
def test_invalid_account_input_is_rejected(client, override):
    sign_in(client, ADMIN_PASSWORD)
    payload = {'username':'new-user','password':PASSWORD, **override}
    assert client.post('/api/users',json=payload).status_code == 400


def test_duplicate_username_is_case_insensitive(client):
    sign_in(client, ADMIN_PASSWORD)
    add_user(client)
    assert client.post('/api/users',json={'username':'BOB','password':PASSWORD}).status_code == 400


def test_password_change_revokes_other_sessions_and_rejects_old_password(client):
    sign_in(client)
    another = TestClient(client.app)
    sign_in(another)
    old_cookie = client.cookies.get(COOKIE_NAME)
    assert client.put('/api/account/password', json={'current_password':'wrong','new_password':PASSWORD}).status_code == 400
    assert client.put('/api/account/password', json={'current_password':REVIEW_PASSWORD,'new_password':PASSWORD}).status_code == 200
    assert client.cookies.get(COOKIE_NAME) != old_cookie
    assert client.get('/api/session').json()['username'] == 'alice'
    assert another.get('/api/session').json()['role'] == 'public'
    assert another.post('/api/session',json={'username':'alice','password':REVIEW_PASSWORD}).status_code == 403
    assert another.post('/api/session',json={'username':'alice','password':PASSWORD}).status_code == 200


def test_logout_invalidates_copied_session(client):
    sign_in(client)
    cookie = client.cookies.get(COOKIE_NAME)
    assert client.delete('/api/session').status_code == 200
    assert client.get('/api/session', headers={'Cookie':f'{COOKIE_NAME}={cookie}'}).json()['role'] == 'public'


def test_unknown_credentials_and_legacy_login_are_rejected(client, monkeypatch):
    monkeypatch.setenv('FORAGE_ADMIN_TOKEN', 'legacy-shared-token')
    unknown = client.post('/api/session',json={'username':'missing','password':PASSWORD})
    wrong = client.post('/api/session',json={'username':'alice','password':'wrong'})
    assert unknown.status_code == wrong.status_code == 403
    assert unknown.json() == wrong.json()
    assert client.post('/api/session',json={'token':'legacy-shared-token','label':'Admin'}).status_code == 403
    assert client.get('/api/session',headers={'Cookie':f'{COOKIE_NAME}=v1.admin.9999999999.0..anything'}).json()['role'] == 'public'


def test_session_expiry_epoch_tampering_and_persistence(client):
    sign_in(client)
    cookie = client.cookies.get(COOKIE_NAME)
    store = AccountStore(client.app.state.accounts.db_path)
    config = client.app.state.auth
    assert store.verify(cookie, config).username == 'alice'
    assert store.verify(cookie, replace(config, epoch='rotated')).role == 'public'
    assert store.verify(cookie[:-1] + ('0' if cookie[-1]!='0' else '1'), config).role == 'public'
    with store.connect() as conn:
        conn.execute('UPDATE user_sessions SET expires_at=0')
    assert store.verify(cookie, config).role == 'public'


def test_login_lockout_and_cookie_security(make_client):
    client = make_client(trust_proxy=True)
    for _ in range(8):
        assert client.post('/api/session',json={'username':'alice','password':'wrong'}).status_code == 403
    assert client.post('/api/session',json={'username':'alice','password':REVIEW_PASSWORD}).status_code == 429
    response = client.post('/api/session', json={'username':'alice','password':REVIEW_PASSWORD},
                           headers={'x-forwarded-for':'203.0.113.3', 'x-forwarded-proto':'https'})
    assert response.status_code == 429  # An account budget survives IP changes.
    response = client.post('/api/session', json={'username':'admin','password':ADMIN_PASSWORD},
                           headers={'x-forwarded-for':'203.0.113.3', 'x-forwarded-proto':'https'})
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    assert response.headers['cache-control'] == 'no-store'


def test_bootstrap_is_one_time_and_requires_credentials_in_production(tmp_path, monkeypatch):
    store = AccountStore(tmp_path/'review.db')
    with pytest.raises(AuthConfigError):
        store.bootstrap(production=True)
    monkeypatch.setenv('FORAGE_BOOTSTRAP_ADMIN_USERNAME','admin')
    monkeypatch.setenv('FORAGE_BOOTSTRAP_ADMIN_PASSWORD',PASSWORD)
    store.bootstrap(production=True)
    assert len(store.list_users()) == 1
    config=AuthConfig()
    session, _ = store.login('admin', PASSWORD, config)
    new_password = 'new private passphrase'
    store.change_password(session.user_id, PASSWORD, new_password, config)
    store.bootstrap(production=True)
    assert store.login('admin',PASSWORD,config) is None
    assert store.login('admin',new_password,config)[0].can_admin
    monkeypatch.delenv('FORAGE_BOOTSTRAP_ADMIN_PASSWORD')
    store.bootstrap(production=True)


def test_concurrent_first_admin_creation_is_atomic(tmp_path):
    store = AccountStore(tmp_path/'review.db')
    def create(index):
        return store.create_user(f'admin{index}', PASSWORD, role='admin', first_only=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        created=list(pool.map(create,range(2)))
    assert sum(bool(u) for u in created) == 1
    assert len(store.list_users()) == 1


def test_deleted_admin_cannot_complete_a_late_account_mutation(client):
    sign_in(client, ADMIN_PASSWORD)
    user=add_user(client,'other-admin','admin')
    assert client.delete('/api/users/'+user['id']).status_code == 204
    with pytest.raises(PermissionError):
        client.app.state.accounts.create_user('late-user',PASSWORD,actor_id=user['id'])
