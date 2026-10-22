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

                   draft → coherence → coherence-fix → assemble → book-critique   ◄── default pipeline
                     │
                     ├──► proofread (post-hoc) ──► serve ──► review-apply  ◄── opt-in, recommended
                     └──► audiobook (ElevenLabs TTS)                 ◄── opt-in, paid

                   critique + iterate (draft → regen loop)    ◄── opt-in
                   coherence (adjacent-pair structural check) ◄── opt-in
                   validate (motif/style mechanical checks)   ◄── opt-in
```

Default pipeline is **draft + fresh coherence + coherence-fix + book-critique**: the Opus drafter with extended thinking handles referent-chain integrity during generation, the coherence-fix stage applies constrained adjacent-pair repairs from a current coherence report after drafting, and the book critic verifies synopsis preservation at the end. The iterate loop (signature critic + regen) and standalone post-hoc coherence critic are opt-in — empirically they whack-a-mole on voice-dense prose and have low recall on the worst compression-induced breaks (cross-chapter antecedent loss). The proofread tool + human review is the recommended quality surface.

Every stage has a CLI subcommand. All stages operate on files under `work/<book_id>/`, so they're inspectable and rerunnable.

### 1. `split` — deterministic chapter split

Zero-LLM. Reads the source and emits `chapters.json` + one `chapters/NNN.md` file per chapter. Two backends:

- **Regex splitter** (`forage/chapter_split.py`) — for plain-text Project Gutenberg sources. Finds CHAPTER/ROMAN/digit headings, strips TOC duplicates, filters <30-word fragments. Pluggable `toc_algorithm` config: default `keep_last` (dedupes repeated heading text, works for most books), alternative `block_run` (drops dense runs of heading matches — needed for multi-part books like Don Quixote whose Part I and Part II both carry "CHAPTER I." bodies). Per-book overrides go in `books/<id>/split_config.json`.
- **EPUB reader** (`forage/epub_reader.py`) — for structured EPUBs. Uses the spine and heading-aware section splitting to identify chapters. Good for clean EPUBs (self-pub + some Gutenberg variants).

Both emit the same `chapters.json` shape, so downstream stages don't care which ran.

### 2. `classify` — LLM chapter classifier

One Sonnet 5.5 call per book. Decides whether each splitter candidate is:

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

GPT-6 Astra generates the synopsis. Books within the existing 260k-token chunk budget use a single call to write `work/<book>/book_synopsis.md`. This budget was established with GPT-5 and remains conservative despite the newer model's larger context window.

For longer books, the summarizer does chunked chaining: split diegetic source at chapter boundaries into N roughly-equal chunks, produce a partial synopsis per chunk, merge into one ~30-sentence prose whole-book synopsis. N=2 for Moby Dick / Little Women / Education / Bleak House; N=3 for Don Quixote.

Runs once per book; cached. Independent of the drafting stage — can be generated before any chapter drafts exist.

### 5. `cuts` — removable-material inventory

One GPT-6 Astra call per book, or per source chunk for longer books. Using the ~30-sentence prose synopsis as the authoritative shape of the book, the prepass identifies three categories of material a careful abridger could remove without materially changing the reader's sense of plot, themes, or principal-character arcs:

- **minor_characters** — named figures whose removal wouldn't affect major arcs (party guests, one-scene hosts, background functionaries)
- **subplots** — self-contained or thematically parallel side narratives not structurally necessary
- **digressions** — essayistic, taxonomic, technical, or descriptive passages that don't advance plot

Each entry requires a one-sentence `reason_removable`. The prompt has an explicit "bias toward preservation" rule — a short, confident inventory is more useful than an inflated list.

Writes `work/<book>/cuts.json`. Consumed by:
- the drafter prompt (explicit "prefer cutting these" block)
- the signature critic prompt (authorized removals — don't flag their absence as voice_erasure)
- the coherence critic prompt (residual seams from authorized cuts are expected, not findings)
- the regen prompt in iterate (cuts override critic findings when they collide — the drafter may still restore *severable* non-cut voice tics that lived inside a cut scene)
- `forage prepare-skips` (see below)

The `skippable_chapters` field nominates chapters whose entire content can be elided. Each entry can carry a `kernel` (1-3 sentence paraphrase of any load-bearing material that must survive), a `relocate_to` segment id, and a `position` (`start`|`end`). `forage prepare-skips <book>` reads these fields, inserts the kernels into the target chapter sources (backing originals up as `<id>.md.orig`), and sets `target_word_count=0` on the skipped chapters. The drafter then reads the augmented sources and skips the zeroed chapters naturally — no drafter changes needed. `forage revert-skips <book>` reverses the operation.

Gatsby example output: 16 minor characters (Owl Eyes, Klipspringer, Catherine, etc.), 9 subplots (Pammy's cameo, Jordan's golf-cheat flashback, Michaelis's overnight vigil), 7 digressions (the Ch 4 guest-list "timetable," Wolfshiem's Metropole reminiscence, Nick's Midwestern homecoming reverie).

### 6. `draft` — Opus drafter (spec-as-prompt)

Default model: `anthropic:claude-opus-5-5` (routable via `FORAGE_DRAFT_MODEL`). The drafter preserves its `max` adaptive-thinking effort and 128k output-token budget on Opus. Opus 5.5 always uses adaptive thinking; its output budget includes both thinking and prose.

The drafter prompt (`prompts/draft_lean.md`) is the abridgment spec + chapter source + (if present) the cuts inventory. The model reads the spec and writes the chapter; no per-chapter signature enumeration, no tier scaffolding. Output goes to `work/<book>/segments/<NNN>.md`.

The system prompt instructs the drafter to preserve standard fiction paragraph conventions — each new speaker's dialogue turn goes in its own paragraph. (A post-hoc `forage.dialogue_split` tool also fixes older drafts that concatenated dialogue under compression pressure.)

**Merge-group initial drafting**: when `draft` is called for a segment that belongs to a merged group, it renders a multi-source prompt covering all group members, calls the LLM once, and splits the output (`## Chapter N` delimited) back into per-member `.md` files. Non-first members of a group are read from disk; no redundant LLM calls.

Token-limited responses from either provider are incomplete, including every member of a merged response. Empty or failed responses are not drafts. Assembly excludes these chapters and reports missing work. Group reuse requires recorded successful checks; rerunning the first member retries an incomplete group once, and later members retain that attempt's status.

**Fallback**: Anthropic drafting exceptions retry on GPT-6 Astra; OpenAI exceptions or `stop_reason=content_filter` retry on Sonnet 5.5. `FORAGE_DRAFT_FALLBACK_MODEL` overrides that choice. The [llm] log line shows the provider switch.

GPT-6 Astra is also available for drafting via `FORAGE_DRAFT_MODEL=openai:gpt-6-astra`. Earlier Gatsby tests compared Opus with GPT-5 and found more compression-induced dangling references in GPT-5 drafts; those results are historical and do not establish GPT-6 Astra's quality or cost.

### `draft-two-pass` — measured revision at a fixed target

For a complete text run using this workflow, including source-aware editorial
review, local repairs, final review, alignment and an immutable review snapshot:

```bash
python -m forage.full_run prepare --output work/_full_runs/my-run \
  --books education secret_adversary
python -m forage.full_run run --output work/_full_runs/my-run \
  --workers 4 --max-usd 200 --max-calls 600
```

This Opus 5.5 runner retains the existing chapter targets and omission decisions.
It uses pristine source chapters, plans in small batches with whole-book context,
and saves everything in a separate workspace. `prepare` is free; `run` makes
paid calls. Exact saved responses are reused when the same run resumes.
Unknown billing after a lost response remains reserved and requires explicit
recovery; it is never silently retried. The cost bound uses standard Opus 5.5
rates and must be reviewed if pricing changes.
After adding credits following a provider credit-balance rejection, resume with
`--retry-credit-errors`. This preserves the failed attempts and their billing
reserves while reusing every completed response.

Each editorial pass reads a frozen set of chapter drafts, including actual
adjacent and dependency chapters. Repairs independently adjudicate critic
findings, apply unique non-overlapping replacements, and verify protected text.
Two bounded repair rounds are followed by a final review. Remaining findings
and exact word differences remain visible; a completed run is not a claim that
all editorial concerns are resolved. `full_run_result.json` records the result.
These are local review revisions; publishing or releasing them is separate.

```bash
forage draft-two-pass education --segment 007 --segment 027 \
  --output-dir work/education/two-pass-run-001
```

Uses the existing `plan.json` targets without a separate length allowance.
One whole-book call generates source-grounded preservation plans for the selected
chapters. Code validates exact passages and cross-chapter evidence, then assigns
section budgets that sum to each target.

Each chapter has two generation passes:

1. Draft from its original source and validated plan.
2. Count the prose and each paragraph mechanically, then pass those measurements
   and the required net change to the model. It evaluates possible cuts and
   returns a complete revision with a brief cut rationale and dependency check.

The revision is counted again. Both texts, the exact requests, source, plan,
review notes, paragraph references and measured word edits remain in the output
directory. Reviewer comments are excluded from word counts. Any remaining target
difference, missing protected text or reported infeasibility is marked
`needs_review`; meeting the mechanical checks does not establish editorial quality.
There is no automatic third pass.

The command saves review artifacts in a new directory and does not replace
accepted segments or publish a book. It uses one planning call plus two chapter
calls, with medium effort and a 32,000-token output limit by default.
Use repeated `--segment` options to select chapters, or omit them to select all
positive-target narrative chapters. `--model` selects the provider/model.
Planning currently supplies the full book in one request; the book and selected
chapters must fit the model context, and relocated chapter sources must first be
reconciled with the original source.

### 7. `critique` — adversarial signature critic

Prompt default: `anthropic:claude-opus-5-5`. The recommended `.env.example` sets `FORAGE_CRITIC_MODEL=anthropic:claude-sonnet-5-5`, which routes both signature and book critics to Sonnet 5.5.

Prompt: `prompts/critic_signature.md`. Hunts for voice-establishing prose, culturally famous passages, and interpretively load-bearing moments that are **absent, paraphrased, or flattened** in the draft. Emits a JSON findings list with severity (high/medium/low) and per-finding fields: `source_passage`, `draft_treatment`, `why_it_matters`, `suggested_fix`.

If `cuts.json` exists the prompt includes the authorized-removals block — the critic is instructed not to flag absences of material on that list as voice_erasure. Non-cut material off the list is still fair game.

### 8. `iterate` — draft → critique → regenerate loop

Runs the critic on a draft, computes a verdict from the findings (any high OR ≥3 mediums → regenerate), and hands the **high+medium findings only** to the drafter's regen prompt (low dropped). The regen block asks for a roughly budget-neutral revision: for every restored passage, tighten lower-priority material (connective sentences, repeated elaboration, scene-setting without argument load, tertiary-character screen-time) of equivalent length — don't just add.

The regen prompt also includes the cuts-override clause: if a critic finding asks the drafter to restore material that lives inside an authorized-cut scene, the drafter skips it. The critic *may* still surface useful complaints about severable material *adjacent* to a cut (a pivot sentence, a signature phrase not tied to the cut scene) — the drafter uses judgment.

Per-iteration snapshots preserved: `NNN.iter0.md`, `NNN.iter1.md`, …, `NNN.critic_signature.json`, `NNN.iter1.critic.json`, …

Default `--max-retries` is **1** (so the loop runs at most: critic → maybe redraft, no verification critic after the final redraft — that final critic was always discarded).

### 9. `assemble` — assembly with budget report

Zero-LLM. Concatenates drafted segments into `work/<book>/abridgment.md`, exports the final assembled book as UTF-8 plain text at `work/<book>/abridgment.txt`, publishes both `abridgment.md` and `abridgment.txt` under `books/<book>/`, and writes `work/<book>/assembly_report.json` with budget stats: book target, ceiling, total drafted, overage (words and %), over_target/over_ceiling flags, and segments drafted/cut/missing.

Always emits work artifacts and published copies when any drafted content exists. Budget adherence is reported, not gated — downstream stages (`book-critique`, `validate`) decide whether the produced abridgment is acceptable.

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

Writes `work/<book>/coherence_report.json`. Intended for human review when run directly — does NOT auto-feed regen. The full-pipeline driver regenerates this report immediately before coherence-fix so repairs never use stale findings, and can run an additional post-fix coherence review optionally.

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

Alignments cache to `work/<book>/alignments/NNN.json`. Re-running reuses mappings only when their embedded source and draft paragraphs match current files; changed inputs or corrupt caches regenerate. Failed regeneration reports an error and preserves the previous review view. The `--render-only` flag skips freshness checks and LLM calls and re-renders HTML from existing alignments.

Empirical: across Gatsby + Dragon Maiden + Secret Adversary, 0.2–1% of aligned paragraphs are marked `unsupported`, and after inspection most unsupported cases are chapter-title headings or drafter-added bridging sentences — zero genuine plot/character fabrications.

### 15. `serve` — editorial review web app

Zero LLM cost. The same alignment data `proofread` renders statically, served as an interactive review app where a note can be attached to any paragraph and published as a machine-readable fix queue.

```bash
pip install -e '.[web]'      # fastapi + uvicorn
forage serve                 # http://127.0.0.1:8000
```

What it adds over `proofread.html`:

- **Book index** with a fidelity mix bar and unsupported/note counts per book.
- **Chapter view** — same verdict buckets, word diffs, and cut-material section, plus filters (unsupported / compressed / has-notes / full-text search) and keyboard navigation (`j` `k` move, `u` next unsupported, `c` comment, `[` `]` chapter, `/` search).
- **Marginalia** — notes sit in the right margin beside the paragraph they annotate. Select text inside a paragraph to quote it in the note.
- **Note fields** — severity (`blocker` … `praise`), kind (`fidelity`, `voice`, `continuity`, `clarity`, `style`, `typo`, `other`), status (`open` → `accepted` / `resolved` / `wontfix`), free-text body, reviewer name.
- **Comment locations** — the original paragraph index, text and anchor remain immutable. The UI uses a separately verified current location: a unique matching passage follows insertions, and review application records explicit destinations for corrected or split passages. Ambiguous or unmatched notes appear under “Notes awaiting a matching passage” with their original text, rather than beside whatever now occupies the old index. `stale` means the reviewed wording changed; it is independent of the open/accepted/resolved/wontfix status.
- **Revision review** — each published LLM response has **Accept revision** and **Reject with comment** controls. Acceptance closes the note; rejection requires feedback and queues it for the next revision pass. An accepted revision has **Reopen revision**, which returns it to review without requesting generation. Reviewers can update a rejection or accept it to cancel the pending request. The original note remains intact and **Review history** records decisions, comments, authors and the response reviewed. A new model response always needs its own acceptance, and an outdated page cannot decide a newer revision.
- **Suggested issues** — the chapter text comes first, with a jump button to compact suggestions below it. These are possible issues from automated review, labeled **Needs attention**, **Suggestion**, or **Optional**. Open a card to compare passages, **Dismiss suggestion**, or **Request change with comment**. You can read and annotate without deciding every suggestion.
- **Review history** — a collapsed panel holds changes already made, dismissed or outdated suggestions, detailed critic records and draft diagnostics. Completed repairs retain **Accept revision**, **Reject with comment**, and **Reopen revision**; dismissed suggestions can be reopened. Before/after passages and reasons remain available. Accepting a repair acknowledges the existing draft and does not dismiss other suggestions. Nothing is queued for generation until a reviewer requests a change.
- **External reruns** — the website records decisions and requests only. An operator runs `review-pull` / `review-sync --apply --republish` separately; there is no website control that starts the pipeline.
- **Regeneration safety** — feedback exports preserve the originally reviewed text. Application rechecks the target against the actual draft before calling a model and blocks notes without sufficient context. Each generated paragraph decision must identify its target paragraphs in the final draft; that mapping is committed with the draft and ledger, so restart recovery preserves both.
- **Deep links** — `/b/<book>?c=<chapter>&p=<paragraph>` opens on the paragraph in question.

**Export feedback** writes the queue to `work/<book>/editorial/edits.json`: comments grouped by chapter, each carrying the paragraph text it was written against and its staleness flag. That file is the overlay a fix stage consumes — the app never edits `segments/*.md` itself, so a review pass can't corrupt drafts. The same document is downloadable without writing to disk at `/api/books/<book>/edits.json`.

#### Access control

Accounts use a username and password. Reading remains public; registration is
admin-only. The **Users** button lets administrators list accounts, create a
reviewer or another administrator, and remove an account. Removal immediately
revokes its sessions while preserving its review notes and attribution. The last
administrator and your own account cannot be removed. Click your account name
to change your password or sign out; a password change ends other sessions.

| Level | Can |
| --- | --- |
| public | read books, chapters, alignments and notes; download feedback |
| reviewer | add, edit, restatus and delete notes |
| admin | reviewer permissions, manage accounts, export feedback, upload revisions and promote review/public release |

Usernames are case-insensitive (3–64 letters, numbers, `.`, `@`, `_`, `-`).
Passwords are 15–128 characters, including spaces and Unicode. Display names
come from the stored account, never a sign-in label. Passwords use salted scrypt
hashes with the [OWASP 32 MiB profile](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
(N=32768, r=8, p=3). Random 256-bit session cookies are `HttpOnly`, `SameSite=Lax`
and `Secure` over HTTPS; only their hashes are stored in SQLite. Every request
checks the current account and session. Logout invalidates copied cookies too.

The old shared `FORAGE_REVIEW_TOKEN` / `FORAGE_ADMIN_TOKEN` login and signed role
cookies are no longer accepted. Sign-in attempts are limited to 8 per address
per 15 minutes; successful sign-ins clear that counter. Writes are limited to
60/minute. Password hashing concurrency is bounded for the small server.

Behind a proxy the limiter has to count the real client rather than the proxy, or the whole internet shares one bucket — so it reads `Fly-Client-IP` first, falling back to the **right-most** `X-Forwarded-For` entry. Right-most matters: proxies append, so the last entry is the one Fly wrote, while anything to its left was supplied by the caller and can be forged to buy a fresh bucket. Forwarded headers are only trusted when `FORAGE_TRUST_PROXY` says a proxy is genuinely in front. Cross-origin writes are refused outright, and every response carries CSP, `nosniff`, `X-Frame-Options: DENY`, and (over HTTPS) HSTS.

| Variable | Purpose |
| --- | --- |
| `FORAGE_BOOTSTRAP_ADMIN_USERNAME` | First administrator username; used only when no accounts exist |
| `FORAGE_BOOTSTRAP_ADMIN_PASSWORD` | Initial password; remove bootstrap variables after first startup |
| `FORAGE_SESSION_HOURS` | Session lifetime, default 720 (30 days) |
| `FORAGE_SESSION_EPOCH` | Bump this integer to sign every live session out at once |
| `FORAGE_ENV` | `production` enables the strict startup check |
| `FORAGE_TRUST_PROXY` | Honour `X-Forwarded-*`; defaults on when `FLY_APP_NAME` is set |
| `FORAGE_ALLOWED_HOSTS` | Comma-separated host allowlist (optional) |
| `FORAGE_WORK_DIR` | Artifact root, default `work/` |
| `FORAGE_BOOKS_DIR` | Book metadata root, default `books/` |
| `FORAGE_ARTIFACT_OVERLAY_DIR` | Optional per-book artifact override root, e.g. `/data/artifacts` |
| `FORAGE_BOOKS_OVERLAY_DIR` | Optional per-book metadata override root, e.g. `/data/books` |
| `FORAGE_REVIEW_DB` | SQLite accounts, sessions and comment queue, default `work/_review/review.db`; keep outside immutable snapshots |
| `FORAGE_HOSTED_ROOT` | Writable root for uploaded books, immutable revisions and independent review/release pointers |
| `FORAGE_EDITS_DIR` | Where publish writes, default `work/<book>/editorial/` |

For a local installation, create the first administrator with a hidden password
prompt (use the same `FORAGE_REVIEW_DB` as the server):

```bash
python -m forage.webapp.accounts create-admin admin
forage serve
```

For a container's first startup, supply both bootstrap variables as secrets.
Production refuses to start without an existing account or valid bootstrap
credentials. Bootstrap never overwrites an existing password. After initialization,
remove both bootstrap variables; accounts and sessions survive restarts in the
persistent database. No credentials are generated or printed by the server.

#### Deploying to Fly.io

`fly.toml` and the `Dockerfile` at the repo root are the whole deployment. Artifacts are baked into the image as a baseline, while the Fly volume holds the comment database, uploaded revisions and review/release pointers under `/data/hosted`, published review overlays, and optional per-book artifact overrides.

```bash
python scripts/package_review_artifacts.py        # deploy/artifacts — MB, not GB
fly launch --no-deploy                            # once; keep the generated app name
fly volumes create forage_review_data --size 1
fly secrets set FORAGE_BOOTSTRAP_ADMIN_USERNAME=admin \
  FORAGE_BOOTSTRAP_ADMIN_PASSWORD='a unique initial password of at least 15 characters'
fly deploy --ha=false
```

`scripts/package_review_artifacts.py` calls installed `forage.review_package` logic. It copies alignment JSON, a trimmed plan, metadata, existing review responses, verified current media references, and immutable publications referenced by review/release history. It excludes private drafts, replay caches, credentials and obsolete unreferenced media. Re-run it before an image deploy to refresh the baked baseline; media publications may be much larger than text-only bundles.

Custom package outputs must be separate from both input roots after resolving symlinks. Packaging validates the selected books, stages both output directories, and restores previous output if replacement raises an exception. The two directory replacements are not a crash-atomic transaction.

For a single revised book, publish the artifact overlay instead of rebuilding:

```bash
python scripts/publish_review_book.py secret_adversary --dry-run
python scripts/publish_review_book.py secret_adversary
```

That packages the same verified review artifacts and metadata, then uploads them to `/data/artifacts/<book>` and `/data/books/<book>`. A mounted book overrides the baked copy on the next request; deleting `/data/artifacts/<book>` falls back to the baked image.

The image installs `fastapi` and `uvicorn` but not the pipeline's model SDKs: the review app only reads JSON off disk and serves HTML. Build with `--build-arg INSTALL_MODE=full` when pipeline stages move behind the admin account and the container needs the full dependency set.

Deployment storage:

- **Stay at one machine.** `min_machines_running = 1` keeps one machine running; it does not cap the count. Check `fly status` before deployment and keep the app at one machine. Scaling to more machines or regions requires shared/replicated storage for both the comment database and uploaded publications; moving only SQLite to Postgres is insufficient.
- **Hosted publication uses persistent storage:** `FORAGE_HOSTED_ROOT=/data/hosted` enables `forage publish-review` and `forage publish-release`. Uploaded revisions, channel pointers and feedback projections survive restarts and deployments on the mounted volume.
- **Publishing writes to the volume**, not to the image: `FORAGE_EDITS_DIR=/data/edits`. Pull a published overlay back down with `fly ssh sftp get /data/edits/<book>/edits.json`, or skip publishing entirely and use `GET /api/books/<book>/edits.json`, which builds the same document on the fly and needs no writable disk.
- **Single-book content refreshes also write to the volume**: `FORAGE_ARTIFACT_OVERLAY_DIR=/data/artifacts` and `FORAGE_BOOKS_OVERLAY_DIR=/data/books`. Use `scripts/publish_review_book.py` after re-aligning a book; no app restart or redeploy is needed once those env vars are deployed.

After a successful first login, remove the bootstrap secrets with
`fly secrets unset FORAGE_BOOTSTRAP_ADMIN_USERNAME FORAGE_BOOTSTRAP_ADMIN_PASSWORD`.
Use the account menu for subsequent password changes. Bumping
`FORAGE_SESSION_EPOCH` invalidates every session. Before upgrading an existing
token-based deployment, back up the SQLite database, configure the initial admin,
and deploy; the migration adds account/session tables without modifying review
records. Remove the obsolete token and signing-key secrets after verifying login.

#### Checking it

`python scripts/check_review_app.py` is the end-to-end check — three layers, ~55 assertions, zero LLM cost:

- **units** — password checks, role separation, session tampering, epoch rotation, logout revocation and first-admin startup refusal
- **api** — anonymous reads, anonymous write refused, reviewer vs admin on publish, sign-in lockout (and that it's per-address, not global), cross-origin refusal, `Secure`/HSTS behind a forwarded HTTPS hop, security headers
- **browser** — real Chrome over the DevTools protocol through the whole review loop: routing, filters, keyboard nav, select-to-quote, add/resolve/delete a note, publish visible to admins only, deep links, mobile layout, no uncaught page errors

The browser layer skips itself when no Chrome is installed; the rest still runs.

### 16. `review-apply` — human feedback incorporation

Plan-only by default, zero LLM cost unless `--apply` is passed. Reads the
published queue at `work/<book>/editorial/edits.json`, groups pending feedback
by chapter, and asks the LLM for the smallest source-supported revision that
addresses correct and relevant comments.

```bash
forage review-apply secret_adversary --segment 002     # plan only
forage review-apply secret_adversary --segment 002 --apply
```

The prompt requires a decision for every feedback item. The model may skip a
comment if it is wrong, stale, already resolved, irrelevant to that chapter, or
would require a broad rewrite, but it must record a concise reason. Applied and
skipped decisions are written to
`work/<book>/editorial/review_apply_ledger.json` with the comment fingerprint,
target chapter, draft-before hash, draft-after hash, timestamp, model, and token
counts. Each decision also carries a per-comment LLM response that the review
web app displays under the original note when the ledger is present in the
artifact tree. Future rounds ignore unchanged feedback already in the ledger;
editing an ordinary comment changes its fingerprint and makes it eligible again.
For a note with a published response, use **Reject with comment** to request
another pass. The follow-up has its own identity and is applied once against the
verified current passage. **Accept revision** and **Reopen revision** make no
model calls. The existing **Accept comment** action means the initial note is
accepted for action; it is separate from accepting the resulting revision.

Book-level comments are considered per target chapter. Without `--segment`, the
stage uses chapters that already have chapter or paragraph feedback rather than
fanning a global note out across the whole book.

### 17. `audiobook` — ElevenLabs narration

Paid API stage. Reads `books/<book>/abridgment.txt` (falling back to `work/<book>/abridgment.txt`) and splits the assembled abridgment into bounded narration chunks. A dry run writes a separate preview beneath `work/<book>/audiobook/preview/`, preserving generated audio, text sidecars, and their manifest:

```bash
forage audiobook gatsby --dry-run
```

Generation requires `ELEVENLABS_API_KEY` and a per-book voice id in `books/<book>/metadata.json`:

```json
{
  "genre": "novel",
  "title": "The Great Gatsby",
  "author": "F. Scott Fitzgerald",
  "audiobook": {
    "voice_id": "<elevenlabs-voice-id>"
  }
}
```

Then run:

```bash
forage audiobook gatsby
```

`--voice-id <id>` remains available as an explicit one-off override for testing.

Outputs:

- `work/<book>/audiobook/chunks/NNNN.txt` - text sent to each request
- `work/<book>/audiobook/audio/NNNN.mp3` - per-chunk audio
- `work/<book>/audiobook/audiobook_manifest.json` - chunk hashes, request ids, status, and paths
- `work/<book>/audiobook/audiobook.mp3` and `books/<book>/audiobook.mp3` when `ffmpeg` is available and `--combine` is enabled

The stage reuses a chunk only when its successful manifest entry matches the complete synthesis request and verified audio bytes. Changes to prose, voice, model, format, seed, language, normalization, voice settings, or stitched context require fresh audio. Legacy manifests and missing, empty, or modified files regenerate. `--overwrite` forces regeneration. Failed synthesis preserves prior successful files without labeling them current; combination requires every current chunk to be valid. Use `--limit N --no-combine` for a paid smoke test on the first N chunks. By default it sends adjacent text and up to three prior ElevenLabs request ids to improve continuity across chunk boundaries; `--zero-retention` disables request-id stitching for accounts that require it.

With `--combine`, missing ffmpeg, incomplete chunks, combination failures, and publication failures are reported and return a nonzero exit status. `--no-combine` explicitly produces separate chunks. If file replacement and rollback both fail, the chunk error records a retained recovery directory and the original backup path for manual restoration.

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
# Required for LLM-backed abridgment stages
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...

# Lean pipeline model routing (recommended defaults)
FORAGE_DRAFT_MODEL=anthropic:claude-opus-5-5
FORAGE_REGEN_MODEL=anthropic:claude-opus-5-5
FORAGE_CRITIC_MODEL=anthropic:claude-sonnet-5-5
FORAGE_SUMMARIZE_MODEL=openai:gpt-6-astra
FORAGE_CUTS_MODEL=openai:gpt-6-astra
FORAGE_COHERENCE_FIX_MODEL=anthropic:claude-sonnet-5-5

# Memoize every LLM response to work/.replay_cache/<hash>.json so reruns
# hit the cache instead of spending. The cache is committed to the repo so
# collaborators inherit the cached responses for the books already processed.
FORAGE_REPLAY=1

# Optional audiobook defaults
# ELEVENLABS_API_KEY=...
# FORAGE_AUDIOBOOK_MODEL=eleven_multilingual_v2
# FORAGE_AUDIOBOOK_OUTPUT_FORMAT=mp3_44100_128
# FORAGE_AUDIOBOOK_MAX_CHARS=9000
```

Per-stage overrides (`FORAGE_{STAGE}_MODEL`) beat the global `FORAGE_MODEL`, which beats whatever the caller passes. The CLI prints which model each call resolved to:

```
[llm] stage=draft:gatsby:001 model=anthropic:claude-opus-5-5
[llm] stage=critic:signature:gatsby:001 model=anthropic:claude-sonnet-5-5 (caller requested anthropic:claude-opus-5-5, overridden by FORAGE_CRITIC_MODEL)
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
forage serve                        # editorial review web app (comments → edits.json)
forage review-apply <book>          # plan human-feedback repair pass (zero LLM cost)
forage review-apply <book> --apply  # apply feedback and update review_apply_ledger.json
forage audiobook <book> --dry-run   # split abridgment into ElevenLabs chunks
forage audiobook <book>             # generate using metadata audiobook.voice_id
forage report [<book>]              # standard results row (all books if no arg)
```

### Resumable production and local revisions

`forage run BOOK` is the shared end-to-end workflow. It previews reuse, pending
work, stale outputs and failures without invoking any provider or adopting files.
Add `--execute` only when you intend to spend provider credits; a replay-cache
miss can still issue a paid request. Text is always required, and audio/graphic
outputs are optional:

```bash
forage run gatsby --workspace /srv/forage
forage run gatsby --workspace /srv/forage --execute
forage run gatsby --outputs text,audio,graphic --audio-voice-id VOICE --audio-chunks-only
forage run gatsby --outputs text,audio,graphic --audio-voice-id VOICE --audio-chunks-only --execute
forage release gatsby REVISION_SHA256 --workspace /srv/forage
```

The default executed run prepares chapters/classification/synopsis/cuts/plan,
drafts every included chapter, runs fresh coherence inspection and bounded
repair, assembles, performs book criticism and mechanical validation, aligns
prose for review, generates selected media, and prepares a local immutable
snapshot. `--iterate` adds signature criticism/regeneration; `--no-coherence-fix`
disables repair, and `--coherence` retains inspection in that mode. Pair targeting
uses repeated `--coherence-fix-pair 001-002`; it requires repair. `--max-retries`
bounds iteration/repair retries. A critic `hold` remains visible as an editorial
judgment; it does not claim a technical generation failure or automatic approval.

The optional `--checkpoint-before-media` stops before audio/art generation.
Resume with the printed `--continue-revision SHA256` plus the checkpoint flag;
acknowledgment applies only to that accepted text revision and becomes stale after
prose changes. It is disabled by default.

Review is asynchronous on a separate website. Local snapshots are ready for
review upload, and generation does not wait for human acknowledgment. The intended
hosted loop is publish review revision → periodically pull feedback → apply
eligible prose feedback → rerun affected outputs → republish. Existing
`review-apply` consumes the local feedback export and preserves its application
ledger. Use the hosted commands below to upload snapshots and review prose,
audio and panels. Local snapshot creation does not itself upload a book. `forage release` explicitly
promotes a verified local revision, independently of review-current. Later human
edits and local review revisions do not change that public-release selection;
promote a newer revision when ready. Neither command deploys a website.

State lives in `work/BOOK/production_state.json`. Exact input/settings/prompt/spec
hashes and output inventories govern reuse; a process lock excludes concurrent
runs and publication changes for the same book. Missing or corrupt outputs and
interrupted stages retry. A failed media branch preserves successful independent
branches and blocks a new snapshot. Existing successful prose edits become accepted
text revisions: their bytes are retained, assembly/criticism/alignment/selected
media refresh, and initial drafting/repair is not repeated merely because prose
changed. To explicitly rerun quality repair, change `--repair-epoch TOKEN`.
Changing source or generation settings archives superseded draft/check/group
files under `.production/draft_history/` before regeneration. A merged group is
one generation unit. Initial request/context hashes remain attached to their
original generation, so later prose edits do not recursively invalidate earlier
chapters. Cuts and plan edits are reconciled against pristine preparation data;
removed cuts remove their prior relocated kernels.

Completed full runs can use the same `review-sync --apply --republish` workflow.
The runner verifies their immutable publication, source chapters and original
plan before applying feedback, then preserves their targets, omissions and
accepted prose. New snapshots contain `full_run_inputs.json`; older full-run
workspaces also need their original `run.json` source inventory. Unchanged runs
reuse the existing revision without model calls. Changed prose refreshes the
common downstream stages; original fidelity findings remain historical evidence.
Automatic iteration/coherence repair is disabled for this refresh path: request
prose changes through review feedback, and start a new run for source/plan changes.
New full runs share the common text identity. Existing editions keep their IDs;
book-level notes on those editions are eligible when the verified snapshot's
plan and draft bytes still match locally.

Legacy drafts without runner provenance require `--adopt-existing --execute`.
Review them first: adoption verifies required nonempty prose and successful
checks against the prepared plan, records `user-adopted` provenance, and does not
pretend to know the original source/model. Missing or failed checks cannot be
adopted. Upstream preparation and downstream checks may still require generation.
Standalone stage commands continue to work; the runner detects their subsequent
changes through content inventories.

Audio uses ElevenLabs and the current work abridgment. Configure
`--audio-voice-id`, `--audio-model`, `--audio-format` and `--audio-max-chars`, or
metadata audiobook settings/environment defaults. Integrated review audio supports
MP3 (`mp3_22050_32` or `mp3_44100_32/64/96/128/192`). By default all chunks must
successfully combine via ffmpeg; combination failure fails the stage.
`--audio-chunks-only` explicitly produces a complete set of independently playable
chunks. The runner never treats a partial chunk limit as a complete audiobook.

Graphics adapt the full included chapter set unless `--graphic-chapters` selects
specific chapter IDs. The integrated layout is one lettered frame per page,
covering consecutive prose units throughout the selection, with a PDF and bounded
contact sheets. Storyboards use the configurable `--graphic-storyboard-model`;
images use OpenAI (`--graphic-provider openai`) with `--graphic-model`,
`--graphic-style`, `--graphic-size` and `--graphic-quality`. Frame density and
lettering use `--graphic-words-per-frame`, `--graphic-font-size` and
`--graphic-caption-height`. Edit captions or image prompts in
`work/BOOK/graphic/storyboard.json`; unchanged art is reused after caption/font
changes, and failed runs resume verified frames. Provider credentials are
`OPENAI_API_KEY` for art and the appropriate key for the storyboard text model.

`media_manifest.json` contains revision-bound audio chunk and graphic frame IDs
with confined relative paths and SHA-256 hashes. Audio timestamps are chunk-local;
unknown duration is null. `publications/REVISION/revision.json` inventories immutable
copies of selected text/review/media files. `review_current.json` and
`release_current.json` have separate atomic histories. Release promotion verifies
all snapshot bytes; failed promotion leaves the prior release intact. Historical
`books/BOOK/abridgment.*`/audio copies remain standalone compatibility deliverables,
not an implicit release promotion.

A workspace contains `books/` and writable `work/`. `--workspace` takes priority;
otherwise `FORAGE_WORKSPACE`, `FORAGE_BOOKS_DIR`/`FORAGE_WORK_DIR`, then the current
working directory provide defaults. Installed wheels carry the exact repository
prompt/spec resources and graphics/static assets, while artifacts and replay
cache stay in the workspace. `--model provider:id` and repeated
`--stage-model STAGE=provider:id` select text models; existing stage/global
environment model overrides keep their documented precedence. See `run --help`
for available settings. No paid generation or creative quality is certified by
the offline integration tests.

### Hosted review, feedback sync and public release

For older completed full runs, package the saved critic findings and repair
history without generation, then publish the returned revision:

```bash
forage prepare-review BOOK --workspace /srv/forage
forage publish-review BOOK REVISION --workspace /srv/forage
```

New full runs package this automatically. Preparation verifies saved evidence,
patch replay, current paragraph alignment, and the prior snapshot inventory;
prose and text identity remain unchanged. Republish is idempotent and retains
reviewer decisions. Subsequent feedback repairs carry the original review items
forward and publish a new response requiring its own review.

The review site runs separately from generation. Configure its writable
`FORAGE_HOSTED_ROOT`, persistent `FORAGE_REVIEW_DB`, and first-start
`FORAGE_BOOTSTRAP_ADMIN_USERNAME` / `FORAGE_BOOTSTRAP_ADMIN_PASSWORD`. Keep the database and exported
feedback outside the immutable `publications/` directories. The web-only image
serves uploads without model SDKs or Pillow. Existing baked artifacts and mounted
whole-book overlays remain supported; a current revision never falls back to an
older media target that it removed. Upload defaults are 128 MiB compressed,
512 MiB for the entire decompressed stream (including tar headers, extended
metadata and trailing data), and 10,000 files. For larger books configure positive
integer
`FORAGE_MAX_UPLOAD_BYTES`, `FORAGE_MAX_EXPANDED_BYTES` and
`FORAGE_MAX_UPLOAD_FILES` on the server; uploads remain bounded by those limits.

On the pipeline machine, set `FORAGE_REVIEW_URL` to the site's base URL and
`FORAGE_ADMIN_USERNAME` and `FORAGE_ADMIN_PASSWORD` to an administrator account
(or select variable names using `--username-env` and `--password-env`). Use a
dedicated publishing account so personal password changes do not interrupt
automation. The client signs in through the account session API. Credentials are read from the
environment and never written into revision manifests. Alternatively configure
`metadata.json` with `{"review": {"url": "https://review.example.org"}}`.
`--site` overrides configuration. Local transport uses `--local-root PATH` or
`FORAGE_REVIEW_LOCAL_ROOT`; choose exactly one transport.

```bash
# REVISION is the SHA-256 printed by a successful forage run --execute.
forage publish-review BOOK REVISION --workspace /srv/forage
forage review-pull BOOK --workspace /srv/forage
forage review-sync BOOK --workspace /srv/forage             # same free pull/plan
forage review-sync BOOK --workspace /srv/forage --apply --republish
forage publish-release BOOK REVISION --workspace /srv/forage
```

Publishing verifies the complete local inventory, uploads an immutable snapshot,
and advances only the selected hosted pointer after server verification.
`publish-review` never promotes a public release. `publish-release` is the
explicit public operation and reports confirmed hosted success; `release`
remains a separate local selection. A failed upload/promotion preserves the
previous current revision. Readers can use the public-release view/downloads
while reviewers work on a newer review revision. A book published directly as a
release can receive and export feedback immediately: unspecified current views
use review when present, otherwise release. Explicit channel/revision selections
remain strict, and this fallback never creates a review publication. Both histories
and old comment anchors survive later publication and release.

The review UI exposes prose, audio playback with chunk-local timestamp notes,
and graphic frame notes. Every new hosted comment names the revision actually
viewed. Notes retain original text/target anchors, author, timestamps and status;
changed targets appear stale and removed targets appear orphaned. Audio notes
with unknown duration accept finite nonnegative times without inventing a length.
Media comments remain available to editors but are not automatically translated
into prose edits.

Revision decisions are stored transactionally in the review database and are
included in feedback exports. Rejection queues feedback; generation continues
through `review-sync --apply --republish` (or an exported `review-apply` pass),
not inside the web server. Original anchors are retained while local ledger
bindings verify the current passage. A request is blocked if its reviewed
chapter changed before application. Production snapshots include a sanitized
`review_responses.json`, so the hosted site receives the new response even when
the model skips a request and leaves the prose unchanged. Review decisions do
not promote a public release.

`review-pull` makes no model calls. It reads the versioned full feedback feed at
`/api/books/BOOK/feedback`, atomically reconciles stable source/comment identities,
and preserves `editorial/review_apply_ledger.json`. Edits, resolved notes and
remote deletions update eligibility without deleting historical application
choices. The imported queue is separate from that ledger. Repeated identical
pulls do not duplicate notes or change their timestamps. Eligibility checks the
current local draft bytes; stale, orphaned, inactive, media and unanchored remote
notes never enter the paid prose pass.

An applied paragraph deletion remains reviewable while its recorded final
chapter still matches. Rejecting it can request restoration through the next
sync. A later chapter change requires a fresh review; decisions submitted from
a page showing a superseded pipeline finding return a conflict and preserve
the existing decision history.

`review-sync --apply` invokes the constrained review-apply stage for eligible
feedback and refreshes affected production outputs. The common production planner validates
all selected stages, settings and output bytes even when prose did not change.
A failed media run is retried; an acknowledged checkpoint alone cannot mark a
revision complete. Explicit output/settings overrides are validated and honored.
`--republish` uploads the resulting complete review revision. It requires
`--apply`; release remains a separate explicit action. Saved requested settings
retain selected outputs and narration/art options across failed runs as well as
successful ones. Override them with `--outputs` or a JSON object supplied through
`--production-options PATH`. Use repeated `--segment CHAPTER` to limit application
or choose chapters for book-level notes. Model routing environment overrides still
apply. A configured media checkpoint remains
in force after text edits and must be acknowledged using `forage run`. Existing
runs predating saved options may require explicit media settings. A failed apply
or regeneration never republishes partial work.

Before changing prose, review application saves a durable intent containing the
validated decision and expected before/after artifact hashes. Interrupted writes
resume without another model call, retaining prior ledger decisions. Apply, pull
and production recover this intent before treating feedback as stale or publishing
new output. A free production preview or direct snapshot refuses unresolved intent.
If someone edited the draft/checks/ledger in the meantime, recovery stops and
preserves those bytes plus `editorial/review_apply_pending.json` for reconciliation;
it does not overwrite the intervening edit.

For local transport, provide the full server feedback export with
`--feedback /path/to/feedback.json`, or place it at the transport's documented
`HOSTED_ROOT/BOOK/feedback.json` (the server updates this projection). A
`feedback_pending` marker blocks local pulls while that projection is unfinished
or failed; HTTP feedback still reads authoritative SQLite state. Repeat a
successful publication to refresh a failed projection. External cron can call these commands periodically; the CLI
does not install a scheduler. The same cycle continues after release:
collect feedback → pull/apply → publish review → explicitly publish a newer
release. Application decisions for unchanged feedback prevent reapplication.

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
forage assemble gatsby              # produces abridgment.md + abridgment.txt
forage coherence gatsby             # structural damage critic (post-hoc)
forage book-critique gatsby         # verifies abridgment against synopsis
forage validate gatsby              # mechanical sanity checks
forage proofread gatsby             # paragraph-level alignment viewer
forage serve                        # review + comment on it in the browser
forage audiobook gatsby --dry-run   # inspect chunking before paid TTS
```

`scripts/full_pipeline.py` is a compatibility wrapper over the same runner:

```bash
.venv/bin/python -m scripts.full_pipeline gatsby              # free preview
.venv/bin/python -m scripts.full_pipeline gatsby --execute    # potentially paid
.venv/bin/python -m scripts.full_pipeline gatsby --iterate --coherence --execute
.venv/bin/python -m scripts.full_pipeline gatsby --skip-coherence-fix --execute
.venv/bin/python -m scripts.full_pipeline gatsby --coherence-fix-selected-pairs --coherence-fix-pair 001-002 --execute
```

`--resume-drafts` is accepted as a compatibility alias because verified resume is
always enabled. `--coherence-fix` explicitly selects the default repair behavior;
`--coherence-fix-all-findings` selects its default scope. Unsupported flags and
conflicting repair/pair selections fail before generation. Use `forage run` for
the full provider/media configuration surface.

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
    audiobook.py                   # ElevenLabs TTS chunking + audio artifacts
    critics.py                     # signature critic
    coherence.py                   # structural coherence critic
    book_critic.py                 # synopsis-vs-abridgment verifier
    iterate.py                     # draft/critique/regen loop
    assemble.py                    # concatenation + budget report
    rebudget.py                    # book-level target reallocation
    validate.py                    # mechanical sanity checks
    align.py                       # per-chapter draft↔source paragraph alignment
    proofread.py                   # HTML renderer for alignments
    webapp/                        # editorial review app (forage serve)
      app.py                       # FastAPI routes: public read, reviewer write, admin publish
      store.py                     # read-only artifact view + SQLite comment queue
      auth.py                      # roles, session configuration, lockout, proxy awareness
      accounts.py                  # password hashes, user management and revocable sessions
      static/                      # single-page client (no build step)
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
    check_review_app.py            # units + api + browser check for forage serve
    package_review_artifacts.py    # trim work/ to the deploy payload
    publish_review_book.py         # publish one book overlay to Fly without redeploy
  Dockerfile                       # review app image (artifacts baked in)
  fly.toml                         # Fly.io service, volume, health check
  spec/
    ABRIDGMENT_SPEC.md             # canonical design doc (also fed to drafter)
  books/                           # source inputs + published deliverables
    <book>/
      <book>.txt | <book>.epub     # source
      metadata.json                # {title, author, genre}
      split_config.json            # optional per-book splitter override
      abridgment.md                # (published) assembled abridgment
      abridgment.txt               # (published) UTF-8 plain-text abridgment
      audiobook.mp3                # (published) combined audiobook, when generated
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
      abridgment.md                # assembled internal markdown-ish output
      abridgment.txt               # UTF-8 plain-text final output
      assembly_report.json         # budget stats, overage, segment tallies
      book_critic.json             # per-synopsis-sentence verdicts
      coherence_report.json        # structural coherence findings
      audiobook/
        chunks/NNNN.txt            # per-request narration text
        audio/NNNN.mp3             # per-request ElevenLabs audio
        audiobook_manifest.json    # request ids, hashes, paths, status
        audiobook.mp3              # combined audio when ffmpeg is available
      proofread.html               # self-contained alignment viewer
      editorial/edits.json         # published review queue (from forage serve)
      editorial/review_apply_ledger.json
                                   # applied/skipped human feedback ledger
      llm_calls.jsonl              # every LLM call this book issued
    .replay_cache/                 # memoized LLM responses — tracked in git so
                                   # collaborators get deterministic replay
  CLAUDE.md                        # project rules for Claude Code
  pyproject.toml
```

## Model-routing summary

Defaults verified on 2026-09-29 against the [Claude model catalog](https://platform.claude.com/docs/en/models/overview) and [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model). The upgrade preserves stage roles, prompts, chunk budgets, and API endpoints. The review-apply prompt omits `temperature`, which the new reasoning models do not support at non-default values. Sonnet 5.5 now uses adaptive thinking by default; output limits include thinking tokens. Quality, latency, and cost observations from earlier runs are not benchmarks of these models.

Existing `.env` overrides still take precedence and must be updated separately. Model changes produce new replay-cache keys; existing drafts, alignments, and cached stage artifacts are not regenerated by changing defaults.

| Stage | Env var | Default | Why |
|---|---|---|---|
| `draft` / `regen` | `FORAGE_DRAFT_MODEL`, `FORAGE_REGEN_MODEL` | `anthropic:claude-opus-5-5` | Drafting and revision with `max` adaptive-thinking effort |
| `draft` fallback | `FORAGE_DRAFT_FALLBACK_MODEL` | `openai:gpt-6-astra` from Anthropic; `anthropic:claude-sonnet-5-5` from OpenAI | Cross-provider retry on exceptions or OpenAI `content_filter` |
| `coherence` | `FORAGE_COHERENCE_MODEL` | `anthropic:claude-sonnet-5-5` | Adjacent-chapter continuity review |
| `coherence-fix` | `FORAGE_COHERENCE_FIX_MODEL` | `anthropic:claude-sonnet-5-5` | Constrained adjacent-pair repairs with Anthropic as the primary provider |
| `coherence-fix` fallback | `FORAGE_COHERENCE_FIX_FALLBACK_MODEL` | `openai:gpt-6-astra` | Automatic retry when Anthropic API calls fail during repair |
| `review-apply` | `FORAGE_REVIEW_APPLY_MODEL` | `anthropic:claude-sonnet-5-5` | Minimal source-backed incorporation of published human review feedback |
| `critic:signature` | `FORAGE_CRITIC_MODEL` | `anthropic:claude-opus-5-5`; example env selects Sonnet 5.5 | Signature and voice preservation review |
| `critic:book` | `FORAGE_CRITIC_MODEL` | `anthropic:claude-sonnet-5-5` | Synopsis preservation review |
| `classify` | `FORAGE_CLASSIFY_MODEL` | `anthropic:claude-sonnet-5-5` (prompt default) | Cheap content-aware classification |
| `summarize` | `FORAGE_SUMMARIZE_MODEL` | `openai:gpt-6-astra` | Long-context synopsis generation |
| `cuts` | `FORAGE_CUTS_MODEL` | `openai:gpt-6-astra` | Removable-material inventory |
| `align` (`proofread`) | `FORAGE_ALIGN_MODEL` | `anthropic:claude-sonnet-5-5` | Source/draft paragraph alignment |
| Legacy `prime` / `prepass` / `reconsider` | `FORAGE_PRIME_MODEL`, `FORAGE_PREPASS_MODEL`, `FORAGE_RECONSIDER_MODEL` | `anthropic:claude-opus-5-5` | Signature discovery and revision |

## Known limitations

- **Budget pressure is structural.** GPT-5 has a preferred compression ratio around 1.2–2× on short inputs. Merge groups alleviate this by giving the drafter bigger combined inputs (3× compression comes naturally). Long-input mode (e.g., whole-book single-shot) swings the other way — GPT-5 over-compresses into summarize-mode.
- **Per-book role classification is coarse.** The lean plan treats every diegetic chapter the same — no per-role (signature/narrative/digressive) compression differentiation. Uniform novels are fine; uneven ones (Moby Dick's narrative vs cetology chapters) don't get the spec-recommended role-specific ratios.
- **Regen whack-a-mole on voice-dense books.** When the regen drafter touches neighboring sentences to integrate a restored passage, it can paraphrase away other signature material — the critic flags those newly-flattened passages in the next round. Visible on Henry Adams's *Education* and similar voice-heavy books. The budget-neutral regen instruction helps but doesn't eliminate the pattern.
- **Content-filter fallback changes the drafter model mid-run.** Books that trip OpenAI's content filter (Moby Dick's Loomings, Uncle Tom's Cabin in places) fall back to Sonnet for that draft. Sonnet compresses differently than GPT-5, so merge groups that fallback can produce less aggressive compression than groups that stay on GPT-5.

## Design documents

- [`spec/ABRIDGMENT_SPEC.md`](spec/ABRIDGMENT_SPEC.md) — the canonical spec that the drafter reads as prompt context and that the pipeline implements.
- [`CLAUDE.md`](CLAUDE.md) — project rules for Claude Code assistants (the approval gate for live LLM calls, etc.).
