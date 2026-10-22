from pathlib import Path
import json
from datetime import datetime, timezone
R=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
responses=[read(p) for p in (R/'calls').rglob('response.json')]
active=[]
for p in (R/'calls').rglob('started.json'):
 if not (p.parent/'response.json').exists() and not (p.parent/'error.json').exists():
  v=read(p);active.append({'stage':v['stage'],'seconds':round((datetime.now(timezone.utc)-datetime.fromisoformat(v['at'])).total_seconds())})
books={}
for b in read(R/'run.json')['books']:
 w=R/'work'/b
 books[b]={key:len(list(w.glob(pattern))) for key,pattern in [('plans','preservation/???.json'),('first','two_pass/*/initial.md'),('second','two_pass/*/draft.md'),('review1','fidelity/initial_review/???.json'),('repair1','repairs/initial_review/???.md'),('review2','fidelity/repair_review/???.json'),('repair2','repairs/repair_review/???.md'),('final_review','fidelity/final_review/???.json'),('alignment','alignments/???.json'),('closure','repairs/blocking_closure/???.md'),('release_review','fidelity/release_review/???.json')]}
 for folder in sorted((w/'fidelity').glob('release_review*')):
  books[b][folder.name]=len(list(folder.glob('???.json')))
  books[b][folder.name+'_reused']=len(list(folder.glob('???.provenance.json')))
print(json.dumps({'completed_calls':len(responses),'recorded_cost':round(sum(v['cost_usd'] for v in responses),4),'books':books,'active':active},indent=2))
