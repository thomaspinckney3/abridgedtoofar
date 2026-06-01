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
    "frame_number": 2,
    "caption": "My misgivings grew; I changed my mind about that harpooneer and tried the bench for a bed, till the knots, planes, and freezing draughts beat me off the plan.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium-wide of the bar-room bench as the landlord planes it while the narrator huddles against a draughty window.",
    "caption_zone": "top_right",
    "visible_people": [
      "Ishmael",
      "Landlord"
    ],
    "visible_places": [
      "Spouter-Inn bar-room"
    ],
    "visible_props": [
      "wooden bench",
      "carpenter’s plane",
      "wood shavings",
      "draughty window",
      "stove"
    ],
    "visible_actions": [
      "Landlord planing bench",
      "Ishmael shivering and testing the bench"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Rough inn bar-room at night: the landlord bends over a scarred wooden bench, pushing a carpenter’s plane as curly shavings fly; nearby the sailor wraps his coat tight, testing the bench while a gust rattles a loose window and a cold draft shows in the candlelight. A black iron stove glows faintly. No readable text. Leave clean negative space in the top-right for the caption.",
    "purpose": "Show Ishmael’s refusal of the shared bed and his failed attempt to sleep on the bench due to discomfort and cold."
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
