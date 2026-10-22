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
    validate_review, validated_json, write)
from forage.production import required_segments
from forage.publication import verify_revision


def close(book, generate, round_number=1):
    with book_lock(book):
        w = book.work_dir
        suffix = '' if round_number == 1 else f'_{round_number}'
        input_label = ('final_review' if round_number == 1 else
                       'release_review' if round_number == 2 else f'release_review_{round_number - 1}')
        output_label = 'release_review' + suffix
        phase = 'blocking_closure' + suffix
        previous = read_json(w / 'full_run_result.json')
        if previous.get('final_review_label') == output_label:
            verify_revision(book, previous['review_revision'])
            return previous
        if previous.get('final_review_label') != input_label:
            raise ValueError(f'Expected completed {input_label} before {output_label}')
        verify_revision(book, previous['review_revision'])
        write(w / f'pre_closure{suffix}_result.json', previous)
        ids = [s['id'] for s in required_segments(read_json(w / 'plan.json'))]
        drafts = {sid: (w / 'segments' / f'{sid}.md').read_text().strip() for sid in ids}
        folder = w / 'repairs' / phase
        folder.mkdir(parents=True, exist_ok=True)

        def one(sid):
            text = drafts[sid]
            context, documents = review_context(book, sid, drafts)
            plan = context['preservation_plan']
            report = read_json(w / 'fidelity' / input_label / f'{sid}.json')
            candidates = [f for f in report['findings'] if f['priority'] == 'must_fix']
            if not candidates:
                value = {'adjudications': [], 'replacements': [], 'remaining_concerns': []}
            else:
                context.update(candidate_findings=candidates, measurements=tr.measure(text, plan))
                request = tr.build_request('fidelity_repair', context, model=MODEL,
                    stage=f'{phase}:{book.book_id}:{sid}', max_tokens=20000,
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

        parallel(ids, one, 4)
        drafts = {sid: (folder / f'{sid}.md').read_text().strip() for sid in ids}

        def final_check(sid):
            context, documents = review_context(book, sid, drafts)
            prior = w / 'fidelity' / input_label
            if context == read_json(prior / f'{sid}.inputs.json'):
                # Reuse only if the entire source/draft/dependency context is identical.
                # Any changed central chapter or supplied partner triggers a fresh review.
                report = read_json(prior / f'{sid}.json')
                validate_review(report, sid, documents, len(context['dependencies']))
                destination = w / 'fidelity' / output_label
                write(destination / f'{sid}.json', report)
                write(destination / f'{sid}.inputs.json', context)
                write(destination / f'{sid}.provenance.json', {
                    'reused_from': f'fidelity/{input_label}/{sid}.json',
                    'reason': 'Entire review context is identical; no provider call required.'})
                emit('review_reused', book=book.book_id, chapter=sid,
                     pass_name=output_label, reason='identical complete context')
            else:
                review(book, sid, drafts, generate, output_label)

        parallel(ids, final_check, 4)
        result = finish(book, drafts, generate, 4, output_label)
        write(w / f'closure{suffix}_result.json', result)
        return result


if __name__ == '__main__':
    load_dotenv(ROOT.parents[2] / '.env')
    generate = Journal(ROOT / 'calls', max_usd=350, max_calls=600)
    generate.retry_credit_errors = True
    round_number = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if round_number < 1:
        raise ValueError('Closure round must be positive')
    result = close(load_book(sys.argv[1], workspace=ROOT), generate, round_number)
    emit('closure_complete', book=sys.argv[1], **result)
