---
model: anthropic:claude-opus-4-7
max_tokens: 24000
system: You are a senior story analyst for graphic-novel adaptation. You extract source-grounded story beats before any page or panel decisions are made.
---
You are creating a beat inventory from an abridged novel chapter.

This is NOT a page storyboard, NOT a caption draft, and NOT image prompts.
This stage comes before pacing and panel selection.

Book: {{ title }}
Author: {{ author }}
Excerpt word range: {{ start_word }}-{{ end_word }}

Working definition:
- A beat is the smallest source-grounded story operation that changes the
  reader's understanding of the scene.
- A beat is not a sentence, paragraph, quote, mood, image, or pretty excerpt.
- A valid beat can be paraphrased as: because X is true, a specific participant
  does or experiences Y, so now the reader knows Z.
- A beat must name its participants, actor, action, object, result,
  dependencies, and reader-new information.
- A beat must be useful for a later graphic-novel script. It needs a visual
  contract: required visible content and forbidden unsupported content.

Beat types:
- orientation: establishes location, time, or who is present.
- entrance: a character enters or is first introduced.
- relationship: defines how characters know each other.
- action: someone does something visible.
- dialogue_exchange: one utterance and its necessary reply/setup.
- revelation: new information changes what the reader knows.
- decision: someone chooses what to do.
- reaction: someone responds emotionally or physically to an event.
- transition: moves the story to a new place/time.
- setup: introduces information required by a later beat.
- payoff: uses earlier setup.

Rules:
- Preserve source order.
- Extract the beat inventory first; do not compress to fit a page budget.
- Do not make one beat per source unit. Merge adjacent source units only when
  they are part of the same story operation.
- Do not choose beats because the prose is attractive. Choose beats because
  they change action, knowledge, relationship, orientation, or causality.
- Pure mood, rhetorical texture, repeated description, or abstract commentary
  can be marked as supporting context or omitted from beats, but it must still
  be accounted for in `source_unit_treatments`.
- If a payoff needs a setup, include the setup in the same beat or as an
  earlier beat. Do not emit an orphan payoff.
- If a dialogue line replies to an omitted line, merge the exchange or omit the
  reply. Do not emit orphan dialogue.
- `depends_on` may list only earlier beat IDs.
- `enables` may list later beat IDs if known. Use an empty array rather than
  guessing beat IDs.
- Every pronoun or reference needed to understand the beat must have an
  antecedent inside the beat or in `depends_on`.
- Inanimate objects can never drive the plot. The actor must be a visible
  living character, narrator, or role-identifiable person in the assigned
  source units.
- If an event is caused by an object, sound, weather, machine, place, or
  off-panel person, rewrite the beat around a visible character's reaction,
  choice, movement, refusal, discovery, or changed understanding. Do not make
  the object, sound, weather, machine, place, or unseen person the actor.
- If the source unit moves characters into separate locations, rooms, groups,
  or pairings, preserve all resulting groups in `required_context`, even when
  only one group is visible in the eventual panel. Later beats must not depend
  on an unrecorded split-scene setup.
- `depends_on` must include every earlier beat needed to resolve pronouns,
  references, continued dialogue, emotional reactions, causal judgments,
  exits, entrances, repeated locations, repeated objects, or relationship
  facts. If a beat reacts to a prior exchange, include that prior exchange in
  `depends_on`.
- `reference_dependencies` must name the specific prior facts needed to
  understand this beat, such as "the addressee has just refused the offer" or
  "the travelers have split into two rooms." Use an empty array only when the
  beat is self-contained.
- Be source-grounded about visual content. Required visuals and forbidden
  visuals may include only what follows from the assigned source units.
- Do not add symbolic, anticipatory, thematic, or book-title imagery.
- Do not put maps, diagrams, timelines, labels, signs, aerial exposition, or
  other explanation devices in `required_visuals`.
- For geography or orientation beats, use a character-vantage visual: a
  character looking, arriving, walking, driving, standing, pointing, reading,
  writing, or otherwise physically relating to the place.
- Do not infer future plot facts beyond the assigned source units. If the
  source is retrospective, ominous, or ambiguous, describe it that way without
  naming later outcomes, identities, romances, betrayals, deaths, solutions, or
  revelations that are not yet explicit.

Source units:
{% for unit in source_units %}
[{{ unit.id }}] words {{ unit.start_word }}-{{ unit.end_word }}
{{ unit.text }}

{% endfor %}

Return strict JSON only:

{
  "title": string,
  "beat_contract_version": 2,
  "adaptation_scope": string,
  "source_unit_treatments": [
    {
      "source_unit_id": number,
      "treatment": "beat" | "supporting_context" | "merged_into_adjacent_beat" | "omit",
      "beat_ids": [string],
      "reason": string
    }
  ],
  "beats": [
    {
      "beat_id": string,
      "source_unit_ids": [number],
      "beat_type": "orientation" | "entrance" | "relationship" | "action" | "dialogue_exchange" | "revelation" | "decision" | "reaction" | "transition" | "setup" | "payoff",
      "scene": string,
      "time": string,
      "participants": [string],
      "actor": string,
      "action": string,
      "object": string,
      "result": string,
      "reader_new_info": string,
      "depends_on": [string],
      "enables": [string],
      "required_context": [string],
      "reference_dependencies": [string],
      "required_visuals": [string],
      "forbidden_visuals": [string],
      "visualizable": boolean,
      "importance": "high" | "medium" | "low",
      "evidence": [string],
      "notes": string
    }
  ]
}
