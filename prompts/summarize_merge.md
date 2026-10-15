---
model: openai:gpt-6-astra
max_tokens: 16000
---
Below are {{partials|length}} partial synopses of {{book.title}} by {{book.author}}, one per part of the book in order.

Merge them into a single continuous synopsis covering the entire book in plot order. Write flowing prose, not a bulleted or sentence-per-line list — use paragraph breaks for major narrative movements (setup, rising action, climax, resolution). Aim for approximately {{target_sentences}} sentences total; a few more or fewer is fine.

Preserve principal characters, major plot turns, setting, and the book's thematic throughline. No preamble, no headings, no bullets — just the synopsis prose.

{% for p in partials %}=== Part {{loop.index}} synopsis ===
{{p}}

{% endfor %}
