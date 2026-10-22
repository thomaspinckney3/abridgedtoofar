"""Verified full-run inputs for the common downstream production workflow.

The snapshot proves where accepted prose came from. It does not pretend that
classification or the standard drafter produced it, and refresh never repeats
those stages or changes the original inclusion/target decisions.
"""
from __future__ import annotations

from .artifacts import read_json
from .production_state import (atomic_json, digest, inventory, sha256_file,
                               text_inputs, verify_inventory)
from .publication import verify_revision
from .review_anchors import paragraphs
from .revision_review import public_responses

INPUTS = 'full_run_inputs.json'
PREPARATION = ('plan.json', 'chapters.json', 'chapter_classifications.json',
               'cuts.json', 'book_synopsis.md', 'pipeline_review.json')


def record_inputs(book, plan):
    """Store source provenance in new immutable full-run publications."""
    atomic_json(book.work_dir / INPUTS, {
        'version': 1, 'source_sha256': sha256_file(book.source_path),
        'metadata_sha256': digest(book.metadata),
        'chapters': inventory(book.work_dir, [f"chapters/{s['id']}.md" for s in plan['segments']]),
    })


def origin_revision(book, state):
    if state.get('full_run_origin'):
        return state['full_run_origin']
    path = book.work_dir / 'full_run_result.json'
    if path.exists() and not state.get('draft_units'):
        result = read_json(path)
        if result.get('status') != 'complete':
            raise ValueError('Full run is not complete')
        return result['review_revision']
    return None


class FullRunOrigin:
    def __init__(self, book, revision):
        self.book = book
        self.manifest = verify_revision(book, revision)
        self.revision = revision
        self.root = book.work_dir / 'publications' / revision
        self.plan = read_json(self.root / 'plan.json')
        stages = self.manifest['stage_summary']['stages']
        if not {'preservation_planning', 'two_pass', 'final_review'} <= set(stages):
            raise ValueError('Publication is not a completed full-run origin')
        self.model = self.manifest['stage_summary']['quality']['model']
        self.preparation = [i for i in self.manifest['outputs'] if i['path'] in PREPARATION]
        if {i['path'] for i in self.preparation} != set(PREPARATION):
            raise ValueError('Full-run preparation inventory is incomplete')
        if not verify_inventory(book.work_dir, self.preparation):
            raise ValueError('Full-run preparation changed; start a new run for source or plan changes')
        self._verify_sources()

    def _verify_sources(self):
        path = self.root / INPUTS
        if path.exists():
            inputs = read_json(path)
            if (inputs.get('version') != 1
                    or inputs['source_sha256'] != sha256_file(self.book.source_path)
                    or inputs['metadata_sha256'] != digest(self.book.metadata)
                    or not verify_inventory(self.book.work_dir, inputs['chapters'])):
                raise ValueError('Full-run source inputs changed')
            self.sources = inputs['chapters']
            return
        # Publications before source inventories used a workspace run manifest.
        # Verify its original source hash and each retained chapter against the
        # immutable alignment; never adopt unverified legacy draft provenance.
        run_path = self.book.work_dir.parent.parent / 'run.json'
        if not run_path.exists():
            raise ValueError('Legacy full run is missing its source manifest')
        run = read_json(run_path)
        source_name = f'books/{self.book.book_id}/{self.book.source_path.name}'
        expected = {i['path']: i['sha256'] for i in run['inputs']}
        if expected.get(source_name) != sha256_file(self.book.source_path):
            raise ValueError('Full-run source inputs changed')
        names = []
        for segment in self.plan['segments']:
            sid = segment['id']
            path = self.book.work_dir / 'chapters' / f'{sid}.md'
            original = f'work/{self.book.book_id}/chapters/{sid}.md'
            expected_hash = expected.get(original + '.orig', expected.get(original))
            if expected_hash != sha256_file(path):
                raise ValueError(f'Full-run source chapter changed: {sid}')
            names.append(f'chapters/{sid}.md')
            alignment = self.root / 'alignments' / f'{sid}.json'
            if alignment.exists() and read_json(alignment)['source_paragraphs'] != paragraphs(path.read_text()):
                raise ValueError(f'Full-run source alignment changed: {sid}')
        self.sources = inventory(self.book.work_dir, names)

    def validate_options(self, config):
        if config['iterate'] or config['coherence'] or config['coherence_fix']:
            raise ValueError('Full-run refresh preserves accepted prose; request changes through review feedback')

    def unchanged(self, config):
        """A first no-op sync reuses the exact publication without model calls."""
        if (config['outputs'] != self.manifest['selected_outputs']
                or any(config['resolved_models'][key] != self.model for key in ('ALIGN', 'CRITIC_BOOK'))
                or not verify_inventory(self.book.work_dir, self.manifest['outputs'])):
            return False
        pointer = read_json(self.book.work_dir / 'review_current.json')
        if pointer['revision'] != self.revision:
            return False
        ledger = self.book.work_dir / 'editorial/review_apply_ledger.json'
        responses = public_responses(read_json(ledger)) if ledger.exists() else {'version': 1, 'entries': []}
        published = self.root / 'review_responses.json'
        return responses == (read_json(published) if published.exists() else {'version': 1, 'entries': []})

    def reusable_stage(self, name, config):
        """Import verified downstream outputs when only review responses changed."""
        names = {'assembly': {'abridgment.md', 'abridgment.txt', 'assembly_report.json'},
                 'book_critic': {'book_critic.json'}, 'validation': {'validation_report.json'},
                 'alignment': {'proofread.html'}}
        if name not in names:
            return None
        expected = {i['path']: i['sha256'] for i in self.manifest['outputs']}
        if any(expected.get(i['path']) != i['sha256'] for i in text_inputs(self.book)):
            return None
        model_key = {'alignment': 'ALIGN', 'book_critic': 'CRITIC_BOOK'}.get(name)
        if model_key and config['resolved_models'][model_key] != self.model:
            return None
        paths = names[name]
        if name == 'alignment':
            paths = paths | {p for p in expected if p.startswith('alignments/')}
        outputs = [i for i in self.manifest['outputs'] if i['path'] in paths]
        if {i['path'] for i in outputs} != paths or not verify_inventory(self.book.work_dir, outputs):
            return None
        metadata = {'origin_revision': self.revision}
        if name == 'book_critic':
            metadata['verdict'] = read_json(self.root / 'book_critic.json')['verdict']
        return {'outputs': outputs, 'metadata': metadata}

    def quality(self):
        """Measure current prose while identifying the original review as history."""
        from .target_revision import normalized, words
        checks = {}
        for segment in self.plan['segments']:
            if segment.get('diegetic_status') != 'diegetic' or segment.get('skipped') or segment['target_word_count'] <= 0:
                continue
            sid, target = segment['id'], segment['target_word_count']
            text = (self.book.work_dir / 'segments' / f'{sid}.md').read_text()
            checks[sid] = {'words': words(text), 'target_words': target,
                'target_delta_words': words(text) - target, 'target_matched': words(text) == target,
                'protected': [{'text': s['passage_hint'], 'present': normalized(s['passage_hint']) in normalized(text)}
                              for s in segment.get('signatures', [])]}
        quality = {'origin_revision': self.revision, 'review_status': 'awaiting_human_review',
                   'historical_fidelity': self.manifest['stage_summary']['quality'],
                   'words': sum(c['words'] for c in checks.values()),
                   'target_words': sum(c['target_words'] for c in checks.values()),
                   'missing_protected': sum(not p['present'] for c in checks.values() for p in c['protected'])}
        atomic_json(self.book.work_dir / 'fixed_target_checks.json', checks)
        atomic_json(self.book.work_dir / 'production_quality.json', quality)
        return {'outputs': inventory(self.book.work_dir, ['production_quality.json', 'fixed_target_checks.json']),
                'metadata': quality}
