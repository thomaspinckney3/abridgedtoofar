"""Evidence-checked editorial conclusions, separate from raw model assertions."""
from collections import Counter
from html import escape as esc
import json
import re
from run import OUT, read, save, norm, verify, stamp

KEYS = ["education/007", "education/027", "secret_adversary/003", "secret_adversary/009"]
INPUTS = {k: read(OUT / k / "inputs.json") for k in KEYS}
COMPLETE = {k: ("recovery/" if k.startswith("education/") else "") for k in KEYS}
ISSUES = []


def evidence(key, variant, quote, chapter=None):
    doc_id = f"{chapter or key}/{variant}"
    doc = INPUTS[key]["documents"][doc_id]
    for p in doc["paragraphs"]:
        if norm(quote) in norm(p["text"]):
            pos = norm(p["text"]).index(norm(quote))
            actual = p["text"][pos:pos + len(norm(quote))]
            assert norm(actual) == norm(quote)
            sid = doc_id.split("/")[1]
            return {"document": doc_id, "paragraph": p["paragraph"], "quote": actual,
                    "file": f"{key}/documents/{sid}.{variant}.md"}
    raise AssertionError((key, doc_id, quote))


def issue(id, key, priority, origin, title, assessment, repair, excerpts):
    ISSUES.append({
        "id": id, "chapter": key, "priority": priority, "origin": origin,
        "title": title, "assessment": assessment, "suggested_repair": repair,
        "evidence": [evidence(key, *e) for e in excerpts],
    })


issue("B1", KEYS[0], "must_fix", "revision", "Introduce the traveling companions",
      "The second pass deletes the companions' introduction, then retains 'the boys' at Eaton Hall and later 'his friends'. This is the confirmed small continuity break from the earlier structural review. It does not require restoring the travel description.",
      "Restore the source's short college-companions introduction near the sailing sentence.",
      [("source", "Several of his college companions sailed with him"),
       ("initial", "Several of his college companions sailed with him"),
       ("revision", "At Eaton Hall the boys were awed")])
issue("B2", KEYS[0], "should_improve", "revision", "Restore the qualification about learning German",
      "The first draft retained Adams's explicit admission that he never learned German well, followed by the joke about his English. The revision removes both. 'Whatever success he had' still hedges the result, so this is loss of a factual qualification and self-mockery, not an affirmative claim of fluency.",
      "Restore the short admission and, if space permits, its English-language joke.",
      [("source", "Adams never learned to talk German well, but the same might be said of his English"),
       ("initial", "Adams never learned to talk German well"),
       ("revision", "Whatever success he had interested him less than his contact with German education.")])
issue("B3", KEYS[0], "should_improve", "revision", "Reconnect the Cross image to the artwork",
      "Both references to the Descent from the Cross disappear from the revised Antwerp passage, while kneeling at the foot of the Cross remains. The surviving cathedral, Rubens and 'only sensual' cues make the scene recoverable, but the specific aesthetic experience becomes less clear. This is a qualified interpretation concern, not proof of a wholly incoherent passage.",
      "Restore the artwork's name with a short source-grounded connection.",
      [("initial", "Even in art, one can hardly begin with Antwerp Cathedral and the Descent from the Cross."),
       ("source", "He never dreamed of trying to educate himself to the Descent from the Cross."),
       ("revision", "He was only too happy to feel himself kneeling at the foot of the Cross")])
issue("B4", KEYS[0], "tradeoff", "mixed_first_draft_and_revision", "Opening irony and the tourist joke lose some buildup",
      "The first draft already omitted the rejoinder that Europe enabled the family's success and the tourist-mathematics capstone. Revision further cuts the boy's 'probably human' self-assessment and the sentence accumulating travel impressions before the mathematical joke. The core paradoxes remain; restoring every lost clause would defeat the abridgment.",
      "Optional: restore one representative ironic qualification or the impressions setup, rather than the entire opening.",
      [("source", "but he was probably human, and no worse than some others."),
       ("initial", "It united itself with a great variety of other impressions"),
       ("revision", "One began at last to see that a great many impressions were needed to make very little education")])

issue("D1", KEYS[1], "must_fix", "first_draft", "Avoid broadening two artists' response into a general claim",
      "The source's 'They felt a railway train as power' refers to St. Gaudens and Matthew Arnold. Both generated drafts make this 'Artists felt', broadening that assertion. The source separately broadens the following complaint about expressing railway power in art to all artists. Those two scopes should remain distinct. This was inherited from the first pass.",
      "Keep St. Gaudens as the subject of the train-as-power clause; retain the broader subject only for the artists' complaint.",
      [("source", "St. Gaudens at Amiens was hardly less sensitive to the force of the female energy than Matthew Arnold"),
       ("source", "They felt a railway train as power, yet they, and all other artists, constantly complained"),
       ("initial", "Artists felt a railway train as power"),
       ("revision", "Artists felt a railway train as power")])
issue("D2", KEYS[1], "should_improve", "revision", "Restore the two sides of the chemist comparison",
      "The first draft retained both the chemist's skepticism about translating forces and his unfamiliarity with dynamos, automobiles and radium. Revision cuts both while retaining 'force of all' and 'the rays were unborn'. Earlier rays/faith context still makes the overall argument intelligible, but the local example loses its explicit comparison. The partial critic wrongly attributed part of this loss to the first draft.",
      "Restore a compact reference to the physical forces alongside Venus/Virgin, and the chemist's ability to feel both.",
      [("source", "neither had he heard of dynamos or automobiles or radium"),
       ("initial", "Such a reversible process would vastly amuse a chemist"),
       ("revision", "yet his mind was ready to feel the force of all, though the rays were unborn and the women were dead.")])
issue("D3", KEYS[1], "should_improve", "first_draft_worsened_by_revision", "Clarify 'all were occult' and 'easiest to handle'",
      "The comparison with radium and other radiant matter was already cut in the first pass. Revision changes 'any of them' to 'any of it' and removes further plural terms, while retaining 'all' and the Virgin being 'easiest'. Earlier discussion of forces supplies recoverable context; this remains a possible local clarity problem, not a demonstrated collapse of the argument.",
      "Restore a short plural comparison grounded in the source, then check the whole paragraph.",
      [("source", "It could scarcely be more complex than radium"),
       ("initial", "Adams knew nothing about any of them"),
       ("revision", "Adams knew nothing about any of it, but though all were occult")])
issue("D4", KEYS[1], "tradeoff", "revision", "Some vivid analogies and comic endings disappear",
      "The second pass removes the Lancelot knife-edge image and the sentence about the dynamo's sex. The risky personal method and the explicit exclusion of the moral issue remain. These are real losses of imagery and ironic cadence, not missing logical premises that all need restoration.",
      "Optional: retain one of these distinctive short effects at the expense of less distinctive exposition.",
      [("initial", "The knife-edge along which he must crawl, like Sir Lancelot in the twelfth century"),
       ("source", "He cared nothing for the sex of the dynamo until he could measure its energy."),
       ("revision", "did not concern one who was studying the relations of unmoral force.")])

issue("W1", KEYS[2], "should_improve", "revision", "Preserve more of the negotiation's spoken rhythm",
      "Revision turns Whittington's ceremonious explanation into brisk transactional speech and removes his retort between Tuppence's two proposed explanations for 'Jane Finn'. The speakers and bluff remain clear, but the character performance and resistance in the exchange are reduced. This is a style concern the structural critic did not measure.",
      "Prefer retaining the retort and selected original sentence shapes; fund them with a whole optional cut elsewhere.",
      [("initial", "Well, I will tell you. I could doubtless obtain some one else for very much less."),
       ("source", "It’s likely, isn’t it, then there would be two girls with a name like that?"),
       ("revision", "I am paying for intelligence to sustain the part, and discretion not to ask too many questions."),
       ("revision", "Or I might just have hit upon it by chance")])
issue("W2", KEYS[2], "tradeoff", "revision", "The American cover-identity hint is less explicit",
      "The reason an American past would be easier to sustain is cut. Paris, the ward role, secrecy and passing as an American all remain, and the later impersonation inference still works. This is a weakened supporting clue, not a broken dependency.",
      "Optional: restore the short sentence about sustaining details of her English past.",
      [("source", "Details about your past life in England might be more difficult to sustain."),
       ("initial", "Details about your past life in England might be more difficult to sustain."),
       ("revision", "it might be simpler for you to pass as an American.")])
issue("W3", KEYS[2], "tradeoff", "mixed_first_draft_and_revision", "The narrator's smile is thinner around Tuppence's bluff",
      "The adventuress/adventurous wordplay was already absent in the first draft. Revision additionally removes her pause to admire her ingenuity. 'Intoxicated with the success of truthfulness', the terrier shake and the hospital-plate dream survive. The critic's blanket attribution of these losses to revision was inaccurate.",
      "Optional: restore one short narratorial aside, rather than every repeated bluff exchange.",
      [("source", "Her present part was of the adventuress rather than the adventurous order"),
       ("initial", "Tuppence paused a moment to admire her own ingenuity"),
       ("revision", "continued Tuppence, intoxicated with the success of truthfulness.")])

issue("T1", KEYS[3], "tradeoff", "revision", "Door-handle suspense is faster and less comic",
      "The long sequence of tentative movement, hesitation and mounting annoyance is compressed. The locked door, careful restoration of the handle, indignation, bedroom detour and listening through the portière all remain. The mechanism is coherent; the loss is suspense timing, explicitly permitted by the plan.",
      "No required repair. If pacing feels too brisk, restore a single hesitation before the locked-door revelation.",
      [("source", "A little more--a little more still--would it never be finished?"),
       ("revision", "Then he pressed, finally with all his might. But the door remained firm.")])
issue("T2", KEYS[3], "tradeoff", "revision", "Number One's ceremonial refusal of the chair disappears",
      "The initial draft includes the Russian's demurral; revision summarizes the German's insistence. The next line explicitly seats Number One, so the pronoun does not create sustained speaker or staging confusion. A small characterization beat is lost.",
      "No required repair. Optionally retain the short demurral if that social performance matters.",
      [("source", "The Russian demurred, but the other insisted."),
       ("initial", "The Russian demurred, but the other insisted."),
       ("revision", "The German insisted that he take the head of the table.")])

# Every complete finding in the truncated responses is retained for audit, but
# neither truncated response counts as a completed chapter review.
DISPOSITIONS = {
    "education/007/partial": [
        ("rejected", "'Whether worthy' is intelligible from the parents' indulgence and the preceding portrait."),
        ("qualified", "Real setup compression; later travel impressions preserve the general sense. See B4."),
        ("confirmed", "Companions introduction is gone; B1."),
        ("qualified", "Specific artwork anchor lost, but Rubens/cathedral/sensual cues remain; B3."),
        ("tradeoff", "Eighteenth- and sixteenth-century cues remain; no broken century progression."),
        ("rejected", "'So much ... that' is a self-contained degree construction, not a dangling connective."),
        ("qualified", "Real loss of self-mockery; some claimed origin details are mixed. See B4."),
    ],
    "education/007/complete": [
        ("rejected", "'Accidental, unintended, unforeseen' and 'no other sense awoke' both remain; the proposed broken Beethoven/Rome connection is unsupported."),
        ("tradeoff", "Desperation is explained by preceding language difficulties; the foolish-but-useful payoff is a genuine optional loss."),
        ("qualified", "Timid parents remain. The ultimate-wisdom ending was cut earlier; optional voice loss, B4."),
        ("tradeoff", "Reason and State purposes remain explicit. The omitted sentence was cut in revision, not the first draft."),
    ],
    "education/027/partial": [
        ("qualified", "The relevant setup was present in the first draft; revision removed it. See D2."),
        ("qualified", "Force/taste contrast remains immediately above; narrower valid issue is the broadened subject in D1."),
    ],
    "education/027/complete": [
        ("rejected", "Plan requires the first Latin line OR a gloss, and explicitly permits cutting Dante's tercet. Those requirements are satisfied."),
        ("tradeoff", "Gibbon's Revolution, Ruskin's reaction, and the force/taste lesson remain; omitted commentary is not a broken dependency."),
        ("qualified", "Local referent concern survives review, with earlier forces as counterevidence; D3. Langley's general modesty remains."),
        ("tradeoff", "Imagery/cadence loss is real, but prayer and the baby remain; D4."),
        ("qualified", "Marx and the moral qualification remain. Only the comic dynamo-sex ending is lost; D4."),
    ],
    "secret_adversary/003/complete": [
        ("qualified", "Wordplay was already absent in the first draft; the ingenuity aside was removed in revision. See W3."),
        ("tradeoff", "Supporting rationale lost, but the actual partner still carries the impersonation inference; W2."),
        ("qualified", "No confused speaker, but a genuine loss of repartee; W1."),
        ("rejected", "The preceding included chapter explicitly sets the station appointment. The taxi also performs her newfound wealth; the clock is optional."),
        ("rejected", "The job-search/proposition/payment context supplies 'work'; no meaningful anaphora failure."),
    ],
    "secret_adversary/009/complete": [
        ("qualified", "The hedge 'hinted' remains, and the source itself uses 'the Russian'. The additional qualification is lost, but no demonstrated new identity disclosure."),
        ("tradeoff", "Seating clarified immediately by Number One; lost demurral is a small performance cost, T2."),
        ("tradeoff", "Arrivals still show the group's variety. Removing the rhetorical inventory is defensible; no repair needed."),
    ],
}

PARTNER_QUOTES = {
    KEYS[0]: [
        "He had studied Karl Marx and his doctrines of history with profound attention",
        "but to Adams the dynamo became a symbol of infinity",
        None, "passed Beethoven as a piece of accidental education",
        "The boy worshipped him", "forty years of varied emotions had not deadened his memories of that city"],
    KEYS[1]: [
        None, "After Gibbs, one of the most distinguished was Langley, of the Smithsonian",
        "Its first violent acceleration in historical times had ended in the catastrophe of 310.",
        "Like all great artists, St. Gaudens held up the mirror and no more.",
        "Adams had gone straight to the Virgin at Chartres"],
    KEYS[2]: [
        "in Mr. Whittington's office, the clerk—he called him Brown.",
        "Who's been blabbing? Rita?", "You didn't invent it. *I* told it to you.",
        "They'll produce a Jane Finn of their own", "One was a big fat sort of chap. Clean shaven, and dark."],
    KEYS[3]: [
        "So that's who Number 1 is", "Carter handed him another. Tommy exclaimed.",
        "is less than a fortnight ahead", "With your own password, wasn't it?",
        "the ragged curtain hiding the recess", "Conrad entered with the evil-looking Number 14"],
}


def main():
    manifest = read(OUT / "manifest.json")
    verify(manifest)
    raw_reviews, checked_quotes, dependencies = [], 0, []
    for key in KEYS:
        completed = read(OUT / key / COMPLETE[key] / "critic.json")
        completed_response = read(OUT / key / COMPLETE[key] / "response.json")
        assert completed_response["stop_reason"] == "end_turn"
        for source in ["partial", "complete"]:
            if source == "partial":
                path = OUT / key / "partial_complete_findings.json"
                if not path.exists():
                    continue
                findings = read(path)["findings"]
            else:
                findings = completed["findings"]
            dispositions = DISPOSITIONS[f"{key}/{source}"]
            assert len(findings) == len(dispositions)
            for finding, (verdict, reason) in zip(findings, dispositions):
                for e in finding["evidence"]:
                    doc = INPUTS[key]["documents"][e["document"]]
                    para = next(x for x in doc["paragraphs"] if x["paragraph"] == e["paragraph"])
                    assert norm(e["quote"]) in norm(para["text"])
                    checked_quotes += 1
                raw_reviews.append({"chapter": key, "response_kind": source,
                                    "finding": finding, "review": verdict, "reason": reason})
        for dep, quoted in zip(INPUTS[key]["dependencies"], PARTNER_QUOTES[key]):
            partner = dep["partner"]
            idx = dep["index"]
            local = [e for e in completed["dependencies"][idx]["evidence"]
                     if e["document"] == f"{key}/revision"]
            local_evidence = [evidence(key, "revision", e["quote"]) for e in local]
            assert local_evidence, (key, idx)
            status = "intact" if partner["included_in_current_reading_sequence"] else "partner_chapter_omitted"
            proof = []
            if quoted:
                partner_key, variant = partner["draft"].rsplit("/", 1)
                proof.append(evidence(key, variant, quoted, partner_key))
            else:
                assert not INPUTS[key]["documents"][partner["draft"]]["paragraphs"]
            note = "Both endpoints survive in function; quotation need not be identical."
            if status == "partner_chapter_omitted":
                note = "The local text is self-contained, but the source-book echo is absent because the existing partner chapter is omitted. Not a defect newly introduced by revision."
            if key == KEYS[1] and idx == 2:
                note = "The originally cited Civitas Dei sentence is cut, but the later 'catastrophe of 310' passage retains the connection. An exact-quote-only check would wrongly report failure."
            dependencies.append({"chapter": key, "index": idx, "partner": partner["id"],
                                 "status": status, "note": note, "evidence": local_evidence + proof})
    attempts = [read(p) for p in OUT.rglob("response.json")]
    assert len(attempts) == 6
    costs = round(sum(x["cost_usd"] for x in attempts), 6)
    assert costs <= 2
    counts = dict(Counter(x["priority"] for x in ISSUES))
    dep_counts = dict(Counter(x["status"] for x in dependencies))
    assert dep_counts == {"intact": 20, "partner_chapter_omitted": 2}
    summary = {
        "reviewed_chapters": 4, "complete_model_reviews": 4, "paid_attempts": 6,
        "truncated_attempts": 2, "cost_usd": costs,
        "model": "claude-sonnet-5-5", "issue_counts": counts,
        "dependency_counts": dep_counts, "raw_candidates_adjudicated": len(raw_reviews),
        "repairs_applied": False, "published": False,
    }
    conclusions = {
        KEYS[0]: "Repair the companions introduction; restore the language qualification and clarify the art reference. Main educational irony and the Beethoven/Rome connection remain.",
        KEYS[1]: "Correct the broadened artist subject and clarify two local comparisons. Marx, Cellini half-natures, personal-method hedges, and the main force/taste argument survive.",
        KEYS[2]: "No confirmed plot or attribution failure. Improve selected dialogue rhythm if style is the priority; distinguish optional losses from broken clues.",
        KEYS[3]: "No required repair identified. Spatial mechanism, limited recognition, principal clues, and cliffhanger survive. Some suspense timing and ceremony are compressed.",
    }
    result = {
        "summary": summary, "reviewer": "Sonnet 5.5 candidates with coding-assistant source-aware adjudication; not blinded.",
        "conclusions": conclusions, "issues": ISSUES, "dependencies": dependencies,
        "raw_candidate_reviews": raw_reviews,
        "unsupported_summary_claims": [
            "Berlin's completed critic says 'no other sense awoke' is lost; it is present in revision paragraph 18.",
            "Dynamo's completed critic summary says Marx and the Cellini half-natures were dropped; revision paragraphs 2 and 16 retain them.",
            "The claim that the Lucretius line requires an additional gloss misreads the plan's 'Latin line OR a clear gloss'.",
        ],
        "limits": [
            "This checks four chapters and 22 planned connections, not every dependency in either complete book.",
            "Critic quotes were valid, but several conclusions or claimed origins were not. Quote validation is not semantic validation.",
            "Style recommendations are editorial judgments; tradeoffs are not mandatory restorations.",
            "All review calls preceded the user's subsequent change to Opus 5.5 routing. They remain labeled Sonnet 5.5.",
        ],
    }
    save(OUT / "assessment.json", result)
    tables = ""
    for key in KEYS:
        c = Counter(x["priority"] for x in ISSUES if x["chapter"] == key)
        tables += f"<tr><td>{esc(INPUTS[key]['plan']['title'])}</td><td>{c['must_fix']}</td><td>{c['should_improve']}</td><td>{c['tradeoff']}</td></tr>"
    cards = ""
    for x in ISSUES:
        quotes = "".join(
            f"<li><a href='{esc(e['file'])}'>{esc(e['document'])}, P{e['paragraph']}</a>"
            f"<blockquote>{esc(e['quote'])}</blockquote></li>" for e in x["evidence"])
        cards += (
            f"<article class='{x['priority']}'><p class='label'>{esc(x['id'])} · {esc(x['chapter'])} · "
            f"{esc(x['priority'].replace('_',' '))} · {esc(x['origin'].replace('_',' '))}</p>"
            f"<h3>{esc(x['title'])}</h3><p>{esc(x['assessment'])}</p>"
            f"<p><b>Follow-up:</b> {esc(x['suggested_repair'])}</p>"
            f"<details><summary>Verified source and draft evidence</summary><ul>{quotes}</ul></details></article>"
        )
    dep_rows = "".join(
        f"<tr><td>{esc(x['chapter'])} / {x['index']}</td><td>{esc(x['partner'])}</td>"
        f"<td>{esc(x['status'].replace('_',' '))}</td><td>{esc(x['note'])}</td></tr>" for x in dependencies)
    raw_rows = "".join(
        f"<tr><td>{esc(x['chapter'])} · {esc(x['response_kind'])} · {esc(x['finding']['id'])}</td>"
        f"<td>{esc(x['finding']['title'])}</td><td>{esc(x['review'])}</td><td>{esc(x['reason'])}</td></tr>"
        for x in raw_reviews)
    raw_links = " · ".join(
        f"<a href='{key}/{COMPLETE[key]}critic.json'>{esc(key)} complete critic</a>" for key in KEYS)
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Detailed coherence and fidelity review</title><style>
body{margin:0;background:#f5f3ee;color:#24332e;font:17px/1.6 system-ui,sans-serif}
main{max-width:1060px;margin:auto;padding:36px 24px 70px}h1{font-size:2.2rem;line-height:1.2}
h2{margin-top:2.2rem}h3{margin:.3rem 0}a{color:#165b49;overflow-wrap:anywhere}
.label{font-size:.8rem;color:#53695e;text-transform:uppercase;letter-spacing:.04em}
.stats{display:flex;flex-wrap:wrap;gap:12px}.stats span{background:#e2ebe5;padding:9px 14px;border-radius:7px}
article{background:white;border:1px solid #d6dcd4;border-left:4px solid #b4b9ad;border-radius:8px;padding:20px;margin:18px 0}
article.must_fix{border-left-color:#a14838}article.should_improve{border-left-color:#a78134}
blockquote{font:1rem/1.6 Georgia,serif;border-left:2px solid #b9c8be;padding-left:14px;margin:8px 0 18px}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #d7ddd6}
.scroll{overflow-x:auto}summary{cursor:pointer}li{margin:.6rem 0}footer{margin-top:30px;border-top:1px solid #d6dcd4;padding-top:18px}
</style><main><p class="label">Forage · original-target two-pass experiment · 20 October 2026</p>
<h1>Detailed coherence and fidelity review</h1>
<p>Two concrete repairs are recommended: introduce the traveling companions in <i>Berlin</i>,
and correct the broadened artist subject in <i>The Dynamo and the Virgin</i>.
Five further recommendations concern qualification, local clarity, and dialogue rhythm.
Six additional observations are defensible artistic tradeoffs, not mandatory restorations.</p>
"""
    html += (
        f"<div class='stats'><span>4 complete reviews</span><span>22 dependencies checked</span>"
        f"<span>Sonnet 5.5 + manual adjudication</span><span>${costs:.2f} total</span></div>"
        "<h2>Chapter results</h2><div class='scroll'><table><thead><tr><th>Chapter</th><th>Repair</th>"
        f"<th>Improve</th><th>Tradeoff</th></tr></thead><tbody>{tables}</tbody></table></div>"
        "<p>Required repairs are a continuity defect and a source-fidelity defect, respectively. "
        "Neither Christie chapter has a confirmed plot, speaker-attribution, or premature-revelation failure.</p>"
        f"<h2>Evidence and editorial recommendations</h2>{cards}"
        "<h2>Cross-chapter connections</h2><p>Twenty connections survive in function. Two partners—"
        "Adams's <i>Chicago</i> and <i>Silence</i>—are omitted from the current production reading sequence. "
        "Their local references remain understandable, but those remote echoes are absent. "
        "These are pre-existing book-level omissions, not new revision errors.</p>"
        f"<details><summary>All 22 connections</summary><div class='scroll'><table><thead><tr>"
        f"<th>Chapter / dependency</th><th>Partner</th><th>Status</th><th>Assessment</th></tr></thead>"
        f"<tbody>{dep_rows}</tbody></table></div></details>"
        "<h2>Critic reliability and rejected claims</h2><p>Several quotations were accurate while "
        "the conclusions drawn from them were wrong. The revised text still contains "
        "'accidental, unintended, unforeseen', 'no other sense awoke', the Marx payoff, and "
        "the Cellini half-natures. Those alleged losses were rejected. The plan permits "
        "the Latin line <em>or</em> a gloss; retaining the Latin satisfies it.</p>"
        f"<details><summary>Review of all {len(raw_reviews)} model candidates, including partial responses</summary>"
        "<div class='scroll'><table><thead><tr><th>Origin</th><th>Candidate</th><th>Decision</th>"
        f"<th>Reason</th></tr></thead><tbody>{raw_rows}</tbody></table></div></details>"
        "<h2>Method, completion and limits</h2><p>The broader critic compared source, first draft and revision "
        "across causality, references, dialogue, qualifications, viewpoint, voice, interpretation, and planned dependencies. "
        "No earlier critic conclusions were supplied. All four chapters received a complete review. "
        "The two initial Adams requests reached their 16,000-token output cap; their complete finding objects "
        "were retained, but the responses were not counted as complete reviews. Two compact reviews with explicit "
        "medium effort completed the work. These retained all central texts and partner drafts, with cited source "
        "excerpts for context chapters. Six paid attempts cost $1.64, within the $2 ceiling.</p>"
        "<p>The coding assistant checked the evidence and separated confirmed problems, qualified recommendations, "
        "and optional losses. This is a four-chapter, unblinded review, not proof of whole-book correctness. "
        "No prose was repaired or published. The later .env change routes future Forage text stages to Opus 5.5; "
        "these completed reviews used Sonnet 5.5.</p>"
        f"<footer>{raw_links}<p><a href='assessment.json'>Reviewed findings and evidence (JSON)</a> · "
        "<a href='manifest.json'>Run manifest</a> · <a href='critic.txt'>Detailed review rubric</a> · "
        "<a href='../coherence/report.html'>Earlier structural review</a> · "
        "<a href='../report.html'>Two-pass comparison</a></p></footer></main></html>"
    )
    (OUT / "report.html").write_text(html)
    links = re.findall(r"href=['\"]([^'\"]+)['\"]", html)
    assert all((OUT / link).exists() for link in links)
    save(OUT / "verification.json", {
        "status": "pass", "original_artifacts_unchanged": True,
        "original_hashes_checked": len(manifest["original_hashes"]),
        "frozen_inputs_checked": len(manifest["input_hashes"]),
        "raw_finding_quotes_checked": checked_quotes,
        "manual_evidence_spans_checked": sum(len(x["evidence"]) for x in ISSUES),
        "dependencies_with_verified_partner_state": len(dependencies),
        "local_links_checked": len(links), "complete_reviews": 4,
        "protected_passages": "32/32 unchanged; reviewed drafts remain byte-identical to the measured experiment.",
    })
    manifest["initial_batch"] = {k: manifest.get(k) for k in ["status", "completed_calls", "cost_usd", "errors"]}
    manifest.update(status="complete_reviewed", reviewed_at=stamp(), completed_calls=6,
                    complete_reviews=4, truncated_attempts=2, cost_usd=costs,
                    recovered_chapters=["education/007", "education/027"],
                    unresolved_errors=[], summary=summary,
                    report="report.html", assessment="assessment.json")
    save(OUT / "manifest.json", manifest)
    verify(manifest)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
