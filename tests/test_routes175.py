import json,unittest
from pathlib import Path
from copy import deepcopy
from agent17.runtime import Engine,Sources
from test_runtime import Fake,response
ROOT=Path(__file__).resolve().parents[1]
CASE='P09.C07.N002.N002'
def opening(case,topic):
 r=response('open_topic');r.update(case_id=case,topic=topic);return r
class RoutingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.src=Sources(ROOT/'data')
 def test_all_structural_locations_have_seven_real_routes(self):
  count=0
  for nid,n in self.src.nodes.items():
   if nid=='ROOT' or n['kind']=='topic_content':continue
   count+=1;self.assertEqual(len(n['topic_routes']),7)
   for topic,route in n['topic_routes'].items():
    self.assertLessEqual(len(route['sources']),4)
    for ref in route['sources']:
     self.assertIn(ref['id'],self.src.nodes)
     self.assertEqual(self.src.nodes[ref['id']]['topic'],topic)
     self.assertEqual(ref['id'].split('.')[0],nid.split('.')[0])
  self.assertEqual(count,1620)
 def test_deep_case_missing_addresses_resolve_without_inventing_nodes(self):
  for topic in ['thoi_gian','noi_nop']:
   self.assertNotIn(CASE+'.TOPIC.'+topic,self.src.nodes)
   route=self.src.resolve_topic(CASE,topic)
   self.assertTrue(route['sources']);self.assertEqual(route['status'],'conditional_sources')
   f=Fake([opening(CASE,topic),response()]);e=Engine(self.src,f);e.nodes=[CASE]
   self.assertEqual(e.process(topic)['mode'],'answer')
   self.assertEqual(f.payloads[-1]['topic_context']['case_id'],CASE)
   self.assertEqual(f.payloads[-1]['windows'][0]['node']['id'],route['sources'][0]['id'])
 def test_bad_load_then_open_topic_recovers_same_turn(self):
  f=Fake([response('load',[CASE+'.TOPIC.noi_nop']),opening(CASE,'noi_nop'),response()]);e=Engine(self.src,f);e.nodes=[CASE]
  r=e.process('ở đâu');self.assertEqual(r['mode'],'answer')
  self.assertIn('INVALID_NODE_ADDRESS',f.payloads[1]['navigation_error']);self.assertEqual(f.payloads[1]['state']['facts'],[])
 def test_two_repairs_then_stop_preserves_everything(self):
  f=Fake([response('load',['INVALID']) for _ in range(3)]);e=Engine(self.src,f);e.nodes=[CASE];e.state['requested_topics']=['ho_so'];e.pages=['old page'];e.last_response={'mode':'answer','speech_text':'','information':{'title':'old','sections':[],'options':[]}}
  before=e.snapshot();r=e.process('nơi nộp');self.assertEqual(r['mode'],'navigation_error');self.assertEqual(r['display_text'],'old page');self.assertTrue(r['preserve_display']);self.assertEqual(before,e.snapshot());self.assertEqual(len(f.payloads),3)
 def test_cannot_open_another_procedure_without_confirmation(self):
  f=Fake([opening('P08.C01','ho_so') for _ in range(3)]);e=Engine(self.src,f);e.nodes=[CASE];r=e.process('hồ sơ');self.assertEqual(r['code'],'TOPIC_OUTSIDE_CURRENT_SCOPE');self.assertEqual(e.nodes,[CASE])
 def test_missing_source_is_not_invalid_address(self):
  src=deepcopy(self.src);src.nodes[CASE]['topic_routes']['noi_nop']={'status':'unconfirmed','sources':[],'applicability':'unknown'}
  final=response();final['mode']='data_gap';f=Fake([opening(CASE,'noi_nop'),final]);e=Engine(src,f);e.nodes=[CASE]
  self.assertEqual(e.process('nơi nộp')['mode'],'data_gap');self.assertIn('NO_CONFIRMED_SOURCE',f.payloads[-1]['navigation_error'])
 def test_enriched_input_content_not_changed_by_route_build(self):
  old=json.loads((ROOT/'data/kb_meta_tree_3.1.json').read_text())
  def walk(n):
   actual=self.src.nodes[n['id']]
   for key,value in n.items():
    if key!='children':self.assertEqual(actual[key],value)
   for c in n['children']:walk(c)
  walk(old['tree'])

 def test_repair_stops_with_remaining_call_budget_and_keeps_panel(self):
  f=Fake([response('load',['INVALID'])]);f.cfg={'max_calls_per_turn':1}
  e=Engine(self.src,f);e.nodes=[CASE];before=e.snapshot()
  self.assertEqual(e.process('nơi nộp')['code'],'NAVIGATION_CALL_BUDGET')
  self.assertEqual(e.snapshot(),before)

 def test_repeated_open_has_feedback_and_bounded_repair(self):
  f=Fake([opening(CASE,'thoi_gian') for _ in range(4)]);e=Engine(self.src,f);e.nodes=[CASE];before=e.snapshot()
  self.assertEqual(e.process('thời hạn')['code'],'TOPIC_ALREADY_LOADED')
  self.assertEqual(e.snapshot(),before)
  self.assertIn('TOPIC_ALREADY_LOADED',f.payloads[2]['navigation_error'])
 def test_explicit_pending_switch_can_use_question_mode(self):
  f=Fake([response('restart'),response()]);e=Engine(self.src,f);e.nodes=['P22'];e.state['pending_switch']='Căn cước';e.last_response={'mode':'question','speech_text':'Đổi không?','information':{}}
  e.process('Có');self.assertTrue(f.payloads[-1]['restart_completed_this_turn'])
  self.assertEqual(f.payloads[-1]['confirmed_new_request'],'Căn cước')

 def test_api_schema_disables_reopening_after_source_delivery(self):
  from types import SimpleNamespace
  from agent17.runtime import Provider,PAGE_SCHEMA
  calls=[]
  def create(**kw):
   calls.append(kw)
   return SimpleNamespace(status='completed',usage=None,id='mock',output_text='{}')
  p=Provider(create,dict(max_calls_per_run=3,model='mock',max_output_tokens=100))
  p.call({'topic_context':None})
  p.call({'topic_context':{'delivery_state':'loaded'}})
  p.call({'topic_context':{'delivery_state':'loaded'}},schema=PAGE_SCHEMA,prompt='route')
  self.assertIn('open_topic',calls[0]['text']['format']['schema']['properties']['action']['enum'])
  self.assertNotIn('open_topic',calls[1]['text']['format']['schema']['properties']['action']['enum'])
  self.assertIn('intent',calls[2]['text']['format']['schema']['properties'])
