You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 4 of 5
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


[35] words 973-999
It was on that slender riotous island which extends itself due east of New York—and where there are, among other natural curiosities, two unusual formations of land.


[36] words 1000-1041
Twenty miles from the city a pair of enormous eggs, identical in contour and separated only by a courtesy bay, jut out into the most domesticated body of salt water in the Western hemisphere, the great wet barnyard of Long Island Sound.



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