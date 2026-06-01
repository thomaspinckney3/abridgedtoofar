You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 2 of 12
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
    11,
    12,
    13
  ],
  "last_scene": "Nick stands at his study window after writing the opening of his manuscript, looking toward a distant silhouetted Gatsby across the water.",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "Nick established as the writing narrator working at a desk in shirtsleeves",
    "Nick's Father introduced solely via flashback with his counsel about judgement",
    "Gatsby seeded as a distant silhouette; face not yet shown"
  ],
  "visual_motifs": [
    "writing desk and manuscript pages as the recurring frame",
    "warm lamp light against cool blue exterior",
    "ghost-figures of confiders around the narrator",
    "seismograph-like ripples in the sky behind Gatsby"
  ],
  "next_page_needs": [
    "Transition from the writing-frame to the actual chronological start: Nick's move East and arrival at West Egg",
    "First proper reveal of Gatsby's face or full figure deferred until a later, narratively earned panel",
    "Introduction of the Buchanans or the geography of West Egg / East Egg as the next concrete locations"
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s American Jazz Age, post-WWI New York and Midwest",
  "line_and_color": "Clean ink linework with muted Art Deco palette: dusky blues, warm sepia, cream, and faded gold accents",
  "lighting": "Soft window light and lamp glow indoors; overcast melancholy outdoors; selective warm highlights on the narrator",
  "lettering": "Hand-drawn rectangular caption boxes in cream with charcoal type; sparing speech balloons reserved for staged exchanges",
  "recurring_motifs": [
    "reserved judgement gaze",
    "father's remembered voice",
    "distant seismograph-like ripples of light",
    "manuscript pages and writing desk"
  ]
}



Existing character continuity:
- Nick Carraway: Lean young man, neatly combed light-brown hair, attentive eyes, slight reserved smile Costume: Sober three-piece tweed suit, soft collar shirt, knit tie; later seen in shirtsleeves at his desk Continuity: Narrator and viewpoint; introduced on page 1 as the writer recalling the events
- Nick's Father: Older man with graying mustache, kind reserved eyes, resemblance to Nick Costume: Edwardian-cut dark suit, vest, watch chain Continuity: Appears only in remembered flashback; not present in current timeline
- Jay Gatsby: Tall silhouette, impeccable posture, face kept in shadow or turned away on first appearance Costume: Pale summer suit, dark tie; outline only on this page Continuity: First glimpsed only as a distant silhouette in a final panel; full reveal reserved for later pages


Source units for this page:

[14] words 405-454
This responsiveness had nothing to do with that flabby impressionability which is dignified under the name of the "creative temperament"—it was an extraordinary gift for hope, a romantic readiness such as I have never found in any other person and which it is not likely I shall ever find again.


[15] words 455-493
No—Gatsby turned out all right at the end; it is what preyed on Gatsby, what foul dust floated in the wake of his dreams that temporarily closed out my interest in the abortive sorrows and short-winded elations of men.


[16] words 494-508
My family have been prominent, well-to-do people in this Middle Western city for three generations.


[17] words 509-529
I graduated from New Haven in 1915, and later took part in that delayed Teutonic migration known as the Great War.


[18] words 530-540
I enjoyed the counter-raid so thoroughly that I came back restless.


[19] words 541-571
Instead of being the warm centre of the world, the Middle West now seemed like the ragged edge of the universe—so I decided to go East and learn the bond business.


[20] words 572-594
Father agreed to finance me for a year, and after various delays I came East, permanently, I thought, in the spring of twenty-two.


[21] words 595-648
The practical thing was to find rooms in the city, but it was a warm season, and I had just left a country of wide lawns and friendly trees, so when a young man at the office suggested that we take a house together in a commuting town, it sounded like a great idea.


[22] words 649-679
He found the house, a weather-beaten cardboard bungalow at eighty a month, but at the last minute the firm ordered him to Washington, and I went out to the country alone.


[23] words 680-719
I had a dog—at least I had him for a few days until he ran away—and an old Dodge and a Finnish woman, who made my bed and cooked breakfast and muttered Finnish wisdom to herself over the electric stove.


[24] words 720-742
It was lonely for a day or so until one morning some man, more recently arrived than I, stopped me on the road.


[25] words 743-753
"How do you get to West Egg village?" he asked helplessly.


[26] words 754-756
I told him.


[27] words 757-766
And as I walked on I was lonely no longer.


[28] words 767-775
I was a guide, a pathfinder, an original settler.


[29] words 776-786
He had casually conferred on me the freedom of the neighbourhood.


[30] words 787-822
And so with the sunshine and the great bursts of leaves growing on the trees, just as things grow in fast movies, I had that familiar conviction that life was beginning over again with the summer.



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
- Do not use speech balloons for lone-speaker remarks, remembered advice, or
  one-off informational questions. Put those in the caption as reported action.
  Reserve balloons for real multi-speaker exchanges where the dialogue order
  and speaker locations both matter.
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