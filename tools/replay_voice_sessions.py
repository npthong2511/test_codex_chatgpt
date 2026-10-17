"""Replay extracted session folders against live APIs. WAV files are not distributed.
Usage: python tools/replay_voice_sessions.py SESSION_DIR ... --live --out reports/new_run
Billable: STT for each WAV plus gpt-5.2 dialogue calls. Does not execute TTS/Unity.
"""
import argparse,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openai import OpenAI
from agent17.runtime import Sources,Provider,Engine
from agent17.transcription import transcribe_vi,has_transcript

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('sessions',nargs='+',type=Path)
 parser.add_argument('--live',action='store_true',required=True)
 parser.add_argument('--out',type=Path,default=Path('reports/new_run'))
 parser.add_argument('--max-calls',type=int,default=130,help='Dialogue calls per session, not including STT')
 args=parser.parse_args();root=Path(__file__).resolve().parents[1]
 cfg=json.loads((root/'config.json').read_text());cfg['max_calls_per_run']=args.max_calls
 args.out.mkdir(parents=True,exist_ok=True)
 with OpenAI(api_key=os.environ[cfg['key_variable']],timeout=cfg['timeout_seconds'],max_retries=0) as client:
  for session in args.sessions:
   provider=Provider(client.responses.create,cfg);engine=Engine(Sources(root/'data'),provider,session_id=session.name);turns=[]
   for turn in sorted((session/'turns').iterdir()):
    if not (turn/'transcripts/user_transcript.txt').exists():
     print('Skip incomplete recording without original transcript:',turn.name);continue
    start=time.perf_counter();stt=[];old=(turn/'transcripts/user_transcript.txt').read_text(encoding='utf-8')
    oldpath=turn/'transcripts/assistant_full_response.v17.json';original=json.loads(oldpath.read_text(encoding='utf-8')) if oldpath.exists() else {}
    before=engine.snapshot()
    try:
     text=transcribe_vi(client.audio.transcriptions.create,next((turn/'audio_in').glob('*.wav')),'gpt-4o-mini-transcribe',events=stt)
     result=engine.process(text) if has_transcript(text) else {'mode':'no_speech_detected'}
     turns.append(dict(turn=turn.name,original_text=old,text=text,stt=stt,original_response=original,response=result,before=before,after=engine.snapshot(),seconds=time.perf_counter()-start))
    except Exception as exc:
     turns.append(dict(turn=turn.name,error=type(exc).__name__,stt=stt));result={'code':'REPLAY_EXCEPTION'}
    (args.out/(session.name+'.json')).write_text(json.dumps(dict(turns=turns,events=provider.events),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(session.name,turn.name,result.get('mode'),result.get('code',''),flush=True)
    if result.get('code') in ('insufficient_quota','RUN_CALL_BUDGET','REPLAY_EXCEPTION'):break
if __name__=='__main__':main()
