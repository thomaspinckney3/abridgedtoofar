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
    "frame_number": 2,
    "caption": "No, when I go to sea, I go as a simple sailor right before the mast, content to be ordered about and to be paid for it.",
    "driver_character": "Ishmael",
    "primary_action": "choose the common-sailor role",
    "shot": "Medium shot at dockside beside a rigged sailing ship’s rail.",
    "caption_zone": "bottom_center",
    "visible_people": [
      "Ishmael"
    ],
    "visible_places": [
      "dock beside a rigged sailing ship"
    ],
    "visible_props": [
      "dock_spiles_and_ropes"
    ],
    "visible_actions": [
      "rest a hand on a tarred rope",
      "look toward the ship",
      "square shoulders in resolve"
    ],
    "supporting_visuals": [
      "A few indistinct sailors moving in the background on the dock",
      "Blocks, lines, and furled canvas suggesting the working parts of the ship",
      "Muted daylight and salt spray at the quay"
    ],
    "do_not_show": [
      "readable text",
      "a captain actively ordering him",
      "a broom or deck-sweeping",
      "a cook’s galley or cooking scenes",
      "officer insignia on Ishmael",
      "whales",
      "speech balloons"
    ],
    "image_prompt": "Ishmael rests his hand on a tarred hemp rope beside a rigged sailing ship at the dock, choosing to ship as a common sailor rather than a passenger. He wears the same plain 1840s working clothes and looks toward the vessel with steady resolve. Background sailors move indistinctly and the ship’s blocks, lines, and furled sails suggest work without drawing focus. No readable text. Leave clean negative space in the bottom-center for the caption.",
    "purpose": "Fix his chosen status as a before-the-mast sailor, not a passenger or officer, accepting orders and wages."
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
