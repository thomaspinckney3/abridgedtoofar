"""Compare completed new drafts with the frozen previous automatic drafts."""
import json
import trial as t
from report import grams

rows = []
for b, ids in t.SAMPLES.items():
    for sid in ids:
        f = t.OUT / b / sid
        if not (f / 'draft.md').exists(): continue
        source = (f / 'source.md').read_text()
        prior = (f / 'previous.md').read_text()
        new = (f / 'draft.md').read_text()
        plan = t.read(f / 'plan.json')
        oldplan = t.read(f / 'previous.plan.json')
        oldtarget, target = oldplan['target_words'], plan['target_words']
        previous_words, words = len(prior.split()), len(new.split())
        sg = set(grams(source))
        def reuse(text):
            gs = grams(text)
            return round(100 * sum(g in sg for g in gs) / len(gs), 2)
        row = {'chapter': b+'/'+sid, 'title': plan['title'], 'source_words': len(source.split()),
            'previous_target': oldtarget, 'previous_words': previous_words,
            'previous_delta_percent': round(100 * (previous_words / oldtarget - 1), 2),
            'fixed_target': target, 'new_words': words,
            'new_delta_percent': round(100 * (words / target - 1), 2),
            'change_from_previous_words': words - previous_words,
            'previous_reuse_percent': reuse(prior), 'new_reuse_percent': reuse(new),
            'previous_protected_words': oldplan['protected_words'], 'new_protected_words': plan['protected_words'],
            'protected_present': sum(t.norm(v['text']) in t.norm(new) for v in plan['verbatim']),
            'protected_total': len(plan['verbatim']),
            'prior_anchors_retained': sum(t.norm(v['text']) in t.norm(new) for v in oldplan['verbatim']),
            'prior_anchors_total': len(oldplan['verbatim'])}
        rows.append(row)
summary = {'chapters': rows}
if rows:
    summary.update({'mean_absolute_target_deviation_percent': {
        'previous': round(sum(abs(r['previous_delta_percent']) for r in rows)/len(rows), 2),
        'new': round(sum(abs(r['new_delta_percent']) for r in rows)/len(rows), 2)},
        'total_words': {'previous': sum(r['previous_words'] for r in rows), 'new': sum(r['new_words'] for r in rows)},
        'note': 'Old and new deviations use their respective targets. Prior anchors are a diagnostic only; the new model received only its newly generated plan.'})
t.save(t.OUT / 'comparison.json', summary)
print(json.dumps(summary, indent=2))
