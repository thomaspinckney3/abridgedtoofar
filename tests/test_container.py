"""Container behaviour that no in-process test can reach: which uid the server
actually runs as, and whether it survives the volume it will meet in
production.

Opt in — these build the real image and are slow:

    FORAGE_DOCKER_TESTS=1 pytest tests/test_container.py
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from .conftest import docker_available
from .test_publication import publication_input

REPO = Path(__file__).resolve().parent.parent
IMAGE = "forage-review:pytest"

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not docker_available(),
                       reason="set FORAGE_DOCKER_TESTS=1 and start docker"),
]

ENV = [
    "-e", "FORAGE_ENV=production",
    "-e", "FORAGE_BOOTSTRAP_ADMIN_USERNAME=admin",
    "-e", "FORAGE_BOOTSTRAP_ADMIN_PASSWORD=admin-password-for-tests",
]


def test_accounts_and_revocations_survive_restart_without_bootstrap(container):
    name = container()
    _run('docker', 'exec', name, 'python', '-c', '''
import http.cookiejar, json, urllib.request
base='http://127.0.0.1:8000'
def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def request(opener, method, path, payload):
    return json.load(opener.open(urllib.request.Request(base+path,
        data=json.dumps(payload).encode(),method=method,headers={'Content-Type':'application/json'})))
admin=client()
request(admin,'POST','/api/session',{'username':'admin','password':'admin-password-for-tests'})
request(admin,'POST','/api/users',{'username':'reviewer','password':'reviewer-password-for-tests'})
request(admin,'PUT','/api/account/password',{'current_password':'admin-password-for-tests','new_password':'changed-admin-password'})
with open('/data/saved-cookie','w') as stream:
    for handler in admin.handlers:
        if hasattr(handler,'cookiejar'):
            stream.write(next(iter(handler.cookiejar)).value)
''')
    _run('docker', 'rm', '-f', name)
    revived = container('-e', 'FORAGE_BOOTSTRAP_ADMIN_USERNAME=', '-e', 'FORAGE_BOOTSTRAP_ADMIN_PASSWORD=')
    _run('docker', 'exec', revived, 'python', '-c', '''
import http.cookiejar, json, urllib.request, urllib.error
base='http://127.0.0.1:8000'
cookie=open('/data/saved-cookie').read()
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(base+path,headers={'Cookie':'forage_review='+cookie})))
assert get('/api/session')['role']=='admin'
assert len(get('/api/users')['users'])==2
def login(password):
    return urllib.request.urlopen(urllib.request.Request(base+'/api/session',
        data=json.dumps({'username':'admin','password':password}).encode(),headers={'Content-Type':'application/json'}))
try:
    login('admin-password-for-tests')
    raise AssertionError('Bootstrap password was restored')
except urllib.error.HTTPError as response:
    assert response.code==403
assert json.load(login('changed-admin-password'))['role']=='admin'
reviewer=next(u for u in get('/api/users')['users'] if u['username']=='reviewer')
response=urllib.request.urlopen(urllib.request.Request(base+'/api/users/'+reviewer['id'],method='DELETE',headers={'Cookie':'forage_review='+cookie}))
assert response.status==204
''')


def _run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"{' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


@pytest.fixture(scope="module")
def image() -> str:
    _run("docker", "build", "-t", IMAGE, ".")
    return IMAGE


@pytest.fixture
def volume():
    name = f"forage-pytest-{uuid.uuid4().hex[:8]}"
    yield name
    _run("docker", "volume", "rm", "-f", name, check=False)


@pytest.fixture
def container(image, volume):
    """A started container, torn down whatever the test does."""
    names: list[str] = []

    def _start(*extra: str) -> str:
        name = f"forage-pytest-{uuid.uuid4().hex[:8]}"
        names.append(name)
        _run("docker", "run", "-d", "--name", name, "-v", f"{volume}:/data",
             *ENV, *extra, image)
        _wait_ready(name)
        return name

    yield _start
    for name in names:
        _run("docker", "rm", "-f", name, check=False)


def _exec(name: str, command: str, check: bool = True) -> str:
    return _run("docker", "exec", name, "sh", "-c", command, check=check)


def _wait_ready(name: str) -> None:
    """A persistent DB already exists during restart; wait for HTTP readiness."""
    deadline = time.monotonic() + 30
    probe = ("import urllib.request; "
             "print(urllib.request.urlopen('http://127.0.0.1:8000/healthz', "
             "timeout=1).status)")
    while time.monotonic() < deadline:
        if _run("docker", "exec", name, "python", "-c", probe, check=False) == "200":
            return
        time.sleep(0.1)
    logs = _run("docker", "logs", name, check=False)
    raise AssertionError(f"container {name} never became ready:\n{logs}")


def test_the_server_process_does_not_run_as_root(container):
    """The process parsing request bodies from the open internet has no
    business being uid 0, single-tenant VM or not."""
    name = container()
    status = _exec(name, "grep ^Uid: /proc/1/status")
    uid = status.split()[1]
    assert uid != "0", f"PID 1 is running as root: {status}"

    assert "uvicorn" in _exec(name, "tr '\\0' ' ' < /proc/1/cmdline")


def test_the_volume_is_writable_by_the_service_account(container):
    name = container()
    owner = _exec(name, "stat -c '%U' /data")
    assert owner == "forage"
    _exec(name, "su forage -s /bin/sh -c 'touch /data/write-probe'")


def test_baked_review_artifacts_are_readable_by_the_service_account(image):
    _run("docker", "run", "--rm", "--user", "10001", "--entrypoint", "python", image, "-c", """
import os
def fail(error):
    raise error
checked = 0
for root in ('/app/artifacts', '/app/books'):
    for directory, _, files in os.walk(root, onerror=fail):
        for name in files:
            with open(os.path.join(directory, name), 'rb') as stream:
                stream.read(1)
            checked += 1
assert checked > 0, 'Expected packaged review artifacts'
""")


def test_a_root_owned_volume_is_adopted_on_boot(image, volume, container):
    """The upgrade path. The live volume was written by a root-running
    container, so the first boot of this image meets root-owned files and has
    to take ownership rather than crash."""
    name = container()
    _run("docker", "rm", "-f", name)

    _run("docker", "run", "--rm", "--user", "root", "--entrypoint", "sh",
         "-v", f"{volume}:/data", image, "-c", "chown -R root:root /data")
    assert _run("docker", "run", "--rm", "--user", "root", "--entrypoint", "sh",
                "-v", f"{volume}:/data", image, "-c", "stat -c '%U' /data") == "root"

    revived = container()
    assert _exec(revived, "stat -c '%U' /data") == "forage"
    assert _exec(revived, "grep ^Uid: /proc/1/status").split()[1] != "0"


def test_the_database_survives_the_ownership_change(container):
    name = container()
    _run("docker", "exec", name, "python", "-c", """
import sqlite3
with sqlite3.connect('/data/review.db') as connection:
    connection.execute(
        'INSERT INTO comments '
        '(id, book_id, segment_id, draft_para, anchor, quote, severity, kind, '
        'status, body, author, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        ('x', 'b', 's', 0, '', '', 'minor', 'other', 'open', 'body', 'alice', 0, 0))
""")
    _run("docker", "restart", name)
    _wait_ready(name)
    rows = _exec(name, "python -c \"import sqlite3;"
                       "print(sqlite3.connect('/data/review.db')"
                       ".execute('SELECT COUNT(*) FROM comments').fetchone()[0])\"")
    assert rows == "1"


def test_hosted_publication_and_feedback_survive_restart(container, publication_input, tmp_path):
    """Exercise image defaults through HTTP, without injecting a hosted root."""
    from forage.hosted_publication import archive_snapshot
    from forage.publication import snapshot_revision

    book, options = publication_input
    revision = snapshot_revision(book, **options)["revision"]
    archive = tmp_path / "revision.tgz"
    archive.write_bytes(archive_snapshot(book, revision))
    name = container()
    _run("docker", "cp", str(archive), f"{name}:/tmp/revision.tgz")
    result = json.loads(_run("docker", "exec", name, "python", "-c", """
import http.cookiejar, json, os, pathlib, sys, urllib.request
book, revision = sys.argv[1:]
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def post(path, payload, content_type='application/json'):
    request = urllib.request.Request('http://127.0.0.1:8000' + path, data=payload,
                                     headers={'Content-Type': content_type}, method='POST')
    with opener.open(request, timeout=10) as response:
        return response.status, json.load(response)
_, session = post('/api/session', json.dumps({'username':os.environ['FORAGE_BOOTSTRAP_ADMIN_USERNAME'], 'password':os.environ['FORAGE_BOOTSTRAP_ADMIN_PASSWORD']}).encode())
_, terms = post('/api/account/contribution-terms', json.dumps({'version':session['contribution_terms']['version'], 'accepted':True}).encode())
status, upload = post(f'/api/books/{book}/revisions', pathlib.Path('/tmp/revision.tgz').read_bytes(), 'application/gzip')
assert status == 201 and upload['revision'] == revision
_, pointer = post(f'/api/books/{book}/publication', json.dumps({'revision': revision, 'channel': 'review'}).encode())
_, note = post(f'/api/books/{book}/comments', json.dumps({'publication_revision': revision, 'scope': 'book', 'body': 'Persist this review.'}).encode())
print(json.dumps({'pointer': pointer, 'comment': note['id'], 'terms': terms}))
""", book.book_id, revision))
    assert result["pointer"]["revision"] == revision
    _run("docker", "restart", name)
    _wait_ready(name)
    after = json.loads(_run("docker", "exec", name, "python", "-c", """
import json, os, sys, urllib.request
book = sys.argv[1]
def get(suffix):
    with urllib.request.urlopen(f'http://127.0.0.1:8000/api/books/{book}/{suffix}', timeout=10) as response:
        return json.load(response)
result = {'publication': get('publication'), 'feedback': get('feedback')}
reading = get('reading')
assert reading['license']['owner'] == 'Abridged Too Far'
assert reading['license']['short_name'] == 'CC BY 4.0'
with urllib.request.urlopen('http://127.0.0.1:8000' + reading['download_url']) as response:
    assert response.headers['Content-Type'].startswith('text/plain')
    assert 'attachment' in response.headers['Content-Disposition']
    text = response.read().decode('utf-8')
    assert 'An abridged book.' in text and 'including commercially' in text
for path in ('/read/' + book, '/static/reader.js', '/static/reader.css', '/terms'):
    with urllib.request.urlopen('http://127.0.0.1:8000' + path) as response:
        assert response.status == 200
        if path == '/terms':
            assert 'Acceptable use policy' in response.read().decode()
request = urllib.request.Request('http://127.0.0.1:8000/api/session',
    data=json.dumps({'username':os.environ['FORAGE_BOOTSTRAP_ADMIN_USERNAME'],
                     'password':os.environ['FORAGE_BOOTSTRAP_ADMIN_PASSWORD']}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(request) as response:
    result['terms'] = json.load(response)['contribution_terms']
print(json.dumps(result))
""", book.book_id))
    assert after["publication"]["review"]["revision"] == revision
    assert after["publication"]["release"] is None
    assert [note["id"] for note in after["feedback"]["comments"]] == [result["comment"]]
    assert after['terms'] == result['terms']


def test_installed_versions_match_the_pin_file(container):
    """Proves the pins are what actually got installed, not just what the file
    claims — a resolver conflict would otherwise pass the manifest test."""
    name = container()
    frozen = {line.lower() for line in _exec(name, "pip freeze").splitlines()
              if "==" in line}
    pinned = {line.strip().lower()
              for line in (REPO / "requirements-web.txt").read_text().splitlines()
              if line.strip() and not line.strip().startswith("#")}
    missing = pinned - frozen
    assert missing == set(), f"pinned but not installed at these versions: {missing}"


def test_the_schema_endpoints_are_closed_in_the_real_image(container):
    name = container("-p", "0:8000")
    for path in ("/openapi.json", "/docs"):
        code = _exec(name, "python -c \"import urllib.request as u;"
                           "\nimport urllib.error as e"
                           f"\ntry: u.urlopen('http://127.0.0.1:8000{path}')"
                           "\nexcept e.HTTPError as err: print(err.code)\"")
        assert code == "404", f"{path} returned {code}"
