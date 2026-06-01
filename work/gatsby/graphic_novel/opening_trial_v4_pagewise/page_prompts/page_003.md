You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 3 of 4
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
    21
  ],
  "last_scene": "In a 1920s office, Nick warms to a colleague’s suggestion to share a house in a commuting town after arriving in the East in spring 1922.",
  "active_characters": [
    "Nick Carraway",
    "Young Man at the Office"
  ],
  "character_updates": [
    "Gatsby established as Nick’s singular exception, defined by rare hope and sensitivity; hinted doom from forces around him.",
    "Nick’s Midwestern roots, Yale ’15 graduate, and WWI service summarized.",
    "Restlessness after the war drives Nick to choose the East and the bond business.",
    "Father finances a year; Nick arrives in spring 1922.",
    "Nick considers sharing a house in a commuting town due to the warm season and affinity for lawns and trees."
  ],
  "visual_motifs": [
    "train platforms and suitcases",
    "windows and thresholds",
    "orderly Midwestern architecture and railings",
    "spring foliage signaling new beginning"
  ],
  "next_page_needs": [
    "Show the commuting town environment and the rented house setting as Nick settles in.",
    "Continue Nick’s narrative captions to introduce the local geography and neighbors.",
    "Begin visual contrast between the quieter commuting town and the glittering East to come, while keeping chronology clear."
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s America with flashbacks to the 1910s Midwest",
  "line_and_color": "Clean ink lines with selective hatching; muted, slightly desaturated palette with warm sepias for memory and cooler neutrals for present reflections",
  "lighting": "Cool, interior daylight for present reflections; warm, sunlit sepia for Midwestern memory; desaturated overcast for wartime recollection; bright, crisp spring light for the move East; soft office daylight for the housing suggestion",
  "lettering": "Classic serif narrative captions; dialogue in understated, readable roman; generous negative space for dense narration",
  "recurring_motifs": [
    "porch railings and straight lines (order/reserve)",
    "train platforms and suitcases (transit between East/West)",
    "seasonal foliage: autumn in reflection, spring blossoms for new start",
    "windows and thresholds (observation vs participation)"
  ]
}



Existing character continuity:
- Nick Carraway: Lean, observant young man with tidy side-parted hair and watchful eyes Costume: Conservative dark three-piece suit, white shirt, slim tie; in flashbacks: simpler Midwestern shirtwaist and vest; for travel: hat and overcoat with suitcase Continuity: Narrator and point-of-view; often framed slightly apart, observing rather than acting
- Nick's Father: Middle-aged gentleman with neatly trimmed mustache and steady gaze Costume: Early 1910s–1920s Midwestern attire: shirt, vest, jacket; pocket watch chain visible Continuity: Appears in memories and moments of guidance/support; presence signals Nick’s moral frame and practical support
- Jay Gatsby (glimpsed): Elegant male silhouette, back turned or softly out of focus, suggesting poise without revealing features Costume: Immaculate suit suggested by clean lines and tailored silhouette Continuity: Introduced as an idea through Nick’s reflection; avoid concrete identifiers until formally met in-story
- Young Man at the Office: Clean-cut clerk in shirtsleeves and tie, energetic posture Costume: 1920s office wear: white shirt, suspenders, narrow tie, sleeve garters Continuity: Colleague who proposes sharing a house in a commuting town


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