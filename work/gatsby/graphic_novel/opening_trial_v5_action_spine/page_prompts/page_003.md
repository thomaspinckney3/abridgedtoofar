You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 3 of 5
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
    16
  ],
  "last_scene": "Nick’s Midwestern study at night (present), with a brief flashback to a train platform last autumn",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "Nick re-anchors in the present at his writing desk and admits his tolerance has limits.",
    "He recalls returning from the East last autumn, resolved against further riotous excursions.",
    "He singles out Gatsby as the exception and praises Gatsby’s extraordinary hope.",
    "He notes that what preyed on Gatsby soured his interest in others’ fleeting sorrows and joys.",
    "He situates himself within a prominent Middle Western family."
  ],
  "visual_motifs": [
    "Fountain pen and open notebook",
    "Pool of lamplight on a wooden desk",
    "Cigarette smoke curling in quiet rooms",
    "Sepia-tinged train platform memory",
    "Dust motes in lamplight",
    "Framed family portrait"
  ],
  "next_page_needs": [
    "Continue into Nick’s Middle Western background and upbringing.",
    "Transition to his decision to go East and the bond business.",
    "Begin orienting the geography that will lead to West Egg and the rental house."
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s America with brief flashbacks to Midwestern 1900s-1910s and college years",
  "line_and_color": "Clean, expressive linework with restrained, naturalistic color; present-day scenes in neutral tones, flashbacks with a soft sepia wash",
  "lighting": "Present: warm desk-lamp pools of light against evening shadows; Flashbacks: late-afternoon Midwestern glow and muted dorm/common-room gaslight",
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
- Nick Carraway: Slim, clean-cut young man in his mid-20s; neat side-parted brown hair; thoughtful, observant eyes Costume: Present: white shirt with rolled sleeves, loosened tie, waistcoat; Flashbacks: casual travel coat over a vest and tie, carrying a worn suitcase Continuity: Keep Nick at his writing desk in the present with warm lamplight and neutral tones; flashback in sepia. Maintain his lean build, side-parted hair, and restrained demeanor.
- Mr. Carraway (Nick’s Father): Tall Midwestern gentleman in his 40s-50s; strong nose, tidy mustache, calm, steady gaze Costume: Dark waistcoat, crisp white shirt, understated tie; summer jacket on the porch Continuity: Always composed and economical in gesture; conveys meaning with minimal words and a steady look.


Source units for this page:

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