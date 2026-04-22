---
model: anthropic:claude-opus-4-7
max_tokens: 64000
---
You will receive a book's source text, followed by stage-specific instructions. This preamble is identical across the prime and pre-pass stages so that both can share a cache read on the book's source text.

# Book metadata

- book_id: {{book_id}}
- declared_genre: {{genre}}

# Source text

{{source_text}}
<!-- CACHE-BREAK -->

# Stage: pre-pass — annotate the pre-identified chapter skeleton

The book's structural units (chapters, front matter, epilogue) have already been identified by a deterministic splitter. Your job is to **annotate each chapter** — role, diegetic status, compression allocation, signatures, notes — plus produce book-level metadata (modernization level, voice-driven flag, motifs, plan notes). You do NOT identify chapter boundaries; that's already done. Respond with a single JSON object and nothing else — no prose before or after, no markdown fences.

## Parameters

- source_word_count: {{source_word_count}}
- target_word_count: {{target_word_count}}
- implied_overall_compression_ratio: {{compression_ratio}}

## Pre-identified chapters

The splitter has identified {{chapters|length}} chapter-level structural units. Your `segments` array must contain one entry per chapter below, keyed by the same `id`. Do NOT merge, split, or renumber them — use the ids exactly as given.

{% for c in chapters %}- **{{c.id}}** [{{c.kind}}]{% if c.number %} #{{c.number}}{% endif %} — {% if c.title %}{{c.title}}{% else %}{{c.raw_heading}}{% endif %} ({{c.word_count}} words)
{% endfor %}

Each chapter's text lives in the source above, at its heading line. Use the source to determine role/signatures/notes.

{% if primed_examples %}## Primed example signatures (non-exhaustive seed)

The passages below were identified in a prior priming pass as signature material in THIS book. They are NON-EXHAUSTIVE examples — use them as anchors for what signature content looks like in this book's voice, and extend the pattern to identify the **complete** set in your plan. Do not limit yourself to these; do not drop any of these without explicit reason.

{% for ex in primed_examples %}- [{{ex.origin}}/{{ex.category}}] "{{ex.passage_hint}}" — {{ex.why}}
{% endfor %}
{% endif %}
## Produce a JSON object with this shape

{
  "book_id": "{{book_id}}",
  "title": "<inferred from text>",
  "author": "<inferred from text>",
  "source_word_count": {{source_word_count}},
  "target_word_count": {{target_word_count}},
  "overall_compression_ratio": {{compression_ratio}},

  "structural_classification": "sequential" | "non_linear_refuse" | "unsegmented",
  "refusal": null | {"reason": "<code>", "detail": "<why>"},

  "modernization_level": "L0" | "L1" | "L2" | "L3" | "L4",
  "modernization_rationale": "<1-2 sentences on era-accumulated difficulty>",

  "cultural_depth": "high" | "medium" | "low",
  "voice_driven_narrator": true | false,
  "indirection_budget_applies": true | false,

  "segments": [
    {
      "id": "<matches splitter chapter id, verbatim>",
      "diegetic_status": "diegetic" | "extradiegetic" | "ambiguous",
      "role": "signature" | "narrative" | "digressive",
      "target_word_count": <int>,
      "relative_compression": <float, 1.0 = book average>,
      "signatures": [
        {
          "origin": "cultural" | "textual" | "critical" | "interpretive",
          "category": "quote" | "prosodic" | "structural" | "voice" | "character" | "thematic" | "narrative" | "touchstone" | "hook",
          "priority": "verbatim" | "recognizable" | "optional",
          "passage_hint": "<short excerpt or clear locator>",
          "why": "<1 sentence>"
        }
      ],
      "notes": "<editorial guidance for the drafter>"
    }
  ],

  "motifs": [
    {
      "name": "<short name>",
      "description": "<1-2 sentences>",
      "indicative_phrases": ["...", "..."],
      "target_legibility": "preserve at book scale"
    }
  ],

  "plan_notes": "<free text for the drafter: overall voice guidance, period/register cautions, known difficult passages>"
}

## Guidance

- Segmentation is already decided — you annotate the splitter's chapters, you don't redo them. Your segments array has one entry per chapter in the skeleton above.
- Classify apparatus per chapter: extradiegetic segments (scholarly intros, editor's notes, translator's notes) should be marked so downstream can cut them. Diegetic front matter (fictional-voice prefaces, in-world etymologies) stays. A segment's `diegetic_status` and its `notes` must agree — if notes say "preserve in compressed form," the status is not extradiegetic.
- Relative compression: signature segments 0.6-0.8, narrative ~1.0, digressive 1.5-2.0 — unless digression is thematically load-bearing, in which case tighten it toward 1.0.
- Signatures from all four origins: famous quotes, prosodically distinctive passages, critically-engaged passages, and material load-bearing for known readings.
- **`passage_hint` must be a single contiguous quote from the source.** Do NOT use `...` ellipses to stitch together disjoint fragments — downstream fuzzy matching can't locate composite strings. If two phrases are both signature-worthy, emit them as separate signatures rather than joining with ellipsis.
- If the book's form is incompatible with sequential abridgment (non-linear cross-referential work, e.g. *Pale Fire*), set `structural_classification` to "non_linear_refuse" and populate `refusal`. Note: if the splitter produced zero or one segment for a prose-continuous book, set `structural_classification` to "unsegmented" and emit a single segment.
- Be concrete. "notes" fields should give the drafter actionable guidance.

### Signature coverage

Signatures are NOT limited to quotable lines. A sustained passage that establishes the narrator's register, irony, or thought-pattern is a signature in its own right, even if no single sentence stands alone. Miss these and the drafter has no preservation obligation on voice material, which it will then compress away.

**Primed examples are a FLOOR, not a ceiling.** If a prime pass surfaced example passages for a segment, keep those verbatim AND extend the pattern to the full set of comparable passages in that segment. Adding one closing image to the primed examples is not "extending the pattern" — look for every comparable passage.

### Signature priority tier (mandatory per signature)

Every signature gets a `priority` tier. The drafter uses this to decide which signatures to preserve verbatim, which to preserve in recognizable form, and which to drop if book-level budget forces a choice. Apply this rubric mechanically rather than by taste:

- **`verbatim`** — assign when ALL of:
  - passage is **≤ ~25 words**, AND
  - passage is a **cultural touchstone** (widely quoted outside the book) OR a **structural bookend** (first/last sentence of the book or of a major section), AND
  - readers expect the exact words; any variation is a loss.
  - Examples: *"Call me Ishmael."*, *"So we beat on, boats against the current..."*, *"Her voice is full of money."*

- **`recognizable`** — default for signature-worthy passages that don't meet the `verbatim` bar:
  - longer passages whose shape, key imagery, and one or two identifying phrases must be preserved but where internal compression (ellipsis between anchor phrases) is acceptable.
  - Examples: the Narcissus/ungraspable-phantom passage (important but can elide internal clauses), the Valley-of-Ashes description, extended characterizations like *"If personality is an unbroken series of successful gestures..."*

- **`optional`** — signature-worthy but not essential to the Success Criterion:
  - interchangeable instances of a motif (if you flag 6 green-light references, 2-3 should be optional — the others carry the motif),
  - character beats that enrich but aren't critical touchstones,
  - nicely-written or critically-discussed lines that aren't widely-cited,
  - passages that could be paraphrased without destroying any specific reading.

**Hard quota: exactly ~25% of the signatures you emit across the whole book must be `optional`.** Count after you've identified the full set and rank by droppability. If you find yourself below 20% optional, re-examine your `recognizable` list and demote the 5–10% least indispensable to `optional`. This is not guidance — the drafter relies on optionals as its budget-adjustment lever. Being stingy with `optional` breaks the pipeline's ability to hit the word-count target.

**Target signature counts per segment (voice-driven works):**
- Signature-role segments: **6–12 signatures.** These are signature-role precisely because they carry a lot of preservation-worthy material. Four is not enough.
- Narrative-role segments: **3–6 signatures.** Include at least one voice-establishing passage per segment.
- Digressive-role segments with thematic load: **4–8 signatures.**
- Pure digression or extradiegetic: **1–3 signatures** (or zero if cut).

For plot-driven works with transparent narrators, halve those ranges.

**Coverage rules:**

- If `voice_driven_narrator` is true, every segment that isn't pure plot or documentary should have **at least two voice-establishing signatures** tagged `interpretive/voice` — typically sustained ironic digressions, satirical asides, or characteristic register-defining paragraphs.
- Signatures must appear throughout a segment, not only at its opening and closing. Chapter middles usually contain voice material the compression pressure will otherwise delete. Explicitly scan each segment middle for voice-establishing passages; flag them as signatures even if no single line is quotable.
- Set `voice_driven_narrator` to true when the narrator's register is constitutive of the reading experience — when paraphrasing their sentences into neutral modern prose would destroy what the book is. Most 1st-person narrators with strong irony qualify; most transparent 3rd-person plot narrators do not.
- For biographies where the biographer (or autobiographical subject) writes in a characteristic voice — sustained irony, distinctive narrative device, unusual person/tense choices — `voice_driven_narrator` is true for that voice, distinct from any biography-specific preservation of primary-source quotations.
