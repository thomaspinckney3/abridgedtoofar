"""Render the full-run records without modifying prose or provider artifacts."""
from pathlib import Path
import html
import json
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def esc(value):
    return html.escape(str(value))


def count(path):
    return len(path.read_text().split()) if path.exists() else None


def render():
    manifest = read(ROOT / 'run.json')
    responses = [read(p) for p in (ROOT / 'calls').rglob('response.json')]
    cost = sum(r['cost_usd'] for r in responses)
    unknown = [read(p) for p in (ROOT / 'calls').rglob('started.json')
               if not (p.parent / 'response.json').exists()]
    reserve = sum(r['maximum_cost_usd'] for r in unknown)
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>Full book run — Opus 5.5</title><style>',
             'body{max-width:1100px;margin:32px auto;padding:0 20px;font:17px/1.5 system-ui;color:#202820;background:#fafbf8}',
             'h1,h2,h3{line-height:1.2}a{color:#186646}table{border-collapse:collapse;width:100%;font-size:14px}',
             'th,td{padding:9px;text-align:left;border-bottom:1px solid #d9e1d5}th{background:#eaf0e6}',
             '.scroll{overflow-x:auto}details{padding:12px 0;border-bottom:1px solid #d9e1d5}',
             'blockquote{border-left:3px solid #b8c8b0;margin:12px 0;padding-left:16px}small{color:#596457}',
             '.must_fix{color:#9e351f}.should_improve{color:#896100}.tradeoff{color:#45644b}',
             '</style><h1>Full book run · Opus 5.5</h1>',
             f'<p>Run status: <strong>{esc(manifest["status"])}</strong>. '
             f'{len(responses)} recorded responses; completed-response cost <strong>${cost:.2f}</strong>.</p>',
             f'<p>{len(unknown)} requests have no final usage report; ${reserve:.2f} remains conservatively reserved. '
             'Recorded usage is not a statement of the account’s total charge.</p>',
             '<p>Original fixed targets; counted two-pass drafting; source-aware review and local repairs. '
             'These are local review artifacts. Model findings remain editorial judgments.</p>']
    for bid in manifest['books']:
        work = ROOT / 'work' / bid
        plan = read(work / 'plan.json')
        result = read(work / 'full_run_result.json', {})
        review_label = result.get('final_review_label', 'final_review')
        parts += [f'<h2>{esc(plan["title"])}</h2>']
        if not result:
            stages = [(name, len(list(work.glob(pattern)))) for name, pattern in
                      [('counted revisions', 'two_pass/*/draft.md'),
                       ('first reviews', 'fidelity/initial_review/???.json'),
                       ('first repairs', 'repairs/initial_review/???.md'),
                       ('second reviews', 'fidelity/repair_review/???.json'),
                       ('second repairs', 'repairs/repair_review/???.md'),
                       ('final reviews', 'fidelity/final_review/???.json')]]
            parts += ['<p>' + '; '.join(f'{n} {name}' for name, n in stages) + '.</p>']
        if result:
            parts += [f'<p>{result["words"]:,} words / {result["target_words"]:,} target. '
                      f'{result["exact_target_chapters"]}/{result["chapters"]} chapters exactly at target. '
                      f'Book critic: {esc(result["book_critic"])}. '
                      f'{result["unresolved_must_fix"]} final must-fix candidates; '
                      f'{result["unresolved_should_improve"]} should-improve candidates.</p>']
        scope = read(work / 'book_critic_scope_assessment.json')
        if scope:
            parts += [f'<p>{esc(scope["assessment"])}</p>']
        links = [(name, f'work/{bid}/{path}') for name, path in
                 [('Read abridgment', 'abridgment.txt'), ('Source comparison', 'proofread.html'),
                  ('Book critic', 'book_critic.json'), ('Full checks', 'fixed_target_checks.json'),
                  ('Omission assessment', 'book_critic_scope_assessment.json')]
                 if (work / path).exists()]
        if not result and (work / 'preview/working-draft.txt').exists():
            links.append(('Current working text — reviews incomplete', f'work/{bid}/preview/working-draft.txt'))
        parts += ['<p>' + ' · '.join(f'<a href="{url}">{name}</a>' for name, url in links) + '</p>',
                  '<div class="scroll"><table><thead><tr><th>Chapter</th><th>Target</th><th>First</th>'
                  '<th>Second</th><th>Final</th><th>Difference</th><th>Final findings</th></tr></thead><tbody>']
        all_findings = []
        for chapter in plan['segments']:
            if chapter.get('skipped') or chapter.get('target_word_count', 0) <= 0:
                continue
            sid = chapter['id']
            first = count(work / 'two_pass' / sid / 'initial.md')
            second = count(work / 'two_pass' / sid / 'revision.md')
            final = count(work / 'segments' / f'{sid}.md')
            report = read(work / 'fidelity' / review_label / f'{sid}.json', {})
            findings = report.get('findings', [])
            totals = Counter(f['priority'] for f in findings)
            cells = [f'{sid} · {chapter.get("title", "")}', chapter['target_word_count'],
                     first, second, final, final - chapter['target_word_count'] if final else None,
                     ', '.join(f'{v} {k}' for k, v in totals.items()) if report else None]
            parts += ['<tr>' + ''.join(f'<td>{esc(c) if c is not None else "—"}</td>' for c in cells) + '</tr>']
            all_findings.extend((sid, f) for f in findings)
        parts += ['</tbody></table></div>']
        if all_findings:
            parts += ['<h3>Final review findings</h3><p>Expand a finding to inspect its claim, counterevidence, and proposed repair.</p>']
        for sid, f in all_findings:
            parts += [f'<details><summary class="{esc(f["priority"])}">{sid} · {esc(f["priority"])} · {esc(f["title"])}</summary>',
                      f'<p>{esc(f["claim"])}</p><p><strong>Counterevidence:</strong> {esc(f.get("counterevidence", ""))}</p>',
                      f'<p><strong>Suggested repair:</strong> {esc(f.get("minimal_repair", ""))}</p>']
            for e in f.get('evidence', []):
                parts += [f'<blockquote>{esc(e["quote"])}<br><small>{esc(e["document"])} · paragraph {e["paragraph"]}</small></blockquote>']
            parts += ['</details>']
    parts += ['</html>']
    (ROOT / 'report.html').write_text('\n'.join(parts))
    print(ROOT / 'report.html')


if __name__ == '__main__':
    render()
