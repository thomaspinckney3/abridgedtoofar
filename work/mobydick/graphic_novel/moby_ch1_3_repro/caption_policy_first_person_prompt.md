You are rewriting the lettering layer for a graphic novel storyboard.

Do not change the art plan, page count, panel count, panel order, beat IDs,
driver characters, character actions, shots, or image prompts except to add a
short instruction reserving the caption zone if needed.

Book: Moby-Dick; or, The Whale
Author: Herman Melville
Narration policy: first-person narrator captions; every caption should read as the narrator saying I/me/my/we/us where natural
Dialogue policy: no speech balloons; convert spoken information into captions

Goals:
- Every panel has exactly one caption.
- Captions flow in the same order as the book and the storyboard panels.
- Use simple language. Prefer one short sentence.
- Use narrator voice. For first-person books, captions must be first-person
  narration using I/me/my/we/us/our where natural. Do not write third-person
  summaries like "Ishmael does..." or "Nick feels...".
- Do not use aphoristic fragments when a clear concrete caption is better.
- Do not add new plot information.
- Remove SFX unless the source absolutely requires a sound for comprehension.
- Avoid speech balloons unless explicitly allowed by `dialogue_policy`.
- Every panel must include a `caption_zone` chosen from:
  `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`,
  `bottom_right`.
- Pick caption zones that avoid faces, major bodies, active hands, and key
  story props described in the panel image prompt.
- If you choose a caption zone, make sure the panel `image_prompt` reserves it:
  add one concise sentence such as "Leave clean negative space in the upper-left
  for a later caption, with faces and important action kept clear of that area."
- Captions are post-lettering text. Do not put text, labels, captions, signs,
  maps, or speech balloons into image prompts.

Source units:
[
  {
    "id": 1,
    "start_word": 1,
    "end_word": 3,
    "text": "CHAPTER 1. Loomings."
  },
  {
    "id": 2,
    "start_word": 4,
    "end_word": 201,
    "text": "Call me Ishmael. Some years ago—never mind how long precisely—having\nlittle or no money in my purse, and nothing particular to interest me\non shore, I thought I would sail about a little and see the watery part\nof the world. It is a way I have of driving off the spleen and\nregulating the circulation. Whenever I find myself growing grim about\nthe mouth; whenever it is a damp, drizzly November in my soul; whenever\nI find myself involuntarily pausing before coffin warehouses, and\nbringing up the rear of every funeral I meet; and especially whenever\nmy hypos get such an upper hand of me, that it requires a strong moral\nprinciple to prevent me from deliberately stepping into the street, and\nmethodically knocking people’s hats off—then, I account it high time to\nget to sea as soon as I can. This is my substitute for pistol and ball.\nWith a philosophical flourish Cato throws himself upon his sword; I\nquietly take to the ship. There is nothing surprising in this. If they\nbut knew it, almost all men in their degree, some time or other,\ncherish very nearly the same feelings towards the ocean with me."
  },
  {
    "id": 3,
    "start_word": 202,
    "end_word": 269,
    "text": "There now is your insular city of the Manhattoes, belted round by\nwharves as Indian isles by coral reefs—commerce surrounds it with her\nsurf. Right and left, the streets take you waterward. Its extreme\ndowntown is the battery, where that noble mole is washed by waves, and\ncooled by breezes, which a few hours previous were out of sight of\nland. Look at the crowds of water-gazers there."
  },
  {
    "id": 4,
    "start_word": 270,
    "end_word": 382,
    "text": "Circumambulate the city of a dreamy Sabbath afternoon. Go from Corlears\nHook to Coenties Slip, and from thence, by Whitehall, northward. What\ndo you see?—Posted like silent sentinels all around the town, stand\nthousands upon thousands of mortal men fixed in ocean reveries. Some\nleaning against the spiles; some seated upon the pier-heads; some\nlooking over the bulwarks of ships from China; some high aloft in the\nrigging, as if striving to get a still better seaward peep. But these\nare all landsmen; of week days pent up in lath and plaster—tied to\ncounters, nailed to benches, clinched to desks. How then is this? Are\nthe green fields gone? What do they here?"
  },
  {
    "id": 5,
    "start_word": 383,
    "end_word": 483,
    "text": "But look! here come more crowds, pacing straight for the water, and\nseemingly bound for a dive. Strange! Nothing will content them but the\nextremest limit of the land; loitering under the shady lee of yonder\nwarehouses will not suffice. No. They must get just as nigh the water\nas they possibly can without falling in. And there they stand—miles of\nthem—leagues. Inlanders all, they come from lanes and alleys, streets\nand avenues—north, east, south, and west. Yet here they all unite. Tell\nme, does the magnetic virtue of the needles of the compasses of all\nthose ships attract them thither?"
  },
  {
    "id": 6,
    "start_word": 484,
    "end_word": 602,
    "text": "Once more. Say you are in the country; in some high land of lakes. Take\nalmost any path you please, and ten to one it carries you down in a\ndale, and leaves you there by a pool in the stream. There is magic in\nit. Let the most absent-minded of men be plunged in his deepest\nreveries—stand that man on his legs, set his feet a-going, and he will\ninfallibly lead you to water, if water there be in all that region.\nShould you ever be athirst in the great American desert, try this\nexperiment, if your caravan happen to be supplied with a metaphysical\nprofessor. Yes, as every one knows, meditation and water are wedded for\never."
  },
  {
    "id": 7,
    "start_word": 603,
    "end_word": 957,
    "text": "But here is an artist. He desires to paint you the dreamiest, shadiest,\nquietest, most enchanting bit of romantic landscape in all the valley\nof the Saco. What is the chief element he employs? There stand his\ntrees, each with a hollow trunk, as if a hermit and a crucifix were\nwithin; and here sleeps his meadow, and there sleep his cattle; and up\nfrom yonder cottage goes a sleepy smoke. Deep into distant woodlands\nwinds a mazy way, reaching to overlapping spurs of mountains bathed in\ntheir hill-side blue. But though the picture lies thus tranced, and\nthough this pine-tree shakes down its sighs like leaves upon this\nshepherd’s head, yet all were vain, unless the shepherd’s eye were\nfixed upon the magic stream before him. Go visit the Prairies in June,\nwhen for scores on scores of miles you wade knee-deep among\nTiger-lilies—what is the one charm wanting?—Water—there is not a drop\nof water there! Were Niagara but a cataract of sand, would you travel\nyour thousand miles to see it? Why did the poor poet of Tennessee, upon\nsuddenly receiving two handfuls of silver, deliberate whether to buy\nhim a coat, which he sadly needed, or invest his money in a pedestrian\ntrip to Rockaway Beach? Why is almost every robust healthy boy with a\nrobust healthy soul in him, at some time or other crazy to go to sea?\nWhy upon your first voyage as a passenger, did you yourself feel such a\nmystical vibration, when first told that you and your ship were now out\nof sight of land? Why did the old Persians hold the sea holy? Why did\nthe Greeks give it a separate deity, and own brother of Jove? Surely\nall this is not without meaning. And still deeper the meaning of that\nstory of Narcissus, who because he could not grasp the tormenting, mild\nimage he saw in the fountain, plunged into it and was drowned. But that\nsame image, we ourselves see in all rivers and oceans. It is the image\nof the ungraspable phantom of life; and this is the key to it all."
  },
  {
    "id": 8,
    "start_word": 958,
    "end_word": 1221,
    "text": "Now, when I say that I am in the habit of going to sea whenever I begin\nto grow hazy about the eyes, and begin to be over conscious of my\nlungs, I do not mean to have it inferred that I ever go to sea as a\npassenger. For to go as a passenger you must needs have a purse, and a\npurse is but a rag unless you have something in it. Besides, passengers\nget sea-sick—grow quarrelsome—don’t sleep of nights—do not enjoy\nthemselves much, as a general thing;—no, I never go as a passenger;\nnor, though I am something of a salt, do I ever go to sea as a\nCommodore, or a Captain, or a Cook. I abandon the glory and distinction\nof such offices to those who like them. For my part, I abominate all\nhonorable respectable toils, trials, and tribulations of every kind\nwhatsoever. It is quite as much as I can do to take care of myself,\nwithout taking care of ships, barques, brigs, schooners, and what not.\nAnd as for going as cook,—though I confess there is considerable glory\nin that, a cook being a sort of officer on ship-board—yet, somehow, I\nnever fancied broiling fowls;—though once broiled, judiciously\nbuttered, and judgmatically salted and peppered, there is no one who\nwill speak more respectfully, not to say reverentially, of a broiled\nfowl than I will. It is out of the idolatrous dotings of the old\nEgyptians upon broiled ibis and roasted river horse, that you see the\nmummies of those creatures in their huge bake-houses the pyramids."
  },
  {
    "id": 9,
    "start_word": 1222,
    "end_word": 1377,
    "text": "No, when I go to sea, I go as a simple sailor, right before the mast,\nplumb down into the forecastle, aloft there to the royal mast-head.\nTrue, they rather order me about some, and make me jump from spar to\nspar, like a grasshopper in a May meadow. And at first, this sort of\nthing is unpleasant enough. It touches one’s sense of honor,\nparticularly if you come of an old established family in the land, the\nVan Rensselaers, or Randolphs, or Hardicanutes. And more than all, if\njust previous to putting your hand into the tar-pot, you have been\nlording it as a country schoolmaster, making the tallest boys stand in\nawe of you. The transition is a keen one, I assure you, from a\nschoolmaster to a sailor, and requires a strong decoction of Seneca and\nthe Stoics to enable you to grin and bear it. But even this wears off\nin time."
  },
  {
    "id": 10,
    "start_word": 1378,
    "end_word": 1517,
    "text": "What of it, if some old hunks of a sea-captain orders me to get a broom\nand sweep down the decks? What does that indignity amount to, weighed,\nI mean, in the scales of the New Testament? Do you think the archangel\nGabriel thinks anything the less of me, because I promptly and\nrespectfully obey that old hunks in that particular instance? Who ain’t\na slave? Tell me that. Well, then, however the old sea-captains may\norder me about—however they may thump and punch me about, I have the\nsatisfaction of knowing that it is all right; that everybody else is\none way or other served in much the same way—either in a physical or\nmetaphysical point of view, that is; and so the universal thump is\npassed round, and all hands should rub each other’s shoulder-blades,\nand be content."
  },
  {
    "id": 11,
    "start_word": 1518,
    "end_word": 1642,
    "text": "Again, I always go to sea as a sailor, because they make a point of\npaying me for my trouble, whereas they never pay passengers a single\npenny that I ever heard of. On the contrary, passengers themselves must\npay. And there is all the difference in the world between paying and\nbeing paid. The act of paying is perhaps the most uncomfortable\ninfliction that the two orchard thieves entailed upon us. But _being\npaid_,—what will compare with it? The urbane activity with which a man\nreceives money is really marvellous, considering that we so earnestly\nbelieve money to be the root of all earthly ills, and that on no\naccount can a monied man enter heaven. Ah! how cheerfully we consign\nourselves to perdition!"
  },
  {
    "id": 12,
    "start_word": 1643,
    "end_word": 1859,
    "text": "Finally, I always go to sea as a sailor, because of the wholesome\nexercise and pure air of the fore-castle deck. For as in this world,\nhead winds are far more prevalent than winds from astern (that is, if\nyou never violate the Pythagorean maxim), so for the most part the\nCommodore on the quarter-deck gets his atmosphere at second hand from\nthe sailors on the forecastle. He thinks he breathes it first; but not\nso. In much the same way do the commonalty lead their leaders in many\nother things, at the same time that the leaders little suspect it. But\nwherefore it was that after having repeatedly smelt the sea as a\nmerchant sailor, I should now take it into my head to go on a whaling\nvoyage; this the invisible police officer of the Fates, who has the\nconstant surveillance of me, and secretly dogs me, and influences me in\nsome unaccountable way—he can better answer than any one else. And,\ndoubtless, my going on this whaling voyage, formed part of the grand\nprogramme of Providence that was drawn up a long time ago. It came in\nas a sort of brief interlude and solo between more extensive\nperformances. I take it that this part of the bill must have run\nsomething like this:"
  },
  {
    "id": 13,
    "start_word": 1860,
    "end_word": 1878,
    "text": "“_Grand Contested Election for the Presidency of the United States._\n“WHALING VOYAGE BY ONE ISHMAEL. “BLOODY BATTLE IN AFFGHANISTAN.”"
  },
  {
    "id": 14,
    "start_word": 1879,
    "end_word": 1993,
    "text": "Though I cannot tell why it was exactly that those stage managers, the\nFates, put me down for this shabby part of a whaling voyage, when\nothers were set down for magnificent parts in high tragedies, and short\nand easy parts in genteel comedies, and jolly parts in farces—though I\ncannot tell why this was exactly; yet, now that I recall all the\ncircumstances, I think I can see a little into the springs and motives\nwhich being cunningly presented to me under various disguises, induced\nme to set about performing the part I did, besides cajoling me into the\ndelusion that it was a choice resulting from my own unbiased freewill\nand discriminating judgment."
  },
  {
    "id": 15,
    "start_word": 1994,
    "end_word": 2132,
    "text": "Chief among these motives was the overwhelming idea of the great whale\nhimself. Such a portentous and mysterious monster roused all my\ncuriosity. Then the wild and distant seas where he rolled his island\nbulk; the undeliverable, nameless perils of the whale; these, with all\nthe attending marvels of a thousand Patagonian sights and sounds,\nhelped to sway me to my wish. With other men, perhaps, such things\nwould not have been inducements; but as for me, I am tormented with an\neverlasting itch for things remote. I love to sail forbidden seas, and\nland on barbarous coasts. Not ignoring what is good, I am quick to\nperceive a horror, and could still be social with it—would they let\nme—since it is but well to be on friendly terms with all the inmates of\nthe place one lodges in."
  },
  {
    "id": 16,
    "start_word": 2133,
    "end_word": 2193,
    "text": "By reason of these things, then, the whaling voyage was welcome; the\ngreat flood-gates of the wonder-world swung open, and in the wild\nconceits that swayed me to my purpose, two and two there floated into\nmy inmost soul, endless processions of the whale, and, mid most of them\nall, one grand hooded phantom, like a snow hill in the air."
  },
  {
    "id": 17,
    "start_word": 2194,
    "end_word": 2197,
    "text": "CHAPTER 2. The Carpet-Bag."
  },
  {
    "id": 18,
    "start_word": 2198,
    "end_word": 2269,
    "text": "I stuffed a shirt or two into my old carpet-bag, tucked it under my\narm, and started for Cape Horn and the Pacific. Quitting the good city\nof old Manhatto, I duly arrived in New Bedford. It was a Saturday night\nin December. Much was I disappointed upon learning that the little\npacket for Nantucket had already sailed, and that no way of reaching\nthat place would offer, till the following Monday."
  },
  {
    "id": 19,
    "start_word": 2270,
    "end_word": 2452,
    "text": "As most young candidates for the pains and penalties of whaling stop at\nthis same New Bedford, thence to embark on their voyage, it may as well\nbe related that I, for one, had no idea of so doing. For my mind was\nmade up to sail in no other than a Nantucket craft, because there was a\nfine, boisterous something about everything connected with that famous\nold island, which amazingly pleased me. Besides though New Bedford has\nof late been gradually monopolising the business of whaling, and though\nin this matter poor old Nantucket is now much behind her, yet Nantucket\nwas her great original—the Tyre of this Carthage;—the place where the\nfirst dead American whale was stranded. Where else but from Nantucket\ndid those aboriginal whalemen, the Red-Men, first sally out in canoes\nto give chase to the Leviathan? And where but from Nantucket, too, did\nthat first adventurous little sloop put forth, partly laden with\nimported cobblestones—so goes the story—to throw at the whales, in\norder to discover when they were nigh enough to risk a harpoon from the\nbowsprit?"
  },
  {
    "id": 20,
    "start_word": 2453,
    "end_word": 2589,
    "text": "Now having a night, a day, and still another night following before me\nin New Bedford, ere I could embark for my destined port, it became a\nmatter of concernment where I was to eat and sleep meanwhile. It was a\nvery dubious-looking, nay, a very dark and dismal night, bitingly cold\nand cheerless. I knew no one in the place. With anxious grapnels I had\nsounded my pocket, and only brought up a few pieces of silver,—So,\nwherever you go, Ishmael, said I to myself, as I stood in the middle of\na dreary street shouldering my bag, and comparing the gloom towards the\nnorth with the darkness towards the south—wherever in your wisdom you\nmay conclude to lodge for the night, my dear Ishmael, be sure to\ninquire the price, and don’t be too particular."
  },
  {
    "id": 21,
    "start_word": 2590,
    "end_word": 2762,
    "text": "With halting steps I paced the streets, and passed the sign of “The\nCrossed Harpoons”—but it looked too expensive and jolly there. Further\non, from the bright red windows of the “Sword-Fish Inn,” there came\nsuch fervent rays, that it seemed to have melted the packed snow and\nice from before the house, for everywhere else the congealed frost lay\nten inches thick in a hard, asphaltic pavement,—rather weary for me,\nwhen I struck my foot against the flinty projections, because from\nhard, remorseless service the soles of my boots were in a most\nmiserable plight. Too expensive and jolly, again thought I, pausing one\nmoment to watch the broad glare in the street, and hear the sounds of\nthe tinkling glasses within. But go on, Ishmael, said I at last; don’t\nyou hear? get away from before the door; your patched boots are\nstopping the way. So on I went. I now by instinct followed the streets\nthat took me waterward, for there, doubtless, were the cheapest, if not\nthe cheeriest inns."
  },
  {
    "id": 22,
    "start_word": 2763,
    "end_word": 2916,
    "text": "Such dreary streets! blocks of blackness, not houses, on either hand,\nand here and there a candle, like a candle moving about in a tomb. At\nthis hour of the night, of the last day of the week, that quarter of\nthe town proved all but deserted. But presently I came to a smoky light\nproceeding from a low, wide building, the door of which stood\ninvitingly open. It had a careless look, as if it were meant for the\nuses of the public; so, entering, the first thing I did was to stumble\nover an ash-box in the porch. Ha! thought I, ha, as the flying\nparticles almost choked me, are these ashes from that destroyed city,\nGomorrah? But “The Crossed Harpoons,” and “The Sword-Fish?”—this, then\nmust needs be the sign of “The Trap.” However, I picked myself up and\nhearing a loud voice within, pushed on and opened a second, interior\ndoor."
  },
  {
    "id": 23,
    "start_word": 2917,
    "end_word": 2987,
    "text": "It seemed the great Black Parliament sitting in Tophet. A hundred black\nfaces turned round in their rows to peer; and beyond, a black Angel of\nDoom was beating a book in a pulpit. It was a negro church; and the\npreacher’s text was about the blackness of darkness, and the weeping\nand wailing and teeth-gnashing there. Ha, Ishmael, muttered I, backing\nout, Wretched entertainment at the sign of ‘The Trap!’"
  },
  {
    "id": 24,
    "start_word": 2988,
    "end_word": 3044,
    "text": "Moving on, I at last came to a dim sort of light not far from the\ndocks, and heard a forlorn creaking in the air; and looking up, saw a\nswinging sign over the door with a white painting upon it, faintly\nrepresenting a tall straight jet of misty spray, and these words\nunderneath—“The Spouter Inn:—Peter Coffin.”"
  },
  {
    "id": 25,
    "start_word": 3045,
    "end_word": 3141,
    "text": "Coffin?—Spouter?—Rather ominous in that particular connexion, thought\nI. But it is a common name in Nantucket, they say, and I suppose this\nPeter here is an emigrant from there. As the light looked so dim, and\nthe place, for the time, looked quiet enough, and the dilapidated\nlittle wooden house itself looked as if it might have been carted here\nfrom the ruins of some burnt district, and as the swinging sign had a\npoverty-stricken sort of creak to it, I thought that here was the very\nspot for cheap lodgings, and the best of pea coffee."
  },
  {
    "id": 26,
    "start_word": 3142,
    "end_word": 3449,
    "text": "It was a queer sort of place—a gable-ended old house, one side palsied\nas it were, and leaning over sadly. It stood on a sharp bleak corner,\nwhere that tempestuous wind Euroclydon kept up a worse howling than\never it did about poor Paul’s tossed craft. Euroclydon, nevertheless,\nis a mighty pleasant zephyr to any one in-doors, with his feet on the\nhob quietly toasting for bed. “In judging of that tempestuous wind\ncalled Euroclydon,” says an old writer—of whose works I possess the\nonly copy extant—“it maketh a marvellous difference, whether thou\nlookest out at it from a glass window where the frost is all on the\noutside, or whether thou observest it from that sashless window, where\nthe frost is on both sides, and of which the wight Death is the only\nglazier.” True enough, thought I, as this passage occurred to my\nmind—old black-letter, thou reasonest well. Yes, these eyes are\nwindows, and this body of mine is the house. What a pity they didn’t\nstop up the chinks and the crannies though, and thrust in a little lint\nhere and there. But it’s too late to make any improvements now. The\nuniverse is finished; the copestone is on, and the chips were carted\noff a million years ago. Poor Lazarus there, chattering his teeth\nagainst the curbstone for his pillow, and shaking off his tatters with\nhis shiverings, he might plug up both ears with rags, and put a\ncorn-cob into his mouth, and yet that would not keep out the\ntempestuous Euroclydon. Euroclydon! says old Dives, in his red silken\nwrapper—(he had a redder one afterwards) pooh, pooh! What a fine frosty\nnight; how Orion glitters; what northern lights! Let them talk of their\noriental summer climes of everlasting conservatories; give me the\nprivilege of making my own summer with my own coals."
  },
  {
    "id": 27,
    "start_word": 3450,
    "end_word": 3509,
    "text": "But what thinks Lazarus? Can he warm his blue hands by holding them up\nto the grand northern lights? Would not Lazarus rather be in Sumatra\nthan here? Would he not far rather lay him down lengthwise along the\nline of the equator; yea, ye gods! go down to the fiery pit itself, in\norder to keep out this frost?"
  },
  {
    "id": 28,
    "start_word": 3510,
    "end_word": 3573,
    "text": "Now, that Lazarus should lie stranded there on the curbstone before the\ndoor of Dives, this is more wonderful than that an iceberg should be\nmoored to one of the Moluccas. Yet Dives himself, he too lives like a\nCzar in an ice palace made of frozen sighs, and being a president of a\ntemperance society, he only drinks the tepid tears of orphans."
  },
  {
    "id": 29,
    "start_word": 3574,
    "end_word": 3613,
    "text": "But no more of this blubbering now, we are going a-whaling, and there\nis plenty of that yet to come. Let us scrape the ice from our frosted\nfeet, and see what sort of a place this “Spouter” may be."
  },
  {
    "id": 30,
    "start_word": 3614,
    "end_word": 3617,
    "text": "CHAPTER 3. The Spouter-Inn."
  },
  {
    "id": 31,
    "start_word": 3618,
    "end_word": 3775,
    "text": "Entering that gable-ended Spouter-Inn, you found yourself in a wide,\nlow, straggling entry with old-fashioned wainscots, reminding one of\nthe bulwarks of some condemned old craft. On one side hung a very large\noilpainting so thoroughly besmoked, and every way defaced, that in the\nunequal crosslights by which you viewed it, it was only by diligent\nstudy and a series of systematic visits to it, and careful inquiry of\nthe neighbors, that you could any way arrive at an understanding of its\npurpose. Such unaccountable masses of shades and shadows, that at first\nyou almost thought some ambitious young artist, in the time of the New\nEngland hags, had endeavored to delineate chaos bewitched. But by dint\nof much and earnest contemplation, and oft repeated ponderings, and\nespecially by throwing open the little window towards the back of the\nentry, you at last come to the conclusion that such an idea, however\nwild, might not be altogether unwarranted."
  },
  {
    "id": 32,
    "start_word": 3776,
    "end_word": 3943,
    "text": "But what most puzzled and confounded you was a long, limber,\nportentous, black mass of something hovering in the centre of the\npicture over three blue, dim, perpendicular lines floating in a\nnameless yeast. A boggy, soggy, squitchy picture truly, enough to drive\na nervous man distracted. Yet was there a sort of indefinite,\nhalf-attained, unimaginable sublimity about it that fairly froze you to\nit, till you involuntarily took an oath with yourself to find out what\nthat marvellous painting meant. Ever and anon a bright, but, alas,\ndeceptive idea would dart you through.—It’s the Black Sea in a midnight\ngale.—It’s the unnatural combat of the four primal elements.—It’s a\nblasted heath.—It’s a Hyperborean winter scene.—It’s the breaking-up of\nthe icebound stream of Time. But at last all these fancies yielded to\nthat one portentous something in the picture’s midst. _That_ once found\nout, and all the rest were plain. But stop; does it not bear a faint\nresemblance to a gigantic fish? even the great leviathan himself?"
  },
  {
    "id": 33,
    "start_word": 3944,
    "end_word": 4017,
    "text": "In fact, the artist’s design seemed this: a final theory of my own,\npartly based upon the aggregated opinions of many aged persons with\nwhom I conversed upon the subject. The picture represents a Cape-Horner\nin a great hurricane; the half-foundered ship weltering there with its\nthree dismantled masts alone visible; and an exasperated whale,\npurposing to spring clean over the craft, is in the enormous act of\nimpaling himself upon the three mast-heads."
  },
  {
    "id": 34,
    "start_word": 4018,
    "end_word": 4199,
    "text": "The opposite wall of this entry was hung all over with a heathenish\narray of monstrous clubs and spears. Some were thickly set with\nglittering teeth resembling ivory saws; others were tufted with knots\nof human hair; and one was sickle-shaped, with a vast handle sweeping\nround like the segment made in the new-mown grass by a long-armed\nmower. You shuddered as you gazed, and wondered what monstrous cannibal\nand savage could ever have gone a death-harvesting with such a hacking,\nhorrifying implement. Mixed with these were rusty old whaling lances\nand harpoons all broken and deformed. Some were storied weapons. With\nthis once long lance, now wildly elbowed, fifty years ago did Nathan\nSwain kill fifteen whales between a sunrise and a sunset. And that\nharpoon—so like a corkscrew now—was flung in Javan seas, and run away\nwith by a whale, years afterwards slain off the Cape of Blanco. The\noriginal iron entered nigh the tail, and, like a restless needle\nsojourning in the body of a man, travelled full forty feet, and at last\nwas found imbedded in the hump."
  },
  {
    "id": 35,
    "start_word": 4200,
    "end_word": 4387,
    "text": "Crossing this dusky entry, and on through yon low-arched way—cut\nthrough what in old times must have been a great central chimney with\nfireplaces all round—you enter the public room. A still duskier place\nis this, with such low ponderous beams above, and such old wrinkled\nplanks beneath, that you would almost fancy you trod some old craft’s\ncockpits, especially of such a howling night, when this corner-anchored\nold ark rocked so furiously. On one side stood a long, low, shelf-like\ntable covered with cracked glass cases, filled with dusty rarities\ngathered from this wide world’s remotest nooks. Projecting from the\nfurther angle of the room stands a dark-looking den—the bar—a rude\nattempt at a right whale’s head. Be that how it may, there stands the\nvast arched bone of the whale’s jaw, so wide, a coach might almost\ndrive beneath it. Within are shabby shelves, ranged round with old\ndecanters, bottles, flasks; and in those jaws of swift destruction,\nlike another cursed Jonah (by which name indeed they called him),\nbustles a little withered old man, who, for their money, dearly sells\nthe sailors deliriums and death."
  },
  {
    "id": 36,
    "start_word": 4388,
    "end_word": 4458,
    "text": "Abominable are the tumblers into which he pours his poison. Though true\ncylinders without—within, the villanous green goggling glasses\ndeceitfully tapered downwards to a cheating bottom. Parallel meridians\nrudely pecked into the glass, surround these footpads’ goblets. Fill to\n_this_ mark, and your charge is but a penny; to _this_ a penny more;\nand so on to the full glass—the Cape Horn measure, which you may gulp\ndown for a shilling."
  },
  {
    "id": 37,
    "start_word": 4459,
    "end_word": 4542,
    "text": "Upon entering the place I found a number of young seamen gathered about\na table, examining by a dim light divers specimens of _skrimshander_. I\nsought the landlord, and telling him I desired to be accommodated with\na room, received for answer that his house was full—not a bed\nunoccupied. “But avast,” he added, tapping his forehead, “you haint no\nobjections to sharing a harpooneer’s blanket, have ye? I s’pose you are\ngoin’ a-whalin’, so you’d better get used to that sort of thing.”"
  },
  {
    "id": 38,
    "start_word": 4543,
    "end_word": 4617,
    "text": "I told him that I never liked to sleep two in a bed; that if I should\never do so, it would depend upon who the harpooneer might be, and that\nif he (the landlord) really had no other place for me, and the\nharpooneer was not decidedly objectionable, why rather than wander\nfurther about a strange town on so bitter a night, I would put up with\nthe half of any decent man’s blanket."
  },
  {
    "id": 39,
    "start_word": 4618,
    "end_word": 4632,
    "text": "“I thought so. All right; take a seat. Supper?—you want supper?\nSupper’ll be ready directly.”"
  },
  {
    "id": 40,
    "start_word": 4633,
    "end_word": 4694,
    "text": "I sat down on an old wooden settle, carved all over like a bench on the\nBattery. At one end a ruminating tar was still further adorning it with\nhis jack-knife, stooping over and diligently working away at the space\nbetween his legs. He was trying his hand at a ship under full sail, but\nhe didn’t make much headway, I thought."
  },
  {
    "id": 41,
    "start_word": 4695,
    "end_word": 4797,
    "text": "At last some four or five of us were summoned to our meal in an\nadjoining room. It was cold as Iceland—no fire at all—the landlord said\nhe couldn’t afford it. Nothing but two dismal tallow candles, each in a\nwinding sheet. We were fain to button up our monkey jackets, and hold\nto our lips cups of scalding tea with our half frozen fingers. But the\nfare was of the most substantial kind—not only meat and potatoes, but\ndumplings; good heavens! dumplings for supper! One young fellow in a\ngreen box coat, addressed himself to these dumplings in a most direful\nmanner."
  },
  {
    "id": 42,
    "start_word": 4798,
    "end_word": 4810,
    "text": "“My boy,” said the landlord, “you’ll have the nightmare to a dead\nsartainty.”"
  },
  {
    "id": 43,
    "start_word": 4811,
    "end_word": 4819,
    "text": "“Landlord,” I whispered, “that aint the harpooneer is it?”"
  },
  {
    "id": 44,
    "start_word": 4820,
    "end_word": 4851,
    "text": "“Oh, no,” said he, looking a sort of diabolically funny, “the\nharpooneer is a dark complexioned chap. He never eats dumplings, he\ndon’t—he eats nothing but steaks, and he likes ’em rare.”"
  },
  {
    "id": 45,
    "start_word": 4852,
    "end_word": 4864,
    "text": "“The devil he does,” says I. “Where is that harpooneer? Is he here?”"
  },
  {
    "id": 46,
    "start_word": 4865,
    "end_word": 4872,
    "text": "“He’ll be here afore long,” was the answer."
  },
  {
    "id": 47,
    "start_word": 4873,
    "end_word": 4917,
    "text": "I could not help it, but I began to feel suspicious of this “dark\ncomplexioned” harpooneer. At any rate, I made up my mind that if it so\nturned out that we should sleep together, he must undress and get into\nbed before I did."
  },
  {
    "id": 48,
    "start_word": 4918,
    "end_word": 4948,
    "text": "Supper over, the company went back to the bar-room, when, knowing not\nwhat else to do with myself, I resolved to spend the rest of the\nevening as a looker on."
  },
  {
    "id": 49,
    "start_word": 4949,
    "end_word": 4992,
    "text": "Presently a rioting noise was heard without. Starting up, the landlord\ncried, “That’s the Grampus’s crew. I seed her reported in the offing\nthis morning; a three years’ voyage, and a full ship. Hurrah, boys; now\nwe’ll have the latest news from the Feegees.”"
  },
  {
    "id": 50,
    "start_word": 4993,
    "end_word": 5147,
    "text": "A tramping of sea boots was heard in the entry; the door was flung\nopen, and in rolled a wild set of mariners enough. Enveloped in their\nshaggy watch coats, and with their heads muffled in woollen comforters,\nall bedarned and ragged, and their beards stiff with icicles, they\nseemed an eruption of bears from Labrador. They had just landed from\ntheir boat, and this was the first house they entered. No wonder, then,\nthat they made a straight wake for the whale’s mouth—the bar—when the\nwrinkled little old Jonah, there officiating, soon poured them out\nbrimmers all round. One complained of a bad cold in his head, upon\nwhich Jonah mixed him a pitch-like potion of gin and molasses, which he\nswore was a sovereign cure for all colds and catarrhs whatsoever, never\nmind of how long standing, or whether caught off the coast of Labrador,\nor on the weather side of an ice-island."
  },
  {
    "id": 51,
    "start_word": 5148,
    "end_word": 5174,
    "text": "The liquor soon mounted into their heads, as it generally does even\nwith the arrantest topers newly landed from sea, and they began\ncapering about most obstreperously."
  },
  {
    "id": 52,
    "start_word": 5175,
    "end_word": 5421,
    "text": "I observed, however, that one of them held somewhat aloof, and though\nhe seemed desirous not to spoil the hilarity of his shipmates by his\nown sober face, yet upon the whole he refrained from making as much\nnoise as the rest. This man interested me at once; and since the\nsea-gods had ordained that he should soon become my shipmate (though\nbut a sleeping-partner one, so far as this narrative is concerned), I\nwill here venture upon a little description of him. He stood full six\nfeet in height, with noble shoulders, and a chest like a coffer-dam. I\nhave seldom seen such brawn in a man. His face was deeply brown and\nburnt, making his white teeth dazzling by the contrast; while in the\ndeep shadows of his eyes floated some reminiscences that did not seem\nto give him much joy. His voice at once announced that he was a\nSoutherner, and from his fine stature, I thought he must be one of\nthose tall mountaineers from the Alleghanian Ridge in Virginia. When\nthe revelry of his companions had mounted to its height, this man\nslipped away unobserved, and I saw no more of him till he became my\ncomrade on the sea. In a few minutes, however, he was missed by his\nshipmates, and being, it seems, for some reason a huge favourite with\nthem, they raised a cry of “Bulkington! Bulkington! where’s\nBulkington?” and darted out of the house in pursuit of him."
  },
  {
    "id": 53,
    "start_word": 5422,
    "end_word": 5459,
    "text": "It was now about nine o’clock, and the room seeming almost\nsupernaturally quiet after these orgies, I began to congratulate myself\nupon a little plan that had occurred to me just previous to the\nentrance of the seamen."
  },
  {
    "id": 54,
    "start_word": 5460,
    "end_word": 5592,
    "text": "No man prefers to sleep two in a bed. In fact, you would a good deal\nrather not sleep with your own brother. I don’t know how it is, but\npeople like to be private when they are sleeping. And when it comes to\nsleeping with an unknown stranger, in a strange inn, in a strange town,\nand that stranger a harpooneer, then your objections indefinitely\nmultiply. Nor was there any earthly reason why I as a sailor should\nsleep two in a bed, more than anybody else; for sailors no more sleep\ntwo in a bed at sea, than bachelor Kings do ashore. To be sure they all\nsleep together in one apartment, but you have your own hammock, and\ncover yourself with your own blanket, and sleep in your own skin."
  },
  {
    "id": 55,
    "start_word": 5593,
    "end_word": 5681,
    "text": "The more I pondered over this harpooneer, the more I abominated the\nthought of sleeping with him. It was fair to presume that being a\nharpooneer, his linen or woollen, as the case might be, would not be of\nthe tidiest, certainly none of the finest. I began to twitch all over.\nBesides, it was getting late, and my decent harpooneer ought to be home\nand going bedwards. Suppose now, he should tumble in upon me at\nmidnight—how could I tell from what vile hole he had been coming?"
  },
  {
    "id": 56,
    "start_word": 5682,
    "end_word": 5698,
    "text": "“Landlord! I’ve changed my mind about that harpooneer.—I shan’t sleep\nwith him. I’ll try the bench here.”"
  },
  {
    "id": 57,
    "start_word": 5699,
    "end_word": 5870,
    "text": "“Just as you please; I’m sorry I can’t spare ye a tablecloth for a\nmattress, and it’s a plaguy rough board here”—feeling of the knots and\nnotches. “But wait a bit, Skrimshander; I’ve got a carpenter’s plane\nthere in the bar—wait, I say, and I’ll make ye snug enough.” So saying\nhe procured the plane; and with his old silk handkerchief first dusting\nthe bench, vigorously set to planing away at my bed, the while grinning\nlike an ape. The shavings flew right and left; till at last the\nplane-iron came bump against an indestructible knot. The landlord was\nnear spraining his wrist, and I told him for heaven’s sake to quit—the\nbed was soft enough to suit me, and I did not know how all the planing\nin the world could make eider down of a pine plank. So gathering up the\nshavings with another grin, and throwing them into the great stove in\nthe middle of the room, he went about his business, and left me in a\nbrown study."
  },
  {
    "id": 58,
    "start_word": 5871,
    "end_word": 6018,
    "text": "I now took the measure of the bench, and found that it was a foot too\nshort; but that could be mended with a chair. But it was a foot too\nnarrow, and the other bench in the room was about four inches higher\nthan the planed one—so there was no yoking them. I then placed the\nfirst bench lengthwise along the only clear space against the wall,\nleaving a little interval between, for my back to settle down in. But I\nsoon found that there came such a draught of cold air over me from\nunder the sill of the window, that this plan would never do at all,\nespecially as another current from the rickety door met the one from\nthe window, and both together formed a series of small whirlwinds in\nthe immediate vicinity of the spot where I had thought to spend the\nnight."
  },
  {
    "id": 59,
    "start_word": 6019,
    "end_word": 6095,
    "text": "The devil fetch that harpooneer, thought I, but stop, couldn’t I steal\na march on him—bolt his door inside, and jump into his bed, not to be\nwakened by the most violent knockings? It seemed no bad idea; but upon\nsecond thoughts I dismissed it. For who could tell but what the next\nmorning, so soon as I popped out of the room, the harpooneer might be\nstanding in the entry, all ready to knock me down!"
  },
  {
    "id": 60,
    "start_word": 6096,
    "end_word": 6165,
    "text": "Still, looking round me again, and seeing no possible chance of\nspending a sufferable night unless in some other person’s bed, I began\nto think that after all I might be cherishing unwarrantable prejudices\nagainst this unknown harpooneer. Thinks I, I’ll wait awhile; he must be\ndropping in before long. I’ll have a good look at him then, and perhaps\nwe may become jolly good bedfellows after all—there’s no telling."
  },
  {
    "id": 61,
    "start_word": 6166,
    "end_word": 6188,
    "text": "But though the other boarders kept coming in by ones, twos, and threes,\nand going to bed, yet no sign of my harpooneer."
  },
  {
    "id": 62,
    "start_word": 6189,
    "end_word": 6211,
    "text": "“Landlord!” said I, “what sort of a chap is he—does he always keep such\nlate hours?” It was now hard upon twelve o’clock."
  },
  {
    "id": 63,
    "start_word": 6212,
    "end_word": 6279,
    "text": "The landlord chuckled again with his lean chuckle, and seemed to be\nmightily tickled at something beyond my comprehension. “No,” he\nanswered, “generally he’s an early bird—airley to bed and airley to\nrise—yes, he’s the bird what catches the worm. But to-night he went out\na peddling, you see, and I don’t see what on airth keeps him so late,\nunless, may be, he can’t sell his head.”"
  },
  {
    "id": 64,
    "start_word": 6280,
    "end_word": 6326,
    "text": "“Can’t sell his head?—What sort of a bamboozingly story is this you are\ntelling me?” getting into a towering rage. “Do you pretend to say,\nlandlord, that this harpooneer is actually engaged this blessed\nSaturday night, or rather Sunday morning, in peddling his head around\nthis town?”"
  },
  {
    "id": 65,
    "start_word": 6327,
    "end_word": 6344,
    "text": "“That’s precisely it,” said the landlord, “and I told him he couldn’t\nsell it here, the market’s overstocked.”"
  },
  {
    "id": 66,
    "start_word": 6345,
    "end_word": 6348,
    "text": "“With what?” shouted I."
  },
  {
    "id": 67,
    "start_word": 6349,
    "end_word": 6361,
    "text": "“With heads to be sure; ain’t there too many heads in the world?”"
  },
  {
    "id": 68,
    "start_word": 6362,
    "end_word": 6382,
    "text": "“I tell you what it is, landlord,” said I quite calmly, “you’d better\nstop spinning that yarn to me—I’m not green.”"
  },
  {
    "id": 69,
    "start_word": 6383,
    "end_word": 6411,
    "text": "“May be not,” taking out a stick and whittling a toothpick, “but I\nrayther guess you’ll be done _brown_ if that ere harpooneer hears you a\nslanderin’ his head.”"
  },
  {
    "id": 70,
    "start_word": 6412,
    "end_word": 6431,
    "text": "“I’ll break it for him,” said I, now flying into a passion again at\nthis unaccountable farrago of the landlord’s."
  },
  {
    "id": 71,
    "start_word": 6432,
    "end_word": 6436,
    "text": "“It’s broke a’ready,” said he."
  },
  {
    "id": 72,
    "start_word": 6437,
    "end_word": 6442,
    "text": "“Broke,” said I—“_broke_, do you mean?”"
  },
  {
    "id": 73,
    "start_word": 6443,
    "end_word": 6454,
    "text": "“Sartain, and that’s the very reason he can’t sell it, I guess.”"
  },
  {
    "id": 74,
    "start_word": 6455,
    "end_word": 6667,
    "text": "“Landlord,” said I, going up to him as cool as Mt. Hecla in a\nsnow-storm—“landlord, stop whittling. You and I must understand one\nanother, and that too without delay. I come to your house and want a\nbed; you tell me you can only give me half a one; that the other half\nbelongs to a certain harpooneer. And about this harpooneer, whom I have\nnot yet seen, you persist in telling me the most mystifying and\nexasperating stories tending to beget in me an uncomfortable feeling\ntowards the man whom you design for my bedfellow—a sort of connexion,\nlandlord, which is an intimate and confidential one in the highest\ndegree. I now demand of you to speak out and tell me who and what this\nharpooneer is, and whether I shall be in all respects safe to spend the\nnight with him. And in the first place, you will be so good as to unsay\nthat story about selling his head, which if true I take to be good\nevidence that this harpooneer is stark mad, and I’ve no idea of\nsleeping with a madman; and you, sir, _you_ I mean, landlord, _you_,\nsir, by trying to induce me to do so knowingly, would thereby render\nyourself liable to a criminal prosecution.”"
  },
  {
    "id": 75,
    "start_word": 6668,
    "end_word": 6798,
    "text": "“Wall,” said the landlord, fetching a long breath, “that’s a purty long\nsarmon for a chap that rips a little now and then. But be easy, be\neasy, this here harpooneer I have been tellin’ you of has just arrived\nfrom the south seas, where he bought up a lot of ’balmed New Zealand\nheads (great curios, you know), and he’s sold all on ’em but one, and\nthat one he’s trying to sell to-night, cause to-morrow’s Sunday, and it\nwould not do to be sellin’ human heads about the streets when folks is\ngoin’ to churches. He wanted to, last Sunday, but I stopped him just as\nhe was goin’ out of the door with four heads strung on a string, for\nall the airth like a string of inions.”"
  },
  {
    "id": 76,
    "start_word": 6799,
    "end_word": 6856,
    "text": "This account cleared up the otherwise unaccountable mystery, and showed\nthat the landlord, after all, had had no idea of fooling me—but at the\nsame time what could I think of a harpooneer who stayed out of a\nSaturday night clean into the holy Sabbath, engaged in such a cannibal\nbusiness as selling the heads of dead idolators?"
  },
  {
    "id": 77,
    "start_word": 6857,
    "end_word": 6866,
    "text": "“Depend upon it, landlord, that harpooneer is a dangerous man.”"
  },
  {
    "id": 78,
    "start_word": 6867,
    "end_word": 7032,
    "text": "“He pays reg’lar,” was the rejoinder. “But come, it’s getting dreadful\nlate, you had better be turning flukes—it’s a nice bed; Sal and me\nslept in that ere bed the night we were spliced. There’s plenty of room\nfor two to kick about in that bed; it’s an almighty big bed that. Why,\nafore we give it up, Sal used to put our Sam and little Johnny in the\nfoot of it. But I got a dreaming and sprawling about one night, and\nsomehow, Sam got pitched on the floor, and came near breaking his arm.\nArter that, Sal said it wouldn’t do. Come along here, I’ll give ye a\nglim in a jiffy;” and so saying he lighted a candle and held it towards\nme, offering to lead the way. But I stood irresolute; when looking at a\nclock in the corner, he exclaimed “I vum it’s Sunday—you won’t see that\nharpooneer to-night; he’s come to anchor somewhere—come along then;\n_do_ come; _won’t_ ye come?”"
  },
  {
    "id": 79,
    "start_word": 7033,
    "end_word": 7075,
    "text": "I considered the matter a moment, and then up stairs we went, and I was\nushered into a small room, cold as a clam, and furnished, sure enough,\nwith a prodigious bed, almost big enough indeed for any four\nharpooneers to sleep abreast."
  },
  {
    "id": 80,
    "start_word": 7076,
    "end_word": 7119,
    "text": "“There,” said the landlord, placing the candle on a crazy old sea chest\nthat did double duty as a wash-stand and centre table; “there, make\nyourself comfortable now, and good night to ye.” I turned round from\neyeing the bed, but he had disappeared."
  },
  {
    "id": 81,
    "start_word": 7120,
    "end_word": 7246,
    "text": "Folding back the counterpane, I stooped over the bed. Though none of\nthe most elegant, it yet stood the scrutiny tolerably well. I then\nglanced round the room; and besides the bedstead and centre table,\ncould see no other furniture belonging to the place, but a rude shelf,\nthe four walls, and a papered fireboard representing a man striking a\nwhale. Of things not properly belonging to the room, there was a\nhammock lashed up, and thrown upon the floor in one corner; also a\nlarge seaman’s bag, containing the harpooneer’s wardrobe, no doubt in\nlieu of a land trunk. Likewise, there was a parcel of outlandish bone\nfish hooks on the shelf over the fire-place, and a tall harpoon\nstanding at the head of the bed."
  },
  {
    "id": 82,
    "start_word": 7247,
    "end_word": 7443,
    "text": "But what is this on the chest? I took it up, and held it close to the\nlight, and felt it, and smelt it, and tried every way possible to\narrive at some satisfactory conclusion concerning it. I can compare it\nto nothing but a large door mat, ornamented at the edges with little\ntinkling tags something like the stained porcupine quills round an\nIndian moccasin. There was a hole or slit in the middle of this mat, as\nyou see the same in South American ponchos. But could it be possible\nthat any sober harpooneer would get into a door mat, and parade the\nstreets of any Christian town in that sort of guise? I put it on, to\ntry it, and it weighed me down like a hamper, being uncommonly shaggy\nand thick, and I thought a little damp, as though this mysterious\nharpooneer had been wearing it of a rainy day. I went up in it to a bit\nof glass stuck against the wall, and I never saw such a sight in my\nlife. I tore myself out of it in such a hurry that I gave myself a kink\nin the neck."
  },
  {
    "id": 83,
    "start_word": 7444,
    "end_word": 7567,
    "text": "I sat down on the side of the bed, and commenced thinking about this\nhead-peddling harpooneer, and his door mat. After thinking some time on\nthe bed-side, I got up and took off my monkey jacket, and then stood in\nthe middle of the room thinking. I then took off my coat, and thought a\nlittle more in my shirt sleeves. But beginning to feel very cold now,\nhalf undressed as I was, and remembering what the landlord said about\nthe harpooneer’s not coming home at all that night, it being so very\nlate, I made no more ado, but jumped out of my pantaloons and boots,\nand then blowing out the light tumbled into bed, and commended myself\nto the care of heaven."
  },
  {
    "id": 84,
    "start_word": 7568,
    "end_word": 7641,
    "text": "Whether that mattress was stuffed with corn-cobs or broken crockery,\nthere is no telling, but I rolled about a good deal, and could not\nsleep for a long time. At last I slid off into a light doze, and had\npretty nearly made a good offing towards the land of Nod, when I heard\na heavy footfall in the passage, and saw a glimmer of light come into\nthe room from under the door."
  },
  {
    "id": 85,
    "start_word": 7642,
    "end_word": 8161,
    "text": "Lord save me, thinks I, that must be the harpooneer, the infernal\nhead-peddler. But I lay perfectly still, and resolved not to say a word\ntill spoken to. Holding a light in one hand, and that identical New\nZealand head in the other, the stranger entered the room, and without\nlooking towards the bed, placed his candle a good way off from me on\nthe floor in one corner, and then began working away at the knotted\ncords of the large bag I before spoke of as being in the room. I was\nall eagerness to see his face, but he kept it averted for some time\nwhile employed in unlacing the bag’s mouth. This accomplished, however,\nhe turned round—when, good heavens! what a sight! Such a face! It was\nof a dark, purplish, yellow colour, here and there stuck over with\nlarge blackish looking squares. Yes, it’s just as I thought, he’s a\nterrible bedfellow; he’s been in a fight, got dreadfully cut, and here\nhe is, just from the surgeon. But at that moment he chanced to turn his\nface so towards the light, that I plainly saw they could not be\nsticking-plasters at all, those black squares on his cheeks. They were\nstains of some sort or other. At first I knew not what to make of this;\nbut soon an inkling of the truth occurred to me. I remembered a story\nof a white man—a whaleman too—who, falling among the cannibals, had\nbeen tattooed by them. I concluded that this harpooneer, in the course\nof his distant voyages, must have met with a similar adventure. And\nwhat is it, thought I, after all! It’s only his outside; a man can be\nhonest in any sort of skin. But then, what to make of his unearthly\ncomplexion, that part of it, I mean, lying round about, and completely\nindependent of the squares of tattooing. To be sure, it might be\nnothing but a good coat of tropical tanning; but I never heard of a hot\nsun’s tanning a white man into a purplish yellow one. However, I had\nnever been in the South Seas; and perhaps the sun there produced these\nextraordinary effects upon the skin. Now, while all these ideas were\npassing through me like lightning, this harpooneer never noticed me at\nall. But, after some difficulty having opened his bag, he commenced\nfumbling in it, and presently pulled out a sort of tomahawk, and a\nseal-skin wallet with the hair on. Placing these on the old chest in\nthe middle of the room, he then took the New Zealand head—a ghastly\nthing enough—and crammed it down into the bag. He now took off his\nhat—a new beaver hat—when I came nigh singing out with fresh surprise.\nThere was no hair on his head—none to speak of at least—nothing but a\nsmall scalp-knot twisted up on his forehead. His bald purplish head now\nlooked for all the world like a mildewed skull. Had not the stranger\nstood between me and the door, I would have bolted out of it quicker\nthan ever I bolted a dinner."
  },
  {
    "id": 86,
    "start_word": 8162,
    "end_word": 8272,
    "text": "Even as it was, I thought something of slipping out of the window, but\nit was the second floor back. I am no coward, but what to make of this\nhead-peddling purple rascal altogether passed my comprehension.\nIgnorance is the parent of fear, and being completely nonplussed and\nconfounded about the stranger, I confess I was now as much afraid of\nhim as if it was the devil himself who had thus broken into my room at\nthe dead of night. In fact, I was so afraid of him that I was not game\nenough just then to address him, and demand a satisfactory answer\nconcerning what seemed inexplicable in him."
  },
  {
    "id": 87,
    "start_word": 8273,
    "end_word": 8414,
    "text": "Meanwhile, he continued the business of undressing, and at last showed\nhis chest and arms. As I live, these covered parts of him were\ncheckered with the same squares as his face; his back, too, was all\nover the same dark squares; he seemed to have been in a Thirty Years’\nWar, and just escaped from it with a sticking-plaster shirt. Still\nmore, his very legs were marked, as if a parcel of dark green frogs\nwere running up the trunks of young palms. It was now quite plain that\nhe must be some abominable savage or other shipped aboard of a whaleman\nin the South Seas, and so landed in this Christian country. I quaked to\nthink of it. A peddler of heads too—perhaps the heads of his own\nbrothers. He might take a fancy to mine—heavens! look at that tomahawk!"
  },
  {
    "id": 88,
    "start_word": 8415,
    "end_word": 8605,
    "text": "But there was no time for shuddering, for now the savage went about\nsomething that completely fascinated my attention, and convinced me\nthat he must indeed be a heathen. Going to his heavy grego, or wrapall,\nor dreadnaught, which he had previously hung on a chair, he fumbled in\nthe pockets, and produced at length a curious little deformed image\nwith a hunch on its back, and exactly the colour of a three days’ old\nCongo baby. Remembering the embalmed head, at first I almost thought\nthat this black manikin was a real baby preserved in some similar\nmanner. But seeing that it was not at all limber, and that it glistened\na good deal like polished ebony, I concluded that it must be nothing\nbut a wooden idol, which indeed it proved to be. For now the savage\ngoes up to the empty fire-place, and removing the papered fire-board,\nsets up this little hunch-backed image, like a tenpin, between the\nandirons. The chimney jambs and all the bricks inside were very sooty,\nso that I thought this fire-place made a very appropriate little shrine\nor chapel for his Congo idol."
  },
  {
    "id": 89,
    "start_word": 8606,
    "end_word": 8819,
    "text": "I now screwed my eyes hard towards the half hidden image, feeling but\nill at ease meantime—to see what was next to follow. First he takes\nabout a double handful of shavings out of his grego pocket, and places\nthem carefully before the idol; then laying a bit of ship biscuit on\ntop and applying the flame from the lamp, he kindled the shavings into\na sacrificial blaze. Presently, after many hasty snatches into the\nfire, and still hastier withdrawals of his fingers (whereby he seemed\nto be scorching them badly), he at last succeeded in drawing out the\nbiscuit; then blowing off the heat and ashes a little, he made a polite\noffer of it to the little negro. But the little devil did not seem to\nfancy such dry sort of fare at all; he never moved his lips. All these\nstrange antics were accompanied by still stranger guttural noises from\nthe devotee, who seemed to be praying in a sing-song or else singing\nsome pagan psalmody or other, during which his face twitched about in\nthe most unnatural manner. At last extinguishing the fire, he took the\nidol up very unceremoniously, and bagged it again in his grego pocket\nas carelessly as if he were a sportsman bagging a dead woodcock."
  },
  {
    "id": 90,
    "start_word": 8820,
    "end_word": 8871,
    "text": "All these queer proceedings increased my uncomfortableness, and seeing\nhim now exhibiting strong symptoms of concluding his business\noperations, and jumping into bed with me, I thought it was high time,\nnow or never, before the light was put out, to break the spell in which\nI had so long been bound."
  },
  {
    "id": 91,
    "start_word": 8872,
    "end_word": 8962,
    "text": "But the interval I spent in deliberating what to say, was a fatal one.\nTaking up his tomahawk from the table, he examined the head of it for\nan instant, and then holding it to the light, with his mouth at the\nhandle, he puffed out great clouds of tobacco smoke. The next moment\nthe light was extinguished, and this wild cannibal, tomahawk between\nhis teeth, sprang into bed with me. I sang out, I could not help it\nnow; and giving a sudden grunt of astonishment he began feeling me."
  },
  {
    "id": 92,
    "start_word": 8963,
    "end_word": 9015,
    "text": "Stammering out something, I knew not what, I rolled away from him\nagainst the wall, and then conjured him, whoever or whatever he might\nbe, to keep quiet, and let me get up and light the lamp again. But his\nguttural responses satisfied me at once that he but ill comprehended my\nmeaning."
  },
  {
    "id": 93,
    "start_word": 9016,
    "end_word": 9039,
    "text": "“Who-e debel you?”—he at last said—“you no speak-e, dam-me, I kill-e.”\nAnd so saying the lighted tomahawk began flourishing about me in the\ndark."
  },
  {
    "id": 94,
    "start_word": 9040,
    "end_word": 9053,
    "text": "“Landlord, for God’s sake, Peter Coffin!” shouted I. “Landlord! Watch!\nCoffin! Angels! save me!”"
  },
  {
    "id": 95,
    "start_word": 9054,
    "end_word": 9114,
    "text": "“Speak-e! tell-ee me who-ee be, or dam-me, I kill-e!” again growled the\ncannibal, while his horrid flourishings of the tomahawk scattered the\nhot tobacco ashes about me till I thought my linen would get on fire.\nBut thank heaven, at that moment the landlord came into the room light\nin hand, and leaping from the bed I ran up to him."
  },
  {
    "id": 96,
    "start_word": 9115,
    "end_word": 9131,
    "text": "“Don’t be afraid now,” said he, grinning again, “Queequeg here wouldn’t\nharm a hair of your head.”"
  },
  {
    "id": 97,
    "start_word": 9132,
    "end_word": 9149,
    "text": "“Stop your grinning,” shouted I, “and why didn’t you tell me that that\ninfernal harpooneer was a cannibal?”"
  },
  {
    "id": 98,
    "start_word": 9150,
    "end_word": 9183,
    "text": "“I thought ye know’d it;—didn’t I tell ye, he was a peddlin’ heads\naround town?—but turn flukes again and go to sleep. Queequeg, look\nhere—you sabbee me, I sabbee—you this man sleepe you—you sabbee?”"
  },
  {
    "id": 99,
    "start_word": 9184,
    "end_word": 9197,
    "text": "“Me sabbee plenty”—grunted Queequeg, puffing away at his pipe and\nsitting up in bed."
  },
  {
    "id": 100,
    "start_word": 9198,
    "end_word": 9300,
    "text": "“You gettee in,” he added, motioning to me with his tomahawk, and\nthrowing the clothes to one side. He really did this in not only a\ncivil but a really kind and charitable way. I stood looking at him a\nmoment. For all his tattooings he was on the whole a clean, comely\nlooking cannibal. What’s all this fuss I have been making about,\nthought I to myself—the man’s a human being just as I am: he has just\nas much reason to fear me, as I have to be afraid of him. Better sleep\nwith a sober cannibal than a drunken Christian."
  },
  {
    "id": 101,
    "start_word": 9301,
    "end_word": 9349,
    "text": "“Landlord,” said I, “tell him to stash his tomahawk there, or pipe, or\nwhatever you call it; tell him to stop smoking, in short, and I will\nturn in with him. But I don’t fancy having a man smoking in bed with\nme. It’s dangerous. Besides, I ain’t insured.”"
  },
  {
    "id": 102,
    "start_word": 9350,
    "end_word": 9382,
    "text": "This being told to Queequeg, he at once complied, and again politely\nmotioned me to get into bed—rolling over to one side as much as to\nsay—“I won’t touch a leg of ye.”"
  },
  {
    "id": 103,
    "start_word": 9383,
    "end_word": 9390,
    "text": "“Good night, landlord,” said I, “you may go.”"
  },
  {
    "id": 104,
    "start_word": 9391,
    "end_word": 9400,
    "text": "I turned in, and never slept better in my life."
  }
]

Storyboard JSON:
{
  "title": "Moby-Dick: Loomings to the Spouter-Inn",
  "adaptation_scope": "Ch. 1–3 excerpt: Ishmael’s opening reflections through his first night at the Spouter-Inn with Queequeg",
  "format": {
    "page_count": 9,
    "target_panels_per_page": 5,
    "reading_order": "left-to-right, top-to-bottom",
    "drafting_mode": "storyboard_from_plot_version"
  },
  "style_bible": {
    "visual_period": "1840s American seaports: Manhattan Battery to New Bedford whaling town, interiors of a rough waterfront inn",
    "line_and_color": "Clean ink line with etched, woodcut texture; limited winter palette (slate blues, tar blacks, whale-bone ivories, candle ambers); occasional spectral whites for the ‘phantom whale’ overlays",
    "lighting": "Cold exterior daylight and dusk; smoky lamplight interiors with chiaroscuro; strong candle pools at night; sudden lamp flare for crisis beats",
    "lettering": "Ishmael VO in a restrained literary voice—small caps italics; dialogue in rough serif with modest dialect; SFX hand-lettered, restrained",
    "recurring_motifs": [
      "Reflections and ripples of water overlaying scenes",
      "Ghost-silhouette of a hooded white whale in negative space",
      "Whale jawbone arch framing barroom moments",
      "Frosted breath in winter streets",
      "Lamp and candle halos that punctuate tension"
    ]
  },
  "characters": [
    {
      "name": "Ishmael",
      "visual_anchor": "Young, weather-worn New Englander; keen eyes; old carpet-bag in hand",
      "costume": "Dark pea coat, woolen scarf, knit cap; fingerless gloves; later, shirt-sleeves in the room",
      "expression_range": "Wry, observant, determined; shifts from wary to accepting",
      "continuity_note": "Carries the carpet-bag from packing through New Bedford arrival; VO captions in first person throughout"
    },
    {
      "name": "Landlord Peter Coffin (aka Jonah at bar)",
      "visual_anchor": "Lean, grinning innkeeper behind a bar set in a whale’s jawbone",
      "costume": "Rolled shirt-sleeves, tarry apron, short waistcoat; later a rough coat when carrying a lamp",
      "expression_range": "Genial, sly, practical; quick to mediate",
      "continuity_note": "Always near the bar downstairs; later appears upstairs with a lamp; occasionally whittles a toothpick"
    },
    {
      "name": "Queequeg",
      "visual_anchor": "Powerful, tattooed South Sea islander; scalp-knot; calm, methodical manner",
      "costume": "Shaggy poncho; bare tattooed chest/arms when indoors; carries tomahawk-pipe; small idol and a preserved head as curio",
      "expression_range": "Composed, courteous; momentary startle at intrusion; then warm and inviting",
      "continuity_note": "Idol set briefly at fireplace for rite, then bagged; tomahawk shown as pipe and then stashed before sleep"
    },
    {
      "name": "Jonah (bartender identity of Coffin for service beats)",
      "visual_anchor": "Same as Peter Coffin, specifically framed beneath the jawbone arch pouring drinks",
      "costume": "Bar apron, sleeves rolled, brimmers in hand",
      "expression_range": "Brisk, service-smile, unflappable",
      "continuity_note": "Use ‘Jonah at service’ vibe during Grampus crew storm-in moments"
    },
    {
      "name": "Bulkington",
      "visual_anchor": "Tall, broad-shouldered, reserved sailor, coat crusted with ice",
      "costume": "Long dark coat, sea boots; hat low over brow",
      "expression_range": "Quiet, distant, steadfast",
      "continuity_note": "Only glimpsed in the doorway departing amid revelry"
    }
  ],
  "pages": [
    {
      "page_number": 1,
      "page_summary": "Ishmael’s cure for spleen draws him to the water; the Battery’s sea-gazers; meditation wedded to water; he chooses the sailor’s berth.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B1"
          ],
          "driver_character": "Ishmael",
          "character_action": "Walks from city streets toward the waterfront, passing coffins and a funeral, deciding to go to sea",
          "beat": "Ishmael chooses the sea to cure his spleen",
          "shot": "medium",
          "image_prompt": "A damp November city street; Ishmael strides with an old carpet-bag, passing a shop window stacked with plain wooden coffins and a distant funeral procession. Harbor masts ghost the horizon. Leave clean negative space in the upper-left for a later caption; keep faces and key motion out of that area.",
          "caption_zone": "top_left",
          "caption": "Call me Ishmael. …I account it high time to get to sea as soon as I can.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Establish carpet-bag; cool, gray palette; breath faintly visible.",
          "lettering_notes": "Open with iconic line in Ishmael VO; short second sentence follows after an ellipsis.",
          "adaptation_note": "Uses the preserved opening lines; compresses the catalogue of hypos into motion."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B2"
          ],
          "driver_character": "Ishmael",
          "character_action": "Joins and observes crowds gazing out over the seawall",
          "beat": "Manhattaners gazing at the water",
          "shot": "wide",
          "image_prompt": "Long horizontal view along the Battery seawall in wintry light; rows of bundled figures stare toward anchored ships and gray water; Ishmael’s silhouette among them. Leave clean negative space in the upper-center for a later caption; avoid covering clustered heads along the railing.",
          "caption_zone": "top_center",
          "caption": "Posted like silent sentinels all around the town, stand thousands upon thousands of mortal men fixed in ocean reveries.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Convey breadth with a panoramic composition; Ishmael small within the mass.",
          "lettering_notes": "One long VO line centered to echo the panel width.",
          "adaptation_note": "Single wide shot per storyboard guidance."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B3"
          ],
          "driver_character": "Ishmael",
          "character_action": "Walks as watery reflections overlap his figure in a contemplative drift",
          "beat": "Meditation and water; the ungraspable phantom of life",
          "shot": "medium",
          "image_prompt": "Soft montage: Ishmael’s profile overlaps moving water—stream ripples fading into ocean swell; faint prairie horizon implied behind. Leave clean negative space in the upper-right; keep Ishmael’s face and water highlights clear elsewhere.",
          "caption_zone": "top_right",
          "caption": "Yes, as every one knows, meditation and water are wedded for ever.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Begin motif of water overlays; no hard cutaways.",
          "lettering_notes": "Short VO; italic to signal reflection.",
          "adaptation_note": "Selective VO preserves Melville’s thesis line."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B3"
          ],
          "driver_character": "Ishmael",
          "character_action": "Continues the reflective walk, eyes on the harbor’s sheen",
          "beat": "Meditation and water; the ungraspable phantom of life (continued)",
          "shot": "close",
          "image_prompt": "Close on Ishmael’s eye catching wavy light; the water’s reflection distorts across his cheek. Leave clean negative space bottom-right; avoid covering the eye highlight.",
          "caption_zone": "bottom_right",
          "caption": "It is the image of the ungraspable phantom of life; and this is the key to it all.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Echo water motif; keep tone quiet.",
          "lettering_notes": "Keep caption compact for pacing.",
          "adaptation_note": "Second key VO from B3 to complete the theme articulation."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B4"
          ],
          "driver_character": "Ishmael",
          "character_action": "Shoulders a bag on a wharf under rigging, ready to ship as a common sailor",
          "beat": "Why he ships before the mast",
          "shot": "medium",
          "image_prompt": "Deck-level angle: coils of rope, tar pots, and a gangplank; Ishmael with carpet-bag slung, glancing up at rigging. Leave clean negative space bottom-left; keep hands and bag clear.",
          "caption_zone": "bottom_left",
          "caption": "No, when I go to sea, I go as a simple sailor…",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Wharf/ship imagery begins; keep bag consistent.",
          "lettering_notes": "VO clipped to the essential identity line.",
          "adaptation_note": "Starts B4; further aphorism follows next page."
        }
      ]
    },
    {
      "page_number": 2,
      "page_summary": "Aphorisms about hardship and pay; fate steers Ishmael to whaling; arrival in cold New Bedford with the packet missed.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B4"
          ],
          "driver_character": "Ishmael",
          "character_action": "Takes orders good-humoredly on deck while a mate barks and coins change hands",
          "beat": "Why he ships before the mast (continued)",
          "shot": "medium",
          "image_prompt": "A mate’s pointing hand orders Ishmael toward a coil; an inset of rough coins dropping into a palm. Leave clean negative space in the upper-right; keep the coin inset unobstructed.",
          "caption_zone": "top_right",
          "caption": "…so the universal thump is passed round, and all hands should be content.",
          "dialogue": [],
          "sfx": [
            "CLINK"
          ],
          "continuity_notes": "Interleave the pay inset for clarity.",
          "lettering_notes": "Short VO over action; light SFX for coins.",
          "adaptation_note": "Pairs ethos with the ‘pay vs. paying’ joke implicitly."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B5"
          ],
          "driver_character": "Ishmael",
          "character_action": "Packs a small carpet-bag at a table, eyes distant",
          "beat": "Fate and the lure of the whale",
          "shot": "medium",
          "image_prompt": "Room interior: Ishmael folds shirts into a worn carpet-bag; a spectral poster-like rectangle of blank ‘playbill’ space hovers behind him as a visual motif (no readable text). Leave clean negative space top-left; avoid covering the bag and Ishmael’s hands.",
          "caption_zone": "top_left",
          "caption": "Grand Contested Election… WHALING VOYAGE BY ONE ISHMAEL.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "No readable text in art; evoke playbill as a blank shape only.",
          "lettering_notes": "All-caps emphasis on ‘WHALING VOYAGE’ within VO to echo playbill rhythm.",
          "adaptation_note": "Captures the ‘playbill of Providence’ gag as VO."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B5"
          ],
          "driver_character": "Ishmael",
          "character_action": "Pauses, staring toward an imagined horizon through a frost-streaked pane",
          "beat": "Fate and the lure of the whale (continued)",
          "shot": "close",
          "image_prompt": "Ishmael’s face reflected in a cold window; beyond it, a faint ghost-ocean; leave clean negative space bottom-center; keep reflection highlights clear.",
          "caption_zone": "bottom_center",
          "caption": "Call it free will if you please—the Fates had the tiller and steered me to whaling.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Begin ghost-sea overlay; establish fatalistic tone.",
          "lettering_notes": "Keep VO concise and aphoristic.",
          "adaptation_note": "Compresses units 12–14 into a single reflective line."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B5"
          ],
          "driver_character": "Ishmael",
          "character_action": "Imagines the vast white shape of a whale looming over him as he cinches the bag",
          "beat": "Fate and the lure of the whale (continued)",
          "shot": "wide",
          "image_prompt": "Room dissolves into a negative-space silhouette of a hooded, snow-white whale towering like a hill behind Ishmael. Leave clean negative space upper-right; keep whale silhouette uninterrupted.",
          "caption_zone": "top_right",
          "caption": "…one grand hooded phantom, like a snow hill in the air.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Reinforce phantom-whale motif; keep it wordless in art.",
          "lettering_notes": "Single VO fragment to land the image.",
          "adaptation_note": "Delivers the iconic image per guidance."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B6"
          ],
          "driver_character": "Ishmael",
          "character_action": "Steps onto a cold New Bedford street, realizing he has missed the boat",
          "beat": "Arrival in New Bedford; missed Nantucket packet",
          "shot": "establishing",
          "image_prompt": "Snow-dusted quay street at night; Ishmael with frosted breath studies a notice board by a dark dock office (no readable text). Leave clean negative space bottom-left; keep Ishmael’s face clear of that area.",
          "caption_zone": "bottom_left",
          "caption": "Saturday night in December—and the Nantucket packet gone till Monday.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Cold palette; establish two-night layover without readable signage.",
          "lettering_notes": "Plain VO to carry the missed-packet info.",
          "adaptation_note": "Uses VO rather than readable sign per clean-art rule."
        }
      ]
    },
    {
      "page_number": 3,
      "page_summary": "Low funds push Ishmael toward the docks; a misstep into a church; the Spouter-Inn beckons and he goes in.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B7"
          ],
          "driver_character": "Ishmael",
          "character_action": "Looks toward the dark harbor, thinking of Nantucket’s whaling primacy",
          "beat": "Why only a Nantucket craft will do",
          "shot": "medium",
          "image_prompt": "Ishmael framed against a harbor’s black water, faint ghost-vignettes of canoes chasing whales in the sky (no text). Leave clean negative space top-center; keep vignette silhouettes unblocked.",
          "caption_zone": "top_center",
          "caption": "Nantucket—the Tyre of this Carthage.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Subtle lore nod; keep overlays minimal.",
          "lettering_notes": "Short, epigrammatic VO.",
          "adaptation_note": "Preserves the crisp Nantucket preference."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B8"
          ],
          "driver_character": "Ishmael",
          "character_action": "Trudges past a warm, pricey inn and angles down toward the docks",
          "beat": "Cold streets and the wrong door",
          "shot": "wide",
          "image_prompt": "Icy street with glowing, genteel inn windows on one side; wind-driven snow; Ishmael turns away toward darker lanes. Leave clean negative space upper-left; avoid faces in that zone.",
          "caption_zone": "top_left",
          "caption": "Money short, I left the warm dear inns and steered dockward for the cheap ones.",
          "dialogue": [],
          "sfx": [
            "WIND"
          ],
          "continuity_notes": "Emphasize chill and thrift-driven choice.",
          "lettering_notes": "Plain VO; subtle WIND SFX.",
          "adaptation_note": "Covers units 20–21 in motion."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B8"
          ],
          "driver_character": "Ishmael",
          "character_action": "Shoulders through a low, smoky doorway and stumbles over an ash-box",
          "beat": "Cold streets and the wrong door (continued)",
          "shot": "medium",
          "image_prompt": "Dim threshold; Ishmael half-trips on a battered ash-box; smoke curls in the entry. Leave clean negative space bottom-right; keep the stumble clear.",
          "caption_zone": "bottom_right",
          "caption": "Blundering into a low, smoky place, I near broke my shins on an ash-box.",
          "dialogue": [],
          "sfx": [
            "THUNK",
            "COUGH"
          ],
          "continuity_notes": "Keep comic misstep readable; no signs.",
          "lettering_notes": "Small SFX near the box and Ishmael.",
          "adaptation_note": "Preserves the comic misstep beat."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B8"
          ],
          "driver_character": "Ishmael",
          "character_action": "Realizes he has entered a Black church mid-service and quietly retreats",
          "beat": "Cold streets and the wrong door (continued)",
          "shot": "medium",
          "image_prompt": "View from the back: congregants and a shadowed preacher’s silhouette; Ishmael halfway turned in retreat at the door, respectful and small. Leave clean negative space top-right; keep congregants’ faces unobscured.",
          "caption_zone": "top_right",
          "caption": "Finding I had stepped into a Black church at worship, I backed out as softly as I could.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Respectful staging—focus on Ishmael’s mistake, not caricature.",
          "lettering_notes": "Quiet VO only.",
          "adaptation_note": "Keeps the misdirection without lingering."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B9"
          ],
          "driver_character": "Ishmael",
          "character_action": "Studies a creaking inn sign and decides to enter",
          "beat": "The Spouter-Inn exterior",
          "shot": "establishing",
          "image_prompt": "Bleak corner inn; a large swinging sign with a crude sperm whale emblem creaks in the wind (no readable text); a dim window glow. Leave clean negative space bottom-left; avoid covering Ishmael at the threshold.",
          "caption_zone": "bottom_left",
          "caption": "The Spouter-Inn—Peter Coffin; but no more of this blubbering now, we are going a-whaling…",
          "dialogue": [],
          "sfx": [
            "CREEEAK"
          ],
          "continuity_notes": "Exterior establishes ‘Spouter’ without legible letters.",
          "lettering_notes": "Run-on VO bridges tone to action.",
          "adaptation_note": "Exterior arrival per guidance; uses the witty bridge line."
        }
      ]
    },
    {
      "page_number": 4,
      "page_summary": "Inside the Spouter-Inn: the inscrutable painting; the weapons and whale-jaw bar; the landlord’s crowded-house solution.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B10"
          ],
          "driver_character": "Ishmael",
          "character_action": "Opens a small shutter to cast crosslight on a vast, smoked canvas and peers at it",
          "beat": "The inscrutable painting",
          "shot": "wide",
          "image_prompt": "A dim entry with tarry wainscots; a huge, blackened canvas fills the wall; Ishmael small before it, a sliver of cold light cutting across. Leave clean negative space top-left; keep painting’s central mass clear.",
          "caption_zone": "top_left",
          "caption": "At first I could scarce make it out—did it not faintly resemble a gigantic fish?",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "No labels or text on the canvas; mood over detail.",
          "lettering_notes": "One short VO, leading to the ‘final theory’ next.",
          "adaptation_note": "Sets painting’s enigma without enumerating guesses."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B10"
          ],
          "driver_character": "Ishmael",
          "character_action": "Leans closer, realizing the whale-and-masts image",
          "beat": "The inscrutable painting (continued)",
          "shot": "close",
          "image_prompt": "Detail of the canvas: three mast-stubs and a looming black mass suggested in smoke and smear; Ishmael’s fingers at the frame edge. Leave clean negative space bottom-right; keep mast-stubs visible.",
          "caption_zone": "bottom_right",
          "caption": "At last I saw it: an exasperated whale in the act of impaling himself upon the three mast-heads.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Anchor three mast stubs for clarity.",
          "lettering_notes": "Deliver the payoff line cleanly.",
          "adaptation_note": "Jumps to Ishmael’s final reading as advised."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B11"
          ],
          "driver_character": "Ishmael",
          "character_action": "Moves into the public room, taking in the wall of weapons",
          "beat": "Weapons wall and Jonah at the bar",
          "shot": "wide",
          "image_prompt": "Low-beamed room; racks of clubs, spears, kinked harpoons and ‘storied irons’; cracked cases; Ishmael enters frame-left. Leave clean negative space upper-center; avoid covering a standout twisted harpoon.",
          "caption_zone": "top_center",
          "caption": "Heathenish clubs and storied irons lined the walls—omens enough for any man.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Plant weapon props for later whaling ambiance.",
          "lettering_notes": "VO only; keep it atmospheric.",
          "adaptation_note": "Compresses wall-lore into one evocative line."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B11"
          ],
          "driver_character": "Ishmael",
          "character_action": "Steps beneath a whale’s jawbone arch as the landlord tends bar",
          "beat": "Weapons wall and Jonah at the bar (continued)",
          "shot": "medium",
          "image_prompt": "Bar counter set under a great whale jawbone arch; bottles behind; the landlord (Jonah) polishing a marked tumbler (no readable marks). Leave clean negative space bottom-left; keep Jonah’s face and the jaw curve clear.",
          "caption_zone": "bottom_left",
          "caption": "Under a whale’s jaw for a bar, Jonah kept cheating tumblers and measures.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Establish ‘Jonah’ and the jawbone bar angle for reuse.",
          "lettering_notes": "Short VO; let the prop tell the joke.",
          "adaptation_note": "Cheating-glass gag implied by a faint etch, not legible."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B12"
          ],
          "driver_character": "Landlord Peter Coffin",
          "character_action": "Leans in with a knowing grin, proposing the only bed: share with a harpooneer",
          "beat": "House full; share a harpooneer’s blanket",
          "shot": "medium",
          "image_prompt": "By the bar, the landlord gestures with a thumb upstairs; Ishmael weighs the offer, doubtful. Leave clean negative space top-right; avoid covering faces and the gesturing hand.",
          "caption_zone": "top_right",
          "caption": "The house was full, said he; I must share a harpooneer’s blanket if I would lie warm.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "No invented dialogue; set the dilemma plainly.",
          "lettering_notes": "One concise VO to set stakes; hold dialogue for later beats.",
          "adaptation_note": "Converts the dialogue turn into Ishmael VO per hard rule against invented speech."
        }
      ]
    },
    {
      "page_number": 5,
      "page_summary": "A cold supper and rumors of the harpooneer; Ishmael waits; the Grampus crew erupts in and revels.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B13"
          ],
          "driver_character": "Ishmael",
          "character_action": "Eats a frigid meal by two tallow candles while the landlord bends to whisper",
          "beat": "Frigid supper and harpooneer rumor",
          "shot": "medium",
          "image_prompt": "Bare supper room; shivering diners clustered; heavy dumplings on tin plates; two smoky candles; landlord aside to Ishmael. Leave clean negative space bottom-left; keep whisper faces visible.",
          "caption_zone": "bottom_left",
          "caption": "We fell to a cold supper; the landlord added, “…he eats nothing but steaks, and he likes ’em rare.”",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Blue-cold palette; candle halos warm faces only.",
          "lettering_notes": "Caption carries the quoted gag line.",
          "adaptation_note": "Compresses meal and rumor into one image with one line."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B13"
          ],
          "driver_character": "Ishmael",
          "character_action": "Glances toward the door, uneasy, as plates clatter",
          "beat": "Frigid supper and harpooneer rumor (continued)",
          "shot": "close",
          "image_prompt": "Ishmael’s wary eyes beyond a forkful of dumpling; door beyond in shallow focus. Leave clean negative space top-center; avoid obscuring Ishmael’s eyes.",
          "caption_zone": "top_center",
          "caption": "I whispered to Coffin—was that the harpooneer come in?",
          "dialogue": [],
          "sfx": [
            "CLATTER"
          ],
          "continuity_notes": "Seed suspense on the door; keep others anonymous.",
          "lettering_notes": "Short, inquisitive VO; small SFX for cutlery.",
          "adaptation_note": "Carries the ‘whisper’ beat as VO."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B14"
          ],
          "driver_character": "Ishmael",
          "character_action": "Returns to the barroom and settles to watch the door",
          "beat": "Waiting in the barroom; suspicions",
          "shot": "medium",
          "image_prompt": "Ishmael on a carved wooden settle near a dim lamp, eyes fixed on the entrance; scrimshawed table beside. Leave clean negative space bottom-right; keep his gaze line clear.",
          "caption_zone": "bottom_right",
          "caption": "He was not yet in; I would wait and let him undress first, and so take the man’s measure.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Bench and scrimshaw table established; low light.",
          "lettering_notes": "Calm VO to set intention.",
          "adaptation_note": "Uses unit 47’s plan as VO."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B15"
          ],
          "driver_character": "Jonah",
          "character_action": "Rushes to pour brimmers as ice-crusted sailors from the Grampus flood in",
          "beat": "The Grampus’s crew storms in",
          "shot": "wide",
          "image_prompt": "Barroom packed with roaring sailors in ice-crusted coats; Jonah under the jawbone arch pouring foaming brimmers; Ishmael half-turned by the rush. Leave clean negative space top-left; keep the jaw arch and Jonah unobstructed.",
          "caption_zone": "top_left",
          "caption": "Word ran the Grampus was in, and in rolled her crew, clamorous and frost-stiff.",
          "dialogue": [],
          "sfx": [
            "SLAM",
            "CHEER",
            "SCRAPE"
          ],
          "continuity_notes": "Reuse bar angle from earlier; raise energy.",
          "lettering_notes": "Loud SFX layered behind; VO sets the beat.",
          "adaptation_note": "Condenses 49–50 into a single kinetic image."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B15"
          ],
          "driver_character": "Jonah",
          "character_action": "Keeps the drink flowing as the capering escalates",
          "beat": "The Grampus’s crew storms in (continued)",
          "shot": "medium",
          "image_prompt": "Sailors mid-caper, mugs aloft; Jonah splashing another brimmer; Ishmael squeezed to the side. Leave clean negative space bottom-left; keep raised glasses free.",
          "caption_zone": "bottom_left",
          "caption": "The liquor mounted, and with it the capering.",
          "dialogue": [],
          "sfx": [
            "THUMP",
            "HA!"
          ],
          "continuity_notes": "Maintain packed room geography.",
          "lettering_notes": "Short VO; boisterous but not cluttered with dialogue.",
          "adaptation_note": "Uses 51 as VO over motion."
        }
      ]
    },
    {
      "page_number": 6,
      "page_summary": "Bulkington slips out; the room quiets; Ishmael refuses to share a bed and fails at the bench plan.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B16"
          ],
          "driver_character": "Ishmael",
          "character_action": "Notices a tall, quiet sailor slip through the door to the winter night as others call after him",
          "beat": "Bulkington’s quiet exit; quiet returns",
          "shot": "medium",
          "image_prompt": "Open doorway with snow beyond; Bulkington’s tall silhouette steps out; hands reach after from the crowd. Leave clean negative space top-right; keep Bulkington’s silhouette clear.",
          "caption_zone": "top_right",
          "caption": "They shouted, “Bulkington! Bulkington! where’s Bulkington?”—but the tall fellow slipped away.",
          "dialogue": [],
          "sfx": [
            "WHOOSH"
          ],
          "continuity_notes": "Make Bulkington imposing and reserved; brief view only.",
          "lettering_notes": "Caption carries the quoted shout as Ishmael’s report.",
          "adaptation_note": "Seeds Bulkington while preserving Ishmael VO."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B16"
          ],
          "driver_character": "Ishmael",
          "character_action": "Sits back as the barroom settles after the uproar",
          "beat": "Bulkington’s quiet exit; quiet returns (continued)",
          "shot": "medium",
          "image_prompt": "Spent sailors slouch; lamps burn low; Ishmael’s intent returns. Leave clean negative space bottom-center; avoid covering Ishmael’s face.",
          "caption_zone": "bottom_center",
          "caption": "After the orgy came a lull, and back came my plan.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Reset mood; prepare for lodging dilemma.",
          "lettering_notes": "Short VO bridges scenes.",
          "adaptation_note": "Uses 53 to pace down."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B17"
          ],
          "driver_character": "Ishmael",
          "character_action": "Declares he won’t bed with a stranger and eyes the long bench",
          "beat": "Ishmael refuses to share; tries the bench",
          "shot": "medium",
          "image_prompt": "Barroom corner bench; Ishmael measuring it with a glance; a cold window drafts. Leave clean negative space top-left; keep Ishmael and bench clear.",
          "caption_zone": "top_left",
          "caption": "No man prefers to sleep two in a bed.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "The bench is plain, rough, knotty.",
          "lettering_notes": "Aphoristic VO to sell the comic principle.",
          "adaptation_note": "States objection crisply."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B18"
          ],
          "driver_character": "Landlord Peter Coffin",
          "character_action": "Good-naturedly planes the bench for Ishmael",
          "beat": "Planing the bench; drafts defeat him",
          "shot": "medium",
          "image_prompt": "The landlord shaves curls off the bench with a hand plane; Ishmael hovers, hopeful; shavings curl and fall. Leave clean negative space bottom-right; keep flying curls visible.",
          "caption_zone": "bottom_right",
          "caption": "To humor me, Coffin planed me a bed along the bench.",
          "dialogue": [],
          "sfx": [
            "SKRRT SKRRT"
          ],
          "continuity_notes": "Whittled toothpick may appear behind the ear; keep stove glow nearby.",
          "lettering_notes": "Gentle SFX; keep VO light.",
          "adaptation_note": "First half of the bench gag."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B18"
          ],
          "driver_character": "Ishmael",
          "character_action": "Tries to lie down but shivers as a draft cuts across him; gives up",
          "beat": "Planing the bench; drafts defeat him (continued)",
          "shot": "medium",
          "image_prompt": "Ishmael awkwardly stretched on the too-short bench; a guttering candle flame leans from a draft; his feet dangle. Leave clean negative space top-center; keep his face and the flame visible.",
          "caption_zone": "top_center",
          "caption": "It proved too short, and the draughts cut me to the quick.",
          "dialogue": [],
          "sfx": [
            "Brrr…"
          ],
          "continuity_notes": "Exaggerate draft curls for humor.",
          "lettering_notes": "Quiet, small SFX; VO lands the failure.",
          "adaptation_note": "Concludes the comic trial-and-error."
        }
      ]
    },
    {
      "page_number": 7,
      "page_summary": "Midnight nears: the ‘head’ misunderstanding; confrontation and the landlord’s true explanation.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B19"
          ],
          "driver_character": "Ishmael",
          "character_action": "Questions the landlord about the harpooneer’s lateness",
          "beat": "The late harpooneer and the ‘head’ puzzle",
          "shot": "medium",
          "image_prompt": "Clock near midnight on the wall (no readable numerals); landlord whittling a toothpick; Ishmael frowning. Leave clean negative space bottom-left; keep clock and faces clear.",
          "caption_zone": "bottom_left",
          "caption": "Near midnight I asked what held my bedfellow abroad.",
          "dialogue": [
            {
              "speaker": "Landlord",
              "text": "Can't sell his head."
            },
            {
              "speaker": "Ishmael",
              "text": "Can't sell his head?"
            }
          ],
          "sfx": [],
          "continuity_notes": "Keep volley tight; anchor both speakers in frame.",
          "lettering_notes": "Two quick balloons; VO anchors the moment.",
          "adaptation_note": "Key setup line delivered as dialogue with Ishmael’s bridging VO."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B19"
          ],
          "driver_character": "Ishmael",
          "character_action": "Presses the landlord for clarity and gets the mischievous answer",
          "beat": "The late harpooneer and the ‘head’ puzzle (continued)",
          "shot": "close",
          "image_prompt": "Shot–reverse-shot feel: Ishmael’s incredulous look; landlord’s sly grin. Leave clean negative space top-right; keep mouths and eyes free.",
          "caption_zone": "top_right",
          "caption": "His next answer near took me aback.",
          "dialogue": [
            {
              "speaker": "Ishmael",
              "text": "With what?"
            },
            {
              "speaker": "Landlord",
              "text": "With heads, to be sure!"
            }
          ],
          "sfx": [],
          "continuity_notes": "Comic timing: half-beat between balloons.",
          "lettering_notes": "Stagger balloons for rhythm; VO above as set-up.",
          "adaptation_note": "Delivers the punchline exchange per guidance."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B20"
          ],
          "driver_character": "Ishmael",
          "character_action": "Squares up, demanding a sober explanation",
          "beat": "Confrontation and explanation: embalmed heads",
          "shot": "medium",
          "image_prompt": "Ishmael stern, finger planting the table; landlord pausing his whittle. Leave clean negative space bottom-center; keep pointing hand visible.",
          "caption_zone": "bottom_center",
          "caption": "Enough, said I; speak out and truly.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Mini courtroom posture; raise stakes before reveal.",
          "lettering_notes": "Commanding VO; no dialogue in this beat.",
          "adaptation_note": "Captures unit 74 stance without inventing speech."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B20"
          ],
          "driver_character": "Landlord Peter Coffin",
          "character_action": "Explains, pantomiming a string of heads",
          "beat": "Confrontation and explanation: embalmed heads (continued)",
          "shot": "medium",
          "image_prompt": "Landlord gestures as if holding a line of round weights like onions, matter-of-fact; Ishmael listens, half-appalled. Leave clean negative space top-left; keep the pantomime clear.",
          "caption_zone": "top_left",
          "caption": "…he bought up a lot of ’balmed New Zealand heads…",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "No actual heads shown—just the gesture.",
          "lettering_notes": "Quoted fragment as VO; dry delivery.",
          "adaptation_note": "States the practical explanation succinctly."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B20"
          ],
          "driver_character": "Ishmael",
          "character_action": "Recoils morally, imagining the worst of the unseen man",
          "beat": "Confrontation and explanation: embalmed heads (continued)",
          "shot": "close",
          "image_prompt": "Ishmael’s face in harsh lamplight, jaw set; faint ghost of a row of blank ovals (no faces) behind him. Leave clean negative space bottom-right; keep his expression clear.",
          "caption_zone": "bottom_right",
          "caption": "Cannibal traffic! I took it for good evidence the harpooneer was stark mad.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Bias reads clearly; prepare for reversal later.",
          "lettering_notes": "Firm VO to button the misunderstanding.",
          "adaptation_note": "Uses unit 76’s recoil in Ishmael’s voice."
        }
      ]
    },
    {
      "page_number": 8,
      "page_summary": "Upstairs to the prodigious bed; Ishmael inventories the room, turns in; footsteps in the night; Queequeg appears.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B21"
          ],
          "driver_character": "Landlord Peter Coffin",
          "character_action": "Leads Ishmael upstairs by candle and boasts of the bed’s size",
          "beat": "Upstairs to the prodigious bed",
          "shot": "wide",
          "image_prompt": "Narrow staircase; landlord ahead with a guttering candle; at the top, a chilly room reveals an outsized bed. Leave clean negative space top-center; keep candle halo and bed silhouette clear.",
          "caption_zone": "top_center",
          "caption": "Come, says Coffin—and by candle he showed me a prodigious bed.",
          "dialogue": [],
          "sfx": [
            "CREAK"
          ],
          "continuity_notes": "Exaggerate bed scale against Ishmael.",
          "lettering_notes": "Simple VO; soft stair SFX optional.",
          "adaptation_note": "Transitions to the chamber per plan."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B22"
          ],
          "driver_character": "Ishmael",
          "character_action": "Inspects the room: harpoon, hooks, hammock, bag—tries on a shaggy ‘door-mat’ poncho",
          "beat": "Room inventory and the door-mat poncho",
          "shot": "medium",
          "image_prompt": "Cold chamber: harpoon at bedhead, bone hooks on a shelf, sea chest; Ishmael half-grinning in a shaggy poncho before a small mirror. Leave clean negative space bottom-left; keep harpoon and poncho clear.",
          "caption_zone": "bottom_left",
          "caption": "A hammock, a bag, bone hooks—and a harpoon; that shaggy ‘door-mat’ was a poncho after all.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Plant prop positions for continuity; poncho gag lands visually.",
          "lettering_notes": "Inventory VO, brisk and light.",
          "adaptation_note": "Seeds room props per requirements."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B22"
          ],
          "driver_character": "Ishmael",
          "character_action": "Blows out the candle and tumbles into bed against the cold",
          "beat": "Room inventory and the door-mat poncho (continued)",
          "shot": "medium",
          "image_prompt": "Ishmael seated on the vast bed, puffing the candle; blankets heap up; frosty window beyond. Leave clean negative space top-right; keep the candle flame visible.",
          "caption_zone": "top_right",
          "caption": "Too cold for parley; trusting the landlord, I turned in.",
          "dialogue": [],
          "sfx": [
            "FWIP"
          ],
          "continuity_notes": "Chill persists; lamp out sets up darkness for intrusion.",
          "lettering_notes": "Tiny SFX for snuffing; VO concise.",
          "adaptation_note": "Prepares for the midnight entrance."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B23"
          ],
          "driver_character": "Ishmael",
          "character_action": "Awakens to heavy footfalls and a glow creeping under the door",
          "beat": "Footsteps; light under the door",
          "shot": "silent",
          "image_prompt": "Dark room; strip of warm light cutting across floorboards from under the door; Ishmael’s open eyes gleam from bed. Leave clean negative space bottom-left; keep the light-strip unobstructed.",
          "caption_zone": "bottom_left",
          "caption": "A slow, heavy footstep—and light beneath the door.",
          "dialogue": [],
          "sfx": [
            "STEP… STEP…"
          ],
          "continuity_notes": "Emphasize suspense; no faces at the door yet.",
          "lettering_notes": "Sparse SFX; one tight VO line.",
          "adaptation_note": "Silent-feel panel per suspense cue, but includes required caption."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B24"
          ],
          "driver_character": "Queequeg",
          "character_action": "Enters calm, sets a candle, unpacks a New Zealand head and tomahawk; tattoos revealed",
          "beat": "Queequeg revealed; Ishmael’s terror",
          "shot": "medium",
          "image_prompt": "Chiaroscuro: Queequeg kneels, tattooed from face to torso, setting down a preserved head and tomahawk; Ishmael half-risen in bed, eyes wide. Leave clean negative space top-center; keep Queequeg’s face and the props clear.",
          "caption_zone": "top_center",
          "caption": "In the candle’s glare stood a tattooed stranger with a New Zealand head and tomahawk—an “abominable savage,” thought I.",
          "dialogue": [],
          "sfx": [],
          "continuity_notes": "Queequeg’s manner stays calm and methodical; no caricature.",
          "lettering_notes": "Quoted phrase within Ishmael VO marks his bias.",
          "adaptation_note": "Introduces Queequeg visually; fear remains internal."
        }
      ]
    },
    {
      "page_number": 9,
      "page_summary": "Queequeg’s brief rite; comic shock in bed; crisis and mediation; acceptance and sleep.",
      "panels": [
        {
          "panel_number": 1,
          "graphic_beat_ids": [
            "B25"
          ],
          "driver_character": "Queequeg",
          "character_action": "Sets a small idol in the fireplace, lights shavings, offers a biscuit, and chants",
          "beat": "Idol ritual at the fireplace",
          "shot": "medium",
          "image_prompt": "Sooty bricks and andirons; a small idol set between them; a tiny blaze of shavings; Queequeg bowing with a biscuit in hand; Ishmael peering from the bed. Leave clean negative space bottom-right; keep idol and flame visible.",
          "caption_zone": "bottom_right",
          "caption": "Calmly he set an idol to the grate, lit shavings, offered a biscuit, and muttered a guttural prayer.",
          "dialogue": [],
          "sfx": [
            "TIK-TIK",
            "MURMUR"
          ],
          "continuity_notes": "Idol visible only in this brief rite; to be bagged afterward.",
          "lettering_notes": "Soft SFX; respectful VO cadence.",
          "adaptation_note": "Shows the rite succinctly and without mockery."
        },
        {
          "panel_number": 2,
          "graphic_beat_ids": [
            "B26"
          ],
          "driver_character": "Queequeg",
          "character_action": "Lights his tomahawk-pipe, snuffs the candle, and springs into bed unaware of Ishmael",
          "beat": "Tomahawk-pipe and sudden bedmate",
          "shot": "medium",
          "image_prompt": "Glow from the tomahawk-pipe bowl; Queequeg’s silhouette arcs into the vast bed; bedclothes fly; the room plunges dark. Leave clean negative space top-left; keep the pipe-glow and motion arc clear.",
          "caption_zone": "top_left",
          "caption": "He lit his tomahawk-pipe, snuffed the light, and sprang into bed as if alone.",
          "dialogue": [],
          "sfx": [
            "FWIP",
            "WHUMP"
          ],
          "continuity_notes": "Convey kinetic shock; keep pipe clearly a smoking tool.",
          "lettering_notes": "Punchy SFX; VO clipped.",
          "adaptation_note": "Prioritizes action clarity per storyboard note."
        },
        {
          "panel_number": 3,
          "graphic_beat_ids": [
            "B27"
          ],
          "driver_character": "Ishmael",
          "character_action": "Rolls away and shouts for the landlord as Queequeg brandishes the tomahawk; the landlord bursts in with a lamp",
          "beat": "Threats in the dark; landlord’s rescue",
          "shot": "wide",
          "image_prompt": "Door flung open; landlord with a bright lamp; Ishmael clutching at him; Queequeg seated up in bed with tomahawk raised in confusion. Leave clean negative space bottom-right; keep all three faces readable.",
          "caption_zone": "bottom_right",
          "caption": "I rolled away and shouted for the landlord.",
          "dialogue": [
            {
              "speaker": "Ishmael",
              "text": "Landlord, for God’s sake!"
            },
            {
              "speaker": "Queequeg",
              "text": "Who-e debel you? … I kill-e!"
            }
          ],
          "sfx": [
            "BANG"
          ],
          "continuity_notes": "Contrast darkness and lamp flare; miscommunication visible.",
          "lettering_notes": "Ishmael’s cry big but not overpowering; Queequeg’s line in distinct but legible dialect font.",
          "adaptation_note": "Keeps two short lines total, as guided."
        },
        {
          "panel_number": 4,
          "graphic_beat_ids": [
            "B28"
          ],
          "driver_character": "Landlord Peter Coffin",
          "character_action": "Mediates with easy authority; Queequeg nods; Ishmael sets a condition",
          "beat": "Peace terms and humanizing turn",
          "shot": "medium",
          "image_prompt": "Bedside parley: landlord calming with a hand out; Queequeg seated kindly, pipe stilled; Ishmael half out of bed, negotiating. Leave clean negative space top-center; keep their hands and faces clear.",
          "caption_zone": "top_center",
          "caption": "Better sleep with a sober cannibal than a drunken Christian.",
          "dialogue": [
            {
              "speaker": "Landlord",
              "text": "He wouldn't harm you."
            },
            {
              "speaker": "Ishmael",
              "text": "Only—stash that tomahawk-pipe; I ain't insured."
            },
            {
              "speaker": "Queequeg",
              "text": "Me sabbee plenty."
            }
          ],
          "sfx": [],
          "continuity_notes": "Queequeg’s kindness reads; pipe about to be stashed.",
          "lettering_notes": "Caption as a quiet moral turn over the talk; keep balloons balanced.",
          "adaptation_note": "Uses preserved lines 96, 99, 101 and Ishmael’s famous acceptance as VO."
        },
        {
          "panel_number": 5,
          "graphic_beat_ids": [
            "B29"
          ],
          "driver_character": "Ishmael",
          "character_action": "Settles back-to-back with Queequeg; landlord exits; the room dims to calm",
          "beat": "Lights out; unlikely peace",
          "shot": "wide",
          "image_prompt": "Restful view of the prodigious bed in half-dark: two figures back-to-back under covers; tomahawk-pipe now stashed on a shelf; the lamp just snuffed at the door. Leave clean negative space bottom-left; keep the bed’s scale and their silhouettes clear.",
          "caption_zone": "bottom_left",
          "caption": "Good night, landlord.",
          "dialogue": [],
          "sfx": [
            "CLICK"
          ],
          "continuity_notes": "Idol no longer visible; pipe visibly set aside; calm palette returns.",
          "lettering_notes": "Soft final VO; tiny SFX for lamp out.",
          "adaptation_note": "Closes with the ironic comfort image per instructions."
        }
      ]
    }
  ],
  "open_questions": [
    "How stylized should Queequeg’s dialect appear in balloons to remain readable and respectful while preserving the iconic line?",
    "For the ‘cheating tumblers’ gag, is a faint etched line on the glass sufficient without readable marks, or should we rely entirely on the caption?",
    "Do we want a slightly taller final panel on Page 9 to emphasize the ‘prodigious bed’ button, or keep uniform panel heights for pace?"
  ]
}

Return strict JSON only. Return the complete storyboard JSON with the same
top-level structure and all pages/panels preserved. In each panel, update only:
- `caption_zone`
- `caption`
- `dialogue`
- `sfx`
- `lettering_notes`
- `image_prompt` only if needed to reserve the caption zone while keeping the
  art text-free.