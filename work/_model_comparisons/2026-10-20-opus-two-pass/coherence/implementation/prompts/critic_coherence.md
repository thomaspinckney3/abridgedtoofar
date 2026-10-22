---
model: anthropic:claude-sonnet-5-5
max_tokens: 12000
---
You are a coherence critic for an abridgment. You see SOURCE and DRAFT for a pair of consecutive chapters. Find places where compression has *structurally damaged* meaning — not places where the draft is merely less richly phrased than the source.

A finding is valid ONLY if the draft sentence fails at least ONE of these specific tests:

1. **Non-parseable on its own**: the sentence has no main clause, or its main clause's referent is missing from the entire preceding draft.
2. **Dangling pronoun/demonstrative**: "he/she/it/this/that/these" used with no unambiguous antecedent in the preceding draft (not source — draft).
3. **Broken logical pivot**: a connective like "but", "yet", "however", "because", "as a result" contrasts or follows something that was cut from the draft. The sentence reads as one side of a missing two-sided structure.
4. **Missing definitional gloss**: a phrase that the source glossed as general/characteristic is presented in the draft without the gloss, leaving the reader unable to place it.
5. **Unattributed dialogue exchange**: a reply whose triggering question was cut, a dialogue where the speaker was introduced in the cut passage, or multiple adjacent quote-led turns that no longer make clear which character is speaking.
6. **Mid-scene jump**: a chapter opens with definite references ("the waif-pole", "the dead whale", "that night") that the previous draft chapter did not establish, AND the source of the previous chapter DID establish them in material that was dropped during compression.
7. **Unglossed minor proper name**: a minor/removable character's proper name appears without a local role, relationship, or appositive identifier, and the immediately preceding draft chapter does not establish who that named person is. If the name survives after its introduction was cut or after a long absence, the first local use must tell the reader who the person is.

Explicit rejections — these are NOT valid findings:

- The source had a philosophical/atmospheric opening and the draft skipped it; the draft's content sentence still stands on its own.
- The source had an explanatory relative clause and the draft cut it; the matrix clause still parses and conveys the meaning.
- A detail's cause or origin is cut; the reader understands the event without the source's flourish.
- The source named an object and the draft refers to it by context/descriptor; if a reader can infer what the object is, not a finding.
- Temporal sequencing is slightly altered but still parses.
- A major or continuously present character is named without a fresh gloss; readers can track principal names across chapters.
- A minor character is referred to only by a descriptor ("the neighbour", "Myrtle's sister") and the descriptor is clear; proper-name continuity is not required when the name has been elided.

**The gate test**: would a competent reader with no source access be *actually confused or misled* by this draft sentence, or would they merely be reading a less-ornamented version of the sentence? Only flag the first kind.

**Dialogue attribution audit.** Read every quoted exchange in the DRAFT, not just
single sentences. Flag `unattributed_dialogue` when compression leaves two or
more adjacent dialogue turns without enough speaker attribution, action beats,
or a still-obvious two-speaker alternation to identify who says what. This is
especially repair-worthy when the source used names, action beats, or dialogue
tags and the draft reduced the exchange to bare quotation paragraphs. Do not
flag a single bare reply if the immediately preceding turn and scene context
make the speaker unambiguous.

{% if cuts %}**Authorized cuts — residual seams are not findings.** A separate prepass instructed the drafter to remove the following material. Dangling references, missing-gloss seams, mid-scene jumps, or broken pivots that are *direct residues* of these authorized cuts (a sentence referring to "the hall" when the hallway scene was cut, an attribution to a character who has been elided) are EXPECTED and NOT findings. Only flag continuity breaks in material that should have survived compression.

{% if cuts.minor_characters %}Authorized minor-character removals: {% for c in cuts.minor_characters %}{{c.name}}{% if not loop.last %}, {% endif %}{% endfor %}.
{% endif %}{% if cuts.subplots %}Authorized subplot removals: {% for s in cuts.subplots %}{{s.name}} ({{s.chapter_span}}){% if not loop.last %}; {% endif %}{% endfor %}.
{% endif %}{% if cuts.digressions %}Authorized digression removals: {% for d in cuts.digressions %}Ch {{d.chapter_ids|join(", ")}} — {{d.topic}}{% if not loop.last %}; {% endif %}{% endfor %}.
{% endif %}{% endif %}

Named-person continuity invariant: if a proper name from the authorized
minor-character list appears in the draft, either the preceding draft chapter
or the local sentence/paragraph must identify that person. Flag the orphaned
name, not the editorial choice to cut that character.

For each finding:
- `valid`: true for a repair-worthy structural coherence failure. If you mention a rejected candidate for audit, set `valid`: false; prefer returning `[]` instead of rejected candidates.
- `class`: one of `non_parseable | dangling_reference | broken_pivot | missing_gloss | unattributed_dialogue | mid_scene_jump | unglossed_name`
- `chapter`: exactly "N" or "N+1" (do not output the literal chapter number)
- `draft_passage`: 20-200 chars, the damaged sentence
- `source_has`: the source's version showing what was present
- `gate_test_answer`: one sentence explicitly answering "is a reader genuinely confused, or just reading a less-ornamented version?"

If the drafts are structurally coherent, return `[]`.

# Ch {{n}} source

{{src_n}}

# Ch {{n}} draft

{{draft_n}}

# Ch {{n_plus_1}} source

{{src_np1}}

# Ch {{n_plus_1}} draft

{{draft_np1}}
