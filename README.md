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
split → plan → draft → critic → iterate → assemble → validate
         ─────────────  LLM calls  ─────────────
```

Each stage has a CLI subcommand. All stages operate on files under `work/<book_id>/`, so they're inspectable and rerunnable.

### 1. `split` — deterministic chapter split

Zero-LLM. Reads the source and emits `chapters.json` + one `chapters/NNN.md` file per chapter. Two backends:

- **Regex splitter** (`forage/chapter_split.py`) — for plain-text Project Gutenberg sources. Finds CHAPTER/ROMAN/digit headings, strips TOC duplicates, filters <30-word fragments.
- **EPUB reader** (`forage/epub_reader.py`) — for structured EPUBs. Uses the spine and filename patterns (`cover`, `contents`, `chapter-NNN`) to identify front-matter vs body. More reliable than regex splitting.

Both emit the same `chapters.json` shape, so downstream stages don't care which ran.

### 2. `plan` — deterministic lean plan

Zero-LLM. Builds `plan.json`:

- Book-level target from `forage/compression.py` — a log-scaled reading-time formula: 1 hour at 24k source words, 5 hours at 600k, at 200 wpm.
- Per-chapter targets apportioned by chapter source share of total diegetic words. Targets rounded up to nearest 100.
- Front-matter, prologues, epilogues, and section dividers classified as `extradiegetic` — excluded from target apportionment and cut at draft time.

(The older LLM-based `prepass` command still exists and produces a richer plan with signature lists, but the lean pipeline doesn't require it.)

### 3. `draft` — GPT-5 drafter (spec-as-prompt)

Default model: `openai:gpt-5` (routable via `FORAGE_DRAFT_MODEL`).

The drafter prompt (`prompts/draft_lean.md`) is the abridgment spec + chapter source, full stop. No per-chapter signature enumeration, no tier scaffolding — the model reads the spec and writes the chapter. Output goes to `work/<book>/segments/<NNN>.md`.

Fallback: if OpenAI returns `stop_reason=content_filter` (which hits on classical-lit triggers like Moby Dick's "pistol and ball"), the drafter transparently retries on Anthropic (`FORAGE_DRAFT_FALLBACK_MODEL`, default Sonnet).

### 4. `critique` — adversarial signature critic

Default model: `anthropic:claude-sonnet-4-6` (routable via `FORAGE_CRITIC_MODEL`).

Prompt: `prompts/critic_signature.md`. Hunts for voice-establishing prose, culturally famous passages, interpretively load-bearing moments that are **absent, paraphrased, or flattened** in the draft. Emits a JSON findings list with severity (high/medium/low) and per-finding fields: `source_passage`, `draft_treatment`, `why_it_matters`, `suggested_fix`.

### 5. `iterate` — draft → critique → regenerate loop

Runs the critic on a draft, computes a verdict from the findings (any high OR ≥2 mediums → regenerate), and if regen is needed, hands the **high+medium findings only** to the drafter's regen prompt (low dropped). The regen prompt asks the drafter to address the flagged passages using the source text as the authoritative basis for restored material, and to tighten lower-priority material elsewhere by roughly equivalent length so the draft stays budget-neutral.

Per-iteration snapshots are preserved: `NNN.iter0.md`, `NNN.iter1.md`, …, `NNN.critic_signature.json`, `NNN.iter1.critic.json`, …

Default `--max-retries` is **2**.

### 6. `assemble` — fail-loud assembly

Zero-LLM. Concatenates drafted segments into `work/<book>/abridgment.md` **only if** the book is complete AND under the +20% ceiling. Otherwise writes `work/<book>/halt.json` with a refusal reason and exits non-zero.

Per the spec's fail-loud rule: the output domain is "faithful abridgment" OR "diagnosed stop" — nothing in between.

### 7. `rebudget` (optional) — book-level reallocation

Reallocates per-segment targets if the assembled total is wildly off book_target.

### 8. `validate` — mechanical sanity checks

Zero-LLM. Motif concordance, style distribution (sentence length, em-dash frequency, vocab richness), signature fuzzy-match coverage. Flags depleted motifs and style divergence from source.

## Legacy LLM stages (optional)

`prime` and `prepass` remain in the CLI for experimentation but are not used by the lean pipeline. They produce a richer plan (LLM-enumerated signatures per segment, web-search-grounded cultural famousness) but at real cost and without clear quality wins over the lean path. See [`prompts/prime.md`](prompts/prime.md) and [`prompts/prepass.md`](prompts/prepass.md).

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
FORAGE_DRAFT_MODEL=openai:gpt-5
FORAGE_REGEN_MODEL=openai:gpt-5
FORAGE_CRITIC_MODEL=anthropic:claude-sonnet-4-6

# Optional: memoize every LLM response to work/.replay_cache/<hash>.json
# Useful for iterating on prompt/pipeline logic without repaying.
FORAGE_REPLAY=1
```

Per-stage overrides (`FORAGE_{STAGE}_MODEL`) beat the global `FORAGE_MODEL`, which beats whatever the caller passes. The CLI prints which model each call resolved to:

```
[llm] stage=draft:gatsby:001 model=openai:gpt-5
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
```

`load_book` auto-detects `.txt` and `.epub` sources.

## CLI usage

```bash
forage -h                           # help
forage split gatsby                 # split source into chapters
forage plan gatsby                  # build deterministic lean plan
forage show gatsby                  # print current plan
forage draft gatsby                 # draft all diegetic chapters
forage draft gatsby --segment 001   # draft just one chapter
forage critique gatsby 001          # run critic on one chapter
forage iterate gatsby 001           # draft → critic → regen loop (default max 2 regens)
forage assemble gatsby              # concatenate + fail-loud gate
forage validate gatsby              # motif + style + signature checks
```

## Directory structure

```
forage/
  forage/                 # core package
    artifacts.py          # Book loader (txt/epub)
    chapter_split.py      # regex splitter for .txt sources
    epub_reader.py        # spine-based EPUB splitter
    compression.py        # book-level target formula
    lean_plan.py          # deterministic plan builder
    drafter.py            # drafting stage
    critics.py            # critic runner
    iterate.py            # draft/critique/regen loop
    assemble.py           # concatenation + fail-loud gate
    rebudget.py           # book-level target reallocation
    validate.py           # mechanical sanity checks
    llm.py                # provider-agnostic LLM client
    prompts.py            # prompt template loader
    json_parse.py         # robust LLM-JSON parsing
    motif_ledger.py       # running motif state across segments
    cli.py                # typer CLI
  prompts/                # Jinja2 + YAML-frontmatter prompts
    draft_lean.md         # spec-as-prompt drafter (lean pipeline)
    draft_segment.md      # older tier-based drafter (uses prepass plan)
    critic_signature.md   # adversarial signature critic
    prepass.md            # LLM plan builder (legacy)
    prime.md              # example-signature seed (legacy)
    reconsider_segment.md # per-segment signature re-id
  scripts/
    lean_iterate_first_n.py   # driver: iterate first N chapters of every book
  spec/
    ABRIDGMENT_SPEC.md    # the canonical design doc
  books/                  # source inputs (per-book dirs with .txt or .epub + metadata.json)
  work/                   # generated output (per-book dirs)
    <book>/
      chapters.json       # structural manifest
      chapters/NNN.md     # split chapter sources
      plan.json           # lean plan with per-chapter targets
      segments/
        NNN.md            # final draft (points at latest iteration)
        NNN.iter0.md      # initial draft
        NNN.iter1.md      # after 1st regen
        NNN.critic_signature.json  # latest critic findings
        NNN.iterN.critic.json      # per-iteration critic snapshots
      abridgment.md       # assembled final output (when complete + under ceiling)
      halt.json           # refusal record when over ceiling
      llm_calls.jsonl     # every LLM call this book has issued
    .replay_cache/        # memoized LLM responses (FORAGE_REPLAY=1)
  CLAUDE.md               # project rules for Claude Code assistance
  pyproject.toml
```

## Model-routing summary

| Stage | Env var | Default | Why |
|---|---|---|---|
| `draft` / `regen` | `FORAGE_DRAFT_MODEL`, `FORAGE_REGEN_MODEL` | `openai:gpt-5` | Strong long-form generator; doesn't collapse to plot spine like `o3` does |
| `draft` fallback | `FORAGE_DRAFT_FALLBACK_MODEL` | `anthropic:claude-sonnet-4-6` | Automatic retry on OpenAI `content_filter` |
| `critic:*` | `FORAGE_CRITIC_MODEL` | `anthropic:claude-sonnet-4-6` | Consistent adversarial voice for signature hunting |

## Known limitations

- **Budget pressure is weak.** GPT-5 has a preferred compression ratio around 1.2–2× and consistently overshoots tight targets (e.g., the log-scale formula allocates ~6.8× for Bleak House; GPT-5 lands around 1.2×). The critic hunts losses, not bloat, so the iterate loop can't trim. Books with naturally loose targets (short novels, contemporary prose) work well; very long dense books overshoot budget.
- **Per-book classification is coarse.** The lean plan treats every diegetic chapter the same — no per-role (signature/narrative/digressive) compression differentiation. Uniform novels are fine; uneven ones (Moby Dick's narrative vs cetology chapters) don't get the spec-recommended role-specific ratios.
- **Regen whack-a-mole on voice-dense books.** When the regen drafter touches neighboring sentences to integrate a restored passage, it can paraphrase away other signature material — the critic then flags those newly-flattened passages in the next round. Visible on Henry Adams's *Education*, where successive rounds find different sets of distinctive-prose losses.

## Design documents

- [`spec/ABRIDGMENT_SPEC.md`](spec/ABRIDGMENT_SPEC.md) — the canonical spec that the drafter reads as prompt context and that the pipeline implements.
- [`CLAUDE.md`](CLAUDE.md) — project rules for Claude Code assistants (the approval gate for live LLM calls, etc.).
