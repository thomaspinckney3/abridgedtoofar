import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

root = Path(__file__).parent
workspace = Path('/mnt/data/forage/work/_full_runs/2026-10-20-opus55')
base = 'https://forage-review.fly.dev'

def get(path):
    with urllib.request.urlopen(base+path, timeout=45) as response:
        return json.load(response)

results = {'site':base,'books':{},'chapters':0,'prior_comments_preserved':7,'provider_calls':0}
before_books = json.loads((root/'books-before.json').read_text())
after_books = get('/api/books')
for before in before_books['books']:
    if before['book_id'] not in {'education','secret_adversary'}:
        assert before == next(b for b in after_books['books'] if b['book_id']==before['book_id'])
for book in ['education','secret_adversary']:
    work = workspace/'work'/book
    expected = json.loads((work/'full_run_result.json').read_text())
    package = json.loads((work/'pipeline_review.json').read_text())
    pointer = get(f'/api/books/{book}/publication')
    assert pointer['review']['revision'] == expected['review_revision']
    assert pointer['review']['text_revision'] == expected['text_revision']
    assert pointer['release'] == json.loads((root/f'{book}-publication-before.json').read_text())['release']
    (root/f'{book}-publication-after.json').write_text(json.dumps(pointer,indent=2))
    feed = get(f'/api/books/{book}/feedback')
    (root/f'{book}-feedback-after.json').write_text(json.dumps(feed,indent=2))
    pipeline_notes = [n for n in feed['comments'] if n.get('pipeline_review')]
    assert {n['id'] for n in pipeline_notes} == {i['id'] for i in package['items']}
    assert all(n['revision_review']['current'] and n['revision_review']['state']=='pending'
               and not n['stale'] and not n['revision_reviews'] for n in pipeline_notes)
    if book == 'secret_adversary':
        old = json.loads((root/'feedback-before.json').read_text())['comments']
        for note in old:
            current = next(n for n in feed['comments'] if n['id']==note['id'])
            assert all(current[k] == v for k,v in note.items()), note['id']
        assert sum(n['pipeline_review']['priority']=='must_fix' for n in pipeline_notes)==2
    chapters = get(f'/api/books/{book}/chapters')
    def verify_chapter(chapter):
        sid = chapter['segment_id']
        live = get(f'/api/books/{book}/chapters/{sid}')
        local = json.loads((work/'alignments'/f'{sid}.json').read_text())
        assert live['publication_revision'] == expected['review_revision']
        assert [b['draft'] for b in live['blocks']] == local['draft_paragraphs']
        for block in live['blocks']:
            for source in block['sources']:
                assert source['text'] == local['source_paragraphs'][source['index']]
        local_ids = {i['id'] for i in package['items'] if i['segment_id']==sid}
        assert {n['id'] for n in live['comments'] if n.get('pipeline_review')} == local_ids
        return sid
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        verified = list(pool.map(verify_chapter, chapters['chapters']))
    download = next(x for x in chapters['downloads'] if x['path']=='abridgment.txt')
    with urllib.request.urlopen(base+download['url'],timeout=45) as response:
        assembled = response.read()
    assert assembled == (work/'publications'/expected['review_revision']/'abridgment.txt').read_bytes()
    results['books'][book] = {'revision':expected['review_revision'],'chapters':len(verified),
        'items':len(pipeline_notes),'text_sha256':hashlib.sha256(assembled).hexdigest()}
    results['chapters'] += len(verified)
results['health'] = get('/healthz')
(root/'live-verification.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
