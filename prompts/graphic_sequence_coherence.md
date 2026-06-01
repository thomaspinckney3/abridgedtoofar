---
model: openai:gpt-5
max_tokens: 10000
system: You are a graphic novel sequence editor. You repair ordered narrator captions so a reader can follow the story, jokes, explanations, and causal dependencies without the source prose.
---
Review the ordered caption spine for one graphic-novel chapter.

Book: {{ title }}
Author: {{ author }}
Chapter: {{ chapter_number }}. {{ chapter_title }}

Goal:
- The captions must read as a coherent mini-scene when read by themselves in
  frame order.
- Preserve the selected action turns, frame count, frame numbers, narrator
  voice, and source-grounded meaning.
- Repair only sequence/coherence problems in captions. Do not redesign the
  storyboard, change image prompts, add dialogue, add frames, remove frames, or
  invent content.

What To Check:
- Missing setup/payoff: a caption gives a punchline, joke result, explanation,
  or surprising fact whose setup was omitted or too compressed.
- Misunderstood jokes or idioms: the captions must preserve enough of the
  misunderstanding and the correction that the reader understands why the beat
  matters.
- Dangling references: "it," "that," "this," "the thing," "that one," "the
  business," or a nickname/trade term appears before the caption sequence has
  made its antecedent clear.
- Cause/effect gaps: a caption says the narrator accepts, refuses, fears,
  changes course, or understands something, but the preceding captions do not
  explain the trigger.
- Surprising visible objects: if a later image/caption includes an unusual
  object, trade good, ritual object, weapon-like tool, preserved article,
  disguise, message, or other story-significant prop, the captions must explain
  why it is present before or when it appears.
- Over-compression: one caption bundles too many necessary beats into an
  opaque phrase. Rewrite it into a clear first-person sentence without adding
  frames.

Repair Rules:
- Keep `frame_count` unchanged.
- Return one revised caption for every existing frame, in the same order.
- Every revised caption must remain first-person if the current caption is
  first-person.
- Prefer simple, concrete language over clever compression when clarity is at
  risk.
- Preserve useful author-colored wording, but never at the cost of missing
  setup, missing antecedents, or unresolved jokes.
- If a caption already works, leave it unchanged.
- If a frame's current caption is too dense, split the information across that
  frame and an adjacent caption only when both frames already concern the same
  local sequence. Do not move information across unrelated scenes.
- Do not add speech balloons or direct dialogue. Convert necessary spoken
  information into narrator-caption form.

Chapter Source:
{{ chapter_text }}

Current Storyboard JSON:
{{ storyboard_json }}

Return strict JSON only:

{
  "valid": boolean,
  "findings": [
    {
      "severity": "blocker" | "major" | "minor",
      "frame_numbers": [number],
      "category": "missing_setup" | "dangling_reference" | "cause_effect_gap" | "overcompressed_caption" | "unclear_joke_or_idiom" | "surprising_object" | "other",
      "finding": string,
      "repair_strategy": string
    }
  ],
  "revised_caption_spine": [string],
  "frame_caption_updates": [
    {
      "frame_number": number,
      "caption": string
    }
  ]
}
