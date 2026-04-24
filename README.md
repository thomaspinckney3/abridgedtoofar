# Forage

A faithful book abridgment pipeline. Takes a full-length book as input and produces a shorter, readable version that preserves the author's voice, distinctive phrasing, and interpretive weight — not just plot.

The canonical design target lives in [`spec/ABRIDGMENT_SPEC.md`](spec/ABRIDGMENT_SPEC.md). The pipeline is a concrete implementation of that spec.

## What makes this different from "summarize it"

Most summarizers strip out everything except plot events. A faithful abridgment preserves:

- **Voice** — the narrator's register, rhetorical habits, ironic asides.
- **Signatures** — culturally famous passages, prosodically distinctive sentences, the interpretively load-bearing bits.
- **Stance** — first-person/third-person, reliable/unreliable, ironic distance.

A reader who loves the original should feel the abridgment is the same book, shorter — not a different book that happens to share the plot.

## Pipeline stages

```
split → classify → plan → summarize → cuts ──┐
                                              │
                      (cuts.json feeds into  ▼ drafter)
                     
                   draft → assemble → book-critique          ◄── default pipeline
                     │
                     └──► proofread (post-hoc)               ◄── opt-in, recommended

                   critique + iterate (draft → regen loop)    ◄── opt-in
                   coherence (adjacent-pair structural check) ◄── opt-in
                   validate (motif/style mechanical checks)   ◄── opt-in
```

Default pipeline is **draft-only + book-critique**: the Opus drafter with extended thinking handles referent-chain integrity during generation, and the book critic verifies synopsis preservation at the end. The iterate loop (signature critic + regen) and coherence critic are opt-in — empirically they whack-a-mole on voice-dense prose and have low recall on the worst compression-induced breaks (cross-chapter antecedent loss). The proofread tool + human review is the recommended quality surface.

Every stage has a CLI subcommand. All stages operate on files under `work/<book_id>/`, so they're inspectable and rerunnable.

### 1. `split` — deterministic chapter split

Zero-LLM. Reads the source and emits `chapters.json` + one `chapters/NNN.md` file per chapter. Two backends:

- **Regex splitter** (`forage/chapter_split.py`) — for plain-text Project Gutenberg sources. Finds CHAPTER/ROMAN/digit headings, strips TOC duplicates, filters <30-word fragments. Pluggable `toc_algorithm` config: default `keep_last` (dedupes repeated heading text, works for most books), alternative `block_run` (drops dense runs of heading matches — needed for multi-part books like Don Quixote whose Part I and Part II both carry "CHAPTER I." bodies). Per-book overrides go in `books/<id>/split_config.json`.
- **EPUB reader** (`forage/epub_reader.py`) — for structured EPUBs. Uses the spine and heading-aware section splitting to identify chapters. Good for clean EPUBs (self-pub + some Gutenberg variants).

Both emit the same `chapters.json` shape, so downstream stages don't care which ran.

### 2. `classify` — LLM chapter classifier

One LLM call per book (~$0.01–$0.20 on Sonnet). Decides whether each splitter candidate is:

- `diegetic` — real narrative chapter, keep
- `extradiegetic` — editor's preface, translator's note, copyright page, illustrations list: cut
- `toc_fragment` — a leaked TOC entry (usually <100 words): cut
- `cut_for_review` — unclear, human review (rare)

Writes `work/<book>/chapter_classifications.json`. The lean planner reads this file to override the kind-based heuristic.

Auto-invoked by `plan` on first run; cached thereafter. Replaces the brittle word-count + filename heuristics we had before.

### 3. `plan` — deterministic lean plan

Zero-LLM itself; auto-invokes `classify` if `chapter_classifications.json` is missing. Builds `plan.json`:

- Book-level target from `forage/compression.py` — a log-scaled reading-time formula: 1 hour at 24k source words, 5 hours at 600k, 200 wpm.
- Per-chapter targets apportioned by chapter source share of total **diegetic** words. Rounded up to nearest 100.
- **Merge groups**: adjacent short chapters (per-chapter target < 1500w) get bundled into super-segments up to 2000w combined target. On books with many short chapters (Moby Dick, Bleak House) this lets GPT-5 find real compression instead of hitting its natural 1.2× floor on short inputs.
- Extradiegetic and toc_fragment entries marked `target_word_count=0`, cut at draft time.

### 4. `summarize` — ~30-sentence prose book synopsis

One (or a few) LLM calls per book. Produces a flowing-prose plot synopsis (~30 sentences, paragraph-structured) used as ground truth by the book-level critic and the cuts prepass. Earlier versions produced 15 sentence-per-line bullets; the prose format gives the downstream stages a more complete, naturalistic shape to hold to.

For books that fit GPT-5's ~272k input context (everything up to ~178k source words, ~13 of our 16 books), a single call writes `work/<book>/book_synopsis.md`.

For longer books, the summarizer does chunked chaining: split diegetic source at chapter boundaries into N roughly-equal chunks, produce a partial synopsis per chunk, merge into one ~30-sentence prose whole-book synopsis. N=2 for Moby Dick / Little Women / Education / Bleak House; N=3 for Don Quixote.

Runs once per book; cached. Independent of the drafting stage — can be generated before any chapter drafts exist.

### 5. `cuts` — removable-material inventory

One LLM call per book (GPT-5, ~$1–2). Using the ~30-sentence prose synopsis as the authoritative shape of the book, the prepass identifies three categories of material a careful abridger could remove without materially changing the reader's sense of plot, themes, or principal-character arcs:

- **minor_characters** — named figures whose removal wouldn't affect major arcs (party guests, one-scene hosts, background functionaries)
- **subplots** — self-contained or thematically parallel side narratives not structurally necessary
- **digressions** — essayistic, taxonomic, technical, or descriptive passages that don't advance plot

Each entry requires a one-sentence `reason_removable`. The prompt has an explicit "bias toward preservation" rule — a short, confident inventory is more useful than an inflated list.

Writes `work/<book>/cuts.json`. Consumed by:
- the drafter prompt (explicit "prefer cutting these" block)
- the signature critic prompt (authorized removals — don't flag their absence as voice_erasure)
- the coherence critic prompt (residual seams from authorized cuts are expected, not findings)
- the regen prompt in iterate (cuts override critic findings when they collide — the drafter may still restore *severable* non-cut voice tics that lived inside a cut scene)

Gatsby example output: 16 minor characters (Owl Eyes, Klipspringer, Catherine, etc.), 9 subplots (Pammy's cameo, Jordan's golf-cheat flashback, Michaelis's overnight vigil), 7 digressions (the Ch 4 guest-list "timetable," Wolfshiem's Metropole reminiscence, Nick's Midwestern homecoming reverie).

### 6. `draft` — Opus drafter (spec-as-prompt)

Default model: `anthropic:claude-opus-4-7` (routable via `FORAGE_DRAFT_MODEL`). The drafter auto-enables max extended thinking whenever the active model is an Opus variant — thinking tokens substantially improve referent-chain integrity under compression (e.g. cutting a character's introduction without orphaning later pronouns that depend on it).

The drafter prompt (`prompts/draft_lean.md`) is the abridgment spec + chapter source + (if present) the cuts inventory. The model reads the spec and writes the chapter; no per-chapter signature enumeration, no tier scaffolding. Output goes to `work/<book>/segments/<NNN>.md`.

The system prompt instructs the drafter to preserve standard fiction paragraph conventions — each new speaker's dialogue turn goes in its own paragraph. (A post-hoc `forage.dialogue_split` tool also fixes older drafts that concatenated dialogue under compression pressure.)

**Merge-group initial drafting**: when `draft` is called for a segment that belongs to a merged group, it renders a multi-source prompt covering all group members, calls the LLM once, and splits the output (`## Chapter N` delimited) back into per-member `.md` files. Non-first members of a group are read from disk; no redundant LLM calls.

**Fallback**: if OpenAI returns `stop_reason=content_filter` (on the drafts where a user-configured `FORAGE_DRAFT_MODEL` routes to OpenAI), the drafter transparently retries on Anthropic (`FORAGE_DRAFT_FALLBACK_MODEL`, default Sonnet). The [llm] log line shows the provider switch.

GPT-5 is still a supported option via `FORAGE_DRAFT_MODEL=openai:gpt-5` — it's ~3–5× cheaper per draft but produces more compression-induced dangling references (Gatsby Ch 1 test: Opus preserved the Jordan and daughter antecedents that GPT-5 cut).

### 7. `critique` — adversarial signature critic

Default model: `anthropic:claude-sonnet-4-6` (routable via `FORAGE_CRITIC_MODEL`).

Prompt: `prompts/critic_signature.md`. Hunts for voice-establishing prose, culturally famous passages, and interpretively load-bearing moments that are **absent, paraphrased, or flattened** in the draft. Emits a JSON findings list with severity (high/medium/low) and per-finding fields: `source_passage`, `draft_treatment`, `why_it_matters`, `suggested_fix`.

If `cuts.json` exists the prompt includes the authorized-removals block — the critic is instructed not to flag absences of material on that list as voice_erasure. Non-cut material off the list is still fair game.

### 8. `iterate` — draft → critique → regenerate loop

Runs the critic on a draft, computes a verdict from the findings (any high OR ≥3 mediums → regenerate), and hands the **high+medium findings only** to the drafter's regen prompt (low dropped). The regen block asks for a roughly budget-neutral revision: for every restored passage, tighten lower-priority material (connective sentences, repeated elaboration, scene-setting without argument load, tertiary-character screen-time) of equivalent length — don't just add.

The regen prompt also includes the cuts-override clause: if a critic finding asks the drafter to restore material that lives inside an authorized-cut scene, the drafter skips it. The critic *may* still surface useful complaints about severable material *adjacent* to a cut (a pivot sentence, a signature phrase not tied to the cut scene) — the drafter uses judgment.

Per-iteration snapshots preserved: `NNN.iter0.md`, `NNN.iter1.md`, …, `NNN.critic_signature.json`, `NNN.iter1.critic.json`, …

Default `--max-retries` is **1** (so the loop runs at most: critic → maybe redraft, no verification critic after the final redraft — that final critic was always discarded).

### 9. `assemble` — assembly with budget report

Zero-LLM. Concatenates drafted segments into `work/<book>/abridgment.md` and writes `work/<book>/assembly_report.json` with budget stats: book target, ceiling, total drafted, overage (words and %), over_target/over_ceiling flags, and segments drafted/cut/missing.

Always emits `abridgment.md` when any drafted content exists. Budget adherence is reported, not gated — downstream stages (`book-critique`, `validate`) decide whether the produced abridgment is acceptable.

### 10. `coherence` — structural damage critic

One Sonnet call per adjacent chapter pair (~$0.02 each). Walks the drafted diegetic chapters pairwise and flags places where compression *structurally damaged* meaning — not places where the draft is merely less richly phrased than source.

Strict gate — only flags:
- Non-parseable sentences
- Dangling pronouns/demonstratives with no antecedent
- Broken logical pivots (cut side of a `but`/`yet`/`because`)
- Missing definitional glosses (the "observable in all sperm whales dying" case)
- Unattributed dialogue (reply without trigger question, speaker elided)
- Mid-scene jumps (chapter opens with "the waif-pole" etc. that prior draft didn't establish)

If `cuts.json` exists the prompt includes the authorized-removals block — residual seams left by authorized cuts (a dangling reference to a character who was cut, a stranded spatial reference to a removed scene) are expected and NOT findings. Only continuity breaks in material that should have survived get flagged.

Empirical numbers from the three books drafted with the cuts-aware pipeline: Dragon Maiden 0 findings / 15 pairs, Christie's *Secret Adversary* 12 findings / 28 pairs, Gatsby 11 findings / 8 pairs. Gatsby's higher hit rate reflects Fitzgerald's more allusive prose — some flagged items are genuine dialogue-turn drops, others are residues even the cuts-aware prompt doesn't fully suppress.

Writes `work/<book>/coherence_report.json`. Intended for human review — does NOT auto-feed regen. The post-assembly full-pipeline driver runs coherence automatically.

### 11. `book-critique` — per-synopsis-sentence verification

One LLM call on Sonnet (~$0.05). For each sentence in `book_synopsis.md`, checks whether the assembled abridgment contains evidence of that plot claim. Each sentence is classified:

- `present` — the abridgment covers this plot beat (right character, right event, right outcome)
- `missing` — no passage of the abridgment speaks to this claim
- `distorted` — event is mentioned but with a different outcome or material fact

Verdict: `ship` if all sentences are present, `hold` otherwise. Reads `abridgment.md` when present; falls back to a concatenation of `segments/NNN.md` with a `[PARTIAL]` marker so it can run mid-pipeline.

Writes `work/<book>/book_critic.json`.

### 12. `rebudget` (optional) — book-level reallocation

Reallocates per-segment targets if the assembled total is wildly off book_target.

### 13. `validate` — mechanical sanity checks

Zero-LLM. Motif concordance, style distribution (sentence length, em-dash frequency, vocab richness), signature fuzzy-match coverage. Flags depleted motifs and style divergence from source.

### 14. `proofread` — paragraph-level alignment viewer

One Sonnet call per chapter (~$0.15 each). For each chapter, aligns draft paragraphs back to their source paragraphs and classifies each as `verbatim`, `paraphrased`, `compressed`, or `unsupported`. Renders a self-contained HTML file at `work/<book>/proofread.html`:

- Color-coded blocks per classification
- Stacked draft ↔ source view for compressed pairs
- Inline word-level diff (using Python's `difflib`) for close pairs where a paragraph-scale edit isn't happening
- Collapsible "source paragraphs not mapped to any draft" section per chapter showing cut material
- `unsupported` flags likely drift / fabrication / cross-chapter movement

Alignments cache to `work/<book>/alignments/NNN.json` — re-running resumes from where it stopped. The `--render-only` flag skips LLM calls and re-renders HTML from existing alignments.

Empirical: across Gatsby + Dragon Maiden + Secret Adversary, 0.2–1% of aligned paragraphs are marked `unsupported`, and after inspection most unsupported cases are chapter-title headings or drafter-added bridging sentences — zero genuine plot/character fabrications.

## Legacy LLM stages (optional)

`prime` and `prepass` remain in the CLI for experimentation but are not used by the lean pipeline. They produce a richer plan (LLM-enumerated signatures per segment, web-search-grounded cultural famousness) but at real cost and without clear quality wins over the lean path.

## Setup

```bash
# 1. Clone & install
git clone https://github.com/thomaspinckney3/forage.git
cd forage
python3 -m venv .venv
.venv/bin/pip install -e .

# 2. Configure API keys
cp .env.example .env   # edit to add your keys
```

Required environment (in `.env`):

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...

# Lean pipeline model routing (recommended defaults)
FORAGE_DRAFT_MODEL=anthropic:claude-opus-4-7
FORAGE_REGEN_MODEL=anthropic:claude-opus-4-7
FORAGE_CRITIC_MODEL=anthropic:claude-sonnet-4-6

# Memoize every LLM response to work/.replay_cache/<hash>.json so reruns
# hit the cache instead of spending. The cache is committed to the repo so
# collaborators inherit the cached responses for the books already processed.
FORAGE_REPLAY=1
```

Per-stage overrides (`FORAGE_{STAGE}_MODEL`) beat the global `FORAGE_MODEL`, which beats whatever the caller passes. The CLI prints which model each call resolved to:

```
[llm] stage=draft:gatsby:001 model=anthropic:claude-opus-4-7
[llm] stage=critic:signature:gatsby:001 model=anthropic:claude-sonnet-4-6 (caller requested anthropic:claude-opus-4-7, overridden by FORAGE_CRITIC_MODEL)
```

## Adding a book

Drop the source under `books/<book_id>/`:

```
books/
  gatsby/
    gatsby.txt                    # Project Gutenberg .txt
    metadata.json                 # {"title": "...", "author": "...", "genre": "novel"}
  dragon_maiden/
    dragon_maiden.epub            # EPUB also supported
    metadata.json
  don_quixote/
    don_quixote.txt
    metadata.json
    split_config.json             # {"toc_algorithm": "block_run"} for multi-part
```

`load_book` auto-detects `.txt` and `.epub` sources.

## CLI usage

```bash
forage -h                           # help (also --help)
forage split <book>                 # chapter split, zero-LLM
forage classify <book>              # LLM classifier (auto-invoked by plan)
forage plan <book>                  # deterministic plan + merge groups
forage summarize <book>             # ~30-sentence prose synopsis (chunked if needed)
forage cuts <book>                  # removable-material prepass (needs synopsis)
forage show <book>                  # print current plan
forage draft <book>                 # draft all diegetic segments (uses cuts.json if present)
forage draft <book> --segment 001   # draft just one
forage critique <book> 001          # run signature critic on one chapter
forage iterate <book> 001           # draft → critic → regen loop (default 1 regen)
forage assemble <book>              # concat + budget report (no fail-loud gate)
forage coherence <book>             # structural damage critic (adjacent-chapter pairs)
forage book-critique <book>         # synopsis-grounded per-sentence verification
forage validate <book>              # motif + style + signature checks
forage proofread <book>             # paragraph-level alignment viewer → proofread.html
forage report [<book>]              # standard results row (all books if no arg)
```

### Standard results report

Every book's pipeline run produces artifacts (`plan.json`, `assembly_report.json`, `book_critic.json`) that `forage report` reads to render a uniform per-book row:

| Column | Meaning |
|---|---|
| `book` | book id |
| `chapters` | drafted / total diegetic chapters |
| `source → final` | raw word counts (source of truth vs assembled abridgment) |
| `compression (vs target)` | achieved ratio vs spec's target ratio — only shown for complete abridgments; partial books show `(partial)` because partial-draft ratios are meaningless |
| `over ceiling` | `under` / `+N%` past target × 1.2 |
| `book critic` | `ship` or `hold`, `<present>/<total>` synopsis sentences verified |

Zero LLM cost to run. Re-run any time to refresh from the on-disk artifacts.

## End-to-end example

```bash
forage split gatsby
forage summarize gatsby             # one-time, produces book_synopsis.md
forage cuts gatsby                  # one-time, produces cuts.json
forage plan gatsby                  # auto-runs classify on first call
for chapter in 001 002 003 ... ; do
  forage iterate gatsby $chapter    # drafts + critiques + regens (cuts-aware)
done
forage assemble gatsby              # produces abridgment.md
forage coherence gatsby             # structural damage critic (post-hoc)
forage book-critique gatsby         # verifies abridgment against synopsis
forage validate gatsby              # mechanical sanity checks
forage proofread gatsby             # paragraph-level alignment viewer
```

Or use the `scripts/full_pipeline.py` driver to run draft across all diegetic chapters, then assemble + book-critique:

```bash
.venv/bin/python -m scripts.full_pipeline gatsby
# opt-in extras:
.venv/bin/python -m scripts.full_pipeline gatsby --iterate      # critic + regen loop
.venv/bin/python -m scripts.full_pipeline gatsby --coherence    # adjacent-pair critic
.venv/bin/python -m scripts.full_pipeline gatsby --iterate --coherence
```

(The full-pipeline script assumes `split`, `summarize`, and `cuts` have already been run; those are book-level one-time prereqs.)

## Directory structure

```
forage/
  forage/                          # core package
    artifacts.py                   # Book loader (txt/epub), artifact paths
    chapter_split.py               # regex splitter for .txt sources
    epub_reader.py                 # spine-based EPUB splitter
    compression.py                 # book-level target formula
    lean_plan.py                   # plan builder + merge-group assignment
    chapter_classifier.py          # LLM classifier (diegetic vs not)
    summarizer.py                  # ~30-sentence prose synopsis, chunked chaining
    drafter.py                     # drafter + merge-group draft + fallback
    cuts.py                        # removable-material prepass
    critics.py                     # signature critic
    coherence.py                   # structural coherence critic
    book_critic.py                 # synopsis-vs-abridgment verifier
    iterate.py                     # draft/critique/regen loop
    assemble.py                    # concatenation + budget report
    rebudget.py                    # book-level target reallocation
    validate.py                    # mechanical sanity checks
    align.py                       # per-chapter draft↔source paragraph alignment
    proofread.py                   # HTML renderer for alignments
    dialogue_split.py              # post-hoc dialogue paragraph splitter
    llm.py                         # provider-agnostic LLM client + routing
    prompts.py                     # prompt template loader
    json_parse.py                  # robust LLM-JSON parsing
    motif_ledger.py                # running motif state across segments
    cli.py                         # typer CLI
  prompts/                         # Jinja2 + YAML-frontmatter prompts
    draft_lean.md                  # spec-as-prompt drafter (lean, cuts-aware)
    critic_signature.md            # adversarial signature critic (cuts-aware)
    critic_coherence.md            # structural damage critic (cuts-aware)
    critic_book.md                 # synopsis-vs-abridgment verifier
    classify_chapters.md           # chapter classifier
    summarize_synopsis.md          # single-call / partial synopsis
    summarize_merge.md             # merge N partial synopses into one
    prepass_cuts.md                # removable-material prepass
    align.md                       # paragraph-level draft↔source alignment
    draft_segment.md               # legacy tier-based drafter
    prepass.md                     # legacy LLM plan builder
    prime.md                       # legacy example-signature seed
    reconsider_segment.md          # per-segment signature re-id
  scripts/
    full_pipeline.py               # single-book end-to-end runner
    lean_iterate_first_n.py        # multi-book sweep: first N chapters each
  spec/
    ABRIDGMENT_SPEC.md             # canonical design doc (also fed to drafter)
  books/                           # source inputs + published deliverables
    <book>/
      <book>.txt | <book>.epub     # source
      metadata.json                # {title, author, genre}
      split_config.json            # optional per-book splitter override
      abridgment.md                # (published) assembled abridgment
      proofread.html               # (published) alignment viewer
  work/                            # generated output
    <book>/
      chapters.json                # structural manifest
      chapters/NNN.md              # split chapter sources
      chapter_classifications.json # LLM verdicts per candidate
      plan.json                    # lean plan with targets + merge groups
      book_synopsis.md             # ~30-sentence prose ground-truth synopsis
      cuts.json                    # removable-material inventory
      segments/
        NNN.md                     # final draft (latest iteration)
        NNN.iterK.md               # per-iteration snapshots
        NNN.critic_signature.json  # latest chapter critic findings
        NNN.iterK.critic.json      # per-iteration critic snapshots
        gNNN.md                    # merged-group raw output (before split)
      alignments/NNN.json          # per-chapter paragraph alignments (for proofread)
      abridgment.md                # assembled final output
      assembly_report.json         # budget stats, overage, segment tallies
      book_critic.json             # per-synopsis-sentence verdicts
      coherence_report.json        # structural coherence findings
      proofread.html               # self-contained alignment viewer
      llm_calls.jsonl              # every LLM call this book issued
    .replay_cache/                 # memoized LLM responses — tracked in git so
                                   # collaborators get deterministic replay
  CLAUDE.md                        # project rules for Claude Code
  pyproject.toml
```

## Model-routing summary

| Stage | Env var | Default | Why |
|---|---|---|---|
| `draft` / `regen` | `FORAGE_DRAFT_MODEL`, `FORAGE_REGEN_MODEL` | `anthropic:claude-opus-4-7` | Max extended thinking auto-enabled on Opus variants; better referent-chain integrity under compression than GPT-5 |
| `draft` fallback | `FORAGE_DRAFT_FALLBACK_MODEL` | `anthropic:claude-sonnet-4-6` | Automatic retry on OpenAI `content_filter` (only fires if user routes drafter to OpenAI) |
| `critic:*` | `FORAGE_CRITIC_MODEL` | `anthropic:claude-sonnet-4-6` | Consistent adversarial voice for signature and book critics |
| `classify` | `FORAGE_CLASSIFY_MODEL` | `anthropic:claude-sonnet-4-6` (prompt default) | Cheap content-aware classification |
| `summarize` | `FORAGE_SUMMARIZE_MODEL` | `openai:gpt-5` | Long-context synopsis generation |

## Known limitations

- **Budget pressure is structural.** GPT-5 has a preferred compression ratio around 1.2–2× on short inputs. Merge groups alleviate this by giving the drafter bigger combined inputs (3× compression comes naturally). Long-input mode (e.g., whole-book single-shot) swings the other way — GPT-5 over-compresses into summarize-mode.
- **Per-book role classification is coarse.** The lean plan treats every diegetic chapter the same — no per-role (signature/narrative/digressive) compression differentiation. Uniform novels are fine; uneven ones (Moby Dick's narrative vs cetology chapters) don't get the spec-recommended role-specific ratios.
- **Regen whack-a-mole on voice-dense books.** When the regen drafter touches neighboring sentences to integrate a restored passage, it can paraphrase away other signature material — the critic flags those newly-flattened passages in the next round. Visible on Henry Adams's *Education* and similar voice-heavy books. The budget-neutral regen instruction helps but doesn't eliminate the pattern.
- **Content-filter fallback changes the drafter model mid-run.** Books that trip OpenAI's content filter (Moby Dick's Loomings, Uncle Tom's Cabin in places) fall back to Sonnet for that draft. Sonnet compresses differently than GPT-5, so merge groups that fallback can produce less aggressive compression than groups that stay on GPT-5.

## Design documents

- [`spec/ABRIDGMENT_SPEC.md`](spec/ABRIDGMENT_SPEC.md) — the canonical spec that the drafter reads as prompt context and that the pipeline implements.
- [`CLAUDE.md`](CLAUDE.md) — project rules for Claude Code assistants (the approval gate for live LLM calls, etc.).
