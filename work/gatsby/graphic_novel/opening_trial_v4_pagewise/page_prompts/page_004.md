You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 4 of 4
Target panels for this page: 5

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
  "last_scene": "Nick settles into a modest West Egg bungalow alone; a small encounter grants him a sense of belonging as summer blooms, and he equips himself with books and a focused outlook, sensing the strangeness of his new community.",
  "active_characters": [
    "Nick Carraway",
    "Finnish Woman",
    "Man on the Road"
  ],
  "character_updates": [
    "Nick takes the bungalow alone after his colleague is sent to Washington.",
    "Nick briefly has a dog, owns an old Dodge, and hires a Finnish housekeeper.",
    "A stranger’s request for directions ends Nick’s initial loneliness and makes him feel at home.",
    "Nick embraces summer optimism, study in finance, and a renewed yet focused self-conception.",
    "Nick notes by chance he has rented in a particularly strange community."
  ],
  "visual_motifs": [
    "porch railings and bungalow thresholds",
    "spring foliage bursting like fast movies",
    "single window framing Nick’s outlook",
    "suitcase on a roadside (newcomer/arrival)"
  ],
  "next_page_needs": [
    "Introduce the geography of the Eggs and the bay to clarify the 'strangest communities' remark.",
    "Contrast Nick’s shabby bungalow with the neighboring mansions to establish scale and tone.",
    "Begin to place key neighbors in space (without full introductions) to set up ensuing encounters."
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s America with flashbacks to the 1910s Midwest",
  "line_and_color": "Clean ink lines with selective hatching; muted, slightly desaturated palette with warm sepias for memory and cooler neutrals for present reflections",
  "lighting": "Bright, crisp spring light for the move East; soft, interior daylight for domestic moments",
  "lettering": "Classic serif narrative captions; dialogue in understated, readable roman; generous negative space for dense narration",
  "recurring_motifs": [
    "porch railings and straight lines (order/reserve)",
    "train platforms and suitcases (transit between East/West)",
    "seasonal foliage: spring blossoms for new start",
    "windows and thresholds (observation vs participation)"
  ]
}



Existing character continuity:
- Nick Carraway: Lean, tidy side-parted hair, watchful eyes; often framed slightly apart as an observer Costume: Conservative dark three-piece suit, white shirt, slim tie; hat and overcoat when outdoors; modest shirtsleeves at home Continuity: Narrating in first person; arrives in a commuting town and settles into a modest bungalow
- Nick's Father: Middle-aged gentleman with neatly trimmed mustache and steady gaze Costume: Early 1910s–1920s Midwestern attire: shirt, vest, jacket; pocket watch chain visible Continuity: Appears in memories and moments of guidance/support; presence signals Nick’s moral frame and practical support
- Jay Gatsby (glimpsed): Elegant male silhouette, back turned or softly out of focus, suggesting poise without revealing features Costume: Immaculate suit suggested by clean lines and tailored silhouette Continuity: Introduced as an idea through Nick’s reflection; avoid concrete identifiers until formally met in-story
- Young Man at the Office: Clean-cut clerk in shirtsleeves and tie, energetic posture Costume: 1920s office wear: white shirt, suspenders, narrow tie, sleeve garters Continuity: Colleague who proposes sharing a house in a commuting town
- Finnish Woman: Sturdy, middle-aged with hair in a bun or kerchief; practical, focused demeanor Costume: Plain 1920s house dress with apron; sensible shoes Continuity: Housekeeper who makes Nick’s bed and cooks breakfast; often near an electric stove
- Man on the Road: Youngish newcomer with suitcase, slightly disoriented posture, hat in hand Costume: Simple 1920s travel wear: light suit, tie, soft hat; scuffed shoes from travel Continuity: Recent arrival who asks Nick for directions, triggering Nick’s sense of belonging


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
- Do not include content from later source units.
- Do not include content from prior source units except as visual continuity.
- If these source units express chronology or cause/effect, make that sequence explicit in the panel beats and captions.
- Do not collapse chronology into a symbolic montage when separate panels would make the sequence clearer.
- Each panel must map to one source unit or adjacent source units.
- Dialogue must come from these source units when possible. If there is no dialogue, use a caption instead of invented speech.
- Image prompts are for art only: no readable text, no captions, no labels, no signs, no speech balloons, no lettering. Leave negative space where lettering can be added later.
- Keep image prompts concrete: setting, action, blocking, expression, lighting, period costume, and mood.
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