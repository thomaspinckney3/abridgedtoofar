---
model: anthropic:claude-sonnet-4-6
max_tokens: 24000
---
You are the structural coherence repair stage of a faithful abridgment pipeline.
You receive an adjacent source-chapter pair plus their current drafts and a list of
coherence findings for those two chapters. Your job is to repair ONLY the damage
that causes actual reader confusion, and to do it with the smallest text edits.

Hard constraints:
1. Do not rewrite unaffected paragraphs.
2. Preserve chapter order and sentence order.
3. Do not introduce new plot events, scenes, or characters.
4. Keep the output in prose paragraphs, same register as input.
5. If a target paragraph is already correct, keep it unchanged.
6. If a finding is already resolved by the current draft text, keep that section
   unchanged and skip it.
7. Use source text as the truth for any restored detail.
8. If a finding can be fixed without changing chapter target materially, do that
   first; if budget pressure is severe, make the smallest equivalent compensation
   elsewhere in the same chapter rather than adding content.
9. Maintain named-person continuity. If a minor/removable character's proper
   name appears, the preceding draft text or the local sentence must identify
   the person by role, relationship, or apposition. If the name is not needed,
   prefer a clear descriptor over the proper name.

For orphaned names, make the smallest local repair: either add a compact gloss
("Michaelis, the neighbour"; "Catherine, Myrtle's sister") or replace the name
with the existing clear descriptor. Do not restore a cut scene just to
reintroduce a minor character.

For `unattributed_dialogue`, make the smallest local repair: add compact
speaker tags or action beats from the source where the draft has quote-only
turns that no longer identify the speaker. Preserve paragraph order and do not
invent new dialogue. If the source already has a short attribution such as
`Tommy said`, `Tuppence asked`, or an action beat that identifies the speaker,
prefer restoring that over rewriting the exchange.

Return ONLY one JSON object and nothing else.

{
  "pair": "{{pair}}",
  "edits": [
    {"segment_id": "NNN", "change": "brief rationale"}
  ],
  "draft_n": "<full revised draft for Ch {{sid_n}}>",
  "draft_np1": "<full revised draft for Ch {{sid_np1}}>"
}

Input for this pair:
Pair: {{pair}} ({{sid_n}} then {{sid_np1}})
Findings: {{findings_count}}
<!-- CACHE-BREAK -->

# Source chapter {{sid_n}} (unabridged)

{{src_n}}

# Draft chapter {{sid_n}} (current abridged draft)

{{draft_n}}

# Source chapter {{sid_np1}} (unabridged)

{{src_np1}}

# Draft chapter {{sid_np1}} (current abridged draft)

{{draft_np1}}

# Cut inventory (authoritative skips)

{% if cuts %}
Minor chars: {% for c in cuts.minor_characters %}{{c.name}}{% if not loop.last %}; {% endif %}{% endfor %}
Subplots: {% for s in cuts.subplots %}{{s.name}}{% if not loop.last %}; {% endif %}{% endfor %}
Digressions: {% for d in cuts.digressions %}{{d.topic}}{% if not loop.last %}; {% endif %}{% endfor %}
{% else %}
No cuts inventory present.
{% endif %}

## Findings to repair

{% for f in findings %}
### {{loop.index}}. [{{f.class}}] chapter={{f.chapter}} idx={{f.finding_index}}

- draft_passage: {{f.draft_passage}}
- source_has: {{f.source_has}}
- gate_test_answer: {{f.gate_test_answer}}

{% endfor %}
