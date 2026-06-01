You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 4 of 4
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
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34
  ],
  "last_scene": "Nick, settled alone in the West Egg bungalow, shelves his new finance volumes by the window as summer begins—aware he has landed in one of the strangest communities in North America.",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "Coworker written out (sent to Washington); Nick is alone in West Egg",
    "Nick's household established: old Dodge, briefly a dog, a Finnish housekeeper",
    "Nick adopts a summer self-improvement program centered on banking and credit"
  ],
  "visual_motifs": [
    "desk lamp and open notebook",
    "father's photograph on the desk",
    "stack of red-and-gold finance volumes",
    "window framing a sliver of distant water",
    "bursting spring leaves along the country road"
  ],
  "next_page_needs": [
    "First concrete reveal of Gatsby's mansion next door—line of sight from Nick's lawn or window",
    "Geography of West Egg vs. East Egg across the bay/water",
    "Drive or ferry across to East Egg to introduce Daisy and Tom Buchanan"
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
    "father's photograph on the desk",
    "stack of red-and-gold finance volumes"
  ]
}



Existing character continuity:
- Nick Carraway: Lean young man, early thirties, neatly parted light-brown hair, thoughtful gray eyes, narrow jaw Costume: Traveling suit on arrival; at the bungalow, white shirt with rolled sleeves, loosened dark tie, suspenders, high-waisted wool trousers; soft cardigan optional for morning road scene Continuity: Same narrator; now physically settled alone in the West Egg bungalow.
- Nick's Father: Older man, silver-streaked hair, trim mustache, kind but stern eyes Costume: Dark three-piece Midwestern suit, watch chain, stiff collar Continuity: Appears briefly in a remembered conversation; render with softer linework and warmer wash.
- Finnish Housekeeper: Stout middle-aged woman, ruddy cheeks, hair in a low bun, capable hands Costume: Plain dark dress, white apron Continuity: New minor character; appears only in the bungalow kitchen.
- Lost Stranger: Young man newer to the area than Nick, hat in hand, uncertain stance Costume: Light summer suit, straw boater, walking shoes Continuity: One-off speaker on the country road.


Source units for this page:

[35] words 973-999
It was on that slender riotous island which extends itself due east of New York—and where there are, among other natural curiosities, two unusual formations of land.


[36] words 1000-1041
Twenty miles from the city a pair of enormous eggs, identical in contour and separated only by a courtesy bay, jut out into the most domesticated body of salt water in the Western hemisphere, the great wet barnyard of Long Island Sound.


[37] words 1042-1058
To the wingless a more interesting phenomenon is their dissimilarity in every particular except shape and size.


[38] words 1059-1089
I lived at West Egg, the—well, the less fashionable of the two, though this is a most superficial tag to express the bizarre and not a little sinister contrast between them.


[39] words 1090-1120
My house was at the very tip of the egg, only fifty yards from the Sound, and squeezed between two huge places that rented for twelve or fifteen thousand a season.


[40] words 1121-1172
The one on my right was a colossal affair by any standard—it was a factual imitation of some Hôtel de Ville in Normandy, with a tower on one side, spanking new under a thin beard of raw ivy, and a marble swimming pool, and more than forty acres of lawn and garden.


[41] words 1173-1176
It was Gatsby's mansion.


[42] words 1177-1195
Or, rather, as I didn't know Mr. Gatsby, it was a mansion inhabited by a gentleman of that name.


[43] words 1196-1238
My own house was an eyesore, but it was a small eyesore, and it had been overlooked, so I had a view of the water, a partial view of my neighbour's lawn, and the consoling proximity of millionaires—all for eighty dollars a month.



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