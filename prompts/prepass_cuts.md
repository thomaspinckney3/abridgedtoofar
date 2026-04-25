---
model: openai:gpt-5
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

   For each skippable chapter, also identify whether a *kernel* of essential content needs to survive elsewhere:

   - `kernel`: a 1-3 sentence paraphrase capturing the load-bearing event/fact/character-introduction from the chapter that later chapters depend on. Use empty string `""` if the chapter is cleanly skippable with no preservation needed.
   - `relocate_to`: the segment ID where the kernel should be inserted (a surviving chapter, NOT another skippable chapter). Use the segment IDs from the `## Chapter NNN` headings, not canonical book chapter numbers.
   - `position`: where in the target chapter to insert — `"start"` (before existing content), `"end"` (after existing content). Use `null` if no kernel.

   Chronology and voice MUST match: the kernel paraphrase should read as a natural continuation/anticipation of the target chapter's existing prose. If a target chapter is in a different narrator-voice (e.g. Esther's first-person vs. omniscient), the kernel should match the target's voice.

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
