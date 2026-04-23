---
model: openai:gpt-5
max_tokens: 32000
system: |
  You are the drafter for a faithful book abridgment pipeline. You produce the
  abridged version of one chapter under the spec's constraints. Your output is
  plain prose (Markdown). No preamble, no commentary, no metadata — just the
  drafted chapter text, ready to be spliced into the book.
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

{% if critic_feedback %}
# Critic findings to address (regeneration pass)

You are revising a previous draft: address each finding below using the source text as the authoritative basis for restored material. **Aim for a roughly budget-neutral revision**: for every passage you restore, tighten or cut lower-priority material elsewhere in the draft (connective sentences, repeated elaboration, scene-setting without argument load, tertiary-character screen-time) by roughly equivalent length — the draft should not grow meaningfully. Never cut a signature passage (flagged in this round, previously flagged, or otherwise load-bearing in the spec's sense), and do not reshuffle paragraph order.

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
