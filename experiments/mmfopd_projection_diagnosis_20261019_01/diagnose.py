"""At most12 existing OULAD DEV cases; deterministic selector replay only."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from pathlib import Path
import sys,json,hashlib,importlib.util,itertools,collections,csv,ast
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1];OLD=ROOT/'experiments/oulad_dynamic_20261019_01'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
if (P/'diagnostic_trace.json').exists():raise RuntimeError('refuse overwrite')
inputs=[OLD/'selection_engine.py',OLD/'design.py',OLD/'frozen/aligned_selector.py',OLD/'dev_data/snapshots_LOCAL.json',OLD/'dev_results/cases_LOCAL.json',OLD/'dev_results/trace_templates.json',OLD/'evidence_manifest.json']+[ROOT/'protection/student_profile/src/fopd'/name for name in ['profile_selector.py','orthogonal_decoder.py','task_attention.py']]
before={str(x.relative_to(ROOT)).replace('\\','/'):sha(x) for x in inputs}
save('protocol.json',{'status':'FROZEN_TARGETED_READ_ONLY_DIAGNOSIS','source_sha256':before,'diagnostic_sha256':sha(Path(__file__)),'selection':'12 dev cases:3 intents x2 wordings x2 cutoffs(42/154), course alternates BBB/DDD/FFF; smallest frozen hash-ranked available student, independent of outcomes or release differences','scope':'no test data, downloads, fitting, parameter search, paid calls or source edits; only24 actual selector replays','additional':'read-only per-case score/subset arithmetic, not new method evaluation'})
sys.path[:0]=[str(OLD),str(ROOT)];spec=importlib.util.spec_from_file_location('projection_diagnosis_engine',OLD/'selection_engine.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e);d=e.d;alg=e.alg
from protection.common.schemas import ProfileRecord,Task
rows=[x for x in load(OLD/'dev_data/snapshots_LOCAL.json') if x['split']=='dev'];oldcases={(x['student'],x['cutoff'],x['intent'],x['wording'],x['method']):x for x in load(OLD/'dev_results/cases_LOCAL.json')};templates=load(OLD/'dev_results/trace_templates.json');records=[ProfileRecord(k,t,'oulad','metadata_only',1.,s,'') for k,(t,s,r,desc) in d.FIELDS.items()];ids=[r.record_id for r in records];traces=[];samples=[];private=[]
def ranking(score):return [ids[i] for i in sorted(range(len(ids)),key=lambda i:(-float(score[i]),ids[i]))]
for intent_no,intent in enumerate(d.INTENTS):
 for wording_no,wording in enumerate(['explicit','ambiguous']):
  for stage_no,cutoff in enumerate([42,154]):
   module=d.MODULES[(intent_no+wording_no+stage_no)%3];pool=[x for x in rows if x['cutoff']==cutoff and x['module']==module];row=min(pool,key=lambda x:hashlib.sha256(('oulad-rank-v1|'+str(x['student'])).encode()).hexdigest());sid=f'S{len(samples)+1:02d}';tc=e.Counter(row);runs={}
   for variant in ['Repaired-Full','Repaired-no-projection']:
    fields,trace,nt,_,wire=e.select(variant,row,intent,wording,tc,[]);old=oldcases[row['student'],cutoff,intent,wording,variant];assert fields==old['selected_fields'] and nt==old['actual_tokens'] and wire==old['payload'];runs[variant]={'fields':fields,'trace':trace,'tokens':nt,'wire':wire}
   full=runs['Repaired-Full'];no=runs['Repaired-no-projection'];ft=full['trace'];nt=no['trace'];task=Task('oulad','anonymous',f'Task purpose {intent}. '+d.question(intent,wording,cutoff),'oulad','development',False)
   # Actual one-hot geometry, not a student's numeric assessment vector.
   z=np.stack([alg.embedding(r) for r in records]);mask=alg.task_mask(task);projector=np.diag(mask);projected=z@projector;pnorm=np.linalg.norm(projected,axis=1);assert np.allclose(pnorm,ft['projection_values'])
   cosine,w,u=alg.attention_values(records,task,d.CFG['temperature']);base=.75*u-np.array([r.sensitivity for r in records])*.25;bonus=np.array([.08 if r.type=='mastery' and alg.mention(r.record_id,task.question) else 0. for r in records]);withp=base+.25*pnorm
   assert np.allclose(withp+bonus,np.array(ft['utility_before_cost'])-np.array(ft['privacy_cost'])+bonus);assert ranking(base)==nt['pre_slot_rank'];assert ranking(withp)==ft['pre_slot_rank'];assert ranking(base+bonus)==nt['rank'];assert ranking(withp+bonus)==ft['rank']
   H=pnorm>0;gap_pre=float(base[H].min()-base[~H].max());gap_post=float((base+bonus)[H].min()-(base+bonus)[~H].max());assert gap_pre>0 and gap_post>0
   stage={};subset_details={}
   for label,score,trace in [('no_projection',base+bonus,nt),('Full',withp+bonus,ft)]:
    order=ranking(score);order0=ranking(base if label=='no_projection' else withp);subset=[]
    for combo in itertools.combinations(range(len(ids)),3):
     names=[ids[i] for i in combo]
     if tc(names)>64:continue
     duplicate=sum(alg.role(records[i])==alg.role(records[j]) for i,j in itertools.combinations(combo,2));objective=float(score[list(combo)].sum()-.15*duplicate);subset.append((set(names),objective,int(pnorm[list(combo)].sum())))
    selected=set(trace['final_fields']);best=next(v for fields,v,c in subset if fields==selected);max_objective=max(v for _,v,_ in subset);assert abs(best-max_objective)<1e-10
    stage[label]={'pre_slot_rank':order0,'post_slot_rank':order,'pre_slot_Top3':order0[:3],'post_slot_Top3':order[:3],'post_bottleneck':sorted(selected),'no_bottleneck_greedy_Top3':sorted(order[:3]),'without_slot':None,'selected_objective':best,'optimal_objective':max_objective,'optimal_tie_count':sum(abs(v-best)<1e-12 for _,v,_ in subset),'selected_projected_role_count':sum(pnorm[ids.index(k)] for k in selected),'max_feasible_projected_role_count':max(c for _,_,c in subset)}
    assert selected==set(order[:3]);assert stage[label]['selected_projected_role_count']==stage[label]['max_feasible_projected_role_count']
    # Slot removal as exact subset arithmetic, not an extra algorithm run.
    s0=base if label=='no_projection' else withp;rank0=ranking(s0);bestkey=None;bestnames=None
    for combo in itertools.combinations(range(len(ids)),3):
     names=[ids[i] for i in combo]
     if tc(names)>64:continue
     dup=sum(alg.role(records[i])==alg.role(records[j]) for i,j in itertools.combinations(combo,2));value=float(s0[list(combo)].sum()-.15*dup);key=(value,tuple(-rank0.index(ids[i]) for i in sorted(combo,key=lambda i:rank0.index(ids[i]))))
     if bestkey is None or key>bestkey:bestkey=key;bestnames=sorted(names)
    stage[label]['without_slot']=bestnames
   fielddetail=[]
   for i,r in enumerate(records):fielddetail.append({'field':r.record_id,'role':alg.role(r),'original_vector':z[i].tolist(),'projected_vector':projected[i].tolist(),'vector_delta_L2':float(np.linalg.norm(z[i]-projected[i])),'projection_norm':float(pnorm[i]),'attention_cosine':float(cosine[i]),'attention_probability':float(w[i]),'attention_unit':float(u[i]),'privacy_cost':.25*r.sensitivity,'slot_bonus':float(bonus[i]),'no_projection_pre_slot_score':float(base[i]),'Full_pre_slot_score':float(withp[i]),'no_projection_final_score':float(base[i]+bonus[i]),'Full_final_score':float(withp[i]+bonus[i]),'projection_score_delta':float(.25*pnorm[i])})
   rankchanged=ft['rank']!=nt['rank'];prechanged=ft['pre_slot_rank']!=nt['pre_slot_rank'];topchanged=set(ft['rank'][:3])!=set(nt['rank'][:3]);finalchanged=full['fields']!=no['fields'];assert not(rankchanged or prechanged or topchanged or finalchanged);assert full['wire']==no['wire']
   residual=z-projected;ortherr=max(float(np.max(abs(projector@projector-projector))),float(np.max(abs(projector-projector.T))),float(np.max(abs(np.sum(projected*residual,axis=1)))))
   detail={'sample':sid,'intent':intent,'wording':wording,'cutoff':cutoff,'question':task.question,'coordinate_names':list(alg.ROLES),'task_mask':mask.tolist(),'field_trace':fielddetail,'stage_trace':stage,'matched_group_already_ahead_min_gap_pre_slot':gap_pre,'matched_group_already_ahead_min_gap_post_slot':gap_post,'geometric_error':ortherr,'hard_gate':{'threshold':.7,'input_candidates':13,'eligible':13,'removed_in_this_pool':0,'occurs_before_projection':True},'no_projection_still_computes_vector_then_disables_utility_term':True,'actual_original_replies_reproduced':True}
   traces.append(detail);samples.append({'sample':sid,'task':intent+'/'+wording,'day':cutoff,'vectors_changed':int(np.sum(np.linalg.norm(z-projected,axis=1)>1e-12)),'projection_boosted_fields':int(H.sum()),'pre_slot_rank_changed':prechanged,'final_rank_changed':rankchanged,'Top3_changed':topchanged,'bottleneck_hides_projection':False,'slot_hides_projection':False,'safety_hides_projection':False,'fields_no_projection':','.join(no['fields']),'fields_Full':','.join(full['fields']),'tokens_no_projection':no['tokens'],'tokens_Full':full['tokens'],'H_min_minus_L_max_pre':gap_pre})
   private.append({'sample':sid,'source_student':row['student'],'source_module':module,'source_cutoff':cutoff,'old_cases_key':[row['student'],cutoff,intent,wording],'payload_no_projection':no['wire'],'payload_Full':full['wire']})
save('diagnostic_trace.json',traces);save('sample_link_LOCAL.json',private)
with (P/'sample_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:writer=csv.DictWriter(f,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
assert len(samples)==12 and all(sha(ROOT/k)==v for k,v in before.items());save('completion.json',{'status':'COMPLETED_TINY_DETERMINISTIC_DIAGNOSIS','samples':12,'actual_selector_replays':24,'new_model_fits':0,'download_bytes':0,'paid_calls':0,'test_data_used':False,'all_source_files_unchanged':True,'all_replays_match_existing_dev_payloads_and_tokens':True,'all_full_candidate_rankings_unchanged':True,'all_Top3_and_final_fields_unchanged':True,'matched_group_pre_slot_gaps':[x['H_min_minus_L_max_pre'] for x in samples],'original_vectors_changed_min_max':[min(x['vectors_changed'] for x in samples),max(x['vectors_changed'] for x in samples)],'mathematical_projector_max_error':max(x['geometric_error'] for x in traces),'primary_cause':'B: already separated role groups receive a uniform reinforcing bonus; no candidate rank or Top3 change exists to be hidden downstream','secondary_cause':'E: binary role-norm bonus duplicates public metadata relevance; not a sensitive-attribute projection','not_established':'A statistical independence from sensitive attributes is not tested/proved','C_or_D_supported':False})
refs={}
for file in [OLD/'selection_engine.py',OLD/'frozen/aligned_selector.py',OLD/'design.py',ROOT/'protection/student_profile/src/fopd/orthogonal_decoder.py']:
 tree=ast.parse(file.read_text(encoding='utf8'));refs[str(file.relative_to(ROOT)).replace('\\','/')]={'sha256':sha(file),'functions':[{'name':n.name,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))]}
save('code_paths.json',refs)
def mdtable():
 out=['| 样本 | 任务/表述 | 天 | z→Pz变更字段/13 | 排名/Top3变化 | 最终字段（两者相同） | Token 无P→Full |','| --- | --- | --- | --- | --- | --- | --- |']
 for s in samples:out.append(f"| {s['sample']} | {s['task']} | {s['day']} | {s['vectors_changed']} | 否/否 | {s['fields_Full']} | {s['tokens_no_projection']}→{s['tokens_Full']} |")
 return '\n'.join(out)
gaps=[x['H_min_minus_L_max_pre'] for x in samples];text='''# MM-FOPD 极简正交投影诊断

**主因：B；补充机制解释：E。** 当前投影是二值任务角色加分，给Attention/成本原本已排在前面的字段统一+.25；12例从完整13字段排名开始就不变，Top3和实际payload也不变。没有证据归因于后续覆盖(C)或断线(D)。A所指的统计独立关系没有检验，不能仅凭未输入属性标签就断言成立。

只读取现有OULAD开发缓存：三任务×明确/模糊×42/154天，共12例；按冻结哈希顺序选取、课程轮换，不看成绩或结果挑样本。仅24次现有选择器确定性复算，均逐字匹配旧开发回复和Token；无下载、训练、测试集访问、参数搜索或生产/历史写入。精确身份和真实回复仅sample_link_LOCAL.json留本地。

## 真实路径、输入与公式

- `experiments/oulad_dynamic_20261019_01/selection_engine.py` L14载入冻结选择器，L16替换为OULAD公共角色；`select` L29构造记录/先过敏感门，L35实际调用`alg.choose`。L50–51返回同一field=value接口及精确Token断言。
- `.../frozen/aligned_selector.py`：`embedding` L32把字段ID映射为8维角色one-hot **z=e_role**；`task_mask` L35从问题的公共别名得到二值m。它们不输入学生数值、性别、残疾标签或敏感属性方向。
- `choose` L43：**P=diag(m)，Pz=z⊙m，p=||Pz||₂∈{0,1}**；L45把它用于utility。无P得分为s₀=.75u−.25*sensitivity+b，Full为s₁=s₀+.25p；u是L39–41的TF-IDF相对Attention，b是L47的Slot奖励(0或.08)。最终输出不是Pz，而是被选字段的原始值。
- L48排序；L49–63用相同score做预算子集优化/贪心；L64–65返回字段。投影项真实进入决策链，**没有输出变化不等于未接线**。no-projection也执行L43的Pz计算，仅在L45禁用其得分贡献，不能把它解释为省去了算子的耗时。
- 生产`protection/student_profile/src/fopd/orthogonal_decoder.py`的`decompose` L17、`project_to_task` L62是旧按位置向量/连续任务词权重实现；**Repaired-Full不走该旧路径**，不能用旧函数名替代本次真实路径。

以上为当前真实行号，SHA256/函数索引在code_paths.json；`...`均指同一OULAD实验目录。

## 逐样本对照（仅12行）

'''+mdtable()+f'''

每例13字段的z、Pz、向量差、Attention、成本、Slot奖励、投影前/后得分和完整排名均在diagnostic_trace.json，均为公共元数据计算值，无学生画像数值。p=1的字段向量不变；其余9–11个one-hot被置零、L2差为1。删除项时并非“原向量为空”，而是取消该二值norm奖励。

## 影响在哪消失：加分前已冗余

令H={{p=1}}，L={{p=0}}。12例在Slot之前均满足min(s₀[H])−max(s₀[L])>0，实际范围**{min(gaps):.6f}～{max(gaps):.6f}**。H已经整体领先；统一给H加.25不会改变组内排序，跨组只拉大间隔。加入Slot之后仍满足分离，Full/无P的完整13字段排名也完全相同。

子集优化另核对全部可行三字段组合：无P的赢家已取得最大可行H字段数。对任意替代集合T，F₁(S)−F₁(T)=[F₀(S)−F₀(T)]+.25[h(S)−h(T)]≥0；因此投影只加固原赢家。并非简单“系数太小”，不能据此建议放大系数或搜索权重。

- Bottleneck：两版本优化前Top3集合=各自优化后集合；角色重复惩罚改变目标值而没有吞掉投影造成的排名差（排名差根本不存在）。
- TaskSlot：可能对两版本共同重排内部名次，但投影的前Slot/后Slot排名都不变；精确取消Slot后的子集算术也保留相同字段，无覆盖证据。
- 硬安全门：发生在投影之前，13个输入候选全部<=.7且通过，实际三字段均满足Token64；该门不是本次投影影响消失的位置。

这些是12条代表性开发例的局部因果定位；与既有全开发记录一致，不据此证明任意任务下投影永远无作用。

## 正交关系到底成立什么

真实二值P满足Pᵀ=P、P²=P、⟨Pz,(I−P)z⟩=0，本次12掩码/全部候选的数值误差为0。这仅是保留坐标与删除坐标正交。不同字段同角色时向量相同，内积可为1；算法没有敏感属性投影器，也未验证“知识⊥策略⊥敏感”或统计独立、互信息消除。更不能用内部Pz变化证明外发隐私改善。

## 最多两个低成本处理候选（本轮均未实施）

1. **删除冗余投影加分，保留透明相关度成本排序与共同硬门。** 改变简化后的算法定义；本12例输出等价仅是回归证据，发布新版本仍应做独立冻结验证，不能把已看结果重新称盲测。本轮不改代码、不再实验。
2. **如保留现式，改名“任务角色奖励”，增加投影前后score/rank trace及冗余提示，撤回敏感正交解耦措辞。** 不改变数学定义或输出；只需低成本日志/等价回归，不需重训，但也不能因此宣称恢复了独立收益。

不建议本轮引入新投影算法、参数搜索或削弱Attention基线来制造差异。

## 2026-10-20组会结论（300字内）

复算12条OULAD开发样本后，投影向量确有变化，且投影项真实进入排序与子集选择。无效的关键发生在打分阶段：它把公共角色one-hot压成0/1奖励，给原本已领先的字段统一加分，完整排名从一开始就没变，后续规则没有覆盖投影差异。坐标投影满足几何正交，但未证明敏感属性解耦。建议删除冗余项，或准确改名并保留诊断日志；不放大系数追求优势。
'''
(P/'mmfopd_projection_diagnosis.md').write_text(text,encoding='utf8');print(json.dumps(load(P/'completion.json'),indent=2))
