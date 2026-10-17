"""Build Meta 3.2 from enriched 3.1. Routes are references, never copied legal text."""
import json,hashlib
from pathlib import Path
from copy import deepcopy
TOPICS=('huong_dan','ho_so','chi_phi','noi_nop','thoi_gian','ket_qua','dieu_kien')
def build(data):
    data=deepcopy(data);nodes={};parents={}
    def walk(n,parent=None):
        if n['id'] in nodes:raise ValueError('duplicate '+n['id'])
        nodes[n['id']]=n;parents[n['id']]=parent
        for child in n['children']:walk(child,n['id'])
    walk(data['tree'])
    for n in nodes.values():
        for t in n.get('topic_catalog',[]):
            if t['id'] not in nodes:raise ValueError('dangling catalog '+t['id'])
        for ref in n.get('supporting_topics',[]):
            if ref['id'] not in nodes:raise ValueError('dangling reference '+ref['id'])
    for nid,n in nodes.items():
        if n['kind']=='topic_content' or nid=='ROOT':continue
        chain=[];current=nid
        while current and current!='ROOT':chain.append(current);current=parents[current]
        routes={}
        for topic in TOPICS:
            anchors=[]
            for owner in chain:
                # Use the declared catalog, never synthesize a topic address.
                entry=next((t for t in nodes[owner].get('topic_catalog',[]) if t['topic']==topic),None)
                if not entry:continue
                source=nodes[entry['id']]
                if not (source['common'] or source.get('inherited_topic_ids') or source.get('supporting_topics')):continue
                anchors.append(dict(id=source['id'],owner_id=owner,
                    relationship='local' if owner==nid else 'ancestor_candidate',
                    condition=source['entry_condition']['text']))
                break
            routes[topic]=dict(status='local_source' if anchors and anchors[0]['relationship']=='local' and nodes[anchors[0]['id']]['common'] else 'conditional_sources' if anchors else 'unconfirmed',
                sources=anchors,applicability='Model must check source conditions; ancestor/sibling references are not automatically applicable.')
        n['topic_routes']=routes
    data['schema_version']='tree-meta/3.2-topic-routes';data['dataset_version']='3.2-for-17.5'
    data['routing_notes']='Every structural location has seven route entries. Unconfirmed is not an actionable source. Routing does not certify legal completeness.'
    return data
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];source=root/'data/kb_meta_tree_3.1.json';data=build(json.loads(source.read_text()));data['routing_input_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    (root/'data/kb_meta_tree_3.2.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
