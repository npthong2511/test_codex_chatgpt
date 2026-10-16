"""V3: queue social audio; publish legacy Unity information only when playback starts."""
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
            display_text = format_information(response['information'])
            speech = response['speech_text'].strip()
            if display_text and not speech:
                speech = ('Anh/chị vui lòng chọn nội dung trên màn hình.'
                          if response['mode'] in ('question', 'switch_confirm')
                          else 'Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?')
                delivery_token['speech_fallback'] = True
            delivery_token.update(pending_display=display_text, turn_id=str(turn_id),
                                  queued_speech=speech, panel_sent=False)
            # A silent finish has no playback to wait for; clear its old display now.
            if not speech:
                if send_panel and not cancelled():
                    publish_information_on_playback(delivery_token, send_panel)
                return ''
        # One short social utterance -> one WAV, one motion job, one display event.
        while not cancelled():
            try:
                tts_queue.put((1, speech), timeout=.1)
                delivery_token['tts_queued'] = True
                break
            except queue.Full:
                continue
        return '' if cancelled() else speech
    def delivered(self,token,job):
        with self.lock:
            if self.engine.acknowledge(token.get('revision'),job.sentence_text):self.persist()

def acknowledge_playback(memory,token,job):
    bridge=getattr(memory,'_v17_bridge',None)
    if bridge is not None:bridge.delivered(token,job)


def publish_information_on_playback(token, send_panel):
    """Called by the playback worker after sd.play succeeds, once per response.

    Sending failures must never stop audio that has already started.
    """
    if token.get('panel_sent'):
        return
    text = token.get('pending_display', '')
    try:
        send_panel({'type': 'speech_text_clear'})
        if text:
            send_panel({'type': 'speech_text', 'job_id': token['revision'], 'text': text})
        token['panel_sent'] = True
        token['display_characters'] = len(text)
        print(f"[UNITY TEXT] Sent at audio start revision={token.get('revision')} chars={len(text)}", flush=True)
    except Exception as exc:
        token['panel_error'] = type(exc).__name__
        print(f"[UNITY TEXT] Send failed during playback: {type(exc).__name__}", flush=True)
