# Graphic novel — working status

Running state across sessions: what is in flight, what is known broken, what to
pick up next. The durable reference — architecture, geometry rationale, cost
table — lives in **[graphic-novel.md](graphic-novel.md)** and should not be
duplicated here.

Keep this short. If an entry stops being true, delete it.

_Last updated: 2026-08-11_

## State of the tree

Branch `graphic-novel-balloon-placement`, on top of `3644fc8`. `main` has not
been fast-forwarded onto it.

Tests pass: 365 passed, 6 skipped.

**Current output is `lettered_pages_v8/`.** The chain that produced it:
`storyboard.layout_v5.json` → `panel_art_jobs_v6.jsonl` → `panel_art_v6/` →
`speaker_anchors_v6.json` → `generated_pages_v8/` → `lettered_pages_v8/`.
Earlier `_v6`/`_v7` page directories are superseded; v7 differs from v8 only in
the balloon-tail attach side.

## Open findings

### 1. Balloons land on characters' faces — cause found, fix validated

**Root cause: the image model cannot use percentage arithmetic.** The art prompt
already states every text box, body box and face box as exact percentages, plus
rules like "keep all faces and mouths inside their face boxes". The model
ignores the numbers while obeying ordinal instructions (left/right speaker
order, bodies low in frame) — so it was never a layout bug or a prompt-coverage
gap. Asking harder in the same form cannot work.

**Validated fix: phrase the same geometry ordinally.** Replace "reserve x 6%,
y 20%, w 38%, h 16%" with "leave the top third as calm, uncluttered background;
no faces, heads, hands or props may enter that band", and "face in x 20%, y 48%,
w 10%, h 10%" with "seen from roughly the waist up, head and face at mid-height".

Two runs, both scored on metrics fixed before generating (44 images, $0.22):

| group | A — numeric | B — ordinal | change |
|---|---|---|---|
| dialogue (all 6 panels, 2 reps) | 1.00 | **0.46** | −54% |
| top-caption (3 panels) | 0.84 | **0.34** | −60% |
| bottom-caption (3 panels) | 1.00 | **0.47** | −53% |

Reserved/panel edge energy; lower is emptier where the text goes. Quieter than
a mirrored control: **B 42/42, A 26/42**. In the first run every B sample beat
every A sample outright.

Visual check, reserved boxes drawn over the art:

- Dialogue: under A, **6/6 panels put a face inside a text box**, usually the
  whole face. Under B, 3/6 are completely clean and 3/6 have only the top of a
  head crossing a box.
- Caption panels (42 of 48 in the book): 6/6 clean bands under B, with
  compositions still full — the band instruction does not hollow out the art.

**Residual, and it is systematic:** where B fails, the head lands just across
the *lower* edge of the balloon band (6p3, 11p1, 11p2). The model treats the
band as approximate, so a band described exactly as large as the text needs
leaves no tolerance. Next attempt should describe a band slightly deeper than
the text actually occupies, and say heads must sit clearly below it with
visible separation. Detect-and-reflow (finding 2) remains the backstop for what
survives that.

Reproduce: `scratchpad/build_ab_prompts.py` (first run),
`scratchpad/build_broad_test.py` + `score_broad.py` (broad run).

**Applied.** `forage/graphic/staging.py` turns boxes into bands and positions;
`scripts/prepare_graphic_panel_art_prompts.py` calls it instead of formatting
percentages. Across all 48 panels the staging section went from 672 percent
signs to zero, and from 799 to 393 characters. `BAND_MARGIN` (0.08) describes
the band deeper than the text needs, which is the intended fix for the residual
above. Covered by `tests/test_graphic_staging.py`, including a property test
that no digit reaches a staging section.

**`BAND_MARGIN` was tested and does not fix the residual.** Regenerating the
three failing panels through the margin (6 images, $0.03) left 6p3 and 11p1
still putting a head across the balloon box, with 11p2 borderline. Reserved-band
emptiness barely moved (0.50 to 0.47).

**Why, and it is structural rather than a tuning problem.** The panels that pass
(7p1, 10p4, 11p3) are seated or middle-distance groups, where heads sit low
naturally. Every panel that fails (6p3, 11p1, 11p2) is a close two-shot of
standing figures — and two standing figures framed from the waist up cannot have
their heads below 44% of a tall panel. The band and the shot are asking for
incompatible things, so the model honours the shot. Widening the band deepens
the conflict instead of resolving it.

The margin is kept because it costs nothing and gives the caption panels
tolerance, but it must not be read as a fix for close two-shots.

**So the prompt fix has a ceiling.** Captions solved (42 of 48 panels), dialogue
half-solved. The remainder needed the balloon to move, not the art.

### Bands split to opposite ends — the fix that closed it

There is no metadata signal for "close standing two-shot": `shot` is `medium`
for both a failing panel (6p3) and a passing one (7p1). So the fix is
structural rather than conditional.

A caption reading first used to push balloons beneath it, reserving one block
from the top of the panel down to ~0.36. That is the depth the model will not
clear. The two bands now go to opposite ends:

| | before | after |
|---|---|---|
| caption | 0.04–0.16 | 0.04–0.16 |
| balloons | 0.20–**0.36** | **0.80**–0.96 |
| top reservation | 0.36 deep | **0.20 deep** |
| staged faces | 0.48–0.58 | **0.31–0.41** |

The last row is the point: the model was measured putting heads at 0.28–0.42,
and the layout now stages them there instead of demanding a composition that
does not exist. Reading order survives — a caption that reads first is still
above balloons that read after it.

**Validated with art (6 images, $0.03): 3 of 3 previously-failing panels now
pass**, every face clear of every box, reserved/panel energy 0.38 (against 0.50
for the deep band and 0.47 for the margin attempt).

`scripts/apply_graphic_thumbnail_layout.py`, guarded by
`tests/test_graphic_band_split.py` — including that caption-last, caption-only
and balloon-only panels are left alone, and that a split line never reads
bottom-up.

**Letterboxing appeared, and was fixed.** On 2 of 3 validation panels the model
drew flat strips top and bottom and inset the scene between them rather than
continuing the room through the bands — full-bleed art became framed insets.
Adding "the reserved bands are part of the scene, not borders: continue the
room's own wall, floor, sky or shadow through them" to `staging.py` removed it:
retested at $0.03, **3 of 3 panels came back full-bleed with every face clear**.

**Follow-on defect, fixed: spike tails.** With the bands at opposite ends, a
balloon can sit a third of a panel from its speaker's mouth, and the tail was
drawn as a triangle spanning the whole distance — a white spike across the
artwork. Only visible on a composed page; every earlier check looked at bare
panel art. `_cap_tail_length` in `scripts/letter_graphic_novel_frames.py` caps
the tail at 16% of frame height while keeping its direction, which is what
comics do for a distant speaker. Covered in `tests/test_graphic_balloon_tails.py`.

### Full-chapter review of the regenerated pages (v6)

All 12 pages, 48 panels, read at full resolution. **The original bug is gone on
47 of 48 panels** — no balloon and no caption lands on a face, including page 11,
which held two of the three original failures. What the review turned up:

**1. Page 4 panel 4 — a caption still covers a face, and the cause is a gap in
the prompt, not the model.** `describe_staging` emits the head-placement rule
("every head must sit clearly below that band") only when the panel has staged
`figures`. Figures are staged on the 6 dialogue panels; **the other 42 get the
band sentence with nothing telling them where heads go.** It holds on 41 of them
and breaks on the one where the caption is itself a description of a standing
man's face, at a low angle, in a doorway — the art draws Tom's head at y
0.09–0.20 straight into a band reserved to 0.23.

**Fixed and validated.** `describe_staging` now emits the head rule whenever a
band exists, phrased conditionally — "any head or face that appears" — since
many of the 42 are landscapes and interiors where "every head" would assert a
figure the panel does not contain. Panels with staged figures keep the stronger
"every head". 42 of 48 prompts changed; the 6 dialogue panels are untouched.
Regenerating page 4 panel 4 (1 image, $0.005) puts Tom's head at y 0.25–0.31,
clearly below the band, with the reserved strip carrying continuous sunlit wall
rather than a flat block. Covered by
`tests/test_graphic_staging.py::TestHeadPlacementReachesEveryPanel`.

**2. Page 12 panel 3 — the model painted two blank caption boxes into the art.**
Flat cream rectangles, one behind the real caption and one on the lawn. The
prompt already says "no caption boxes, no speech balloons" in its hard
constraints, so this is a compliance failure rather than a missing instruction —
the same family as the letterboxing, which the band wording fixed. 1 of 48.

**3. Reserved bands cleared by washing the art out** (page 9 panel 1, page 12
panel 4). Rather than a hard strip, the model fades the lawn or floor to a pale
wash through the band. The anti-letterbox sentence forbids strips and frames; it
does not forbid draining the scene. Softer than letterboxing and easy to miss.

**4. Tails no longer spike, but they now visibly aim at the wrong thing.** The
cap works. What it exposed is finding 2 below: the anchor is the staged
`thumbnail_layout` mouth point — the left/right template at y 0.373 — not the
art. On page 11 panel 3 the speakers stand in a doorway upper-right, and Daisy's
tail points straight up at **Nick**, who is not speaking. This was masked while
balloons sat near the top, close to their anchors; moving them to the bottom
made a wrong direction long and obvious.

**5. Long captions render in markedly smaller type** (3p4, 4p4, 10p4, 12p3) —
the fit chain shrinks to fit rather than splitting, and those boxes read as a
different, harder-to-read book from their neighbours.

Nothing here is a regression of the balloon fix; 1, 4 and 5 are pre-existing
weaknesses that the fix made visible or moved into view.

### The band approach was avoidance, not a fix — balloons now sit by the speaker

Splitting the bands to opposite ends kept balloons off faces by keeping them
away from everything: a strip along the bottom, every balloon in it, tails
reaching up across the art. Nothing covered a face because nothing was near one,
and the page stopped reading as comics — the dialogue looked like a row of
subtitles under the picture.

**`--balloon-placement near-speaker` already existed and had never once run.**
It places each balloon beside its speaker's detected head and routes it around
detected faces, but it was gated on `not using_slot`, and the layout stage gives
every balloon a slot. The good path was dead code. A slot now sets the balloon's
*size* only; the speaker sets its position.

Four things had to follow from that, all free:

- **Captions are registered before balloons are placed.** They are lettered
  last, so they were painting over balloons — page 11 panel 2 lost the first two
  lines of Tom's dialogue behind one.
- **Placement scores every candidate and takes the least obstructed**, weighting
  a face 12× a caption. First-fit fell back to its own starting guess when
  nothing was clear, choosing the worst spot rather than the best.
- **Balloons avoid each other**, which zone stacking used to guarantee for free.
- **The tail is part of the balloon's silhouette.** It was a separate polygon
  drawn over the balloon, so the balloon's own outline ran across the tail's
  base — a cone resting on a box. Base widened to ~1/8 of the balloon, seam
  painted out, and the text centred rather than flush-left.

Guarded by `tests/test_graphic_balloon_placement.py`.

**What this leaves.** The art still reserves a bottom band for balloons that no
longer go there, so several panels (7p1, 11p1, 11p2) carry a dead third of floor.
The staging instruction should ask for negative space *beside and above the
speakers' heads* instead of a band at the bottom — which means regenerating the
art ($0.24) and reworking `staging.py` and `apply_graphic_thumbnail_layout.py`.
Current output: `lettered_pages_v11/`.

### Where the chapter stands after v8

1, 2 and 4 are fixed and the chapter regenerated ($0.44: 48 images at $0.24 plus
6 vision calls). Across all 12 pages **no balloon or caption lands on a face**,
and every tail points at the speaker the art actually drew.

**Letterboxing is a residual, not a regression.** It looked like the head rule
had caused it — page 7 panel 3 came back with a flat slate block above an inset
scene. Measured with the same detector over both runs, it is **2 of 48 panels
before the change and 3 of 48 after**: noise at this sample size, and the panel
that regressed most visibly (7p1) is a dialogue panel whose prompt did not
change at all. The model is simply inconsistent run to run on this. Worth
attacking through wording, not worth reading a single run as evidence.

Item 3 (bands cleared by washing the art out) did not recur; item 5 (shrunken
type on long captions) is unchanged and now the most visible cosmetic flaw.

**Do not trust reserved-band energy on its own from here.** That metric fell
from 0.50 to 0.38 when the model was letterboxing and rose to 0.60 once the
scene continued through the bands — so on this axis the *worse* page scored
better. It measures emptiness, which conflates "no faces" with "no art at all".
It is still useful for detecting a band the model ignored outright; it cannot
tell a clean band from a blank one. Always look at the page.

**Left alone deliberately:** `scripts/graphic_novel_experiment.py` has its own
duplicate numeric prompt builder around line 788. Nothing calls it — other
scripts import only unrelated helpers from that module — so it is dead for this
purpose, but it is a second copy that would reintroduce the bug if revived.

Supporting measurements on the original art, for reference:

Measured on `chapter_001_reassembled_pagewise_opus_v1`, `storyboard.layout_v4.json`:

- Planned overlap between text boxes and staged `face_box`es across all 48
  panels: **zero**. The layout does keep balloons off the faces it staged.
- But staged faces are a near-template: three variants across 12 figures, every
  face between **y 0.476 and 0.624** of the panel, derived from a `body_box`
  that is itself one of three fixed rectangles.
- The generated art puts heads much higher. On page 6 panel 3, Tom's face lands
  at roughly **y 0.09–0.23**, Nick's at **0.38–0.51** — against a staged band
  starting at 0.476.
- Balloons are planned into **y 0.20–0.36**, which is exactly where the art
  actually puts heads. The collision is structural, not incidental.

So the staged `face_box` is a guess that the art never agreed to honour, and
every downstream avoidance decision is made against that guess.

Three directions, roughly in order of cost:

1. Feed the staged figure boxes into the art prompt hard enough that the art
   complies (cheapest, but asks the image model for spatial obedience it has not
   so far shown).
2. Detect faces in the returned art and reflow balloons around what is actually
   there. `scripts/graphic_speaker_anchor.py` already does vision detection for
   mouths — the same pass could supply real face boxes. Costs a vision call per
   panel.
3. Reserve the top band unconditionally and place figures below it, so the plan
   stops depending on where the art puts heads.

### 2. Tail anchors aim at torsos, not mouths — resolved

The fallback anchor was the layout's staged `mouth_point`, a left/right template
at y 0.373. Tails therefore pointed wherever the template said, not where the
art drew the speaker: on page 11 panel 3 Daisy's tail pointed at **Nick**.

**Fixed by running the anchor stage that already existed.** No new code was
needed — `scripts/graphic_speaker_anchor.py` detects mouths, and
`compose_graphic_panel_page` already accepts `--anchors-json`; the chapter had
simply been lettered without it. It skips panels with no speech, so this chapter
cost 6 vision calls. All 12 anchors came back `visible` at confidence 0.83–0.90,
and every balloon in `lettered_pages_v8/layout.json` now reads
`anchor_source: detection`.

**One rendering bug surfaced once tails aimed truthfully.** `_attach_side` chose
the balloon edge by testing x before y, so a speaker mostly *above* a balloon but
slightly to one side attached sideways: on page 7 panel 1 Daisy's tail was 141px
tall and 18px wide, a sliver reading as a stray dark line rather than a wedge.
The edge is now chosen by whichever one the speaker is furthest beyond. Covered
by `tests/test_graphic_balloon_tails.py::TestAttachSide`.

### 3. The placeholder-art harness cannot catch finding 1

`scripts/graphic_placeholder_art.py` renders each panel by painting that panel's
own `body_box` and `face_box` into a flat image. That is exactly the assumption
under test, so the harness is self-consistent by construction: placeholder faces
are always where the layout staged them, and a balloon that would cover a real
face never covers a placeholder one.

It remains useful for what it was built for — it is how the tail bug in finding
2 was found. But it cannot answer "does the art get covered", and reading a
clean placeholder run as evidence of that would be wrong.

## Next threads

Ordered by what the v6 review says is worth doing, cheapest first:

- **Wire the anchor stage into the driver.** It is now proven to work, but it
  still has to be invoked by hand; a chapter lettered without `--anchors-json`
  silently falls back to the template that pointed Daisy's tail at Nick.
- **Add "do not drain or fade the scene" to the anti-letterbox wording**, and
  fold blank caption boxes into it explicitly. Letterboxing sits at ~2–3 of 48
  panels and is the last art-side defect.
- **Split long captions across boxes instead of shrinking the type**, so the
  handful of dense panels read like the rest of the book.

- **Fold the slots stage into layout.** Layout runs immediately after slots in
  every driver and overwrites its slot boxes, `lettering_constraints`,
  `panel_archetype` and `speaker_region`. Only its report survives. Called out
  in `graphic-novel.md` as the obvious next simplification.
- **Stale model ids.** Several prompts still pin `model: openai:gpt-5`, no
  longer a listed model. They work today; they should move to a current id.
- **Finish the `scripts/` → `forage/graphic/` migration.** Done: `letter`,
  `layout`, `art`, `summarize`. Still direct script invocations: the LLM
  authoring stages, compose, QA, packaging.

## Re-orienting quickly

```bash
.venv/bin/python -m pytest tests/ -q          # 318 pass, <1s
git status --short                            # scope of uncommitted work
ls -lat work/gatsby/graphic_novel/            # newest run dir
```

The active run is `work/gatsby/graphic_novel/chapter_001_reassembled_pagewise_opus_v1`.
`debug_pages/` holds lettered pages with anchor markers drawn — read those, not
`generated_pages/`, which is art before lettering.

Reminder from `CLAUDE.md`: any stage that issues a live LLM or image call needs
explicit human approval first, including under `FORAGE_REPLAY=1`.
