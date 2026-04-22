---
model: anthropic:claude-opus-4-7
max_tokens: 8000
---
You will receive a book's source text, followed by stage-specific instructions. This preamble is identical across the prime and pre-pass stages so that both can share a cache read on the book's source text.

# Book metadata

- book_id: {{book_id}}
- declared_genre: {{genre}}

# Source text

{{source_text}}
<!-- CACHE-BREAK -->

# Stage: prime — surface example signature passages

Your task is to produce a **non-exhaustive** set of example signature passages drawn from this specific book. The pre-pass stage will use your output as anchors when it produces the complete signature inventory for every segment. Your job is to establish, with concrete examples, what signature-worthy content looks like in THIS book's voice and concerns — not to enumerate everything.

{% if search_enabled %}
## Web search (use it) — three-tier provenance

For any claim about how the text has been read or received, search at three levels and note the tier for each result:

1. **Scholarly** — annotated editions, university-press books, academic essays.
2. **Encyclopedic** — Wikipedia specifically.
3. **Mass-audience** — SparkNotes or LitCharts specifically.

Discipline:

- If a tier is silent on a specific passage or question, **say so explicitly** — do not fill the silence with priors.
- If you make a claim from memory rather than from a search result, **mark it inline** as "(from memory, unverified)".
- When tiers disagree or emphasize different things, **report the disagreement** rather than synthesizing it away.
- Distinguish what is **load-bearing for the critical argument** from what is framing or context. A signature is load-bearing; frame is not.

Integration with the output:

- For each signature tagged `origin: "critical"` or `origin: "cultural"`, the `why` field must cite which tier(s) corroborate it (e.g., "scholarly + Wikipedia; mass-audience silent on this passage").
- If no tier corroborates a claim for critical/cultural origin, use a different origin tag (`textual` or `interpretive`) or drop the example.
- Do NOT reproduce paywalled or substantial copyrighted excerpts from criticism; extract claims, not long quotations.

Your final output is the JSON object described below; tool use happens server-side and doesn't change the response shape.

{% endif %}
Respond with a single JSON object and nothing else — no prose before or after, no markdown fences.

## What counts as a signature

A passage carries signature weight if it meets any of:

- **Cultural famousness** — widely quoted outside the book; reader recognition expected.
- **Textual distinctiveness** — prosodically, rhetorically, or stylistically unique; the sentence-shape itself is signature.
- **Critical engagement** — passages the critical tradition returns to.
- **Interpretive weight** — material specific readings of the book depend on.
- **Voice-establishing prose** — in voice-driven narrators, sustained ironic digressions, satirical asides, or register-defining paragraphs. The narrator's consciousness IS the content.

## Guidance for selecting examples

- Pick **25–40 examples** spanning the whole book. Do NOT cluster them in opening and closing chapters. For a novel of ~100 chapters, average one example every 3–5 chapters.
- Include at least one example from each origin type that applies.
- For voice-driven narrators: at least **one-third of your examples** must be voice-establishing passages drawn from chapter **middles** — sustained ironic digressions, satirical asides, register-defining paragraphs. These are the passages compression pressure will otherwise delete.
- Give **multiple examples per signature-role chapter** where warranted. If an opening chapter carries five distinct voice passages (a famous opening, an ironic digression on X, a satirical aside on Y, a set-piece metaphor, a closing image), list all five rather than picking just the opening.
- Include verbatim passage text (not paraphrased) in `passage_hint` so downstream string-matching works.
- **`passage_hint` must be a single contiguous quote from the source.** Do NOT use `...` ellipses to stitch together disjoint fragments — downstream fuzzy matching can't locate composite strings. If two separate phrases are both signature-worthy, emit them as two separate examples rather than joining with ellipsis.
- Each example should stand alone as evidence of "this is what signature material looks like in this book." The full set should convey "this is the density and variety of signature material the downstream stage should match."

## Produce a JSON object with this shape

{
  "book_id": "{{book_id}}",
  "notes": "<free text: what kinds of signature material exist in this book; what a downstream stage should hunt for>",
  "examples": [
    {
      "origin": "cultural" | "textual" | "critical" | "interpretive",
      "category": "quote" | "prosodic" | "structural" | "voice" | "character" | "thematic" | "narrative" | "touchstone" | "hook",
      "segment_hint": "<rough location: 'Chapter 3', 'early', 'the whaling scenes', etc.>",
      "passage_hint": "<verbatim excerpt from source, 10-40 words>",
      "why": "<1-2 sentences on what makes this signature-worthy>"
    }
  ]
}
