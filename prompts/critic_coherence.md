---
model: anthropic:claude-sonnet-4-6
max_tokens: 12000
---
You are a coherence critic for an abridgment. You see SOURCE and DRAFT for a pair of consecutive chapters. Find places where compression has *structurally damaged* meaning — not places where the draft is merely less richly phrased than the source.

A finding is valid ONLY if the draft sentence fails at least ONE of these specific tests:

1. **Non-parseable on its own**: the sentence has no main clause, or its main clause's referent is missing from the entire preceding draft.
2. **Dangling pronoun/demonstrative**: "he/she/it/this/that/these" used with no unambiguous antecedent in the preceding draft (not source — draft).
3. **Broken logical pivot**: a connective like "but", "yet", "however", "because", "as a result" contrasts or follows something that was cut from the draft. The sentence reads as one side of a missing two-sided structure.
4. **Missing definitional gloss**: a phrase that the source glossed as general/characteristic is presented in the draft without the gloss, leaving the reader unable to place it.
5. **Unattributed dialogue exchange**: a reply whose triggering question was cut, or a dialogue where the speaker was introduced in the cut passage.
6. **Mid-scene jump**: a chapter opens with definite references ("the waif-pole", "the dead whale", "that night") that the previous draft chapter did not establish, AND the source of the previous chapter DID establish them in material that was dropped during compression.

Explicit rejections — these are NOT valid findings:

- The source had a philosophical/atmospheric opening and the draft skipped it; the draft's content sentence still stands on its own.
- The source had an explanatory relative clause and the draft cut it; the matrix clause still parses and conveys the meaning.
- A detail's cause or origin is cut; the reader understands the event without the source's flourish.
- The source named an object and the draft refers to it by context/descriptor; if a reader can infer what the object is, not a finding.
- Temporal sequencing is slightly altered but still parses.

**The gate test**: would a competent reader with no source access be *actually confused or misled* by this draft sentence, or would they merely be reading a less-ornamented version of the sentence? Only flag the first kind.

For each finding:
- `class`: one of `non_parseable | dangling_reference | broken_pivot | missing_gloss | unattributed_dialogue | mid_scene_jump`
- `chapter`: "N" or "N+1"
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
