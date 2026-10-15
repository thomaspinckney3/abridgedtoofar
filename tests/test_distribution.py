"""Build/install proof independent of the checkout and its writable artifacts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_installed_wheel_resources_and_offline_workspace(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    source = tmp_path / 'build-source'; source.mkdir()
    for name in ['pyproject.toml', 'setup.py', 'MANIFEST.in']:
        shutil.copyfile(repository / name, source / name)
    for name in ['forage', 'prompts', 'spec']:
        shutil.copytree(repository / name, source / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    wheels = tmp_path / 'wheels'; wheels.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'FORAGE_WORKSPACE', 'FORAGE_WORK_DIR', 'FORAGE_BOOKS_DIR'}}
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--wheel-dir', str(wheels), str(source)], check=True, capture_output=True, text=True, env=env)
    wheel = next(wheels.glob('forage-*.whl'))
    site = tmp_path / 'installed'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--target', str(site), str(wheel)], check=True, capture_output=True, text=True, env=env)
    outside = tmp_path / 'outside'; outside.mkdir()
    workspace = outside / 'workspace'
    script = r'''
import sys, json, io, os
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import forage
from forage import resources, graphic
from forage.artifacts import load_book
from forage.prompts import load_prompt
from forage.production import plan_production
from forage.production_state import atomic_json
from forage.source_fingerprint import source_fingerprint_for_stage
from forage.llm import LLMResponse, production_context, replay_cache_path
from PIL import Image
root = Path(sys.argv[2]); root.mkdir()
source = root / 'books' / 'tiny' / 'source.txt'; source.parent.mkdir(parents=True)
source.write_text('CHAPTER 1\n\nA tiny book for a zero-cost plan.\n')
assert Path(forage.__file__).is_relative_to(Path(sys.argv[1]))
assert 'Faithful' in resources.resource_path('spec/ABRIDGMENT_SPEC.md').read_text() or resources.resource_path('spec/ABRIDGMENT_SPEC.md').stat().st_size > 1000
assert load_prompt('draft_lean').config['model']
assert all(not item['missing'] for item in source_fingerprint_for_stage('draft')['files'])
assert (Path(forage.__file__).parent / 'webapp/static/app.js').is_file()
book = load_book('tiny', workspace=root, create=False)
result = plan_production(book)
assert result['execute'] is False and not book.work_dir.exists()
with production_context({}, book.work_dir.parent / '.replay_cache'):
    assert replay_cache_path('fixture').is_relative_to(root / 'work')
book.work_dir.mkdir(parents=True)
atomic_json(book.work_dir / 'plan.json', {'segments': [{'id': '001', 'title': 'Tiny', 'diegetic_status': 'diegetic', 'source_word_count': 10, 'target_word_count': 8}]})
(book.work_dir / 'segments').mkdir()
(book.work_dir / 'segments/001.md').write_text('A traveler crosses the old stone bridge and comes home.')
atomic_json(book.work_dir / 'segments/001.checks.json', {'status':'drafted'})
def storyboard(**kwargs):
    payload=json.loads(kwargs['prompt'][kwargs['prompt'].index('{'):])
    return LLMResponse(json.dumps({'frames':[{'id':u['id'],'image_prompt':'A traveler on a bridge.','caption':'He comes home.'} for u in payload['units']]}), 'mock', 0, 0, 0, 'stop')
def image(**kwargs):
    output=io.BytesIO(); Image.new('RGB', tuple(map(int, kwargs['size'].split('x'))), 'white').save(output, format='PNG'); return output.getvalue()
graphic.complete=storyboard; graphic.generate_image=image
result=graphic.generate_graphic(book, text_revision='a'*64, options={})
assert result['targets'] and any(i['path'].endswith('.pdf') for i in result['outputs'])
assert not (Path(forage.__file__).parent.parent / 'work').exists()
from typer.testing import CliRunner
from forage.cli import app
cli = CliRunner().invoke(app, ['run', 'tiny', '--workspace', str(root)])
assert cli.exit_code == 0, cli.output
from forage.publication import snapshot_revision
from forage.production_state import inventory
from forage.hosted_publication import HostedPublications
(book.work_dir / 'abridgment.txt').write_text('A traveler comes home.')
atomic_json(book.work_dir / 'alignments/001.json', {'draft_paragraphs':['A traveler comes home.']})
snapshot = snapshot_revision(book, text_revision='a'*64,
    outputs=inventory(book.work_dir, ['abridgment.txt','plan.json','alignments/001.json']),
    media_index={'version':1,'book_id':'tiny','text_revision':'a'*64,'targets':[]},
    stage_summary={'status':'complete','selected_outputs':['text'],
        'stages':{'assembly':{'status':'complete'},'alignment':{'status':'complete'}}})
host = root.parent / 'hosting'
for command in ['publish-review','publish-release']:
    invoked = CliRunner().invoke(app, [command,'tiny',snapshot['revision'],'--workspace',str(root),'--local-root',str(host)])
    assert invoked.exit_code == 0, invoked.output
    assert 'confirmed' in invoked.output
assert HostedPublications(host).status('tiny')['release']['revision'] == snapshot['revision']
atomic_json(host / 'tiny/feedback.json', {'version':1,'source_id':'installed-smoke','book_id':'tiny','complete':True,'comments':[]})
for command in ['review-pull','review-sync']:
    invoked = CliRunner().invoke(app, [command,'tiny','--workspace',str(root),'--local-root',str(host)])
    assert invoked.exit_code == 0, invoked.output
for command in ['publish-review','publish-release','review-pull','review-sync']:
    assert CliRunner().invoke(app,[command,'--help']).exit_code == 0
from forage import review_package
assert Path(review_package.__file__).is_relative_to(Path(sys.argv[1]))
assert not any(name.startswith('scripts') for name in sys.modules)
print(json.dumps({'package':forage.__file__, 'prompts':str(resources.resource_path('prompts/draft_lean.md')), 'graphic_targets':len(result['targets']), 'cli_plan':'passed','hosted_cli':'passed'}))
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(site), str(workspace)], cwd=outside, env=env, check=True, capture_output=True, text=True)
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    assert str(site) in proof['package'] and proof['graphic_targets'] == 1
    assert proof['hosted_cli'] == 'passed'
    for source_prompt in (repository / 'prompts').glob('*.md'):
        assert source_prompt.read_bytes() == (site / 'forage/_resources/prompts' / source_prompt.name).read_bytes()
    assert (repository / 'spec/ABRIDGMENT_SPEC.md').read_bytes() == (site / 'forage/_resources/spec/ABRIDGMENT_SPEC.md').read_bytes()
