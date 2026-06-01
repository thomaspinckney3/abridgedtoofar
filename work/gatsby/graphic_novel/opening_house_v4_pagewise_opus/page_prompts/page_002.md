You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 2 of 4
Target panels for this page: 4

Use ONLY the source units assigned to this page for new story content. Prior context is for continuity only.

Prior continuity context:
{
  "covered_source_unit_ids": [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11
  ],
  "last_scene": "Nick at his writing desk after returning from the East, having just begun his memoir and reflected on his father's advice and the limits of his tolerance.",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "Nick established as reserved, observant narrator writing in retrospect",
    "Father introduced only as a memory figure, not a present character"
  ],
  "visual_motifs": [
    "writing desk and open journal",
    "window light",
    "sepia memory tone",
    "the East as a horizon"
  ],
  "next_page_needs": [
    "Transition from the writing desk into the East: Nick's arrival in West Egg",
    "Introduce the physical setting of Long Island, the bungalow, and the neighboring Gatsby estate",
    "Prepare to introduce Daisy and Tom Buchanan"
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s American Jazz Age, post-WWI Midwest and East Coast",
  "line_and_color": "Clean inked linework with muted watercolor washes; sepia and dusty blues for memory, warmer ambers for present",
  "lighting": "Soft window light and lamp glow; long shadows suggesting introspection",
  "lettering": "Hand-lettered serif captions in rectangular boxes for Nick's narration; classic round speech balloons reserved for spoken lines",
  "recurring_motifs": [
    "the writing desk and journal",
    "window light",
    "father's remembered figure",
    "the East as a distant horizon"
  ]
}



Existing character continuity:
- Nick Carraway: Lean young man, neat side-parted light brown hair, calm observant eyes, slight reserved posture Costume: White shirt with rolled sleeves, vest and loosened tie; in memory panels, a younger collegiate sweater Continuity: Introduced this page as the narrator, writing in retrospect after returning from the East.
- Nick's Father: Older man, graying mustache, kind but reserved eyes, seated upright Costume: Three-piece Midwestern suit, watch chain across the vest Continuity: Appears only in Nick's memory; not a present-tense character.


Source units for this page:

[12] words 336-361
Only Gatsby, the man who gives his name to this book, was exempt from my reaction—Gatsby, who represented everything for which I have an unaffected scorn.


[13] words 362-403
If personality is an unbroken series of successful gestures, then there was something gorgeous about him, some heightened sensitivity to the promises of life, as if he were related to one of those intricate machines that register earthquakes ten thousand miles away.


[14] words 404-453
This responsiveness had nothing to do with that flabby impressionability which is dignified under the name of the "creative temperament"—it was an extraordinary gift for hope, a romantic readiness such as I have never found in any other person and which it is not likely I shall ever find again.


[15] words 454-492
No—Gatsby turned out all right at the end; it is what preyed on Gatsby, what foul dust floated in the wake of his dreams that temporarily closed out my interest in the abortive sorrows and short-winded elations of men.


[16] words 493-507
My family have been prominent, well-to-do people in this Middle Western city for three generations.


[17] words 508-528
I graduated from New Haven in 1915, and later took part in that delayed Teutonic migration known as the Great War.


[18] words 529-539
I enjoyed the counter-raid so thoroughly that I came back restless.


[19] words 540-570
Instead of being the warm centre of the world, the Middle West now seemed like the ragged edge of the universe—so I decided to go East and learn the bond business.


[20] words 571-593
Father agreed to finance me for a year, and after various delays I came East, permanently, I thought, in the spring of twenty-two.


[21] words 594-647
The practical thing was to find rooms in the city, but it was a warm season, and I had just left a country of wide lawns and friendly trees, so when a young man at the office suggested that we take a house together in a commuting town, it sounded like a great idea.



Rules:
- Preserve source-unit order exactly.
- Cover every assigned source unit. Do not omit a source unit from the page.
- The page's `source_unit_ids` must be the complete assigned list in order.
- The panels' `source_unit_ids`, read in panel order, must cover the complete
  assigned list in order. No gaps.
- Do not include content from later source units.
- Do not include content from prior source units except as visual continuity.
- Build each page around a concrete action spine: the reader should always know
  where Nick physically is, what he is doing, and why the next panel follows.
- For abstract exposition, do not create detached symbolic tableaux. Attach the
  narration to visible behavior such as writing, packing, arriving, walking,
  reading, speaking with another person, looking from a window, or entering a
  room.
- For geography, avoid standalone map/aerial context unless it is anchored to a
  character's route or vantage. Prefer concrete movement: train, station, road,
  ferry/shoreline, bungalow, window, neighboring estate, and line-of-sight.
- Each page summary should state the physical action first, then the abstract
  meaning. Example shape: "Nick returns home and begins writing; while he does,
  he recalls..."
- Each panel beat must be an observable action or decision, not only a theme.
- If these source units express chronology or cause/effect, make that sequence explicit in the panel beats and captions.
- Do not collapse chronology into a symbolic montage when separate panels would make the sequence clearer.
- Each panel must map to one source unit or adjacent source units.
- Dialogue must come from these source units when possible. If there is no dialogue, use a caption instead of invented speech.
- Every panel must have exactly one non-empty caption. The caption belongs
  inside the panel art as a reserved caption slot; never leave a panel with
  dialogue only.
- Captions must be readable comic narration, not formatting notes. Do not use
  `//`, slash separators, bullet syntax, or labels inside caption text.
- Avoid speech balloons by default. Use dialogue only when the source contains
  an explicit spoken line and the visible speaker is staged clearly in that
  same panel. If the speaker is absent, off-panel, only remembered, or hard to
  anchor visually, carry the information in the caption instead.
- If one speaker needs multiple short balloons, keep all of that speaker's
  balloons near the same staged figure; do not assign the same speaker to both
  sides of the panel.
- Image prompts are for art only: no readable text, no captions, no labels, no signs, no speech balloons, no lettering.
- Lettering space is part of the art plan, not a post-hoc repair. Every panel
  must define explicit in-panel `lettering_slots`, and the image prompt must
  reserve those exact empty areas before art is generated.
- Do not place caption boxes or balloons in gutters or outside panel frames.
- Use one of these panel archetypes: `caption_only`, `single_character`,
  `two_character`, `three_character_wide`.
- Use `single_character` for one visible speaker, `two_character` for two
  visible speakers, and `three_character_wide` only for a full-width panel with
  three visible speakers.
- If a panel has dialogue, stage speakers in the same left-to-right order as
  the balloon reading order. If this cannot be done clearly, omit the weaker
  balloon and carry the information in the caption.
- Keep faces, mouths, active hands, key props, and important gestures outside
  every lettering slot.
- Keep image prompts concrete: setting, action, blocking, expression, lighting, period costume, and mood.
- If the source is mostly context-setting, use a recurring frame action to hold
  it together rather than scattering unrelated images.
- If you need a montage, explain why in `adaptation_note`.

Return strict JSON only:

{
  "style_bible": {
    "visual_period": string,
    "line_and_color": string,
    "lighting": string,
    "lettering": string,
    "recurring_motifs": [string]
  },
  "characters": [
    {
      "name": string,
      "visual_anchor": string,
      "costume": string,
      "expression_range": string,
      "continuity_note": string
    }
  ],
  "page": {
    "page_number": number,
    "page_summary": string,
    "source_unit_ids": [number],
    "source_word_range": [number, number],
    "panels": [
      {
        "panel_number": number,
        "beat": string,
        "shot": "establishing" | "wide" | "medium" | "close" | "detail" | "silent",
        "image_prompt": string,
        "panel_archetype": "caption_only" | "single_character" | "two_character" | "three_character_wide",
        "lettering_slots": [
          {
            "id": string,
            "kind": "caption" | "speech" | "thought",
            "zone": "top_left" | "top_center" | "top_right" | "bottom_left" | "bottom_center" | "bottom_right",
            "box": {"x": number, "y": number, "w": number, "h": number},
            "speaker": string,
            "speaker_side": "left" | "center" | "right",
            "reserved_for": string,
            "reading_order": number
          }
        ],
        "caption_zone": "top_left" | "top_center" | "top_right" | "bottom_left" | "bottom_center" | "bottom_right",
        "caption": string,
        "dialogue": [
          {"speaker": string, "text": string}
        ],
        "sfx": [string],
        "continuity_notes": string,
        "source_unit_ids": [number],
        "source_word_range": [number, number],
        "source_anchor": string,
        "adaptation_note": string
      }
    ]
  },
  "continuity_state": {
    "covered_source_unit_ids": [number],
    "last_scene": string,
    "active_characters": [string],
    "character_updates": [string],
    "visual_motifs": [string],
    "next_page_needs": [string]
  }
}