"""One adaptive citizen turn per scenario; persisted raw API evidence, no model judge."""
import json,os,time,sys,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from openai import OpenAI
from agent17.runtime import Sources,Provider,Engine
BASE=Path(__file__).resolve().parent

def run(case,text,report_root=None):
 cfg=json.loads((BASE/'config.json').read_text());directory=(report_root or BASE/'reports')/case;directory.mkdir(exist_ok=True)
 path=directory/'run.json';record=json.loads(path.read_text()) if path.exists() else {'case':case,'turns':[],'events':[]}
 cfg['max_calls_per_run']=200
 current_hash=hashlib.sha256((BASE/'agent17/runtime.py').read_bytes()).hexdigest()
 if record.get('runtime_sha256',current_hash)!=current_hash:raise RuntimeError('Runtime changed; use a fresh report directory')
 client=OpenAI(api_key=os.environ[cfg['key_variable']],timeout=cfg['timeout_seconds'],max_retries=0)
 p=Provider(client.responses.create,cfg);p.total_calls=len(record['events'])
 e=Engine(Sources(BASE/'data'),p,record.get('snapshot'),case)
 start=time.perf_counter();result=e.process(text);elapsed=time.perf_counter()-start
 record['turns'].append(dict(user=text,response=result,seconds=elapsed,event_start=len(record['events']),event_count=len(p.events)))
 record['events'].extend(p.events);record['snapshot']=e.snapshot()
 record['runtime_sha256']=hashlib.sha256((BASE/'agent17/runtime.py').read_bytes()).hexdigest()
 path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
 client.close()
 return {'case':case,'turn':len(record['turns']),'seconds':round(elapsed,2),'calls':len(p.events),'response':result}
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('replies');ap.add_argument('--output',default='reports/new_run');args=ap.parse_args()
 report_root=BASE/args.output;report_root.mkdir(parents=True,exist_ok=True)
 replies=json.loads(Path(args.replies).read_text())
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(run,k,v,report_root) for k,v in replies.items()]
  for f in as_completed(futures):print(json.dumps(f.result(),ensure_ascii=False),flush=True)
