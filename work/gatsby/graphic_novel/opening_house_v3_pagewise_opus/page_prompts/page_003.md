You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 3 of 4
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
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21
  ],
  "last_scene": "Spring 1922: Nick steps off a train into the East with a coworker who suggests sharing a house in a commuting town.",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "Nick established biographically: prominent Midwestern family, Yale 1915, Great War veteran returned restless",
    "Nick financed by his father for a year to learn the bond business in the East",
    "An unnamed office coworker introduced as the catalyst for the commuter-town housing plan"
  ],
  "visual_motifs": [
    "desk lamp and open notebook",
    "ghosted figure in window glass (Gatsby implied)",
    "memory panels with feathered edges and warmer wash",
    "train platform and travel luggage marking the move East"
  ],
  "next_page_needs": [
    "Arrival in West Egg: the rented bungalow, neighboring Gatsby's mansion, line of sight across the lawn or water",
    "First concrete glimpse or named mention of Gatsby's house",
    "Possible drive to East Egg / introduction of Daisy and Tom if pacing allows"
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s American Jazz Age; muted period authenticity in dress and interiors",
  "line_and_color": "Clean inked linework with soft watercolor washes; sepia and dusk-blue palette with cream paper tones",
  "lighting": "Warm interior lamplight against cool window light; long shadows suggesting memory and retrospection",
  "lettering": "Hand-lettered serif captions in cream caption boxes with thin black borders; minimal balloons",
  "recurring_motifs": [
    "a single desk lamp",
    "open notebook and pen",
    "window framing distant water",
    "father's photograph on the desk"
  ]
}



Existing character continuity:
- Nick Carraway: Lean young man, early thirties, neatly parted light-brown hair, thoughtful gray eyes, narrow jaw Costume: White shirt with sleeves rolled, loosened dark tie, suspenders, high-waisted wool trousers; in war flashback, U.S. Army officer's olive drab tunic and Sam Browne belt; in 1922 arrival, traveling suit with overcoat and hat Continuity: Same narrator from page 1, now bridging memory to action: war, return home, decision to go East.
- Nick's Father: Older man, silver-streaked hair, trim mustache, kind but stern eyes Costume: Dark three-piece Midwestern suit, watch chain, stiff collar Continuity: Appears briefly in a remembered conversation; render with softer linework and warmer wash.


Source units for this page:

[22] words 648-678
He found the house, a weather-beaten cardboard bungalow at eighty a month, but at the last minute the firm ordered him to Washington, and I went out to the country alone.


[23] words 679-718
I had a dog—at least I had him for a few days until he ran away—and an old Dodge and a Finnish woman, who made my bed and cooked breakfast and muttered Finnish wisdom to herself over the electric stove.


[24] words 719-741
It was lonely for a day or so until one morning some man, more recently arrived than I, stopped me on the road.


[25] words 742-752
"How do you get to West Egg village?" he asked helplessly.


[26] words 753-755
I told him.


[27] words 756-765
And as I walked on I was lonely no longer.


[28] words 766-774
I was a guide, a pathfinder, an original settler.


[29] words 775-785
He had casually conferred on me the freedom of the neighbourhood.


[30] words 786-821
And so with the sunshine and the great bursts of leaves growing on the trees, just as things grow in fast movies, I had that familiar conviction that life was beginning over again with the summer.


[31] words 822-845
There was so much to read, for one thing, and so much fine health to be pulled down out of the young breath-giving air.


[32] words 846-887
I bought a dozen volumes on banking and credit and investment securities, and they stood on my shelf in red and gold like new money from the mint, promising to unfold the shining secrets that only Midas and Morgan and Maecenas knew.


[33] words 888-950
I was rather literary in college—one year I wrote a series of very solemn and obvious editorials for the Yale News—and now I was going to bring back all such things into my life and become again that most limited of all specialists, the "well-rounded man." This isn't just an epigram—life is much more successfully looked at from a single window, after all.


[34] words 951-972
It was a matter of chance that I should have rented a house in one of the strangest communities in North America.



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