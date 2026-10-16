"""Split output before any TTS job; information never enters the audio queue."""
from copy import deepcopy
import json
from pathlib import Path
import queue
import threading
from .runtime import Engine,Provider

class VoiceBridge:
    def __init__(self,kb,create,memory,model=None,enabled=True):
        if not enabled:raise RuntimeError('Live API disabled')
        self.memory=memory;self.lock=threading.RLock()
        cfg=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
        if model:cfg['model']=model
        self.engine=Engine(kb,Provider(create,cfg),getattr(memory,'dialogue_v17',None),memory.session_id)
    def persist(self):
        self.memory.dialogue_v17=self.engine.snapshot();self.memory.save()
    def generate(self,text,tts_queue,stop_event,abort_event,split_sentences,delivery_token,send_panel=None,turn_id=''):
        cancelled=lambda:stop_event.is_set() or (abort_event is not None and abort_event.is_set())
        with self.lock:
            response=self.engine.process(text,cancelled)
            if response is None or cancelled():return ''
            self.persist();delivery_token.update(revision=response['revision'],response=deepcopy(response))
            if send_panel:
                # Separate packet; TTS/motion failure cannot suppress the display send.
                packet=dict(type='information_panel',protocol_version=17,session_id=self.memory.session_id,
                            turn_id=str(turn_id),revision=response['revision'],action='replace',
                            mode=response['mode'],payload=response['information'])
                try:send_panel(packet);delivery_token['panel_sent']=True
                except Exception as exc:
                    delivery_token['panel_error']=type(exc).__name__
                    response['speech_text']='Chưa gửi được thông tin lên màn hình. Anh/chị vui lòng thử lại.'
        sentences,tail=split_sentences(response['speech_text'])
        if tail.strip():sentences.append(tail.strip())
        for job_id,sentence in enumerate(sentences,1):
            while not cancelled():
                try:tts_queue.put((job_id,sentence),timeout=.1);break
                except queue.Full:continue
            if cancelled():return ''
        return response['speech_text']
    def delivered(self,token,job):
        with self.lock:
            if self.engine.acknowledge(token.get('revision'),job.sentence_text):self.persist()

def acknowledge_playback(memory,token,job):
    bridge=getattr(memory,'_v17_bridge',None)
    if bridge is not None:bridge.delivered(token,job)
