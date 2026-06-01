Review one generated graphic-novel frame against its storyboard contract.

Return strict JSON only. Do not include prose outside JSON.

Your job is not to judge taste. Your job is to catch automation failures that
will break a source-grounded graphic adaptation:

- recurring character appearance drift
- recurring or archaic prop confusion
- literalized similes, metaphors, idioms, memories, or jokes
- unsupported people, animals, objects, labels, symbols, or events
- readable text in the image
- the frame focusing on a supporting detail instead of the primary action
- caption-zone failure, where the reserved area is too busy for later lettering

Use the image itself as evidence. A finding is valid only if it is visible.
If a storyboard instruction is merely absent from the image but the omission
does not harm continuity or story comprehension, mark it minor or omit it.

Storyboard contract:
{
  "title": "Moby-Dick — Ch.2 The Carpet-Bag: Finding a Bed in New Bedford",
  "source_chapter": "Chapter 2. The Carpet-Bag",
  "character_continuity": {
    "Ishmael": {
      "role": "narrator and traveler",
      "visual_description": "Young adult seaman, lean, wind-reddened face, dark wool pea-coat, knit cap, patched leather boots, carrying a small worn carpet-bag under one arm."
    },
    "church preacher": {
      "role": "preacher at the waterfront church",
      "visual_description": "Middle-aged Black man in a plain dark frock coat, standing in a simple wooden pulpit, one hand raised and the other holding a closed book."
    },
    "church congregants": {
      "role": "worshipers in pews",
      "visual_description": "Rows of bundled-up Black townsfolk in plain winter garments, seen in dim lamplight as attentive silhouettes facing the pulpit."
    }
  },
  "prop_continuity": {
    "carpet-bag": {
      "visual_description": "Small, old-fashioned soft-sided travel bag of mottled fabric with leather trim, scuffed and hand-carried under the arm.",
      "avoid_confusion": "Do not depict a modern suitcase or backpack; keep it a compact 19th-century travel bag."
    },
    "patched boots": {
      "visual_description": "Dark leather ankle boots with visible sole wear and rough toe patches.",
      "avoid_confusion": "Avoid shiny or new footwear; soles should look thin and battered."
    },
    "silver coins": {
      "visual_description": "A few small, tarnished silver coins resting in Ishmael’s gloved palm.",
      "avoid_confusion": "No modern coin designs; keep details indistinct and with No readable text."
    },
    "ash-box": {
      "visual_description": "Low wooden or tin box in a porch corner, half-filled with gray stove ashes, lid ajar with dust about.",
      "avoid_confusion": "Not a coal scuttle or trash can; fine ash should suggest a hearth clean-out."
    },
    "Spouter Inn signboard": {
      "visual_description": "A creaking, weathered wooden swinging sign showing a faint painting of a tall, misty jet of spray.",
      "avoid_confusion": "No readable text on the sign; emphasize the spray image and aged wood."
    },
    "pulpit book": {
      "visual_description": "A thick, closed, leather-bound book held by the preacher.",
      "avoid_confusion": "No readable title or page text."
    }
  },
  "frame": {
    "frame_number": 5,
    "caption": "Then I saw the swinging sign with a tall jet of spray—ominous names or no—and judged this the very spot for cheap lodgings, so I made for the door.",
    "driver_character": "Ishmael",
    "primary_action": "chooses the Spouter Inn and moves to enter",
    "shot": "Low-angle medium shot of Ishmael under a creaking sign, hand reaching for the tavern’s weathered door.",
    "caption_zone": "top_center",
    "visible_people": [
      "Ishmael"
    ],
    "visible_places": [
      "bleak dockside corner",
      "exterior of a dilapidated wooden inn"
    ],
    "visible_props": [
      "Spouter Inn signboard",
      "carpet-bag",
      "patched boots"
    ],
    "visible_actions": [
      "Ishmael looks up at the sign and reaches for the door latch",
      "the sign swings on rusty irons in the wind"
    ],
    "supporting_visuals": [
      "A gable-ended house leaning slightly, clapboards weathered",
      "Night wind pushing sleet across the corner",
      "Faint lamplight from within"
    ],
    "do_not_show": [
      "No readable text on the sign",
      "Do not depict Peter Coffin as a person yet",
      "No skull-and-crossbones or invented symbols",
      "No interior scenes beyond a vague glow"
    ],
    "image_prompt": "Ishmael stands at a bleak dockside corner beneath a creaking, weathered sign painted with a faint tall jet of spray, his hand reaching for the inn’s worn wooden door while his carpet-bag rides under his arm; the gable-ended house leans slightly as wind drives sleet past. No readable text. Leave clean negative space in the top-center for the caption.",
    "purpose": "Land the chapter’s decision: he picks the Spouter Inn as his lodging and prepares to enter."
  }
}

Return this JSON shape:

{
  "frame_number": number,
  "valid": boolean,
  "findings": [
    {
      "severity": "blocker" | "major" | "minor",
      "category": "character_continuity" | "prop_confusion" | "literalized_comparison" | "unsupported_content" | "readable_text" | "primary_action" | "caption_zone" | "other",
      "finding": string,
      "visible_evidence": string,
      "repair_prompt": string
    }
  ]
}
