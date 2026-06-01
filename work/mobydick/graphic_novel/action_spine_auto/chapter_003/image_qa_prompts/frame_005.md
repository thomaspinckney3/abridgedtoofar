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
    "frame_number": 5,
    "caption": "Presently he entered with a New Zealand head, prayed to his little wooden idol, stripped to his tattooings, and at last sprang into bed with his tomahawk-pipe, whereat I sang out.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Dramatic candlelit leap: Queequeg, tattooed, tomahawk-pipe in mouth, springs into bed as the narrator recoils; the idol glows faintly on the hearth.",
    "caption_zone": "top_center",
    "visible_people": [
      "Ishmael",
      "Queequeg"
    ],
    "visible_places": [
      "Upstairs room with hearth"
    ],
    "visible_props": [
      "bedclothes thrown back",
      "tomahawk-pipe",
      "wooden idol between andirons",
      "shavings embers at hearth",
      "candle on floor"
    ],
    "visible_actions": [
      "Queequeg mid-leap into bed",
      "Ishmael recoiling and crying out"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "Night interior: a tattooed South Sea harpooneer springs onto a vast bed, tomahawk-pipe clenched, as the startled sailor recoils under the covers; at the fireplace, a little ebony idol stands between sooty andirons with faint embers from burnt shavings. Candlelight throws wild shadows. No readable text. Leave clean negative space in the top-center for the caption.",
    "purpose": "Deliver the shocking first contact that triggers Ishmael’s outcry."
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
