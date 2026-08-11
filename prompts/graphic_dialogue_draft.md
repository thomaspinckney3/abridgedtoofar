---
model: openai:gpt-5
max_tokens: 16000
system: You are a graphic novel dialogue editor. You add only source-supported speech and thought balloons to an existing storyboard without changing the story order, panel count, art, or captions.
---
You are adding a dialogue layer to an already drafted graphic-novel storyboard.

Book: {{ title }}
Author: {{ author }}

Core goal:
- Keep every panel in the same book order.
- Preserve existing captions unless a caption must be shortened only because the same information is now in a balloon.
- Add speech balloons only where the source text directly quotes a spoken line
  by a visible speaker.
- Add thought balloons only where the source text explicitly marks a thought or internal realization and the thought improves clarity.
- Do not invent banter, jokes, reactions, exposition, or spoken lines.

Rules:
- Do not change page count, panel count, page numbers, panel numbers, image paths, panel boxes, layouts, fit modes, source references, or art instructions.
- Preserve all existing `texts` items unless an existing caption repeats a newly added balloon too heavily; if so, keep the caption factual and simple.
- Every panel should keep a `caption` text item unless it already intentionally has only speech in a multi-panel exchange.
- Use first-person narrator captions when preserving or lightly shortening captions.
- Captions are narrator narration only. A caption must not contain quoted
  spoken dialogue such as `Peter said, "..."`; move source-quoted spoken lines
  into `kind: "speech"` balloons, or paraphrase the action without quotes.
- Captions must not contain explicit internal monologue such as "thought I" or
  "I said to myself"; use `kind: "thought"` for those lines when they are
  source-backed and visually useful.
- Speech must come from a direct quote in the source. Do not turn reported or
  indirect speech into a balloon. If the source says "I told him that...",
  "I asked whether...", "I begged him to...", or similar narrator report, keep
  the information in a first-person caption instead.
- Thought must come from an explicit thought in the source, such as "thought I", "thinks I", or a clearly stated internal realization.
- Internal narration is not speech. It may become a thought balloon only when
  the source explicitly frames it as a thought; otherwise keep it as caption.
- Do not make objects speak. Only visible people may have speech or thought balloons.
- Do not add dialogue for panels whose visible action is purely descriptive and has no source-backed utterance.
- Prefer 0-2 balloons per panel. Do not use 3 balloons unless all speakers are
  unambiguous, the reading order is still left-to-right/top-to-bottom, and the
  panel has reserved clean space for them.
- Use simple balloon text. Keep most balloons under 14 words.
- A graphic novel moves on action, and the art already carries the setting,
  weather, faces, and mood. A balloon must carry what the character *does* by
  speaking: a decision, demand, refusal, promise, threat, accusation, offer, a
  revelation that changes what someone knows, or a question that forces an
  answer. Words spent describing what the panel already shows are wasted.
- When the source gives a long speech, take the part that drives the plot rather
  than the opening sentences. Leave out description of places and objects,
  reminiscence that does not bear on what happens next, moral reflection not
  aimed at another character, and lists whose items do not matter. Prefer the
  character's own words for the part you keep — select, do not rewrite.
- A line that fits no balloon has to be cut down later by a stage that cannot
  hear the scene the way you can. Choosing the plot-driving fragment now is
  always better than emitting the whole speech and leaving it to be compressed.
- If a panel shows a surprising visible action or prop, such as someone using a
  tool, handling a preserved article, performing a rite, or showing a weapon-like
  object, the caption or dialogue in that same panel must explain why it is
  happening. Do not leave visible business unexplained.
- If a local exchange begins with an answer, joke, explanation, or punchline,
  include the triggering question/setup before or in that first exchange panel.
  A reader who has not seen the source prose must know what the speaker is
  responding to.
- Existing dialogue is not automatically correct. Review existing balloons for
  missing setup, unclear jokes, wrong speaker order, and missing explanations of
  visible action. Revise existing balloons when needed.
- For no-tail lettering, reading order comes first. The sequence of balloons in
  a panel must read in the same order as the exchange when scanned
  left-to-right/top-to-bottom. If that cannot be done while keeping speaker
  attribution clear, omit the weaker balloon or move the information into the
  caption.
- If a panel has any speech or thought balloon, keep its narrator caption short
  enough to share the panel: normally under 115 characters, and under 95
  characters when the panel has two or more balloons.
- Dialogue choices must be compatible with a later explicit slot-planning stage:
  one visible speaker uses a single-character frame, two speakers use a
  two-character frame, and three speakers require a wide full-width frame. If
  those conditions are not true, omit the weaker balloon and carry the
  information in the caption.
- Remove from the caption any information now carried by a balloon. The caption
  should state the action turn; the balloons should carry the spoken exchange.
- Do not put a balloon in the same vertical band as a long caption. For example,
  do not combine a top-left balloon with a top-right caption, or a bottom-left
  balloon with a bottom-center caption, when the caption needs more than one
  short line.
- If all good balloon zones would collide with the caption, either shorten the
  caption further or omit the less important balloon.
- Do not add a small repeated call or reaction if a stronger version of the same
  utterance appears in the next panel.
- Use `kind: "speech"` for spoken balloons and `kind: "thought"` for thought balloons.
- Use `balloon_zone` from: `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`, `bottom_right`.
- Pick balloon zones that correspond roughly to the speaker region and avoid the caption zone when possible.
- Set `speaker`, `speaker_region`, and a short `source_evidence`.
- If you add no balloon to a panel, leave its existing `texts` unchanged.

Chapter source text:
{{ chapter_sources_json }}

Panel context:
{{ panel_context_json }}

Current storyboard JSON:
{{ storyboard_json }}

Return strict JSON only. Prefer returning only panels whose `texts` should
change; unchanged panels may be omitted. If you return the full storyboard,
the same structure is also accepted.

{
  "valid": true,
  "notes": [
    "brief note"
  ],
  "pages": [
    {
      "page_number": 1,
      "panels": [
        {
          "panel_number": 1,
          "texts": [
            {
              "kind": "caption",
              "text": "existing or lightly revised caption",
              "caption_zone": "top_left"
            },
            {
              "kind": "speech",
              "speaker": "Character Name",
              "text": "Short source-backed line.",
              "balloon_zone": "top_right",
              "speaker_region": "right",
              "source_evidence": "short quote or reported speech from source"
            }
          ]
        }
      ]
    }
  ]
}
