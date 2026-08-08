"""Book and segment ids become path components, so validation is the only
thing standing between a URL and the filesystem."""

from __future__ import annotations

import pytest

from forage.webapp.store import valid_book_id, valid_segment_id

from .conftest import BOOK_ID, SEGMENT_ID

VALIDATORS = (valid_book_id, valid_segment_id)


@pytest.mark.parametrize("validator", VALIDATORS)
@pytest.mark.parametrize("value", [".", ".."])
def test_dot_segments_are_rejected(validator, value):
    """The character class admits these on its own: both are made entirely of
    permitted characters. A bare dot-segment resolves outside the directory it
    is supposed to name."""
    assert validator(value) is False


@pytest.mark.parametrize("validator", VALIDATORS)
@pytest.mark.parametrize("value", [
    "", "../etc", "a/b", "a\\b", "a b", "x" * 65, "café", "a\x00b", "a\nb",
])
def test_malformed_ids_are_rejected(validator, value):
    assert validator(value) is False


@pytest.mark.parametrize("validator", VALIDATORS)
@pytest.mark.parametrize("value", [
    "gatsby", "a.b-c_d", "001", "...", "x" * 64, "-leading-dash",
])
def test_ordinary_ids_are_accepted(validator, value):
    """Including "..." — three dots is a legal directory name, not a traversal.
    Over-tightening here would break real book ids."""
    assert validator(value) is True


def test_traversal_id_does_not_reach_the_filesystem(client):
    """End to end: the route rejects it rather than relying on the layout
    happening to have nothing one level up."""
    for value in (".", "..", "%2e%2e"):
        assert client.get(f"/api/books/{value}/chapters").status_code == 404


def test_known_book_still_resolves(client):
    response = client.get(f"/api/books/{BOOK_ID}/chapters")
    assert response.status_code == 200
    assert [c["segment_id"] for c in response.json()["chapters"]] == [SEGMENT_ID]
