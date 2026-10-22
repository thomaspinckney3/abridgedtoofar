"""Compare frozen sources and generated outputs; no API calls."""
import html
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent


def read(p): return json.loads(p.read_text())
def save(p, data): p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
def grams(text):
    w = re.findall(r"\w+(?:['’]\w+)?", text.lower().replace("’", "'"))
    return [tuple(w[i:i+5]) for i in range(len(w)-4)]


def main():
    manifest = read(OUT / "manifest.json")
    chapters = []
    for book, ids in manifest["samples"].items():
        meta = read(OUT / book / "metadata.json")
        selected = read(OUT / book / "selected_chapters.json")
        for sid in ids:
            folder = OUT / book / sid
            case = next(x for x in selected if x["id"] == sid)
            plan = read(folder / "plan.json") if (folder / "plan.json").exists() else None
            texts = {v: (folder / (v + ".md")).read_text() for v in ["source", "existing", "previous", "draft"] if (folder / (v + ".md")).exists()}
            source_grams = set(grams(texts["source"]))
            previous_plan = read(folder / "previous.plan.json")
            protected = set().union(*(set(grams(v["text"])) for v in previous_plan["verbatim"] + (plan["verbatim"] if plan else [])))
            metrics = []
            for variant, text in texts.items():
                n = len(text.split()); gs = grams(text); rest = [g for g in gs if g not in protected]
                metrics.append({"variant": variant, "words": n,
                    "target_delta_percent": round(100*(n/case["target_words"]-1),2),
                    "source_length_percent": round(100*n/len(texts["source"].split()),2),
                    "five_gram_reuse_percent": round(100*sum(g in source_grams for g in gs)/len(gs),2),
                    "outside_protected_reuse_percent": round(100*sum(g in source_grams for g in rest)/len(rest),2) if rest else None})
            chapters.append({"key": book + "/" + sid, "book": book, "id": sid,
                "book_title": meta["title"], "author": meta["author"], "title": case["title"],
                "target": case["target_words"], "previous_target": previous_plan["target_words"], "previous_plan": previous_plan, "plan": plan, "texts": texts, "metrics": metrics,
                "checks": read(folder / "checks.json") if (folder / "checks.json").exists() else None,
                "notes": read(folder / "draft.notes.raw.json") if (folder / "draft.notes.raw.json").exists() else None,
                "blocked": read(folder / "blocked.json") if (folder / "blocked.json").exists() else (read(OUT / book / "blocked.json") if (OUT / book / "blocked.json").exists() else None)})
    save(OUT / "metrics.json", [{"chapter": c["key"], "target": c["target"], "variants": c["metrics"]} for c in chapters])
    assessment = read(OUT / "assessment.json") if (OUT / "assessment.json").exists() else {"summary": "Generation or manual assessment pending.", "findings": [], "limits": manifest["limitations"], "chapters": {}}
    calls = [{"path": str(p.relative_to(OUT)), **{k: read(p)[k] for k in ["model", "stop_reason", "usage", "cost_usd", "duration_s"]}} for p in sorted(OUT.rglob("*.response.json"))]
    data = {"manifest": manifest, "chapters": chapters, "assessment": assessment, "calls": calls,
            "known_cost_usd": round(sum(c["cost_usd"] for c in calls),6)}
    template = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forage · Larger fixed targets</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f5;color:#24313a;font:16px/1.65 system-ui,sans-serif}main{max-width:1460px;margin:auto;padding:28px}header,section{margin-bottom:24px}h1{font-size:clamp(26px,4vw,39px);line-height:1.2}h2{font-size:23px}h3{font-size:18px}p{max-width:105ch}.muted{color:#5a6670}.card{padding:24px;background:#fff;border:1px solid #cbd6d5;border-radius:10px}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:10px;border-bottom:1px solid #d5dedc;text-align:left;white-space:nowrap}th{vertical-align:bottom}a{color:#155e91}li{margin:8px 0}select{font:inherit;padding:9px;width:100%;max-width:100%;border:1px solid #b8c8c7;border-radius:5px;background:#fff;color:inherit}label{display:block;font-weight:600;margin-bottom:8px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:24px}.reader{min-width:0}.chapter{font:19px/1.8 Georgia,serif}.chapter p{white-space:pre-wrap;overflow-wrap:anywhere}.chapter p::before{content:attr(data-p);font:11px system-ui;color:#778488;float:left;margin:10px 0 0 -16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 ui-monospace,monospace}details{margin:14px 0}summary{font-weight:600;cursor:pointer}blockquote{margin:10px 0;padding-left:16px;border-left:3px solid #238271;font:17px/1.7 Georgia,serif}.badge{display:inline-block;margin:0 7px 7px 0;padding:5px 10px;background:#e0efe7;border-radius:5px}.flow{display:flex;gap:16px;flex-wrap:wrap}.flow p{flex:1;min-width:190px;border-left:3px solid #238271;padding-left:12px}.pass{color:#176a4a}.fail{color:#9a3d26}@media(max-width:800px){main{padding:14px}.card{padding:18px}.cols{grid-template-columns:1fr}.chapter{font-size:18px}td,th{padding:8px}}
</style></head><body><main>
<header><p class="muted">Forage · 20 October 2026 · isolated experiment</p><h1>What happens with one larger fixed target?</h1><p id="summary"></p><p id="cost" class="muted"></p></header>
<section class="card"><h2>Experiment design</h2><div class="flow"><p><strong>1. Whole book → plans</strong><br>Opus rereads each complete original book and regenerates plans for the same four chapters, using one shared rubric and a fixed target rounded from the previous target × 4/3.</p><p><strong>2. Code validates</strong><br>Quoted evidence must exist, protected text must fit the 25% cap, and section weights become budgets summing exactly to target. All evidence passed validation on the first attempt in this run; no repair calls were needed.</p><p><strong>3. Source + plan → draft</strong><br>A separate call abridges each original chapter using the validated plan and compact operational instructions.</p><p><strong>4. Measure and review</strong><br>Count words, verify protected text and inspect continuity, source fidelity, style and planning choices. Each response is preserved unchanged. No trim pass or post-generation rewrite was run.</p></div><p>No chapter-specific preservation choices were written or edited by the coding assistant. Existing abridgments were withheld from both model stages and retained only for comparison. Model and effort: Opus 5.5, medium. The model sees one fixed word target and section allocations adding to it. Earlier drafts and targets are withheld. Both the target size and its framing changed, and regenerated plans can choose different priorities.</p><p><a href="planning_prompt.txt">Shared planning prompt</a> · <a href="drafting_prompt.txt">Shared drafting prompt</a> · <a href="manifest.json">Run manifest</a> · <a href="trial.py">Experiment harness</a></p></section>
<section class="card"><h2>Results</h2><div class="scroll"><table><thead><tr><th>Chapter</th><th>Prior target</th><th>Prior words</th><th>Fixed target</th><th>New words</th><th>New vs target</th><th>Exact spans</th><th>Prior → new<br>wording reuse</th></tr></thead><tbody id="results"></tbody></table></div><p class="muted">Wording reuse: the percentage of consecutive five-word windows that also occur in the source after case and punctuation normalization. It is not a style or quality score. The previous automatic trial used the same model and shared planning rubric. Different draft lengths and newly generated plans affect comparison; this is not a controlled model ranking. Wording reuse outside protected excerpts excludes the union of old and new protected five-word windows.</p><ul id="findings"></ul><h3>Interpretation</h3><ul id="next"></ul><h3>Limits</h3><ul id="limits"></ul><p><a href="assessment.json">Complete assessment</a> · <a href="verification.json">Artifact verification</a></p></section>
<section class="card"><h2>Inspect a chapter</h2><label for="chapter">Chapter</label><select id="chapter"></select><h3 id="chapterTitle"></h3><div id="badges"></div><p id="chapterVerdict"></p><ul id="chapterFindings"></ul><div id="examples"></div><details><summary>Automatically selected exact passages</summary><div id="anchors"></div></details><details><summary>Cross-chapter dependencies identified by the planner</summary><div id="dependencies"></div></details><details><summary>Full generated and validated plan</summary><pre id="plan"></pre></details><details><summary>Draft model’s complete reviewer notes</summary><pre id="notes"></pre></details><p id="links"></p></section>
<section><h2>Read side by side</h2><div class="cols"><article class="reader card"><label for="left">Left version</label><select id="left"></select><div class="chapter" id="leftText"></div></article><article class="reader card"><label for="right">Right version</label><select id="right"></select><div class="chapter" id="rightText"></div></article></div></section>
</main><script id="data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent),el=id=>document.getElementById(id),labels={source:'Original source',existing:'Production abridgment',previous:'Previous automatic draft',draft:'Larger fixed-target draft'};
const node=(tag,text)=>{const x=document.createElement(tag);x.textContent=text;return x};
el('summary').textContent=data.assessment.summary;
el('cost').textContent=`${data.calls.length} completed calls · $${data.known_cost_usd.toFixed(4)} known API cost · full-book planning plus chapter drafting · no production publication`;
for(const id of ['findings','limits'])for(const s of data.assessment[id]||[])el(id).append(node('li',s));
for(const s of data.assessment.next_pipeline_changes||[])el('next').append(node('li',s));
for(const c of data.chapters){const row=document.createElement('tr'),old=c.metrics.find(x=>x.variant==='previous'),fresh=c.metrics.find(x=>x.variant==='draft'),checks=c.checks;for(const text of [`${c.author}: ${c.title}`,c.previous_target,old.words,c.target,fresh?.words??'—',fresh?`${fresh.target_delta_percent>0?'+':''}${fresh.target_delta_percent}%`:'—',checks?`${checks.protected.filter(x=>x.present).length}/${checks.protected.length}`:'—',`${old.five_gram_reuse_percent}% → ${fresh?fresh.five_gram_reuse_percent+'%':'—'}`])row.append(node('td',text));el('results').append(row);const o=node('option',`${c.author} — ${c.title}`);o.value=c.key;el('chapter').append(o)}
function active(){return data.chapters.find(c=>c.key===el('chapter').value)}
function reader(side){const c=active();el(side+'Text').replaceChildren();const text=c.texts[el(side).value]||'No output available.';text.trim().split(/\n\s*\n/).forEach((p,i)=>{const e=node('p',p.replace(/\s*\n\s*/g,' '));e.dataset.p=i+1;el(side+'Text').append(e)})}
function render(){const c=active(),a=data.assessment.chapters[c.key]||{};el('chapterTitle').textContent=c.book_title+' · '+c.title;el('chapterVerdict').textContent=a.verdict||JSON.stringify(c.blocked||'Assessment pending');for(const id of ['badges','chapterFindings','examples','anchors','dependencies','links'])el(id).replaceChildren();if(c.checks){for(const s of [`${c.checks.words} words`,`Fixed target: ${c.target}`,`${c.checks.target_delta_words>0?'+':''}${c.checks.target_delta_words} words (${c.checks.target_delta_percent>0?'+':''}${c.checks.target_delta_percent}%)`]){const e=node('span',s);e.className='badge';el('badges').append(e)}}for(const f of a.findings||[])el('chapterFindings').append(node('li',f));for(const ex of a.examples||[]){const d=document.createElement('details');d.append(node('summary',ex.title),node('p',ex.observation));for(const p of ex.passages)d.append(node('h3',labels[p.variant]),node('blockquote',p.text));el('examples').append(d)}for(const v of c.plan?.verbatim||[]){const d=document.createElement('details');const present=c.checks?.protected.find(x=>x.id===v.id)?.present;const s=node('summary',`${v.id}: ${v.purpose} · ${v.words} words · ${present===undefined?'pending':present?'PASS':'FAIL'}`);s.className=present?'pass':'fail';d.append(s,node('blockquote',v.text));el('anchors').append(d)}for(const dep of c.plan?.dependencies||[]){const d=document.createElement('details');d.append(node('summary',dep.instruction),node('h3','This chapter'),node('blockquote',dep.local_evidence),node('h3',dep.other_chapter),node('blockquote',dep.other_evidence));el('dependencies').append(d)}el('plan').textContent=JSON.stringify(c.plan,null,2);el('notes').textContent=JSON.stringify(c.notes,null,2);for(const [label,file] of [['Source','source.md'],['Production','existing.md'],['Previous trial','previous.md'],['New draft','draft.md'],['Plan','plan.json'],['Checks','checks.json']]){if((file==='draft.md'&&!c.texts.draft)||(file==='plan.json'&&!c.plan)||(file==='checks.json'&&!c.checks))continue;const a=node('a',label);a.href=c.key+'/'+file;el('links').append(a,document.createTextNode(' · '))}for(const side of ['left','right']){el(side).replaceChildren();for(const v of Object.keys(c.texts)){const o=node('option',labels[v]);o.value=v;el(side).append(o)}el(side).value=side==='left'?'previous':c.texts.draft?'draft':'source';reader(side)}}
el('chapter').addEventListener('change',render);for(const side of ['left','right'])el(side).addEventListener('change',()=>reader(side));render();
</script></body></html>'''
    (OUT / "report.html").write_text(template.replace("__DATA__", json.dumps(data,ensure_ascii=False).replace("</", "<\\/")))
    print(json.dumps({"chapters": len(chapters), "drafts": sum('draft' in c['texts'] for c in chapters), "cost_usd": data['known_cost_usd']},indent=2))


if __name__ == "__main__": main()
