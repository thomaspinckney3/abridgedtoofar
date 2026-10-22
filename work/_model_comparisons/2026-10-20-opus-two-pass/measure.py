"""Mechanical comparison of first and second passes; no provider calls."""
import json
import trial as t
from report import grams
from forage import target_revision as pipeline

rows=[]
for b,ids in t.SAMPLES.items():
    for sid in ids:
        f=t.OUT/b/sid
        if not (f/'two_pass/result.json').exists(): continue
        result=t.read(f/'two_pass/result.json')
        plan=t.read(f/'plan.json')
        source=(f/'source.md').read_text()
        initial=(f/'initial.md').read_text()
        revised=(f/'draft.md').read_text()
        source_grams=set(grams(source))
        def reuse(text):
            gs=grams(text)
            return round(100*sum(g in source_grams for g in gs)/len(gs),2)
        prior=t.PREVIOUS.parent/'2026-10-20-opus-crossbook'/b/sid
        prior_words=len((prior/'draft.md').read_text().split())
        review=t.read(f/'two_pass/revision.notes.json')
        para=pipeline.paragraphs(initial)
        contradicted=[]
        for i,entry in enumerate(review['cut_evaluation']):
            if entry['action'] in {'cut','compress'} and all(pipeline.normalized(para[j-1]) in pipeline.normalized(revised) for j in entry['paragraph_ids']):
                contradicted.append({'evaluation_index':i,'entry':entry,'reason':'Every referenced paragraph survives verbatim despite a cut/compress label; inspect the rationale.'})
        rows.append({'chapter':b+'/'+sid,'title':plan['title'],'target':plan['target_words'],
                     'source_words':len(source.split()),'first':result['initial'],
                     'revision':result['revision'],'words_removed_net':result['measured_changes']['net_words_removed'],
                     'initial_reuse_percent':reuse(initial),'revision_reuse_percent':reuse(revised),
                     'source_retained_percent':round(100*len(revised.split())/len(source.split()),2),
                     'earlier_original_target_draft_words':prior_words,
                     'earlier_larger_target_draft_words':len((f/'previous.md').read_text().split()),
                     'cut_evaluation_entries':len(review['cut_evaluation']),
                     'cut_evaluation_flags':contradicted,'reported_infeasible':review['infeasible']})
summary={'chapters':rows}
if rows:
    summary['mean_absolute_target_deviation_percent']={k:round(sum(abs(r[k]['target_delta_percent']) for r in rows)/len(rows),2) for k in ['first','revision']}
    summary['total_words']={k:sum(r[k]['words'] for r in rows) for k in ['first','revision']}
    summary['protected']={k:{'present':sum(a['present'] for r in rows for a in r[k]['protected']), 'total':sum(len(r[k]['protected']) for r in rows)} for k in ['first','revision']}
t.save(t.OUT/'comparison.json',summary)
print(json.dumps(summary,indent=2))
