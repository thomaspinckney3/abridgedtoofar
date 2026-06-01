Create a graphic-novel action spine for one chapter.

Book: Moby-Dick; or, The Whale
Author: Herman Melville
Chapter: 4. The Counterpane
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
CHAPTER 4. The Counterpane.

Upon waking next morning about daylight, I found Queequeg’s arm thrown
over me in the most loving and affectionate manner. You had almost
thought I had been his wife. The counterpane was of patchwork, full of
odd little parti-coloured squares and triangles; and this arm of his
tattooed all over with an interminable Cretan labyrinth of a figure, no
two parts of which were of one precise shade—owing I suppose to his
keeping his arm at sea unmethodically in sun and shade, his shirt
sleeves irregularly rolled up at various times—this same arm of his, I
say, looked for all the world like a strip of that same patchwork
quilt. Indeed, partly lying on it as the arm did when I first awoke, I
could hardly tell it from the quilt, they so blended their hues
together; and it was only by the sense of weight and pressure that I
could tell that Queequeg was hugging me.

My sensations were strange. Let me try to explain them. When I was a
child, I well remember a somewhat similar circumstance that befell me;
whether it was a reality or a dream, I never could entirely settle. The
circumstance was this. I had been cutting up some caper or other—I
think it was trying to crawl up the chimney, as I had seen a little
sweep do a few days previous; and my stepmother who, somehow or other,
was all the time whipping me, or sending me to bed supperless,—my
mother dragged me by the legs out of the chimney and packed me off to
bed, though it was only two o’clock in the afternoon of the 21st June,
the longest day in the year in our hemisphere. I felt dreadfully. But
there was no help for it, so up stairs I went to my little room in the
third floor, undressed myself as slowly as possible so as to kill time,
and with a bitter sigh got between the sheets.

I lay there dismally calculating that sixteen entire hours must elapse
before I could hope for a resurrection. Sixteen hours in bed! the small
of my back ached to think of it. And it was so light too; the sun
shining in at the window, and a great rattling of coaches in the
streets, and the sound of gay voices all over the house. I felt worse
and worse—at last I got up, dressed, and softly going down in my
stockinged feet, sought out my stepmother, and suddenly threw myself at
her feet, beseeching her as a particular favour to give me a good
slippering for my misbehaviour; anything indeed but condemning me to
lie abed such an unendurable length of time. But she was the best and
most conscientious of stepmothers, and back I had to go to my room. For
several hours I lay there broad awake, feeling a great deal worse than
I have ever done since, even from the greatest subsequent misfortunes.
At last I must have fallen into a troubled nightmare of a doze; and
slowly waking from it—half steeped in dreams—I opened my eyes, and the
before sun-lit room was now wrapped in outer darkness. Instantly I felt
a shock running through all my frame; nothing was to be seen, and
nothing was to be heard; but a supernatural hand seemed placed in mine.
My arm hung over the counterpane, and the nameless, unimaginable,
silent form or phantom, to which the hand belonged, seemed closely
seated by my bed-side. For what seemed ages piled on ages, I lay there,
frozen with the most awful fears, not daring to drag away my hand; yet
ever thinking that if I could but stir it one single inch, the horrid
spell would be broken. I knew not how this consciousness at last glided
away from me; but waking in the morning, I shudderingly remembered it
all, and for days and weeks and months afterwards I lost myself in
confounding attempts to explain the mystery. Nay, to this very hour, I
often puzzle myself with it.

Now, take away the awful fear, and my sensations at feeling the
supernatural hand in mine were very similar, in their strangeness, to
those which I experienced on waking up and seeing Queequeg’s pagan arm
thrown round me. But at length all the past night’s events soberly
recurred, one by one, in fixed reality, and then I lay only alive to
the comical predicament. For though I tried to move his arm—unlock his
bridegroom clasp—yet, sleeping as he was, he still hugged me tightly,
as though naught but death should part us twain. I now strove to rouse
him—“Queequeg!”—but his only answer was a snore. I then rolled over, my
neck feeling as if it were in a horse-collar; and suddenly felt a
slight scratch. Throwing aside the counterpane, there lay the tomahawk
sleeping by the savage’s side, as if it were a hatchet-faced baby. A
pretty pickle, truly, thought I; abed here in a strange house in the
broad day, with a cannibal and a tomahawk! “Queequeg!—in the name of
goodness, Queequeg, wake!” At length, by dint of much wriggling, and
loud and incessant expostulations upon the unbecomingness of his
hugging a fellow male in that matrimonial sort of style, I succeeded in
extracting a grunt; and presently, he drew back his arm, shook himself
all over like a Newfoundland dog just from the water, and sat up in
bed, stiff as a pike-staff, looking at me, and rubbing his eyes as if
he did not altogether remember how I came to be there, though a dim
consciousness of knowing something about me seemed slowly dawning over
him. Meanwhile, I lay quietly eyeing him, having no serious misgivings
now, and bent upon narrowly observing so curious a creature. When, at
last, his mind seemed made up touching the character of his bedfellow,
and he became, as it were, reconciled to the fact; he jumped out upon
the floor, and by certain signs and sounds gave me to understand that,
if it pleased me, he would dress first and then leave me to dress
afterwards, leaving the whole apartment to myself. Thinks I, Queequeg,
under the circumstances, this is a very civilized overture; but, the
truth is, these savages have an innate sense of delicacy, say what you
will; it is marvellous how essentially polite they are. I pay this
particular compliment to Queequeg, because he treated me with so much
civility and consideration, while I was guilty of great rudeness;
staring at him from the bed, and watching all his toilette motions; for
the time my curiosity getting the better of my breeding. Nevertheless,
a man like Queequeg you don’t see every day, he and his ways were well
worth unusual regarding.

He commenced dressing at top by donning his beaver hat, a very tall
one, by the by, and then—still minus his trowsers—he hunted up his
boots. What under the heavens he did it for, I cannot tell, but his
next movement was to crush himself—boots in hand, and hat on—under the
bed; when, from sundry violent gaspings and strainings, I inferred he
was hard at work booting himself; though by no law of propriety that I
ever heard of, is any man required to be private when putting on his
boots. But Queequeg, do you see, was a creature in the transition
stage—neither caterpillar nor butterfly. He was just enough civilized
to show off his outlandishness in the strangest possible manners. His
education was not yet completed. He was an undergraduate. If he had not
been a small degree civilized, he very probably would not have troubled
himself with boots at all; but then, if he had not been still a savage,
he never would have dreamt of getting under the bed to put them on. At
last, he emerged with his hat very much dented and crushed down over
his eyes, and began creaking and limping about the room, as if, not
being much accustomed to boots, his pair of damp, wrinkled cowhide
ones—probably not made to order either—rather pinched and tormented him
at the first go off of a bitter cold morning.

Seeing, now, that there were no curtains to the window, and that the
street being very narrow, the house opposite commanded a plain view
into the room, and observing more and more the indecorous figure that
Queequeg made, staving about with little else but his hat and boots on;
I begged him as well as I could, to accelerate his toilet somewhat, and
particularly to get into his pantaloons as soon as possible. He
complied, and then proceeded to wash himself. At that time in the
morning any Christian would have washed his face; but Queequeg, to my
amazement, contented himself with restricting his ablutions to his
chest, arms, and hands. He then donned his waistcoat, and taking up a
piece of hard soap on the wash-stand centre table, dipped it into water
and commenced lathering his face. I was watching to see where he kept
his razor, when lo and behold, he takes the harpoon from the bed
corner, slips out the long wooden stock, unsheathes the head, whets it
a little on his boot, and striding up to the bit of mirror against the
wall, begins a vigorous scraping, or rather harpooning of his cheeks.
Thinks I, Queequeg, this is using Rogers’s best cutlery with a
vengeance. Afterwards I wondered the less at this operation when I came
to know of what fine steel the head of a harpoon is made, and how
exceedingly sharp the long straight edges are always kept.

The rest of his toilet was soon achieved, and he proudly marched out of
the room, wrapped up in his great pilot monkey jacket, and sporting his
harpoon like a marshal’s baton.

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