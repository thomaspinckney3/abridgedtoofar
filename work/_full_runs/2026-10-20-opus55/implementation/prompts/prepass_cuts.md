---
model: openai:gpt-6-astra
max_tokens: 12000
---
You are building a "cuts inventory" for an abridgment of **{{book.title}}** by {{book.author}}. Enumerate characters, subplots, and digressions that a careful abridger could REMOVE without materially changing a reader's sense of the book's plot, themes, or central characters.

{% if synopsis %}# Authoritative synopsis

The abridgment must preserve everything that appears in this {{ synopsis.splitlines()|length }}-sentence synopsis. Treat the synopsis as the shape the abridgment must hold to; anything orthogonal to it is a candidate for cutting.

{{synopsis}}

{% endif %}# Three categories

1. **Minor characters**: named figures whose removal would not alter the reader's understanding of the plot or the major characters' arcs. Typical examples: one-scene hosts, one-line speakers, one-chapter guests, background figures who never recur. Do NOT include anyone mentioned in the synopsis.

2. **Subplots**: branch narratives that are self-contained or thematically parallel but not structurally necessary to the main arc. Examples: embedded stories told inside chapters, side adventures that don't affect the protagonist's outcome, subplots centered on minor characters.

3. **Digressions**: chapters or substantial passages that are essayistic, taxonomic, technical, philosophical, or descriptive in a way that doesn't advance plot or reveal main-character interiority. Examples: Moby Dick's cetological chapters, genealogical exposition, historical-context lectures, extended field-notes.

4. **Whole-chapter skips**: chapter IDs whose ENTIRE content can be removed without losing any plot beat the synopsis depends on. A chapter qualifies only if every meaningful event in it is either subplot material listed in (2), digression material listed in (3), or background colour with no main-arc consequence. Be conservative: if a chapter contains *any* line whose absence would orphan a later reference (a name, a return, a callback), keep it off this list — UNLESS the load-bearing material can be cleanly distilled and relocated.

   For each skippable chapter, decide whether a *kernel* of essential content needs to survive elsewhere. The kernel decision has exactly two outcomes:

   **(a) Relocate a kernel** — produce a 1-3 sentence paraphrase of the chapter's load-bearing material and identify exactly one target:

   - `relocate_to`: MUST be either the most-recent surviving chapter BEFORE the skipped chapter (in segment-ID order) OR the next surviving chapter AFTER it. Long-distance relocations are forbidden — the kernel must land in an immediate prior-or-subsequent kept chapter, never further away. Use the segment IDs from the `## Chapter NNN` headings, not canonical book chapter numbers.
   - `position`: `"start"` (before existing content of the target) or `"end"` (after).
   - The kernel paraphrase MUST integrate naturally with the target chapter's voice and chronology — read as a clean continuation/anticipation of the target's existing prose, not a mood-breaking interjection. If a target chapter is in a different narrator-voice (e.g. Esther's first-person vs. omniscient), the kernel must match the target's voice.

   **(b) Clean skip with no kernel** — pick this if (i) no later chapter depends on a setup or callback from this chapter, OR (ii) the load-bearing material can't be relocated to either the prior or subsequent kept chapter without breaking voice or chronology. This is a first-class outcome, not a fallback. Famous voice-signature passages (e.g. Moby Dick's Cetology meta-commentary, Bleak House's elegiac coda) often belong here — the loss is real but trying to relocate them produces worse damage than just letting them go.

   For (b), set `kernel: ""`, `relocate_to: null`, `position: null`.

   Pick exactly one outcome per chapter. Do NOT propose alternatives or hedged placements.

Each entry requires a **one-sentence `reason_removable`** that a careful reader would accept as justification. If you can't articulate a justification, don't list the item.

**Safety rule**: bias toward preservation. When in doubt, leave it off the list. A short inventory of definitely-removable items is more useful than an inflated list that mixes sure cuts with speculative ones.

# Output

Respond with a single JSON object — no preamble, no markdown fences:

```json
{
  "minor_characters": [
    {"name": "...", "appearances_summary": "where and how they appear", "reason_removable": "one sentence"}
  ],
  "subplots": [
    {"name": "...", "chapter_span": "Ch X or Ch X–Y", "reason_removable": "one sentence"}
  ],
  "digressions": [
    {"chapter_ids": ["NNN"], "topic": "...", "reason_removable": "one sentence"}
  ],
  "skippable_chapters": [
    {
      "chapter_id": "NNN",
      "reason_removable": "one sentence",
      "kernel": "1-3 sentence paraphrase of load-bearing content; empty string if none",
      "relocate_to": "MMM",
      "position": "start" | "end" | null
    }
  ]
}
```

**CRITICAL — chapter IDs**: Use ONLY the three-digit segment ID shown in the `## Chapter NNN` headings below (e.g. `"007"`, `"034"`). Do NOT use the book's canonical chapter numbers from your training data, which may differ from the segment IDs (e.g. Bleak House's canonical Chapter 1 may be segment 002 here because of preface material). Always cross-reference the heading you see in the source text and copy that exact NNN value into `chapter_ids` / `chapter_id` fields. If you describe content that you recall from canonical Chapter N, find the segment whose `## Chapter NNN` heading actually contains that content and use NNN.

Keep each array potentially empty (`[]`) if no such items exist.

# Source

{{source}}
