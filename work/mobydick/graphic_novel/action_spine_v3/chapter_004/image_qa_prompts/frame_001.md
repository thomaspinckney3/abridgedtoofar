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
  "title": "The Counterpane — Action Spine (Frames 3–8 range)",
  "source_chapter": "Moby-Dick, Ch. 4: The Counterpane",
  "character_continuity": {
    "Ishmael": {
      "role": "Narrator; lodging sailor at the Spouter-Inn",
      "visual_description": "Young adult man, lean build, dark wavy hair to the ears, clean but travel-worn look; in a simple off-white 19th-century nightshirt when in bed."
    },
    "Queequeg": {
      "role": "Harpooner; Ishmael’s bedfellow",
      "visual_description": "Powerfully built man with dark brown skin, dense black geometric tattoos covering arms and chest, short black hair; calm, self-possessed demeanor. When dressing: a very tall black felt beaver hat; later cowhide boots, pantaloons, waistcoat, and a heavy short pilot monkey jacket; carries a whaling harpoon."
    }
  },
  "prop_continuity": {
    "patchwork_counterpane": {
      "visual_description": "A thick patchwork quilt with many small, irregular squares and triangles in mixed colors spread over the bed.",
      "avoid_confusion": "It is a quilt on the bed, not a rug or wall hanging."
    },
    "tomahawk-pipe": {
      "visual_description": "A small wooden smoking pipe with a hatchet-shaped metal head resting near Queequeg.",
      "avoid_confusion": "Do not depict a large battle axe; it is a pipe with a hatchet-like head."
    },
    "whaling_harpoon": {
      "visual_description": "A stout whaling harpoon with a detachable wooden stock and a long, straight-edged steel head kept very sharp.",
      "avoid_confusion": "Not a spear or pike; show the detachable stock and the steel head used for shaving when unsheathed."
    },
    "beaver_hat": {
      "visual_description": "A very tall black felt stovepipe-style top hat.",
      "avoid_confusion": "Do not depict the animal; it is a hat of beaver felt style."
    },
    "cowhide_boots": {
      "visual_description": "Damp, wrinkled, brown cowhide pull-on boots, slightly ill-fitting and creaky.",
      "avoid_confusion": "Not modern lace-up boots or riding boots."
    },
    "pilot_monkey_jacket": {
      "visual_description": "A short, heavy, double-breasted, dark wool sailor’s jacket suited to cold weather.",
      "avoid_confusion": "Not a tailcoat or long overcoat."
    },
    "washstand_and_mirror_shard": {
      "visual_description": "A small wash-stand table with a basin and a small piece of mirror tacked against the wall above.",
      "avoid_confusion": "Do not show a full-length dressing mirror."
    },
    "hard_soap_bar": {
      "visual_description": "A small off-white rectangular bar of hard soap.",
      "avoid_confusion": "Do not depict it as food."
    }
  },
  "frame": {
    "frame_number": 1,
    "caption": "I woke at daylight to find Queequeg’s tattooed arm thrown over me, so blended with the patchwork counterpane that only its weight told me he was hugging me.",
    "driver_character": "Ishmael",
    "primary_action": "wakes and discovers Queequeg’s arm hugging him",
    "shot": "Medium close in bed, dawn light across the quilt",
    "caption_zone": "top_left",
    "visible_people": [
      "Ishmael",
      "Queequeg"
    ],
    "visible_places": [
      "Spouter-Inn bedchamber"
    ],
    "visible_props": [
      "patchwork_counterpane"
    ],
    "visible_actions": [
      "Ishmael waking and looking down",
      "Queequeg sleeping with arm draped over Ishmael"
    ],
    "supporting_visuals": [
      "Dawn light from a small window",
      "Queequeg’s tattooed forearm blending visually with the quilt’s colored pieces",
      "Simple wooden bed and rough-plastered wall"
    ],
    "do_not_show": [
      "Readable text anywhere",
      "Wedding imagery or rings",
      "Literal labyrinth or maze apart from tattoos",
      "Additional people",
      "Any memory scene or phantom hand as a separate figure"
    ],
    "image_prompt": "Ishmael wakes and looks down at Queequeg’s tattooed arm draped across his chest. Stage them in a narrow 19th-century inn bed under a multicolored patchwork quilt; the intricate black tattoos on the arm visually echo the quilt’s little squares and triangles. Dawn light spills softly from a small window. Ishmael’s eyes are open in surprised recognition while Queequeg sleeps, his arm heavy across Ishmael. No readable text. Leave clean negative space in the top-left for the caption.",
    "purpose": "Establish the morning discovery and the intimate, comic predicament that begins the chapter’s action."
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
