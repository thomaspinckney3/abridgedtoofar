"""Contribution licenses require current, explicit, authenticated assent."""
import pytest

from forage.webapp.accounts import AccountStore, CONTRIBUTION_TERMS_VERSION
from .conftest import BOOK_ID, ADMIN_PASSWORD, sign_in, accept_contribution_terms

ENDPOINT = '/api/account/contribution-terms'


def test_public_terms_and_links(client):
    for path in ('/', '/b/testbook', '/release/testbook', '/read', '/read/testbook'):
        response = client.get(path)
        assert response.status_code == 200
        assert 'href="/terms">Terms of Use</a>' in response.text
    response = client.get('/terms')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-cache'
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert f'datetime="{CONTRIBUTION_TERMS_VERSION}"' in response.text
    for content in ('CC BY 4.0', 'copyright license', 'commercial', 'irrevocable',
                    'retain ownership', 'Acceptable use policy', 'not retroactively',
                    'adds no restrictions', 'href="/read"', 'href="/"'):
        assert content in response.text
    assert '<script' not in response.text
    assert not client.get('/api/session').json()['contribution_terms']['accepted']


@pytest.mark.parametrize('password', [None, ADMIN_PASSWORD])
def test_every_contribution_route_requires_assent_for_reviewers_and_admins(client, password):
    options = {'password': password} if password else {}
    session = sign_in(client, accept_terms=False, **options)
    assert session['contribution_terms']['accepted_at'] is None
    for method, path, payload in (
        ('post', f'/api/books/{BOOK_ID}/comments', {'scope': 'book', 'body': 'A note'}),
        ('post', f'/api/books/{BOOK_ID}/comments', {'scope': 'audio', 'body': 'A note'}),
        ('post', f'/api/books/{BOOK_ID}/comments', {'scope': 'graphic', 'body': 'A note'}),
        ('patch', '/api/comments/missing', {'body': 'An edit'}),
        ('post', '/api/comments/missing/revision-review', {'action': 'rejected', 'body': 'More work'}),
    ):
        response = getattr(client, method)(path, json=payload)
        assert response.status_code == 428, response.text
        assert '/terms' in response.json()['detail']
    assert client.get(f'/api/books/{BOOK_ID}/comments').json()['comments'] == []
    accept_contribution_terms(client)
    note = client.post(f'/api/books/{BOOK_ID}/comments', json={'scope': 'book', 'body': 'A note'})
    assert note.status_code == 201
    assert client.patch('/api/comments/' + note.json()['id'], json={'body': 'An edit'}).status_code == 200


@pytest.mark.parametrize('accepted', [None, False, 1, 'true', [], {}])
def test_consent_cannot_be_implied_or_coerced(client, accepted):
    sign_in(client, accept_terms=False)
    assert client.post(ENDPOINT, json={'version': CONTRIBUTION_TERMS_VERSION,
                                       'accepted': accepted}).status_code == 400
    assert not client.get('/api/session').json()['contribution_terms']['accepted']


def test_consent_is_authenticated_current_version_and_same_origin(client):
    payload = {'version': CONTRIBUTION_TERMS_VERSION, 'accepted': True}
    assert client.post(ENDPOINT, json=payload).status_code == 401
    sign_in(client, accept_terms=False)
    assert client.post(ENDPOINT, json=payload, headers={'Origin': 'https://elsewhere.example'}).status_code == 403
    for version in (None, '', 'old-version', [CONTRIBUTION_TERMS_VERSION]):
        assert client.post(ENDPOINT, json={**payload, 'version': version}).status_code == 409
    assert not client.get('/api/session').json()['contribution_terms']['accepted']
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'


def test_receipt_is_idempotent_persistent_and_specific_to_account_and_version(client):
    alice = sign_in(client, accept_terms=False)
    first = accept_contribution_terms(client)
    assert first['accepted'] and first['accepted_at'] > 0
    assert accept_contribution_terms(client) == first
    store = AccountStore(client.app.state.accounts.db_path)
    assert store.terms_status(alice['user_id']) == first
    # An administrator cannot accept for another account by forging user_id.
    admin = sign_in(client, ADMIN_PASSWORD, accept_terms=False)
    with store.connect() as conn:
        conn.execute('DELETE FROM contribution_terms_acceptances WHERE user_id=?', (alice['user_id'],))
    response = client.post(ENDPOINT, json={'version': CONTRIBUTION_TERMS_VERSION,
                                         'accepted': True, 'user_id': alice['user_id']})
    assert response.status_code == 200
    assert not store.terms_status(alice['user_id'])['accepted']
    assert store.terms_status(admin['user_id'])['accepted']
    with store.connect() as conn:
        conn.execute('UPDATE contribution_terms_acceptances SET version=?', ('old-version',))
    assert not store.terms_status(admin['user_id'])['accepted']
    assert client.post(f'/api/books/{BOOK_ID}/comments', json={'scope': 'book', 'body': 'No'}).status_code == 428
    accept_contribution_terms(client)
    with store.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM contribution_terms_acceptances').fetchone()[0] == 2


def test_legacy_notes_deletion_and_account_management_do_not_imply_consent(client):
    # Model a pre-terms account and review without changing any existing note.
    alice = sign_in(client)
    note = client.post(f'/api/books/{BOOK_ID}/comments', json={'scope': 'book', 'body': 'Existing note'}).json()
    store = client.app.state.accounts
    with store.connect() as conn:
        conn.execute('DELETE FROM contribution_terms_acceptances')
    assert client.get(f'/api/books/{BOOK_ID}/comments').json()['comments'][0]['body'] == 'Existing note'
    assert client.patch('/api/comments/' + note['id'], json={'body': 'Unlicensed edit'}).status_code == 428
    assert client.delete('/api/comments/' + note['id']).status_code == 200
    receipt = accept_contribution_terms(client)
    sign_in(client, ADMIN_PASSWORD, accept_terms=False)
    assert client.get('/api/users').status_code == 200
    assert client.delete('/api/users/' + alice['user_id']).status_code == 204
    assert store.terms_status(alice['user_id']) == receipt
    # Reusing a username never inherits acceptance from a removed account.
    replacement = client.post('/api/users', json={'username': 'alice', 'password': 'a replacement password'}).json()
    assert replacement['id'] != alice['user_id']
    assert not store.terms_status(replacement['id'])['accepted']
