"""Persistent accounts and revocable sessions in the review database.

Uses stdlib scrypt (N=2**15, r=8, p=3), an OWASP-recommended 32 MiB profile.
Only salted password hashes and hashes of random 256-bit session IDs are stored.
Account mutations and session issuance recheck identity inside transactions.
"""
from __future__ import annotations

from contextlib import contextmanager
import getpass
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
import uuid

from .auth import ADMIN, REVIEWER, AuthConfigError, Session

MIN_PASSWORD = 15
MAX_PASSWORD = 128
_USERNAME = re.compile(r"[a-z0-9][a-z0-9_.@-]{2,63}\Z")
_COOKIE = re.compile(r"u2\.[0-9a-f]{64}\Z")
# Bound expensive hashing across concurrent HTTP workers in this process.
_HASH_SLOTS = threading.BoundedSemaphore(2)


def username_key(username):
    if not isinstance(username, str) or not _USERNAME.fullmatch(username.strip().lower()):
        raise ValueError("Username must be 3–64 letters, numbers, dots, @, hyphens or underscores.")
    return username.strip().lower()


def validate_password(password):
    if not isinstance(password, str) or not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise ValueError(f"Password must be {MIN_PASSWORD}–{MAX_PASSWORD} characters.")
    try:
        password.encode('utf-8')
    except UnicodeError:
        raise ValueError('Password must contain valid Unicode characters.') from None


def _derive(password, salt):
    with _HASH_SLOTS:
        return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**15, r=8, p=3,
                              maxmem=64 * 1024 * 1024, dklen=32)


def hash_password(password):
    validate_password(password)
    salt = secrets.token_bytes(16)
    return f"scrypt-32768-8-3${salt.hex()}${_derive(password, salt).hex()}"


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > MAX_PASSWORD:
        return False
    try:
        algorithm, salt, expected = encoded.split('$')
        if algorithm != 'scrypt-32768-8-3' or len(salt) != 32 or len(expected) != 64:
            return False
        return hmac.compare_digest(_derive(password, bytes.fromhex(salt)), bytes.fromhex(expected))
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return False


_DUMMY_HASH = 'scrypt-32768-8-3$' + '00' * 16 + '$' + '00' * 32


def _public(row):
    return {key: row[key] for key in ('id', 'username', 'display_name', 'role', 'created_at')}


def _session(row):
    return Session(role=row['role'], label=row['display_name'], user_id=row['id'],
                   username=row['username'])


class AccountStore:
    def __init__(self, db_path: Path):
        from .store import mutable_path
        self.db_path = mutable_path(Path(db_path))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('reviewer', 'admin')),
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at REAL NOT NULL,
                    epoch TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user ON user_sessions(user_id);
            ''')

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def list_users(self):
        with self.connect() as conn:
            return [_public(row) for row in conn.execute('SELECT * FROM users ORDER BY username')]

    def bootstrap(self, production=False):
        # Bootstrap is one-time initialization, never an environment-password
        # override of an existing user's password or a resurrection mechanism.
        if self.list_users():
            return
        username = os.environ.get('FORAGE_BOOTSTRAP_ADMIN_USERNAME')
        password = os.environ.get('FORAGE_BOOTSTRAP_ADMIN_PASSWORD')
        if username and password:
            self.create_user(username, password, role=ADMIN, first_only=True)
        elif production or username or password:
            raise AuthConfigError('No accounts exist. Set FORAGE_BOOTSTRAP_ADMIN_USERNAME and '
                                  'FORAGE_BOOTSTRAP_ADMIN_PASSWORD for first startup, or run '
                                  'python -m forage.webapp.accounts create-admin USERNAME.')

    def create_user(self, username, password, *, display_name=None, role=REVIEWER,
                    first_only=False, actor_id=None):
        username = username_key(username)
        display_name = username if display_name is None or display_name == '' else display_name
        if (not isinstance(display_name, str) or not display_name.strip()
                or len(display_name) > 64 or any(ord(c) < 32 for c in display_name)):
            raise ValueError('Display name must be 1–64 printable characters.')
        if role not in (REVIEWER, ADMIN):
            raise ValueError('Role must be reviewer or admin.')
        encoded = hash_password(password)
        row = dict(id=uuid.uuid4().hex, username=username, display_name=display_name.strip(),
                   role=role, password_hash=encoded, created_at=time.time())
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if actor_id is not None:
                self._require_admin(conn, actor_id)
            if first_only and conn.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                return None
            try:
                conn.execute('INSERT INTO users VALUES (:id,:username,:display_name,:role,:password_hash,:created_at)', row)
            except sqlite3.IntegrityError:
                raise ValueError('That username already exists.') from None
        return _public(row)

    @staticmethod
    def _require_admin(conn, actor_id):
        row = conn.execute('SELECT role FROM users WHERE id=?', (actor_id,)).fetchone()
        if not row or row['role'] != ADMIN:
            raise PermissionError('An administrator account is required.')

    def delete_user(self, user_id, *, actor_id):
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._require_admin(conn, actor_id)
            row = conn.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
            if not row:
                raise KeyError('Account not found.')
            if row['role'] == ADMIN and conn.execute("SELECT count(*) FROM users WHERE role='admin'").fetchone()[0] <= 1:
                raise ValueError('The last administrator account cannot be removed.')
            if user_id == actor_id:
                raise ValueError('You cannot remove your own account.')
            conn.execute('DELETE FROM users WHERE id=?', (user_id,))

    def _issue(self, conn, user_id, config):
        cookie = 'u2.' + secrets.token_hex(32)
        conn.execute('DELETE FROM user_sessions WHERE expires_at <= ? OR epoch != ?',
                     (time.time(), config.epoch))
        conn.execute('INSERT INTO user_sessions VALUES (?,?,?,?)',
                     (hashlib.sha256(cookie.encode()).hexdigest(), user_id,
                      time.time() + config.session_seconds, config.epoch))
        return cookie

    def login(self, username, password, config):
        try:
            username = username_key(username)
        except ValueError:
            username = ''
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        valid = verify_password(password, row['password_hash'] if row else _DUMMY_HASH)
        if not row or not valid:
            return None
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT * FROM users WHERE id=? AND password_hash=?',
                                   (row['id'], row['password_hash'])).fetchone()
            if not current:
                return None
            return _session(current), self._issue(conn, current['id'], config)

    def verify(self, cookie, config):
        if not isinstance(cookie, str) or not _COOKIE.fullmatch(cookie):
            return Session()
        with self.connect() as conn:
            row = conn.execute('''SELECT u.* FROM users u JOIN user_sessions s ON u.id=s.user_id
                WHERE s.session_hash=? AND s.expires_at>? AND s.epoch=?''',
                (hashlib.sha256(cookie.encode()).hexdigest(), time.time(), config.epoch)).fetchone()
        return _session(row) if row else Session()

    def logout(self, cookie):
        if isinstance(cookie, str) and _COOKIE.fullmatch(cookie):
            with self.connect() as conn:
                conn.execute('DELETE FROM user_sessions WHERE session_hash=?',
                             (hashlib.sha256(cookie.encode()).hexdigest(),))

    def change_password(self, user_id, current_password, new_password, config):
        validate_password(new_password)
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row or not verify_password(current_password, row['password_hash']):
            raise ValueError('Current password is incorrect.')
        encoded = hash_password(new_password)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            changed = conn.execute('UPDATE users SET password_hash=? WHERE id=? AND password_hash=?',
                                   (encoded, user_id, row['password_hash'])).rowcount
            if not changed:
                raise ValueError('Account changed. Sign in again.')
            conn.execute('DELETE FROM user_sessions WHERE user_id=?', (user_id,))
            return self._issue(conn, user_id, config)


def main():
    import argparse
    from .store import ReviewStore
    parser = argparse.ArgumentParser(description='Create the first administrator using a hidden password prompt.')
    parser.add_argument('command', choices=['create-admin'])
    parser.add_argument('username')
    args = parser.parse_args()
    password = getpass.getpass('Password (15–128 characters): ')
    if password != getpass.getpass('Confirm password: '):
        parser.error('Passwords do not match.')
    try:
        account = AccountStore(ReviewStore().db_path).create_user(args.username, password, role=ADMIN, first_only=True)
        if account is None:
            parser.error('Accounts already exist. Sign in as an administrator to manage users.')
    except ValueError as exc:
        parser.error(str(exc))
    print('Administrator created.')


if __name__ == '__main__':
    main()
