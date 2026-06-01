You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 2 of 5
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
    8
  ],
  "last_scene": "College dormitory at night (flashback)",
  "active_characters": [
    "Nick Carraway"
  ],
  "character_updates": [
    "Established Nick’s present-day writing frame and his father’s formative advice.",
    "Shown Nick’s college experiences with unsolicited confidences and his habit of feigning sleep."
  ],
  "visual_motifs": [
    "Fountain pen and notebook",
    "Warm desk-lamp light",
    "Porch swing at dusk",
    "College pennants and dorm shadows"
  ],
  "next_page_needs": [
    "Return to the present writing desk to re-anchor time after the flashback.",
    "Continue the narrator’s reflective thread, building from hope and unequal decencies toward his limits and the setting to come."
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
- Nick Carraway: Slim, clean-cut young man in his mid-20s; neat side-parted brown hair; thoughtful, observant eyes Costume: Present: white shirt with rolled sleeves, loosened tie, waistcoat; Flashbacks: as a teen in a simple collared shirt and sweater; College: casual tweed jacket and tie Continuity: Keep Nick’s hair part, lean build, and composed posture consistent across ages; age him down subtly in flashbacks (softer jawline, slightly shorter).
- Mr. Carraway (Nick’s Father): Tall Midwestern gentleman in his 40s-50s; strong nose, tidy mustache, calm, steady gaze Costume: Dark waistcoat, crisp white shirt, understated tie; summer jacket on the porch Continuity: Always composed and economical in gesture; conveys meaning with minimal words and a steady look.


Source units for this page:

[9] words 253-270
And, after boasting this way of my tolerance, I come to the admission that it has a limit.


[10] words 271-294
Conduct may be founded on the hard rock or the wet marshes, but after a certain point I don't care what it's founded on.


[11] words 295-335
When I came back from the East last autumn I felt that I wanted the world to be in uniform and at a sort of moral attention forever; I wanted no more riotous excursions with privileged glimpses into the human heart.


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