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
  "title": "Chapter 3: The Spouter-Inn — Action Spine",
  "source_chapter": "Moby-Dick, Chapter 3: The Spouter-Inn",
  "character_continuity": {
    "Ishmael (narrator)": {
      "role": "Narrator, traveler seeking a bed",
      "visual_description": "Young adult sailor, average build, clean-shaven, dark hair, wearing a worn dark monkey jacket over a plain shirt, rough trousers, and sea-scuffed boots; carries himself wary but curious."
    },
    "Peter Coffin (landlord)": {
      "role": "Innkeeper of the Spouter-Inn",
      "visual_description": "Lean New Englander, late middle-age, angular face with a wry grin, hair tied back or under a cap; simple waistcoat and rolled-up shirtsleeves; practical hands that plane wood or whittle."
    },
    "Queequeg (harpooneer)": {
      "role": "South Seas harpooneer and Ishmael’s future bedfellow",
      "visual_description": "Tall, powerfully built; skin with a purplish-yellow cast; face, torso, and limbs tattooed in dark square patterns; mostly bald with a small scalp-knot; wears a heavy grego/wrapall and a shaggy poncho-like cloak with quill-like tags when arriving; carries a tomahawk-shaped pipe, a seaman’s bag, a preserved head in trade, and a small polished wooden idol."
    }
  },
  "prop_continuity": {
    "smoke-dark whaling painting": {
      "visual_description": "Large, smoke-blackened oil painting with a looming dark shape above three faint blue verticals in a stormy, chaotic sea.",
      "avoid_confusion": "It is an abstracted whaling scene, not a literal supernatural tableau; no readable labels or plaques."
    },
    "wooden bench": {
      "visual_description": "Old carved wooden settle/bench with notches and whittled marks.",
      "avoid_confusion": "Do not depict it as a bed; it’s a hard bench in the bar-room."
    },
    "carpenter's plane": {
      "visual_description": "Sturdy wooden-bodied hand plane with exposed iron.",
      "avoid_confusion": "Tool for shaving wood, not a weapon."
    },
    "candle": {
      "visual_description": "Plain tallow candle with small brass or tin holder.",
      "avoid_confusion": "No readable labels; keep flame modest."
    },
    "seaman's bag": {
      "visual_description": "Large, weathered canvas sea-bag with knotted cords.",
      "avoid_confusion": "Not a trunk; soft-sided and cinched with rope."
    },
    "New Zealand preserved head": {
      "visual_description": "Small, shrunken, lacquer-dark human head with closed features, carried carefully.",
      "avoid_confusion": "A preserved head used as a trade curiosity, not a fresh or gory depiction."
    },
    "tomahawk-pipe": {
      "visual_description": "Hatchet-shaped smoking pipe with a bowl at the head and a mouthpiece at the handle.",
      "avoid_confusion": "It is primarily a pipe; do not render as a separate battle axe."
    },
    "wooden idol": {
      "visual_description": "Small, polished, hunch-backed ebony-like figurine set between andirons.",
      "avoid_confusion": "Not a living baby; a carved object used in a private rite."
    },
    "grego (heavy sailor's coat)": {
      "visual_description": "Bulky, dark wrapall coat with deep pockets, sea-worn.",
      "avoid_confusion": "Not a cape; a heavy overcoat."
    },
    "harpoon by bed": {
      "visual_description": "Tall iron harpoon standing upright at the bed’s head.",
      "avoid_confusion": "Keep as background prop; not used as weapon in scene."
    },
    "prodigious bed": {
      "visual_description": "Very large, plain wooden bedstead with heavy, rumpled blankets.",
      "avoid_confusion": "No ornate finials; utilitarian inn bed."
    },
    "papered fireboard": {
      "visual_description": "Thin panel with printed paper covering the fireplace opening.",
      "avoid_confusion": "Do not include readable text or imagery; it is removed for the idol."
    },
    "shaggy poncho-like cloak": {
      "visual_description": "Thick, door-mat-like garment with a central slit and small tinkling quill-like tags on the edge.",
      "avoid_confusion": "Garment, not an actual mat; worn as a poncho."
    }
  },
  "frame": {
    "frame_number": 3,
    "caption": "I changed my mind about that harpooneer, chose the bench, and soon learned that knots, a foot too short, and the meeting draughts would never do.",
    "driver_character": "Ishmael (narrator)",
    "primary_action": "attempts to make a bench-bed and abandons it",
    "shot": "Medium, lateral view of bench by wall and window",
    "caption_zone": "top_right",
    "visible_people": [
      "Ishmael (narrator)",
      "Peter Coffin (landlord)"
    ],
    "visible_places": [
      "Spouter-Inn public room/bar-room"
    ],
    "visible_props": [
      "wooden bench",
      "carpenter's plane",
      "candle"
    ],
    "visible_actions": [
      "Ishmael arranges bench and a chair to extend it, then recoils, clutching his coat against cold as the landlord lowers the plane in the background"
    ],
    "supporting_visuals": [
      "Wood shavings near the bench",
      "A loosely fitted window and rickety door suggesting drafts",
      "A central iron stove in the room"
    ],
    "do_not_show": [
      "The bench turning into a real bed",
      "Exaggerated wind effects or flying debris",
      "No readable text"
    ],
    "image_prompt": "Ishmael tries to bed down on a carved wooden bench he has shoved along the wall with a chair for length, then hugs his coat and grimaces as a cold draft cuts over him. In the background the landlord lowers a carpenter’s plane, wood shavings scattered near the bench; a loose window and rickety door suggest the crossing currents. No readable text. Leave clean negative space in the top-right for the caption.",
    "purpose": "Show Ishmael’s refusal of the share and the failure of his improvised alternative."
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
