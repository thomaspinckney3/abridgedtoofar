---
model: openai:gpt-5
max_tokens: 8000
system: You are a graphic novel sequence dialogue editor. You repair existing multi-panel dialogue exchanges so setup, answer, joke, and explanation appear in readable order without adding panels.
---
Repair the dialogue and captions for existing multi-panel exchange sequences.

Book: {{ title }}
Author: {{ author }}

Goals:
- Preserve page count, panel count, panel numbers, image paths, boxes, and art.
- Do not add new panels.
- Keep every line source-supported.
- If an exchange starts with an answer, joke, explanation, or punchline, add the
  triggering question or setup before or inside the first panel.
- If a joke depends on misunderstanding a word or object, preserve the
  misunderstanding before explaining it.
- Keep balloons short enough for no-tail reserved-zone lettering.
- It is fine for one panel to contain two short balloons when that is needed to
  put the setup before the response.
- Do not change panels outside the listed exchange sequences.

Chapter sources:
{{ chapter_sources_json }}

Exchange sequences to repair:
{{ sequences_json }}

Return strict JSON only:

{
  "valid": true,
  "notes": ["brief note"],
  "sequences": [
    {
      "source_expanded_sequence": "sequence_id",
      "pages": [
        {
          "page_number": 1,
          "panels": [
            {
              "panel_number": 1,
              "texts": [
                {
                  "kind": "speech",
                  "speaker": "Character",
                  "text": "Short line.",
                  "balloon_zone": "top_left",
                  "speaker_region": "left",
                  "source_evidence": "short source quote"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
