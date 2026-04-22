# Faithful Abridgment — Working Spec

**Status:** draft, iterating. This document is updated as we make decisions.
**System scope (current):** English-language novels. Other book types (poetry, essays, drama, non-fiction, translated works) are out of scope for this system's preservation rules and would require a separate spec.

---

## Primary success criterion

After reading the abridgment, the reader should be able to understand a literary critique of the full text — follow the critic's claims, see where in the book they apply, and evaluate whether they seem supported. Not to become a critic themselves; to be a capable audience for criticism of the original.

This is the thesis statement of the system. It is stronger than content-faithfulness or voice-faithfulness individually: it requires that the abridgment preserve the textual material any plausible critical reading works with, not just the plot and register. For canonical works this means the critical touchstones are non-negotiable; for less-critiqued works the bar devolves to preserving the kind of material any reading would need (thematic content, formal features, character psychology, narrative framing, historical/contextual markers).

The abridgment must not itself be interpretive. It preserves the textual material criticism engages with and leaves interpretation to the reader.

---

## Input / output

**Input:** A single plain-text file containing the full book. UTF-8 encoding assumed; both Unix and Windows line endings accepted. The system must identify and exclude non-book content (Gutenberg preamble/postamble, licensing boilerplate, transcriber credits) before the pre-pass operates on the text. Misidentifying boilerplate as chapter content contaminates every downstream pass, so the boundary-detection step is critical.

**Output:** A single plain-text file containing the abridged book. No separate metadata files; any metadata the system wants to emit (modernization level applied, confidence notes, validation results) is embedded in the output file as a clearly-demarcated header or footer.

## Scope constraints (v1)

- **Copyright:** Out-of-copyright books only. This removes fair-use constraints on verbatim preservation, which matters because faithful abridgment of a stylistically distinctive author benefits from preserving actual sentences.
- **Resources:** No hard time or compute budget. Multi-pass, multi-agent, regeneration loops are all in scope. "No constraints" means permission, not mandate — system design should still apply reasonable engineering judgment.
- **Edition:** The system abridges whatever text it is given. No edition selection, no identifying which edition is "best." If the input is a scholarly edition with editorial apparatus, the system must handle that (treat apparatus as non-book content to exclude, or handle case-by-case per the front/back matter policy).

## Architectural commitments

- **Global plan pre-pass.** The system produces a global plan artifact before any chapter-level work begins. The plan is inspectable and contains: signature inventory (cultural and textual), motif inventory, compression schedule per chapter, modernization level, structural-feature flags, cross-chapter dependencies, and chapter-level word budgets. Every downstream pass references the global plan; chapter-level passes do not operate independently.
- **Chapter-by-chapter execution under global plan.** Drafting happens per chapter, but within the constraints and references the global plan established. This is the explicit defense against breadth-first drift.

## Operational constraint

The system runs **fully autonomously** on an arbitrary book. No human intervention from input to finished abridgment. The per-book preservation spec — identifying what in this specific book must be preserved — is authored by the LLM in a pre-pass, not by a human curator.

External software (written as part of this system) is available to supplement the LLM. **Sub-agents and multi-LLM passes are in scope** — the system can decompose into specialized roles (signature detector, abridger, critic, etc.) and use generate-critique-regenerate loops. **Reproducibility is preferred but not a hard requirement** — generation stochasticity is acceptable where judgment lives, deterministic tooling preferred where measurement lives.

This creates a division of labor:

- **Tools do measurement.** Deterministic text analysis: sentence statistics, structural parsing, concordance, word counts, motif frequency, comparative analysis against reference corpora.
- **LLM does judgment.** Identifying which measured features are signature-level; deciding what to preserve/paraphrase/cut; generation of the abridged prose; cultural recall.
- **Tools do enforcement.** Validation hooks that check output against the per-book spec and reject non-compliant output, forcing regeneration rather than letting bad output ship. The spec is inspectable; compliance is mechanically checkable.

The boundary matters: text-derivable properties (prosodic, structural, motif-frequency) *must* flow through tooling, not LLM inference. LLM-only measurement of things tools can measure deterministically is a reliability regression.

## Validation

Validation operates at three scales with distinct mechanisms and failure modes. Conflating them misses failures that can only be caught at the appropriate scale.

### Scale 1: Pre-drafting (validating the plan)

Before any segment is drafted:

- **Signature set diversity check.** The identified signature inventory covers multiple plausible critical readings, not just one. Defends against reading-privileging failure.
- **Compression schedule feasibility.** Sum of segment allocations is internally consistent; no segment is allocated impossibly-aggressive compression given the signatures identified within it.
- **Pre-pass independent replication.** Signature identification is run independently two or more times; agreement is measured. High agreement = high confidence. Disagreement flags uncertain regions, handled conservatively (less aggressive compression there).
- **Structural classification decision.** The book is confirmed as pipeline-compatible, or the system refuses here (before drafting work is wasted).

### Scale 2: Per-segment (during drafting)

After each segment draft:

Mechanical:
- Identified signatures assigned to this segment are present in the draft (string match).
- Word count within tolerance of plan target.
- Period spellings preserved verbatim (pattern match against pre-pass inventory).
- Segment title preserved.

LLM-critic:
- Voice fidelity (source-aware): source and draft style compared; flag flattening, sentimentality injection, explanation insertion, modernization-beyond-configured-level.
- Semantic fidelity (source-aware): flag hallucination, plot omission, character-motivation loss.
- Cross-reference integrity: callbacks in this segment have preserved setups; setups in this segment that will be called back later are preserved.

### Scale 3: Post-drafting (end-to-end)

After all segments are drafted:

Mechanical:
- **Concordance comparison** for every identified motif: occurrences-per-1000-words in source and abridgment; flag significant divergence. Catches motif depletion directly.
- **Style-distribution comparison**: sentence-length histogram, punctuation density, vocabulary richness for source and abridgment; large deviations flag voice flattening at aggregate level.
- **Structural coverage**: every source segment has a corresponding output segment.

LLM-critic:
- Pacing coherence (read across segments, flag lurches in compression or tone).
- Character arc coherence (each major character develops consistently; voice is stable).
- Narrative coherence (the book reads as a single artifact, not a concatenation).

**Success Criterion validation (structured test):**
- Sample real criticism of the source text across multiple interpretive traditions (formal, political, psychological, thematic).
- For each piece of criticism, use the abridgment as sole context for a critic-LLM tasked with explaining or evaluating the claim. Compare against the same operation using the full source.
- Convergence indicates the Success Criterion is met for that piece of criticism; divergence flags under-preserved material.
- Coverage across interpretive traditions catches reading-privileging failures.

### Critic pass design

Resolved design commitments:

**Framing: all diagnostic critics adversarial.** Each critic's task is to find the worst instance of its failure type in the input. Constructive/approval framing produces bland diagnoses that give the re-plan path no traction. A synthesis step over all critic outputs handles overall assessment at the emission gate; it aggregates, does not re-evaluate.

**Vantage: source-aware for most, abridgment-only for specific critics.** Different failures detect at different vantage points. Source-aware critics catch semantic drift from the original; abridgment-only critics simulate the first-time reader and catch failures source-aware critics can't see (unexplained callbacks, pacing problems invisible when you know what was cut).

**Specialization: ~8 narrow critics.** Each has a specific failure vocabulary and produces diagnoses with location information. Current roster:

| Critic | Vantage | Scale | Hunts for |
|---|---|---|---|
| Voice | Source-aware | Segment + E2E | Flattening, sentimentality injection, explanation insertion, register homogenization, modernization-beyond-level |
| Semantic fidelity | Source-aware | Segment | Hallucination, plot omission, motivation loss, cross-reference severing |
| Signature/motif | Source-aware | Segment + E2E | Missing signatures (LLM-verified); motif frequency divergence from source |
| Character arc | Source-aware | E2E | Voice inconsistency across segments; arc-compression damage |
| Thematic preservation | Source-aware | E2E | For each identified thematic strand, whether the abridgment preserves engaging material |
| Pacing coherence | Abridgment-only | E2E | Compression lurches, tonal shifts between segments |
| Narrative coherence | Abridgment-only | E2E | Unexplained references, orientation failures, lost setups |
| Success Criterion | Hybrid | E2E | Whether sampled criticism across traditions is supportable from abridgment alone |

**Redundancy: N=3 independent runs per critic, severity-weighted failure rules.**

- **High-stakes failures** (signature loss, hallucination, identified-motif depletion, voice erasure in a signature passage): any single critic run finding the failure triggers regeneration. False positives are cheaper than false negatives for these.
- **Lower-stakes failures** (pacing lurches, mild thematic thinning, minor voice issues): 2-of-3 agreement on the same issue location triggers regeneration. Protects against single-critic noise.
- **Informational flags**: logged for diagnostic context; never trigger regeneration.

Independence across runs: prompt variation (different example failures, different phrasings), with model-class variation used where feasible. Shared-blind-spots between generator and critic is the most serious critic design risk; running N=3 with variation mitigates without eliminating it.

**v1 stance on critic independence:** use what's available — prompt variation is reliable, model-class variation opportunistic. Accept the shared-blind-spots residual risk for v1.

**Future improvement:** validation quality improves materially if critics run on independent LLMs (different providers, different architectures). This is a v2 target, not a v1 requirement.

**Diagnostic specificity requirement (reiterated):** every critic's output must be actionable. "This abridgment fails X" is insufficient; "this abridgment fails X because passages A, B, C were compressed past threshold" is required. The re-plan path is only useful if critics provide real priors.

**Cost note:** for full-length-novel sources, this design produces on the order of thousands of per-segment critic outputs and tens of end-to-end outputs per run. Validation work is comparable in scale to drafting work, possibly larger. This is intentional and acceptable given the no-resource-constraints permission, but worth being explicit about.

### Meta-validation

How we know validation is working:

- **Mechanical checks** are tested against synthetic positive/negative cases (injected violations, verified compliance).
- **Critic pass reliability**: cross-critic agreement on multiple independent runs; adversarial testing (have a generator try to pass a critic while actually violating spec); regression testing against previously-validated abridgments once they exist.
- **Critic blind-spot risk**: the generator and critic may share systematic biases if from the same model class. Mitigations: use different model classes for critic when possible; include adversarial critics specifically hunting for bias-pattern failures; always run mechanical checks even when critics approve.

### Failure handling

- **Per-segment validation failure:** regenerate with specific failure feedback. Retry budget per segment (e.g., 5 attempts). On budget exhaustion: halt with diagnostic.
- **End-to-end validation failure after all segments passed individually:** re-run pre-pass with the failure pattern and the failed abridgment as explicit inputs, regenerate, re-validate. Retry budget at pre-pass level is 1 — a single principled re-plan. If the second run also fails end-to-end, halt with full diagnostic including both attempts.

The re-plan takes as context: (a) the original source, (b) the failed abridgment, (c) structured diagnoses from the end-to-end critics specifying what was under-preserved or over-cut. The pre-pass uses this as prior information to adjust the signature inventory and compression schedule, not merely to retry. Without new information, a retry would have the same failure mode as the original run.

This is the "fail-loud" philosophy applied correctly: don't ship broken output, but do use validation's own diagnosis before giving up. A retry with no new information would be stochastic hope; a re-plan with the failure pattern as input is a principled recovery attempt. Halting on first failure would throw away information validation produced.

All pre-pass outputs, validation results, and diagnostic traces are logged across both attempts so the state is fully reconstructible for human review when the fallback halt triggers.

## Preservation targets

### 1. Universal structural/narrative (every English-language novel)

These must be preserved or the output is a summary, not an abridgment:

- Plot / narrative arc
- Character identities and arcs (including interiority where it exists)
- POV and narrator stance (first/third/omniscient; reliable/unreliable; ironic distance)
- Setting (geographical, temporal)
- Chapter or section structure and titles (where present — the book's native structural segmentation and its markers; see Structural Segmentation section)
- Tone

### 2. Signatures (universal category, per-book instances)

Every novel has signatures. Identifying the specific instance set is a per-book job for the LLM pre-pass. Signatures originate from four sources — a passage qualifies if it satisfies any one:

- **Cultural famousness** — quotes that have escaped the book into the culture. Identifiable via cultural recall and external lookup.
- **Textual distinctiveness** — passages the pre-pass identifies as prosodically or stylistically signature (rhetorical density, unusual construction, thematic compression). Identifiable via textual analysis.
- **Critical engagement** — passages the critical tradition returns to, even if not commonly quoted. Identifiable via cultural/critical recall of the book's reception.
- **Interpretive weight** — material that specific readings depend on, even when no individual passage is famous. Narrative framing material for narrative-theory readings; formally distinctive passages for formalist readings; psychologically articulate passages for psychoanalytic readings. Identifiable via knowledge of what critical readings of the work engage with.

Categories of signatures (cutting across the four origins):

- **Quotable lines** — aphoristic, structurally prominent, culturally escaped.
- **Prosodic signatures** — sentence-length distribution, punctuation rhythm, syllable patterns where metrical.
- **Structural signatures** — chapter length patterns; opening/closing conventions; frames, footnotes, embedded documents.
- **Voice signatures** — archaic diction, invented vocabulary, dialect, register shifts.
- **Character signatures** — catch-phrases, speech tics, articulation-points of psychology.
- **Thematic/imagic signatures** — recurring motifs, symbol systems, color/weather/time patterns.
- **Narrative signatures** — frame stories, structural conceits, tone shifts at pivotal moments.
- **Critical-touchstone signatures** — passages the critical tradition engages with.
- **Interpretive-hook signatures** — textual material load-bearing for identified readings.

Preservation rule: identified signatures are preserved verbatim or as close to verbatim as compression allows; paraphrase is not permitted to erase a signature. The abridgment must not privilege one interpretive tradition over others — preserve the textual material different readings depend on, not a reading itself.

### 3. Variable weights (per-book assessment required)

How load-bearing each dimension is for the specific book. Drives compression aggressiveness:

- **Prose style as artifact.** High for Nabokov, Woolf, McCarthy. Low for transparent plot-driven prose.
- **Digression / indirection.** Load-bearing in Tristram Shandy, Eliot. Skippable in tight commercial fiction.
- **Genre-specific load.** Mystery clues and reveal timing; SFF worldbuilding and coined vocabulary; romance emotional beats; historical research texture; satire's specific jokes; gothic atmosphere.

### Cross-cutting axes

- **Era** — primary driver of period-language activation in signatures and voice preservation.
- **Structural complexity** — affects both preservation targets and chunking strategy for processing.
- **Era-accumulated difficulty** — how much of the source's difficulty is era-accumulated (vocabulary/syntax that was ordinary when written but obscure now) vs. author-intended (archaism as deliberate feature). Measurable deterministically via obsolete-vocab density and syntactic distance from contemporary prose. Feeds into modernization level default.

## Non-personalization constraint

**v1:** The system produces **one canonical abridgment per book**. No per-reader customization, no user-configurable parameters at run time. Reader profile is a system-level design commitment, not a runtime input.

**Future:** Per-reader customization is anticipated but deferred. Design principle: parameterize the reader axis, fix its value for v1. Keep the reader concept explicit in the spec, prompts, and tool interfaces so that later variation is adding values to an existing parameter rather than refactoring hardcoded assumptions.

**Implicit target reader (v1 fixed value):** a generally educated adult reading fiction for its own sake — not for a class or specialist study. Willing to look up occasional words, unwilling to wrestle with sentences. Broadly familiar with canonical literature but not a specialist. This is the broadest audience for a faithful abridgment (someone approaching a classic they haven't read) and among the more demanding (wants the reading experience, not just content).

All system-level decisions (modernization thresholds, signature-famousness criteria, compression aggressiveness, whether to preserve ambiguity) are calibrated for this reader. When the reader axis is unfrozen later, these calibrations become functions of reader profile, not constants.

## Modernization axis

"Faithful" has two senses that usually align but can come apart: faithful-to-surface (preserve language as-written) and faithful-to-experience (give the modern reader something close to the original reader's experience). For high era-accumulated-difficulty works (Shakespeare, Chaucer, some 17th-c prose), these come apart — period preservation adds difficulty that wasn't in the original experience. For low era-accumulated-difficulty works where archaism is author-intended (Nabokov, for example), they align.

Modernization is therefore a transmutation axis — but per the non-personalization constraint, the level is **automatically determined** by the pre-pass from the book's era-accumulated-difficulty score, calibrated for the implicit target reader. Not a user parameter.

Levels:

- **L0 None** — strict period preservation, orthography included.
- **L1 Light** — standardize OCR/typesetting artifacts only. Minimal intervention.
- **L2 Vocabulary** — replace genuinely obsolete vocabulary. Keep syntax and register.
- **L3 Vocabulary + syntax** — update inverted clauses, comma-splicing, obsolete grammar. Recognizable register but period rhythm lost.
- **L4 Full** — contemporary prose throughout. Voice substantially replaced.

Expected distribution for English novels with the implicit target reader:
- Most 19th-c and later novels → L0 or L1.
- Pre-1800 prose → L2 possible.
- Pre-1700 prose → L3 may be justified.
- Pre-1500 prose or verse → system should refuse: "this is a translation problem, not an abridgment problem."

Rules across all levels:

1. **Signatures preserved verbatim regardless of level.** Signatures are identity markers, not modernization candidates.
2. **Level is derived by the pre-pass, not chosen.** Era-accumulated-difficulty measurement is a deterministic tool operation.
3. **At L3+, voice preservation goals are fundamentally compromised** — output metadata declares the modernization level so the reader understands what they're getting. The spec does not claim to preserve voice at L3 or above.
4. **Refusal is a valid output.** If the book is too far outside the currently-configured reader's domain (e.g., Chaucer for the v1 general reader; heavy verse; works whose difficulty is irreducible for the target reader), the system emits a refusal with reasoning rather than silently producing unfaithful output. Refusal is reader-relative — a future reader profile could accept books the v1 profile refuses.

---

## Goal

Produce a faithful abridgment of an arbitrary English-language novel within the scope constraints above. "Faithful" here means faithful to **voice, structure, digressive character, and critical substance** — sufficient to meet the Primary Success Criterion. A plot-only version is a different project.

Word-count targets are derived per-book by the pre-pass from the source length and the non-uniform compression schedule (below), not fixed globally. When the Success Criterion and the derived word-count target conflict, the Success Criterion wins. The system should not cut critically-engaged or signature material to hit a word count; the derived target is a soft anchor, not a hard maximum.

## Compression schedule (non-uniform)

Compression ratio is allocated by chapter type, not applied flat:

- **Signature chapters** — ~3x. Openings, closings, pivotal set-pieces, culturally famous passages, chapters the critical tradition engages with. Cut tightly but preserve the shape and most of the voice.
- **Narrative chapters** — ~4x. Standard plot and character progression.
- **Digressive chapters** — ~6–8x. Tangents, essayistic interludes, taxonomic or technical material, extended asides. Compress hard but do not eliminate — for books where digression is load-bearing (see Variable weights), the digressive mode is part of the book's character and cannot be removed wholesale.

The signature-chapter list is per-book and provisional; it should grow as chapters are encountered during drafting.

## Approach: hybrid splice-and-paraphrase

- **Preserve verbatim:** famously distinctive passages, iconic phrases, signature voice moments, period markers.
- **Paraphrase in style:** connective tissue, redundant elaboration, repeated points made once.
- **Cut:** extended tangential asides when the indirection budget (below) has room.

Pure splice (only the source author's actual sentences, stitched) has a hard compression floor and reads choppy below ~2x. Pure paraphrase flexes further but drifts into pastiche. Hybrid is the default.

## Voice preservation rules

1. **Preserve period spellings verbatim.** Archaic or historical orthography stays as printed. Do not modernize. The temptation to clean up pre-contemporary spelling is strong and is the wrong instinct.
2. **Preserve archaic vocabulary.** If a word is period-distinctive or marked, keep it. If the reader needs a footnote, that's fine; don't paraphrase away the word.
3. **Preserve the source's punctuation idiosyncrasies.** Semicolons, em-dashes, italics for emphasis. These are part of the rhythm.
4. **Preserve the register.** Period cadence, sudden philosophical pivots, deadpan comic turns, sermonic or aphoristic modes where present. If a paraphrased sentence sounds like 2020s prose when the source does not, it's wrong.
5. **Preserve temporal signatures.** References to contemporary events, people, and places of the source's period stay even if unfamiliar. Don't substitute a modern analogue; don't gloss a period-specific allusion.

## Indirection budget

For books where digression or philosophical aside is identified as load-bearing (see Variable weights), always-cutting-the-tangent falsifies the book's character even when every mechanical check passes. In such books, each chapter should preserve at least one digression or philosophical aside in compressed form, even when aggressive cutting is called for. Which one is an editorial choice; *that* there is one is a rule.

## Chapter-level workflow (interactive phase)

Per chapter:
1. Read source.
2. Identify: signature passages (preserve), essential plot/argument (preserve in paraphrase), digressions (compress or cut per budget).
3. Draft at target ratio for that chapter type.
4. Trace: note what was preserved verbatim, what was paraphrased, what was cut.
5. Flag any editorial judgment call worth reviewing.

## Open questions

Resolved (retained for audit):
- ~~Who is the reader?~~ Implicit target reader hardcoded for v1; parameterized for future variation.
- ~~Failure mode catalog.~~ See Failure Modes section.
- ~~Global plan vs chapter-by-chapter?~~ Global plan committed.
- ~~Input/output formats?~~ Single plain-text file each.
- ~~Copyright posture?~~ Out-of-copyright only, v1.
- ~~Resource constraints?~~ None, v1.
- ~~Edition choice?~~ System processes whatever text is given.
- ~~Error recovery policy?~~ Fail loud — system halts with diagnostic, no degraded output.
- ~~Front matter / back matter policy?~~ Per-segment classification (diegetic / extradiegetic / ambiguous) by the pre-pass; no blanket rule.
- ~~Non-standard chapter structures?~~ Resolved by the structural-segmentation reframe: pre-pass identifies native segmentation, chapters are one common case, not required.

Still open:
- ~~**Is validation mechanical-only, or also LLM-critic-pass?**~~ Effectively resolved by the Primary Success Criterion: mechanical validation cannot evaluate whether the abridgment supports critical engagement (which is inherently interpretive), so an LLM-critic pass is required. The remaining question is design — what specifically the critic evaluates and how.
- **Play-format and similar register-shifting chapters.** Either specialized sub-agent or case-by-case handling under the global plan's structural flags.
- **Cross-segment setup** — if a minor character is introduced in a cut passage and referenced later, how does the global plan catch this before it becomes a problem?

## Error recovery

The system fails loud, not graceful. Validation failures do not produce degraded output. Specifically:

- **Chapter-level validation failure after retry budget exhausted:** system halts on that chapter, emits a diagnostic, requires human review. No best-effort emission of broken chapters.
- **Pre-pass self-validation failure:** system halts before chapter drafting begins.
- **Structural incompatibility** (see below): system refuses the book with reasoning.
- **Reader-domain mismatch** (book too hard for v1 reader profile): system refuses with reasoning.

The output domain is therefore: *a faithful abridgment* OR *a diagnosed stop*. Nothing in between.

## Front matter, back matter, and apparatus

A single policy doesn't work because some apparatus is part of the fiction and some isn't. The pre-pass classifies per segment:

- **Diegetic** (part of the narrative — fake prefaces, framing documents, integrated footnotes): treated as chapters under normal abridgment rules. Examples: the John Ray foreword in *Lolita*; the Custom-House preface in *The Scarlet Letter*; the editorial apparatus in *Pale Fire*; the endnotes in *Infinite Jest*.
- **Extradiegetic** (apparatus around the fiction — editor's notes, scholarly annotations, translator's notes, third-party introductions, critical afterwords, author biographies): cut. Not "the book" being abridged.
- **Ambiguous** (author's own preface, dedications, epigraphs): defaults — preserve dedications and epigraphs verbatim; cut author prefaces unless the pre-pass identifies them as diegetically integrated.

Classification signals the pre-pass can use: does the segment narrate events; third-person references to the novel vs. first-person narrative voice; authorship (novel's author vs. editor/scholar); whether the book's structural coherence depends on the segment.

## Structural segmentation

The pre-pass identifies the book's **native structural segmentation** — whatever divisions the book itself uses. Chapters are the most common case but not required. Alternatives the pre-pass must handle: parts with nested chapters, numbered sections without titles, symbol-delimited scene breaks, titled sections, date/time headers (epistolary/diary form), and unbroken prose.

Terminology below: a **segment** is whatever unit the pre-pass identifies. In a chaptered novel, segments are chapters; in a scene-broken novel, segments are scenes.

**Segmentation granularity.** The pre-pass selects the coarsest native segmentation that yields reasonably-sized processing units. Multi-level hierarchies (parts containing chapters containing sections) are preserved in the output, but the working granularity for compression is one level — typically chapters if present.

**Unsegmented books.** If a book has no native structural markers, the pre-pass performs semantic segmentation (identifying scene or topic shifts). If semantic segmentation is unreliable for the text, the book may process as one large unit with context-fit chunking. Output preserves the source's lack of structural markers.

**Compression granularity ≠ structural granularity.** Compression can be allocated sub-segment where appropriate. A chapter that mixes signature prose with technical or taxonomic material, for example, benefits from this: signature passages compress less than the technical passages, within the same chapter. The global plan allocates compression at whatever granularity is most faithful — per segment by default, finer where signatures cluster non-uniformly within a segment.

## Structural-type classification

Before compression planning, the pre-pass determines whether the book's form is compatible with segment-by-segment faithful abridgment:

- **Sequential segmentable structure** (chapters, sections, scenes, or clearly-identifiable semantic units): proceed.
- **Non-linear cross-referential structure** (*Pale Fire* as canonical example) where segments cannot be abridged independently because they deeply reference each other in non-sequential ways: refuse with reasoning. The segment-by-segment pipeline would sever the cross-references that constitute the work.

Structural refusal is a refusal trigger distinct from the reader-relative one. Reader-relative refusal: "too hard for this reader." Structural refusal: "form incompatible with sequential segment-based abridgment regardless of reader."

## Failure modes

The system must explicitly defend against these. Defense mechanism noted per category.

### Critical-engagement failures (abridgment works but cannot support the success criterion)
- **Critical-engagement loss** — abridgment is content-faithful, voice-preserved, and mechanically valid, but a reader of it cannot follow criticism of the original because the specific passage a critic works with was compressed past usefulness. Passes all mechanical checks.
- **Reading-privileging** — pre-pass over-weighted one interpretive tradition and under-preserved material other readings depend on.
- **Thematic flattening** — digressive chapters compressed as elaboration when they actually carried the book's thematic content.

*Defense: LLM-critic pass specifically evaluating whether the abridgment supports critical engagement; pre-pass diversity check (does the identified signature set cover multiple plausible readings, not just one); conservative compression on digressive chapters that the critical tradition engages with.*

### Fidelity failures (output diverges from source)
- **Hallucination of connective content** — invented bridging between cut passages.
- **Plot omission** — essential causal information lost in cuts.
- **Character omission** — minor characters referenced later without preserved setup.
- **Cross-reference severing** — setup cut while callback retained, or vice versa.
- **Motif depletion** — symbolic recurrences reduced below legibility threshold.

*Defense: mechanical validation (signature inventory + motif tracking), cross-chapter state tracking, critic pass.*

### Voice failures (register wrong even when content right) — LLM-systematic biases
- **Flattening toward neutral prose** — distinctive register lost to grammatical clarity.
- **Modernization beyond configured level** — period orthography, vocabulary, punctuation updated beyond what the modernization axis permits. (Modernization itself is not a failure; only exceeding the configured level is.)
- **Sentimentality injection** — contemporary emotional vocabulary added.
- **Explanation insertion** — source's deliberate opacity clarified away.
- **Dialect cleanup** — speech patterns standardized.
- **Register homogenization** — deliberate register shifts averaged to a middle register.
- **Parallel construction asymmetry** — partial cuts within a sentence that break a grammatical or rhetorical parallel ("considering that X, and that Y" with Y removed; "not only A but also B" with B removed). The surviving clause reads as awkwardly weighted because the construction expected a counterpart. Defense rule: when cutting within a sentence, either cut the whole sentence or preserve its parallel structures intact.

*Defense: critic pass specifically hunting LLM biases; prompt structure counteracting them; mechanical checks for period-language preservation.*

### Structural failures (book's shape misrepresented)
- **Compression pacing lurches** — inconsistent compression ratios across chapters.
- **Digressive-character erasure** — always cutting the tangent.
- **Proportion drift** — source-to-abridgment chapter length ratio inconsistent.
- **Chapter title loss or alteration.**

*Defense: mechanical validation (compression accuracy per chapter, chapter title preservation), global pacing plan in pre-pass.*

### Signature failures (identified features not preserved)
- **Quote loss** — famous/identified quotes paraphrased or cut.
- **Stylistic-tic erasure** — prosodic signatures smoothed.
- **Aphoristic compression loss** — tight maxims diluted in paraphrase.

*Defense: mechanical validation (string match on signature inventory), critic pass for aphoristic fidelity.*

### Continuity failures (global coherence broken by local decisions)
- **Spec drift across chapters** — later chapters forget earlier decisions (breadth-first drift).
- **Character voice inconsistency** — same character sounds different across chapters.
- **Thematic forgetting** — theme established early fails to resonate late because echoes were cut.

*Defense: global plan authored in pre-pass and referenced by every chapter pass; cross-chapter critic pass after chapter drafts complete.*

### Operational failures (system fails without knowing)
- **Silent failure** — output emitted without flagging validation issues.
- **Pre-pass contamination** — pre-pass missed major signatures; entire downstream run self-consistently wrong.
- **Over-confidence on unknown books** — full-aggression processing when cultural recall is thin.
- **Spec-output mismatch** — spec says preserve X; output doesn't; no check caught it.

*Defense: self-critique of pre-pass (multiple independent signature-detection passes, or LLM critique of its own spec); confidence metadata attached to output when cultural knowledge is thin; mechanical spec-compliance gate before emission.*

### Priority note

- **LLM-systematic biases** (voice failures) are the highest-frequency category because they're systematic rather than random. Defending against them is the main job of any critic pass.
- **Operational failures** are the highest-stakes category because they produce confidently wrong output with no surface signal. Worth investing disproportionately in pre-pass self-validation.

## Decisions log

- **2026-04-18:** Non-uniform compression schedule committed (see Compression schedule section for per-chapter-type ratios).
- **2026-04-18:** Hybrid splice/paraphrase as default approach.
- **2026-04-18:** Period spellings preserved verbatim.
