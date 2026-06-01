---
model: openai:gpt-5
max_tokens: 24000
system: You are a graphic novel page editor. You turn a graphic plot treatment into pages, panels, text-free art prompts, and a separate lettering script while preserving character-driven causality.
---
You are creating a graphic novel storyboard from an intermediate graphic plot
treatment. The treatment has already decided what source material is preserved,
compressed, implied, or omitted.

Book: {{ title }}
Author: {{ author }}
Requested pages: {{ pages }}
Target panels per page: {{ panels_per_page }}

Hard rules:
- Use the plot treatment as the source of truth.
- Preserve graphic beat order exactly.
- Cover every graphic beat at least once.
- Do not include omitted source units.
- A panel may cover one beat or adjacent beats only.
- The plot treatment has already skipped source material that does not drive the
  graphic novel forward. Do not reintroduce skipped scenes, omitted exposition,
  atmospheric motifs, or future-story imagery while designing panels.
- Do not split a beat merely to preserve every described detail. One clear
  action panel is better than several panels of context if the extra context
  does not change what a character does next.
- Inanimate objects can never drive the plot. Every panel action must be driven
  by a visible living character, narrator, or role-identifiable person.
- Maps, diagrams, signs, labels, camera moves, montages, vignettes, timelines,
  trains, buildings, weather, books, windows, and landscapes are supports only.
  They cannot be the panel's action.
- If geography must be explained, stage it through a character looking,
  walking, pointing, arriving, entering, leaving, writing, reading, or speaking.
- Captions and dialogue are post-lettering text, not part of the image prompt.
- Image prompts must be for clean art only: no readable text, no captions,
  no labels, no signs, no maps with text, no speech balloons, no lettering.
- Lettering space is an image-generation constraint. Every panel must define
  explicit in-panel `lettering_slots` before art is generated, and the
  `image_prompt` must tell the artist to reserve those exact empty areas.
- Do not place caption boxes or balloons in gutters or outside panel frames.
- Image prompts must be source-grounded in content. The art style may be
  expressive, simplified, painterly, cartooned, or non-photorealistic, and
  scenery may be simplified for clarity. But the depicted people, places, props,
  animals, vehicles, weather, and actions must come from the beat's
  `visual_anchor`, `visual_evidence`, `physical_action_spine`, or necessary
  period/setting defaults.
- Stylization must not invent narrative content. Do not add unsupported objects,
  creatures, events, relationships, locations, symbols, or motifs.
- Do not add symbolic, anticipatory, thematic, or book-title imagery. Do not
  add any creature, object, emblem, place, color motif, weather motif, or other
  recurring visual motif unless the assigned beat explicitly places that visible
  thing in the scene.
- If a beat contains abstraction or reflection, draw the narrator's concrete
  physical situation and carry the abstraction in the caption. Do not draw a
  visual metaphor that adds unsupported content for the abstraction.
- Every panel must have exactly one caption. The caption should tell the story
  in simple, readable language and should flow in book order from the previous
  panel.
- Captions must be final reader-facing narration, not formatting notes. Do not
  use `//`, slash separators, bullet syntax, or labels inside caption text.
- Match the source narration voice. If the source/excerpt is first-person,
  captions must be first-person narration from that narrator, not third-person
  summaries about the narrator.
- Avoid speech balloons by default. Use dialogue only when the source contains
  an explicit spoken line and the visible speaker can be anchored unambiguously
  in the panel. Otherwise convert the information into the caption.
- Do not use speech balloons for lone-speaker remarks, remembered advice, or
  one-off informational questions. Put those in the caption as reported action.
  Reserve balloons for real multi-speaker exchanges where the dialogue order
  and speaker locations both matter.
- Use one of these panel archetypes: `caption_only`, `single_character`,
  `two_character`, `three_character_wide`.
- Use `single_character` for one visible speaker, `two_character` for two
  visible speakers, and `three_character_wide` only for a full-width panel with
  three visible speakers.
- Every panel must include one caption slot inside the art. The slot must be a
  simple empty area where the renderer can later place a caption box.
- If a panel has speech or thought balloons, add `balloon` slots tied to the
  speaking character. Stage speakers in the same left-to-right order as the
  balloon reading order. If that cannot be done clearly, omit the balloon and
  move the information into the caption.
- Keep faces, mouths, active hands, key props, and important gestures outside
  every lettering slot. Put these constraints directly into the `image_prompt`.
- Keep `caption_zone` for compatibility, choosing one of:
  `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`,
  `bottom_right`.
- Use exact source wording from `caption_candidates` when it is useful, but keep
  captions short enough for comics pacing.
- Do not invent speeches. Dialogue should come only from caption candidates or
  obvious quoted source lines.
- If a beat is reflective, stage the narrator physically writing, remembering,
  looking, walking, or deciding.

Graphic plot treatment:
{{ plot_version_json }}

Return strict JSON only:

{
  "title": string,
  "adaptation_scope": string,
  "format": {
    "page_count": number,
    "target_panels_per_page": number,
    "reading_order": "left-to-right, top-to-bottom",
    "drafting_mode": "storyboard_from_plot_version"
  },
  "style_bible": {
    "visual_period": string,
    "line_and_color": string,
    "lighting": string,
    "lettering": string,
    "recurring_motifs": [string]
  },
  "characters": [
    {
      "name": string,
      "visual_anchor": string,
      "costume": string,
      "expression_range": string,
      "continuity_note": string
    }
  ],
  "pages": [
    {
      "page_number": number,
      "page_summary": string,
      "panels": [
        {
          "panel_number": number,
          "graphic_beat_ids": [string],
          "driver_character": string,
          "character_action": string,
          "beat": string,
          "shot": "establishing" | "wide" | "medium" | "close" | "detail" | "silent",
          "image_prompt": string,
          "panel_archetype": "caption_only" | "single_character" | "two_character" | "three_character_wide",
          "lettering_slots": [
            {
              "id": string,
              "kind": "caption" | "speech" | "thought",
              "zone": "top_left" | "top_center" | "top_right" | "bottom_left" | "bottom_center" | "bottom_right",
              "box": {"x": number, "y": number, "w": number, "h": number},
              "speaker": string,
              "speaker_side": "left" | "center" | "right",
              "reserved_for": string,
              "reading_order": number
            }
          ],
          "caption_zone": "top_left" | "top_center" | "top_right" | "bottom_left" | "bottom_center" | "bottom_right",
          "caption": string,
          "dialogue": [
            {"speaker": string, "text": string}
          ],
          "sfx": [string],
          "continuity_notes": string,
          "lettering_notes": string,
          "adaptation_note": string
        }
      ]
    }
  ],
  "open_questions": [string]
}
