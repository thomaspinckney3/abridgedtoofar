You are creating an intermediate graphic-novel plot version from an abridged novel excerpt.

This is NOT a page storyboard and NOT image prompts. It is the planning layer
between abridged prose and storyboard generation.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Excerpt word range: 1-1238
Downstream target pages: 5
Downstream target panels per page: 5

Goal:
- Preserve narrative function, chronology, character relationships, and distinctive voice.
- Do not preserve every sentence as a panel.
- Do not preserve every source unit as caption text. A graphic novel should move
  faster than the abridged prose.
- Make the plot readable as comics by identifying concrete actions, time frames,
  physical anchors, and what can be compressed, implied, or omitted.
- Account for every source unit explicitly so omissions are intentional.

Disposition labels:
- keep_as_panel: source unit deserves direct visual staging.
- keep_as_caption: source wording or voice should remain, but it can ride over another action.
- merge_into_adjacent_beat: source unit is needed, but only as part of a larger beat.
- imply_visually: source unit should be communicated mostly through staging/design.
- omit: source unit can be dropped for graphic-novel pacing.

Rules:
- Preserve source order.
- Every source unit must appear exactly once in `unit_treatments`.
- Every source unit not marked `omit` must appear in exactly one `graphic_beats[].source_unit_ids`.
- `graphic_beats` must be in source order.
- Prefer fewer, stronger graphic beats over one beat per sentence.
- Use `omit` for low-value texture, repetitive reflection, or detail that would
  slow the graphic novel without changing plot, character, orientation, or
  distinctive voice.
- Do not keep a source unit only because the prose is attractive. Keep it only
  if it serves the graphic adaptation.
- Keep Gatsby-like narrator-frame material distinct from story-present chronology.
- For each beat, state the physical action first. Abstract meaning comes second.
- For geography, the physical action spine should be a character moving through
  or looking at a place. A map may be supporting storyboard guidance, but it
  should not be the main action spine unless no character vantage exists.
- Never use a map, diagram, label, signpost, aerial view, or other exposition
  device as the `physical_action_spine` when a character can physically look,
  walk, arrive, enter, leave, point, ride, write, read, or otherwise act.
- If a map would help the eventual page, mention it only as optional support in
  `storyboard_guidance`; keep the main beat grounded in character action.
- Inanimate objects can never drive the plot. A train, map, house, book, sun,
  camera move, label, weather effect, or landscape may be a prop, setting, or
  visual support, but never the actor of the beat.
- Every graphic beat must have a living character or role-identifiable person
  as `driver_character`. For reflective passages, the driver is usually Nick as
  narrator: writing, remembering, looking, walking, arriving, deciding, reading,
  or explaining.
- `physical_action_spine` must begin from what that character does or
  experiences, not what an object or camera does.
- A montage is not a plot driver. If a montage is useful, the action spine must
  still begin with the character's action or experience; put montage details in
  `storyboard_guidance`.
- Likewise, vignettes, insets, timelines, transitions, and sequences are layout
  methods, not plot drivers.
- If a source unit is omitted, give a concrete reason such as `repetitive_reflection`,
  `rhetorical_texture`, `already_implied`, `low_plot_value`, or `pace_cost_too_high`.
- If exact source wording should survive, put it in `caption_candidates`. Be
  selective; do not include a caption candidate for every non-omitted source unit.
- Do not invent plot events, new relationships, or unearned explanations.
- Do not decide page layouts here. Give storyboard guidance, not panels.

Source units:

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



Return strict JSON only:

{
  "title": string,
  "adaptation_scope": string,
  "pacing_strategy": {
    "summary": string,
    "target_reader_experience": string,
    "compression_ratio": "light" | "moderate" | "aggressive",
    "main_risks": [string]
  },
  "time_frames": [
    {
      "id": string,
      "label": string,
      "chronological_position": string,
      "reader_cue": string,
      "visual_cue": string
    }
  ],
  "unit_treatments": [
    {
      "source_unit_id": number,
      "disposition": "keep_as_panel" | "keep_as_caption" | "merge_into_adjacent_beat" | "imply_visually" | "omit",
      "time_frame": string,
      "subject": string,
      "narrative_function": string,
      "preservation_reason": string,
      "omit_or_compress_reason": string
    }
  ],
  "graphic_beats": [
    {
      "beat_id": string,
      "source_unit_ids": [number],
      "time_frame": string,
      "subject": string,
      "driver_character": string,
      "character_goal_or_state_change": string,
      "physical_action_spine": string,
      "narrative_function": string,
      "essential_facts": [string],
      "character_relationships": [string],
      "setting_or_orientation": string,
      "caption_candidates": [string],
      "visual_anchor": string,
      "compression_guidance": string,
      "storyboard_guidance": string,
      "pacing_priority": "high" | "medium" | "low"
    }
  ],
  "omitted_units": [
    {
      "source_unit_id": number,
      "reason": string,
      "safe_because": string
    }
  ],
  "continuity_requirements": [
    {
      "type": "character" | "place" | "time_frame" | "object" | "theme",
      "name": string,
      "requirement": string
    }
  ],
  "storyboard_instructions": [string]
}