"""V2: display information using legacy Unity text packets; social speech stays audio-only."""
from copy import deepcopy
import json
from pathlib import Path
import queue
import threading
from .runtime import Engine,Provider

def format_information(information):
    """Plain text for the existing Unity UI; never include internal node IDs."""
    blocks = []
    title = information.get('title', '').strip()
    if title:
        blocks.append(title)
    for section in information.get('sections', []):
        lines = []
        heading = section.get('title', '').strip()
        if heading:
            lines.append(heading)
        lines.extend('- ' + item.strip() for item in section.get('items', []) if item.strip())
        if lines:
            blocks.append('\n'.join(lines))
    options = []
    for option in information.get('options', []):
        label = option.get('label', '').strip()
        if label:
            identifier = option.get('id', '').strip()
            options.append(f'{identifier}. {label}' if identifier else label)
    if options:
        blocks.append('\n'.join(options))
    return '\n\n'.join(blocks)

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
                display_text = format_information(response['information'])
                try:
                    # Old Unity clients understand these two message types.
                    # Clear first even if they append each subsequent speech_text.
                    send_panel({'type': 'speech_text_clear'})
                    if cancelled():
                        return ''
                    if display_text:
                        send_panel({'type': 'speech_text',
                                    'job_id': response['revision'],
                                    'text': display_text})
                    delivery_token['panel_sent'] = True
                    delivery_token['display_characters'] = len(display_text)
                    print(f"[UNITY TEXT] Sent revision={response['revision']} "
                          f"turn={turn_id} chars={len(display_text)}", flush=True)
                except Exception as exc:
                    delivery_token['panel_error'] = type(exc).__name__
                    print(f"[UNITY TEXT] Send failed: {type(exc).__name__}", flush=True)
                    response['speech_text'] = 'Chưa gửi được thông tin lên màn hình. Anh/chị vui lòng thử lại.'
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
