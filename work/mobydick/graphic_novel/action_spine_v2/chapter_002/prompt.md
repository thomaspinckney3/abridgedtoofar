Create a graphic-novel action spine for one chapter.

Book: Moby-Dick; or, The Whale
Author: Herman Melville
Chapter: 2. The Carpet-Bag
Requested frame range: 3-8

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
  For example, do not leave "selling his head" hanging; explain that the
  character was selling preserved heads or whatever the source actually means.
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
- Every image prompt must say "No readable text."
- Every frame must reserve one caption zone chosen from:
  `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`,
  `bottom_right`.

Chapter text:
CHAPTER 2. The Carpet-Bag.

I stuffed a shirt or two into my old carpet-bag, tucked it under my
arm, and started for Cape Horn and the Pacific. Quitting the good city
of old Manhatto, I duly arrived in New Bedford. It was a Saturday night
in December. Much was I disappointed upon learning that the little
packet for Nantucket had already sailed, and that no way of reaching
that place would offer, till the following Monday.

As most young candidates for the pains and penalties of whaling stop at
this same New Bedford, thence to embark on their voyage, it may as well
be related that I, for one, had no idea of so doing. For my mind was
made up to sail in no other than a Nantucket craft, because there was a
fine, boisterous something about everything connected with that famous
old island, which amazingly pleased me. Besides though New Bedford has
of late been gradually monopolising the business of whaling, and though
in this matter poor old Nantucket is now much behind her, yet Nantucket
was her great original—the Tyre of this Carthage;—the place where the
first dead American whale was stranded. Where else but from Nantucket
did those aboriginal whalemen, the Red-Men, first sally out in canoes
to give chase to the Leviathan? And where but from Nantucket, too, did
that first adventurous little sloop put forth, partly laden with
imported cobblestones—so goes the story—to throw at the whales, in
order to discover when they were nigh enough to risk a harpoon from the
bowsprit?

Now having a night, a day, and still another night following before me
in New Bedford, ere I could embark for my destined port, it became a
matter of concernment where I was to eat and sleep meanwhile. It was a
very dubious-looking, nay, a very dark and dismal night, bitingly cold
and cheerless. I knew no one in the place. With anxious grapnels I had
sounded my pocket, and only brought up a few pieces of silver,—So,
wherever you go, Ishmael, said I to myself, as I stood in the middle of
a dreary street shouldering my bag, and comparing the gloom towards the
north with the darkness towards the south—wherever in your wisdom you
may conclude to lodge for the night, my dear Ishmael, be sure to
inquire the price, and don’t be too particular.

With halting steps I paced the streets, and passed the sign of “The
Crossed Harpoons”—but it looked too expensive and jolly there. Further
on, from the bright red windows of the “Sword-Fish Inn,” there came
such fervent rays, that it seemed to have melted the packed snow and
ice from before the house, for everywhere else the congealed frost lay
ten inches thick in a hard, asphaltic pavement,—rather weary for me,
when I struck my foot against the flinty projections, because from
hard, remorseless service the soles of my boots were in a most
miserable plight. Too expensive and jolly, again thought I, pausing one
moment to watch the broad glare in the street, and hear the sounds of
the tinkling glasses within. But go on, Ishmael, said I at last; don’t
you hear? get away from before the door; your patched boots are
stopping the way. So on I went. I now by instinct followed the streets
that took me waterward, for there, doubtless, were the cheapest, if not
the cheeriest inns.

Such dreary streets! blocks of blackness, not houses, on either hand,
and here and there a candle, like a candle moving about in a tomb. At
this hour of the night, of the last day of the week, that quarter of
the town proved all but deserted. But presently I came to a smoky light
proceeding from a low, wide building, the door of which stood
invitingly open. It had a careless look, as if it were meant for the
uses of the public; so, entering, the first thing I did was to stumble
over an ash-box in the porch. Ha! thought I, ha, as the flying
particles almost choked me, are these ashes from that destroyed city,
Gomorrah? But “The Crossed Harpoons,” and “The Sword-Fish?”—this, then
must needs be the sign of “The Trap.” However, I picked myself up and
hearing a loud voice within, pushed on and opened a second, interior
door.

It seemed the great Black Parliament sitting in Tophet. A hundred black
faces turned round in their rows to peer; and beyond, a black Angel of
Doom was beating a book in a pulpit. It was a negro church; and the
preacher’s text was about the blackness of darkness, and the weeping
and wailing and teeth-gnashing there. Ha, Ishmael, muttered I, backing
out, Wretched entertainment at the sign of ‘The Trap!’

Moving on, I at last came to a dim sort of light not far from the
docks, and heard a forlorn creaking in the air; and looking up, saw a
swinging sign over the door with a white painting upon it, faintly
representing a tall straight jet of misty spray, and these words
underneath—“The Spouter Inn:—Peter Coffin.”

Coffin?—Spouter?—Rather ominous in that particular connexion, thought
I. But it is a common name in Nantucket, they say, and I suppose this
Peter here is an emigrant from there. As the light looked so dim, and
the place, for the time, looked quiet enough, and the dilapidated
little wooden house itself looked as if it might have been carted here
from the ruins of some burnt district, and as the swinging sign had a
poverty-stricken sort of creak to it, I thought that here was the very
spot for cheap lodgings, and the best of pea coffee.

It was a queer sort of place—a gable-ended old house, one side palsied
as it were, and leaning over sadly. It stood on a sharp bleak corner,
where that tempestuous wind Euroclydon kept up a worse howling than
ever it did about poor Paul’s tossed craft. Euroclydon, nevertheless,
is a mighty pleasant zephyr to any one in-doors, with his feet on the
hob quietly toasting for bed. “In judging of that tempestuous wind
called Euroclydon,” says an old writer—of whose works I possess the
only copy extant—“it maketh a marvellous difference, whether thou
lookest out at it from a glass window where the frost is all on the
outside, or whether thou observest it from that sashless window, where
the frost is on both sides, and of which the wight Death is the only
glazier.” True enough, thought I, as this passage occurred to my
mind—old black-letter, thou reasonest well. Yes, these eyes are
windows, and this body of mine is the house. What a pity they didn’t
stop up the chinks and the crannies though, and thrust in a little lint
here and there. But it’s too late to make any improvements now. The
universe is finished; the copestone is on, and the chips were carted
off a million years ago. Poor Lazarus there, chattering his teeth
against the curbstone for his pillow, and shaking off his tatters with
his shiverings, he might plug up both ears with rags, and put a
corn-cob into his mouth, and yet that would not keep out the
tempestuous Euroclydon. Euroclydon! says old Dives, in his red silken
wrapper—(he had a redder one afterwards) pooh, pooh! What a fine frosty
night; how Orion glitters; what northern lights! Let them talk of their
oriental summer climes of everlasting conservatories; give me the
privilege of making my own summer with my own coals.

But what thinks Lazarus? Can he warm his blue hands by holding them up
to the grand northern lights? Would not Lazarus rather be in Sumatra
than here? Would he not far rather lay him down lengthwise along the
line of the equator; yea, ye gods! go down to the fiery pit itself, in
order to keep out this frost?

Now, that Lazarus should lie stranded there on the curbstone before the
door of Dives, this is more wonderful than that an iceberg should be
moored to one of the Moluccas. Yet Dives himself, he too lives like a
Czar in an ice palace made of frozen sighs, and being a president of a
temperance society, he only drinks the tepid tears of orphans.

But no more of this blubbering now, we are going a-whaling, and there
is plenty of that yet to come. Let us scrape the ice from our frosted
feet, and see what sort of a place this “Spouter” may be.

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