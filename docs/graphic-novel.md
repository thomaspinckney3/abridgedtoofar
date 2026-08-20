# Graphic novel pipeline

Turns an abridged prose chapter into lettered comic pages.

> This document is the durable reference: how the pipeline works and why.
> For what is in flight, what is known broken, and what to pick up next, see
> **[graphic-novel-status.md](graphic-novel-status.md)**.

Every stage reads a storyboard JSON and writes a storyboard JSON. That single
shape is what lets stages be reordered, rerun, and inspected between steps — if
you can read the storyboard, you can see exactly what any stage did.

```
chapter prose
   │
   ├─ beats ────────► story structure          LLM
   ├─ storyboard ───► pages, panels, captions   LLM
   ├─ dialogue ─────► speech + thought balloons LLM
   │
   ├─ letter ───────► fit dialogue to balloons  free
   ├─ slots ────────► reserve lettering zones   free
   ├─ layout ───────► panel/balloon/figure boxes free
   │
   ├─ art-prompts ──► one generation job/panel  free
   ├─ art ──────────► panel images              $$$ images
   ├─ compose ──────► composite + letter pages  free
   │
   ├─ qa ───────────► vision check on the art   LLM
   └─ package ──────► PDF + contact sheets      free
```

## Running it

Stages that have been migrated are `forage graphic <stage>`; the rest are still
`python -m scripts.<name>` (see *Migration status* below).

```bash
# free, deterministic — run these as often as you like
forage graphic letter  storyboard.json --out-json sb.lettered.json --out-report letter.json
forage graphic layout  sb.lettered.json --out-json sb.layout.json --rough-dir rough/

# costs money — both refuse to spend without an explicit flag
forage graphic summarize sb.layout.json --book-id gatsby --run-dir run/ \
    --out-json sb.final.json --dry-run          # drop --dry-run to spend
forage graphic art jobs.jsonl --out-dir art/    # estimate only
forage graphic art jobs.jsonl --out-dir art/ --yes   # actually generates
```

`forage graphic art` prints a cost table and exits unless you pass `--yes`.
Images that already exist are skipped, so re-running after a failure pays only
for the panels still missing.

## The fitting chain

A line of dialogue that does not fit a balloon is handled in three steps, in
this order, because each is more lossy than the last:

1. **It fits** — nothing happens. Balloon budget is 95 characters.
2. **Split** (`graphic_balloon_split`) — break it across two linked balloons
   from the same speaker, at a sentence boundary, or at a clause joint with an
   ellipsis carried out of one balloon and into the next. Free and lossless:
   every word survives.
3. **Compress** (`forage graphic summarize`) — an LLM keeps what the character
   *does* by speaking (decide, demand, reveal, refuse) and drops what the art
   already shows. Costs money, so it only sees lines that failed both lossless
   options. Every result is validated — it must fit, must introduce no name
   absent from the original, and must differ from the input — and a failing
   result leaves the line untouched rather than reaching the page.

The best fix is upstream: `prompts/graphic_dialogue_draft.md` tells the drafter
to select the plot-driving part of a long speech, so most lines never need
steps 2 or 3.

## Geometry

Two coordinate systems, deliberately:

- **Page fractions** (`forage.graphic.geometry.Box`, `x/y/w/h` in 0–1) are what
  stages exchange and what is stored in the storyboard. They survive a change
  of output resolution.
- **Pixels** are what the compositor and letterer draw in. Convert at the edge
  with `Box.to_pixel_rect(width, height)`, never earlier.

`forage/graphic/geometry.py` is the single source for panel rectangles, the
canonical grids, page size, and panel capacity. It exists because the layout
stage and the compositor each used to carry their own copy: two `Box` classes
with incompatible fields, two page-size readers, and two six-panel grids. They
agreed at 1536×2048 and nowhere else — at 1536×3072 the bottom panel came out
0.557 of the page in one and 0.330 in the other, so balloons were planned
against one grid and drawn against another.

**If you add a grid or change a margin, change it here and nowhere else.**

### Panel capacity

How many speakers a panel can hold is a question about its rectangle, so it
lives with the geometry. A wide panel that is also tall (or large enough by
area) seats 3 figures; anything else seats 2. A panel may carry one balloon
more than it has figures, so a single speaker can hold a split line.

Three stages act on that number and all three read it from `panel_capacity`:
the lettering policy caps balloons, the slots stage reserves a zone for each,
and the layout caps figures. A stage that capped lower on its own would reserve
no space for a balloon the layout places anyway — the art then comes back with
nothing kept clear where that balloon lands.

Boxes are resolved *per page*, through `panel_boxes`, not read off individual
panels. Most pages arrive unplaced and are gridded downstream, so a stage that
only looks for `panel["box"]` silently skips every check that depends on the
rectangle.

### Balloon tails

A tail is aimed at one of three things, in falling order of confidence:

1. **A detected anchor** — `graphic_speaker_anchor` looks at the art that came
   back and finds the speaker's mouth. Best, but costs a vision call per panel.
2. **The layout's staged mouth** — `thumbnail_layout.figures[].mouth_point`,
   where the layout put the figure and what the art prompt asked for.
3. **A fixed fraction of the panel** — `ANCHOR_Y["mouth"]`, 0.34. A guess.

Only (1) existed as a real source; without it the letterer dropped straight to
(3) and aimed every tail at 0.34 regardless of where the layout had staged the
figure — typically 0.54. Tails pointed at empty art, and on a four-line balloon
the anchor landed *inside* the balloon, so the tail was drawn from the bottom
edge back up through its own last two lines. Six of twelve balloons on Gatsby
pages 6/7/11.

Whatever the source, the anchor is projected outside the balloon before an
attach side is chosen (`_anchor_outside_balloon`). A tail that points inward is
never correct, and a balloon tall enough to cover its own anchor is easy to
write and hard to notice.

### Reading order

Balloons are normally placed one per speaker, side by side. When a panel
contains a split line the layout stacks strictly in text order instead —
otherwise the other speaker's balloon sits level with the split's first half and
the reader crosses into it mid-sentence.

## Artifacts

Stages write beside their input with a stage suffix, so intermediate states
survive for inspection:

| file | written by |
|---|---|
| `storyboard.json` | storyboard stage |
| `storyboard.policy_vN.json` | lettering policy |
| `storyboard.slots_vN.json` | lettering slots |
| `storyboard.layout_vN.json` | thumbnail layout |
| `storyboard.panel_art_vN.json` | art-prompt prep |
| `*_report.json` | every stage, alongside its output |
| `art/page_NNN_panel_NNN.png` | panel art |
| `lettered_pages/` | compose |

Rough-in thumbnails (`--rough-dir`) render a whole page as coloured boxes in
about 15 ms with no art and no LLM. That is the fast loop for layout work —
use it to settle balloon placement before generating anything.

## Models and cost

| stage | model | typical cost |
|---|---|---|
| beats / storyboard / dialogue | `openai:gpt-5.6-terra` | ~$0.03–0.07 per call |
| summarize | `openai:gpt-5.6-terra` | ~$0.01 per chapter |
| art | `gpt-image-2`, quality `low` | ~$0.005 per panel |

Quality defaults to `low` throughout: panel art gets iterated on constantly, and
the questions it has to answer — does the balloon cover the face, is the figure
where the layout staged it — are legible at low fidelity. Raise it only for a
final render.

Override a model per stage with `FORAGE_<STAGE>_MODEL`, or globally with
`FORAGE_MODEL`. Set `FORAGE_REPLAY=1` to memoize responses so reruns are free.

> Several prompts still pin `model: openai:gpt-5`, which is no longer listed as
> available. They work today but should be moved to a current model id.

## Migration status

The graphic pipeline is being moved out of `scripts/` into `forage/graphic/`
behind `forage graphic`. Migrated so far:

- `forage/graphic/geometry.py` — panel rectangles, grids, capacity
- `forage/graphic/panel_art.py` — panel art generation
- `forage/graphic/cli.py` — `letter`, `layout`, `art`, `summarize`

Still in `scripts/`, invoked directly: the LLM authoring stages (`graphic_beat_
list`, `graphic_storyboard*`, `graphic_dialogue_draft`), the deterministic
lettering internals (`apply_graphic_lettering_policy`, `apply_graphic_lettering_
slots`, `apply_graphic_thumbnail_layout`), composition (`compose_graphic_panel_
page`, `letter_graphic_novel_*`), QA (`graphic_image_qa`), and packaging.

Every stage that reasons about a panel rectangle now reads it from
`forage.graphic.geometry` — grids, page size, wideness, and capacity. Nothing
outside that module computes a panel box, and no hand-written grid or
hardcoded threshold is left in `scripts/`.

The slots stage is the odd one out: the layout stage runs immediately after it
in every driver and overwrites its slot boxes, `lettering_constraints`,
`panel_archetype` and `speaker_region`. What survives is its report — so the
value in keeping it honest about capacity is that its warnings are true, not
that its geometry reaches the page. Folding it into the layout stage is the
obvious next simplification.

## Testing

```bash
.venv/bin/python -m pytest tests/ -q
```

The graphic tests cover the parts that are cheap to get wrong and expensive to
notice: geometry agreement between planning and rendering
(`test_graphic_compose_geometry.py`), the fitting chain and its losslessness
property against every storyboard in `work/` (`test_graphic_balloon_split.py`),
capacity and reading order (`test_graphic_geometry.py`), balloon-cap agreement
between the slots and layout stages (`test_graphic_lettering_slots.py`), tail
anchoring (`test_graphic_balloon_tails.py`), and the spending behaviour of art
generation (`test_graphic_panel_art.py`). None of them call a model or an image
API.

### Rendering without paying

The compositor and letterer can be exercised end to end on placeholder art:
generate a flat image per panel at the size its art job asks for, painting the
panel's own `body_box` and `face_box` from `thumbnail_layout` into it. Anything
that overlaps a face box is then the pipeline covering a figure it staged
itself, which is a question worth answering before spending anything on art.
That is how the tail bug above was found — it is invisible in the rough-in
thumbnails, because those draw balloons as plain rectangles with no tails.
