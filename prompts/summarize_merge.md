---
model: openai:gpt-5
max_tokens: 4000
---
Below are {{partials|length}} partial synopses of {{book.title}} by {{book.author}}, one per part of the book in order. Merge them into a single {{target_sentences}}-sentence synopsis covering the entire book in plot order. Preserve principal characters, major plot turns, setting, and the book's thematic throughline. Output only the {{target_sentences}} sentences, one per line, no preamble.

{% for p in partials %}=== Part {{loop.index}} synopsis ===
{{p}}

{% endfor %}
