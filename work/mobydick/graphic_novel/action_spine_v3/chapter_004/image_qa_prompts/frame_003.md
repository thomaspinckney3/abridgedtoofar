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
    "frame_number": 3,
    "caption": "By much wriggling and loud expostulations I woke him; he drew back his arm, shook himself, and sat up staring, while I lay quiet and curious rather than afraid.",
    "driver_character": "Ishmael",
    "primary_action": "rouses Queequeg with persistent wriggling and scolding",
    "shot": "Two-shot at bed edge as Queequeg sits up",
    "caption_zone": "top_center",
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
      "Ishmael mid-expostulation, propped up",
      "Queequeg withdrawing his arm, shaking himself, sitting up and staring"
    ],
    "supporting_visuals": [
      "Ruffled bedding from the struggle",
      "Queequeg’s tattoos visible over chest and arms"
    ],
    "do_not_show": [
      "A literal pike-staff or dog",
      "Splashing water",
      "Readable text",
      "Any third person in the room"
    ],
    "image_prompt": "Ishmael leans forward in bed, mid-expostulation, as Queequeg sits up withdrawing his arm and giving himself a vigorous dry shake before staring at Ishmael. The rough inn bed is tousled, tattoos bold over Queequeg’s chest and arms, morning light cool. No readable text. Leave clean negative space in the top-center for the caption.",
    "purpose": "Resolve the immediate predicament by waking Queequeg and shift Ishmael’s mood from alarm to curiosity."
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
