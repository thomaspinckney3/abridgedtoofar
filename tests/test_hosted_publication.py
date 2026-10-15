import io
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from forage import publication
from forage.hosted_publication import HostedPublications, archive_snapshot
from forage.production_state import inventory
from tests.test_publication import publication_input


def mutated(payload, *, name=None, kind=None, duplicate=False, extra=False, corrupt=False):
    stream = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as source, tarfile.open(fileobj=stream, mode="w:gz") as target:
        for index, member in enumerate(source):
            data = source.extractfile(member).read()
            if index == 1:
                if name:
                    member.name = name
                if kind:
                    member.type = kind
                    member.linkname = "../../escape"
                    data = b""
                    member.size = 0
                if corrupt:
                    data = b"X" * len(data)
            target.addfile(member, io.BytesIO(data))
            if duplicate and index == 1:
                target.addfile(member, io.BytesIO(data))
        if extra:
            member = tarfile.TarInfo("extra.txt")
            member.size = 1
            target.addfile(member, io.BytesIO(b"x"))
    return stream.getvalue()


def test_upload_verify_explicit_channels_and_history(publication_input, tmp_path):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    hosted = HostedPublications(tmp_path / "hosted")
    assert not hosted.root.exists()
    assert hosted.book_ids() == []
    assert hosted.status(book.book_id) == {"review": None, "release": None}
    assert not hosted.root.exists()
    archive = archive_snapshot(book, first["revision"])
    hosted.upload(book.book_id, archive)
    assert hosted.status(book.book_id)["review"] is None
    review = hosted.promote(book.book_id, first["revision"])
    release = hosted.promote(book.book_id, first["revision"], "release")
    hosted.upload(book.book_id, archive)
    assert hosted.promote(book.book_id, first["revision"]) == review
    (book.work_dir / "abridgment.txt").write_text("Second abridgment.")
    kwargs["outputs"] = inventory(book.work_dir, [x["path"] for x in kwargs["outputs"]])
    second = publication.snapshot_revision(book, **kwargs)
    hosted.upload(book.book_id, archive_snapshot(book, second["revision"]))
    hosted.promote(book.book_id, second["revision"])
    assert hosted.status(book.book_id)["release"] == release
    assert len(hosted.status(book.book_id)["review"]["history"]) == 2
    root, manifest = hosted.resolve(book.book_id, channel="release")
    assert manifest["revision"] == first["revision"]
    assert (root / "abridgment.txt").read_text() == "An abridged book."
    assert hosted.book_ids() == [book.book_id]


@pytest.mark.parametrize("change", [
    {"name": "../escape"}, {"name": "/absolute"}, {"name": "a/../../escape"},
    {"name": "a\\escape"}, {"name": "a//escape"}, {"name": "C:/escape"},
    {"kind": tarfile.SYMTYPE}, {"kind": tarfile.LNKTYPE}, {"kind": tarfile.FIFOTYPE},
    {"kind": tarfile.CHRTYPE}, {"kind": tarfile.DIRTYPE}, {"duplicate": True},
    {"extra": True}, {"corrupt": True},
])
def test_bad_archives_preserve_pointer(publication_input, tmp_path, change):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    hosted = HostedPublications(tmp_path / "hosted")
    archive = archive_snapshot(book, revision)
    hosted.upload(book.book_id, archive)
    old = hosted.promote(book.book_id, revision)
    with pytest.raises(ValueError):
        hosted.upload(book.book_id, mutated(archive, **change))
    assert hosted.status(book.book_id)["review"] == old
    assert not list((hosted.root / book.book_id).glob(".upload-*"))


@pytest.mark.parametrize("limits", [
    {"max_archive_bytes": 1}, {"max_expanded_bytes": 20}, {"max_files": 1},
])
def test_archive_limits(publication_input, tmp_path, limits):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    hosted = HostedPublications(tmp_path / "hosted", **limits)
    with pytest.raises(ValueError):
        hosted.upload(book.book_id, archive_snapshot(book, revision))
    assert hosted.status(book.book_id)["review"] is None


def test_wrong_book_corruption_and_atomic_pointer_failure(publication_input, tmp_path, monkeypatch):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    archive = archive_snapshot(book, revision)
    hosted = HostedPublications(tmp_path / "hosted")
    with pytest.raises(ValueError, match="identity"):
        hosted.upload("another", archive)
    hosted.upload(book.book_id, archive)
    old = hosted.promote(book.book_id, revision)
    def fail(*args, **kwargs):
        raise OSError("simulated disk full")
    monkeypatch.setattr(publication, "atomic_json", fail)
    with pytest.raises(OSError):
        hosted.promote(book.book_id, revision, "release")
    assert hosted.status(book.book_id) == {"review": old, "release": None}
    root, _ = hosted.resolve(book.book_id)
    (root / "abridgment.txt").write_text("corruption")
    with pytest.raises(ValueError):
        hosted.resolve(book.book_id)


@pytest.mark.parametrize("book_id", ["../x", "x/y", "", ".hidden", "a\\b", "x" * 65, "x" * 129])
def test_invalid_books_rejected(tmp_path, book_id):
    with pytest.raises(ValueError):
        HostedPublications(tmp_path).upload(book_id, b"nonsense")


def test_symlink_book_storage_rejected(publication_input, tmp_path):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    root = tmp_path / "hosted"
    root.mkdir()
    (root / book.book_id).symlink_to(book.work_dir, target_is_directory=True)
    with pytest.raises(ValueError):
        HostedPublications(root).upload(book.book_id, archive_snapshot(book, revision))


def test_concurrent_duplicate_upload_stays_verified(publication_input, tmp_path):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    archive = archive_snapshot(book, revision)
    hosted = HostedPublications(tmp_path / "hosted")
    def upload():
        try:
            return hosted.upload(book.book_id, archive)["revision"]
        except RuntimeError:
            return "locked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: upload(), range(2)))
    assert revision in outcomes
    assert set(outcomes) <= {revision, "locked"}
    assert hosted.resolve(book.book_id, revision)[1]["revision"] == revision


def _expanded_metadata(archive, kind):
    import gzip
    if kind == 'trailing-tar':
        return gzip.compress(gzip.decompress(archive) + b'\0' * 65536)
    if kind == 'concatenated-gzip':
        return archive + gzip.compress(b'x' * 65536)
    output = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as source, \
         tarfile.open(fileobj=output, mode='w:gz', format=tarfile.PAX_FORMAT) as target:
        for index, member in enumerate(source):
            body = source.extractfile(member).read()
            if index == 0:
                if kind == 'pax':
                    member.pax_headers['comment'] = 'x' * 65536
                else:
                    extension = tarfile.TarInfo('././@LongLink')
                    extension.type = tarfile.GNUTYPE_LONGNAME
                    content = b'x' * 65536 + b'\0'
                    extension.size = len(content)
                    target.addfile(extension, io.BytesIO(content))
            target.addfile(member, io.BytesIO(body))
    return output.getvalue()


@pytest.mark.parametrize('kind', ['pax', 'gnu', 'trailing-tar', 'concatenated-gzip'])
def test_total_expansion_includes_tar_metadata_and_trailing_streams(publication_input, tmp_path, kind):
    import gzip
    book, options = publication_input
    revision = publication.snapshot_revision(book, **options)['revision']
    original = archive_snapshot(book, revision)
    normal_size = len(gzip.decompress(original))
    host = HostedPublications(tmp_path / 'host', max_expanded_bytes=normal_size)
    host.upload(book.book_id, original)
    pointer = host.promote(book.book_id, revision)
    inflated = _expanded_metadata(original, kind)
    assert len(gzip.decompress(inflated)) > normal_size
    with pytest.raises(ValueError, match='expanded stream limit'):
        host.upload(book.book_id, inflated)
    assert host.status(book.book_id)['review'] == pointer
    assert host.resolve(book.book_id)[1]['revision'] == revision
    assert not list((host.root / book.book_id).glob('.upload-*'))


def test_actual_expansion_limit_covers_headers_and_accepts_exact_size(publication_input, tmp_path):
    import gzip
    book, options = publication_input
    revision = publication.snapshot_revision(book, **options)['revision']
    archive = archive_snapshot(book, revision)
    actual_size = len(gzip.decompress(archive))
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        file_bytes = sum(member.size for member in tar)
    assert actual_size > file_bytes + 100
    host = HostedPublications(tmp_path / 'limited', max_expanded_bytes=file_bytes + 100)
    with pytest.raises(ValueError, match='expanded stream limit'):
        host.upload(book.book_id, archive)
    assert not (host.root / book.book_id / 'publications').exists()
    enough = HostedPublications(tmp_path / 'enough', max_expanded_bytes=actual_size)
    assert enough.upload(book.book_id, archive)['revision'] == revision


def test_truncated_gzip_is_rejected_before_snapshot_install(publication_input, tmp_path):
    book, options = publication_input
    revision = publication.snapshot_revision(book, **options)['revision']
    archive = archive_snapshot(book, revision)
    host = HostedPublications(tmp_path / 'host')
    with pytest.raises(ValueError, match='invalid publication archive'):
        host.upload(book.book_id, archive[:-8])
    assert not (host.root / book.book_id / 'publications').exists()


@pytest.mark.parametrize('limit', ['max_archive_bytes', 'max_expanded_bytes', 'max_files'])
@pytest.mark.parametrize('invalid', [0, -1, True, '100'])
def test_invalid_resource_limit_cannot_disable_bounding(tmp_path, limit, invalid):
    with pytest.raises(ValueError, match='positive integers'):
        HostedPublications(tmp_path / 'host', **{limit: invalid})


def test_valid_pax_metadata_is_allowed_with_sufficient_total_limit(publication_input, tmp_path):
    import gzip
    book, options = publication_input
    revision = publication.snapshot_revision(book, **options)['revision']
    archive = _expanded_metadata(archive_snapshot(book, revision), 'pax')
    host = HostedPublications(tmp_path / 'host', max_expanded_bytes=len(gzip.decompress(archive)))
    assert host.upload(book.book_id, archive)['revision'] == revision
    assert host.status(book.book_id)['review'] is None
