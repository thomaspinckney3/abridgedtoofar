You are creating an intermediate graphic-novel plot version from an abridged novel excerpt.

This is NOT a page storyboard and NOT image prompts. It is the planning layer
between abridged prose and storyboard generation.

Book: The Great Gatsby
Author: F. Scott Fitzgerald
Excerpt word range: 2-4762
Downstream target pages: 12
Downstream target panels per page: 4

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
- Keep Gatsby-like narrator-frame material distinct from story-present chronology.
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
- Every graphic beat must have a living character or role-identifiable person
  as `driver_character`. For reflective passages, the driver is usually Nick as
  narrator: writing, remembering, looking, walking, arriving, deciding, reading,
  or explaining.
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
  future motifs into visible imagery. For example, do not add whale imagery just
  because the book is about whaling or a character thinks about whales; include
  a whale only when the assigned source units place a physical whale, whale
  image, or whale object in the scene.
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

Source units:

[1] words 2-24
In my younger and more vulnerable years my father gave me some advice that I've been turning over in my mind ever since.


[2] words 25-49
"Whenever you feel like criticizing anyone," he told me, "just remember that all the people in this world haven't had the advantages that you've had."


[3] words 50-253
He didn't say any more, but we've always been unusually communicative in a reserved way, and I understood that he meant a great deal more than that. In consequence, I'm inclined to reserve all judgements, a habit that has opened up many curious natures to me and also made me the victim of not a few veteran bores. The abnormal mind is quick to detect and attach itself to this quality when it appears in a normal person, and so it came about that in college I was unjustly accused of being a politician, because I was privy to the secret griefs of wild, unknown men. Most of the confidences were unsought—frequently I have feigned sleep, preoccupation, or a hostile levity when I realized by some unmistakable sign that an intimate revelation was quivering on the horizon; for the intimate revelations of young men, or at least the terms in which they express them, are usually plagiaristic and marred by obvious suppressions. Reserving judgements is a matter of infinite hope. I am still a little afraid of missing something if I forget that, as my father snobbishly suggested, and I snobbishly repeat, a sense of the fundamental decencies is parcelled out unequally at birth.


[4] words 254-493
And, after boasting this way of my tolerance, I come to the admission that it has a limit. Conduct may be founded on the hard rock or the wet marshes, but after a certain point I don't care what it's founded on. When I came back from the East last autumn I felt that I wanted the world to be in uniform and at a sort of moral attention forever; I wanted no more riotous excursions with privileged glimpses into the human heart. Only Gatsby, the man who gives his name to this book, was exempt from my reaction—Gatsby, who represented everything for which I have an unaffected scorn. If personality is an unbroken series of successful gestures, then there was something gorgeous about him, some heightened sensitivity to the promises of life, as if he were related to one of those intricate machines that register earthquakes ten thousand miles away. This responsiveness had nothing to do with that flabby impressionability which is dignified under the name of the "creative temperament"—it was an extraordinary gift for hope, a romantic readiness such as I have never found in any other person and which it is not likely I shall ever find again. No—Gatsby turned out all right at the end; it is what preyed on Gatsby, what foul dust floated in the wake of his dreams that temporarily closed out my interest in the abortive sorrows and short-winded elations of men.


[5] words 494-594
My family have been prominent, well-to-do people in this Middle Western city for three generations. I graduated from New Haven in 1915, and later took part in that delayed Teutonic migration known as the Great War. I enjoyed the counter-raid so thoroughly that I came back restless. Instead of being the warm centre of the world, the Middle West now seemed like the ragged edge of the universe—so I decided to go East and learn the bond business. Father agreed to finance me for a year, and after various delays I came East, permanently, I thought, in the spring of twenty-two.


[6] words 595-719
The practical thing was to find rooms in the city, but it was a warm season, and I had just left a country of wide lawns and friendly trees, so when a young man at the office suggested that we take a house together in a commuting town, it sounded like a great idea. He found the house, a weather-beaten cardboard bungalow at eighty a month, but at the last minute the firm ordered him to Washington, and I went out to the country alone. I had a dog—at least I had him for a few days until he ran away—and an old Dodge and a Finnish woman, who made my bed and cooked breakfast and muttered Finnish wisdom to herself over the electric stove.


[7] words 720-742
It was lonely for a day or so until one morning some man, more recently arrived than I, stopped me on the road.


[8] words 743-753
"How do you get to West Egg village?" he asked helplessly.


[9] words 754-786
I told him. And as I walked on I was lonely no longer. I was a guide, a pathfinder, an original settler. He had casually conferred on me the freedom of the neighbourhood.


[10] words 787-822
And so with the sunshine and the great bursts of leaves growing on the trees, just as things grow in fast movies, I had that familiar conviction that life was beginning over again with the summer.


[11] words 823-951
There was so much to read, for one thing, and so much fine health to be pulled down out of the young breath-giving air. I bought a dozen volumes on banking and credit and investment securities, and they stood on my shelf in red and gold like new money from the mint, promising to unfold the shining secrets that only Midas and Morgan and Maecenas knew. I was rather literary in college—one year I wrote a series of very solemn and obvious editorials for the Yale News—and now I was going to bring back all such things into my life and become again that most limited of all specialists, the "well-rounded man." This isn't just an epigram—life is much more successfully looked at from a single window, after all.


[12] words 952-1059
It was a matter of chance that I should have rented a house in one of the strangest communities in North America. It was on that slender riotous island which extends itself due east of New York—and where there are, among other natural curiosities, two unusual formations of land. Twenty miles from the city a pair of enormous eggs, identical in contour and separated only by a courtesy bay, jut out into the most domesticated body of salt water in the Western hemisphere, the great wet barnyard of Long Island Sound. To the wingless a more interesting phenomenon is their dissimilarity in every particular except shape and size.


[13] words 1060-1239
I lived at West Egg, the—well, the less fashionable of the two, though this is a most superficial tag to express the bizarre and not a little sinister contrast between them. My house was at the very tip of the egg, only fifty yards from the Sound, and squeezed between two huge places that rented for twelve or fifteen thousand a season. The one on my right was a colossal affair by any standard—it was a factual imitation of some Hôtel de Ville in Normandy, with a tower on one side, spanking new under a thin beard of raw ivy, and a marble swimming pool, and more than forty acres of lawn and garden. It was Gatsby's mansion. Or, rather, as I didn't know Mr. Gatsby, it was a mansion inhabited by a gentleman of that name. My own house was an eyesore, but it was a small eyesore, and it had been overlooked, so I had a view of the water, a partial view of my neighbour's lawn, and the consoling proximity of millionaires—all for eighty dollars a month.


[14] words 1240-1302
Across the courtesy bay the white palaces of fashionable East Egg glittered along the water, and the history of the summer really begins on the evening I drove over there to have dinner with the Tom Buchanans. Daisy was my second cousin once removed, and I'd known Tom in college. And just after the war I spent two days with them in Chicago.


[15] words 1303-1392
Her husband, among various physical accomplishments, had been one of the most powerful ends that ever played football at New Haven—a national figure in a way, one of those men who reach such an acute limited excellence at twenty-one that everything afterward savours of anticlimax. His family were enormously wealthy—even in college his freedom with money was a matter for reproach—but now he'd left Chicago and come East in a fashion that rather took your breath away: for instance, he'd brought down a string of polo ponies from Lake Forest.


[16] words 1393-1523
And so it happened that on a warm windy evening I drove over to East Egg to see two old friends whom I scarcely knew at all. Their house was even more elaborate than I expected, a cheerful red-and-white Georgian Colonial mansion, overlooking the bay. The lawn started at the beach and ran towards the front door for a quarter of a mile, jumping over sundials and brick walks and burning gardens—finally when it reached the house drifting up the side in bright vines as though from the momentum of its run. The front was broken by a line of French windows, glowing now with reflected gold and wide open to the warm windy afternoon, and Tom Buchanan in riding clothes was standing with his legs apart on the front porch.


[17] words 1524-1626
He had changed since his New Haven years. Now he was a sturdy straw-haired man of thirty, with a rather hard mouth and a supercilious manner. Two shining arrogant eyes had established dominance over his face and gave him the appearance of always leaning aggressively forward. Not even the effeminate swank of his riding clothes could hide the enormous power of that body—he seemed to fill those glistening boots until he strained the top lacing, and you could see a great pack of muscle shifting when his shoulder moved under his thin coat. It was a body capable of enormous leverage—a cruel body.


[18] words 1627-1655
His speaking voice, a gruff husky tenor, added to the impression of fractiousness he conveyed. There was a touch of paternal contempt in it, even toward people he liked.


[19] words 1656-1668
"I've got a nice place here," he said, his eyes flashing about restlessly.


[20] words 1669-1708
Turning me around by one arm, he moved a broad flat hand along the front vista, including in its sweep a sunken Italian garden, a half acre of deep, pungent roses, and a snub-nosed motorboat that bumped the tide offshore.


[21] words 1709-1718
"It belonged to Demaine, the oil man. We'll go inside."


[22] words 1719-1809
We walked through a high hallway into a bright rosy-coloured space, fragilely bound into the house by French windows at either end. The windows were ajar and gleaming white against the fresh grass outside that seemed to grow a little way into the house. A breeze blew through the room, blew curtains in at one end and out the other like pale flags, twisting them up toward the frosted wedding-cake of the ceiling, and then rippled over the wine-coloured rug, making a shadow on it as wind does on the sea.


[23] words 1810-1900
The only completely stationary object in the room was an enormous couch on which two young women were buoyed up as though upon an anchored balloon. They were both in white, and their dresses were rippling and fluttering as if they had just been blown back in after a short flight around the house. Then there was a boom as Tom Buchanan shut the rear windows and the caught wind died out about the room, and the curtains and the rugs and the two young women ballooned slowly to the floor.


[24] words 1901-1944
The younger of the two was a stranger to me. She was extended full length at her end of the divan, completely motionless, and with her chin raised a little, as if she were balancing something on it which was quite likely to fall.


[25] words 1945-1977
The other girl, Daisy, made an attempt to rise—she leaned slightly forward with a conscientious expression—then she laughed, an absurd, charming little laugh, and I laughed too and came forward into the room.


[26] words 1978-1981
"I'm p-paralysed with happiness."


[27] words 1982-2025
She laughed again and held my hand for a moment, looking up into my face, promising that there was no one in the world she so much wanted to see. She hinted in a murmur that the surname of the balancing girl was Baker.


[28] words 2026-2046
At any rate, Miss Baker's lips fluttered, she nodded at me almost imperceptibly, and then quickly tipped her head back again.


[29] words 2047-2127
I looked back at my cousin, who began to ask me questions in her low, thrilling voice. It was the kind of voice that the ear follows up and down, as if each speech is an arrangement of notes that will never be played again. Her face was sad and lovely with bright things in it, but there was an excitement in her voice that men who had cared for her found difficult to forget: a singing compulsion, a whispered "Listen."


[30] words 2128-2155
I told her how I had stopped off in Chicago for a day on my way East, and how a dozen people had sent their love through me.


[31] words 2156-2162
"Do they miss me?" she cried ecstatically.


[32] words 2163-2181
"The whole town is desolate. All the cars have the left rear wheel painted black as a mourning wreath."


[33] words 2182-2198
"How gorgeous! Let's go back, Tom. Tomorrow!" Then she added irrelevantly: "You ought to see the baby."


[34] words 2199-2201
"I'd like to."


[35] words 2202-2212
"She's asleep. She's three years old. Haven't you ever seen her?"


[36] words 2213-2213
"Never."


[37] words 2214-2220
"Well, you ought to see her. She's—"


[38] words 2221-2238
Tom Buchanan, who had been hovering restlessly about the room, stopped and rested his hand on my shoulder.


[39] words 2239-2242
"What you doing, Nick?"


[40] words 2243-2246
"I'm a bond man."


[41] words 2247-2248
"Who with?"


[42] words 2249-2251
I told him.


[43] words 2252-2258
"Never heard of them," he remarked decisively.


[44] words 2259-2261
This annoyed me.


[45] words 2262-2274
"You will," I answered shortly. "You will if you stay in the East."


[46] words 2275-2303
"Oh, I'll stay in the East, don't you worry," he said, glancing at Daisy and then back at me. "I'd be a God damned fool to live anywhere else."


[47] words 2304-2330
At this point Miss Baker said: "Absolutely!" with such suddenness that I started. Then, with a series of rapid, deft movements, she stood up into the room.


[48] words 2331-2347
"I'm stiff," she complained. "I've been lying on that sofa for as long as I can remember."


[49] words 2348-2364
"Don't look at me," Daisy retorted, "I've been trying to get you to New York all afternoon."


[50] words 2365-2382
"No, thanks," said Miss Baker to the four cocktails just in from the pantry. "I'm absolutely in training."


[51] words 2383-2416
Her host looked at her incredulously. "You are!" He took down his drink as if it were a drop in the bottom of a glass. "How you ever get anything done is beyond me."


[52] words 2417-2489
I looked at Miss Baker, wondering what it was she "got done." She was a slender, small-breasted girl, with an erect carriage, which she accentuated by throwing her body backward at the shoulders like a young cadet. Her grey sun-strained eyes looked back at me with polite reciprocal curiosity out of a wan, charming, discontented face. It occurred to me now that I had seen her, or a picture of her, somewhere before.


[53] words 2490-2501
"You live in West Egg," she remarked contemptuously. "I know somebody there."


[54] words 2502-2506
"I don't know a single—"


[55] words 2507-2510
"You must know Gatsby."


[56] words 2511-2515
"Gatsby?" demanded Daisy. "What Gatsby?"


[57] words 2516-2551
Before I could reply that he was my neighbour dinner was announced; wedging his tense arm imperatively under mine, Tom Buchanan compelled me from the room as though he were moving a checker to another square.


[58] words 2552-2587
Slenderly, languidly, their hands set lightly on their hips, the two young women preceded us out on to a rosy-coloured porch, open toward the sunset, where four candles flickered on the table in the diminished wind.


[59] words 2588-2645
"Why candles?" objected Daisy, frowning. She snapped them out with her fingers. "In two weeks it'll be the longest day in the year." She looked at us all radiantly. "Do you always watch for the longest day of the year and then miss it? I always watch for the longest day in the year and then miss it."


[60] words 2646-2665
"We ought to plan something," yawned Miss Baker, sitting down at the table as if she were getting into bed.


[61] words 2666-2681
"All right," said Daisy. "What'll we plan?" She turned to me helplessly: "What do people plan?"


[62] words 2682-2696
Before I could answer her eyes fastened with an awed expression on her little finger.


[63] words 2697-2702
"Look!" she complained; "I hurt it."


[64] words 2703-2710
We all looked—the knuckle was black and blue.


[65] words 2711-2747
"You did it, Tom," she said accusingly. "I know you didn't mean to, but you did do it. That's what I get for marrying a brute of a man, a great, big, hulking physical specimen of a—"


[66] words 2748-2759
"I hate that word 'hulking,' " objected Tom crossly, "even in kidding."


[67] words 2760-2762
"Hulking," insisted Daisy.


[68] words 2763-2819
They talked at once now and then, cool as their white dresses and their impersonal eyes. They knew that presently dinner would be over and a little later the evening too would be over and casually put away. It was sharply different from the West, where an evening was hurried from phase to phase towards its close.


[69] words 2820-2844
"You make me feel uncivilized, Daisy," I confessed on my second glass of corky but rather impressive claret. "Can't you talk about crops or something?"


[70] words 2845-2874
"Civilization's going to pieces," broke out Tom violently. "I've gotten to be a terrible pessimist about things. Have you read The Rise of the Coloured Empires by this man Goddard?"


[71] words 2875-2883
"Why, no," I answered, rather surprised by his tone.


[72] words 2884-2917
"Well, it's a fine book, and everybody ought to read it. The idea is if we don't look out the white race will be—will be utterly submerged. It's all scientific stuff; it's been proved."


[73] words 2918-2938
"Tom's getting very profound," said Daisy, with an expression of unthoughtful sadness. "He reads deep books with long words in them."


[74] words 2939-2979
"Well, these books are all scientific," insisted Tom, glancing at her impatiently. "This fellow has worked out the whole thing. It's up to us, who are the dominant race, to watch out or these other races will have control of things."


[75] words 2980-2993
"We've got to beat them down," whispered Daisy, winking ferociously toward the fervent sun.


[76] words 2994-3012
"You ought to live in California—" began Miss Baker, but Tom interrupted her by shifting heavily in his chair.


[77] words 3013-3057
"This idea is that we're Nordics. I am, and you are, and you are, and—" after an infinitesimal hesitation he included Daisy with a slight nod—"and we've produced all the things that go to make civilization—oh, science and art, and all that. Do you see?"


[78] words 3058-3112
When, almost immediately, the telephone rang inside and the butler left the porch Daisy seized upon the interruption; yet Tom frowned, pushed back his chair, and without a word went inside. A subdued impassioned murmur was audible in the room beyond, trembled on the verge of coherence, sank down, mounted excitedly, and then ceased altogether.


[79] words 3113-3123
"This Mr. Gatsby you spoke of is my neighbour—" I began.


[80] words 3124-3134
"Don't talk. I want to hear what happens," said Miss Baker.


[81] words 3135-3140
"Is something happening?" I inquired innocently.


[82] words 3141-3156
"You mean to say you don't know?" said Miss Baker, honestly surprised. "I thought everybody knew."


[83] words 3157-3158
"I don't."


[84] words 3159-3169
"Why—" she said hesitantly. "Tom's got some woman in New York."


[85] words 3170-3175
"Got some woman?" I repeated blankly.


[86] words 3176-3178
Miss Baker nodded.


[87] words 3179-3193
"She might have the decency not to telephone him at dinner time. Don't you think?"


[88] words 3194-3208
Almost before I had grasped her meaning Tom and Daisy were back at the table.


[89] words 3209-3217
"It couldn't be helped!" cried Daisy with tense gaiety.


[90] words 3218-3275
She sat down, glanced searchingly at Miss Baker and then at me, and continued: "I looked outdoors for a minute, and it's very romantic outdoors. There's a bird on the lawn that I think must be a nightingale come over on the Cunard or White Star Line. He's singing away—" Her voice sang: "It's romantic, isn't it, Tom?"


[91] words 3276-3299
"Very romantic," he said, and then miserably to me: "If it's light enough after dinner, I want to take you down to the stables."


[92] words 3300-3370
The telephone rang inside, startlingly, and as Daisy shook her head decisively at Tom the subject of the stables, in fact all subjects, vanished into air. I was conscious of wanting to look squarely at everyone, and yet to avoid all eyes. I doubt if even Miss Baker, who seemed to have mastered a certain hardy scepticism, was able utterly to put this fifth guest's shrill metallic urgency out of mind.


[93] words 3371-3424
Tom and Miss Baker, with several feet of twilight between them, strolled back into the library, while, trying to look pleasantly interested and a little deaf, I followed Daisy around a chain of connecting verandas to the porch in front. In its deep gloom we sat down side by side on a wicker settee.


[94] words 3425-3469
Daisy took her face in her hands as if feeling its lovely shape, and her eyes moved gradually out into the velvet dusk. I saw that turbulent emotions possessed her, so I asked what I thought would be some sedative questions about her little girl.


[95] words 3470-3491
"We don't know each other very well, Nick," she said suddenly. "Even if we are cousins. You didn't come to my wedding."


[96] words 3492-3497
"I wasn't back from the war."


[97] words 3498-3515
"That's true." She hesitated. "Well, I've had a very bad time, Nick, and I'm pretty cynical about everything."


[98] words 3516-3543
Evidently she had reason to be. I waited but she didn't say any more, and after a moment I returned rather feebly to the subject of her daughter.


[99] words 3544-3550
"I suppose she talks, and—eats, and everything."


[100] words 3551-3575
"Oh, yes." She looked at me absently. "Listen, Nick; let me tell you what I said when she was born. Would you like to hear?"


[101] words 3576-3577
"Very much."


[102] words 3578-3672
"It'll show you how I've gotten to feel about—things. Well, she was less than an hour old and Tom was God knows where. I woke up out of the ether with an utterly abandoned feeling, and asked the nurse right away if it was a boy or a girl. She told me it was a girl, and so I turned my head away and wept. 'All right,' I said, 'I'm glad it's a girl. And I hope she'll be a fool—that's the best thing a girl can be in this world, a beautiful little fool.'"


[103] words 3673-3725
"You see I think everything's terrible anyhow," she went on in a convinced way. "Everybody thinks so—the most advanced people. And I know. I've been everywhere and seen everything and done everything." Her eyes flashed around her in a defiant way, rather like Tom's, and she laughed with thrilling scorn. "Sophisticated—God, I'm sophisticated!"


[104] words 3726-3810
The instant her voice broke off, ceasing to compel my attention, my belief, I felt the basic insincerity of what she had said. It made me uneasy, as though the whole evening had been a trick of some sort to exact a contributory emotion from me. I waited, and sure enough, in a moment she looked at me with an absolute smirk on her lovely face, as if she had asserted her membership in a rather distinguished secret society to which she and Tom belonged.


[105] words 3811-3850
Inside, the crimson room bloomed with light. Tom and Miss Baker sat at either end of the long couch and she read aloud to him from the Saturday Evening Post—the words, murmurous and uninflected, running together in a soothing tune.


[106] words 3851-3865
When we came in she held us silent for a moment with a lifted hand.


[107] words 3866-3881
"To be continued," she said, tossing the magazine on the table, "in our very next issue."


[108] words 3882-3896
Her body asserted itself with a restless movement of her knee, and she stood up.


[109] words 3897-3916
"Ten o'clock," she remarked, apparently finding the time on the ceiling. "Time for this good girl to go to bed."


[110] words 3917-3929
"Jordan's going to play in the tournament tomorrow," explained Daisy, "over at Westchester."


[111] words 3930-3932
"Oh—you're Jordan Baker."


[112] words 3933-3977
I knew now why her face was familiar—its pleasing contemptuous expression had looked out at me from many rotogravure pictures of the sporting life. I had heard some story of her too, a critical, unpleasant story, but what it was I had forgotten long ago.


[113] words 3978-3988
"Good night," she said softly. "Wake me at eight, won't you."


[114] words 3989-3992
"If you'll get up."


[115] words 3993-4001
"I will. Good night, Mr. Carraway. See you anon."


[116] words 4002-4048
"Of course you will," confirmed Daisy. "In fact I think I'll arrange a marriage. Come over often, Nick, and I'll sort of—oh—fling you together. You know—lock you up accidentally in linen closets and push you out to sea in a boat, and all that sort of thing—"


[117] words 4049-4061
"Good night," called Miss Baker from the stairs. "I haven't heard a word."


[118] words 4062-4081
"She's a nice girl," said Tom after a moment. "They oughtn't to let her run around the country this way."


[119] words 4082-4087
"Who oughtn't to?" inquired Daisy coldly.


[120] words 4088-4089
"Her family."


[121] words 4090-4131
"Her family is one aunt about a thousand years old. Besides, Nick's going to look after her, aren't you, Nick? She's going to spend lots of weekends out here this summer. I think the home influence will be very good for her."


[122] words 4132-4143
Daisy and Tom looked at each other for a moment in silence.


[123] words 4144-4151
"Is she from New York?" I asked quickly.


[124] words 4152-4163
"From Louisville. Our white girlhood was passed together there. Our beautiful white—"


[125] words 4164-4179
"Did you give Nick a little heart to heart talk on the veranda?" demanded Tom suddenly.


[126] words 4180-4204
"Did I?" She looked at me. "I can't seem to remember, but I think we talked about the Nordic race. Yes, I'm sure we did."


[127] words 4205-4213
"Don't believe everything you hear, Nick," he advised me.


[128] words 4214-4260
I said lightly that I had heard nothing at all, and a few minutes later I got up to go home. They came to the door with me and stood side by side in a cheerful square of light. As I started my motor Daisy peremptorily called:


[129] words 4261-4261
"Wait!


[130] words 4262-4280
"I forgot to ask you something, and it's important. We heard you were engaged to a girl out West."


[131] words 4281-4291
"That's right," corroborated Tom kindly. "We heard that you were engaged."


[132] words 4292-4297
"It's a libel. I'm too poor."


[133] words 4298-4321
"But we heard it," insisted Daisy, opening up again in a flower-like way. "We heard it from three people, so it must be true."


[134] words 4322-4379
Of course I knew what they were referring to, but I wasn't even vaguely engaged. The fact that gossip had published the banns was one of the reasons I had come East. You can't stop going with an old friend on account of rumours, and on the other hand I had no intention of being rumoured into marriage.


[135] words 4380-4480
Their interest rather touched me and made them less remotely rich—nevertheless, I was confused and a little disgusted as I drove away. It seemed to me that the thing for Daisy to do was to rush out of the house, child in arms—but apparently there were no such intentions in her head. As for Tom, the fact that he "had some woman in New York" was really less surprising than that he had been depressed by a book. Something was making him nibble at the edge of stale ideas as if his sturdy physical egotism no longer nourished his peremptory heart.


[136] words 4481-4654
Already it was deep summer on roadhouse roofs and in front of wayside garages, where new red petrol-pumps sat out in pools of light, and when I reached my estate at West Egg I ran the car under its shed and sat for a while on an abandoned grass roller in the yard. The wind had blown off, leaving a loud, bright night, with wings beating in the trees and a persistent organ sound as the full bellows of the earth blew the frogs full of life. The silhouette of a moving cat wavered across the moonlight, and, turning my head to watch it, I saw that I was not alone—fifty feet away a figure had emerged from the shadow of my neighbour's mansion and was standing with his hands in his pockets regarding the silver pepper of the stars. Something in his leisurely movements and the secure position of his feet upon the lawn suggested that it was Mr. Gatsby himself, come out to determine what share was his of our local heavens.


[137] words 4655-4762
I decided to call to him. Miss Baker had mentioned him at dinner, and that would do for an introduction. But I didn't call to him, for he gave a sudden intimation that he was content to be alone—he stretched out his arms toward the dark water in a curious way, and, far as I was from him, I could have sworn he was trembling. Involuntarily I glanced seaward—and distinguished nothing except a single green light, minute and far away, that might have been the end of a dock. When I looked once more for Gatsby he had vanished, and I was alone again in the unquiet darkness.



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