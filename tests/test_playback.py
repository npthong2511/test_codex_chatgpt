import ast
import json
import queue
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent17.playback import play_response_audio
from agent17.voice_bridge_v3 import publish_information_on_playback
import test_runtime as legacy_tests
from test_runtime import response

ROOT = Path(__file__).resolve().parents[1]


def extract_function(path, name, namespace):
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    future = ast.parse('from __future__ import annotations').body[0]
    module = ast.Module(body=[future, fn], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace[name]


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.job = SimpleNamespace(job_id=1, wav_path=Path('social.wav'), sentence_text='Xin chào.')
        self.token = {'revision': 1, 'pending_display': 'Hồ sơ\n- Giấy tờ', 'panel_sent': False}
        self.events = []

    def publish(self, job):
        publish_information_on_playback(self.token, lambda p: self.events.append(p['type']))

    def audio(self, notify):
        self.events.append('sd.play')
        notify()
        self.events.append('sd.wait')

    def run_audio(self, motion=None, play_motion=None, play_audio=None, allow=True):
        return play_response_audio(self.job, motion, 'bad motion', allow,
            play_motion or self.audio, play_audio or self.audio,
            self.publish, lambda job: self.events.append('delivered'), self.token)

    def test_no_display_until_playback_then_same_event_for_motion(self):
        self.assertTrue(self.run_audio(motion=object()))
        self.assertEqual(self.events,['sd.play','speech_text_clear','speech_text','sd.wait','delivered'])
        self.assertTrue(self.token['audio_started']); self.assertTrue(self.token['audio_completed'])

    def test_motion_failure_uses_audio_only_and_publishes_at_start(self):
        self.assertTrue(self.run_audio())
        self.assertTrue(self.token['audio_only'])
        self.assertEqual(self.events[0:3],['sd.play','speech_text_clear','speech_text'])

    def test_failed_audio_device_never_displays_information(self):
        def bad_audio(notify):raise OSError('no output device')
        self.assertFalse(self.run_audio(play_audio=bad_audio))
        self.assertEqual(self.events,[]); self.assertFalse(self.token['panel_sent'])
        self.assertEqual(self.token['playback_error'],'OSError')

    def test_pre_audio_motion_validation_failure_falls_back(self):
        def invalid_motion(notify):raise ValueError('bad columns')
        self.assertTrue(self.run_audio(motion=object(),play_motion=invalid_motion))
        self.assertTrue(self.token['audio_only']); self.assertEqual(self.events.count('sd.play'),1)

    def test_error_after_audio_started_never_replays_speech(self):
        def broken_frames(notify):
            self.events.append('sd.play');notify();raise OSError('frame send failed')
        self.assertFalse(self.run_audio(motion=object(),play_motion=broken_frames))
        self.assertEqual(self.events.count('sd.play'),1)
        self.assertNotIn('delivered',self.events)

    def test_display_failure_does_not_stop_audio(self):
        def broken_sender(packet):raise OSError('offline')
        ok=play_response_audio(self.job,None,'motion fail',True,self.audio,self.audio,
            lambda job:publish_information_on_playback(self.token,broken_sender),None,self.token)
        self.assertTrue(ok); self.assertTrue(self.token['audio_completed'])
        self.assertEqual(self.token['panel_error'],'OSError');self.assertIn('sd.wait',self.events)

    def test_disabled_fallback_never_publishes_unplayed_content(self):
        self.assertFalse(self.run_audio(allow=False));self.assertEqual(self.events,[])

    def test_display_is_sent_only_once(self):
        self.run_audio();self.publish(self.job)
        self.assertEqual(self.events.count('speech_text'),1)

    def test_real_audio_only_function_calls_hook_after_successful_play(self):
        sd=SimpleNamespace(play=lambda *args:self.events.append('sd.play'),wait=lambda:self.events.append('sd.wait'))
        fn=extract_function(ROOT/'voice_motion_runtime_v17.py','play_wav_only',
            {'TAIL_PAD_MS':200,'load_wav_for_playback':lambda *args,**kwargs:([0],16000),'sd':sd})
        fn('file.wav',on_audio_started=lambda:self.events.append('hook'))
        self.assertEqual(self.events,['sd.play','hook','sd.wait'])

    def test_real_motion_function_calls_hook_before_first_frame(self):
        columns=['time_sec','roll','yaw','lip_open_dist_3d','mouth_width_dist_3d','upper_lip_thickness_3d','lower_lip_thickness_3d']
        class Frame:
            def __init__(self):self.columns=columns
            iloc=[dict.fromkeys(columns,0.0)]
            def __contains__(self,key):return key in columns
            def __len__(self):return 1
        cfg=SimpleNamespace(dt_min_ratio=.35,dt_max_ratio=2.2,progress_gain=.35,
            force_catchup_if_progress_error_gt=.04,idle_sleep_sec=.001,print_every_n_sent=20)
        sd=SimpleNamespace(play=lambda *args:self.events.append('sd.play'),wait=lambda:self.events.append('sd.wait'))
        fn=extract_function(ROOT/'motion_pipeline_utils_v3.py','send_prebuilt_motion_in_sync',
            {'Path':Path,'TAIL_PAD_MS':200,'get_wav_duration_sec':lambda p:.001,
             'load_wav_for_playback':lambda *a,**k:([0],16000),'sd':sd,'time':time,
             'np':SimpleNamespace(clip=lambda x,lo,hi:max(lo,min(hi,x)))})
        fn(Frame(),'file.wav',SimpleNamespace(send_face_data=lambda **kw:self.events.append('face')),cfg,
            on_audio_started=lambda:self.events.append('hook'))
        self.assertEqual(self.events,['sd.play','hook','face','sd.wait'])

    def test_social_sentences_are_one_audio_job_and_display_is_deferred(self):
        r=response();r['speech_text']='Thông tin ở trên màn hình. Anh/chị hỏi thêm gì không?'
        b=legacy_tests.LegacyDisplayTests().bridge([r]);q=queue.Queue();packets=[];token={}
        b.generate('a',q,threading.Event(),None,lambda s:([s],''),token,packets.append)
        self.assertEqual(q.qsize(),1);self.assertEqual(q.get()[1],r['speech_text'])
        self.assertEqual(packets,[]);self.assertFalse(token['panel_sent'])

    def test_empty_social_text_gets_audio_without_speaking_information(self):
        r=response();r['speech_text']=''
        b=legacy_tests.LegacyDisplayTests().bridge([r]);q=queue.Queue();packets=[];token={}
        b.generate('a',q,threading.Event(),None,lambda s:([],s),token,packets.append)
        self.assertTrue(token['speech_fallback']);self.assertEqual(packets,[])
        self.assertNotIn('GIAY_TO_KHONG_DOC',q.get()[1])

    def test_tts_error_is_recorded_and_no_playback_job_is_produced(self):
        token={};tq=queue.Queue();mq=queue.Queue();pq=queue.Queue()
        tq.put((1,'Xin chào'));tq.put(None)
        def broken_tts(*args):raise RuntimeError('TTS unavailable')
        fn=extract_function(ROOT/'voice_motion_runtime_v17.py','tts_worker_v2',
            {'queue':queue,'SENTINEL':None,'text_to_speech':broken_tts})
        fn(tq,mq,pq,threading.Event(),'test',Path('/tmp'),delivery_token=token)
        self.assertEqual(token['tts_error'],'RuntimeError');self.assertIsNone(pq.get());self.assertTrue(pq.empty())

    def test_actual_playback_worker_falls_back_and_invokes_display_hook(self):
        pq=queue.Queue();pq.put(self.job);pq.put(None);gate=threading.Event();gate.set()
        namespace={'queue':queue,'time':time,'SENTINEL':None,'play_response_audio':play_response_audio,
                   'play_wav_only':lambda path,on_audio_started:self.audio(on_audio_started)}
        fn=extract_function(ROOT/'voice_motion_runtime_v17.py','playback_unity_worker',namespace)
        fn(pq,threading.Event(),None,SimpleNamespace(play_audio_even_if_motion_failed=True,motion_wait_sleep_sec=.01),
           None,{}, {1:'motion build failed'},threading.Condition(),None,
           playback_start_event=gate,on_started=self.publish,
           on_delivered=lambda job:self.events.append('delivered'),delivery_token=self.token)
        self.assertEqual(self.events,['sd.play','speech_text_clear','speech_text','sd.wait','delivered'])
        self.assertEqual(pq.unfinished_tasks,0)

if __name__=='__main__':unittest.main()
