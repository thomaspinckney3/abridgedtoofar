"""Read-only verification of frozen inputs, API provenance and generated prose."""
import json
import re
import trial as t


def main():
    m = t.verify()
    calls = []
    for response in sorted(t.OUT.rglob('*.response.json')):
        r = t.read(response)
        stage = response.name.removesuffix('.response.json')
        request = response.with_name(stage + '.request.json')
        start = response.with_name(stage + '.started.json')
        assert t.sha(request) == t.read(start)['request_sha256']
        payload = t.read(request)
        assert payload['model'] == r['model'] == t.MODEL
        assert r['stop_reason'] == 'end_turn'
        assert payload['output_config'] == {'effort': 'medium'}
        assert payload['service_tier'] == 'standard_only'
        calls.append({'path': str(response.relative_to(t.OUT)), 'cost_usd': r['cost_usd'], 'stop_reason': r['stop_reason']})
    rows = []
    for b, ids in t.SAMPLES.items():
        folder = t.OUT / b
        planning = t.read(folder / 'planning.request.json')
        t.audit_target_framing(planning['system'])
        selected = t.read(folder / 'selected_chapters.json')
        for sid in ids:
            f = folder / sid
            plan = t.read(f / 'plan.json')
            previous = t.read(f / 'previous.plan.json')
            target = round(previous['target_words'] * 4 / 3)
            assert plan['target_words'] == target
            assert next(x['target_words'] for x in selected if x['id'] == sid) == target
            assert sum(s['words'] for s in plan['sections']) == target
            assert t.read(f / 'draft.preflight.json')['plan_sha256'] == t.sha(f / 'plan.json')
            t.audit_target_framing(json.dumps(plan))
            req = t.read(f / 'draft.request.json')
            t.audit_target_framing(req['system'])
            instructions = req['messages'][0]['content'].split('# Complete original chapter')[0]
            t.audit_target_framing(instructions)
            assert json.dumps(plan, ensure_ascii=False, indent=2) in instructions
            body = t.read(f / 'draft.response.json')['text']
            prose, notes = t._extract_chapter_notes(body)
            assert (f / 'draft.md').read_text() == prose.strip() + '\n'
            checks = t.read(f / 'checks.json')
            assert len(prose.split()) == checks['words']
            assert len(re.findall(r'<!--\s*FORAGE_CHAPTER_NOTES', body)) == 1
            local = (f / 'source.md').read_text()
            paras = t.paragraphs(local)
            full = t.norm((folder / 'full_source.txt').read_text())
            local_start = full.index(t.norm(local)); local_end = local_start + len(t.norm(local))
            for a in plan['verbatim']:
                assert t.norm(a['text']) in t.norm(paras[a['paragraph'] - 1])
            for d in plan['dependencies']:
                assert t.norm(d['local_evidence']) in t.norm(local)
                assert t.norm(d['other_evidence']) in full[:local_start] or t.norm(d['other_evidence']) in full[local_end:]
            protected = [t.norm(a['text']) in t.norm(prose) for a in plan['verbatim']]
            assert protected == [x['present'] for x in checks['protected']]
            rows.append({'chapter': b + '/' + sid, 'fixed_target': target, 'words': checks['words'],
                'protected_present': sum(protected), 'protected_total': len(protected),
                'verified_dependency_pairs': len(plan['dependencies']),
                'prose_identical_to_provider_response': True, 'fixed_target_prompt_audit': 'pass'})
    cost = round(sum(c['cost_usd'] for c in calls), 6)
    assert cost <= m['maximum_cost_usd']
    result = {'status': 'pass', 'live_artifacts_unchanged': len(m['input_hashes']),
        'frozen_inputs_unchanged': len(m['frozen_hashes']),
        'previous_experiment_artifacts_unchanged': len(m['previous_artifact_hashes']),
        'chapters': rows, 'calls': calls, 'cost_usd': cost,
        'announced_maximum_usd': m['maximum_cost_usd'],
        'meaning': 'Verification of provenance and measurements; this does not assert editorial perfection or exact target compliance.'}
    t.save(t.OUT / 'verification.json', result)
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
