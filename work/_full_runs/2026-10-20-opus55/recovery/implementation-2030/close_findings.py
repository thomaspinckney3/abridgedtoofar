"""Close final blocking findings with local edits, then review and finish again.

No offsetting cuts are allowed: a final coherence correction must not start
another round of length-driven deletions. Original targets remain measured.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[2]))
from dotenv import load_dotenv
from forage import target_revision as tr
from forage.full_run import (Journal, MODEL, apply_replacements, book_lock, emit,
    evidence_check, finish, load_book, parallel, read_json, review, review_context,
    validated_json, write)
from forage.production import required_segments
from forage.publication import verify_revision


def close(book, generate):
    with book_lock(book):
        w = book.work_dir
        previous = read_json(w / 'full_run_result.json')
        if previous.get('final_review_label') == 'release_review':
            verify_revision(book, previous['review_revision'])
            return previous
        verify_revision(book, previous['review_revision'])
        write(w / 'pre_closure_result.json', previous)
        ids = [s['id'] for s in required_segments(read_json(w / 'plan.json'))]
        drafts = {sid: (w / 'segments' / f'{sid}.md').read_text().strip() for sid in ids}
        folder = w / 'repairs' / 'blocking_closure'
        folder.mkdir(parents=True, exist_ok=True)

        def one(sid):
            text = drafts[sid]
            context, documents = review_context(book, sid, drafts)
            plan = context['preservation_plan']
            report = read_json(w / 'fidelity/final_review' / f'{sid}.json')
            candidates = [f for f in report['findings'] if f['priority'] == 'must_fix']
            if not candidates:
                value = {'adjudications': [], 'replacements': [], 'remaining_concerns': []}
            else:
                context.update(candidate_findings=candidates, measurements=tr.measure(text, plan))
                request = tr.build_request('fidelity_repair', context, model=MODEL,
                    stage=f'blocking_closure:{book.book_id}:{sid}', max_tokens=20000,
                    target_words=plan['target_words'], actual_words=tr.words(text),
                    difference_words=tr.words(text) - plan['target_words'])
                request['prompt'] += (
                    '\n\nFINAL COHERENCE CLOSURE: only the supplied must_fix candidates are in scope. '
                    'Adjudicate each against source and current text. Make only the smallest edits '
                    'needed for confirmed defects. Preserve the original fixed target, but do not '
                    'make unrelated edits, optional restorations, or offsetting cuts in this pass. '
                    'Code reports the actual word delta. Each replacement must name at least one '
                    'confirmed finding_id. Every confirmed finding must be addressed by a replacement. '
                    'Each old string must be at most 150 words. Keep all other prose unchanged.')

                def validate(value):
                    judgments = value['adjudications']
                    if sorted(a['id'] for a in judgments) != sorted(f['id'] for f in candidates):
                        raise ValueError('Adjudicate every blocking candidate exactly once')
                    for a in judgments:
                        if a['decision'] not in {'confirmed', 'rejected', 'uncertain'}:
                            raise ValueError('Invalid adjudication')
                        if not a.get('reason') or not a.get('evidence'):
                            raise ValueError('Adjudication needs evidence and rationale')
                        evidence_check(a['evidence'], documents)
                    confirmed = {a['id'] for a in judgments if a['decision'] == 'confirmed'}
                    covered = set()
                    for patch in value['replacements']:
                        linked = set(patch.get('finding_ids', []))
                        if not linked or not linked <= confirmed:
                            raise ValueError('Every patch must address confirmed blocking findings only')
                        if tr.words(patch['old']) > 150:
                            raise ValueError('Closing patch must be at most 150 words')
                        covered.update(linked)
                    if covered != confirmed:
                        raise ValueError('Every confirmed finding needs a patch')
                    apply_replacements(text, value['replacements'], plan)
                    return value

                value = validated_json(generate, request, validate)
            revised = apply_replacements(text, value['replacements'], plan)
            value.update(checks=tr.measure(revised, plan),
                         measured_changes=tr.measured_changes(text, revised))
            write(folder / f'{sid}.json', value)
            (folder / f'{sid}.md').write_text(revised + '\n')
            emit('closure_ready', book=book.book_id, chapter=sid,
                 candidates=len(candidates), patches=len(value['replacements']))

        parallel(ids, one, 8)
        drafts = {sid: (folder / f'{sid}.md').read_text().strip() for sid in ids}
        parallel(ids, lambda sid: review(book, sid, drafts, generate, 'release_review'), 8)
        result = finish(book, drafts, generate, 8, 'release_review')
        write(w / 'closure_result.json', result)
        return result


if __name__ == '__main__':
    load_dotenv(ROOT.parents[2] / '.env')
    generate = Journal(ROOT / 'calls', max_usd=350, max_calls=600)
    generate.retry_credit_errors = True
    result = close(load_book(sys.argv[1], workspace=ROOT), generate)
    emit('closure_complete', book=sys.argv[1], **result)
