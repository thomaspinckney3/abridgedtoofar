Review one clean graphic-novel page image. The image has panel art only; it
does not yet contain captions, speech balloons, or thought bubbles.

Your job is to locate the actual visual anchor for each text item that needs a
speaker tail:

- `speech`: locate the speaker's mouth point. If the mouth is obscured, use the
  center of the lower face where a speech tail should point.
- `thought`: locate the character's head or temple point where a thought-bubble
  trail should point.

Use the supplied panel boxes to keep each target inside its own panel. Use
speaker names, speaker_region, and speaker_visual_hint to identify the right
person. Do not choose a different character just because they are nearer the
planned balloon zone.

If the named speaker is not visible, ambiguous, or too cropped to anchor
reliably, set `visible` to false and confidence at or below 0.40. Do not invent
coordinates when the speaker cannot be identified.

Page contract:
{
  "title": "Moby-Dick",
  "source_chapter": "Chapter 3: The Spouter-Inn",
  "page_number": 1,
  "page_size": {
    "width": 1536,
    "height": 2048
  },
  "panel_boxes": [
    {
      "panel_number": 1,
      "x1": 24,
      "y1": 24,
      "x2": 1512,
      "y2": 444
    },
    {
      "panel_number": 2,
      "x1": 24,
      "y1": 462,
      "x2": 759,
      "y2": 882
    },
    {
      "panel_number": 3,
      "x1": 777,
      "y1": 462,
      "x2": 1512,
      "y2": 882
    },
    {
      "panel_number": 4,
      "x1": 24,
      "y1": 900,
      "x2": 759,
      "y2": 1320
    },
    {
      "panel_number": 5,
      "x1": 777,
      "y1": 900,
      "x2": 1512,
      "y2": 1320
    },
    {
      "panel_number": 6,
      "x1": 24,
      "y1": 1338,
      "x2": 1512,
      "y2": 2024
    }
  ],
  "targets": [
    {
      "panel_number": 1,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Peter Coffin",
      "text": "He went out peddling. Maybe he can't sell his head.",
      "speaker_region": "right",
      "speaker_visual_hint": "lean older landlord on the right, wearing a cap and waistcoat",
      "balloon_zone": "top_right"
    },
    {
      "panel_number": 2,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Ishmael",
      "text": "Peddling his head around town?",
      "speaker_region": "center",
      "speaker_visual_hint": "young sailor in a dark jacket",
      "balloon_zone": "top_left"
    },
    {
      "panel_number": 3,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Peter Coffin",
      "text": "That's precisely it. The market's overstocked.",
      "speaker_region": "right",
      "speaker_visual_hint": "lean older landlord in cap and waistcoat, whittling",
      "balloon_zone": "top_right"
    },
    {
      "panel_number": 4,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Ishmael",
      "text": "With what?",
      "speaker_region": "center",
      "speaker_visual_hint": "young sailor in a dark jacket",
      "balloon_zone": "top_left"
    },
    {
      "panel_number": 5,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Peter Coffin",
      "text": "With heads, to be sure.",
      "speaker_region": "right",
      "speaker_visual_hint": "lean older landlord in cap and waistcoat, shrugging",
      "balloon_zone": "top_right"
    },
    {
      "panel_number": 6,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Peter Coffin",
      "text": "Embalmed New Zealand heads. He's sold all but one.",
      "speaker_region": "right",
      "speaker_visual_hint": "lean older landlord in cap and waistcoat leaning toward Ishmael",
      "balloon_zone": "top_right"
    }
  ]
}

Return strict JSON only, with this exact shape:

{
  "page_number": number,
  "anchors": [
    {
      "panel_number": number,
      "text_index": number,
      "kind": "speech" | "thought",
      "speaker": string,
      "text": string,
      "visible": boolean,
      "confidence": number,
      "mouth_point": {"x": number, "y": number} | null,
      "mouth_point_ratio": {"x": number, "y": number} | null,
      "face_box": {"x1": number, "y1": number, "x2": number, "y2": number} | null,
      "evidence": string,
      "reason": string
    }
  ]
}

Coordinate rules:

- `mouth_point` and `face_box` are absolute pixel coordinates on the full page
  image.
- `mouth_point_ratio` is normalized within that panel's box: x=0 at the panel's
  left edge, x=1 at the right edge, y=0 at the top, y=1 at the bottom.
- Coordinates must be inside the target panel. If `visible` is false, use null
  for the coordinate fields.