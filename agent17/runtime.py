"""V17: model decisions, bounded local source windows, no semantic validator."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import time
from .display import paginate, order_sections


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)
S={'type':'string'}
TOPIC={'type':'string','enum':['huong_dan','ho_so','chi_phi','noi_nop','thoi_gian','ket_qua','dieu_kien']}
SELECTED_TOPIC={'type':'string','enum':['','huong_dan','ho_so','chi_phi','noi_nop','thoi_gian','ket_qua','dieu_kien']}
def arr(item=S, **kw): return dict(type='array',items=item,**kw)
FACT=obj(dict(key=S,value=S,evidence=S,node_id=S))
STATE=obj(dict(facts=arr(FACT),path=arr(S),summary=S,pending_switch=S,
    stage={'type':'string','enum':['identify','choose_topic','topic']},
    selected_topic=SELECTED_TOPIC,available_topics=arr(TOPIC),pending_topics=arr(TOPIC),requested_topics=arr(TOPIC),pending_question=S,
    case_resolution=obj(dict(resolved={'type':'boolean'},case_id=S,missing_conditions=arr(S)))))
PANEL=obj(dict(title=S,sections=arr(obj(dict(kind={'type':'string','enum':['prepare','conditional','authority','quantity','notes','steps','content','gap']},title=S,items=arr(S)))),options=arr(obj(dict(id=S,label=S,node_ids=arr(S))))))
SCHEMA=obj(dict(action={'type':'string','enum':['load','open_topic','respond','restart']},
    mode={'type':'string','enum':['question','answer','switch_confirm','finish','data_gap']},
    node_ids=arr(S,maxItems=4),case_id=S,topic=SELECTED_TOPIC,state=STATE,speech_text=S,information=PANEL,citations=arr(S)))

from .dialogue_policy import PROMPT, ROUTE_PROMPT as PAGE_PROMPT, CONTENT_CONTRACTS
TOPIC_LABELS = {'huong_dan':'Các bước thực hiện','ho_so':'Hồ sơ','chi_phi':'Phí, lệ phí','noi_nop':'Nơi nộp hồ sơ','thoi_gian':'Thời hạn','ket_qua':'Kết quả','dieu_kien':'Điều kiện'}
PAGE_SCHEMA = obj(dict(intent={'type':'string','enum':['page','continue','unclear']},page={'type':'integer'},clarification=S))

class Sources:
    def __init__(self,directory):
        path=Path(directory)/'kb_meta_tree_3.2.json'
        if not path.exists():path=Path(directory)/'kb_meta_tree_3.1.json'
        if not path.exists():path=Path(directory)/'kb_meta_tree_3.0.json'
        raw=path.read_bytes();self.meta_filename=path.name
        self.topic_layer=path.name!='kb_meta_tree_3.0.json'
        self.hash=hashlib.sha256(raw).hexdigest();self.nodes={};self.parents={}
        def walk(n,parent=None):
            self.nodes[n['id']]=n;self.parents[n['id']]=parent
            for c in n['children']:walk(c,n['id'])
        walk(json.loads(raw)['tree'])
    def route_menu(self,nid):
        node=self.nodes.get(nid,{})
        if node.get('owner_id'):node=self.nodes[node['owner_id']]
        return dict(case_id=node.get('id',''),topics={k:dict(status=v['status'],source_ids=[r['id'] for r in v['sources']]) for k,v in node.get('topic_routes',{}).items()})
    def resolve_topic(self,nid,topic):
        node=self.nodes.get(nid)
        if not node or node['kind']=='topic_content':raise APIError('INVALID_CASE_ADDRESS')
        route=node.get('topic_routes',{}).get(topic)
        if route is None:raise APIError('INVALID_TOPIC')
        return deepcopy(route)
    def brief(self,n,blocks=True):
        structural=[c for c in n['children'] if c['kind']!='topic_content']
        d=dict(id=n['id'],title=n['title'],condition=n['entry_condition']['text'],kind=n['kind'],
               children_count=len(n.get('supporting_topics',[])) if n['kind']=='topic_content' else len(structural),related=n.get('related_node_ids',[]))
        if n.get('topic_catalog'):d['topic_catalog']=n['topic_catalog']
        if n['kind']!='topic_content' and n['id']!='ROOT':
            d['identification_contract']=dict(
                distinction_candidates=[dict(id=c['id'],condition=c['entry_condition']['text'],kind=c['kind'],same_condition_as_owner=c['entry_condition']['text'].strip()==n['entry_condition']['text'].strip()) for c in structural],
                completion='Model must resolve applicable case distinctions before topic menu; content/rule nodes are not automatically identity questions.')
        if n.get('topic'):
            d['content_contract']=dict(required_parts=CONTENT_CONTRACTS[n['topic']],coverage='not_certified_complete')
        for key in ('topic','owner_id','content_status','gap_note','supporting_topics'):
            if key in n:d[key]=n[key]
        if blocks:
            source=n
            if self.topic_layer and n['kind']!='topic_content':
                source=self.nodes.get(n['id']+'.TOPIC.dieu_kien',{'id':n['id'],'common':[]})
            d['blocks']=[dict(id=f"{source['id']}#{i}",text=b['text'],topics=b.get('topics',[]),
                              source_refs=b.get('source_refs',[]),review_status=b.get('review_status','inherited_not_revalidated'))
                         for i,b in enumerate(source['common'])]
        return d
    def window(self,nid):
        n=self.nodes[nid];anc=[];p=self.parents[nid]
        inherited=set(n.get('inherited_topic_ids',[]))
        while p and p!='ROOT':
            a=self.brief(self.nodes[p])
            if n.get('topic') and p!=n.get('owner_id'):
                a['topic_catalog']=[t for t in a.get('topic_catalog',[]) if t['topic']==n['topic']]
            a['rule_refs']=[self.brief(c,False) for c in self.nodes[p]['children'] if c['kind']=='conditional_rules']
            if n.get('topic'):
                inherited_id=p+'.TOPIC.'+n['topic']
                if inherited_id in inherited:
                    seen={b['id'] for b in a['blocks']}
                    a['blocks'].extend(b for b in self.brief(self.nodes[inherited_id])['blocks'] if b['id'] not in seen)
            anc.append(a);p=self.parents[p]
        if n['kind']=='topic_content':
            children=[]
            for ref in n.get('supporting_topics',[]):
                child=self.brief(self.nodes[ref['id']])
                child['reference_relationship']=ref['relationship']
                children.append(child)
        else:
            children=[self.brief(c, nid!='ROOT' and c['kind']!='topic_content') for c in n['children']]
        if nid=='ROOT':
            for child in children:child.pop('topic_catalog',None)
        return dict(node=self.brief(n),ancestors=list(reversed(anc)),
                    children=children,
                    child_selection=n.get('child_selection','all_applicable'))

class APIError(RuntimeError):pass
class Provider:
    def __init__(self,create,cfg):self.create=create;self.cfg=cfg;self.events=[];self.total_calls=0
    def call(self,payload, *, prompt=None, schema=None):
        if self.total_calls>=self.cfg['max_calls_per_run']:raise APIError('RUN_CALL_BUDGET')
        self.total_calls+=1;e={'call':self.total_calls,'payload':deepcopy(payload),'model':self.cfg['model']};self.events.append(e)
        active_schema=schema or SCHEMA
        if schema is None and payload.get('topic_context',{}):
            # One content-opening operation per turn: sources have already been delivered.
            # Further navigation uses explicit references, or the model responds/asks.
            active_schema=deepcopy(SCHEMA)
            active_schema['properties']['action']['enum']=['load','respond','restart']
        start=time.perf_counter()
        try:
            r=self.create(model=self.cfg['model'],store=False,
                input=[{'role':'system','content':prompt or PROMPT},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],
                reasoning={'effort':'none'},max_output_tokens=180 if schema is PAGE_SCHEMA else self.cfg['max_output_tokens'],
                text={'format':{'type':'json_schema','name':'citizen_v17','strict':True,'schema':active_schema}})
            e.update(status=r.status,usage=r.usage.model_dump() if r.usage else None,response_id=r.id)
            if r.status!='completed':raise APIError('INCOMPLETE_RESPONSE')
            try:result=json.loads(r.output_text)
            except json.JSONDecodeError:
                e['invalid_output_text']=r.output_text
                raise APIError('INVALID_JSON_RESPONSE') from None
            e['decision']=result;return result
        except APIError:raise
        except Exception as exc:
            code=getattr(exc,'code',None) or type(exc).__name__
            e['error']={'code':code,'status':getattr(exc,'status_code',None)}
            raise APIError(code) from None
        finally:e['seconds']=time.perf_counter()-start

def empty_state():return dict(facts=[],path=[],summary='',pending_switch='',stage='identify',selected_topic='',available_topics=[],pending_topics=[],requested_topics=[],pending_question='',case_resolution=dict(resolved=False,case_id='',missing_conditions=[]))
class Engine:
    def __init__(self,sources,provider,snapshot=None,session_id='console'):
        self.sources=sources;self.provider=provider;self.session_id=session_id
        self.nodes=['ROOT'];self.state=empty_state();self.last_response=None;self.revision=0;self.last_spoken='';self.pages=[];self.page_index=0
        if snapshot and snapshot.get('dialogue_version')=='17.5' and snapshot.get('meta_hash')==sources.hash and snapshot.get('session_id')==session_id:
            for key in ('nodes','state','last_response','revision','last_spoken'):setattr(self,key,deepcopy(snapshot[key]))
            self.pages=deepcopy(snapshot.get('pages',[]));self.page_index=snapshot.get('page_index',0)
    def snapshot(self):
        return dict(dialogue_version='17.5',meta_hash=self.sources.hash,session_id=self.session_id,**{k:deepcopy(getattr(self,k)) for k in ('nodes','state','last_response','revision','last_spoken','pages','page_index')})
    def process(self,text,cancelled=lambda:False):
        nodes=list(self.nodes);state=deepcopy(self.state);last=deepcopy(self.last_response);switch_request='';restart_used=False;navigation_error='';navigation_history=[];route_calls=0;repair_count=0;topic_context=None
        try:
            if self.pages:
                if cancelled():return None
                route_calls=1
                route=self.provider.call(dict(user_text=text,current=self.page_index+1,total=len(self.pages),context=dict(stage=self.state.get('stage'),pending_question=self.state.get('pending_question',''),selected_topic=self.state.get('selected_topic',''),last_question=self.last_response.get('speech_text',''),options=self.last_response.get('information',{}).get('options',[]))),
                                         prompt=PAGE_PROMPT,schema=PAGE_SCHEMA)
                if cancelled():return None
                if route['intent']=='unclear':
                    return self.clarify(route.get('clarification') or 'Anh/chị vui lòng nói lại yêu cầu; tôi đang giữ nội dung trên màn hình.')
                if route['intent']=='page':
                    self.page_index=max(0,min(len(self.pages)-1,route['page']-1))
                    self.revision+=1
                    return dict(mode='page',speech_text='',information=deepcopy(self.last_response['information']),
                                display_text=self.pages[self.page_index],display_only=True,
                                revision=self.revision,session_id=self.session_id)
            for step in range(self.provider.cfg['max_calls_per_turn']-route_calls):
                if cancelled():return None
                windows=[self.sources.window(n) for n in nodes]
                topic=state.get('selected_topic','')
                if topic and not self.sources.topic_layer:
                    for w in windows:
                        for item in [w['node'],*w['ancestors'],*w['children']]:
                            item['available_topics']=sorted({t for b in item.get('blocks',[]) for t in b.get('topics',[])})
                            item['blocks']=[b for b in item.get('blocks',[]) if not b.get('topics') or topic in b['topics'] or 'dieu_kien' in b['topics']]
                menus={w['node'].get('owner_id',w['node']['id']) for w in windows}
                case=state.get('case_resolution',{}).get('case_id')
                if case in self.sources.nodes:menus.add(case)
                p=dict(topic_routes=[self.sources.route_menu(n) for n in sorted(menus) if n!='ROOT'],topic_context=topic_context,user_text=switch_request if restart_used else text,state=state,last_response=last,windows=windows,loaded_topic=topic,topic_labels=TOPIC_LABELS,correction_anchors=[dict(id=n,title=self.sources.nodes[n]['title'],condition=self.sources.nodes[n]['entry_condition']['text']) for n in state.get('path',[]) if n in self.sources.nodes and self.sources.nodes[n]['kind']!='topic_content'],
                       display_context=dict(current=self.page_index+1,total=len(self.pages),at_last_page=self.page_index>=len(self.pages)-1),
                       confirmed_new_request=switch_request,restart_completed_this_turn=restart_used,navigation_history=navigation_history[-5:],navigation_error=navigation_error,calls_remaining=self.provider.cfg['max_calls_per_turn']-route_calls-step)
                r=self.provider.call(p)
                if cancelled():return None
                previous_state=state
                state=r['state'];navigation_error=''
                if r['action']=='restart':
                    if not (self.state.get('pending_switch') and self.last_response and self.last_response['mode'] in ('switch_confirm','question')):
                        state=previous_state;navigation_error='RESTART_REQUIRES_PREVIOUS_SWITCH_CONFIRM: respond switch_confirm first, preserve current scope.';continue
                    if restart_used:
                        navigation_error='RESTART_ALREADY_COMPLETED: load the new procedure using confirmed_new_request; do not restart again.';continue
                    restart_used=True;switch_request=self.state.get('pending_switch') or state['pending_switch']
                    nodes=['ROOT'];state=empty_state();last=None
                elif r['action']=='open_topic':
                    try:
                        case_id=r.get('case_id','');requested_topic=r.get('topic','')
                        scope=nodes[0].split('.')[0] if nodes[0]!='ROOT' else None
                        if scope is None or case_id.split('.')[0]!=scope:raise APIError('TOPIC_OUTSIDE_CURRENT_SCOPE')
                        route=self.sources.resolve_topic(case_id,requested_topic)
                    except APIError as exc:
                        state=previous_state;repair_count+=1
                        if repair_count>2:return self.navigation_failure(str(exc))
                        navigation_error=str(exc)+': use case_id and topic from topic_routes; do not invent node IDs.'
                        continue
                    if topic_context and topic_context['case_id']==case_id and topic_context['topic']==requested_topic and topic_context.get('delivery_state')=='loaded':
                        state=previous_state;repair_count+=1
                        if repair_count>2:return self.navigation_failure('TOPIC_ALREADY_LOADED')
                        navigation_error='TOPIC_ALREADY_LOADED: the requested source is already in windows. Respond from it, ask an applicable condition, or load an explicit supporting_topics reference. Do not open_topic again.'
                        continue
                    topic_context=dict(case_id=case_id,topic=requested_topic,delivery_state='loaded' if route['sources'] else 'no_source',**route)
                    requested=[v['id'] for v in route['sources']]
                    state['selected_topic']=requested_topic
                    nodes=requested or [case_id]
                    navigation_history.append(list(nodes))
                    if not requested:navigation_error='NO_CONFIRMED_SOURCE: this is a data gap, not a malformed address. Explain the gap; do not keep loading.'
                elif r['action']=='load':
                    requested=r['node_ids']
                    if not requested or len(requested)>4 or any(n not in self.sources.nodes for n in requested):
                        state=previous_state;repair_count+=1
                        if repair_count>2:return self.navigation_failure('INVALID_NODE_ADDRESS')
                        navigation_error='INVALID_NODE_ADDRESS: '+str(requested)+'. Choose an existing ID in windows, or use open_topic with topic_routes. No state was committed.'
                        continue
                    scope=nodes[0].split('.')[0] if nodes[0]!='ROOT' else None
                    requested_scopes={n.split('.')[0] for n in requested}
                    # A bounded supporting reference is not a change of procedure.
                    # Require the main scope in the same window set and an explicit source link.
                    linked=set()
                    for window in p['windows']:
                        for node in [window['node'], *window['children'], *window['ancestors']]:
                            linked.update(node.get('related',[]))
                            linked.update(v['id'] for v in node.get('topic_catalog',[]))
                    references_only=(scope is not None and scope in requested_scopes and all(
                        n.split('.')[0]==scope or (n in linked and self.sources.nodes[n]['kind']!='procedure') for n in requested))
                    if (len(requested_scopes)>1 or (scope and requested_scopes!={scope})) and not references_only:
                        # Address-scope protocol only. No interpretation or validation of user/legal content.
                        state=previous_state
                        navigation_error='LOAD_OUTSIDE_CURRENT_SCOPE: respond switch_confirm; restart only after citizen confirmation.'
                        continue
                    if requested in navigation_history:
                        navigation_error='REPEATED_WINDOW: sources are not accumulated. If both windows are needed, load their IDs TOGETHER (max 4), then answer or ask a missing citizen condition. Do not alternate windows.'
                    navigation_history.append(list(requested))
                    nodes=list(dict.fromkeys(requested))
                    if scope:nodes.sort(key=lambda n:n.split('.')[0]!=scope)
                else:
                    r['information']=order_sections(r['information'])
                    self.nodes=nodes;self.state=state;self.revision+=1
                    self.pages=paginate(r['information'],self.provider.cfg.get('display_columns',40),self.provider.cfg.get('display_rows',11))
                    self.page_index=0
                    result={**r,'revision':self.revision,'session_id':self.session_id,
                            'display_text':self.pages[0] if self.pages else ''}
                    self.last_response={k:deepcopy(result[k]) for k in ('mode','speech_text','information')}
                    return result
            if repair_count:return self.navigation_failure('NAVIGATION_CALL_BUDGET')
            raise APIError('TURN_CALL_BUDGET')
        except APIError as exc:
            return dict(mode='transport_error',speech_text='Kết nối xử lý chưa hoàn tất. Anh/chị vui lòng thử lại.',
                        information={'title':'Chưa hoàn tất xử lý','sections':[],'options':[]},code=str(exc),revision=self.revision,session_id=self.session_id)
    def navigation_failure(self,code):
        return dict(mode='navigation_error',code=code,speech_text='Tôi chưa mở được mục vừa yêu cầu. Anh/chị có thể chọn lại mục; thông tin trước đó vẫn được giữ.',
                    information=deepcopy((self.last_response or {}).get('information',{'title':'','sections':[],'options':[]})),
                    display_text=self.pages[self.page_index] if self.pages else '',preserve_display=True,
                    revision=self.revision,session_id=self.session_id)
    def clarify(self,speech):
        # Clarification is a model action; preserve the committed dialogue and cached pages.
        self.revision+=1
        return dict(mode='clarification',speech_text=speech,information=deepcopy((self.last_response or {}).get('information',{'title':'','sections':[],'options':[]})),
                    display_text=self.pages[self.page_index] if self.pages else '',preserve_display=True,
                    revision=self.revision,session_id=self.session_id)
    def acknowledge(self,revision,text):
        if revision==self.revision:self.last_spoken=text;return True
        return False
