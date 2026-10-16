"""Text-only V17 console. Does not call TTS or motion."""
import json,os
from pathlib import Path
from openai import OpenAI
from agent17 import Sources,Provider,Engine
base=Path(__file__).resolve().parent
cfg=json.loads((base/'config.json').read_text())
client=OpenAI(api_key=os.environ[cfg['key_variable']],timeout=cfg['timeout_seconds'],max_retries=0)
engine=Engine(Sources(base/'data'),Provider(client.responses.create,cfg))
try:
 while True:
  text=input('Người dân (exit để thoát): ').strip()
  if text.lower()=='exit':break
  result=engine.process(text)
  print('ÂM THANH:',result['speech_text'])
  print('MÀN HÌNH:',result.get('display_text', json.dumps(result['information'],ensure_ascii=False,indent=2)))
finally:client.close()
