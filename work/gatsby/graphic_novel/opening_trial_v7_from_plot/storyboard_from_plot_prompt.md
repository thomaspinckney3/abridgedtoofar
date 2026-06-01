You are creating a graphic novel storyboard from an intermediate graphic plot
treatment. The treatment has already decided what source material is preserved,
compressed, implied, or omitted.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Requested pages: 5
Target panels per page: 5

Hard rules:
- Use the plot treatment as the source of truth.
- Preserve graphic beat order exactly.
- Cover every graphic beat at least once.
- Do not include omitted source units.
- A panel may cover one beat or adjacent beats only.
- Inanimate objects can never drive the plot. Every panel action must be driven
  by a living character or role-identifiable person, usually Nick.
- Maps, diagrams, signs, labels, camera moves, montages, vignettes, timelines,
  trains, buildings, weather, books, windows, and landscapes are supports only.
  They cannot be the panel's action.
- If geography must be explained, stage it through a character looking,
  walking, pointing, arriving, entering, leaving, writing, reading, or speaking.
- Captions and dialogue are post-lettering text, not part of the image prompt.
- Image prompts must be for clean art only: no readable text, no captions,
  no labels, no signs, no maps with text, no speech balloons, no lettering.
- Use exact source wording from `caption_candidates` when it is useful, but keep
  captions short enough for comics pacing.
- Do not invent speeches. Dialogue should come only from caption candidates or
  obvious quoted source lines.
- If a beat is reflective, stage Nick physically writing, remembering, looking,
  walking, or deciding.

Graphic plot treatment:
{
  "title": "Gatsby Begins: Nick Arrives and Points East",
  "adaptation_scope": "Opening narration through Nick’s move to West Egg, early summer settling-in, and spatial orientation culminating in the reveal of Gatsby’s mansion.",
  "pacing_strategy": {
    "summary": "Anchor the reflective voice to clear, physical moments of Nick acting: writing, remembering, deciding, moving, looking. Compress aphorisms into select captions riding over visualized actions. Stage geography through Nick’s vantage rather than diagrams.",
    "target_reader_experience": "Feel Nick’s cautious, witty voice while swiftly arriving in West Egg, sensing summer’s restart, and seeing the Eggs and Gatsby’s mansion without bogging down in exposition.",
    "compression_ratio": "moderate",
    "main_risks": [
      "Over-weighting narration and slowing early pages",
      "Blurring narrator-frame (after the events) with story-present (spring–summer 1922)",
      "Letting geographic exposition stall action",
      "Diluting the distinctiveness of Nick’s aphorisms if over-trimmed"
    ]
  },
  "time_frames": [
    {
      "id": "TF1",
      "label": "Narrator Retrospective (after the East)",
      "chronological_position": "Post-1922 return; Nick writing/reflecting after the novel’s main events",
      "reader_cue": "Past-tense reflections, moral framing, references to having ‘come back from the East’",
      "visual_cue": "Nick at a desk or window with notebook and lamplight; quieter palette"
    },
    {
      "id": "TF2",
      "label": "Midwest Background to Departure",
      "chronological_position": "Pre-1922: family background, Yale (1915), Great War, decision to go East",
      "reader_cue": "Concise backstory beats moving toward spring of ’22",
      "visual_cue": "Sepia or cooler tones; family portrait, Yale cap, trench flashes, a ticket to New York"
    },
    {
      "id": "TF3",
      "label": "Spring–Early Summer 1922: Settling in West Egg",
      "chronological_position": "Nick’s first weeks in West Egg, early summer mood",
      "reader_cue": "Present-tense of place; neighbors, errands, sunshine, self-improvement kick",
      "visual_cue": "Warm greens and golds; roadside exchange; red-and-gold finance books"
    },
    {
      "id": "TF4",
      "label": "Orientation: The Two Eggs and Neighbors",
      "chronological_position": "Still spring–summer 1922; Nick physically situates home, bay, and mansions",
      "reader_cue": "Pointing out shorelines, ‘West Egg’ vs ‘East Egg’, and Gatsby’s mansion",
      "visual_cue": "Nick on shoreline or porch sightlines across the Sound; dusk light for contrast"
    }
  ],
  "unit_treatments": [
    {
      "source_unit_id": 1,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Nick recalls father’s formative advice",
      "narrative_function": "Establish narrator’s ethos and reflective frame",
      "preservation_reason": "Iconic opening line and voice-launch",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 2,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Father’s caution against criticism",
      "narrative_function": "Theme seed: tolerance/judgment",
      "preservation_reason": "Key principle shaping Nick’s stance",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 3,
      "disposition": "merge_into_adjacent_beat",
      "time_frame": "TF1",
      "subject": "Unspoken depth in father-son exchange",
      "narrative_function": "Deepen the advice without new plot",
      "preservation_reason": "Adds nuance to Beat 1",
      "omit_or_compress_reason": "Combine to avoid over-captioning"
    },
    {
      "source_unit_id": 4,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Nick reserves judgments; attracts confidences and bores",
      "narrative_function": "Character trait with social effect",
      "preservation_reason": "Sets up why people confide in him",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 5,
      "disposition": "imply_visually",
      "time_frame": "TF1",
      "subject": "College accusations; privy to secret griefs",
      "narrative_function": "Show consequences of Nick’s reserve",
      "preservation_reason": "Supports montage of confidences",
      "omit_or_compress_reason": "Visual implication avoids dense exposition"
    },
    {
      "source_unit_id": 6,
      "disposition": "imply_visually",
      "time_frame": "TF1",
      "subject": "Feigning sleep; plagiaristic revelations",
      "narrative_function": "Tone and texture of confidences",
      "preservation_reason": "Reinforces Beat 2 montage",
      "omit_or_compress_reason": "Best shown in quick vignettes"
    },
    {
      "source_unit_id": 7,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "‘Reserving judgements is a matter of infinite hope’",
      "narrative_function": "Memorable aphorism; theme",
      "preservation_reason": "Signature line worth preserving verbatim",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 8,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Unequal parceling of fundamental decencies",
      "narrative_function": "Nuances Nick’s tolerance",
      "preservation_reason": "Distinctive voice; worldview complexity",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 9,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Admitted limit to tolerance",
      "narrative_function": "Foreshadowing boundary",
      "preservation_reason": "Preps turn toward Gatsby exception",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 10,
      "disposition": "merge_into_adjacent_beat",
      "time_frame": "TF1",
      "subject": "Conduct on rock or marshes; don’t care after a point",
      "narrative_function": "Reinforce limit to tolerance",
      "preservation_reason": "Supports 9 without new action",
      "omit_or_compress_reason": "Merge to keep pace"
    },
    {
      "source_unit_id": 11,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "After coming back from the East, desire for moral uniformity",
      "narrative_function": "Anchor when/why Nick is narrating",
      "preservation_reason": "Frames story as aftermath of disillusion",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 12,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Gatsby alone exempt from Nick’s reaction",
      "narrative_function": "Title character hook",
      "preservation_reason": "Signals Gatsby’s special status",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 13,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "‘Something gorgeous’: heightened sensitivity metaphor",
      "narrative_function": "Define Gatsby’s allure",
      "preservation_reason": "Signature descriptive image",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 14,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Extraordinary gift for hope; romantic readiness",
      "narrative_function": "Theme core of Gatsby",
      "preservation_reason": "Essential characterization",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 15,
      "disposition": "keep_as_caption",
      "time_frame": "TF1",
      "subject": "Gatsby turned out all right; foul dust in his wake",
      "narrative_function": "Mystery/foreboding; foreshadow fallout",
      "preservation_reason": "Sets stakes and tone",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 16,
      "disposition": "keep_as_caption",
      "time_frame": "TF2",
      "subject": "Prominent Middle Western family",
      "narrative_function": "Place Nick’s class/background",
      "preservation_reason": "Orient social position",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 17,
      "disposition": "keep_as_caption",
      "time_frame": "TF2",
      "subject": "Yale ‘15; Great War service",
      "narrative_function": "Timeline and maturity",
      "preservation_reason": "Concise life markers",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 18,
      "disposition": "keep_as_caption",
      "time_frame": "TF2",
      "subject": "Enjoyed counter-raid; returned restless",
      "narrative_function": "Motivation to leave Midwest",
      "preservation_reason": "Explains eastward push",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 19,
      "disposition": "keep_as_panel",
      "time_frame": "TF2",
      "subject": "Middle West feels like ragged edge; decide to learn bonds in East",
      "narrative_function": "Decision point and move",
      "preservation_reason": "Actionable pivot to plot",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 20,
      "disposition": "keep_as_caption",
      "time_frame": "TF2",
      "subject": "Father bankrolls year; arrives in spring ’22",
      "narrative_function": "Means/time stamp for relocation",
      "preservation_reason": "Precise timing needed",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 21,
      "disposition": "keep_as_panel",
      "time_frame": "TF3",
      "subject": "Office friend proposes sharing a commuting house",
      "narrative_function": "Set-up for West Egg lodging",
      "preservation_reason": "Concrete action toward setting",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 22,
      "disposition": "keep_as_panel",
      "time_frame": "TF3",
      "subject": "Friend finds $80 bungalow; gets sent to Washington; Nick goes alone",
      "narrative_function": "Places Nick solo in the bungalow",
      "preservation_reason": "Explains Nick’s solitary arrival",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 23,
      "disposition": "imply_visually",
      "time_frame": "TF3",
      "subject": "Dog (briefly), old Dodge, Finnish housekeeper",
      "narrative_function": "Texture of Nick’s domestic setup",
      "preservation_reason": "Quick visual character/setting cues",
      "omit_or_compress_reason": "No need for full caption; show instead"
    },
    {
      "source_unit_id": 24,
      "disposition": "keep_as_panel",
      "time_frame": "TF3",
      "subject": "A newer arrival stops Nick on the road",
      "narrative_function": "Inciting moment of belonging",
      "preservation_reason": "Action that flips Nick’s loneliness",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 25,
      "disposition": "keep_as_panel",
      "time_frame": "TF3",
      "subject": "‘How do you get to West Egg village?’",
      "narrative_function": "Dialog establishing locale",
      "preservation_reason": "Natural speech; anchors place name",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 26,
      "disposition": "merge_into_adjacent_beat",
      "time_frame": "TF3",
      "subject": "Nick gives directions",
      "narrative_function": "Completes micro-interaction",
      "preservation_reason": "Folds into Beat 8 action flow",
      "omit_or_compress_reason": "Avoid redundant panel"
    },
    {
      "source_unit_id": 27,
      "disposition": "keep_as_caption",
      "time_frame": "TF3",
      "subject": "Lonely no longer",
      "narrative_function": "State change from isolation to belonging",
      "preservation_reason": "Concise inner turn",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 28,
      "disposition": "keep_as_caption",
      "time_frame": "TF3",
      "subject": "Guide, pathfinder, original settler",
      "narrative_function": "Elevated self-mockery; tone",
      "preservation_reason": "Distinctive flourish; brief",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 29,
      "disposition": "keep_as_caption",
      "time_frame": "TF3",
      "subject": "Freedom of the neighbourhood conferred",
      "narrative_function": "Lock-in sense of acceptance",
      "preservation_reason": "Completes the belonging beat",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 30,
      "disposition": "keep_as_caption",
      "time_frame": "TF3",
      "subject": "Summer makes life feel new again",
      "narrative_function": "Seasonal mood and momentum",
      "preservation_reason": "Key seasonal thesis; energizes pacing",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 31,
      "disposition": "omit",
      "time_frame": "TF3",
      "subject": "So much to read; so much health in the air",
      "narrative_function": "Ambient enthusiasm",
      "preservation_reason": "",
      "omit_or_compress_reason": "already_implied by 30 and 32; pace_cost_too_high"
    },
    {
      "source_unit_id": 32,
      "disposition": "keep_as_panel",
      "time_frame": "TF3",
      "subject": "Buys red-and-gold banking books promising secret riches",
      "narrative_function": "Shows self-improvement and money-world focus",
      "preservation_reason": "Strong, visual metaphor (‘new money’)",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 33,
      "disposition": "keep_as_caption",
      "time_frame": "TF3",
      "subject": "Literary past, aim to be ‘well-rounded’; single-window aphorism",
      "narrative_function": "Intellectual self-portrait and credo",
      "preservation_reason": "Reveals Nick’s stance and limits",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 34,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "By chance in a very strange community",
      "narrative_function": "Transition to local geography",
      "preservation_reason": "Sets up the Eggs exposition",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 35,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "Island east of New York with unusual formations",
      "narrative_function": "Macro orientation",
      "preservation_reason": "Needed context for Eggs contrast",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 36,
      "disposition": "imply_visually",
      "time_frame": "TF4",
      "subject": "Two enormous eggs jutting into Long Island Sound",
      "narrative_function": "Spatial comprehension",
      "preservation_reason": "Better shown than told via Nick’s vantage",
      "omit_or_compress_reason": "Avoid expository drag; keep visual"
    },
    {
      "source_unit_id": 37,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "Identical in shape, different in all else",
      "narrative_function": "Theme of superficial likeness vs real difference",
      "preservation_reason": "Sharp contrast line; brief",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 38,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "Nick in West Egg, the less fashionable one",
      "narrative_function": "Place Nick socially/geographically",
      "preservation_reason": "Orientation required",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 39,
      "disposition": "keep_as_panel",
      "time_frame": "TF4",
      "subject": "Nick’s small house at the tip, squeezed between huge places",
      "narrative_function": "Establish exact home position and contrast",
      "preservation_reason": "Concrete staging for later scenes",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 40,
      "disposition": "keep_as_panel",
      "time_frame": "TF4",
      "subject": "Colossal Norman Hôtel de Ville imitation with tower, pool, vast lawns",
      "narrative_function": "Set Gatsby’s neighbor-mansion grandeur",
      "preservation_reason": "Signature visual; prepares reveal",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 41,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "It was Gatsby’s mansion",
      "narrative_function": "Reveal and hook",
      "preservation_reason": "Essential payoff to description",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 42,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "Nick didn’t yet know Mr. Gatsby",
      "narrative_function": "Preserve initial ignorance",
      "preservation_reason": "Protects chronology and mystery",
      "omit_or_compress_reason": ""
    },
    {
      "source_unit_id": 43,
      "disposition": "keep_as_caption",
      "time_frame": "TF4",
      "subject": "Nick’s eyesore cottage with fine views and millionaire neighbors for $80",
      "narrative_function": "Finalize home scale and perks",
      "preservation_reason": "Economics/irony in one neat detail",
      "omit_or_compress_reason": ""
    }
  ],
  "graphic_beats": [
    {
      "beat_id": "B1",
      "source_unit_ids": [
        1,
        2,
        3
      ],
      "time_frame": "TF1",
      "subject": "Nick writes and recalls his father’s advice",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Articulate his guiding ethos before the tale",
      "physical_action_spine": "Nick settles at a desk, opens a notebook, pauses as his father’s words resurface; he visualizes the scene briefly",
      "narrative_function": "Launch narrator frame; set tolerance theme",
      "essential_facts": [
        "Nick’s father warned against easy criticism",
        "Nick has pondered this advice for years"
      ],
      "character_relationships": [
        "Nick respects his father’s moral counsel"
      ],
      "setting_or_orientation": "Quiet Midwestern study, later timeframe",
      "caption_candidates": [
        "In my younger and more vulnerable years my father gave me some advice that I've been turning over in my mind ever since.",
        "Whenever you feel like criticizing anyone, just remember that all the people in this world haven't had the advantages that you've had."
      ],
      "visual_anchor": "Nick’s hand over a blank page; ghosted memory of father’s face behind him",
      "compression_guidance": "Let unit 3’s ‘he meant more’ ride as subtext in Nick’s expression rather than additional text.",
      "storyboard_guidance": "Warm lamplight; over-the-shoulder notebook view; father appears in a soft-edged memory panel nested within the scene.",
      "pacing_priority": "high"
    },
    {
      "beat_id": "B2",
      "source_unit_ids": [
        4,
        5,
        6,
        7,
        8
      ],
      "time_frame": "TF1",
      "subject": "Nick’s habit of reserving judgment and its social effects",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Explain why people confide in him—and his wary tolerance",
      "physical_action_spine": "Nick, younger, endures late-night confessions in a dorm/train club car; he feigns sleep to dodge another",
      "narrative_function": "Show trait-in-action; texture without stalling",
      "essential_facts": [
        "Nick reserves judgments",
        "People detect this and confide in him",
        "He’s cautious because ‘decencies’ aren’t equally given"
      ],
      "character_relationships": [
        "Nick as listener to ‘wild, unknown men’"
      ],
      "setting_orientation": "College-age and early adult milieus, transient spaces",
      "caption_candidates": [
        "I'm inclined to reserve all judgements...",
        "Reserving judgements is a matter of infinite hope.",
        "...a sense of the fundamental decencies is parcelled out unequally at birth."
      ],
      "visual_anchor": "Nick half-lit on a bunk/seat as a roommate leans in to confide; Nick’s eyes closed to avoid it",
      "compression_guidance": "Run 4/7/8 as brief captions over two small vignettes showing 5/6 silently.",
      "storyboard_guidance": "Montage feel: two or three thin, horizontal insets of confidences. Keep text minimal and aphoristic.",
      "pacing_priority": "medium"
    },
    {
      "beat_id": "B3",
      "source_unit_ids": [
        9,
        10,
        11
      ],
      "time_frame": "TF1",
      "subject": "Nick’s limit to tolerance after returning from the East",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Set the mood of post-East austerity",
      "physical_action_spine": "Nick returns home with a suitcase, pointedly declines a lively invitation, and closes his door",
      "narrative_function": "Frame disillusionment; set the ‘after’ stance",
      "essential_facts": [
        "His tolerance has limits",
        "After coming back from the East he wanted moral ‘uniform’"
      ],
      "character_relationships": [
        "Nick vs. society’s ‘riotous excursions’"
      ],
      "setting_or_orientation": "Midwestern doorstep or hallway; autumn light",
      "caption_candidates": [
        "I wanted the world to be in uniform and at a sort of moral attention forever."
      ],
      "visual_anchor": "Doorknob turning as chatter and light from a party spill into the hall",
      "compression_guidance": "Fold 10 into the same caption stream as 9 to avoid redundancy.",
      "storyboard_guidance": "Cooler palette shift from B1/B2; let the ‘uniform’ idea be visualized by straightened picture frames or a tidied room.",
      "pacing_priority": "medium"
    },
    {
      "beat_id": "B4",
      "source_unit_ids": [
        12,
        13,
        14,
        15
      ],
      "time_frame": "TF1",
      "subject": "Gatsby as exception and embodiment of hope",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Name the exception that compels him to tell this story",
      "physical_action_spine": "Nick pauses at the window, looking toward distant water where a lone figure stands far off",
      "narrative_function": "Plant Gatsby’s mystique and stakes",
      "essential_facts": [
        "Only Gatsby was exempt from Nick’s scorn",
        "Gatsby had a ‘romantic readiness’ and gift for hope",
        "Something foul preyed on Gatsby’s dreams"
      ],
      "character_relationships": [
        "Nick’s reverent, puzzled regard for Gatsby"
      ],
      "setting_or_orientation": "Interior window to a suggestion of shoreline; keep it abstract",
      "caption_candidates": [
        "Only Gatsby... was exempt from my reaction—Gatsby, who represented everything for which I have an unaffected scorn.",
        "There was something gorgeous about him... an extraordinary gift for hope, a romantic readiness...",
        "No—Gatsby turned out all right at the end; it is what preyed on Gatsby... that temporarily closed out my interest..."
      ],
      "visual_anchor": "Nick’s reflection over glass; far-off solitary figure on a dock as a conceptual motif",
      "compression_guidance": "Favor the ‘gift for hope’ and ‘preyed on’ lines; keep the earthquake-machine metaphor if space allows as a single fragment.",
      "storyboard_guidance": "Do not introduce later icons explicitly; keep the distant figure generic.",
      "pacing_priority": "high"
    },
    {
      "beat_id": "B5",
      "source_unit_ids": [
        16,
        17,
        18,
        19,
        20
      ],
      "time_frame": "TF2",
      "subject": "From Midwest pedigree to decision to go East, spring ’22",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Leave the Midwest to pursue bonds in New York",
      "physical_action_spine": "Nick packs a trunk, takes a train ticket from his father, and boards eastbound",
      "narrative_function": "Deliver backstory swiftly into the main setting",
      "essential_facts": [
        "Prominent Midwestern roots",
        "Yale ‘15; war veteran; restless afterwards",
        "Decides to learn the bond business; financed by father",
        "Arrives in spring 1922"
      ],
      "character_relationships": [
        "Father supports Nick’s move"
      ],
      "setting_orientation": "Family home to station platform; early spring light",
      "caption_candidates": [
        "I came East... in the spring of twenty-two."
      ],
      "visual_anchor": "Train ticket stamped ‘New York’ and ‘1922’",
      "compression_guidance": "Convey 16–18 as two quick images (portrait/Yale cap; trench flash) then land on decisive 19–20.",
      "storyboard_guidance": "Sepia-to-color transition as the train heads East to cue timeline shift.",
      "pacing_priority": "high"
    },
    {
      "beat_id": "B6",
      "source_unit_ids": [
        21,
        22
      ],
      "time_frame": "TF3",
      "subject": "The commuting-house plan that leaves Nick solo",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Settle affordably near the city",
      "physical_action_spine": "At the office a colleague pitches sharing a house; cut to the bungalow as the colleague departs for Washington",
      "narrative_function": "Put Nick in West Egg with a reason for solitude",
      "essential_facts": [
        "Commuting house idea sounded great",
        "Friend found a cheap bungalow then got transferred",
        "Nick goes out alone"
      ],
      "character_relationships": [
        "Nick and unnamed coworker"
      ],
      "setting_or_orientation": "Bond office to weather-beaten bungalow",
      "caption_candidates": [],
      "visual_anchor": "Shabby bungalow with a hastily tacked ‘$80’ note on a rent ledger",
      "compression_guidance": "One dialog bubble for the pitch; one suitcase wave goodbye to convey transfer.",
      "storyboard_guidance": "Keep the office scene brisk; focus on the consequence shot at the bungalow.",
      "pacing_priority": "medium"
    },
    {
      "beat_id": "B7",
      "source_unit_ids": [
        23
      ],
      "time_frame": "TF3",
      "subject": "Nick’s threadbare domestic setup",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Settle into a routine",
      "physical_action_spine": "Nick parks his old Dodge as a Finnish woman fusses inside; a small dog darts off",
      "narrative_function": "Texture and modesty of Nick’s life",
      "essential_facts": [
        "Old Dodge",
        "Finnish housekeeper",
        "Dog quickly disappears"
      ],
      "character_relationships": [
        "Employer–housekeeper rapport (muted)"
      ],
      "setting_or_orientation": "Bungalow interior/exterior morning light",
      "caption_candidates": [],
      "visual_anchor": "Electric stove with the woman muttering; dog streak exiting frame",
      "compression_guidance": "No captions; let props do the work.",
      "storyboard_guidance": "Use small props to hint thrift and routine.",
      "pacing_priority": "low"
    },
    {
      "beat_id": "B8",
      "source_unit_ids": [
        24,
        25,
        26,
        27,
        28,
        29,
        30
      ],
      "time_frame": "TF3",
      "subject": "A stranger asks directions; Nick feels he belongs as summer begins",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Shift from isolation to modest belonging",
      "physical_action_spine": "On a leafy roadside, a lost man hails Nick; Nick points the way and walks on, lighter",
      "narrative_function": "Human contact transforms mood; infuse summer optimism",
      "essential_facts": [
        "A newer arrival asks the way to West Egg village",
        "Nick gives directions",
        "Nick feels ‘lonely no longer’ and like a ‘pathfinder’",
        "Summer brings a sense of new beginnings"
      ],
      "character_relationships": [
        "Nick and anonymous neighbor"
      ],
      "setting_or_orientation": "Country road near West Egg; bright morning",
      "caption_candidates": [
        "How do you get to West Egg village?",
        "And as I walked on I was lonely no longer.",
        "I was a guide, a pathfinder, an original settler.",
        "He had casually conferred on me the freedom of the neighbourhood.",
        "I had that familiar conviction that life was beginning over again with the summer."
      ],
      "visual_anchor": "Nick’s outstretched arm indicating a turn; trees bursting with new leaves",
      "compression_guidance": "Keep dialog to the single question; the rest as one or two tight captions over the walk-away image.",
      "storyboard_guidance": "Use motion lines/leaves to embody ‘fast movies’ growth without text.",
      "pacing_priority": "high"
    },
    {
      "beat_id": "B9",
      "source_unit_ids": [
        32,
        33
      ],
      "time_frame": "TF3",
      "subject": "Self-improvement kick: finance books and the ‘well-rounded man’",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Resolve to shape his mind and career",
      "physical_action_spine": "Nick unpacks gleaming red-and-gold books onto a shelf; pins an old Yale News clipping nearby",
      "narrative_function": "Show ambition and intellectual posture",
      "essential_facts": [
        "Finance books gleam like ‘new money’",
        "Nick was literary; aims to be ‘well-rounded’",
        "Belief: life is best viewed from a single window"
      ],
      "character_relationships": [],
      "setting_or_orientation": "Bungalow interior; bookcase and small desk",
      "caption_candidates": [
        "They stood on my shelf in red and gold like new money from the mint...",
        "...become again that most limited of all specialists, the 'well-rounded man.'",
        "Life is much more successfully looked at from a single window, after all."
      ],
      "visual_anchor": "Close-up of gilt spines; thumbtacked clipping titled ‘Yale News’",
      "compression_guidance": "Use two compact captions max; let the ‘new money’ simile carry the rest visually.",
      "storyboard_guidance": "Warm interior light to connect back to B1’s study but now in the 1922 present.",
      "pacing_priority": "medium"
    },
    {
      "beat_id": "B10",
      "source_unit_ids": [
        34,
        35,
        36,
        37,
        38
      ],
      "time_frame": "TF4",
      "subject": "Nick orients us to the two Eggs from his vantage",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Explain the neighborhood’s odd twin peninsulas and his place among them",
      "physical_action_spine": "Nick walks to the shore and points across the bay, comparing the two headlands",
      "narrative_function": "Geographic orientation tied to character",
      "essential_facts": [
        "The island has two unusual ‘eggs’",
        "They’re identical in shape but different in character",
        "Nick lives in West Egg, the less fashionable"
      ],
      "character_relationships": [],
      "setting_or_orientation": "Long Island Sound shoreline; both Eggs in view",
      "caption_candidates": [
        "To the wingless a more interesting phenomenon is their dissimilarity in every particular except shape and size.",
        "I lived at West Egg, the—well, the less fashionable of the two..."
      ],
      "visual_anchor": "Nick’s arm framing both curving shores; houses dotting each side with differing vibes",
      "compression_guidance": "Imply 36 visually; keep captions lean to avoid atlas-feel.",
      "storyboard_guidance": "Resist map cutaways; keep POV grounded in Nick’s line of sight.",
      "pacing_priority": "medium"
    },
    {
      "beat_id": "B11",
      "source_unit_ids": [
        39
      ],
      "time_frame": "TF4",
      "subject": "Nick’s cottage squeezed between palaces",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Place himself precisely on the Egg",
      "physical_action_spine": "Nick steps outside, glances left and right at looming neighboring estates",
      "narrative_function": "Scale contrast and exact location",
      "essential_facts": [
        "Tip of the Egg",
        "Fifty yards from the Sound",
        "Between two huge seasonal rentals"
      ],
      "character_relationships": [],
      "setting_or_orientation": "Cottage front; water glint visible beyond",
      "caption_candidates": [],
      "visual_anchor": "Tiny cottage with glimpses of sprawling lawns on both sides",
      "compression_guidance": "No added text; let architecture tell the story.",
      "storyboard_guidance": "Use a slightly elevated angle to show proximity to water and flanking estates.",
      "pacing_priority": "high"
    },
    {
      "beat_id": "B12",
      "source_unit_ids": [
        40,
        41,
        42
      ],
      "time_frame": "TF4",
      "subject": "The colossal Norman pastiche next door—Gatsby’s",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Register the neighbor’s opulence while maintaining initial ignorance of the man",
      "physical_action_spine": "Nick studies the mansion’s tower, raw ivy, and pool through the hedge",
      "narrative_function": "Introduce Gatsby’s sphere without meeting him",
      "essential_facts": [
        "Colossal, newly built Norman ‘Hôtel de Ville’ imitation",
        "Marble pool, forty-plus acres",
        "It belongs to ‘Gatsby,’ whom Nick has not met"
      ],
      "character_relationships": [
        "Nick as neighbor to Gatsby (unknown to him yet)"
      ],
      "setting_orientation": "Boundary hedge; wide view of the mansion",
      "caption_candidates": [
        "The one on my right was a colossal affair... a factual imitation of some Hôtel de Ville in Normandy...",
        "It was Gatsby's mansion.",
        "Or, rather... it was a mansion inhabited by a gentleman of that name."
      ],
      "visual_anchor": "Tower profile with thin beard of raw ivy; bright marble pool beyond lawns",
      "compression_guidance": "One sweeping exterior with a tight inset of the tower detail; three short captions maximum.",
      "storyboard_guidance": "Keep Gatsby himself unseen; emphasize newness and scale.",
      "pacing_priority": "high"
    },
    {
      "beat_id": "B13",
      "source_unit_ids": [
        43
      ],
      "time_frame": "TF4",
      "subject": "Nick’s ‘small eyesore’ with million-dollar views",
      "driver_character": "Nick Carraway",
      "character_goal_or_state_change": "Own his modest perch with ironic pride",
      "physical_action_spine": "Nick leans on his porch rail, taking in water and a slice of the neighbor’s immaculate lawn",
      "narrative_function": "Close orientation with economic irony and vantage",
      "essential_facts": [
        "House is a small eyesore, overlooked",
        "View of water and neighbor’s lawn",
        "$80 a month among millionaires"
      ],
      "character_relationships": [],
      "setting_orientation": "Porch view angled to water and next lawn",
      "caption_candidates": [
        "My own house was an eyesore, but it was a small eyesore...",
        "...and the consoling proximity of millionaires—all for eighty dollars a month."
      ],
      "visual_anchor": "Nick on the porch; horizon of the Sound; manicured green just intruding",
      "compression_guidance": "Two crisp captions; let the image deliver the joke.",
      "storyboard_guidance": "Sunset or golden-hour warmth to segue into future social scenes.",
      "pacing_priority": "medium"
    }
  ],
  "omitted_units": [
    {
      "source_unit_id": 31,
      "reason": "already_implied",
      "safe_because": "Generalized zeal for reading and healthful air is covered by the summer-rebirth caption (30) and the concrete finance-book image (32)."
    }
  ],
  "continuity_requirements": [
    {
      "type": "character",
      "name": "Nick Carraway",
      "requirement": "Distinct dual presence: (a) retrospective writer in TF1; (b) active observer/actor in TF2–TF4. Maintain consistent modest dress and understated demeanor."
    },
    {
      "type": "character",
      "name": "Nick’s Father",
      "requirement": "Appears only in memory; gentle, reserved presence. Do not overdefine."
    },
    {
      "type": "character",
      "name": "Anonymous Neighbor (directions)",
      "requirement": "Harmless, slightly helpless newcomer; one-line dialog only."
    },
    {
      "type": "character",
      "name": "Finnish Woman (housekeeper)",
      "requirement": "Middle-aged, practical; shown muttering at electric stove; minimal face time."
    },
    {
      "type": "character",
      "name": "Coworker",
      "requirement": "Well-meaning; brief; exits swiftly to Washington. No further development."
    },
    {
      "type": "character",
      "name": "Jay Gatsby (implied)",
      "requirement": "Not seen directly; presence indicated only by mansion and scale. Maintain mystery."
    },
    {
      "type": "place",
      "name": "Nick’s Bungalow",
      "requirement": "Weather-beaten, compact; near the water; porch with view; feels ‘overlooked’ among palaces."
    },
    {
      "type": "place",
      "name": "Gatsby’s Mansion",
      "requirement": "‘Factual imitation’ Norman Hôtel de Ville; tower with raw ivy; marble pool; forty-plus acres; spanking new."
    },
    {
      "type": "place",
      "name": "West Egg vs East Egg",
      "requirement": "Twin peninsulas visible from Nick’s vantage; West Egg less fashionable; avoid map panels—use shoreline sightlines."
    },
    {
      "type": "time_frame",
      "name": "TF1 vs TF2–TF4",
      "requirement": "Color/light and staging must clearly separate narrator’s later reflections (TF1) from 1922 present (TF2–TF4)."
    },
    {
      "type": "object",
      "name": "Red-and-gold finance books",
      "requirement": "Gleam like ‘new money’; serve as motif for Nick’s self-improvement and money-world."
    },
    {
      "type": "object",
      "name": "Old Dodge",
      "requirement": "Aging, modest car; emphasizes Nick’s means vs neighbors."
    },
    {
      "type": "theme",
      "name": "Judgment vs Tolerance",
      "requirement": "Retain key aphorisms and the stated limit to Nick’s tolerance; avoid overexplaining with new text."
    },
    {
      "type": "theme",
      "name": "Hope and Summer Rebirth",
      "requirement": "Tie the roadside exchange and leafy visuals to the ‘life beginning over again with the summer’ line."
    },
    {
      "type": "theme",
      "name": "Superficial Similarity vs Deep Difference",
      "requirement": "Two Eggs identical in shape yet different in character; cue this through architecture and lawn vibes."
    }
  ],
  "storyboard_instructions": [
    "Maintain a clear visual grammar between TF1 (retrospective: desk, lamplight, cooler palette) and TF2–TF4 (1922 present: warmer, brighter).",
    "Let select aphorisms ride as captions over action; avoid over-captioning. Prioritize lines 1, 7, 11, 12–15, 30, 32, 33, 41–43.",
    "Keep geography grounded in Nick’s physical POV: have him point, look, or walk; no standalone maps or labels as main action.",
    "Use quick, silent vignettes for confidences (units 5–6) and domestic texture (23); save text for essential turns.",
    "Protect Gatsby’s mystery: exterior grandeur only; no direct sight of Gatsby yet.",
    "Emphasize contrasts of scale: Nick’s ‘small eyesore’ flanked by palaces; show Sound glimpses to lock orientation.",
    "Use seasonal cues (sunbursts, fast-growing leaves) to embody the ‘summer begins again’ idea without additional text.",
    "Keep dialog minimal and natural: one balloon for the directions question; otherwise rely on captions.",
    "Transitional moments (B5 train East; B10 shoreline orientation) should carry momentum, not stall—compose with strong leading lines.",
    "Ensure beats can expand to 25 panels downstream: each beat supports 1–3 panels while preserving order and clarity."
  ]
}

Return strict JSON only:

{
  "title": string,
  "adaptation_scope": string,
  "format": {
    "page_count": number,
    "target_panels_per_page": number,
    "reading_order": "left-to-right, top-to-bottom",
    "drafting_mode": "storyboard_from_plot_version"
  },
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
  "pages": [
    {
      "page_number": number,
      "page_summary": string,
      "panels": [
        {
          "panel_number": number,
          "graphic_beat_ids": [string],
          "driver_character": string,
          "character_action": string,
          "beat": string,
          "shot": "establishing" | "wide" | "medium" | "close" | "detail" | "silent",
          "image_prompt": string,
          "caption": string,
          "dialogue": [
            {"speaker": string, "text": string}
          ],
          "sfx": [string],
          "continuity_notes": string,
          "lettering_notes": string,
          "adaptation_note": string
        }
      ]
    }
  ],
  "open_questions": [string]
}