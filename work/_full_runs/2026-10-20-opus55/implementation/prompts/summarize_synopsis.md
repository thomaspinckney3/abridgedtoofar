---
model: openai:gpt-6-astra
max_tokens: 8000
---
Provide a synopsis of the following book{% if note %} {{note}}{% endif %}.

Write flowing prose, not a bulleted or sentence-per-line list. The synopsis should be approximately {{n_sentences}} sentences long (aim for that total; a few more or fewer is fine). Use normal paragraph breaks to structure the synopsis — typically one paragraph per major narrative movement (setup, inciting events, rising action, climax, resolution). Do NOT put one sentence per line.

Preserve principal characters, major plot turns, setting, and the book's thematic throughline. No preamble, no headings, no bullets — just the synopsis prose.

{{source}}
