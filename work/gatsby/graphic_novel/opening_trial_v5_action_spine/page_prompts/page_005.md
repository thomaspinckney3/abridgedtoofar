You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 5 of 5
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
    34,
    35,
    36
  ],
  "last_scene": "West Egg shoreline outside Nick’s bungalow, afternoon (flashback)",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "After giving directions, Nick feels at home—‘a guide’ with the freedom of the neighborhood.",
    "He embraces the start of summer, planning to read and restore his health.",
    "He buys and shelves a dozen red-and-gold volumes on banking to pursue a serious, ‘well-rounded’ self.",
    "He walks to the bay and fixes the Eggs’ geography from his West Egg shoreline vantage."
  ],
  "visual_motifs": [
    "Sepia-tinged memories of travel and country roads",
    "Weather-beaten bungalow",
    "Porch swing and summer cicada dusk",
    "Fountain pen and open notebook",
    "Shoreline vista across a courtesy bay"
  ],
  "next_page_needs": [
    "Explicitly distinguish West Egg and East Egg and their social contrast.",
    "Orient Nick’s bungalow relative to the neighboring estates, including Gatsby’s, by clear line-of-sight.",
    "Maintain Nick’s shoreline vantage to introduce the bay as a separator and foreshadow connections across it."
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s America with brief flashbacks to Midwestern 1900s-1910s and college years",
  "line_and_color": "Clean, expressive linework with restrained, naturalistic color; present-day scenes in neutral tones, flashbacks with a soft sepia wash",
  "lighting": "Present: warm desk-lamp pools of light against evening shadows; Flashbacks: bright spring-summer sunlight with soft sepia tint, deep greens and sky-blues muted by age-wash",
  "lettering": "First-person narration in classic serif caption boxes; quoted memories set in italic captions or caption-with-quote; dialogue balloons for in-scene speakers",
  "recurring_motifs": [
    "Fountain pen and open notebook",
    "Pool of lamplight on a wooden desk",
    "Porch swing and summer cicada dusk",
    "College pennants and radiator pipes",
    "Cigarette smoke curling in quiet rooms"
  ]
}



Existing character continuity:
- Nick Carraway: Slim, clean-cut Midwesterner with neatly side-parted brown hair and observant eyes Costume: White shirt with rolled sleeves, loosened tie, waistcoat; casual cap outdoors Continuity: Remain in 1922 flashback: walking the West Egg road to his bungalow, then at his porch and shoreline; keep sepia-warm palette for memory.
- Mr. Carraway (Nick’s Father): Tall Midwestern gentleman with tidy mustache and steady gaze Costume: Dark waistcoat, crisp white shirt, understated tie; light summer jacket on the porch Continuity: Appears briefly in flashback as a measured, composed presence.
- Office Young Man: Fresh-faced clerk in his twenties, slick hair, eager posture Costume: City office wear: shirtsleeves with suspenders, tie slightly loose Continuity: Appears only in New York office flashback to propose the commuting house.
- Finnish Woman (Housekeeper): Sturdy, middle-aged woman with a kerchief over her hair and lined, practical face Costume: Simple housedress and apron Continuity: Always near the small kitchen’s electric stove, occupied with breakfast tasks.
- Roadside Man: Nervous newcomer with hat slightly askew, uncertain stance Costume: City suit a bit rumpled from travel Continuity: Meets Nick on the country road near West Egg.


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