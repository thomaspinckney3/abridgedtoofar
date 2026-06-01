You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 1 of 4
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

[1] words 1-23
In my younger and more vulnerable years my father gave me some advice that I've been turning over in my mind ever since.


[2] words 24-48
"Whenever you feel like criticizing anyone," he told me, "just remember that all the people in this world haven't had the advantages that you've had."


[3] words 49-75
He didn't say any more, but we've always been unusually communicative in a reserved way, and I understood that he meant a great deal more than that.


[4] words 76-106
In consequence, I'm inclined to reserve all judgements, a habit that has opened up many curious natures to me and also made me the victim of not a few veteran bores.


[5] words 107-154
The abnormal mind is quick to detect and attach itself to this quality when it appears in a normal person, and so it came about that in college I was unjustly accused of being a politician, because I was privy to the secret griefs of wild, unknown men.


[6] words 155-210
Most of the confidences were unsought—frequently I have feigned sleep, preoccupation, or a hostile levity when I realized by some unmistakable sign that an intimate revelation was quivering on the horizon; for the intimate revelations of young men, or at least the terms in which they express them, are usually plagiaristic and marred by obvious suppressions.


[7] words 211-218
Reserving judgements is a matter of infinite hope.


[8] words 219-252
I am still a little afraid of missing something if I forget that, as my father snobbishly suggested, and I snobbishly repeat, a sense of the fundamental decencies is parcelled out unequally at birth.


[9] words 253-270
And, after boasting this way of my tolerance, I come to the admission that it has a limit.


[10] words 271-294
Conduct may be founded on the hard rock or the wet marshes, but after a certain point I don't care what it's founded on.


[11] words 295-335
When I came back from the East last autumn I felt that I wanted the world to be in uniform and at a sort of moral attention forever; I wanted no more riotous excursions with privileged glimpses into the human heart.



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