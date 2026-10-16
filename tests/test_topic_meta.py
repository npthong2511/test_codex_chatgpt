import json
import unittest
from pathlib import Path
from agent17.runtime import Sources
from tools.build_topic_meta import TOPICS

ROOT=Path(__file__).resolve().parents[1]

class TopicMetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=Sources(ROOT/'data')
        cls.original=json.loads((ROOT/'data/kb_meta_tree_3.0.json').read_text())
        cls.old={}
        def walk(n):
            cls.old[n['id']]=n
            for c in n['children']:walk(c)
        walk(cls.original['tree'])
    def test_new_file_is_active(self):
        self.assertEqual(self.src.meta_filename,'kb_meta_tree_3.1.json')
    def test_every_case_has_seven_topics(self):
        cases=[n for n in self.src.nodes.values() if n['kind']=='case_group']
        self.assertEqual(len(cases),137)
        for n in cases:
            self.assertEqual({t['topic'] for t in n['topic_catalog']},set(TOPICS))
            self.assertEqual(n['common'],[])
    def test_original_structure_and_conditions_preserved(self):
        for nid,old in self.old.items():
            new=self.src.nodes[nid]
            self.assertEqual(new['entry_condition'],old['entry_condition'])
            self.assertEqual([c['id'] for c in new['children'] if c['kind']!='topic_content'],[c['id'] for c in old['children']])
    def test_no_dangling_references(self):
        for n in self.src.nodes.values():
            for key in ('related_node_ids','inherited_topic_ids'):
                for target in n.get(key,[]):self.assertIn(target,self.src.nodes,(n['id'],target))
            for ref in n.get('supporting_topics',[]):self.assertIn(ref['id'],self.src.nodes)
    def test_all_original_text_preserved_verbatim(self):
        spans={}
        for n in self.src.nodes.values():
            for b in n['common']:
                p=b.get('provenance',{})
                if p.get('kind')!='original_span':continue
                key=(p['node_id'],p['block_index']);spans.setdefault(key,{})[(p['start'],p['end'])]=b.get('original_text',b['text'])
                self.assertEqual(self.old[p['node_id']]['common'][p['block_index']]['text'][p['start']:p['end']].strip(),b.get('original_text',b['text']))
        for nid,n in self.old.items():
            for i,b in enumerate(n['common']):
                recovered=''.join(v for _,v in sorted(spans[(nid,i)].items()))
                self.assertEqual(''.join(recovered.split()),''.join(b['text'].split()))
    def test_topic_nodes_do_not_mix_unrelated_topics(self):
        for n in self.src.nodes.values():
            if n['kind']=='topic_content':
                self.assertTrue(all(n['topic'] in b['topics'] for b in n['common']))
    def test_identification_does_not_eagerly_load_all_topics(self):
        w=self.src.window('P08.C01')
        self.assertTrue(all('dieu_kien' in b['topics'] for b in w['node']['blocks']))
        for child in w['children']:
            if child['kind']=='topic_content':self.assertNotIn('blocks',child)
    def test_sibling_cases_are_not_inherited(self):
        w=self.src.window('P08.C01.TOPIC.ho_so')
        ids=[b['id'] for a in [w['node'],*w['ancestors']] for b in a.get('blocks',[])]
        self.assertFalse(any(x.startswith('P08.C02.') or x.startswith('P08.C03.') for x in ids))
    def test_web_supplements_have_quote_and_url(self):
        for n in self.src.nodes.values():
            for b in n['common']:
                p=b.get('provenance',{})
                if p.get('kind')=='web_supplement':
                    self.assertTrue(p['quote'].strip());self.assertTrue(p['source_url'].startswith('https://'))
                    self.assertTrue(b['source_refs'])

if __name__=='__main__':unittest.main()
