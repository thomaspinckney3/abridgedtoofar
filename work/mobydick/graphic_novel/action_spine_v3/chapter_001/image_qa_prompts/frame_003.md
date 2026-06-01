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
    "frame_number": 3,
    "caption": "By reason of these things, I fixed on a whaling voyage—the great whale and the wild, distant seas swayed me, and the wonder-world swung open.",
    "driver_character": "Ishmael",
    "primary_action": "resolve to ship on a whaling voyage",
    "shot": "Wide shot along the pier toward the open harbor and horizon.",
    "caption_zone": "bottom_center",
    "visible_people": [
      "Ishmael"
    ],
    "visible_places": [
      "pier leading toward open harbor"
    ],
    "visible_props": [
      "dock_spiles_and_ropes"
    ],
    "visible_actions": [
      "stride toward the seaward end of the pier",
      "turn his back to the city",
      "look to the horizon"
    ],
    "supporting_visuals": [
      "Wind catches his coat hem as he moves seaward",
      "City skyline receding behind him, low on the frame",
      "Choppy water and pale light opening ahead"
    ],
    "do_not_show": [
      "whales or whale imagery",
      "readable text",
      "maps or route lines",
      "personified Fates or stage programs",
      "election or battle scenes",
      "speech balloons"
    ],
    "image_prompt": "Ishmael strides along the pier toward the open harbor, turning his back to the city and facing the horizon, resolved to ship on a whaling voyage. Wind tugs his dark coat as coiled hemp lines and wooden spiles pass in the foreground; the city skyline falls away behind and pale light opens over choppy water ahead. No readable text. Leave clean negative space in the bottom-center for the caption.",
    "purpose": "Show the specific commitment to a whaling voyage and his inward welcome of its vastness and mystery."
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
