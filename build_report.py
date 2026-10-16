from pathlib import Path
import json,statistics,html
base=Path(__file__).resolve().parent;reports=base/'reports'
def metrics(records):
 turns=[t for d in records for t in d['turns']];es=[e for d in records for e in d['events']]
 vals=lambda k:sum((e.get('usage') or {}).get(k,0) for e in es)
 return dict(dialogues=len(records),turns=len(turns),calls=len(es),api_errors=sum('error'in e or e.get('status')!='completed' for e in es),turn_errors=sum(t['response']['mode']=='transport_error' for t in turns),input_tokens=vals('input_tokens'),output_tokens=vals('output_tokens'),total_tokens=vals('input_tokens')+vals('output_tokens'),cached_input_tokens=sum(((e.get('usage') or {}).get('input_tokens_details') or {}).get('cached_tokens',0) for e in es),median_seconds=statistics.median(t['seconds'] for t in turns) if turns else 0,mean_tokens_per_turn=(vals('input_tokens')+vals('output_tokens'))/len(turns) if turns else 0,max_seconds=max((t['seconds'] for t in turns),default=0))
sets={name:[json.loads(p.read_text()) for p in sorted(reports.glob(pattern))] for name,pattern in [('pilot','pilot/D*/run.json'),('main','D*/run.json'),('regression1','regression1/*/run.json'),('regression','regression/*/run.json')]}
m={k:metrics(v) for k,v in sets.items()};m['all']=metrics(sum(sets.values(),[]));m['all']['recorded_runs']=m['all'].pop('dialogues');m['all']['unique_scenarios']=10;(reports/'metrics.json').write_text(json.dumps(m,indent=2))
es=[e for d in sets['main'] for e in d['events']]
audit={'max_windows_per_call':max(len(e['payload']['windows']) for e in es),'nested_children_leaked':sum('children' in n for e in es for w in e['payload']['windows'] for n in w['children']), 'answer_speech_not_template':[], 'questions_without_options':[], 'runtime_hashes':list({d['runtime_sha256'] for d in sets['main']})}
for d in sets['main']:
 for i,t in enumerate(d['turns'],1):
  r=t['response']
  if r['mode'] in ['answer','data_gap'] and r['speech_text']!='Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?':audit['answer_speech_not_template'].append([d['case'],i])
  if r['mode'] in ['question','switch_confirm'] and not r['information']['options']:audit['questions_without_options'].append([d['case'],i])
(reports/'structural_audit.json').write_text(json.dumps(audit,indent=2))
parts=['<!doctype html><html lang="vi"><meta charset="utf-8"><title>V17 — Hội thoại API</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 20px;color:#192537;background:#f5f7fb}article{background:white;border-radius:12px;padding:20px;margin:20px 0}.user{color:#154c91}.speech{background:#e6f3ec;padding:12px}.panel{border:1px solid #ccd7e3;padding:16px;border-radius:8px}small{color:#526174}h1,h2,h3{line-height:1.3}li{margin:6px 0}</style><h1>V17 — Kết quả hội thoại API thực tế</h1><p>Người dân mô phỏng thủ công; phản hồi trợ lý lấy nguyên từ API. Phần xanh là văn bản đưa vào TTS, khung trắng là nội dung gửi Unity. Không phải bản ghi âm hoặc ảnh Unity.</p>']
esc=lambda s:html.escape(str(s))
for group in ['main','regression1','regression']:
 if not sets[group]:continue
 parts.append('<h2>'+('Bộ 10 hội thoại chính' if group=='main' else ('Kiểm tra sửa lần 1' if group=='regression1' else 'Kiểm tra bản cuối'))+'</h2>')
 for d in sets[group]:
  parts.append('<article><h2>'+esc(d['case'])+'</h2>')
  for i,t in enumerate(d['turns'],1):
   r=t['response'];p=r['information'];events=d['events'][t['event_start']:t['event_start']+t['event_count']];tin=sum((e.get('usage')or{}).get('input_tokens',0)for e in events);tout=sum((e.get('usage')or{}).get('output_tokens',0)for e in events)
   parts.append(f'<h3>Lượt {i}</h3><p class="user"><b>Người dân:</b> {esc(t["user"])}</p><p class="speech"><b>Âm thanh:</b> {esc(r["speech_text"])}</p><div class="panel"><b>{esc(p["title"])}</b>')
   for sec in p['sections']:parts.append('<h4>'+esc(sec['title'])+'</h4><ul>'+''.join('<li>'+esc(x)+'</li>'for x in sec['items'])+'</ul>')
   if p['options']:parts.append('<ul>'+''.join('<li><b>'+esc(o['id'])+'.</b> '+esc(o['label'])+'</li>'for o in p['options'])+'</ul>')
   parts.append(f'</div><p><small>{esc(r["mode"])} · {t["event_count"]} API calls · {tin:,} input + {tout:,} output tokens · {t["seconds"]:.2f} giây</small></p>')
  parts.append('</article>')
parts.append('</html>');(reports/'Hoi_thoai.html').write_text('\n'.join(parts));print(json.dumps(m,indent=2));print(json.dumps(audit))
