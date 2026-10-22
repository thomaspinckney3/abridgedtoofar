"""Verify both passes, counted feedback, source evidence and immutable inputs."""
import json
import trial as t
from forage import target_revision as pipeline


def main():
    manifest = t.verify()
    for rel in ['forage/target_revision.py','prompts/preservation_plan.md','prompts/draft_fixed_target.md','prompts/revise_fixed_target.md']:
        original_hash = t.sha(t.OUT / 'implementation' / rel)
        current_hash = t.sha(t.ROOT / rel)
        if current_hash != original_hash:
            change = next(c for c in t.read(t.OUT/'post_run_validation_fix.json')['changes'] if c['path']==rel)
            assert change['executed_sha256']==original_hash and change['current_sha256']==current_hash
    rows = []
    for book, ids in t.SAMPLES.items():
        f = t.OUT / book
        selected = [{**c, 'source': (f/c['id']/'source.md').read_text()} for c in t.read(f/'selected_chapters.json')]
        validated = pipeline.validate_plans((f/'full_source.txt').read_text(), selected, t.read(f/'plan.raw.json'))
        built_plan = pipeline.planning_request(t.read(f/'metadata.json'), (f/'full_source.txt').read_text(), selected)
        sent_plan = t.read(f/'planning.request.json')
        assert built_plan['prompt'] == sent_plan['messages'][0]['content'] and built_plan['system'] == sent_plan['system']
        original = {s['id']: s for s in t.read(f/'original_plan.json')['segments']}
        for sid in ids:
            p = f/sid
            plan = t.read(p/'plan.json')
            assert plan == next(x for x in validated if x['id'] == sid)
            assert plan['target_words'] == original[sid]['target_word_count']
            run = p/'two_pass'
            measured = []
            for stage in ['initial','revision']:
                payload = t.read(run/(stage+'.request.json'))
                built = t.read(run/(stage+'.input.json'))
                assert payload['messages'][0]['content'] == built['prompt']
                assert payload['system'] == built['system']
                raw = t.read(run/(stage+'.response.json'))
                prose, notes = pipeline.split_response(raw['text'])
                assert (run/(stage+'.md')).read_text() == prose+'\n'
                assert t.read(run/(stage+'.notes.json')) == notes
                assert t.read(run/(stage+'.checks.json')) == pipeline.measure(prose,plan)
                assert t.read(run/(stage+'.preflight.json'))['plan_sha256'] == t.sha(p/'plan.json')
                measured.append(pipeline.measure(prose,plan))
            rebuilt_initial = pipeline.build_request('draft_fixed_target', dict(book=t.read(f/'metadata.json'), preservation_plan=plan, original_source=(p/'source.md').read_text()), model='anthropic:'+t.MODEL, stage=f'target_revision:initial:{sid}')
            assert rebuilt_initial == t.read(run/'initial.input.json')
            initial = (run/'initial.md').read_text().strip()
            revised = (run/'revision.md').read_text().strip()
            rebuilt, feedback = pipeline.revision_request(t.read(f/'metadata.json'), (p/'source.md').read_text(),plan,initial)
            assert t.read(run/'revision.input.json') == rebuilt
            assert t.read(run/'measured_feedback.json') == feedback
            assert t.read(run/'measured_changes.json') == pipeline.measured_changes(initial,revised)
            assert (p/'initial.md').read_bytes() == (run/'initial.md').read_bytes()
            assert (p/'draft.md').read_bytes() == (run/'revision.md').read_bytes()
            pipeline._review(t.read(run/'revision.notes.json'),len(feedback['first_draft_paragraphs']))
            rows.append({'chapter':book+'/'+sid,'target_words':plan['target_words'],
                         'initial':measured[0],'revision':measured[1],
                         'cut_evaluations':len(t.read(run/'revision.notes.json')['cut_evaluation']),
                         'dependency_evidence_pairs':len(plan['dependencies']),
                         'prose_matches_provider':True,'feedback_matches_mechanical_count':True})
    calls=[]
    for p in sorted(t.OUT.rglob('*.response.json')):
        r=t.read(p); stem=p.name.removesuffix('.response.json')
        request=p.with_name(stem+'.request.json')
        assert t.sha(request) == t.read(p.with_name(stem+'.started.json'))['request_sha256']
        assert r['model']==t.MODEL and r['stop_reason']=='end_turn'
        payload=t.read(request)
        assert payload['output_config']=={'effort':'medium'}
        assert payload['service_tier']=='standard_only'
        calls.append({'path':str(p.relative_to(t.OUT)),'cost_usd':r['cost_usd']})
    cost=round(sum(c['cost_usd'] for c in calls),6)
    assert cost <= manifest['maximum_cost_usd']
    result={'status':'pass','live_artifacts_unchanged':len(manifest['input_hashes']),
            'previous_experiment_artifacts_unchanged':len(manifest['previous_artifact_hashes']),
            'frozen_inputs_unchanged':len(manifest['frozen_hashes']),
            'executed_implementation_snapshot_verified':True,'current_code_renders_identical_model_requests':True,'post_run_validation_fix':t.read(t.OUT/'post_run_validation_fix.json'),'chapters':rows,
            'calls':calls,'cost_usd':cost,
            'limits':'Provenance and arithmetic verification; not a declaration of editorial quality or target compliance.'}
    t.save(t.OUT/'verification.json',result)
    print(json.dumps({'status':'pass','chapters':len(rows),'calls':len(calls),'cost_usd':cost},indent=2))

if __name__=='__main__':main()
