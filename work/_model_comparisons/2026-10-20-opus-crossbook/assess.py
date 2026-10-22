"""Source-aware review of saved experiment outputs; no generation or text edits."""
import json
from pathlib import Path
import re
import trial as t

OUT = t.OUT


def passage(key, variant, needle, following=0):
    path = OUT / key / (variant + ".md")
    paras = re.split(r"\n\s*\n", path.read_text().strip())
    for i,p in enumerate(paras):
        if needle in t.flat(p):
            return {"variant":variant,"paragraph":i+1,"path":str(path.relative_to(OUT)),
                    "text":"\n\n".join(t.flat(x) for x in paras[i:i+1+following])}
    raise AssertionError((key,variant,needle))


def example(key,title,observation,needles):
    return {"title":title,"observation":observation,"passages":[passage(key,v,n) for v,n in needles.items()]}


assessment = {
 "summary":"Automatic whole-book planning found meaningful stylistic and narrative dependencies, but the resulting drafts all failed the length requirement. All 31 protected excerpts survived; each draft exceeded even the 20% ceiling. The manual Gatsby success has not generalized to an automatic first-draft workflow.",
 "method":"Four purposively chosen chapters from two books. Opus 5.5 medium read each complete original book and produced two plans with the same generic rubric. The coding assistant selected samples and reviewed results, but did not author or edit chapter-specific preservation choices. Code validated source quotations, bounded protected text, and apportioned section budgets. One short automatic evidence-repair call per book fixed formatting mismatches, followed by one fresh source-based draft per chapter. No draft was hand-edited, trimmed or published. Editorial review was unblinded and performed by the coding assistant; no independent model judge.",
 "findings":[
  "All four first drafts missed both the ±5% target range and the +20% ceiling: Berlin 2,932/2,200 (+33.27%); Dynamo and Virgin 2,735/2,100 (+30.24%); Whittington’s Offer 1,807/1,300 (+39.00%); Adventures of Tommy 1,997/1,600 (+24.81%). None declared INFEASIBLE.",
  "All 31 verbatim excerpts survived, including punctuation apart from straight/curly quotes and whitespace. Protected text was only 172, 140, 108 and 141 words respectively—6.7–8.8% of target—so the exact-quotation cap was not the limiting constraint.",
  "The automatically generated ESSENTIAL tier recreated much of the original preservation pressure. It contained 11–12 requirements per chapter, many bundling several scenes, examples, quotations or allusions. Instructions such as keeping the Sumner anecdote, the Gymnasium details, the full musical awakening and multiple travel impressions were all simultaneously mandatory. This is an inference from the plans and outputs, not a causal ablation.",
  "The model’s reviewer notes badly underestimated length: 'near the 2200 target', 'near the upper end', or 'slightly above/outside' appeared despite 24.8–39.0% overruns. Measuring after generation exposed the error. Merely stating a ceiling in the prompt did not enforce it.",
  "Whole-book planning did find useful dependencies without manual hints: Brown’s ordinary clerk appearance and telephone message, Rita, the unexplained Jane Finn name, the curtained recess, the strike date, and the honest-men motif; for Adams, the Civil Law ghost, dynamo metaphor, Wagner delay and Sumner relationship. The 27 cited dependency pairs passed quote-existence checks after repair; this does not prove every interpretation or every omission correct.",
  "A joint consistency problem remains: Berlin’s plan cites the later Marx-study sentence in Dynamo and Virgin as support for retaining its Marx foreshadowing. The Dynamo draft explicitly cuts that cited sentence. Source-based dependency discovery must be followed by checking that the relevant endpoints survive in the abridged book, allowing faithful paraphrase.",
  "Source wording reuse is 88.77%, 90.30%, 84.49% and 78.06% in the four new drafts. Berlin and the Christie samples are more verbatim than their existing comparators; Dynamo is approximately unchanged (existing 91.08%). All new drafts are longer than the comparators, so this is not evidence of superior fidelity at equal compression.",
  "Both initial validation failures were surface mismatches, not demonstrated fabricated passages: 'The' versus the source's 'THE' in the opening of the next Adams chapter, and an added opening quotation mark in a mid-speech Christie excerpt. Bounded automatic repair fixed only those fields; initial plans and patches are retained."
 ],
 "limits":[
  "This tests automatic planning plus fresh drafting, whereas the successful Gatsby trial revised an existing Opus draft using an assistant-authored plan. Planning method, chapter, author and drafting stage all changed. These results do not isolate which difference caused the failed budgets.",
  "The same model planned and drafted, and the assistant reviewed unblinded. Four selected chapters and one sample each cannot establish performance for all books.",
  "The full books fit the model context here. Very large books need a persistent chapter index, retrieved evidence and a book-level dependency map; concatenating every book into one prompt is not a universal scaling solution.",
  "Mechanical validation proves exact quoted text exists and arithmetic is consistent. It does not establish that the protected selection is adequate, that the ESSENTIAL tier is feasible, or that every inferred relationship is valid.",
  "Existing abridgments have mixed model/revision provenance. They were not supplied to either model stage, and are comparison artifacts rather than a matched old-prompt control.",
  "A generic evidence-repair stage was added after the initial validation failures. This is an experiment harness, not an integrated production release. The recorded eight calls cost $3.612624, within the original $7.18113 conservative cap. No additional trim passes were used to conceal first-draft failures."
 ],
 "next_pipeline_changes":[
  "Budget the ESSENTIAL tier, not just exact quotes: split bundled requirements into ranked functions with estimated section costs, and return low-priority functions to the optional tier when the total cannot fit. Preserve causality and argument rather than every supporting example.",
  "Make word count an actual acceptance gate. After drafting, pass the measured count, precise excess, plan and source back for a bounded trim pass; recount and verify protected text and continuity. If a feasible result cannot be reached within a fixed iteration/cost cap, return an explicit review exception.",
  "Audit dependencies against generated chapters, not only original-book quotations. Retain both endpoints, or explicitly approve removal of the complete unit. Check for premature revelations as well as omissions.",
  "Separate normalized evidence matching from exact-output quotation checks so capitalization or excerpt-boundary formatting need not trigger a full-plan rejection. Preserve the original source text when canonicalizing.",
  "Cache a book-level index and dependency map for reuse across chapter drafts and reviewer iterations. Use retrieval and coverage checks when the whole book cannot fit safely in one planning context."
 ],
 "chapters":{}
}

assessment['chapters']['education/007']={
 "verdict":"Strong preservation of Adams’s verbal irony, but failed budget: 2,932 words against 2,200, and 292 words above the 2,640 ceiling.",
 "findings":[
  "All seven exact spans survive. The double perspective of boy and older narrator, the self-deprecating family portrait, the London antitheses, the Sumner/cabman–poodle sequence and the involuntary Beethoven awakening remain coherent.",
  "The plan requires so much travel and school detail that most of the source’s scenes remain expansive. At 68.19% of source length, this resembles the earlier Opus tendency to cut roughly a third rather than meet the approximately half-length target.",
  "Compared with the 2,661-word existing version, the new draft adds 271 words and raises wording reuse from 62.05% to 88.77%. That is stronger surface preservation with a worse budget, not an equal-length win.",
  "The plan protects the Marx anticipation partly because of a specific later sentence; the partner Dynamo draft omits that cited sentence. The dynamo metaphor itself survives in both. Other occurrences of Marx elsewhere in the book were not regenerated in this experiment."
 ],
 "examples":[
  example('education/007','An unprotected comic qualification survives','The new draft preserves the sequence of conditionally good behavior—being well behaved only when watched, observing conventions only when unable to escape them. The large first paragraph is also one place where preservation consumes the budget.',{'source':'The boy Henry wanted','draft':'The boy Henry wanted'}),
  example('education/007','Source wording replaces a looser Marx image','The source and new draft retain the retrospective qualification that he had no idea Marx was waiting for him. The existing version gives Marx a more literal presence in the mist. This is a local stylistic/fidelity benefit, although the later cited Marx payoff is cut in the new Dynamo chapter.',{'source':'he had no idea that Karl Marx','existing':'Karl Marx stood there','draft':'he had no idea that Karl Marx'})
 ]}

assessment['chapters']['education/027']={
 "verdict":"The argument and characteristic contrasts remain readable, but the draft is 2,735 words against 2,100, exceeding the 2,520 ceiling by 215 words.",
 "findings":[
  "All eight exact spans survive. The distinction between Langley’s mechanism and Adams’s symbolic response, the tentative measurement by attraction on his own mind, the Venus/Virgin relation and the force-versus-taste contrast remain.",
  "The Branly coherer callback retains its setup. When the Dante tercet is cut, a short bridge preserves who invoked whom. The date and complete departure ending survive. No major new causal or attribution gap was found in this local close reading.",
  "The plan’s ESSENTIAL tier covers nearly every original argumentative stage and many examples. Merely limiting exact excerpts to 140 words did not produce a feasible 2,100-word draft.",
  "The existing version has 2,408 words and 91.08% wording reuse; the new one has 2,735 and 90.30%. More retained material here is not a demonstrated overall improvement.",
  "The new draft explicitly drops the source’s Marx-study sentence even though the same book-planning response uses it as a dependency for Berlin. This is an inconsistency between the planner’s cross-chapter reasoning and the generated chapter set."
 ],
 "examples":[
  example('education/027','Tentative method survives','The new draft retains the constraint that the common measure is attraction on Adams’s own mind, rather than simply presenting faith and electricity as a demonstrated physical identity.',{'source':'this common value could have no measure','draft':'this common value could have no measure'}),
  example('education/027','The cited Marx payoff is cut','The source and existing abridgment contain the sentence used by Berlin’s plan as evidence. The new draft moves from the inert-facts aphorism directly to Langley’s selection of exhibits. Its own notes explicitly record cutting Marx.',{'source':'He had studied Karl Marx','existing':'He had studied Karl Marx','draft':'Nothing in education is so astonishing'})
 ]}

assessment['chapters']['secret_adversary/003']={
 "verdict":"The clue handling and comic dialogue are well preserved, but 1,807 words is 39% above the 1,300 target and 247 words over the 1,560 ceiling.",
 "findings":[
  "All eight exact spans survive. The planner correctly treats the clerk Brown, telephone message and outer office as consequential clues, despite their apparently minor local role. They remain unremarked in the draft.",
  "The ward/pensionnat arrangement, secrecy, American accent, accidental Jane Finn name, Rita exchange, truthful bluff, £50 payment and five-pound-note punchline remain in source order without later explanations.",
  "The buns are retained before the later 'supper of buns' reference; the dream still connects to hospital work. New-speaker paragraphs and attribution are clear.",
  "The new text is 622 words longer than the existing 1,185-word abridgment. Its wording reuse rises from 60.05% to 84.49%, but the existing version already retains Brown and the telephone message; this is successful automatic protection, not restoration of a previously missing clue.",
  "Many optional units remain lengthy, including the approach, office arrival and haggling. The model’s note 'may sit slightly above' substantially understates the measured overrun."
 ],
 "examples":[
  example('secret_adversary/003','Clue retained without explanation','The automatic planner supplies the later Carter passage as evidence, but the draft keeps Brown’s name as an ordinary dismissal. The existing abridgment also preserves it. No premature identification of the clerk is added.',{'source':'That’ll do, Brown','existing':"That'll do, Brown",'draft':"That'll do, Brown"}),
  example('secret_adversary/003','The comic narrative distinction remains','The source’s adventuress/adventurous wordplay is retained exactly, including the preceding mundane hunger and money motive. This is one of the planner’s selected style-bearing passages.',{'source':'adventuress rather than','draft':'adventuress rather than'})
 ]}

assessment['chapters']['secret_adversary/009']={
 "verdict":"A coherent suspense scene with retained uncertainty, but 1,997 words exceeds the 1,600 target by 24.81% and the 1,920 ceiling by 77 words.",
 "findings":[
  "All eight exact spans survive. The door/recess/stair geometry, numbered arrivals, Number One’s deference to Brown, and failed locked-door attempt followed by the communicating door remain intelligible.",
  "The draft preserves both familiar-but-unnamed faces, the 29th, the honest Labour leaders being used, the Clymes assignment and fingerprints, and uncertainty about the missing document and the girl. It neither names Number One’s public identity nor identifies the attacker or explains the girl’s condition.",
  "The tentative recognition of Boris’s voice survives ('rather thought'), whereas the existing draft asserts 'That was Boris.' Tommy’s comic indignation and bulldog tenacity remain, together with the sinister honest-men punchline.",
  "The new draft is 607 words longer than the existing 1,390-word text, with wording reuse rising from 49.33% to 78.06%. It cuts the line that money only nominally comes from the States; this loses a political nuance but creates no clear local contradiction.",
  "The last location question is interrupted by the blow, and the complete cliffhanger is preserved. The model’s own 'slightly outside' length warning still understates the overrun."
 ],
 "examples":[
  example('secret_adversary/009','Limited recognition remains limited','The source and new draft qualify the voice as one Tommy rather thought was Boris’s. The existing version makes the identification certain. This matters in a scene built on restricted sight and incomplete knowledge.',{'source':'Tommy rather thought','existing':'That was Boris','draft':'Tommy rather thought'}),
  example('secret_adversary/009','Suspense retains its physical mechanism','The new text keeps the rusty bolt and communicating door, with the portière blocking sight but allowing hearing. This lets the subsequent uncertain voice recognition make sense.',{'source':'a communicating door','draft':'a communicating door'})
 ]}

summary=[]
for key, chapter in assessment['chapters'].items():
    folder=OUT/key
    checks=t.read(folder/'checks.json')
    assert all(x['present'] for x in checks['protected'])
    assert not checks['under_ceiling'] and not checks['within_target_range']
    checks['manual_review']='Source-aware review complete; budget failed. See assessment.json for style and dependency findings.'
    checks['accepted_for_production']=False
    checks['acceptance_reasons']=['outside_target_range','over_absolute_ceiling']
    t.save(folder/'checks.json',checks)
    summary.append({'chapter':key,'words':checks['words'],'target':checks['target_words'],
                    'accepted':False,'reasons':checks['acceptance_reasons']})
assert sum(len(t.read(OUT/key/'checks.json')['protected']) for key in assessment['chapters'])==31
assert 'Karl Marx' not in (OUT/'education/027/draft.md').read_text()
t.save(OUT/'acceptance.json',{'scope':'Experiment acceptance decisions only; production pipeline unchanged.','chapters':summary,'accepted_count':0})
t.save(OUT/'assessment.json',assessment)
manifest=t.verify()
manifest['status']='assessed_all_four_rejected_for_length'
manifest['assessment']='assessment.json'
manifest['acceptance']='acceptance.json'
manifest['results']['accepted_drafts']=0
manifest['results']['protected_spans_passed']=31
manifest['results']['protected_spans_total']=31
t.save(OUT/'manifest.json',manifest)
print('Assessment saved: 4 drafts reviewed, 31 protected excerpts retained, 0 accepted on length.')
