"""Report QA and byte manifest; does not repeat selector executions."""
from pathlib import Path
import json,hashlib,collections
P=Path(__file__).parent;ROOT=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
report=P/'mmfopd_projection_diagnosis.md';text=report.read_text(encoding='utf8')
text=text.replace('共12例；按冻结哈希顺序选取','共12个任务化样本，复用3名学生的早/晚快照（非12名独立学生）；按冻结哈希顺序选取')
text=text.replace('L14载入冻结选择器，L16替换为OULAD公共角色；`select` L29构造记录/先过敏感门，L35实际调用`alg.choose`。L50–51返回同一field=value接口及精确Token断言。','L13载入冻结选择器，L15替换为OULAD公共角色；`select` L26入口、L27构造记录/先过敏感门，L32实际调用`alg.choose`。L47–49执行预算断言、field=value序列化及精确Token校验并返回。')
text=text.replace('`embedding` L32','`embedding` L29–30').replace('`task_mask` L35','`task_mask` L31')
text=text.replace('`choose` L43：','`choose` L37入口、L39计算：').replace('L45把它用于utility','L41把它用于utility').replace('无P得分为s₀=.75u−.25*sensitivity+b，Full为s₁=s₀+.25p；u是L39–41的TF-IDF相对Attention，b是L47的Slot奖励','先定义a=.75u−.25*sensitivity；无P得分s₀=a+b，Full为s₁=a+b+.25p。u是L33–35的TF-IDF相对Attention，b是L43的Slot奖励')
text=text.replace('L48排序；L49–63用相同score做预算子集优化/贪心；L64–65返回字段。','L44排序；L45–61用相同score做预算子集优化/贪心；L62–63记录trace并返回字段。').replace('也执行L43的Pz计算，仅在L45禁用','也执行L39的Pz计算，仅在L41禁用')
text=text.replace('min(s₀[H])−max(s₀[L])>0','min(a[H])−max(a[L])>0')
traces=load('diagnostic_trace.json');slot_changed=sum(x['stage_trace']['Full']['pre_slot_rank']!=x['stage_trace']['Full']['post_slot_rank'] for x in traces)
assert all(x['stage_trace'][k]['without_slot']==x['stage_trace'][k]['post_bottleneck'] for x in traces for k in ['Full','no_projection'])
text=text.replace('TaskSlot：可能对两版本共同重排内部名次','TaskSlot：实际在'+str(slot_changed)+'/12例对两版本共同重排内部名次')
report.write_text(text,encoding='utf8')
# Validate that the quoted key lines contain the actual mechanisms.
old=ROOT/'experiments/oulad_dynamic_20261019_01';algo=(old/'frozen/aligned_selector.py').read_text(encoding='utf8').splitlines();engine=(old/'selection_engine.py').read_text(encoding='utf8').splitlines()
assert 'projected=' in algo[38] and 'utility=' in algo[40] and 'score=net+slot' in algo[42] and 'ordered=sorted' in algo[43] and 'return set' in algo[62]
assert 'spec=' in engine[12] and 'alg.ROLE_ALIASES=' in engine[14] and 'eligible=' in engine[26] and 'alg.choose' in engine[31] and 'tokenizer.encode' in engine[47]
assert len(text.split('| S'))==13
protocol=load('protocol.json');assert all(sha(ROOT/k)==v for k,v in protocol['source_sha256'].items());assert sha(P/'diagnose.py')==protocol['diagnostic_sha256']
summary=text.split('## 2026-10-20组会结论（300字内）')[1].strip();assert len(summary)<=300
(P/'qa.json').write_text(json.dumps({'status':'VERIFIED','sample_rows':12,'source_lines_verified':True,'source_and_prior_results_unchanged':True,'slot_reorders_both_variants_in_cases':slot_changed,'without_slot_both_keep_same_final_fields':True,'meeting_conclusion_characters':len(summary),'all_candidate_score_vectors_saved':12*13,'actual_selector_replays':24,'extra_replays_in_finalization':0},indent=2),encoding='utf8')
(P/'.gitattributes').write_text('* -text\n',encoding='utf8')
template=(old/'sync_public.py').read_text(encoding='utf8').replace('2026-10-19-oulad-dynamic-01','2026-10-19-mmfopd-projection-diagnosis-01').replace('Add OULAD forward-heldout MM-FOPD verification and component simplification evidence','Add tiny12-case projection score-path diagnosis without retraining')
(P/'sync_public.py').write_text(template,encoding='utf8')
files=[]
for file in sorted(P.iterdir()):
 if not file.is_file() or file.name in ['evidence_manifest.json','sync_receipt.json']:continue
 files.append({'path':file.name,'bytes':file.stat().st_size,'sha256':sha(file),'local_only':file.name.endswith('_LOCAL.json')})
(P/'evidence_manifest.json').write_text(json.dumps({'status':'TINY_DETERMINISTIC_DEVELOPMENT_DIAGNOSIS','classification':'mechanism diagnosis, not new empirical benchmark','privacy':'no student identifiers/values in public report or metadata scores; LOCAL mapping excluded','files':files},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'report':str(report),'sample_rows':12,'public_files':sum(not f['local_only'] for f in files),'excluded':sum(f['local_only'] for f in files),'source_lines_verified':True,'meeting_conclusion_characters':len(summary)},indent=2))
