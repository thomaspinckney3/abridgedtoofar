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
    "frame_number": 4,
    "caption": "Alone, I examined the harpooneer’s outlandish gear, even tried on his shaggy door-mat poncho, then, thinking he would not come, blew out the light and turned in.",
    "driver_character": null,
    "primary_action": null,
    "shot": "Interior of the cold room: the narrator in the shaggy poncho before a tiny mirror, with the huge bed and seaman’s gear around.",
    "caption_zone": "top_left",
    "visible_people": [
      "Ishmael"
    ],
    "visible_places": [
      "Upstairs room with prodigious bed"
    ],
    "visible_props": [
      "large bed",
      "sea chest",
      "seaman’s bag",
      "harpoon at headboard",
      "hammock bundle",
      "bone fishhooks on shelf",
      "shaggy poncho",
      "candle"
    ],
    "visible_actions": [
      "Ishmael trying on poncho at a small bit of glass",
      "bed turned down, candle ready to be snuffed"
    ],
    "supporting_visuals": [],
    "do_not_show": [],
    "image_prompt": "A cramped, cold inn chamber: a prodigious bed dominates; a harpoon leans at the headboard; a sea chest serves as table; a rolled hammock and a sailor’s bag lie in a corner; bone fishhooks on a rough shelf. The sailor, half-laughing and startled, wears an absurd shaggy poncho before a tiny bit of mirror, candlelight flickering as he prepares to extinguish it and get into bed. No readable text. Leave clean negative space in the top-left for the caption.",
    "purpose": "Mark Ishmael’s inspection of the harpooneer’s effects and his choice to retire first."
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
