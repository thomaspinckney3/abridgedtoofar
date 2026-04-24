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
  ]
}
```

Use the chapter ID numbers shown in the `## Chapter NNN` headings below for `chapter_ids`. Keep each array potentially empty (`[]`) if no such items exist.

# Source

{{source}}
