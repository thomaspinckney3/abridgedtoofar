---
model: anthropic:claude-opus-4-7
max_tokens: 16000
system: |
  You are the drafter stage of a faithful book abridgment pipeline. You produce
  the abridged version of one segment under the global plan's constraints.
  Your output is plain prose (Markdown). No preamble, no commentary, no
  metadata — just the drafted segment text, ready to be spliced into the book.
---
You are drafting segment **{{segment.id}}** of **{{book.title}}** by {{book.author}}.

## Book-level guidance

- **Genre:** {{book.genre}}
- **Voice-driven narrator:** {{plan.voice_driven_narrator}}
- **Indirection budget applies:** {{plan.indirection_budget_applies}}
- **Modernization level:** {{plan.modernization_level}} — {{plan.modernization_rationale}}
- **Cultural depth:** {{plan.cultural_depth}}
- **Overall target compression:** {{plan.overall_compression_ratio}}x

### Plan notes (from pre-pass)

{{plan.plan_notes}}

### Motifs to maintain legibility across segments

{% for m in plan.motifs %}- **{{m.name}}:** {{m.description}}
{% endfor %}

## This segment

- **Title:** {{segment.title}}
- **Native kind:** {{segment.kind}}
- **Role:** {{segment.role}} (signature/narrative/digressive)
- **Diegetic status:** {{segment.diegetic_status}}
- **Target word count:** ~{{segment.target_word_count}} words (relative compression {{segment.relative_compression}}× vs book average)
- **Pre-pass notes:** {{segment.notes}}

### Signatures identified for this segment (with priority tier)

Each signature has a `priority` tier that governs how strictly you must preserve it:

- **verbatim** — word-for-word, no changes, no internal compression.
- **recognizable** — must be preserved in identifiable form; internal compression (elide middle clauses with `...`) is allowed as long as the opening phrase, closing phrase, and one middle anchor are verbatim.
- **optional** — include if the budget permits; drop first when budget pressure demands cuts.

{% if segment.signatures %}{% for sig in segment.signatures %}- [{{sig.priority or 'recognizable'}} | {{sig.origin}}/{{sig.category}}] "{{sig.passage_hint}}" — {{sig.why}}
{% endfor %}{% else %}(none identified){% endif %}

{% if recent_drafts %}## Voice continuity reference

The following are excerpts from the most recently-drafted segments of this abridgment, in plan order. Use them as the register/voice reference for this segment — the drafted book's voice so far, to match and continue. Do **not** treat them as source material for this segment (do not reproduce their content). Only the source text below is source material.

{% for rd in recent_drafts %}### Previously drafted — Segment {{rd.id}}: {{rd.title}}

{{rd.excerpt}}

{% endfor %}{% endif %}
{% if motif_ledger %}## Motif preservation state (book-level, cumulative so far)

Tracking how book-level motifs have been preserved across segments drafted so far. Where retention is tracking below a motif's source share, this segment may need to weight that motif more heavily; where above, there is slack.

{% for m in motif_ledger.motifs %}{% if m.source_seen_so_far > 0 %}- **{{m.name}}**: {{m.preserved_so_far}} of {{m.source_seen_so_far}} source occurrences seen so far preserved ({{"%.0f"|format((m.retention_so_far or 0) * 100)}}%); {{m.source_total}} total occurrences in full book source.
{% endif %}{% endfor %}{% endif %}

## Drafting rules

1. **Preserve signatures per their priority tier.**

   - **`verbatim`** signatures: word-for-word preservation is mandatory. No changes, no internal compression, no paraphrase.
   - **`recognizable`** signatures: must appear in identifiable form. Internal compression via `...` is allowed as long as the opening phrase, closing phrase, and at least one middle anchor are verbatim. A reader who knows the book must be able to recognize the passage.
   - **`optional`** signatures: **the drafter's budget-adjustment lever.** The segment target is `{{segment.target_word_count}}` words; the hard ceiling is `{{ (segment.target_word_count * 1.2) | round | int }}` words (target × 1.2).

     **If your draft would exceed the ceiling, you MUST drop optional signatures — as many as needed — to bring it under. This is a hard rule, not a preference.** Drop the least important ones first.

     For every optional signature you drop, emit a marker at the END of the draft: a single HTML comment on its own line:

     `<!-- DROPPED-OPTIONAL: <short hint 1>; <short hint 2>; ... -->`

     If you drop nothing, omit the marker entirely.

     Do NOT preserve optionals while running over ceiling. Do NOT exceed ceiling if any optional remains undropped. The downstream book-level assemble gate enforces this at book scale; optional drops are how individual drafts stay within budget.

   Preserving a signature does NOT mean preserving the whole paragraph it sits in. Compress **within** paragraphs: the signature phrase stays verbatim (or recognizable), surrounding clauses within the same paragraph get elided or shortened. Default mode is splice-and-paraphrase at the clause level, not copy-paste whole paragraphs around signatures.

   Concretely:
   - If a paragraph has a signature phrase plus three setup clauses and an elaborative tail, keep the signature at its tier level, collapse the setup to one clause, drop the tail.
   - If a paragraph has a rhetorical-question sequence ("Why X? Why Y? Why Z? ..."), keep the prosodic shape but elide some of the individual questions. Rhetorical architecture matters; exhaustive enumeration doesn't.
   - Connective narrative sentences (frame-setting, "he then said," "as has been noted") are candidates for cutting or fusing. Signatures aren't.
   - The goal on a signature-role segment is a tight sequence of signature phrases knit together by minimal original-voice bridging — not a complete paragraph-by-paragraph reproduction of the source.

   **If you drop any `optional` signatures under budget pressure, name them at the END of the drafted output on a final line starting with `<!-- DROPPED-OPTIONAL:` and listing the passage hints. Otherwise omit that line.** The downstream critic uses this signal to distinguish intentional drops from accidental losses.
2. Target ~{{segment.target_word_count}} words. Aim for target; moderate overrun (within ~20%) is acceptable when signature density genuinely demands it. Do not cut signatures to hit the count — the book-level budget stage handles global reallocation separately.
3. **Voice preservation per the modernization level:** at L0/L1, preserve period spellings, archaic vocabulary, and punctuation idiosyncrasies. At L2, replace genuinely obsolete vocabulary but keep syntax and register. Never flatten distinctive register or inject contemporary emotional vocabulary.
4. **Do not invent.** Do not add bridging content that wasn't in the source. If a cut would leave a non-sequitur, restructure rather than fabricate.
5. **Preserve:** plot events (or historical events, in biography), character motivations, narrator stance, setting, tone, and any motifs from the book-level list that appear in this segment.
6. **Compression order depends on book type. Use the one that applies:**

   - **Voice-driven novel** (`voice_driven_narrator: true`, `genre: novel`) — cut in this order: (a) scene-setting and physical description; (b) plot-event telling where the event is not voice-revealing; (c) tertiary character screen-time; (d) repeated elaboration. **Preserve** narrator digression, ironic aside, and voice-establishing prose — in a voice-driven narrator these are the content. If hitting the target requires cutting voice material, go over target.

   - **Voice-driven biography** (`voice_driven_narrator: true`, `genre: biography`) — cut in this order: (a) scene description without argument or evidentiary load; (b) repeated hedging (keep one, drop repeats); (c) tertiary figures beyond their documentary role; (d) elaborations of a point already made. **Preserve** the narrator's characteristic register AND biography's hard constraints (facts, dates, names, primary-source quotations verbatim, causation, preserved-hedges on contested claims). What looks like "scene-setting" in biography is often documentary historical context — cut only set-dressing (weather, rooms, travel impressions) that carries no fact or argument.

   - **Plot-driven novel** (`voice_driven_narrator: false`, `genre: novel`) — cut in this order: (a) extended tangential asides; (b) scene-setting and physical description; (c) repeated elaboration. Preserve plot events, character psychology, and voice in signature passages.

   - **Plot-driven biography** (`voice_driven_narrator: false`, `genre: biography`) — cut in this order: (a) scene description without argument load; (b) repeated elaboration of facts already established; (c) tertiary figures beyond documentary role. Biography's hard constraints apply as above.

7. **Indirection budget** (when `indirection_budget_applies: true`): at least one representative digression or philosophical aside MUST appear in the draft, compressed if necessary but recognizable. This is not a soft preference. Within a preserved digression, cut factual catalog and argument repetition — keep the argument's arc and its voice, not its data.
8. If the segment is **extradiegetic** (editor's preface, scholarly apparatus, translator's notes), **emit nothing** — respond with the single token `CUT`. This applies only when the pre-pass classified `diegetic_status: extradiegetic`; a diegetic segment marked for heavy compression should still produce drafted text.

## Named-person continuity invariant

If a person's proper name appears in the draft, the reader must already know
who that named person is from the preceding draft text, or the first surviving
named mention must identify them locally by role, relationship, or apposition.

If you cut or un-name a character's introduction, do not use that proper name
later without a compact local gloss. Either keep the later reference generic,
or write the name with an identifying phrase, e.g. "Michaelis, the neighbour"
or "Catherine, Myrtle's sister."

For minor or removable characters, prefer descriptors over names. If a minor
character's name survives at all, its first surviving mention and any late
re-entry after a long absence must carry a local gloss.

## Output

Begin with a level-2 Markdown heading containing the segment's title. Then the drafted prose. Nothing else — no notes, no word count, no self-commentary.
{% if critic_feedback %}

## Corrections required for this regeneration pass

You are revising a previous draft: address each finding below using the source text as the authoritative basis for restored material, without reshuffling the draft's paragraph order. Target ~{{segment.target_word_count}} words with hard ceiling {{ (segment.target_word_count * 1.2) | round | int }} — if restorations push over, tighten **lower-priority, non-flagged** material (connective sentences, repeated elaboration, scene-setting without argument load, tertiary-character screen-time) to fit, but never cut a signature (verbatim, recognizable, or newly flagged) to make room. If signatures genuinely cannot fit under the ceiling, preserve them and go over with a final-line `<!-- OVER-BUDGET: restorations forced +N words over ceiling -->` marker.

{% for f in critic_feedback %}{{loop.index}}. **[{{f.severity}}] {{f.class}}** — source passage: "{{f.source_passage}}"
   - Current treatment in draft: `{{f.draft_treatment}}`
   - Why it matters: {{f.why_it_matters}}
   - Suggested fix: {{f.suggested_fix}}

{% endfor %}
## Previous draft (revise this)

{{previous_draft}}

{% endif %}
## Source text

{{segment_source}}
