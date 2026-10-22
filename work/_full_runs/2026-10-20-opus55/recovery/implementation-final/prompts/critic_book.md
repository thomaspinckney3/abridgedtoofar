---
model: anthropic:claude-sonnet-5-5
max_tokens: 8000
---
You verify that an abridgment of a book preserves each plot claim from the book's authoritative synopsis.

Inputs:
1. The **synopsis**: {{sentences|length}} sentences of ground truth about the book's plot, principal characters, and themes.
2. The **abridgment**: the candidate shortened version.

For each synopsis sentence, report one of:

- **`present`** — the abridgment covers this plot beat with the right character(s), event, and outcome.
- **`missing`** — no passage of the abridgment speaks to this claim.
- **`distorted`** — the event is mentioned but with a different outcome, character, or material fact than the synopsis states.

Output a single JSON array in sentence order — no preamble, no markdown fences:

```json
[
  {"sentence": 1, "status": "present", "evidence": "<short quote or paraphrase from the abridgment>", "note": ""},
  {"sentence": 2, "status": "missing", "evidence": "", "note": "no reference to X anywhere"},
  {"sentence": 3, "status": "distorted", "evidence": "<quote>", "note": "abridgment says X; synopsis says Y"}
]
```

Every synopsis sentence must appear exactly once. Be strict about `distorted` — only mark it when the abridgment asserts something materially different from the synopsis, not when it merely omits a detail.{% if partial_note %}

{{partial_note}}{% endif %}

# Synopsis ({{sentences|length}} sentences)

{% for s in sentences %}{{loop.index}}. {{s}}
{% endfor %}

# Abridgment

{{abridgment}}
