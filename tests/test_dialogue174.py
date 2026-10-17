import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from copy import deepcopy
from agent17.runtime import Engine,Sources
from agent17.transcription import transcribe_vi
from test_runtime import Fake,response
from test_topics_pages import Provider,long_response
ROOT=Path(__file__).resolve().parents[1]

class DialogueTests(unittest.TestCase):
 def test_unclear_preserves_pages_question_facts_and_request(self):
  p=Provider([long_response()],[dict(intent='unclear',page=0,clarification='Anh/chị muốn xem tiếp hay chọn mục khác?')])
  e=Engine(Sources(ROOT/'data'),p);e.process('hồ sơ');e.state['requested_topics']=['ho_so'];e.state['pending_question']='Chọn tuổi';e.page_index=1
  before=e.snapshot();r=e.process('unintelligible input');after=e.snapshot()
  self.assertEqual(r['mode'],'clarification');self.assertTrue(r['preserve_display'])
  for key in ['pages','page_index','state','nodes','last_response']:self.assertEqual(before[key],after[key])
  self.assertEqual(len(p.payloads),1)
 def test_stt_sets_language_without_prompt_and_retries_once(self):
  with TemporaryDirectory() as td:
   p=Path(td)/'audio.wav';p.write_bytes(b'example');calls=[];responses=iter(['接下來','tiếp theo'])
   def create(**kwargs):calls.append({k:v for k,v in kwargs.items() if k!='file'});return SimpleNamespace(text=next(responses))
   events=[];self.assertEqual(transcribe_vi(create,p,'model',events=events),'tiếp theo')
   self.assertEqual(len(calls),2);self.assertEqual(calls[0]['language'],'vi');self.assertNotIn('prompt',calls[0])
 def test_stt_does_not_replace_unknown_latin_word(self):
  with TemporaryDirectory() as td:
   p=Path(td)/'audio.wav';p.write_bytes(b'example');events=[]
   self.assertEqual(transcribe_vi(lambda **kw:SimpleNamespace(text='DeepL'),p,'model',events=events),'DeepL');self.assertEqual(len(events),1)
 def test_contract_keeps_local_conditions_and_does_not_claim_complete(self):
  s=Sources(ROOT/'data');b=s.brief(s.nodes['P08.FIRST'])
  self.assertTrue(b['identification_contract']['distinction_candidates'])
  t=s.brief(s.nodes['P08.C01.TOPIC.ho_so'])
  self.assertEqual(t['content_contract']['coverage'],'not_certified_complete')
  self.assertIn('conditional_documents',t['content_contract']['required_parts'])

 def test_section_order_uses_model_roles_without_changing_content(self):
  from agent17.display import order_sections
  info={'title':'Hồ sơ','sections':[{'kind':'notes','title':'Lưu ý','items':['Không thu ảnh']},{'kind':'prepare','title':'Chuẩn bị','items':['Phiếu điện tử theo điều kiện']}],'options':[]}
  result=order_sections(info)
  self.assertEqual(result['sections'][0]['kind'],'prepare')
  self.assertEqual(info['sections'][0]['kind'],'notes')
  self.assertEqual(result['sections'][1],info['sections'][0])

 def test_foreign_transcript_is_not_silence_but_punctuation_is(self):
  from agent17.transcription import has_transcript
  self.assertTrue(has_transcript('接頭'))
  self.assertFalse(has_transcript('...'))
  self.assertFalse(has_transcript(''))

 def test_same_condition_content_children_are_explicit(self):
  src=Sources(ROOT/'data')
  candidates=src.brief(src.nodes['P22.C02'])['identification_contract']['distinction_candidates']
  self.assertTrue(candidates)
  self.assertTrue(all(c['same_condition_as_owner'] for c in candidates))
 def test_old_dialogue_protocol_snapshot_is_not_reused(self):
  e=Engine(Sources(ROOT/'data'),Fake([]));snap=e.snapshot();snap.pop('dialogue_version');snap['state']['summary']='obsolete'
  restored=Engine(e.sources,Fake([]),snap)
  self.assertEqual(restored.state['summary'],'')
