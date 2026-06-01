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
    "frame_number": 4,
    "caption": "He jumped out and, by signs and sounds, gave me to understand he would dress first and then leave me to dress, which I took for a very civilized overture and let him proceed.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium shot of Queequeg on the floor gesturing politely toward his clothes and the door while Ishmael watches from bed.",
    "caption_zone": "top_right",
    "visible_people": [
      "Ishmael",
      "Queequeg"
    ],
    "visible_places": [
      "Spouter-Inn room"
    ],
    "visible_props": [
      "scattered clothes"
    ],
    "visible_actions": [
      "gesturing politely",
      "watching from bed"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Small inn room; tattooed man on the floor making courteous gestures toward clothes and the doorway; narrator sits in bed observing; morning light; no written words visible. No readable text. Leave clean negative space in the top-right for the caption.",
    "purpose": "Establish Queequeg’s considerate offer and Ishmael’s acceptance while he continues to observe."
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
