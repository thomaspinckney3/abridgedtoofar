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
    "frame_number": 7,
    "caption": "To my amazement he washed only chest, arms, and hands, then lathered his face and, unsheathing the harpoon head, fell to harpooning his cheeks before marching out wrapped in his pilot monkey jacket, sporting the weapon like a marshal’s baton.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Medium shot at the wash-stand: Queequeg, in pantaloons and waistcoat, lathers his face and uses the harpoon head as a razor before a small wall mirror; his jacket and the harpoon’s stock rest nearby.",
    "caption_zone": "bottom_right",
    "visible_people": [
      "Queequeg",
      "Ishmael"
    ],
    "visible_places": [
      "Spouter-Inn room",
      "wash-stand",
      "small mirror"
    ],
    "visible_props": [
      "soap",
      "water basin",
      "harpoon head",
      "harpoon stock",
      "pilot monkey jacket"
    ],
    "visible_actions": [
      "washing torso",
      "lathering face",
      "shaving with harpoon head",
      "preparing to leave"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Simple boarding-house room; small wash-stand with basin; tattooed man, trousers and waistcoat on, face lathered, carefully shaving with a gleaming harpoon head before a tiny wall mirror; harpoon stock leaned aside, heavy jacket ready; no written labels or text. No readable text. Leave clean negative space in the bottom-right for the caption.",
    "purpose": "Deliver the chapter’s peak oddity—the harpoon shave—and close the scene with his finished toilette and exit."
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
