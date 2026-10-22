"""Source-aware editorial assessment of this run; no model calls or prose edits."""
import json
import trial as t


def passage(key, variant, text):
    actual = t.flat((t.OUT / key / (variant + '.md')).read_text())
    assert t.flat(text) in actual, (key, variant, text)
    return {'variant': variant, 'text': text}


def example(key, title, observation, pairs):
    return {'title': title, 'observation': observation,
            'passages': [passage(key, v, s) for v, s in pairs]}


def main():
    m = t.verify()
    comparison = t.read(t.OUT / 'comparison.json')
    rows = {x['chapter']: x for x in comparison['chapters']}
    assert len(rows) == 4
    chapters = {}
    k = 'education/007'
    chapters[k] = {
        'verdict': 'Closer to the requested length, with fuller Adams phrasing, but still 437 words beyond the fixed target.',
        'findings': [
            '3,370 words versus 2,933; +14.90%, compared with +33.27% in the prior run. The new draft adds 438 words and retains 78.37% of the source.',
            'The original self-mockery, qualified retrospective Marx reference, Sumner/cabman/poodle sequence, Apthorp introduction, and comic deflation of the Beethoven awakening remain coherent.',
            'The restored parental paradox and London tall-hats episode provide more of Adams’s actual phrasing and social comedy. Five-word wording reuse rises from 88.77% to 95.41%, partly because less is cut.',
            'All eight new protected excerpts survive, as do all seven protected excerpts from the previous plan. The Civil Law ghost, Wagner forward reference and Thuringen ending also survive.',
            'The reviewer note estimates that the total should be near 2,933. The mechanical count is 3,370; section allocations did not reliably constrain the response.'
        ],
        'examples': [example(k, 'A restored parental paradox',
            'This sentence is absent from the previous automatic draft. The larger draft restores the exact source wording and its joke about the parents’ own European advantages.',
            [('source', 'Strictly followed, the rule would have obliged them never to quit Quincy;'),
             ('draft', 'Strictly followed, the rule would have obliged them never to quit Quincy;')])]
    }
    assert 'Strictly followed' not in (t.OUT / k / 'previous.md').read_text()
    k = 'education/027'
    marx = 'He had studied Karl Marx and his doctrines of history with profound attention, yet he could not apply them at Paris.'
    chapters[k] = {
        'verdict': 'The Marx connection is repaired and the prose is very close to Adams, but the draft is only a light abridgment: 89.35% of the source remains.',
        'findings': [
            '3,566 words versus 2,800; +27.36%, compared with +30.24% previously. It adds 831 words to the previous draft and cuts only 425 words from the source.',
            'The new automatic plan explicitly requires the Marx passage in this chapter, as well as the foreshadowing in Berlin. Both now survive. The previous plan/draft combination preserved the setup but dropped this payoff.',
            'Langley’s opinions remain attributed to him; the Branly coherer is introduced before its later comparison; the Lucretius/Venus premise remains when the Dante verse is cut. The Gibbon, force/taste and blind-man’s-dog sequences remain connected.',
            'All eight protected excerpts from both plans survive. Five-word wording reuse rises from 90.30% to 97.81%; this is consistent with preserving Adams’s language, but much of the gain comes from retaining nearly the whole chapter.',
            'One small scope change merits review: after removing the Matthew Arnold comparison, the draft says “Artists felt a railway train as power”. The source assigns that feeling to St. Gaudens and Arnold, then broadens the following complaint to all other artists. The abridgment slightly broadens the first claim too.',
            'The model’s note says the draft may fall short of 2,800 words; the actual result is 766 words longer. This is direct evidence of an unreliable internal length estimate.'
        ],
        'examples': [
            example(k, 'Marx setup and payoff now agree',
                'This exact sentence was omitted in the previous automatic draft and is restored here. Berlin also keeps its earlier retrospective Marx reference.',
                [('source', marx), ('draft', marx)]),
            example(k, 'A small attribution tradeoff despite high wording reuse',
                'The earlier draft keeps the feeling attached to St. Gaudens. The new draft changes the subject to artists generally after cutting the two-person comparison.',
                [('source', 'They felt a railway train as power, yet they, and all other artists, constantly complained that the power embodied in a railway train could never be embodied in art.'),
                 ('previous', 'He felt a railway train as power, yet he, and all other artists, constantly complained that the power embodied in a railway train could never be embodied in art.'),
                 ('draft', 'Artists felt a railway train as power, yet they constantly complained that the power embodied in a railway train could never be embodied in art.')])
        ]
    }
    assert 'Karl Marx' not in (t.OUT / k / 'previous.md').read_text()
    k = 'secret_adversary/003'
    chapters[k] = {
        'verdict': 'A faithful, lively reading with the clues and comic timing intact, but it retains 88.27% of the original chapter.',
        'findings': [
            '2,108 words versus 1,733; +21.64%, compared with +39.00% previously. It adds 301 words to the prior draft and cuts only 280 words from the source.',
            'The office clerk is introduced neutrally before delivering the telephone message and being addressed as Brown. Rita, Paris, the ward role, secrecy and the American accent all remain without explaining their later significance.',
            'Tuppence’s ignorance of the Jane Finn name stays explicit. Her literal-truth bluff, “adventuress” wordplay, money-loving banter and taxi punchline retain Christie’s performed dialogue rather than becoming plot summary.',
            'The buns are introduced before the hungry money calculation, and Tommy’s retained pencil is present before the telegram. The £100 offer and actual £50 payment remain distinct.',
            'All eight new and all eight previous protected excerpts survive. Wording reuse rises from 84.49% to 93.79%. Almost every exchange remains, explaining both the fuller voice and weak compression.',
            'Quotation marks mix straight and curly forms, with protected passages tending to preserve curly forms. This is a presentation inconsistency; the validator explicitly permits this typography difference.'
        ],
        'examples': [example(k, 'Bluffing by literal truth remains performed dialogue',
            'Both the statement of ignorance and the exact comic reply survive. The passage is not rewritten as a narrator’s explanation of a solved mystery.',
            [('source', '“No,” she replied with perfect truth. “Rita knows nothing about me.”'),
             ('draft', '“No,” she replied with perfect truth. “Rita knows nothing about me.”')])]
    }
    k = 'secret_adversary/009'
    money = '“Does that matter, since the money only nominally comes from the States?”'
    chapters[k] = {
        'verdict': 'More of Christie’s suspense and political detail survive, but this chapter moves farther from its target in percentage terms.',
        'findings': [
            '2,705 words versus 2,133; +26.82%, compared with +24.81% previously. It adds 708 words and retains 89.81% of the source.',
            'The recess is opposite the meeting room; Tommy leaves his shoes behind the curtain, restores the locked door handle, and opens the communicating door from the adjacent bedroom. The portière explains why the later account is based on voices.',
            'The initial identification of Boris remains tentative (“rather thought”), as does the commanding man’s voice. Mr. Brown may be among them; the girl’s condition and the identity of the person striking Tommy remain unrevealed.',
            'The new version restores the qualification that the money only nominally comes from the States, which was cut in the previous automatic draft. It also retains the union leaders’ honest motives, the 29th, Clymes and the fingerprint gloves.',
            'All eight new and all eight previous protected excerpts survive. Wording reuse rises from 78.06% to 91.86%. The detailed door-handle scene and most of the plotting dialogue remain nearly whole despite being allocated much shorter section budgets.',
            'The new draft drops the source’s mention of “the pale Russian” from the earlier list of arrivals, before his entrance. Its note discloses that chronology adjustment. Speaker turns and source-supported attribution remain readable.'
        ],
        'examples': [
            example(k, 'A meaningful qualification restored',
                'The prior automatic draft omits this sentence. The new draft preserves the distinction between a money route and its real origin.',
                [('source', money), ('draft', money)]),
            example(k, 'Uncertainty stays uncertainty',
                'Tommy’s initial speaker identification retains the source’s qualification. This matters because he is listening through a curtain and cannot see the meeting.',
                [('source', 'Another voice which Tommy rather thought was that of Boris replied:'),
                 ('draft', 'Another voice which Tommy rather thought was that of Boris replied:')])
        ]
    }
    assert 'only nominally' not in (t.OUT / k / 'previous.md').read_text()
    assessment = {
        'summary': 'The larger fixed targets produced fuller, more literal abridgments, but did not resolve length control. All four drafts are 14.9–27.4% longer than their targets. Mean absolute target deviation improves from 31.83% to 22.68%, while the drafts grow by 24.05% overall. Three now retain about 90% of their source chapter.',
        'findings': [
            'Targets increased by one third, rounded to whole words: 2,200 → 2,933; 2,100 → 2,800; 1,300 → 1,733; 1,600 → 2,133. The planning and drafting instructions use one fixed target without a range or allowance.',
            'Both whole-book plans were regenerated automatically. All quote evidence passed initial mechanical validation; no repair calls or manual chapter-specific plan edits were needed. Six paid calls cost $3.467052.',
            'All 32 protected passages in the new plans survive. All 31 protected passages from the prior plans also survive, even though those plans were withheld from the models. Twenty-six cross-chapter evidence pairs validate against the original books.',
            'Five-word wording reuse increases in every chapter, to 91.86–97.81%. Source-aware reading confirms fuller authorial phrasing and coherent main connections, with a small subject-generalization issue in Dynamo. Wording reuse alone is not a quality score.',
            'The Adams Marx connection now survives in both chapters. Christie’s Brown/telephone clue remains unobtrusive; Tommy’s uncertain identifications and the undisclosed girl’s condition remain intact. The nominal US funding qualification is restored.',
            'The result weakens the idea that the old target or allowance wording alone caused the length problem. The preservation-heavy plans and inaccurate length estimates remain plausible causes. This is an inference from this small sample, not an isolated causal test.',
            'New outputs are preserved exactly as returned by the provider after the standard reviewer-note extraction. No trim pass or prose correction was added to this experiment. Production files and the previous experiment are unchanged.'
        ],
        'next_pipeline_changes': [
            'Keep a single explicit target in future tests; this run provides no reason to reintroduce multiple competing length numbers.',
            'If the chosen length is meant to be enforced, count the complete draft mechanically and feed the measured count and unchanged target into a bounded revision step. Validate protected passages and continuity again after revision. No such paid step was run here.',
            'To isolate the effect of target framing from target size and stochastic planning, use matched drafts with a frozen preservation plan and change one factor at a time. The present experiment intentionally changed the two user-requested factors together.'
        ],
        'limits': m['limitations'] + [
            'The comparison measures one response per chapter and is not a statistical reliability estimate.',
            'Higher wording reuse is confounded by the new drafts being longer. The reviewer read the outputs knowing which trial produced them.',
            'Mechanical quote matching proves text presence, not that all cross-chapter dependencies in a full assembled book are satisfied.'
        ],
        'chapters': chapters,
        'measurements': comparison,
        'reviewer': 'Coding assistant source-aware editorial review; not blinded or independent.'
    }
    t.save(t.OUT / 'assessment.json', assessment)
    for k in chapters:
        p = t.OUT / k / 'checks.json'
        checks = t.read(p)
        checks['manual_review'] = 'completed; see assessment.json; length differences and local editorial findings remain'
        t.save(p, checks)
    m['status'] = 'complete_measured_and_reviewed'
    m['review_completed_at'] = t.stamp()
    m['report'] = 'report.html'
    m['summary_measurements'] = {k: comparison[k] for k in ['mean_absolute_target_deviation_percent', 'total_words']}
    t.save(t.OUT / 'manifest.json', m)
    print('Reviewed all four chapters; verified quoted examples; preserved all generated prose.')

if __name__ == '__main__': main()
