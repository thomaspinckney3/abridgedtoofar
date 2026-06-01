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
  "title": "Moby-Dick Ch. 4: The Counterpane — Action Spine",
  "source_chapter": "Chapter 4. The Counterpane",
  "character_continuity": {},
  "prop_continuity": {},
  "frame": {
    "frame_number": 2,
    "caption": "I tried to unlock his bridegroom clasp and wriggle free, when a slight scratch and a fling of the quilt showed the tomahawk sleeping by his side.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium shot from bedside level as the narrator wriggles and flips the quilt back to reveal a tomahawk near the sleeping Queequeg.",
    "caption_zone": "top_left",
    "visible_people": [
      "Ishmael",
      "Queequeg"
    ],
    "visible_places": [
      "Spouter-Inn room",
      "bed"
    ],
    "visible_props": [
      "patchwork counterpane",
      "tomahawk"
    ],
    "visible_actions": [
      "wriggling",
      "sleeping",
      "revealing object"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Cramped inn bedroom; narrator twisting free while flipping back the quilt; a small tomahawk appears near the sleeping tattooed man; morning light; modest coverage with quilt; no labels or text visible. No readable text. Leave clean negative space in the top-left for the caption.",
    "purpose": "Escalate the predicament with the discovery of the weapon and the narrator’s effort to get free."
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
