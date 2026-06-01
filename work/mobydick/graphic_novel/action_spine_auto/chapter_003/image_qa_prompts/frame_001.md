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
    "frame_number": 1,
    "caption": "The landlord told me his house was full, and I agreed, rather than wander further on so bitter a night, to share a harpooneer’s blanket if he were not decidedly objectionable.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium two-shot at the bar, candlelit, with the narrator facing the landlord across the whale-jaw arch.",
    "caption_zone": "bottom_left",
    "visible_people": [
      "Ishmael",
      "Landlord"
    ],
    "visible_places": [
      "Spouter-Inn public room with whale-jaw bar"
    ],
    "visible_props": [
      "candle",
      "bar shelves with bottles",
      "arched whale jawbone"
    ],
    "visible_actions": [
      "Landlord offering terms",
      "Ishmael nodding reluctantly"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Candlelit interior of a rough seaport inn public room; a vast whale jawbone frames a small bar where a wiry landlord gestures matter-of-factly, while a travel-worn sailor with sea bag and coat listens, hesitant. Old bottles and decanters on shabby shelves, cracked curios cases in the background. Low beams and scuffed floorboards. No readable text. Leave clean negative space in the bottom-left for the caption.",
    "purpose": "Establish Ishmael’s provisional decision to share the harpooneer’s bed rather than go back into the bitter night."
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
