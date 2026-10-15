---
model: anthropic:claude-opus-5-5
max_tokens: 4000
system: |
  You are re-identifying the signature inventory for one segment of a book whose
  global plan already exists. Your output is a JSON object and nothing else —
  no prose before or after, no markdown fences.
---
You are re-running signature identification for **segment {{segment.id}} — {{segment.title}}** of **{{book.title}}** by {{book.author}}.

The book's global plan has already been produced. This reconsideration exists so we can iterate on signature-identification quality without re-running the whole pre-pass. Your output updates this segment's entry only.

## Book-level context (fixed)

- Genre: {{book.genre}}
- Voice-driven narrator: {{plan.voice_driven_narrator}}
- Indirection budget applies: {{plan.indirection_budget_applies}}
- Modernization level: {{plan.modernization_level}}
- Overall compression ratio: {{plan.overall_compression_ratio}}x
- Plan notes: {{plan.plan_notes}}

## This segment

- Title: {{segment.title}}
- Native kind: {{segment.kind}}
- Role: {{segment.role}}
- Target word count: {{segment.target_word_count}} (relative compression {{segment.relative_compression}}× vs book average)

## Signature-coverage guidance

Signatures are NOT limited to quotable lines. A sustained passage that establishes the narrator's register, irony, or thought-pattern is a signature in its own right, even if no single sentence stands alone. Miss these and the drafter has no preservation obligation on voice material, which it will then compress away.

**Target signature counts for this segment (voice-driven works):**
- Signature-role: **6–12 signatures.** Four is not enough for a signature-role segment.
- Narrative-role: **3–6 signatures.** Include at least one voice-establishing passage.
- Digressive-role with thematic load: **4–8 signatures.**

Halve these ranges for plot-driven works with transparent narrators.

**Coverage rules:**

- If the book has a voice-driven narrator, the segment should carry **at least two voice-establishing signatures** tagged `interpretive/voice` — typically sustained ironic digressions, satirical asides, or characteristic register-defining paragraphs.
- Signatures must appear throughout the segment, not only at its opening and closing. Chapter middles usually contain voice material the compression pressure will otherwise delete. Explicitly scan the middle; flag voice passages even if no single line is quotable.
- Signatures come from four origins (any one qualifies): cultural famousness, textual distinctiveness, critical engagement, interpretive weight.
- **`passage_hint` must be a single contiguous quote from the source.** Do NOT use `...` ellipses to stitch together disjoint fragments — downstream fuzzy matching can't locate composite strings. If two phrases are both signature-worthy, emit them as separate signatures.

## Your task

Return a JSON object with this shape — nothing else:

{
  "segment_id": "{{segment.id}}",
  "role": "signature" | "narrative" | "digressive",
  "signatures": [
    {
      "origin": "cultural" | "textual" | "critical" | "interpretive",
      "category": "quote" | "prosodic" | "structural" | "voice" | "character" | "thematic" | "narrative" | "touchstone" | "hook",
      "priority": "verbatim" | "recognizable" | "optional",
      "passage_hint": "<short excerpt or clear locator; use the source's exact words so downstream string-matching works>",
      "why": "<1 sentence>"
    }
  ],
  "notes": "<editorial guidance for the drafter>"
}

## Priority tier rubric

Every signature gets a `priority`. Apply mechanically:

- **`verbatim`** — passage is ≤ ~25 words AND (cultural touchstone OR structural bookend) AND exact words matter. Examples: *"Call me Ishmael."*, *"Her voice is full of money."*, closing sentences.
- **`recognizable`** — default. Longer passages whose shape + key imagery + one identifying phrase must stay, internal compression allowed.
- **`optional`** — signature-worthy but not essential to the Success Criterion. Interchangeable motif instances, character beats, nicely-written lines not widely cited. **At book scale, the prepass targets ~25% of signatures as `optional`.** For this single-segment reconsider, aim for roughly 25% as well — the drafter needs optionals to absorb budget pressure.

## Source text for this segment

{{segment_source}}
