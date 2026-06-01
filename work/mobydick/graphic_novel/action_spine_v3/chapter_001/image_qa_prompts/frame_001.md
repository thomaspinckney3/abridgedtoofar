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
  "title": "Moby-Dick — Loomings (Action Spine)",
  "source_chapter": "Chapter 1: Loomings",
  "character_continuity": {
    "Ishmael": {
      "role": "narrator and prospective sailor",
      "visual_description": "A lean young man in plain 1840s working clothes: dark wool pea coat, simple shirt, rough trousers, worn boots, knit watch cap; clean-shaven or light stubble; thoughtful, reserved demeanor."
    }
  },
  "prop_continuity": {
    "coin_purse": {
      "visual_description": "A small, worn brown leather coin purse with a simple clasp; only a few coins inside.",
      "avoid_confusion": "Not a modern wallet or billfold; do not show paper currency."
    },
    "dock_spiles_and_ropes": {
      "visual_description": "Weathered wooden pier posts with coiled tarred hemp ropes and mooring lines.",
      "avoid_confusion": "Not decorative nautical props; avoid modern synthetic lines or bright plastic buoys."
    }
  },
  "frame": {
    "frame_number": 1,
    "caption": "Call me Ishmael; finding a damp, drizzly November in my soul, I take to the ship and set my course for the watery part of the world.",
    "driver_character": "Ishmael",
    "primary_action": "decide to go to sea",
    "shot": "Medium-wide three-quarter view at the pier edge, profile toward the harbor.",
    "caption_zone": "bottom_center",
    "visible_people": [
      "Ishmael"
    ],
    "visible_places": [
      "city waterfront pier",
      "harbor horizon"
    ],
    "visible_props": [
      "coin_purse",
      "dock_spiles_and_ropes"
    ],
    "visible_actions": [
      "stand at the pier deciding",
      "look toward the water",
      "hold a small coin purse"
    ],
    "supporting_visuals": [
      "Overcast sky with a light drizzle and damp planks underfoot",
      "A few distant indistinct figures along the rail far behind Ishmael",
      "Moored merchant ships in the distance with furled sails",
      "Sea birds wheeling over gray water"
    ],
    "do_not_show": [
      "whales",
      "readable text",
      "speech balloons",
      "pistol and ball",
      "coffin warehouses or funerals as literal scenes",
      "hats being knocked off",
      "personified Fates or stage scenes",
      "Narcissus or mirror-water imagery"
    ],
    "image_prompt": "Ishmael stands at the edge of a city pier, gazing out over the gray harbor as he grips a nearly empty coin purse, deciding to go to sea. He wears a dark wool pea coat, rough trousers, worn boots, and a knit watch cap; his posture is thoughtful but resolute. Damp wooden spiles and coiled tarred hemp ropes frame the pier; light drizzle mists the air under a low overcast. Distant ships sit at anchor far beyond him and a few indistinct figures linger well in the background. No readable text. Leave clean negative space in the bottom-center for the caption.",
    "purpose": "Establish the narrator and his present resolve to go to sea as his remedy for melancholy."
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
