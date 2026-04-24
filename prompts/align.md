---
model: anthropic:claude-sonnet-4-6
max_tokens: 8000
---
You are aligning a faithful book abridgment back to its source for proofreading. Given the numbered paragraphs of the SOURCE chapter and the numbered paragraphs of the DRAFT (abridged) chapter, produce a mapping from each draft paragraph to the source paragraph(s) it derives from.

# Rules

- A draft paragraph usually compresses one or more contiguous source paragraphs. List all source paragraph indices it draws from.
- A draft paragraph may be near-verbatim ("verbatim"), paraphrased with the same content ("paraphrased"), compressed from multiple source paragraphs ("compressed"), or unsupported by this chapter's source ("unsupported" — e.g. bridging sentence, pulled from adjacent chapter, or possible drift).
- If a draft paragraph is clearly a bridging sentence or transition the drafter added (not in source), mark it `unsupported` and leave `source_paras` empty.
- A draft paragraph may match source paragraphs that are not contiguous — that's fine, just list all the indices.
- Do NOT invent source support; if you can't find a clear anchor, mark it unsupported.

# Output

Respond with a single JSON array and nothing else. One object per draft paragraph, in draft order:

```json
[
  {"draft_para": 0, "source_paras": [0, 1], "note": "compressed"},
  {"draft_para": 1, "source_paras": [2], "note": "verbatim"},
  {"draft_para": 2, "source_paras": [], "note": "unsupported — bridging sentence"}
]
```

Note values: `verbatim` | `paraphrased` | `compressed` | `unsupported`.
Optionally add a brief explanatory comment after the note keyword (e.g. `"unsupported — likely pulled from Ch 5"`).

# Source paragraphs

{{source_paragraphs}}

# Draft paragraphs

{{draft_paragraphs}}
