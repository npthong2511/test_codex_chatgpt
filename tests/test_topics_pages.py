import json
import queue
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from agent17.display import paginate, format_information
from agent17.runtime import Engine, Sources, APIError, empty_state
from agent17.voice_bridge_v3 import VoiceBridge
import test_runtime as old

ROOT=Path(__file__).resolve().parents[1]

class Provider(old.Fake):
    def __init__(self, items, routes=()):
        super().__init__(items)
        self.routes=iter(routes)
        self.route_payloads=[]
    def call(self, payload, **kwargs):
        if kwargs:
            self.route_payloads.append(deepcopy(payload))
            return next(self.routes)
        return super().call(payload)


def long_response():
    r=old.response()
    r['information']['sections'][0]['items']=[f'Giấy tờ {i}: cần bản chính để đối chiếu và bản sao theo yêu cầu.' for i in range(15)]
    return r

class PagesTests(unittest.TestCase):
    def setUp(self):self.src=Sources(ROOT/'data')
    def test_bounds_and_no_lost_content(self):
        info=long_response()['information']
        pages=paginate(info)
        self.assertGreater(len(pages),2)
        for page in pages:
            self.assertLessEqual(len(page.splitlines()),11)
            self.assertTrue(all(len(line)<=40 for line in page.splitlines()))
        rendered=' '.join(' '.join(p.splitlines()[:-1]) for p in pages)
        self.assertEqual(' '.join(rendered.split()), ' '.join(format_information(info).split()))
    def test_configurable_size_unicode_long_word(self):
        info={'title':'A'*150,'sections':[],'options':[]}
        pages=paginate(info,24,5)
        self.assertTrue(all(len(x.splitlines())<=5 for x in pages))
        self.assertTrue(all(len(line)<=24 for x in pages for line in x.splitlines()))
    def test_forward_back_absolute_no_business_regeneration(self):
        p=Provider([long_response()],[{'intent':'page','page':2},{'intent':'page','page':1},{'intent':'page','page':999}])
        e=Engine(self.src,p);first=e.process('hồ sơ');original=deepcopy(e.pages)
        second=e.process('tiếp');back=e.process('mở lại 1/2');last=e.process('trang cuối')
        self.assertEqual(second['display_text'],original[1])
        self.assertEqual(back['display_text'],first['display_text'])
        self.assertEqual(last['display_text'],original[-1])
        self.assertEqual(len(p.payloads),1)
        self.assertTrue(second['display_only']);self.assertEqual(second['speech_text'],'')
        self.assertEqual(set(p.route_payloads[0]),{'user_text','current','total'})
    def test_bridge_page_direct_send_and_no_tts(self):
        p=Provider([long_response()],[{'intent':'page','page':2}])
        e=Engine(self.src,p);e.process('hồ sơ')
        class Memory:
            def save(self):pass
        b=object.__new__(VoiceBridge);b.memory=Memory();b.engine=e;b.lock=threading.RLock()
        q=queue.Queue();sent=[];token={}
        speech=b.generate('tiếp',q,threading.Event(),None,None,token,sent.append)
        self.assertEqual(speech,'');self.assertTrue(q.empty());self.assertTrue(token['display_only'])
        self.assertEqual([x['type'] for x in sent],['speech_text_clear','speech_text'])
        self.assertEqual(sent[-1]['text'],e.pages[1])
        self.assertNotIn('tts_queued',token)
    def test_snapshot_restores_pages(self):
        e=Engine(self.src,Provider([long_response()]));e.process('hồ sơ')
        other=Engine(self.src,Provider([], [{'intent':'page','page':2}]),e.snapshot())
        self.assertEqual(other.process('tiếp')['display_text'],e.pages[1])
    def test_old_snapshot_migrates(self):
        e=Engine(self.src,Provider([]));snap=e.snapshot();snap.pop('pages');snap.pop('page_index')
        self.assertEqual(Engine(self.src,Provider([]),snap).pages,[])
    def test_change_topic_replaces_pages(self):
        new=old.response();new['information']['title']='Phí';new['state'].update(stage='topic',selected_topic='chi_phi')
        e=Engine(self.src,Provider([long_response(),new],[{'intent':'continue','page':0}]))
        e.process('hồ sơ');r=e.process('cho xem phí')
        self.assertEqual(e.page_index,0);self.assertTrue(r['display_text'].startswith('Phí'))
        self.assertNotIn('Giấy tờ 14', ''.join(e.pages))
    def test_correction_or_switch_goes_to_business_model(self):
        for text in ['tiếp nhưng tôi nói nhầm cháu 8 tuổi','tôi muốn đổi sang khai sinh']:
            r=old.response();r['mode']='question'
            p=Provider([long_response(),r],[{'intent':'continue','page':0}]);e=Engine(self.src,p)
            e.process('hồ sơ');e.process(text)
            self.assertEqual(p.payloads[-1]['user_text'],text)
    def test_page_cancel_does_not_commit(self):
        p=Provider([long_response()]);e=Engine(self.src,p);e.process('hồ sơ');before=e.snapshot()
        self.assertIsNone(e.process('tiếp',lambda:True));self.assertEqual(before,e.snapshot())
    def test_route_error_preserves_cached_pages(self):
        p=Provider([long_response()]);e=Engine(self.src,p);e.process('hồ sơ');before=e.snapshot()
        def fail(*a,**k):raise APIError('offline')
        p.call=fail
        self.assertEqual(e.process('tiếp')['mode'],'transport_error');self.assertEqual(e.snapshot(),before)
    def test_topic_filter_keeps_conditions_and_topic_inventory(self):
        p=Provider([old.response()]);e=Engine(self.src,p);e.nodes=['P08'];e.state.update(stage='topic',selected_topic='chi_phi')
        e.process('phí')
        w=p.payloads[0]['windows'][0]
        for n in [w['node'],*w['children'],*w['ancestors']]:
            self.assertIn('available_topics',n)
            for b in n['blocks']:
                self.assertTrue(not b['topics'] or 'chi_phi' in b['topics'] or 'dieu_kien' in b['topics'])
    def test_finish_clears_cached_pages(self):
        r=old.response();r.update(mode='finish',speech_text='',information={'title':'','sections':[],'options':[]})
        e=Engine(self.src,Provider([long_response(),r],[{'intent':'continue','page':0}]))
        e.process('hồ sơ');e.process('xong');self.assertEqual(e.pages,[])

if __name__=='__main__':unittest.main()
