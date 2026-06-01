---
model: openai:gpt-5
max_tokens: 12000
system: You are a graphic novel adaptation editor. You produce structured, visually specific storyboards from prose while preserving plot causality, character continuity, and tone.
---
You will adapt an excerpt from a published abridgment into a graphic novel storyboard.

Book: {{ title }}
Author: {{ author }}
Excerpt word range: {{ start_word }}-{{ end_word }}
Requested pages: {{ pages }}
Target panels per page: {{ panels_per_page }}

Adaptation rules:
- Preserve the excerpt's sequence of events and character relationships.
- Convert narration into visual action, panel composition, post-lettering captions, and sparse dialogue.
- Keep final lettering short. Do not invent long speeches.
- Preserve essential literary tone through captions and visual motifs, not through large text blocks.
- Do not include copyrighted art styles, living artist names, camera brands, or real actor likenesses.
- Make character descriptions repeatable enough for image generation continuity.
- Every panel must have a concrete visual prompt that could be handed to an image model.
- Image prompts must be for art only: no readable text, no captions, no labels, no speech balloons, no lettering. If text will be added later, leave clean negative space.
- Avoid vague prompts like "dramatic scene"; specify setting, action, blocking, expression, lighting, period costume, and mood.
- Do not over-adapt. If a moment is internal, choose a visible gesture, object, or setting detail that externalizes it.
- Do not combine non-adjacent story moments in one panel. Each panel must map to one contiguous source unit or to two immediately adjacent units.
- Do not create montage panels unless the source unit itself is summary/montage prose.
- Panel order must follow source order exactly. Do not jump forward and back.
- If adjacent source units express chronology or cause/effect, preserve that chain clearly. Do not collapse chronology into a symbolic montage if it would obscure what happened first, what caused what, or where a later decision takes place.
- If a source unit says a character moved, returned, or went somewhere, make the origin, destination, and timing explicit in beat/caption wording.
- Favor the most concrete scene beats over abstract thesis beats. If the prose is reflective, anchor the panel in the closest concrete memory, object, place, or gesture.
- Dialogue must come from the excerpt when possible. If the excerpt has no dialogue for a panel, use captions rather than invented speech.
- Captions and dialogue are a post-lettering script, not part of the image prompt.

Source units:
{% for unit in source_units %}
[{{ unit.id }}] words {{ unit.start_word }}-{{ unit.end_word }}
{{ unit.text }}

{% endfor %}

Return strict JSON only, with this shape:

{
  "title": string,
  "adaptation_scope": string,
  "format": {
    "page_count": number,
    "target_panels_per_page": number,
    "reading_order": "left-to-right, top-to-bottom"
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
          "beat": string,
          "shot": "establishing" | "wide" | "medium" | "close" | "detail" | "silent",
          "image_prompt": string,
          "caption": string,
          "dialogue": [
            {"speaker": string, "text": string}
          ],
          "sfx": [string],
          "continuity_notes": string,
          "source_unit_ids": [number],
          "source_word_range": [number, number],
          "source_anchor": string,
          "adaptation_note": string
        }
      ]
    }
  ],
  "open_questions": [string]
}

Excerpt:

{{ excerpt }}
