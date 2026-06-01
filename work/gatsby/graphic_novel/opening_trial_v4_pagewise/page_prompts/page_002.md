You are drafting one page of a graphic novel adaptation from a published abridgment.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Page: 2 of 4
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
    11
  ],
  "last_scene": "Nick’s reflective narration from youthful advice through college confidences to his return from the East in autumn, embracing a stricter moral posture.",
  "active_characters": [
    "Nick Carraway",
    "Nick's Father"
  ],
  "character_updates": [
    "Nick’s philosophy of reserving judgment established and contextualized by his father’s advice.",
    "Nick shown as a confidant in college, often unwillingly.",
    "Nick admits limits to his tolerance and, post-East, desires moral order."
  ],
  "visual_motifs": [
    "porch railings and orderly lines",
    "train platforms/suitcase",
    "autumn leaves",
    "windows/thresholds"
  ],
  "next_page_needs": [
    "Continue from Nick’s post-East resolve into the next chronological setting and characters he introduces.",
    "Maintain narrator’s introspective captions while staging clear environments for upcoming scenes.",
    "Begin establishing the East/West contrast visually if the next units move toward Long Island or New York."
  ]
}


Existing style bible:
{
  "visual_period": "Early 1920s America with flashbacks to the 1910s Midwest",
  "line_and_color": "Clean ink lines with selective hatching; muted, slightly desaturated palette with warm sepias for memory and cooler neutrals for present reflections",
  "lighting": "Naturalistic, time-of-day motivated; warm late-afternoon glow for the porch memory, dormroom lamplight for college, crisp autumn daylight for the return home",
  "lettering": "Classic serif narrative captions; dialogue in understated, readable roman; generous negative space for dense narration",
  "recurring_motifs": [
    "porch railings and straight lines (order/reserve)",
    "train platforms and suitcases (transit between East/West)",
    "autumn leaves (afterglow/aftermath)",
    "windows and thresholds (observation vs participation)"
  ]
}



Existing character continuity:
- Nick Carraway: Lean, observant young man in his late 20s; tidy hair parted to the side; watchful eyes; composed posture Costume: Conservative 1920s civilian dress: dark three-piece suit, white shirt, slim tie; in flashback, simpler Midwestern shirtwaist and vest Continuity: Narrator and point-of-view; frequently framed slightly apart from others, looking on rather than performing
- Nick's Father: Middle-aged gentleman with neatly trimmed mustache; calm, steady gaze; composed demeanor Costume: Early 1910s Midwestern attire: shirt, vest, rolled sleeves on a porch; pocket watch chain visible Continuity: Appears only in memory; presence sets Nick’s moral framework


Source units for this page:

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