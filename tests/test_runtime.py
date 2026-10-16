import unittest,json,queue,threading,socket
from pathlib import Path
from copy import deepcopy
from agent17.runtime import Sources,Engine,empty_state,APIError
from agent17.voice_bridge_v2 import VoiceBridge, format_information
from unity_tcp_sender_v7 import UnityTcpServer
ROOT=Path(__file__).resolve().parents[1]

def response(action='respond',nodes=None,state=None):
 return dict(action=action,node_ids=nodes or [],state=state or empty_state(),mode='answer',
 speech_text='Thông tin trên màn hình.',information={'title':'Hồ sơ','sections':[{'title':'Hồ sơ','items':['GIAY_TO_KHONG_DOC']}],'options':[]},citations=[])
class Fake:
 def __init__(self,items):self.items=iter(items);self.payloads=[];self.cfg={'max_calls_per_turn':9}
 def call(self,p):self.payloads.append(deepcopy(p));return next(self.items)
class Tests(unittest.TestCase):
 def setUp(self):self.src=Sources(ROOT/'data')
 def test_local_windows_no_grandchildren(self):
  for nid in self.src.nodes:
   w=self.src.window(nid)
   self.assertNotIn('children',w['node'])
   self.assertEqual([c['id'] for c in w['children']],[c['id'] for c in self.src.nodes[nid]['children']])
   self.assertTrue(all('children' not in c for c in w['children']))
 def test_load_replaces_window(self):
  f=Fake([response('load',['P08']),response('load',['P08.NEW'])])
  # Select an actual child rather than assuming a dataset address.
  child=self.src.nodes['P08']['children'][0]['id']
  f=Fake([response('load',['P08']),response('load',[child]),response()]);e=Engine(self.src,f)
  e.process('căn cước');self.assertEqual(e.nodes,[child])
  self.assertEqual([w['node']['id'] for w in f.payloads[-1]['windows']],[child])
 def test_restart_discards_old_facts(self):
  f=Fake([response('restart'),response()]);e=Engine(self.src,f)
  e.nodes=['P08'];e.state={'facts':[{'key':'age','value':'5','evidence':'5 tuổi','node_id':'P08'}],'path':['P08'],'summary':'old','pending_switch':'khai sinh'}
  e.last_response={'mode':'switch_confirm','speech_text':'Đổi không?','information':{}}
  e.process('đồng ý');p=f.payloads[-1]
  self.assertEqual(p['state']['facts'],[]);self.assertEqual(p['confirmed_new_request'],'khai sinh');self.assertEqual(p['windows'][0]['node']['id'],'ROOT')
 def test_cross_procedure_requires_confirmation(self):
  r=response();r['mode']='switch_confirm';r['state']['pending_switch']='khai sinh'
  f=Fake([response('load',['P01']),r]);e=Engine(self.src,f);e.nodes=['P08']
  out=e.process('khai sinh');self.assertEqual(out['mode'],'switch_confirm');self.assertEqual(e.nodes,['P08'])
  self.assertIn('LOAD_OUTSIDE',f.payloads[-1]['navigation_error'])
 def test_restart_without_prompt_cannot_reset(self):
  f=Fake([response('restart'),response()]);e=Engine(self.src,f);e.nodes=['P08']
  e.process('đổi');self.assertEqual(e.nodes,['P08']);self.assertIn('RESTART_REQUIRES',f.payloads[-1]['navigation_error'])
 def test_repeated_window_has_navigation_feedback(self):
  f=Fake([response('load',['P08']),response('load',['P08.FIRST']),response('load',['P08']),response()]);e=Engine(self.src,f)
  e.process('a');self.assertIn('REPEATED_WINDOW',f.payloads[-1]['navigation_error']);self.assertEqual(len(f.payloads[-1]['navigation_history']),3)
 def test_confirmed_restart_uses_new_request(self):
  f=Fake([response('restart'),response()]);e=Engine(self.src,f);e.nodes=['P08'];e.state['pending_switch']='khai sinh'
  e.last_response={'mode':'switch_confirm'};e.process('Có')
  self.assertEqual(f.payloads[-1]['user_text'],'khai sinh');self.assertTrue(f.payloads[-1]['restart_completed_this_turn'])
 def test_cancel_after_model_response_does_not_commit(self):
  cancelled=[False]
  class CancelProvider(Fake):
   def call(self,p):
    cancelled[0]=True;return response()
  e=Engine(self.src,CancelProvider([]));before=e.snapshot()
  self.assertIsNone(e.process('a',lambda:cancelled[0]));self.assertEqual(e.snapshot(),before)
 def test_explicit_supporting_reference_preserves_main_scope(self):
  f=Fake([response('load',['P25.M01','P24.N001']),response()]);e=Engine(self.src,f);e.nodes=['P24.N001']
  self.assertEqual(e.process('nộp thay')['mode'],'answer')
  self.assertEqual(e.nodes,['P24.N001','P25.M01'])
  self.assertEqual(f.payloads[-1]['navigation_error'],'')
 def test_cancel_no_commit(self):
  f=Fake([response()]);e=Engine(self.src,f);before=e.snapshot()
  self.assertIsNone(e.process('a',lambda:True));self.assertEqual(before,e.snapshot())
 def test_transport_failure_no_partial_state(self):
  f=Fake([response('load',['NO_SUCH_NODE'])]);e=Engine(self.src,f);before=e.snapshot()
  self.assertEqual(e.process('a')['mode'],'transport_error');self.assertEqual(before,e.snapshot())
 def test_snapshot_isolation_and_stale_ack(self):
  e=Engine(self.src,Fake([response()]),session_id='A');e.process('a');snap=e.snapshot()
  self.assertEqual(Engine(self.src,Fake([]),snap,'B').nodes,['ROOT'])
  self.assertFalse(e.acknowledge(0,'stale'));self.assertTrue(e.acknowledge(1,'played'))
 def test_split_tcp_tts(self):
  class Memory:
   session_id='a'
   def save(self):pass
  b=object.__new__(VoiceBridge);b.memory=Memory();b.lock=threading.RLock();b.engine=Engine(self.src,Fake([response()]),session_id='a')
  tcp=UnityTcpServer();tcp.conn,client=socket.socketpair();q=queue.Queue();token={}
  try:
   b.generate('a',q,threading.Event(),None,lambda s:([],s),token,tcp.send_message,'t1')
   stream=client.makefile('r', encoding='utf-8')
   self.assertEqual(json.loads(stream.readline()),{'type':'speech_text_clear'})
   packet=json.loads(stream.readline());stream.close()
   self.assertEqual(packet['type'],'speech_text');self.assertEqual(packet['job_id'],1)
   self.assertNotIn('Thông tin trên màn hình.',packet['text']);self.assertIn('GIAY_TO_KHONG_DOC',packet['text'])
   self.assertNotIn('GIAY_TO_KHONG_DOC',q.get()[1]);self.assertTrue(token['panel_sent'])
  finally:tcp.close();client.close()
 def test_departure_clears_panel(self):
  t=UnityTcpServer();t.conn,c=socket.socketpair()
  try:
   t.send_person_detection(True);c.recv(65536);t.send_person_detection(False)
   f=c.makefile();self.assertEqual(json.loads(f.readline())['type'],'speech_text_clear');f.close()
  finally:t.close();c.close()

class IntegrationTests(unittest.TestCase):
 def test_voice_main_wires_panel_sender_and_audio_only(self):
  import ast
  tree=ast.parse((ROOT/'voice_motion_runtime_v17.py').read_text())
  funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
  worker=funcs['response_generation_worker']
  self.assertIn('panel_sender',[a.arg for a in worker.args.args])
  calls=[n for n in ast.walk(worker) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='llm_stream_to_tts_queue']
  self.assertEqual(len(calls),1);self.assertIn('send_panel',[k.arg for k in calls[0].keywords])
  playback=funcs['playback_unity_worker']
  # No unconditional path can forward generated speech to the text channel.
  self.assertNotIn('send_speech_text(',ast.unparse(playback))
 def test_panel_failure_reports_audio_error(self):
  class Memory:
   session_id='a'
   def save(self):pass
  b=object.__new__(VoiceBridge);b.memory=Memory();b.lock=threading.RLock();b.engine=Engine(Sources(ROOT/'data'),Fake([response()]),session_id='a')
  def fail(packet):raise OSError('offline')
  q=queue.Queue();token={}
  b.generate('a',q,threading.Event(),None,lambda s:([],s),token,fail,'t1')
  self.assertEqual(token['panel_error'],'OSError');self.assertIn('Chưa gửi được',q.get()[1])

class LegacyDisplayTests(unittest.TestCase):
 def bridge(self, replies):
  class Memory:
   session_id='legacy-test'
   def save(self):pass
  b=object.__new__(VoiceBridge);b.memory=Memory();b.lock=threading.RLock()
  b.engine=Engine(Sources(ROOT/'data'),Fake(replies),session_id='legacy-test')
  return b
 def test_options_are_readable_without_internal_ids(self):
  info={'title':'Độ tuổi','sections':[], 'options':[
   {'id':'A','label':'Chưa đủ 6 tuổi','node_ids':['P08.C01']},
   {'id':'B','label':'Từ đủ 6 đến dưới 14 tuổi','node_ids':['P08.C02']}]}
  self.assertEqual(format_information(info),'Độ tuổi\n\nA. Chưa đủ 6 tuổi\nB. Từ đủ 6 đến dưới 14 tuổi')
 def test_legacy_client_replaces_content_across_turns(self):
  first=response();second=response();second['information']={'title':'Câu hỏi mới','sections':[], 'options':[{'id':'A','label':'Đồng ý','node_ids':[]}]}
  b=self.bridge([first,second]);packets=[];q=queue.Queue()
  for _ in range(2):b.generate('a',q,threading.Event(),None,lambda s:([],s),{},packets.append)
  screen=''
  for packet in packets:
   if packet['type']=='speech_text_clear':screen=''
   elif packet['type']=='speech_text':screen+=packet['text']
   else:self.fail('Unsupported message type')
  self.assertEqual(screen,'Câu hỏi mới\n\nA. Đồng ý')
  self.assertEqual([p['job_id'] for p in packets if p['type']=='speech_text'],[1,2])
  self.assertEqual(q.get()[1],first['speech_text']);self.assertEqual(q.get()[1],second['speech_text'])
 def test_finish_only_clears_display(self):
  r=response();r.update(mode='finish',speech_text='',information={'title':'','sections':[],'options':[]})
  b=self.bridge([r]);packets=[];q=queue.Queue()
  b.generate('xong',q,threading.Event(),None,lambda s:([],s),{},packets.append)
  self.assertEqual(packets,[{'type':'speech_text_clear'}]);self.assertTrue(q.empty())
 def test_cancelled_response_does_not_send_or_speak(self):
  b=self.bridge([response()]);packets=[];q=queue.Queue();stop=threading.Event();stop.set()
  b.generate('a',q,stop,None,lambda s:([],s),{},packets.append)
  self.assertEqual(packets,[]);self.assertTrue(q.empty())
 def test_main_disables_preset_text_and_marks_display_sent(self):
  import ast
  tree=ast.parse((ROOT/'voice_motion_runtime_v17.py').read_text())
  config=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='VoiceMotionRuntimeConfig')
  flags={n.target.id:n.value.value for n in config.body if isinstance(n,ast.AnnAssign) and isinstance(n.value,ast.Constant)}
  self.assertIs(flags['send_preset_speech_text_to_unity'],False)
  self.assertIs(flags['send_searching_text_to_unity'],False)
  callback=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='send_panel_to_unity')
  self.assertIn('response_text_sent_event.set()',ast.unparse(callback))

if __name__=='__main__':unittest.main()
