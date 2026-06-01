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
    "frame_number": 3,
    "caption": "By dint of much wriggling and expostulation I roused him; he shook himself like a Newfoundland dog and sat up, while I lay quietly eyeing him with no serious misgivings, bent on narrowly observing so curious a creature.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Two-shot, three-quarters view: Queequeg upright in bed mid-shake, Ishmael propped on an elbow watching intently.",
    "caption_zone": "bottom_center",
    "visible_people": [
      "Ishmael",
      "Queequeg"
    ],
    "visible_places": [
      "Spouter-Inn room",
      "bed"
    ],
    "visible_props": [
      "patchwork counterpane"
    ],
    "visible_actions": [
      "waking",
      "shaking off sleep",
      "watching closely"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Simple wooden bed in a modest inn room; tattooed man sitting bolt upright mid-shake; the narrator watching calmly and curiously; soft morning light; no signage or text. No readable text. Leave clean negative space in the bottom-center for the caption.",
    "purpose": "Show the turn from alarm to curiosity and the narrator’s decision to observe Queequeg."
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
