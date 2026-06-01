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
    "frame_number": 2,
    "caption": "Sounding my pockets and finding only a few pieces of silver, I told myself to inquire the price and not be too particular where I lodged.",
    "driver_character": "Ishmael",
    "primary_action": "counts his small funds and resolves on frugal lodgings",
    "shot": "Medium shot, three-quarter view, Ishmael in a bleak street holding coins in his gloved palm.",
    "caption_zone": "bottom_center",
    "visible_people": [
      "Ishmael"
    ],
    "visible_places": [
      "dreary New Bedford street"
    ],
    "visible_props": [
      "silver coins",
      "carpet-bag",
      "patched boots"
    ],
    "visible_actions": [
      "Ishmael studies a few coins in his palm",
      "he hefts the carpet-bag under his other arm"
    ],
    "supporting_visuals": [
      "Ten-inch-thick packed snow along the curb, scuffed by foot traffic",
      "icy breath and drifting flakes",
      "dark facades with a few dim windows"
    ],
    "do_not_show": [
      "No readable text",
      "No speech balloons or thought bubbles",
      "No modern currency details",
      "Do not split his reasoning into separate visual beats"
    ],
    "image_prompt": "Ishmael stands in a bleak, snowbound street, tilting a gloved palm to reveal a few tarnished silver coins while his other arm hugs a small, worn carpet-bag. His patched boots and the bitter night air underscore his frugal resolve. No readable text. Leave clean negative space in the bottom-center for the caption.",
    "purpose": "Show his practical decision to seek cheap lodging, which drives the next actions."
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
