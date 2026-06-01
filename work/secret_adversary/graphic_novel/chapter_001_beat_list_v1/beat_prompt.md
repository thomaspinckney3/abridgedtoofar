You are creating a beat inventory from an abridged novel chapter.

This is NOT a page storyboard, NOT a caption draft, and NOT image prompts.
This stage comes before pacing and panel selection.

Book: The Secret Adversary
Author: Agatha Christie
Excerpt word range: 395-1362

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

[1] words 1-3
"Tommy, old thing!"


[2] words 4-6
"Tuppence, old bean!"


[3] words 7-35
The two young people greeted each other affectionately, momentarily blocking the Dover Street Tube exit. The adjective "old" was misleading: their united ages would certainly not have totalled forty-five.


[4] words 36-52
"Not seen you for simply centuries," said the young man. "Come and chew a bun with me."


[5] words 53-91
The girl assented, and they walked down Dover Street towards Piccadilly. The very faint anxiety underlying his tone did not escape the astute ears of Miss Prudence Cowley, known to her intimate friends for some mysterious reason as "Tuppence."


[6] words 92-94
"Tommy, you're stony!"


[7] words 95-102
"Not a bit of it. Rolling in cash."


[8] words 103-108
"You always were a shocking liar."


[9] words 109-125
Tommy chuckled. "Demobbed like everything else, I suppose. Two months ago. Gratuity? Spent. The cost of living—"


[10] words 126-153
"My dear child, there is nothing I do *not* know about the cost of living. Here we are at Lyons', and we will each pay for our own."


[11] words 154-186
They found a table. "Funny scraps one does overhear," murmured Tommy. "I passed two Johnnies in the street to-day talking about some one called Jane Finn. Did you ever hear such a name?"


[12] words 187-256
Tommy was pleasantly ugly, with a shock of slicked-back red hair—nondescript, yet unmistakably the face of a gentleman and a sportsman. Tuppence had no claim to beauty, but there was character and charm in the elfin lines of her little face, with its determined chin and large, wide-apart grey eyes. She wore a small bright green toque over her bobbed black hair; her appearance was a valiant attempt at smartness.


[13] words 257-280
"Now then," said Tommy, taking a large bite of bun. "Let's get up-to-date. I haven't seen you since that time in hospital in 1916."


[14] words 281-364
"Very well." Tuppence helped herself liberally to buttered toast and gave the abridged biography of Miss Prudence Cowley, fifth daughter of Archdeacon Cowley of Little Missendell, Suffolk: ward duties, plate-washing, peeling potatoes, sweeping out wards (where she found a friend of her childhood in Lieutenant Thomas Beresford—bow, Tommy!), then a trade van, a motor-lorry, and a young general. "After that, a Government office, and several enjoyable tea parties—until I was combed out at last. Since then I've been looking for a job. Now—your turn."


[15] words 365-409
"There's less variety in mine. France, Mesopotamia, wounded again, hospital out there, Egypt till the Armistice, finally demobbed. For ten long, weary months I've been job hunting. There aren't any jobs. And, if there were, they wouldn't give 'em to me. What good am I?"


[16] words 410-411
"Rich relations?"


[17] words 412-433
"An old uncle who's more or less rolling. Wanted to adopt me once. I refused—because of the mater. Old boy hated her."


[18] words 434-441
"Your mother's dead, isn't she?" said Tuppence gently.


[19] words 442-453
Tommy nodded. Tuppence's grey eyes looked misty. "You're a good sort, Tommy."


[20] words 454-462
"Rot! Well, that's my position. I'm just about desperate."


[21] words 463-515
"So am I. I shall have to go home. Father's a dear, but you've no idea how I worry him—short skirts and smoking are immoral, in his early Victorian view. He just heaved a sigh of relief when the war took me off. Seven of us at home. All housework and mothers' meetings!"


[22] words 516-587
She burst out: "Money, money, money! I think about money morning, noon and night. There are only three ways to get it: to be left it, to marry it, or to make it. The first is ruled out—my relatives are in homes for decayed gentlewomen. Marriage is my best chance. I made up my mind to marry money when I was quite young. Any thinking girl would. I'm not sentimental, you know."


[23] words 588-601
"No one would ever think of sentiment in connection with you," said Tommy hastily.


[24] words 602-632
"That's not very polite. Well, there it is—I'm ready and willing, but I never meet any rich men. All the boys I know are about as hard up as I am."


[25] words 633-634
"Same here."


[26] words 635-648
"We've tried the orthodox ways. Suppose we try the unorthodox. Tommy, let's be adventurers!"


[27] words 649-653
"Certainly. How do we begin?"


[28] words 654-668
"If we could make ourselves known, people might hire us to commit crimes for them."


[29] words 669-673
"Delightful—coming from a clergyman's daughter!"


[30] words 674-701
"The moral guilt would be theirs—not mine. Let's form a—joint venture! It struck me as such a romantic phrase. It's got an Elizabethan flavour about it—galleons and doubloons."


[31] words 702-714
"Trading under the name of the Young Adventurers, Ltd.? Is that your idea?"


[32] words 715-723
"Don't laugh. Advertisement! Have you got paper and pencil?"


[33] words 724-735
Tommy handed over a rather shabby green notebook, and Tuppence wrote busily.


[34] words 736-756
"How's this? 'Two young adventurers for hire. Willing to do anything, go anywhere. Pay must be good. No unreasonable offer refused.'"


[35] words 757-769
"It would strike me as either a hoax or written by a lunatic."


[36] words 770-803
"It's not half so insane as a thing I read this morning beginning 'Petunia' and signed 'Best Boy.'" She tore out the leaf and handed it to him. "There you are. *Times*, I think."


[37] words 804-828
Tommy was holding the paper thoughtfully. His face burned a deeper red. "Shall we really try it, Tuppence? Just for the fun of the thing?"


[38] words 829-855
"Tommy, you're a sport! Let's drink to success." She poured cold dregs of tea into the two cups. "Here's to our joint venture, and may it prosper!"


[39] words 856-861
"The Young Adventurers, Ltd.!" responded Tommy.


[40] words 862-882
They put down the cups and laughed rather uncertainly. Tuppence rose. "I must return to my palatial suite at the hostel."


[41] words 883-896
"Perhaps it is time I strolled round to the *Ritz*. Where shall we meet?"


[42] words 897-902
"Twelve o'clock to-morrow. Piccadilly Tube station."


[43] words 903-911
"My time is my own," replied Mr. Beresford magnificently.


[44] words 912-941
The two young people went off in opposite directions. Tuppence's hostel was situated in what was charitably called Southern Belgravia. For reasons of economy she did not take a bus.


[45] words 942-957
She was half-way across St. James's Park when a man's voice behind her made her start.


[46] words 958-968
"Excuse me. But may I speak to you for a moment?"



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