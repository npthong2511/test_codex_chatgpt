"""Build V17.3 topic-layer data from preserved spans and reviewed supplements.

No runtime legal decisions. All condition paths are retained; references are not inheritance.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import hashlib
import json

TOPICS={'huong_dan':'Các bước thực hiện','ho_so':'Hồ sơ cần chuẩn bị','chi_phi':'Phí và chi phí',
        'noi_nop':'Nơi nộp hồ sơ','thoi_gian':'Thời hạn','ket_qua':'Kết quả và quyền lợi','dieu_kien':'Điều kiện và lưu ý'}

def build(original,assignments,supplements,corrections=()):
    correction_map={c["assignment_id"]:c for c in corrections}
    result=deepcopy(original);nodes={};parents={}
    def index(n,parent=None):
        nodes[n['id']]=n;parents[n['id']]=parent
        for c in n['children']:index(c,n['id'])
    index(result['tree']);old_ids=set(nodes);parts={k:{t:[] for t in TOPICS} for k in nodes};covered={}
    for unit in assignments:
        n=nodes[unit['node']];b=n['common'][unit['block']]
        text=b['text'][unit['start']:unit['end']]
        assert text==unit['text']
        assert unit['topics'] and set(unit['topics'])<=set(TOPICS)
        coverage_key=(unit['node'],unit['block']);covered.setdefault(coverage_key,[]).append((unit['start'],unit['end']))
        block=deepcopy(b);block['text']=text.strip();block['topics']=unit['topics']
        block['provenance']={'kind':'original_span','node_id':unit['node'],'block_index':unit['block'],
                             'start':unit['start'],'end':unit['end'],'assignment_id':unit['id']}
        block['review_status']='inherited_not_revalidated'
        if unit['id'] in correction_map:
            correction=correction_map[unit['id']]
            assert correction['old_text']==block['text']
            block['original_text']=block['text'];block['text']=correction['new_text']
            block['correction']=deepcopy(correction);block['review_status']='source_corrected_form_name'
        for topic in unit['topics']:parts[unit['node']][topic].append(deepcopy(block))
    for nid,n in nodes.items():
        for i,b in enumerate(n['common']):
            spans=sorted(covered.get((nid,i),[]));recovered=''.join(b['text'][a:z] for a,z in spans)
            assert ''.join(recovered.split())==''.join(b['text'].split()),(nid,i,'lost content')
    for item in supplements:
        assert item['target_node_id'] in nodes
        assert item['topic'] in TOPICS
        sid=item['source_id'];result['sources'][sid]=item['source']
        parts[item['target_node_id']][item['topic']].append(dict(text=item['text'],topics=[item['topic']],
            source_refs=[sid],provenance={'kind':'web_supplement','source_url':item['source']['urls'][0],
            'quote':item['source_quote'],'reviewed_at':'2026-10-16','applicability':item['applicability']},
            review_status='web_sourced_supplement'))
    topicsets={}
    def topics_below(n):
        own={t for t,v in parts[n['id']].items() if v}
        for c in n['children']:own.update(topics_below(c))
        if n['kind'] in ('case_group','procedure'):own.update(TOPICS)
        topicsets[n['id']]=own
        return own
    topics_below(result['tree'])
    def tid(nid,t):return nid+'.TOPIC.'+t
    def chain(nid):
        ancestors=[];p=parents[nid]
        while p and p!='ROOT':ancestors.append(p);p=parents[p]
        return ancestors
    for nid in sorted(old_ids):
        n=nodes[nid]
        if nid=='ROOT':continue
        original_children=list(n['children']);anc=chain(nid)
        rule_groups=[]
        for aid in [nid,*anc]:
            rule_groups.extend(c for c in nodes[aid]['children'] if c['kind']=='conditional_rules' and c['id']!=nid)
        n['common']=[];n['topic_catalog']=[]
        for topic in TOPICS:
            if topic not in topicsets[nid]:continue
            refs=[]
            for c in original_children:
                if topic in topicsets[c['id']]:refs.append(dict(id=tid(c['id'],topic),owner_id=c['id'],title=c['title'],
                    condition=c['entry_condition']['text'],relationship='conditional_child'))
            for rg in rule_groups:
                if topic in topicsets[rg['id']] and not any(r['owner_id']==rg['id'] for r in refs):
                    refs.append(dict(id=tid(rg['id'],topic),owner_id=rg['id'],title=rg['title'],
                                     condition=rg['entry_condition']['text'],relationship='conditional_rule'))
            # Explicit cross references keep the original semantics, never inherit sibling content.
            for related in n.get('related_node_ids',[]):
                if related in nodes and related not in anc and related!=nid and topic in topicsets[related]:
                    refs.append(dict(id=tid(related,topic),owner_id=related,title=nodes[related]['title'],
                        condition=nodes[related]['entry_condition']['text'],relationship='explicit_reference'))
            local=parts[nid][topic];inherited=[tid(a,topic) for a in reversed(anc) if parts[a][topic]]
            status='local_content' if local else 'inherited_content' if inherited else 'conditional_sources' if refs else 'unconfirmed'
            node=dict(id=tid(nid,topic),title=TOPICS[topic],kind='topic_content',topic=topic,owner_id=nid,
                      entry_condition=deepcopy(n['entry_condition']),common=local,children=[],child_selection='none',
                      content_status=status,inherited_topic_ids=inherited,supporting_topics=refs,
                      related_node_ids=list(dict.fromkeys([r['id'] for r in refs]+inherited)))
            if status=='unconfirmed':node['gap_note']='Chưa có dữ liệu xác nhận cho mục này trong phạm vi trường hợp; không được suy đoán hoặc mặc định không thu phí.'
            n['children'].append(node)
            n['topic_catalog'].append(dict(id=node['id'],topic=topic,title=node['title'],status=status))
    result.update(schema_version='tree-meta/3.1-topics',dataset_version='3.1-for-17.3',
                  parent_meta_sha256=hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    result['semantics'].update(topic_layer='Mỗi case_group có 7 topic_content. common chỉ nằm trong topic. Điều kiện nhánh cũ được giữ nguyên. supporting_topics là liên kết có điều kiện, KHÔNG phải kế thừa.',
        legal_currency='Nội dung gốc bảo toàn, không mặc định đã kiểm định lại. Bổ sung web có URL, trích dẫn, phạm vi. Xem báo cáo và unresolved gaps trước khi triển khai.')
    result['statistics'].update(original_nodes_preserved=len(old_ids),topic_nodes_added=sum(len(n.get('topic_catalog',[])) for n in nodes.values()),
        source_segments=len(assignments),supplement_placements=len(supplements),checks_scope='Bảo toàn đoạn nguồn và địa chỉ; không chứng nhận đầy đủ/hiệu lực pháp lý của toàn bộ dữ liệu.')
    all_nodes=[]
    def count(n):
        all_nodes.append(n)
        for child in n['children']:count(child)
    count(result['tree'])
    result['statistics'].update(tree_nodes=len(all_nodes),leaf_nodes=sum(not n['children'] for n in all_nodes),
        branch_nodes=sum(bool(n['children']) for n in all_nodes),reviewed_corrections=len(corrections),
        duplicate_source_spans='Intentional reuse across topics; original spans remain uniquely identified in provenance.')
    return result

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    original=json.loads((root/'data/kb_meta_tree_3.0.json').read_text())
    assignments=json.loads((root/'data/migration/topic_assignments.json').read_text())
    supplements=json.loads((root/'data/migration/reviewed_supplements.json').read_text())
    corrections=json.loads((root/'data/migration/reviewed_corrections.json').read_text())
    result=build(original,assignments,supplements,corrections)
    (root/'data/kb_meta_tree_3.1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['statistics'])
