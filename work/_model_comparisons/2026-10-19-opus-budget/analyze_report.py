"""Free, deterministic comparison and self-contained reader for the frozen trial."""
import difflib
import html
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent


def read(name):
    return json.loads((OUT / name).read_text())


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def grams(text):
    words = re.findall(r"\w+(?:['’]\w+)?", text.lower().replace("’", "'"))
    return [tuple(words[i:i + 5]) for i in range(len(words) - 4)]


def normalized(text):
    return " ".join(text.translate(str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'})).split())


def main():
    plan = read("preservation_plan.json")
    labels = {"source": "Original source", "existing": "Existing abridgment",
              "opus_before": "Opus 5.5 · before", "revision": "Opus 5.5 · revised",
              "sonnet": "Sonnet 5.5", "astra": "GPT-6 Astra", "sol": "GPT-6.1 Sol"}
    texts = {key: (OUT / ("revision.md" if key == "revision" else f"inputs/{key}.md")).read_text()
             for key in labels}
    source_grams = set(grams(texts["source"]))
    protected_grams = set().union(*(set(grams(v["text"])) for v in plan["verbatim"]))
    metrics = []
    for key, text in texts.items():
        all_grams = grams(text)
        unprotected = [g for g in all_grams if g not in protected_grams]
        n = len(text.split())
        metrics.append({
            "variant": key, "label": labels[key], "words": n,
            "target_delta_percent": round((n / 2300 - 1) * 100, 2),
            "source_length_percent": round(n / len(texts["source"].split()) * 100, 2),
            "source_five_gram_percent": round(sum(g in source_grams for g in all_grams) / len(all_grams) * 100, 2),
            "unprotected_five_gram_percent": round(sum(g in source_grams for g in unprotected) / len(unprotected) * 100, 2),
            "unprotected_five_gram_windows": len(unprotected),
            "protected_exact": [v["id"] for v in plan["verbatim"] if normalized(v["text"]) in normalized(text)],
        })
    save("metrics.json", metrics)
    before = texts["opus_before"].split()
    after = texts["revision"].split()
    opcodes = difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    diff = {"method": "Whitespace-token SequenceMatcher, case and punctuation sensitive; diagnostic alignment, not a semantic edit classification.",
            "before_words": len(before), "after_words": len(after), "net_removed": len(before) - len(after),
            "net_removed_percent": round((len(before) - len(after)) / len(before) * 100, 2),
            "unchanged_words": sum(j - i for tag, i, j, a, b in opcodes if tag == "equal"),
            "delete_only_words": sum(j - i for tag, i, j, a, b in opcodes if tag == "delete"),
            "replace_old_words": sum(j - i for tag, i, j, a, b in opcodes if tag == "replace"),
            "replace_new_words": sum(b - a for tag, i, j, a, b in opcodes if tag == "replace"),
            "insert_only_words": sum(b - a for tag, i, j, a, b in opcodes if tag == "insert")}
    save("diff_summary.json", diff)
    diff_parts = []
    for tag, i, j, a, b in opcodes:
        if tag == "equal": diff_parts.append(html.escape(" ".join(after[a:b])))
        else:
            if j > i: diff_parts.append('<del>' + html.escape(" ".join(before[i:j])) + '</del>')
            if b > a: diff_parts.append('<ins>' + html.escape(" ".join(after[a:b])) + '</ins>')
    (OUT / "word_diff.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Opus revision: word diff</title><style>body{max-width:900px;margin:2rem auto;padding:1rem;font:19px/1.75 Georgia,serif}del{background:#ffe3e3;color:#812929}ins{background:#dcf5df;color:#14562b}a{color:#255ca5}</style><h1>Opus revision: word diff</h1><p>Deleted words are crossed out in red; additions are underlined in green. Whitespace-token alignment; paragraph breaks are omitted.</p><p><a href="report.html">Return to comparison</a></p><article>''' + " ".join(diff_parts) + '</article></html>')
    raw_response = read("response.json")["text"]
    notes_blocks = re.findall(r"<!--\s*FORAGE_CHAPTER_NOTES\s*(.*?)\s*-->", raw_response, re.S)
    assert len(notes_blocks) == 1
    raw_notes = json.loads(notes_blocks[0])
    save("revision.notes.raw.json", raw_notes)
    assessment = read("assessment.json") if (OUT / "assessment.json").exists() else {"verdict": "Manual assessment pending.", "findings": [], "caveats": []}
    payload = {"plan": plan, "checks": read("checks.json"), "manifest": read("manifest.json"),
               "metrics": metrics, "texts": texts, "labels": labels, "assessment": assessment,
               "notes": raw_notes, "diff": diff}
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Gatsby II · Opus budget experiment</title>
<style>
:root{color-scheme:light;--ink:#202a32;--muted:#56616c;--line:#ccd5da;--paper:#fff;--accent:#176b61}*{box-sizing:border-box}body{margin:0;background:#f4f6f5;color:var(--ink);font:16px/1.6 system-ui,sans-serif}main{max-width:1440px;margin:auto;padding:28px}header,section{margin-bottom:24px}h1{font-size:clamp(25px,4vw,40px);line-height:1.2}h2{font-size:23px}h3{font-size:18px}a{color:#185c95}p{max-width:100ch}li{margin-bottom:8px}.card{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:22px}.muted{color:var(--muted)}.badge{display:inline-block;padding:5px 11px;background:#e1efe9;border-radius:5px;margin:0 5px 7px 0;font-weight:600}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);white-space:nowrap}.highlight{background:#e7f4ec}details{margin:12px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace}.readers{display:grid;grid-template-columns:1fr 1fr;gap:24px}.reader{min-width:0}.reader label{display:block;font-weight:700;margin-bottom:8px}select{max-width:100%;width:100%;font:inherit;padding:10px;border:1px solid var(--line);border-radius:5px;background:white;color:var(--ink)}.chapter{margin-top:15px;font:19px/1.8 Georgia,serif}.chapter p{white-space:pre-wrap;overflow-wrap:anywhere}.chapter p::before{content:attr(data-p);float:left;font:11px/1.8 system-ui;color:#7d858b;margin-left:-16px;padding-top:7px}blockquote{border-left:3px solid var(--accent);padding-left:16px;margin:10px 0;font-family:Georgia,serif}.anchor{color:#165d3e;font-weight:600}@media(max-width:800px){main{padding:14px}.card{padding:17px}.readers{grid-template-columns:1fr}.chapter{font-size:18px}th,td{padding:8px}}
</style></head><body><main>
<header><p class="muted">Forage · isolated editorial experiment · 19 October 2026</p><h1>Can Opus meet the budget and keep Fitzgerald’s voice?</h1><p id="verdict"></p><div id="badges"></div><p id="cost" class="muted"></p></header>
<section class="card"><h2>What changed</h2><p>One revision of the existing 3,187-word Opus draft, using the full source, a bounded preservation plan, and a concise operational specification. Same Opus 5.5 medium effort; one generation call, no retry. Target: 2,300 words; target range: 2,185–2,415; ceiling: 2,760. The nine protected spans total 515 words. The coding assistant specified the plan before generation, informed by the earlier comparison.</p><ul id="findings"></ul><h3>Limits and tradeoffs</h3><ul id="caveats"></ul></section>
<section class="card"><h2>Saved results compared</h2><div class="scroll"><table><thead><tr><th>Version</th><th>Words</th><th>Vs target</th><th>Source length</th><th>5-gram reuse</th><th>Excluding protected 5-grams</th></tr></thead><tbody id="metrics"></tbody></table></div><p class="muted">Wording reuse is the share of consecutive five-word windows also found in the source after case and punctuation normalization. It is not a style or quality score. The last column excludes any window whose five-word sequence occurs in one of the protected passages. This does not control for other differences in selection or length. Prior model samples were first drafts; this is a revision with an assistant-authored plan.</p><p><a href="word_diff.html">Inspect every deletion and addition</a> · <a href="../2026-10-19-gpt/report.html">Earlier multi-chapter comparison and style review</a></p></section>
<section class="card"><h2>Evidence and preservation checks</h2><div id="evidence"></div><details><summary>Checked before/after cut list</summary><ul id="cuts"></ul></details><details><summary>Nine protected passages</summary><div id="protected"></div></details><details><summary>Full frozen preservation plan</summary><pre id="plan"></pre></details><details><summary>Model’s revision notes — complete, self-reported</summary><pre id="notes"></pre></details><p><a href="request.txt">Exact user prompt</a> · <a href="request.json">Provider request</a> · <a href="assessment.json">Editorial assessment</a> · <a href="manifest.json">Run manifest</a> · <a href="revision.md">Revised chapter</a></p></section>
<section><h2>Read side by side</h2><p class="muted">Select any saved version. Numbers identify paragraphs within that version, not cross-version anchors.</p><div class="readers"><article class="reader card"><label for="left">Left version</label><select id="left"></select><div class="chapter" id="leftText"></div></article><article class="reader card"><label for="right">Right version</label><select id="right"></select><div class="chapter" id="rightText"></div></article></div></section>
</main><script id="data" type="application/json">__DATA__</script><script>
const d=JSON.parse(document.getElementById('data').textContent), el=id=>document.getElementById(id);
el('verdict').textContent=d.assessment.verdict;
const c=d.checks;
for(const s of [`${c.words.toLocaleString()} words`,`${c.target_delta_percent>0?'+':''}${c.target_delta_percent}% vs target`,`${c.protected.filter(x=>x.present).length}/9 protected spans`,c.within_target_range?'Within target range':'Outside target range']){const e=document.createElement('span');e.className='badge';e.textContent=s;el('badges').append(e)}
el('cost').textContent=`One call · $${d.manifest.result.cost_usd.toFixed(4)} · ${d.manifest.result.duration_s}s · provider stop: ${d.manifest.result.stop_reason} · local experiment; no publication`;
for(const id of ['findings','caveats'])for(const s of d.assessment[id]||[]){const e=document.createElement('li');e.textContent=s;el(id).append(e)}
for(const cut of d.assessment.actual_revision_changes||[]){const e=document.createElement('li');e.textContent=`${cut.unit}: ${cut.change}`;el('cuts').append(e)}
for(const m of d.metrics){const row=document.createElement('tr');if(m.variant==='revision')row.className='highlight';for(const v of [m.label,m.words.toLocaleString(),m.variant==='source'?'—':`${m.target_delta_percent>0?'+':''}${m.target_delta_percent}%`,`${m.source_length_percent}%`,`${m.source_five_gram_percent}%`,`${m.unprotected_five_gram_percent}%`]){const e=document.createElement('td');e.textContent=v;row.append(e)}el('metrics').append(row)}
for(const v of d.plan.verbatim){const e=document.createElement('details'),s=document.createElement('summary'),q=document.createElement('blockquote');s.textContent=`${v.id} · ${v.purpose} · ${v.words} words · ${c.protected.find(x=>x.id===v.id).present?'PASS':'FAIL'}`;s.className='anchor';q.textContent=v.text;e.append(s,q);el('protected').append(e)}
for(const x of d.assessment.examples||[]){const e=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('p');s.textContent=x.title;p.textContent=x.observation;e.append(s,p);for(const pass of x.passages){const h=document.createElement('h3'),q=document.createElement('blockquote');h.textContent=d.labels[pass.variant];q.textContent=pass.text;e.append(h,q)}el('evidence').append(e)}
el('plan').textContent=JSON.stringify(d.plan,null,2);el('notes').textContent=JSON.stringify(d.notes,null,2);
for(const side of ['left','right']){for(const [value,label] of Object.entries(d.labels)){const o=document.createElement('option');o.value=value;o.textContent=label;el(side).append(o)}el(side).value=side==='left'?'opus_before':'revision';const render=()=>{el(side+'Text').replaceChildren();d.texts[el(side).value].trim().split(/\n\s*\n/).forEach((text,i)=>{const p=document.createElement('p');p.dataset.p=i+1;p.textContent=text.replace(/\s*\n\s*/g,' ');el(side+'Text').append(p)})};el(side).addEventListener('change',render);render()}
</script></body></html>'''
    # JSON is embedded as data; escape closing tags to keep source text inert.
    (OUT / "report.html").write_text(template.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")))
    print(json.dumps({"metrics": metrics, "diff": diff}, indent=2))


if __name__ == "__main__":
    main()
