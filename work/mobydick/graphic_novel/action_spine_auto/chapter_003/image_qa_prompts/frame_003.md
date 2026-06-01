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
  "title": "The Spouter-Inn — Chapter Action Spine (Frames 3–8)",
  "source_chapter": "Moby-Dick, Chapter 3: The Spouter-Inn",
  "character_continuity": {},
  "prop_continuity": {},
  "frame": {
    "frame_number": 3,
    "caption": "Close upon midnight I made the landlord speak out, learned the talk of 'selling his head' meant ’balmed New Zealand heads, and yet let him lead me up to the prodigious bed.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Stairwell over-the-shoulder as the landlord leads with a candle and the narrator follows.",
    "caption_zone": "bottom_center",
    "visible_people": [
      "Ishmael",
      "Landlord"
    ],
    "visible_places": [
      "Spouter-Inn stairwell",
      "Upstairs corridor"
    ],
    "visible_props": [
      "candle"
    ],
    "visible_actions": [
      "Landlord leading the way",
      "Ishmael following, resigned"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Narrow wooden stairwell in a weathered inn, lit by a single candle held by the landlord climbing ahead; the sailor follows, hand on the rail, his face wary but resolved. Shadowed corridor above. No readable text. Leave clean negative space in the bottom-center for the caption.",
    "purpose": "Resolve the ‘head’ confusion and move Ishmael into the room despite lingering unease."
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
