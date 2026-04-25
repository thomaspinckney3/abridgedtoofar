---
model: anthropic:claude-opus-4-7
max_tokens: 32000
system: |
  You are the drafter for a faithful book abridgment pipeline. You produce the
  abridged version of one chapter under the spec's constraints. Your output is
  plain prose (Markdown). No preamble, no commentary, no metadata — just the
  drafted chapter text, ready to be spliced into the book.

  Preserve standard fiction paragraph conventions. Each new speaker's dialogue
  turn goes in its own paragraph (separated by a blank line). Never concatenate
  multiple speakers' lines into one paragraph, even under compression pressure.
  A single speaker's dialogue plus surrounding attribution and action may
  share a paragraph.
---
# Forage abridgment spec (authoritative guidance)

{{spec}}

<!-- CACHE-BREAK -->

---

{% if merged_members %}# These chapters

- **Book:** {{book.title}} by {{book.author}} ({{book.genre}})
- **Group:** {{segment.id}} — {{merged_members|length}} adjacent chapters drafted together
- **Per-chapter targets:** {% for m in merged_members %}ch{{loop.index}}={{m.target_word_count}}{% if not loop.last %}, {% endif %}{% endfor %}
- **Combined source:** {{segment.source_word_count}} words
- **Combined target:** {{segment.target_word_count}} words

Produce one contiguous output, but delimit each sub-chapter with a `## Chapter N` heading line so the output can be split into per-chapter drafts downstream. Hit each sub-chapter's target. Compress aggressively — the combined ratio is about {{'%.1f'|format(segment.source_word_count / segment.target_word_count)}}×.
{% else %}# This chapter

- **Book:** {{book.title}} by {{book.author}} ({{book.genre}})
- **Chapter:** {{segment.title}} (id {{segment.id}})
{% endif %}

{% if cuts %}
# Cuttable material inventory

A prepass has identified the following characters, subplots, and digressions as *removable without meaningfully changing the book's plot, themes, or principal-character arcs.* When compressing this chapter, prefer cutting or minimizing these over cutting anything else. You do not need to invent reasons to preserve material on this list.

{% if cuts.minor_characters %}**Minor characters — prefer to elide, un-name, or collapse into descriptors:**
{% for c in cuts.minor_characters %}- **{{c.name}}** — {{c.reason_removable}}
{% endfor %}
{% endif %}{% if cuts.subplots %}**Subplots — prefer to cut or reduce to one-sentence summary:**
{% for s in cuts.subplots %}- **{{s.name}}** ({{s.chapter_span}}) — {{s.reason_removable}}
{% endfor %}
{% endif %}{% if cuts.digressions %}**Digressions — prefer to cut or condense heavily:**
{% for d in cuts.digressions %}- **Ch {{d.chapter_ids|join(", ")}} — {{d.topic}}** — {{d.reason_removable}}
{% endfor %}{% endif %}
{% endif %}
{% if kernels %}
# Mandatory passages to preserve — relocated kernels

The following passages are kernels relocated from chapters that were elided wholesale. They carry plot beats, character setups, or callbacks that LATER chapters depend on, so they MUST appear in your draft of this chapter, in either the position indicated or somewhere structurally equivalent. Preserve them verbatim or paraphrase only minimally; do NOT paraphrase them down further or omit them, even under compression pressure. The per-chapter target word count assumes these kernels are present.

{% for k in kernels %}- **From skipped Ch {{k.from_chapter}} → into Ch {{k.to_chapter}} ({{k.position}}):**
  > {{k.kernel}}

{% endfor %}{% endif %}
{% if critic_feedback %}
# Critic findings to address (regeneration pass)

You are revising a previous draft: address each finding below using the source text as the authoritative basis for restored material. **Aim for a roughly budget-neutral revision**: for every passage you restore, tighten or cut lower-priority material elsewhere in the draft (connective sentences, repeated elaboration, scene-setting without argument load, tertiary-character screen-time) by roughly equivalent length — the draft should not grow meaningfully. Never cut a signature passage (flagged in this round, previously flagged, or otherwise load-bearing in the spec's sense), and do not reshuffle paragraph order.{% if cuts %}

**Cuts inventory overrides critic findings.** If a finding asks you to restore material that lives inside — or is inseparable from — a scene, subplot, character, or digression on the authorized cuts inventory above, SKIP that finding. The cuts inventory takes priority over critic feedback because it represents an upstream editorial decision the critic may not fully honor. The critic *may* still surface useful complaints about material ADJACENT to a cut (e.g. a causal link, pivot, or signature phrase that could have survived even though the scene it lived in was cut) — use judgment: restore only the severable, non-cut element, not the cut scene itself.{% endif %}

{% for f in critic_feedback %}{{loop.index}}. **[{{f.severity}}] {{f.class}}**
   - Source passage: "{{f.source_passage}}"
   - Current treatment in draft: `{{f.draft_treatment}}`
   - Why it matters: {{f.why_it_matters}}
   - Suggested fix: {{f.suggested_fix}}

{% endfor %}
## Previous draft (revise this)

{{previous_draft}}

{% endif %}
# Source text

{{segment_source}}

# Task

Produce the faithful abridgment per the spec above. {% if merged_members %}Emit {{merged_members|length}} chapter-delimited sub-sections with `## Chapter N` headings so the output can be split. {% endif %}Output only the abridged prose — no preamble, no commentary, no metadata.
