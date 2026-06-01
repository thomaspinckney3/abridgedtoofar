Review one clean graphic-novel image. It may be a full composed page or a
single panel crop. The image has art only; it does not yet contain captions,
speech balloons, or thought bubbles.

Your job is to locate the visual anchor for each text item that needs a
speaker tail:

- `speech`: locate the speaker's mouth point. If the mouth is obscured, use the
  center of the lower face where a speech tail should point.
- `thought`: locate the character's head or temple point where a thought-bubble
  trail should point.

Also locate a separate `tail_target_point`. This is where the rendered balloon
tail should end. It should be slightly offset from the mouth/head toward the
planned balloon zone, usually on the edge of the lower face or just outside the
lips. Do not put the tail target on the center of the mouth; a speech tail
should point to the speaker without stabbing into the mouth.

Use the supplied image contract to keep each target in the right panel or
single-panel image. Use speaker names, speaker_region, and speaker_visual_hint
to identify the right person. Do not choose a different character just because
they are nearer the planned balloon zone.

The image may include a colored coordinate grid and small numeric edge labels.
Those marks are a temporary detection aid, not part of the artwork. Use the
grid to make coordinates precise, but ignore it as story content.

If the named speaker is not visible, ambiguous, or too cropped to anchor
reliably, set `visible` to false and confidence at or below 0.40. Do not invent
coordinates when the speaker cannot be identified.

Image contract:
{
  "title": "Moby-Dick",
  "source_chapter": "Chapter 3: The Spouter-Inn",
  "image_mode": "panel",
  "coordinate_grid": "visible, every 0.1 in x and y, for detection only",
  "page_number": 1,
  "panel_number": 5,
  "image_size": {
    "width": 1024,
    "height": 1536
  },
  "targets": [
    {
      "panel_number": 5,
      "text_index": 0,
      "kind": "speech",
      "speaker": "Peter Coffin",
      "text": "With heads, to be sure.",
      "speaker_region": "right",
      "speaker_visual_hint": "lean older landlord in cap and waistcoat, shrugging",
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
      "tail_target_point": {"x": number, "y": number} | null,
      "tail_target_point_ratio": {"x": number, "y": number} | null,
      "face_box": {"x1": number, "y1": number, "x2": number, "y2": number} | null,
      "evidence": string,
      "reason": string
    }
  ]
}

Coordinate rules:

- In `image_mode: "page"`, `mouth_point`, `tail_target_point`, and `face_box`
  are absolute pixel coordinates on the full page image. The ratio fields are
  normalized within that target panel's page box.
- In `image_mode: "panel"`, `mouth_point`, `tail_target_point`, and `face_box`
  are absolute pixel coordinates on the single panel image. The ratio fields
  are normalized within the single panel image.
- Coordinates must be inside the target panel or panel image. If `visible` is
  false, use null for the coordinate fields.