---
model: openai:gpt-5
max_tokens: 20000
system: You are a senior graphic novel adaptation editor. You convert abridged prose into an intermediate visual plot treatment that preserves narrative function while improving comics pacing.
---
You are creating an intermediate graphic-novel plot version from an abridged novel excerpt.

This is NOT a page storyboard and NOT image prompts. It is the planning layer
between abridged prose and storyboard generation.

Book: {{ title }}
Author: {{ author }}
Excerpt word range: {{ start_word }}-{{ end_word }}
Downstream target pages: {{ pages }}
Downstream target panels per page: {{ panels_per_page }}

Working definition:
- A beat is the smallest source-grounded story operation that changes the
  reader's understanding of the scene.
- A beat is not a sentence, paragraph, quote, mood, image, or pretty excerpt.
- A valid beat can be paraphrased as: because X is true, a specific participant
  does or experiences Y, so now the reader knows Z.
- A beat must name its participants, actor, action, object, result, dependencies,
  and reader-new information.
- If a selected beat only makes sense because of an omitted setup, either merge
  that setup into the same beat, add the setup as an earlier beat, or drop the
  dependent beat.

Goal:
- Preserve narrative function, chronology, character relationships, and distinctive voice.
- Do not preserve every sentence as a panel.
- Do not preserve every scene as a panel. The graphic version should skip
  material that does not change what a character does, decides, discovers,
  wants, risks, or understands next.
- Do not preserve every source unit as caption text. A graphic novel should move
  faster than the abridged prose.
- Make the plot readable as comics by identifying concrete actions, time frames,
  physical anchors, and what can be compressed, implied, or omitted.
- Account for every source unit explicitly so omissions are intentional.

Disposition labels:
- keep_as_panel: source unit deserves direct visual staging.
- keep_as_caption: source wording or voice should remain, but it can ride over another action.
- merge_into_adjacent_beat: source unit is needed, but only as part of a larger beat.
- imply_visually: source unit should be communicated mostly through staging/design.
- omit: source unit can be dropped for graphic-novel pacing.

Rules:
- Preserve source order.
- Every source unit must appear exactly once in `unit_treatments`.
- Every source unit not marked `omit` must appear in exactly one `graphic_beats[].source_unit_ids`.
- `graphic_beats` must be in source order.
- Each `graphic_beats[].source_unit_ids` array must be strictly ascending.
- Across `graphic_beats`, source IDs must also be globally ascending after
  omitted units are removed. Never reach backward to an earlier source unit.
- Do not combine distant source units into one beat when intervening non-omitted
  units belong to a different beat; split them into separate ordered beats.
- Prefer fewer, stronger graphic beats over one beat per sentence.
- Treat the requested page and panel counts as a hard pacing budget. If a source
  unit would only produce atmosphere, essay, abstraction, repeated mood, or a
  non-causal stop along the way, prefer `omit`, `keep_as_caption`, or
  `merge_into_adjacent_beat` instead of creating a new beat.
- A source unit should become `keep_as_panel` only if it contains an observable
  action, decision, arrival, departure, encounter, discovery, confrontation, or
  other change that drives the next beat.
- Use `omit` for low-value texture, repetitive reflection, or detail that would
  slow the graphic novel without changing plot, character, orientation, or
  distinctive voice.
- Do not keep a source unit only because the prose is attractive. Keep it only
  if it serves the graphic adaptation.
- Keep narrator-frame material distinct from story-present chronology.
- For each beat, state the physical action first. Abstract meaning comes second.
- For geography, the physical action spine should be a character moving through
  or looking at a place. A map may be supporting storyboard guidance, but it
  should not be the main action spine unless no character vantage exists.
- Never use a map, diagram, label, signpost, aerial view, or other exposition
  device as the `physical_action_spine` when a character can physically look,
  walk, arrive, enter, leave, point, ride, write, read, or otherwise act.
- If a map would help the eventual page, mention it only as optional support in
  `storyboard_guidance`; keep the main beat grounded in character action.
- Inanimate objects can never drive the plot. A train, map, house, book, sun,
  camera move, label, weather effect, or landscape may be a prop, setting, or
  visual support, but never the actor of the beat.
- Every graphic beat must have a visible living character, narrator, or
  role-identifiable person as `driver_character`. For reflective passages, the
  driver is usually the narrator: writing, remembering, looking, walking,
  arriving, deciding, reading, or explaining.
- `physical_action_spine` must begin from what that character does or
  experiences, not what an object or camera does.
- A montage is not a plot driver. If a montage is useful, the action spine must
  still begin with the character's action or experience; put montage details in
  `storyboard_guidance`.
- Likewise, vignettes, insets, timelines, transitions, and sequences are layout
  methods, not plot drivers.
- Be source-grounded about visual content. `visual_anchor` and
  `storyboard_guidance` may include only people, places, props, animals,
  vehicles, weather, and actions that are physically present in the assigned
  source units or are necessary period/setting defaults.
- Artistic style may be expressive, simplified, or non-photorealistic. Scenery
  may be simplified for clarity. But stylization must not add new narrative
  content: no unsupported objects, animals, events, relationships, locations, or
  motifs.
- Do not turn abstract mentions, comparisons, themes, book-title concepts, or
  future motifs into visible imagery. Include a creature, object, emblem, place,
  or recurring visual motif only when the assigned source units place that
  visible thing in the scene.
- If a source unit is reflective or essayistic but worth keeping, stage the
  narrator's literal action or state (walking, writing, deciding, entering,
  reading, remembering) and put the abstract content in a short caption
  candidate. Do not stage a visual metaphor that adds unsupported content for
  the abstraction.
- If a source unit is omitted, give a concrete reason such as `repetitive_reflection`,
  `rhetorical_texture`, `already_implied`, `low_plot_value`, or `pace_cost_too_high`.
- If exact source wording should survive, put it in `caption_candidates`. Be
  selective; do not include a caption candidate for every non-omitted source unit.
- Do not invent plot events, new relationships, or unearned explanations.
- Do not decide page layouts here. Give storyboard guidance, not panels.
- Select beats by story necessity, not literary salience.
- Prefer story operations that establish orientation, entrances, relationships,
  cause/effect turns, dialogue setup/payoff pairs, decisions, revelations, and
  reactions.
- Deprioritize decorative prose, repeated atmosphere, abstract reflection, and
  literary turns that require missing prose context.
- Do not keep a payoff unless its required setup is in the same beat or an
  earlier selected beat.
- Do not keep a response line unless the line it responds to is present in the
  same beat or an earlier selected beat.
- Do not keep an abstract causal phrase such as "therefore", "evidently",
  "before I grasped her meaning", "after that", "it", "that", or "them" unless
  the antecedent is explicit in the beat or a previous selected beat.
- `depends_on` must list only earlier beat IDs. Use it for setup required to
  understand this beat, not for vague thematic relation.
- `enables` may list later beat IDs when this beat sets up a later payoff. Use
  an empty array if the later beat ID is not yet obvious.
- If an event is caused by an object, sound, weather, machine, place, or
  off-panel person, rewrite the beat around a visible character's reaction,
  choice, movement, refusal, discovery, or changed understanding.
- If a source unit moves characters into separate locations, rooms, groups, or
  pairings, preserve all resulting groups in `required_context`.
- `reference_dependencies` must name the specific prior facts needed to
  understand the beat. Use an empty array only when the beat is self-contained.
- Do not put maps, diagrams, timelines, labels, signs, aerial exposition, or
  other explanation devices in `required_visuals`. For geography beats, use a
  character-vantage visual.
- Do not infer future plot facts beyond the assigned source units.

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
  "pacing_strategy": {
    "summary": string,
    "target_reader_experience": string,
    "compression_ratio": "light" | "moderate" | "aggressive",
    "main_risks": [string]
  },
  "time_frames": [
    {
      "id": string,
      "label": string,
      "chronological_position": string,
      "reader_cue": string,
      "visual_cue": string
    }
  ],
  "unit_treatments": [
    {
      "source_unit_id": number,
      "disposition": "keep_as_panel" | "keep_as_caption" | "merge_into_adjacent_beat" | "imply_visually" | "omit",
      "time_frame": string,
      "subject": string,
      "narrative_function": string,
      "preservation_reason": string,
      "omit_or_compress_reason": string
    }
  ],
  "graphic_beats": [
    {
      "beat_id": string,
      "source_unit_ids": [number],
      "beat_type": "orientation" | "entrance" | "relationship" | "action" | "dialogue_exchange" | "revelation" | "decision" | "reaction" | "transition" | "setup" | "payoff",
      "time_frame": string,
      "scene": string,
      "time": string,
      "participants": [string],
      "subject": string,
      "driver_character": string,
      "actor": string,
      "action": string,
      "object": string,
      "result": string,
      "reader_new_info": string,
      "depends_on": [string],
      "enables": [string],
      "required_context": [string],
      "reference_dependencies": [string],
      "character_goal_or_state_change": string,
      "physical_action_spine": string,
      "narrative_function": string,
      "essential_facts": [string],
      "character_relationships": [string],
      "setting_or_orientation": string,
      "caption_candidates": [string],
      "visual_anchor": string,
      "required_visuals": [string],
      "forbidden_visuals": [string],
      "visualizable": boolean,
      "importance": "high" | "medium" | "low",
      "visual_evidence": [string],
      "compression_guidance": string,
      "storyboard_guidance": string,
      "pacing_priority": "high" | "medium" | "low"
    }
  ],
  "omitted_units": [
    {
      "source_unit_id": number,
      "reason": string,
      "safe_because": string
    }
  ],
  "continuity_requirements": [
    {
      "type": "character" | "place" | "time_frame" | "object" | "theme",
      "name": string,
      "requirement": string
    }
  ],
  "storyboard_instructions": [string]
}
