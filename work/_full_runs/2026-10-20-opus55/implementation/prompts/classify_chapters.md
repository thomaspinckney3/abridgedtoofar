---
model: anthropic:claude-sonnet-5-5
max_tokens: 12000
system: |
  You classify the structural pieces of a book source, after an automated
  splitter has located candidate chapter boundaries, into diegetic (part of
  the narrative) vs extradiegetic (apparatus to cut from an abridgment).
  Respond with a single JSON array and nothing else — no preamble, no
  commentary, no markdown fences.
---
You are classifying the structural pieces of **{{book.title}}** by {{book.author}} ({{book.genre}}).

An automated splitter has broken the book's source into the candidate segments listed below. Your job: decide which are real narrative (keep) and which are apparatus around the narrative (cut).

## Classes

- **`diegetic`** — part of the book proper. Real chapters. Prologues that tell story (e.g., the framed-narrative prologue of The Phantom of the Opera). Epilogues that tell story (final chapter of a Dickens novel). Author's preface *when it is part of the narrative voice* (rare).
- **`extradiegetic`** — apparatus around the book. Editor's preface, translator's note, publisher's copyright and license text, illustration lists, author's biographical note, dedications, afterword, glossary, about-the-author blurbs, the Project Gutenberg header/footer.
- **`toc_fragment`** — a leaked table-of-contents entry. Under ~100 words, content is just a chapter title or heading line with little or no prose body.
- **`cut_for_review`** — genuinely unclear from the sample. Use sparingly.

## Decision rules

1. **Word count under 100 is almost always `toc_fragment`** unless the sample shows real prose of its own (e.g., a one-paragraph chapter, which is rare).
2. **Prologues default to `diegetic`** unless the text is clearly editorial commentary about the book rather than part of the book.
3. **Prefaces/forewords by the translator or editor are `extradiegetic`.** Author's own prefaces are a judgment call — prefer `diegetic` when they establish the narrative voice, `extradiegetic` when they're purely bibliographic or meta.
4. **Multi-part divider pages** ("PART ONE", "PART TWO" with a short title blurb of <200 words): `extradiegetic`. The chapters inside the parts are where the story lives.
5. **When in doubt, prefer `diegetic`.** Silently cutting real content is worse than keeping apparatus; the abridgment drafter can compress the noise, but it can't recover cut chapters.

## Candidates

{% for c in candidates %}
### Candidate {{c.id}}
- kind (splitter): **{{c.kind}}**
- number: {{c.number or '—'}}
- title: "{{c.title or '(no title)'}}"
- word_count: {{c.word_count}}
- sample: "{{c.sample}}"

{% endfor %}

## Output

Return a JSON array with one object per candidate, in the same order as listed above:

```json
[
  {"id": "001", "status": "extradiegetic", "reason": "Project Gutenberg header"},
  {"id": "002", "status": "toc_fragment", "reason": "table-of-contents stub"},
  {"id": "003", "status": "diegetic", "reason": "Chapter I narrative"}
]
```

Every candidate must appear once. `status` must be exactly one of `diegetic | extradiegetic | toc_fragment | cut_for_review`. `reason` is one short phrase — no more than a dozen words.
