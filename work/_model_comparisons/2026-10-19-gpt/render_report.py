"""Render a standalone reader and deterministic metrics without API calls."""
import html
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
manifest = json.loads((OUT / "manifest.json").read_text())
prior = json.loads((OUT / "anthropic_manifest.json").read_text())
all_requests = prior["requests"] + manifest["requests"]
preflight = json.loads((OUT / "preflight_assessment.json").read_text())
labels = {"source": "Original source", "baseline": "Existing abridgment",
          "opus55": "Opus 5.5", "sonnet55": "Sonnet 5.5", "astra": "GPT-6 Astra", "sol61": "GPT-6.1 Sol"}


def tokens(text):
    return re.findall(r"\w+(?:['’]\w+)?", text.lower().replace("’", "'"))


def metrics(text, source, target):
    words = len(text.split())
    src, draft = tokens(source), tokens(text)
    source_grams = set(zip(src, src[1:], src[2:], src[3:], src[4:]))
    draft_grams = list(zip(draft, draft[1:], draft[2:], draft[3:], draft[4:]))
    return {"words": words, "target_delta_percent": round((words / target - 1) * 100, 1),
            "compression": round(len(source.split()) / words, 2),
            "paragraphs": len(re.split(r"\n\s*\n", text.strip())),
            "source_five_gram_percent": round(100 * sum(g in source_grams for g in draft_grams) / max(1, len(draft_grams)), 1)}


data, rows, all_metrics = [], [], []
for ch in manifest["chapters"]:
    book, sid = ch["book"], ch["id"]
    base = OUT / book / "baseline"
    source = (base / "chapters" / f"{sid}.md").read_text()
    texts = {"source": source, "baseline": (base / "segments" / f"{sid}.md").read_text()}
    for label in ["opus55", "sonnet55", "astra", "sol61"]:
        path = OUT / book / label / "segments" / f"{sid}.md"
        if path.exists():
            texts[label] = path.read_text()
    title = ("The Great Gatsby" if book == "gatsby" else "Moby-Dick") + " — " + ch["title"]
    data.append({"title": title, "texts": texts,
                 "notes": preflight["chapters"][f"{book}/{sid}"], "target": ch["target_words"]})
    for variant, text in texts.items():
        if variant == "source":
            continue
        m = {"book": book, "chapter": sid, "variant": variant,
             **metrics(text, source, ch["target_words"])}
        all_metrics.append(m)
        rows.append(f"<tr><td>{html.escape(title)}</td><td>{labels[variant]}</td>"
                    f"<td>{m['words']:,}</td><td>{ch['target_words']:,}</td>"
                    f"<td>{m['target_delta_percent']:+.1f}%</td><td>{m['compression']:.2f}×</td>"
                    f"<td>{m['source_five_gram_percent']:.1f}%</td></tr>")
    for req in all_requests:
        if req["book"] == book and sid in req["members"] and req.get("result", {}).get("status") == "failed":
            rows.append(f"<tr><td>{html.escape(title)}</td><td>{labels[req['variant']]}</td>"
                        "<td colspan='5'>No completed draft — see recorded request status</td></tr>")
(OUT / "metrics.json").write_text(json.dumps(all_metrics, indent=2) + "\n")
assessment_path = OUT / "assessment.json"
assessment = json.loads(assessment_path.read_text()) if assessment_path.exists() else {}
for item, chapter in zip(data, manifest["chapters"]):
    item["assessment"] = assessment.get("chapters", {}).get(f"{chapter['book']}/{chapter['id']}", {})
assessment_html = "".join(f"<p>{html.escape(p)}</p>" for p in assessment.get("findings", []))
if not assessment_html:
    assessment_html = "<p>Generation and assessment pending. Baselines and source chapters are available below.</p>"
style_html = ""
style_path = OUT / "style_analysis.json"
if style_path.exists():
    style = json.loads(style_path.read_text())
    style_html = '<section id="style"><h2>Style fidelity review</h2>'
    style_html += "".join(f"<p>{html.escape(p)}</p>" for p in style["findings"])
    style_html += '<div class="table-wrap"><table><thead><tr><th>Chapter</th><th>Stylistic judgment</th></tr></thead><tbody>'
    style_html += "".join(f"<tr><td>{html.escape(r['chapter'])}</td><td>{html.escape(r['judgment'])}</td></tr>" for r in style["chapter_judgments"])
    style_html += '</tbody></table></div>'
    style_html += '<p class="muted">' + html.escape(style["method"]) + '</p>'
    for example in style["examples"]:
        style_html += '<details><summary>' + html.escape(example["title"]) + '</summary>'
        style_html += '<p>' + html.escape(example["interpretation"]) + '</p>'
        for passage in example["passages"]:
            style_html += '<h3>' + html.escape(passage["label"]) + '</h3>'
            if passage.get("unavailable"):
                style_html += '<p>No completed draft.</p>'
            else:
                style_html += '<p class="muted"><a href="' + html.escape(passage["path"], quote=True) + '">Saved text</a> · paragraph ' + str(passage["paragraph"]) + ', line ' + str(passage["line"]) + '</p>'
                style_html += '<blockquote>' + html.escape(passage["text"].replace("\n", " ")) + '</blockquote>'
        style_html += '</details>'
    style_html += '<p><a href="style_analysis.json">Full style analysis data</a></p></section>'
call_rows = []
for req in all_requests:
    r = req.get("result", {})
    call_rows.append(f"<tr><td>{html.escape(req['key'])}</td><td>{html.escape(r.get('status', 'pending'))}</td>"
                     f"<td>{r.get('duration_s', '—')}</td><td>{r.get('output_tokens', '—')}</td>"
                     f"<td>{('$' + format(r['cost_usd'], '.4f')) if r.get('cost_usd') is not None else 'unknown' if r.get('status') == 'failed' else '—'}</td></tr>")
payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forage · GPT and Anthropic comparison · 19 October 2026</title>
<style>
:root{color-scheme:light;--ink:#202d32;--paper:#faf9f5;--line:#d5d9d7;--accent:#145d61}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}
header,main{max-width:1440px;margin:auto;padding:24px 32px}header{border-bottom:1px solid var(--line)}
h1{font-size:30px;line-height:1.2}h2{font-size:21px}p{max-width:1000px}a{color:var(--accent)}
.muted{color:#556466;font-size:14px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}
td,th{border-bottom:1px solid var(--line);padding:9px 12px;text-align:left}th{background:#eaf0ec}
select,button{font:inherit;padding:8px 12px;border:1px solid #9eaead;border-radius:5px;background:white;color:var(--ink)}
label{display:block;margin-bottom:8px}.toolbar{position:sticky;top:0;background:var(--paper);padding:16px 0;z-index:2}
.reader{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pane{min-width:0}.prose{white-space:pre-wrap;font:18px/1.8 Georgia,serif;padding:24px;background:white;border:1px solid var(--line);height:75vh;overflow:auto}
details{border:1px solid var(--line);padding:12px 18px;margin:16px 0}summary{cursor:pointer}footer{margin:24px 0;font-size:14px}
@media(max-width:760px){header,main{padding:16px}.reader{grid-template-columns:1fr}.prose{height:60vh}}
@media print{.prose{height:auto;overflow:visible}.toolbar{position:static}}
</style><header><div class="muted">FORAGE · MODEL EVALUATION · 19 OCTOBER 2026</div>
<h1>Four chapters: GPT, Anthropic, and existing abridgments</h1>
<p>Compare GPT-6 Astra and GPT-6.1 Sol drafts with the earlier Opus 5.5 and Sonnet 5.5 trial, existing abridgments, and original chapters. The new GPT drafts reuse the frozen drafting inputs from the Anthropic trial. This is a drafting-stage evaluation; published books are unchanged.</p>
<p class="muted">GPT batch status: STATUS · GPT generation cost: COST</p></header><main>
STYLE_ANALYSIS
<h2>Overall abridgment assessment</h2>ASSESSMENT
<details><summary>Method and limits</summary><p>The GPT trial reuses the exact saved source, plan, cut inventory, system instructions and Forage draft_lean prompt text from the Anthropic trial. As in Forage’s OpenAI adapter, cached prompt and prompt are concatenated into one user message. A benchmark-only Chat Completions adapter sets medium reasoning, standard service tier, a 32,000-token output limit including reasoning, and disables SDK retries. Existing pipeline chapter parsing is reused. Moby-Dick’s two chapters share one request; Gatsby’s chapter requests are independent.</p>
<p>This is a drafting-stage test, with no new planning, paid critics, repair passes, fallback, or publication. The GPT and Anthropic inputs are identical; their reasoning settings and output ceilings differ. A shared “medium” label does not establish equal reasoning compute across providers. Opus’s first request used maximum effort and timed out; its remaining two used medium. Sonnet used default effort. <a href="../2026-10-19/report.html">Original Anthropic report</a>.</p>
<p>Existing abridgments have drafting and repair history involving GPT-5, Opus 4.7 and Sonnet 4.6, so comparing their final outputs with fresh drafts cannot isolate model version as the sole cause of a difference. One sample per model across four chapters does not establish a general ranking. The qualitative assessment is a source-aware review by the coding assistant, not an independent or blinded judge.</p>
<p>Word counts use whitespace splitting, consistent with the pipeline. Five-gram retention measures how often five consecutive draft words also appear in the source after normalizing case and punctuation; it is a wording-retention measure, not an accuracy or quality score. Cost is calculated from returned usage, including reasoning and cache accounting. Responses token counting was used for preflight; the cost ceiling reserves an extra 1,024 input tokens per request for framing differences.</p></details>
<h2>Length and wording retention</h2><div class="table-wrap"><table><thead><tr><th>Chapter</th><th>Version</th><th>Words</th><th>Target</th><th>Difference</th><th>Compression</th><th>Source 5-grams</th></tr></thead><tbody>ROWS</tbody></table></div>
<h2>Read side by side</h2><div class="toolbar"><label for="chapter">Chapter</label><select id="chapter"></select></div>
<div id="chapter-findings"></div>
<details><summary>Pre-generation checklist and baseline observations</summary><div id="checklist"></div></details>
<div class="reader"><section class="pane"><label for="left">Left version</label><select id="left"></select><article class="prose" id="lefttext"></article></section>
<section class="pane"><label for="right">Right version</label><select id="right"></select><article class="prose" id="righttext"></article></section></div>
<h2>Recorded API usage</h2><div class="table-wrap"><table><thead><tr><th>Request</th><th>Status</th><th>Seconds</th><th>Output tokens incl. thinking</th><th>Cost</th></tr></thead><tbody>CALLS</tbody></table></div>
<p class="muted">Costs use provider token counts, including cache writes/reads and reasoning, at standard API prices for <a href="https://developers.openai.com/api/docs/models/gpt-6-astra">GPT-6 Astra</a>, <a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol">GPT-6.1 Sol</a> and <a href="https://platform.claude.com/docs/en/models/overview">Anthropic models</a>. The earlier Anthropic trial recorded $0.8695 plus one timed-out call with unknown cost; its conservative total upper bound was $3.57. The header cost covers this GPT batch only. Prices exclude taxes or account-specific adjustments. Local artifacts: <a href="manifest.json">manifest</a> · <a href="metrics.json">metrics</a> · <a href="assessment.json">full assessment</a> · <a href="preflight_assessment.json">pre-generation checklist</a>.</p>
<details><summary>Configuration finding for a future full pipeline run</summary><p>CONFIGURATION_NOTE</p></details>
<footer>Saved outputs only. No API calls or changes to live content occur when opening this report.</footer></main>
<script>const data=PAYLOAD;const labels={source:'Original source',baseline:'Existing abridgment',opus55:'Opus 5.5',sonnet55:'Sonnet 5.5',astra:'GPT-6 Astra',sol61:'GPT-6.1 Sol'};
const chapter=document.getElementById('chapter');data.forEach((d,i)=>chapter.add(new Option(d.title,i)));
function drawText(side){document.getElementById(side+'text').textContent=data[Number(chapter.value)].texts[document.getElementById(side).value]||'Not generated';}
function draw(){const d=data[Number(chapter.value)];['left','right'].forEach(side=>{const s=document.getElementById(side);let selected=s.value;s.replaceChildren();Object.keys(d.texts).forEach(k=>s.add(new Option(labels[k],k)));s.value=d.texts[selected]?selected:side==='left'?'baseline':d.texts.astra?'astra':d.texts.sol61?'sol61':d.texts.opus55?'opus55':d.texts.sonnet55?'sonnet55':'source';drawText(side);});const c=document.getElementById('checklist');c.replaceChildren();const p=document.createElement('p');p.textContent=d.notes.baseline_observation;c.append(p);const ul=document.createElement('ul');d.notes.inspect.forEach(t=>{const li=document.createElement('li');li.textContent=t;ul.append(li)});c.append(ul);if(d.notes.cut_plan_caveat){const p=document.createElement('p');p.textContent=d.notes.cut_plan_caveat;c.append(p)}const f=document.getElementById('chapter-findings');f.replaceChildren();if(d.assessment.judgment){const h=document.createElement('h3');h.textContent=d.assessment.judgment;f.append(h);const list=document.createElement('ul');d.assessment.observations.forEach(t=>{const li=document.createElement('li');li.textContent=t;list.append(li)});f.append(list)}}
chapter.addEventListener('change',draw);['left','right'].forEach(s=>document.getElementById(s).addEventListener('change',()=>drawText(s)));draw();
</script></html>'''
for key, value in {"STATUS": html.escape(manifest["status"]),
                   "COST": ("$" + format(manifest["recorded_generation_cost_usd"], ".4f") + " recorded; total upper bound $" + format(manifest["total_cost_upper_bound_usd"], ".2f")) if "recorded_generation_cost_usd" in manifest else "in progress",
                   "ASSESSMENT": assessment_html, "ROWS": "".join(rows),
                   "STYLE_ANALYSIS": style_html,
                   "CALLS": "".join(call_rows),
                   "CONFIGURATION_NOTE": html.escape(assessment.get("configuration_note", "No finding recorded.")),
                   "PAYLOAD": payload}.items():
    page = page.replace(key, value)
(OUT / "report.html").write_text(page)
print(OUT / "report.html")
