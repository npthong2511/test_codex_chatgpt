"""Focused live regressions seeded from previously observed conversations."""
import json,os,time,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from openai import OpenAI
from agent17 import Sources,Provider,Engine
BASE=Path(__file__).resolve().parent
CASES={
 'D02_switch':{'from':'D02','turn':1,'messages':['Tôi muốn hỏi đăng ký khai sinh cho con thì sao?','Có, đổi sang khai sinh.']},
 'D09_correction':{'from':'D09','turn':5,'messages':['Tôi không thuộc diện miễn. Tôi chỉ cần biết giấy tờ thôi.']},
 'D06_fee':{'from':'D06','turn':3,'messages':['Vậy phí đăng ký bao nhiêu và bao lâu có kết quả?']}
}

def run(cid,c):
 cfg=json.loads((BASE/'config.json').read_text());src=Sources(BASE/'data');client=OpenAI(api_key=os.environ[cfg['key_variable']],timeout=90,max_retries=0);provider=Provider(client.responses.create,cfg)
 snapshot=None
 if 'from' in c:
  old=json.loads((BASE/'reports'/c['from']/'run.json').read_text());t=old['turns'][c['turn']-1];r=t['response'];event=old['events'][t['event_start']+t['event_count']-1]
  snapshot={'meta_hash':src.hash,'session_id':cid,'nodes':[w['node']['id'] for w in event['payload']['windows']], 'state':r['state'],'last_response':{k:r[k] for k in ('mode','speech_text','information')},'revision':r['revision'],'last_spoken':''}
 e=Engine(src,provider,snapshot,cid);record={'case':cid,'seed':c,'initial_snapshot':snapshot,'turns':[],'events':provider.events}
 out=BASE/'reports/regression'/cid;out.mkdir(parents=True,exist_ok=True)
 for msg in c['messages']:
  start=time.perf_counter();first=len(provider.events);r=e.process(msg)
  record['turns'].append({'user':msg,'response':r,'seconds':time.perf_counter()-start,'event_start':first,'event_count':len(provider.events)-first})
  record['snapshot']=e.snapshot();record['runtime_sha256']=hashlib.sha256((BASE/'agent17/runtime.py').read_bytes()).hexdigest()
  (out/'run.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
  print(json.dumps({'case':cid,'response':r},ensure_ascii=False),flush=True)
 client.close()
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(run,k,v) for k,v in CASES.items()]
  for f in as_completed(futures):f.result()
