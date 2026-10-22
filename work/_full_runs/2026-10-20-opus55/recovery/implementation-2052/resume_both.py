"""Resume both approved full runs, retaining every settled provider response."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO))
from dotenv import load_dotenv
from forage.full_run import Journal, emit, load_book, read_json, run_book, stamp, write
from forage.publication import verify_revision

load_dotenv(REPO / '.env')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--retry-credit-errors', action='store_true',
                    help='Use only after the user requests a funded-account retry.')
parser.add_argument('--workers', type=int, default=4)
args = parser.parse_args()
if (ROOT / 'calls/credit_blocked.json').exists() and not args.retry_credit_errors:
    raise SystemExit('Provider credit stop is still active; this cap-only resume cannot clear it.')
generate = Journal(ROOT / 'calls', max_usd=350, max_calls=600,
                   retry_credit_errors=args.retry_credit_errors)
# Retrying this operational cap does not clear a later provider credit rejection.
generate.retry_credit_errors = True
manifest = read_json(ROOT / 'run.json')
write(ROOT / 'recovery' / ('before-resume-' + stamp().replace(':', '-') + '.json'), manifest)
manifest.update(status='running', max_usd=350, max_calls=600, resumed_at=stamp(),
                results={}, errors={}, workers=args.workers, concurrent_books=2)
write(ROOT / 'run.json', manifest)

def one(bid):
    book = load_book(bid, workspace=ROOT)
    done = book.work_dir / 'full_run_result.json'
    if done.exists():
        result = read_json(done)
        verify_revision(book, result['review_revision'])
        return result
    return run_book(book, generate, args.workers)

with ThreadPoolExecutor(max_workers=2) as pool:
    futures = {pool.submit(one, bid): bid for bid in manifest['books']}
    for future in as_completed(futures):
        bid = futures[future]
        try:
            manifest['results'][bid] = future.result()
        except Exception as exc:
            manifest['errors'][bid] = {'type': type(exc).__name__, 'error': str(exc)}
            emit('book_failed', book=bid, **manifest['errors'][bid])
        manifest['usage'] = generate.totals()
        write(ROOT / 'run.json', manifest)
manifest.update(status='failed' if manifest['errors'] else 'complete',
                finished_at=stamp(), usage=generate.totals())
write(ROOT / 'run.json', manifest)
emit('run_finished', status=manifest['status'], usage=manifest['usage'])
if manifest['errors']:
    raise SystemExit(1)
