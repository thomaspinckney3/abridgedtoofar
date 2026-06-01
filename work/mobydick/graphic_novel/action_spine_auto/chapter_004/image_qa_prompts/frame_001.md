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
    "frame_number": 1,
    "caption": "Upon waking about daylight, I found Queequeg’s tattooed arm thrown over me, blending with the patchwork counterpane until its weight told me I was hugged.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium close-up from above the bed, dawn light on a patchwork quilt with a tattooed brown arm draped over the narrator.",
    "caption_zone": "bottom_right",
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
      "wake",
      "hugging posture",
      "lying in bed"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "19th-century New England inn bedroom at dawn; two men in a small bed; a brightly colored patchwork quilt; a tattooed brown arm draped over the pale narrator; soft daylight through a small window; no text anywhere. No readable text. Leave clean negative space in the bottom-right for the caption.",
    "purpose": "Establish the waking discovery and physical predicament that launches the scene."
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
