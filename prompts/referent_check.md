---
model: anthropic:claude-sonnet-4-6
max_tokens: 12000
---
You are checking whether short paragraph pairs from an abridged novel stand on their own referentially. You are NOT reading the book in order — you are seeing isolated 2-paragraph windows in scrambled order. Your job is to flag windows whose meaning depends on material not in the window.

# Failure modes to flag

1. **Pronoun dangle** — `she`, `he`, `they`, `it`, `this`, `that` whose antecedent is not inside the window
2. **Definite-article dangle** — `the other girl`, `the letter`, `that night`, `the map` — a definite reference with no introducing/establishing noun inside the window
3. **Callback dangle** — `as I said`, `remember when`, `returned to the subject of X`, `that promise` — referring to prior material not in the window
4. **Connective dangle** — `but`, `however`, `so`, `yet`, `because` opening a paragraph that contrasts or follows something not inside the window

# What NOT to flag

- Generic referents a fluent reader resolves from literary convention: `the morning`, `the sun`, `the house` when there's been any previous setting
- First-person narrator pronouns (`I`, `my`) — always self-resolving
- Proper-named characters introduced elsewhere in the book — assume readers track named characters across windows; only flag PRONOUN dangles, not `Tom` or `Daisy`
- Stylistically-compressed prose where context is clear: "He stood up" after "Tom sat" is fine even across paragraphs — the dangle must create genuine confusion, not just "less setup than the original"
- Short dialogue responses (`"Yes."` / `"Very much."`) where the question isn't in the window — these are a known limitation of windowing

# Output

Return a single JSON array. Each entry:

```json
{
  "window_id": "W7",
  "referent": "the other girl",
  "nature": "pronoun" | "definite_article" | "callback" | "connective",
  "sentence": "<the problematic sentence, 10-40 words>",
  "explanation": "<one sentence: why a reader seeing only this window would be confused about this referent>"
}
```

Return `[]` if every window stands on its own.

# Windows (in random order)

{% for w in windows %}## [{{w.id}}]

{{w.text}}

{% endfor %}
