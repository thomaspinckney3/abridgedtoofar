"""Provider-free identities and feedback rules for reviewing an LLM revision."""
from __future__ import annotations

import hashlib
import json

from .review_anchors import chapter_hash


def response_id(entry: dict) -> str:
    identity = {key: entry.get(key) for key in (
        'comment_id', 'source_id', 'segment_id', 'run_id', 'feedback_key',
        'used_at', 'draft_after_hash', 'action', 'reason')}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_responses(ledger: dict) -> dict:
    """Publish decision history without copying private editorial artifacts."""
    keys = {'comment_id', 'source_id', 'segment_id', 'run_id', 'feedback_key',
            'used_at', 'draft_after_hash', 'action', 'reason', 'changed_paragraphs',
            'draft_changed', 'comment_binding', 'model', 'review_request_id'}
    return {'version': 1, 'entries': [{k: v for k, v in entry.items() if k in keys}
            for entry in ledger.get('entries', []) if isinstance(entry, dict)]}


def actionable(comment: dict) -> bool:
    review = comment.get('revision_review')
    return not review or (review.get('state') == 'rejected' and review.get('current') is True)


def request_for(comment: dict) -> dict | None:
    review = comment.get('revision_review') or {}
    return review.get('request') if review.get('state') == 'rejected' else None


def request_matches(request: dict, segment_id: str, paragraphs: list[str]) -> bool:
    return (isinstance(request, dict) and isinstance(request.get('id'), str)
            and bool(request['id']) and isinstance(request.get('body'), str)
            and bool(request['body'].strip()) and request.get('segment_id') == segment_id
            and request.get('chapter_anchor') == chapter_hash(paragraphs))
