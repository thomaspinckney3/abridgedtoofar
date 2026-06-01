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
    "frame_number": 5,
    "caption": "I saw him commence at top with a very tall beaver hat, then crush himself—boots in hand and hat on—under the bed, and at last emerge dented, creaking and limping about the room.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium-wide comedic angle: Queequeg emerging from under the bed with a tall dented hat and newly pulled-on cowhide boots, limping.",
    "caption_zone": "bottom_left",
    "visible_people": [
      "Queequeg",
      "Ishmael"
    ],
    "visible_places": [
      "Spouter-Inn room",
      "bed"
    ],
    "visible_props": [
      "tall beaver hat",
      "cowhide boots",
      "bed"
    ],
    "visible_actions": [
      "crawling under bed",
      "emerging",
      "limping"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Humble wooden-floored inn room; tattooed man with an overly tall, dented top hat limps away from the bed in stiff cowhide boots; narrator partly visible watching; no legible markings anywhere. No readable text. Leave clean negative space in the bottom-left for the caption.",
    "purpose": "Show the outlandish order of dressing and its awkward result, deepening Ishmael’s amused observation."
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
