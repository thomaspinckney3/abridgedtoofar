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
    "frame_number": 4,
    "caption": "Blundering into a public-looking doorway, I stumbled over an ash-box, choked, opened the inner door on a thundering preacher and his flock, and straightway backed out.",
    "driver_character": "Ishmael",
    "primary_action": "backs out of the mistaken church entry",
    "shot": "Interior threshold shot from the aisle, with Ishmael half-turned and retreating through the open door; preacher and congregation in background.",
    "caption_zone": "top_right",
    "visible_people": [
      "Ishmael",
      "church preacher",
      "church congregants"
    ],
    "visible_places": [
      "church interior with simple pulpit",
      "porch/threshold with ash dust"
    ],
    "visible_props": [
      "ash-box",
      "pulpit book",
      "carpet-bag"
    ],
    "visible_actions": [
      "Ishmael coughs and retreats, one hand on the door",
      "preacher raises a hand with a closed book",
      "congregants turn their heads toward the disturbance"
    ],
    "supporting_visuals": [
      "Ash motes hanging in lamplight",
      "Plain wooden pews and pulpit",
      "Dim, smoky illumination"
    ],
    "do_not_show": [
      "No readable text on walls or book",
      "No hellfire or literal Tophet imagery",
      "No caricatured features; keep respectful, realistic figures",
      "No speech balloons"
    ],
    "image_prompt": "Ishmael, coughing and startled, backs out through a church doorway, one hand on the doorframe and his carpet-bag tucked tight, as a preacher in a simple pulpit holds up a closed book and congregants glance over in dim lamplight; ash dust drifts in the air near a low ash-box at the threshold. No readable text. Leave clean negative space in the top-right for the caption.",
    "purpose": "Show the mistaken turn and quick retreat that continues his search for a bed."
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
