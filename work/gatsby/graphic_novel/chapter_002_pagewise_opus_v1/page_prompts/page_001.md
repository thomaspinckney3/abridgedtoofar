You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 1 of 7
Target panels for this page: 4

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

[1] words 4762-4798
About halfway between West Egg and New York the motor road hastily joins the railroad and runs beside it for a quarter of a mile, so as to shrink away from a certain desolate area of land.


[2] words 4799-4849
This is a valley of ashes—a fantastic farm where ashes grow like wheat into ridges and hills and grotesque gardens; where ashes take the forms of houses and chimneys and rising smoke and, finally, with a transcendent effort, of ash-grey men, who move dimly and already crumbling through the powdery air.


[3] words 4850-4893
Occasionally a line of grey cars crawls along an invisible track, gives out a ghastly creak, and comes to rest, and immediately the ash-grey men swarm up with leaden spades and stir up an impenetrable cloud, which screens their obscure operations from your sight.


[4] words 4894-4919
But above the grey land and the spasms of bleak dust which drift endlessly over it, you perceive, after a moment, the eyes of Doctor T.


[5] words 4920-4920
J.


[6] words 4921-4921
Eckleburg.


[7] words 4922-4926
The eyes of Doctor T.


[8] words 4927-4927
J.


[9] words 4928-4937
Eckleburg are blue and gigantic—their retinas are one yard high.


[10] words 4938-4958
They look out of no face, but, instead, from a pair of enormous yellow spectacles which pass over a nonexistent nose.


[11] words 4959-4991
Evidently some wild wag of an oculist set them there to fatten his practice in the borough of Queens, and then sank down himself into eternal blindness, or forgot them and moved away.


[12] words 4992-5012
But his eyes, dimmed a little by many paintless days, under sun and rain, brood on over the solemn dumping ground.


[13] words 5013-5054
The valley of ashes is bounded on one side by a small foul river, and, when the drawbridge is up to let barges through, the passengers on waiting trains can stare at the dismal scene for as long as half an hour.


[14] words 5055-5078
There is always a halt there of at least a minute, and it was because of this that I first met Tom Buchanan's mistress.


[15] words 5079-5091
The fact that he had one was insisted upon wherever he was known.


[16] words 5092-5107
Though I was curious to see her, I had no desire to meet her—but I did.


[17] words 5108-5144
I went up to New York with Tom on the train one afternoon, and when we stopped by the ash-heaps he jumped to his feet and, taking hold of my elbow, literally forced me from the car.


[18] words 5145-5149
"We're getting off," he insisted.


[19] words 5150-5156
"I want you to meet my girl."


[20] words 5157-5176
I think he'd tanked up a good deal at luncheon, and his determination to have my company bordered on violence.



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