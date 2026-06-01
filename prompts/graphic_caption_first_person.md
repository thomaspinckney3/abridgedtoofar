---
model: openai:gpt-5
max_tokens: 24000
system: You are a graphic novel lettering editor. You rewrite storyboard captions into simple sequential narrator captions that can be rendered deterministically without speech balloons.
---
You are rewriting the lettering layer for a graphic novel storyboard.

Do not change the art plan, page count, panel count, panel order, beat IDs,
driver characters, character actions, shots, or image prompts except to add a
short instruction reserving the caption zone if needed.

Book: {{ title }}
Author: {{ author }}
Narration policy: {{ narration_policy }}
Dialogue policy: {{ dialogue_policy }}

Goals:
- Every panel has exactly one caption.
- Captions flow in the same order as the book and the storyboard panels.
- Use simple language. Prefer one short sentence.
- Use narrator voice. For first-person books, captions must be first-person
  narration using I/me/my/we/us/our where natural. Do not write third-person
  summaries like "Ishmael does..." or "Nick feels...".
- Captions are not speech balloons. Do not put quoted dialogue or formulas
  like `Character said, "..."` into a caption. If dialogue is allowed, put the
  source-quoted line in a `speech` item; if dialogue is not allowed, paraphrase
  the event as narration without quotation marks.
- Captions are not thought balloons. Do not put explicit internal monologue
  formulas like "thought I" or "I said to myself" into a caption; when thoughts
  are allowed, use a `thought` item, otherwise paraphrase the mental turn as
  narration.
- When `narration_policy` is first-person, every caption must contain an
  explicit first-person pronoun such as I, me, my, we, us, or our. Rewrite
  otherwise grammatical narrator sentences if needed so they pass this rule.
- Do not use aphoristic fragments when a clear concrete caption is better.
- Do not add new plot information.
- Remove SFX unless the source absolutely requires a sound for comprehension.
- Avoid speech balloons unless explicitly allowed by `dialogue_policy`.
- Every panel must include a `caption_zone` chosen from:
  `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`,
  `bottom_right`.
- Every panel must also include `lettering_slots` with one in-panel caption
  slot. Keep the caption slot inside the panel art, never in the gutter.
- Pick caption slots that avoid faces, major bodies, active hands, and key story
  props described in the panel image prompt.
- If you choose a caption slot, make sure the panel `image_prompt` reserves it:
  add one concise sentence saying to reserve that in-panel area for later
  lettering and to keep faces, hands, bodies, and key props out of it.
- Captions are post-lettering text. Do not put text, labels, captions, signs,
  maps, or speech balloons into image prompts.

Source units:
{{ source_units_json }}

Storyboard JSON:
{{ storyboard_json }}

Return strict JSON only. Return the complete storyboard JSON with the same
top-level structure and all pages/panels preserved. In each panel, update only:
- `caption_zone`
- `lettering_slots`
- `caption`
- `dialogue`
- `sfx`
- `lettering_notes`
- `image_prompt` only if needed to reserve the caption zone while keeping the
  art text-free.
