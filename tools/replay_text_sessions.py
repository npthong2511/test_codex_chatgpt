"""Billable text-only controlled replay of stored session inputs, no STT/TTS/Unity."""
import argparse,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openai import OpenAI
from agent17.runtime import Sources,Provider,Engine
from agent17.transcription import has_transcript

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('sessions',nargs='+',type=Path);p.add_argument('--out',type=Path,default=Path('reports/new_run'));p.add_argument('--live',action='store_true',required=True);p.add_argument('--max-calls',type=int,default=130);args=p.parse_args()
 root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'config.json').read_text());cfg['max_calls_per_run']=args.max_calls;args.out.mkdir(parents=True,exist_ok=True)
 with OpenAI(api_key=os.environ[cfg['key_variable']],timeout=cfg['timeout_seconds'],max_retries=0) as client:
  for path in args.sessions:
   source=json.loads(path.read_text());provider=Provider(client.responses.create,cfg);engine=Engine(Sources(root/'data'),provider,session_id=path.stem);turns=[]
   for t in source['turns']:
    start=time.perf_counter();before=engine.snapshot();r=engine.process(t['text']) if has_transcript(t['text']) else {'mode':'no_speech_detected'}
    turns.append(dict(turn=t['turn'],text=t['text'],baseline=t['response'],response=r,before=before,after=engine.snapshot(),seconds=time.perf_counter()-start))
    (args.out/path.name).write_text(json.dumps(dict(method='Replay identical stored text; no new STT, TTS or Unity calls.',turns=turns,events=provider.events),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(path.stem,t['turn'],r.get('mode'),r.get('code',''),flush=True)
    if r.get('code') in ['insufficient_quota','RUN_CALL_BUDGET']:break
if __name__=='__main__':main()
