---
model: openai:gpt-5
max_tokens: 18000
system: You are a graphic novel adaptation editor. You reduce one prose chapter into a short first-person action spine and one source-grounded frame plan per spine sentence.
---
Create a graphic-novel action spine for one chapter.

Book: {{ title }}
Author: {{ author }}
Chapter: {{ chapter_number }}. {{ chapter_title }}
Requested frame range: {{ min_frames }}-{{ max_frames }}

Goal:
- Find the chapter's core action: what a person does, decides, discovers,
  enters, leaves, accepts, refuses, fears, or understands next.
- Produce a short action-oriented synopsis in plain prose. This synopsis should
  sound like the answer to "what actually happens in this chapter?"
- The action-oriented synopsis must contain exactly one sentence per selected
  action turn. Do not write one long sentence that hides multiple frame beats.
- Then write first-person caption sentences in the narrator's voice, using the
  author's language where it helps clarity.
- Create exactly one frame for each caption sentence.
- The same selected action turns must appear in all three layers:
  the sentences of `action_oriented_synopsis`, `action_steps[].plain_sentence`,
  `caption_spine[]`, and `frames[]`.
- Create a continuity sheet before the frames:
  - `character_continuity` gives one stable visual description for every
    named or role-identifiable person who appears visibly.
  - `prop_continuity` gives one stable visual description for recurring,
    compound, archaic, or easily misread objects.
- Every frame must have a single `driver_character` and `primary_action`.
  Supporting details may appear, but they must not become the main visual
  action unless they are the selected action turn.

Selection rules:
- Do not preserve every paragraph, scene, detail, description, or joke.
- Omit material that does not drive the chapter's action forward.
- Do not create frames for rhetorical examples, analogies, philosophical
  explanations, hypothetical scenes, jokes, catalogues, or supporting arguments.
  Fold their useful meaning into a caption over the real action, or omit them.
- Do not create a frame for a context tableau that merely illustrates mood,
  setting, attraction, social pattern, or a general idea. A frame must change
  the narrator's situation, decision, knowledge, relationship, or physical path.
  If the only change is "this confirms the mood," fold it into an adjacent
  action frame.
- A narrator identity hook may be preserved as its own opening frame when it
  orients the reader for the chapter/book, especially in a first chapter or
  first-person narration.
- Do not split motives, reasons, explanations, costs, benefits, or attitudes
  into separate frames when they all support the same action decision. Fold them
  into that decision's caption.
- Do not turn a hypothetical into a visible event. If the narrator says "what
  if I were ordered to sweep a deck," do not draw him sweeping unless the
  chapter actually places him on that deck in story-present action.
- Use the fewest frames that preserve the chapter's action spine. Stay within
  the requested frame range unless the chapter is structurally impossible.
- Most chapters should use 3-6 frames. Use more than 6 only when the chapter has
  more than 6 actual action turns, not merely because it has many paragraphs.
- If the chapter's actual movement is one main decision supported by several
  reasons, use at most 4 frames. Reasons are not separate action turns.
- Example: if the narrator chooses to go as a common sailor and gives several
  reasons such as humility, orders, being paid, exercise, or air, that is still
  one action turn: choosing the common-sailor role. Do not create separate
  frames for each reason.
- Example: if the narrator says fate draws him to a voyage and the named object
  of the voyage opens wonder or curiosity, that is still one action turn:
  choosing or welcoming that voyage. Do not create separate frames for fate,
  curiosity, and welcome unless the chapter contains separate physical events.
- Likewise, choosing a course and welcoming that same course are one action
  turn unless the chapter contains a later physical event that changes the
  choice.
- Inanimate objects cannot drive the action. A street, sign, weather, ship,
  painting, bed, bench, or door may be setting or prop, but a person must drive
  each frame.
- If the narrator is reflecting, stage the narrator's concrete physical action
  or posture and put the reflection in the caption.

Caption rules:
- Captions must be first-person narration when the source chapter is first
  person. Use I, me, my, we, us, or our in every caption.
- If another character performs the visible action, keep the caption in the
  narrator's first-person viewpoint: "I watched him...", "I saw him...",
  "I found him...", "I let him...", or "I followed him...". Do not write
  captions that begin as detached third-person summary.
- Captions should be clear enough to carry the story without extra dialogue.
- Captions must make sense without the reader having the source paragraph open.
  Do not use a cryptic quotation, joke, idiom, or archaic phrase unless the
  caption itself gives the immediate context needed to understand it.
- Before returning, read only `caption_spine[]` in order. It must work as a
  coherent mini-scene without the images or source. If a caption contains a
  setup, misunderstanding, punchline, correction, or payoff, the needed setup
  and correction must appear either in that caption or in the immediately
  preceding/following caption. Do not let a later caption depend on a joke or
  explanation that was omitted.
- If a caption introduces a surprising object, person, place, quoted phrase,
  nickname, euphemism, or trade term, explain why it matters in the same
  caption unless an earlier caption already introduced that exact thing.
- Avoid dangling references such as "that business," "the mystery," "it,"
  "that one," or "the thing" unless the antecedent is explicit in the same
  caption or the immediately previous caption.
- If a source uses an ambiguous shorthand for a compound object, prefer the
  disambiguated compound name in captions and image prompts. For example, use
  "tomahawk-pipe" or "tomahawk-shaped pipe" rather than bare "tomahawk" when
  the visible object is a smoking pipe that could otherwise be mistaken for a
  weapon.
- Prefer compact author-colored language over neutral plot summary.
- Do not create speech balloons or dialogue.
- A caption may name an entity or idea that the source names, but naming it in
  the caption does not automatically allow it to appear visibly in the art.

Continuity rules:
- Use the exact same character description for a recurring person every time
  that person appears. If "the landlord" appears in three frames, all three
  image prompts must use the same age, build, hair/facial-hair, clothing, and
  posture vocabulary unless the source visibly changes him.
- Do not over-specify unsupported biography, ethnicity, or costume details.
  Continuity is for stable visual recognition, not invention.
- If a recurring character appears in a frame, include that character's
  continuity description in the frame's image prompt or rely on the generated
  frame prompt to inject it from `character_continuity`.
- If a prop has an archaic or compound name, disambiguate what it is. For
  example, a "tomahawk-pipe" is a smoking pipe with a hatchet-like form, not
  a separate battle axe, unless the source explicitly distinguishes it as one.
- If the source later calls the same compound prop by a shorter name, keep the
  same prop-continuity key so it is not redrawn as a different object.

Visual rules:
- The art may be stylized, simplified, painterly, cartooned, or
  non-photorealistic.
- The visible content must be source-grounded. Do not invent people, animals,
  creatures, objects, locations, symbols, relationships, events, labels, maps,
  signs with readable text, or visual metaphors.
- Do not show a named entity as a visible thing unless the chapter physically
  places that visible thing in the scene of the frame.
- Do not show the content of a comparison, joke, memory, prophecy, fear, or
  abstraction as a visible scene unless the chapter physically enters that scene.
- Named concepts in narration should usually be carried by caption and by the
  character's action/posture, not by invented visual entities.
- If the source mentions a sign, book, paper, painting, or label, the image may
  show the object but must not include readable text.
- Do not literalize similes, metaphors, idioms, jokes, or comparisons in the
  art. If a caption says a person "shook himself like a dog," show the person
  waking and shaking off sleep; do not show a dog, water, wet fur, spray, or
  other literal content from the comparison unless it is physically present in
  the source scene.
- Every frame must include a `do_not_show` list for image-generation traps:
  literalized similes, ambiguous props, readable text, unsupported symbols,
  or support actions that should not dominate the frame.
- If the source includes a minor comic/procedural detail, do not foreground it
  unless that detail is the selected action turn. Keep the frame centered on
  the `driver_character` and `primary_action`.
- The first sentence of every `image_prompt` must visibly stage the
  `driver_character` performing the `primary_action`.
- Do not make a secondary character's helper action more visually prominent
  than the driver character's primary action. If a helper action must appear,
  describe it as background or secondary.
- `image_prompt` must be self-contained visual direction. Do not rely on the
  caption text to explain the image; the final image-generation prompt may omit
  the caption to prevent metaphor literalization.
- Every image prompt must say "No readable text."
- Every frame must reserve one caption zone chosen from:
  `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`,
  `bottom_right`.

Chapter text:
{{ chapter_text }}

Return strict JSON only:

{
  "title": string,
  "source_chapter": string,
  "adaptation_principle": string,
  "character_continuity": {
    "character_or_role_name": {
      "role": string,
      "visual_description": string
    }
  },
  "prop_continuity": {
    "prop_name": {
      "visual_description": string,
      "avoid_confusion": string
    }
  },
  "action_oriented_synopsis": string,
  "action_steps": [
    {
      "step_number": number,
      "plain_sentence": string,
      "first_person_caption": string
    }
  ],
  "caption_spine": [string],
  "frames": [
    {
      "frame_number": number,
      "caption": string,
      "driver_character": string,
      "primary_action": string,
      "shot": string,
      "caption_zone": "top_left" | "top_center" | "top_right" | "bottom_left" | "bottom_center" | "bottom_right",
      "source_evidence": [string],
      "visible_content": {
        "people": [string],
        "places": [string],
        "props": [string],
        "actions": [string]
      },
      "supporting_visuals": [string],
      "do_not_show": [string],
      "image_prompt": string,
      "purpose": string
    }
  ],
  "omitted_material": [
    {
      "material": string,
      "reason": string
    }
  ],
  "visual_safety_notes": [string]
}
