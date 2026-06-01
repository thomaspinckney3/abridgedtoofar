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
    "frame_number": 6,
    "caption": "When the landlord burst in and named him Queequeg, I chose to trust the sober cannibal if he stowed his pipe, and turning in again I never slept better in my life.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Three-shot: landlord in the doorway with candle, Ishmael at his side, Queequeg seated in bed setting the pipe aside and making room.",
    "caption_zone": "bottom_right",
    "visible_people": [
      "Ishmael",
      "Landlord",
      "Queequeg"
    ],
    "visible_places": [
      "Upstairs room"
    ],
    "visible_props": [
      "candle",
      "bed",
      "tomahawk-pipe set aside"
    ],
    "visible_actions": [
      "Landlord calming the scene",
      "Queequeg motioning space kindly",
      "Ishmael consenting to return to bed"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Candlelit doorway scene: the landlord holds a light, grinning reassurance; the sailor stands near him relieved; Queequeg sits up in the vast bed, pipe set aside, politely making room with a calm gesture. The room’s sparse whaling gear remains. No readable text. Leave clean negative space in the bottom-right for the caption.",
    "purpose": "Resolve the conflict and show Ishmael’s decision to accept Queequeg as bedfellow."
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
