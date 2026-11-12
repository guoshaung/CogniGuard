"""T5 counts only from preserved raw outputs; full and conditional denominators."""
from common_adjusted import *
import csv,collections,math,shutil

def main():
 assert (O/'T5_evaluation/FINISHED.json').exists();d=O/'delivery_P3_P4';d.mkdir(exist_ok=False);sources=read(O/'T5_SOURCES.json');ss={x['id']:x for x in sources};rows=[read(p) for p in (O/'T5_evaluation/records').glob('*.json')];lookup={r['id']:r for r in rows};ins=read(O/'T5_insertion/INSERT_T5_all_RESULT.json')['rows'];idx={r['id']:r for r in ins};cov=[];success=set();planned=read(O/'data/T5_QUESTIONS.json')
 for x in planned:
  for m in ['CertInsert','RC']:
   ident='T5__'+x['id']+'__'+m;r=idx.get(ident,{});q=lookup.get(ident,{});ok=r.get('status')=='PREDICTED_TARGET_REACHED' and q.get('certificate') is True and q.get('anchor_invariant') is True and q.get('selection_invariant') is True
   if ok:success.add(ident)
   cov.append(dict(kind='coverage',id=ident,source_id=x['id'],dataset='T5',method=m,status=r.get('status','NOT_RUN_SOURCE_OR_PREPARATION_FAILURE'),watermarkable=ok,explanation_words=ss.get(x['id'],{}).get('explanation_words'),inserted_entries=r.get('inserted_entries'),seconds=r.get('seconds'),zero_insertion_positive=ok and r.get('inserted_entries')==0))
 for r in rows:r['conditional_eligible']=r['method']=='Fingerprint' or 'T5__'+r['source_id']+'__'+r['method'] in success
 fc=read(O/'delivery_P6/figure_counts.json');fc['meta'].update(run_id='EVAL03_ADJUSTED_P3_P4',actual_T5_sources=len(sources),planned_T5_sources=len(planned),T5_source_quality='FORMAT_ONLY_NOT_GOLD',paired_actual=None,superseded_pair_plan=60,P5_status='NOT_STARTED_OPTIONAL')
 def cnt(rr,key):return dict(k=sum(x.get(key) is True for x in rr),n=len(rr)) if rr else None
 def band(n):return '<100' if n<100 else '100-200' if n<=200 else '200-400' if n<=400 else '>400'
 fc['coverage_by_length_by_method']={'T5':{}}
 for m in ['CertInsert','RC']:
  rr=[r for r in cov if r['method']==m];fc['coverage']['T5'][m]=cnt(rr,'watermarkable');fc['coverage_by_length_by_method']['T5'][m]={b:cnt([r for r in rr if r['explanation_words'] is not None and band(r['explanation_words'])==b],'watermarkable') for b in ['<100','100-200','200-400','>400']}
 fc['coverage_by_length']['T5']=fc['coverage_by_length_by_method']['T5']['CertInsert']
 for m in ['CertInsert','RC','Fingerprint']:
  for a in ['none','ocr','crop_first100','crop_middle100']:fc['detection']['T5'][m][a]=cnt([r for r in rows if r['method']==m and r['attack']==a and r['conditional_eligible'] and isinstance(r.get('detected'),bool)],'detected')
 fc['T5_detection_missingness']={}
 for m in ['CertInsert','RC','Fingerprint']:
  fc['T5_detection_missingness'][m]={}
  parents=[r for r in rows if r['method']==m and r['attack']=='none' and r['conditional_eligible']]
  for a in ['none','ocr','crop_first100','crop_middle100']:
   rr=[r for r in rows if r['method']==m and r['attack']==a and r['conditional_eligible']]
   fc['T5_detection_missingness'][m][a]=dict(recorded=len(rr),scorable=sum(isinstance(r.get('detected'),bool) for r in rr),unknown_scores=sum(not isinstance(r.get('detected'),bool) for r in rr),missing_from_parent=len(parents)-len(rr),missing_interpretation='crop includes NOT_APPLICABLE short texts; OCR may include failed rendering/recognition; inspect raw OCR records')
 cc=[r for r in rows if r['method']=='CertInsert' and r['attack']=='none'];fc['certificate']['T5']=dict(restore_pass=cnt(cc,'certificate'),anchor_invariant_pass=cnt(cc,'anchor_invariant'))
 orig=[r for r in rows if r['method']=='Fingerprint' and r['attack']=='none' and r.get('p') is not None];fc['T5_unmarked_CertInsert_detector']=dict(k=sum(r['p']<.01 for r in orig),n=len(orig));fc['T5_zero_insertion_success']={m:cnt([r for r in cov if r['method']==m and r['watermarkable']],'zero_insertion_positive') for m in ['CertInsert','RC']}
 gen=read(O/'P3/RESULT.json');fc['T5_generation']=dict(planned=gen['planned'],attempted=gen['attempted'],completed=sum(r['status']=='COMPLETED' for r in gen['rows']),natural_eos=sum(r.get('stop_type')=='eos' for r in gen['rows']),token_limited=sum(r.get('stop_type')=='limit' for r in gen['rows']),failed=sum(r['status']=='FAILED' for r in gen['rows']))
 usage=[]
 for root in ['P3','T5_insertion']:
  f=O/root/'GPU_USAGE.jsonl'
  if f.exists():usage.extend(dict(x,component=root) for x in map(json.loads,f.read_text().splitlines()))
 fc['T5_resource_usage']=dict(GPU_residence_seconds=sum(x['seconds'] for x in usage),stages=usage,source_generation_tokens=sum(r.get('tokens',0) for r in gen['rows']),paid_API_calls=0,interpretation='Model residence wall time, not summed parallel request latency; excludes previously archived batches')
 put(d/'figure_counts.json',fc);allrows=cov+rows;fields=sorted({k for r in allrows for k in r})
 with (d/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in allrows)
 fmt=lambda v:'N/A' if v is None else f"{v['k']}/{v['n']}";text=['# P3：T5生成讲解与P4独立审核包','','冻结方法未改变。完整计划分母200；截断、失败和不可加水印不替换。','','|方法|可加水印/计划源|原样条件检出|OCR|前100词|中100词|','|---|---|---|---|---|---|']
 for m in ['CertInsert','RC','Fingerprint']:text.append('|'+m+'|'+fmt(fc['coverage']['T5'].get(m))+'|'+'|'.join(fmt(fc['detection']['T5'][m][a]) for a in ['none','ocr','crop_first100','crop_middle100'])+'|')
 text+=['','Fingerprint是来源Top-1，不是水印检测。水印条件检出分母仅成功嵌入且可计分输出，不能替代完整分母覆盖率。','各攻击缺失/不可计分数量单列于figure_counts.json的T5_detection_missingness；不将未返回或解析失败当成阴性，也不隐去其存在。','',f"生成状态：{json.dumps(fc['T5_generation'],ensure_ascii=False)}",f"未加水印T5原文在CertInsert检测器下的阳性：{fmt(fc['T5_unmarked_CertInsert_detector'])}。这与知识指纹Top-1字段不同。",f"零插入即达到目标的输出：{json.dumps(fc['T5_zero_insertion_success'])}，不应称为新嵌入信号。",'', '|讲解词数|CertInsert覆盖|RC覆盖|','|---|---|---|']
 for b in ['<100','100-200','200-400','>400']:text.append('|'+b+'|'+fmt(fc['coverage_by_length_by_method']['T5']['CertInsert'][b])+'|'+fmt(fc['coverage_by_length_by_method']['T5']['RC'][b])+'|')
 human=read(O/'P4/STATUS.json');text+=['',f"P4：{human['source_count']}个共同成功源，{human['versions']}个版本，已导出两名审核者的独立盲审页面。未收到评分，自然度/新增关系/知识错误均为null，一致性尚不能计算。",'', '知识检查是机械PROVISIONAL指标，不是独立人工金标；T5原文由Qwen根据题干生成，只作格式检查，没有静默修补。','本阶段P5可选基线尚未运行；历史26个中断范围槽另有归档，不冒充已完成配对基线。','逐个输出与OCR失败/不可计分状态见原始记录及per_item.csv。','', '决策：ANALYZE。结果不自动授权修改冻结方法或扩样。']
 (d/'RESULT.md').write_text('\n'.join(text),encoding='utf8');put(d/'P4_STATUS.json',human)
 # Independent cross-check from serialized CSV, not the in-memory count helper.
 parsed=list(csv.DictReader((d/'per_item.csv').open(encoding='utf-8-sig')));checks=[]
 for m in ['CertInsert','RC']:
  rr=[r for r in parsed if r['kind']=='coverage' and r['method']==m];actual={'k':sum(r['watermarkable']=='True' for r in rr),'n':len(rr)};assert actual==fc['coverage']['T5'][m];checks.append(dict(metric=m+'.coverage',actual=actual))
 for m in ['CertInsert','RC','Fingerprint']:
  for a in ['none','ocr','crop_first100','crop_middle100']:
   rr=[r for r in parsed if r['kind']=='evaluation' and r['method']==m and r['attack']==a and r['conditional_eligible']=='True' and r['detected'] in ['True','False']];actual={'k':sum(r['detected']=='True' for r in rr),'n':len(rr)} if rr else None;assert actual==fc['detection']['T5'][m][a];checks.append(dict(metric=m+'.'+a,actual=actual))
 put(d/'INDEPENDENT_VALIDATION.json',dict(PASS=True,checks=checks));print('P3REPORT',len(allrows))
if __name__=='__main__':main()
