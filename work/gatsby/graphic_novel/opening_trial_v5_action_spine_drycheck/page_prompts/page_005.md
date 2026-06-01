You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 5 of 5
Target panels for this page: 5

Use ONLY the source units assigned to this page for new story content. Prior context is for continuity only.

Prior continuity context:
{
  "covered_source_unit_ids": [],
  "last_scene": "",
  "active_characters": [],
  "character_updates": [],
  "visual_motifs": [],
  "next_page_needs": []
}




Existing character continuity:
(none yet)


Source units for this page:

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
- Image prompts are for art only: no readable text, no captions, no labels, no signs, no speech balloons, no lettering. Leave negative space where lettering can be added later.
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