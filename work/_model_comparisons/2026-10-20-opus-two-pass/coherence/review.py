"""Save the assistant's source-aware review separately from critic findings."""
from html import escape as esc
import json
from pathlib import Path
import re

from run import OUT, ROOT, TRIAL, read, save, sha, verify, stamp

REVIEWS = {
    ("education/007", 0): {
        "verdict": "confirmed",
        "confidence": "high",
        "origin": "introduced_by_second_pass",
        "title": "Traveling companions disappear before 'the boys'",
        "assessment": (
            "The source and initial draft explicitly say several college companions sailed "
            "with Adams. The revision removes that introduction but retains 'the boys' at "
            "Eaton Hall and later 'his friends'. This is a real, small continuity break "
            "introduced by the length-reduction pass."
        ),
        "suggested_action": (
            "Restore the short source sentence introducing the college companions near "
            "the sailing sentence, then compensate with an unrelated optional cut."
        ),
        "evidence": [
            {"file": "../education/007/initial.md", "text": "Several of his college companions sailed with him"},
            {"file": "../education/007/draft.md", "text": "At Eaton Hall the boys were awed"},
        ],
    },
    ("education/007", 1): {
        "verdict": "not_confirmed",
        "confidence": "medium",
        "origin": "existing_neighbor",
        "title": "Lee's 'staff' is inferable from the surrounding scene",
        "assessment": (
            "This is in the existing Harvard College draft. The earlier paragraphs identify "
            "the two Petersburg Virginians and Lee's habitual leadership. The next sentence "
            "says he kept his friends under control. Those cues make the military metaphor "
            "understandable; I would not treat this as a required repair."
        ),
        "suggested_action": "No repair recommended on this evidence.",
        "evidence": [
            {"file": "education/007/segments/006.md", "text": "the two others were town-Virginians from Petersburg"},
            {"file": "education/007/segments/006.md", "text": "he kept his temper and his friends under control"},
        ],
    },
    ("education/027", 0): {
        "verdict": "context_dependent",
        "confidence": "medium",
        "origin": "existing_neighbor",
        "title": "Hewitt's political role is underexplained in an existing chapter",
        "assessment": (
            "The existing Indian Summer draft removes the local New York-school "
            "introduction. However, the actual preceding included draft is segment 023 "
            "(024 and 025 are omitted), where Abram Hewitt is named as one of Adams's "
            "serious readers. That preceding chapter was outside this pair's context. "
            "The critic's claim that he has no first name or prior introduction is therefore "
            "too strong. A local political-role gloss may help, but this is not a new "
            "revision defect."
        ),
        "suggested_action": "Review in full reading context before any repair.",
        "evidence": [
            {"file": "context/education-023.md", "text": "Abram Hewitt, Wayne McVeagh, and Hay himself"},
            {"file": "education/027/segments/026.md", "text": "President Cleveland set aside Hewitt"},
        ],
    },
    ("education/027", 1): {
        "verdict": "confirmed",
        "confidence": "medium",
        "origin": "existing_neighbor",
        "title": "'Even there' loses its explicit reference to preserving friendship",
        "assessment": (
            "The existing Indian Summer draft retains 'Even there, Adams would have been "
            "beaten' but removes the sentence saying the friends were trying to save their "
            "personal relation. The broader struggle to retain Hay's company is still "
            "present, so the scene is recoverable, but the connective is locally weakened."
        ),
        "suggested_action": "Restore the personal-relation link or revise the connective in a later repair.",
        "evidence": [
            {"file": "education/027/chapters/026.md", "text": "all they tried to save was the personal relation"},
            {"file": "education/027/segments/026.md", "text": "Even there, Adams would have been beaten"},
        ],
    },
    ("education/027", 2): {
        "verdict": "context_dependent",
        "confidence": "medium",
        "origin": "existing_neighbor",
        "title": "Walcott is unglossed, but already unglossed in the source",
        "assessment": (
            "This name is in the existing Twilight draft, not the revised Dynamo chapter. "
            "Neither the local source nor the draft gives a role gloss; the critic itself "
            "acknowledges this. The surrounding geology discussion suggests his role. "
            "A gloss could improve accessibility, but the supplied evidence does not "
            "establish that abridgment removed an introduction."
        ),
        "suggested_action": "Treat as an optional accessibility improvement, not a demonstrated new defect.",
        "evidence": [
            {"file": "education/027/segments/028.md", "text": "find Walcott so vigorously flinging the ganoid"},
            {"file": "education/027/chapters/028.md", "text": "find Walcott so vigorously acting the part of Comus"},
        ],
    },
    ("education/027", 3): {
        "verdict": "possible",
        "confidence": "medium",
        "origin": "comparison_cut_in_first_pass_referent_weakened_in_second",
        "title": "'All were occult' loses its immediate comparison",
        "assessment": (
            "The local comparison with radium and other radiant matter was already absent "
            "in the initial draft. The second pass further cuts the list of energies' "
            "properties and changes 'any of them' to singular 'any of it', while retaining "
            "'all were occult' and 'the Virgin easiest to handle'. This weakens the local "
            "referent. It is less conclusive than the Berlin finding: radium, rays, and "
            "'both energies' still appear earlier, so a reader can recover the broad "
            "comparison from the chapter."
        ),
        "suggested_action": (
            "Clarify the compared forces with a short source-grounded link. Count this "
            "as a possible local clarity repair, not proven loss of the whole argument."
        ),
        "evidence": [
            {"file": "../education/027/source.md", "text": "It could scarcely be more complex than radium"},
            {"file": "../education/027/initial.md", "text": "Adams knew nothing about any of them"},
            {"file": "../education/027/draft.md", "text": "Adams knew nothing about any of it, but though all were occult"},
            {"file": "../education/027/draft.md", "text": "both energies acted as interchangeable force on man"},
        ],
    },
}


def norm(text):
    return " ".join(text.split())


def main():
    m = read(OUT / "manifest.json")
    verify(m)
    context = OUT / "context/education-023.md"
    context.parent.mkdir(exist_ok=True)
    context.write_bytes((ROOT / "work/education/segments/023.md").read_bytes())
    rows, chapters = [], []
    reports = read(OUT / "coherence_report.json")["reports"]
    for report, group in zip(reports, m["groups"]):
        assert report["group"] == group["path"]
        selected_rows = []
        for index, finding in enumerate(report["findings"]):
            review = REVIEWS[(group["path"], index)]
            for evidence in review["evidence"]:
                assert evidence["text"] in norm((OUT / evidence["file"]).read_text()), evidence
            passage = norm(finding["draft_passage"])
            draft = norm((OUT / group["path"] / "segments" / f"{finding['segment_id']}.md").read_text())
            assert passage in draft, "Critic quoted an absent draft passage"
            row = {
                "group": group["path"], "index": index, "critic": finding,
                "is_selected_revision": finding["segment_id"] == group["selected"],
                "review": review,
            }
            rows.append(row)
            if row["is_selected_revision"]:
                selected_rows.append(row)
        chapters.append({
            "book": group["book"], "segment": group["selected"], "title": group["title"],
            "pairs_checked": len(group["pairs"]), "critic_flags": len(selected_rows),
            "confirmed": sum(x["review"]["verdict"] == "confirmed" for x in selected_rows),
            "possible": sum(x["review"]["verdict"] == "possible" for x in selected_rows),
        })
    assert len(rows) == 6 and sum(x["is_selected_revision"] for x in rows) == 2
    assessment = {
        "reviewer": "Coding assistant, source-aware manual adjudication; no additional model calls",
        "reviewed_at": stamp(), "chapters": chapters, "findings": rows,
        "summary": {"pairs_checked": 8, "selected_revision_flags": 2,
                    "selected_confirmed": 1, "selected_possible": 1,
                    "existing_neighbor_flags": 4, "cost_usd": m["cost_usd"]},
        "limitations": m["limitations"],
        "no_findings_does_not_mean": "No style loss, perfect fidelity, or exhaustive coherence coverage.",
        "repairs_applied": False,
    }
    save(OUT / "assessment.json", assessment)
    table = "".join(
        f"<tr><td>{esc(c['book'])}</td><td>{esc(c['title'])}</td><td>{c['pairs_checked']}</td>"
        f"<td>{c['critic_flags']}</td><td>"
        + ("1 confirmed" if c["confirmed"] else "1 possible" if c["possible"] else "No findings")
        + "</td></tr>" for c in chapters
    )

    def card(row):
        f, r = row["critic"], row["review"]
        group = row["group"]
        links = [
            (f"{group}/segments/{f['segment_id']}.md", "Reviewed draft"),
            (f"{group}/chapters/{f['segment_id']}.md", "Source"),
            (f"{group}/responses/{f['pair']}.json", "Raw critic response"),
        ]
        evidence = "".join(
            f"<li><a href='{esc(e['file'])}'>{esc(e['file'])}</a>: "
            f"<q>{esc(e['text'])}</q></li>" for e in r["evidence"]
        )
        return (
            f"<article><p class='eyebrow'>{esc(group)} · segment {esc(f['segment_id'])} · "
            f"{esc(r['verdict'].replace('_',' '))}</p><h3>{esc(r['title'])}</h3>"
            f"<blockquote>{esc(f['draft_passage'])}</blockquote>"
            f"<p><b>Critic:</b> {esc(f['gate_test_answer'])}</p>"
            f"<p><b>Review:</b> {esc(r['assessment'])}</p>"
            f"<p><b>Proposed follow-up:</b> {esc(r['suggested_action'])}</p>"
            f"<details><summary>Evidence and raw result</summary><ul>{evidence}</ul><p>"
            + " · ".join(f"<a href='{esc(url)}'>{esc(label)}</a>" for url, label in links)
            + "</p></details></article>"
        )

    selected = "".join(card(r) for r in rows if r["is_selected_revision"])
    neighbors = "".join(card(r) for r in rows if not r["is_selected_revision"])
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coherence review — two-pass revisions</title>
<style>
body{margin:0;background:#f5f3ee;color:#23302e;font:17px/1.6 system-ui,sans-serif}
main{max-width:1040px;margin:auto;padding:36px 24px 70px}h1{font-size:2.1rem;line-height:1.2}
h2{margin-top:2.3rem}h3{margin:.3rem 0}a{color:#14604e;overflow-wrap:anywhere}
.eyebrow{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:#536b60}
.stats{display:flex;gap:14px;flex-wrap:wrap}.stats span{padding:9px 15px;background:#e2ebe5;border-radius:7px}
article{background:white;border:1px solid #d9ded7;border-radius:10px;padding:22px;margin:18px 0}
blockquote{margin:16px 0;padding:8px 20px;border-left:3px solid #a1844d;font-family:Georgia,serif}
table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;padding:12px;border-bottom:1px solid #d6dcd7}
.tablewrap{overflow-x:auto}summary{cursor:pointer}li{margin:.6rem 0}
footer{margin-top:36px;border-top:1px solid #d6dcd7;padding-top:18px;font-size:.9rem}
</style><main><p class="eyebrow">Forage · original-target two-pass experiment · 20 October 2026</p>
<h1>Coherence review of the revised chapters</h1>
<p>The critic flagged two passages in the revisions. Source-aware review confirms one
new continuity break in <i>Berlin</i> and identifies one possible local clarity issue
in <i>The Dynamo and the Virgin</i>. Neither Christie revision received a finding.</p>
"""
    html += (
        f"<div class='stats'><span>4 revised chapters</span><span>8 adjacent-pair checks</span>"
        f"<span>Sonnet 5.5</span><span>${m['cost_usd']:.2f} API cost</span></div>"
        "<h2>Coverage</h2><div class='tablewrap'><table><thead><tr><th>Book</th>"
        "<th>Revised chapter</th><th>Pairs</th><th>Flags</th><th>Manual review</th></tr></thead>"
        f"<tbody>{table}</tbody></table></div>"
        "<p>Each check used the exact revised chapter and a genuine preceding or following "
        "chapter from the current production drafts, with source text for both. These are "
        "mixed-version chapter windows, not a newly regenerated whole book.</p>"
        f"<h2>Findings in the revisions</h2>{selected}"
        "<h2>Findings in existing neighbors</h2><p>Four additional flags concern unchanged "
        "neighboring drafts. They are not defects introduced by the two-pass experiment.</p>"
        f"{neighbors}<h2>Method and limits</h2>"
        "<p>The existing <code>forage.coherence.run_coherence</code> stage and "
        "<code>critic_coherence</code> prompt ran unchanged. The recording transport saved "
        "all eight complete responses and token usage, disabled automatic retries, and "
        "checked each request against its frozen preflight input.</p>"
        "<p>The old production cut lists were not supplied because these revisions used "
        "new preservation plans. The prompt's conditional exemption for seams caused by "
        "authorized cuts was therefore inactive. No draft was repaired or published.</p>"
        "<p>This critic checks structural clarity, not style preservation or exhaustive "
        "fidelity. It sees only an adjacent pair; earlier context may change a finding. "
        "The manual review above is separate from the model's raw output.</p>"
        "<footer><a href='assessment.json'>Reviewed findings (JSON)</a> · "
        "<a href='coherence_report.json'>Pipeline reports</a> · "
        "<a href='manifest.json'>Run manifest and input hashes</a> · "
        "<a href='../report.html'>Original two-pass comparison</a> · "
        f"<a href='{PRICING_URL}'>Anthropic pricing used for cost calculation</a></footer></main></html>"
    )
    (OUT / "report.html").write_text(html)
    m.update(status="complete_reviewed", reviewed_at=stamp(),
             summary=assessment["summary"], assessment="assessment.json", report="report.html")
    save(OUT / "manifest.json", m)
    verify(m)
    # Every report link and quoted finding must resolve to the reviewed local artifact.
    links = re.findall(r"href=['\"]([^'\"]+)['\"]", html)
    local_links = [x for x in links if not x.startswith("https://")]
    assert all((OUT / link).exists() for link in local_links)
    save(OUT / "verification.json", {
        "status": "pass", "all_original_inputs_unchanged": True,
        "original_artifacts_checked": len(m["input_hashes"]),
        "frozen_inputs_checked": len(m["frozen_hashes"]),
        "all_six_critic_quotes_present_in_reviewed_drafts": True,
        "all_manual_review_evidence_verified": True,
        "complete_responses": 8, "skipped_pairs": 0,
        "local_report_links_checked": len(local_links),
        "production_text_or_reports_changed": False,
    })
    print(json.dumps(assessment["summary"], indent=2))


PRICING_URL = "https://platform.claude.com/docs/en/models/sonnet-5-5/overview"
if __name__ == "__main__":
    main()
