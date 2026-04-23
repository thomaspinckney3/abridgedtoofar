---
model: openai:gpt-5
max_tokens: 8000
---
Provide a {{n_sentences}} sentence synopsis of the following book{% if note %} {{note}}{% endif %}. Output exactly {{n_sentences}} sentences, one per line, no preamble.

{{source}}
