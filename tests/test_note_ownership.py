"""Account identity, rather than an editable display label, owns human notes."""
import pytest

from .conftest import ADMIN_PASSWORD, BOOK_ID, REVIEW_PASSWORD, sign_in
from .test_revision_review import revised, decide
from forage.webapp.store import ReviewStore


def note(client, **extra):
    response = client.post(f'/api/books/{BOOK_ID}/comments',
                           json={'scope': 'book', 'body': 'Original note.', **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_other_reviewer_cannot_mutate_owner_or_admin_notes(client):
    alice = sign_in(client)
    own = note(client, author='spoof', author_user_id='spoof')
    assert own['author_user_id'] == alice['user_id'] and own['author'] == 'alice'
    sign_in(client, ADMIN_PASSWORD)
    admin_note = note(client)
    sign_in(client, label='Bob')
    for row in (own, admin_note):
        url = '/api/comments/' + row['id']
        for payload in ({'body': 'Stolen'}, {'status': 'resolved'}, {}):
            assert client.patch(url, json=payload).status_code == 403
        assert client.delete(url).status_code == 403
        assert client.app.state.reviews.get(row['id'])['body'] == 'Original note.'
    sign_in(client)
    url = '/api/comments/' + own['id']
    changed = client.patch(url, json={'body': 'Mine', 'author': 'spoof', 'author_user_id': 'spoof'})
    assert changed.status_code == 200
    assert changed.json()['author_user_id'] == alice['user_id']
    assert changed.json()['author'] == 'alice'
    assert client.delete(url).status_code == 200
    sign_in(client, ADMIN_PASSWORD)
    assert client.patch('/api/comments/' + admin_note['id'], json={'status': 'resolved'}).status_code == 200


def test_matching_labels_recreated_accounts_and_legacy_notes_cannot_claim_ownership(client):
    alice = sign_in(client)
    original = note(client)
    legacy = note(client)
    with client.app.state.reviews._connect() as conn:
        conn.execute('UPDATE comments SET author_user_id=NULL WHERE id=?', (legacy['id'],))
    assert client.patch('/api/comments/' + legacy['id'], json={'body': 'Claim'}).status_code == 403
    sign_in(client, ADMIN_PASSWORD)
    assert client.delete('/api/users/' + alice['user_id']).status_code == 204
    replacement = client.app.state.accounts.create_user('alice', REVIEW_PASSWORD, display_name='alice')
    assert replacement['id'] != alice['user_id']
    sign_in(client)
    for row in (original, legacy):
        assert client.delete('/api/comments/' + row['id']).status_code == 403
        assert client.patch('/api/comments/' + row['id'], json={'body': 'Claim'}).status_code == 403
    sign_in(client, ADMIN_PASSWORD)
    for row in (original, legacy):
        assert client.patch('/api/comments/' + row['id'], json={'body': 'Admin corrected'}).status_code == 200
        assert client.delete('/api/comments/' + row['id']).status_code == 200


def test_revoked_actor_cannot_complete_a_late_note_mutation(client):
    alice = sign_in(client)
    row = note(client)
    sign_in(client, ADMIN_PASSWORD)
    assert client.delete('/api/users/' + alice['user_id']).status_code == 204
    store = client.app.state.reviews
    with pytest.raises(PermissionError):
        store.update(row['id'], actor_id=alice['user_id'], body='late')
    with pytest.raises(PermissionError):
        store.delete(row['id'], actor_id=alice['user_id'])
    assert store.get(row['id'])['body'] == row['body']


def test_revision_decisions_require_ownership_and_admin_can_manage_all(revised):
    client, _, row = revised
    sign_in(client, label='Bob')
    assert decide(client, row, 'accepted').status_code == 403
    assert client.app.state.reviews.get(row['id'])['revision_reviews'] == []
    sign_in(client, ADMIN_PASSWORD)
    accepted = decide(client, row, 'accepted')
    assert accepted.status_code == 200
    sign_in(client)
    assert decide(client, accepted.json(), 'reopened').status_code == 200


def test_nullable_ownership_upgrade_preserves_legacy_notes(client):
    sign_in(client)
    row = note(client)
    store = client.app.state.reviews
    before = store.get(row['id'])
    with store._connect() as conn:
        conn.execute('ALTER TABLE comments DROP COLUMN author_user_id')
    migrated = ReviewStore(store.db_path).get(row['id'])
    assert migrated['author_user_id'] is None
    for field in ('id', 'body', 'author', 'created_at', 'anchor', 'revision_reviews'):
        assert migrated[field] == before[field]
