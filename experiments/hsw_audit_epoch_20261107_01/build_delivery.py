"""Snapshot reporting only after every included public parent is quality-locked.

Writes a new versioned delivery directory, never replaces an earlier report.
"""
import argparse,csv,datetime,difflib,json,math
from collections import Counter,defaultdict
from pathlib import Path
from bootstrap import E,R,save,digest
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args()
D=R/('analysis_'+a.round);V=R/('delivery_'+a.round);V.mkdir()
evalrec=json.loads((D/'EVALUATION_RECEIPT.json').read_text())
gallery=json.loads((D/'GALLERY_PUBLIC.json').read_text());actualids={g['issue_id'] for g in gallery if g['method']!='B0'}
tasks=json.loads((R/'TASKS_FROZEN.json').read_text());locks={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for row in json.loads(p.read_text()).get('rows',[]):locks[row['task_id']]=row
rows=[];cost=[]
for t in tasks:
 row={k:t.get(k) for k in ['task_id','source_id','source_split','stage','method','recipient_pseudonym','epoch','issue_id','source_sha256']}
 row.update(status='NOT_RUN',facts='NOT_RUN',coverage='NOT_RUN',overall_quality='NOT_RUN',reason='stage/resource pending at snapshot')
 p=R/'raw'/t['task_id']/'result.json'
 if t['task_id'] in actualids or (t['issue_id'] is None and p.exists()):
  d=json.loads(p.read_text());q=locks[t['task_id']];assert digest(p.parent/'public.txt')==q['public_sha256']
  row.update(status='COMPLETE' if d['natural_EOS'] else 'TECHNICAL_TRUNCATED',reason=d['finish_reason'],
   facts=q['facts'],coverage=q['coverage'],task_utility=q['task_utility'],overall_quality=q['overall'],
   EOS=d['natural_EOS'],A=d['A_bytes'],B=d['B_ids_equal'],all_logits_finite=d['raw_finite_all'],
   generated_tokens=d['generated_tokens'],public_tokens=len(d['public_ids']),wall_seconds=d['wall_seconds'],public_sha256=d['public_sha256'],
   evidence=json.dumps(q['evidence'],ensure_ascii=False))
  original=Path(t['source_path']).read_text(encoding='utf-8');text=(p.parent/'public.txt').read_text(encoding='utf-8')
  row['change_1minus_SequenceMatcher_no_autojunk']=1-difflib.SequenceMatcher(None,original,text,autojunk=False).ratio()
 rows.append(row)
def csvwrite(path,data):
 fields=list(dict.fromkeys(k for r in data for k in r))
 with path.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
csvwrite(V/'RESULTS.csv',rows)
sources=json.loads((R/'inputs/DATA_MANIFEST_FROZEN.json').read_text());csvwrite(V/'DATA_MANIFEST.csv',sources)
actual=[r for r in rows if r['status']!='NOT_RUN'];n=len(actual);eos=sum(r.get('EOS',False) for r in actual);qc=Counter(r['overall_quality'] for r in actual)
wmown=list(csv.DictReader((D/'OWN_KEY_DIAGNOSTICS.csv').open(encoding='utf-8-sig')))
status=list(csv.DictReader((D/'STATUS_SUMMARY.csv').open(encoding='utf-8-sig')))
life=json.loads((D/'REAL_TEXT_LIFECYCLE.json').read_text())
exact=[r for r in life if not r['parent_id'].startswith('B0_')]
older=[r for r in exact if r['expected_epoch']=='E1'];newer=[r for r in exact if r['expected_epoch']=='E2']
full=[r for r in status if r['role']=='DEV' and r['variant']=='FULL' and not r['rule'].startswith('PRIMARY')]
qchecks='\n'.join(f'- {r["task_id"]}: {r["overall_quality"]}; EOS={r.get("EOS")}; {r["status"]}。' for r in actual)
fptable='\n'.join(f'- {r["method"]} / {r["rule"]}: 正确{r["CORRECT"]}、错误{r["WRONG"]}、歧义{r["AMBIGUOUS"]}、拒识{r["REJECT"]} / {r["denominator_queries"]}。' for r in full)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
save(V/'README.md',f'''# HSW-AUDIT-EPOCH-01：可恢复检查点 {a.round}

快照UTC：{now}。本目录不是整个有限发行矩阵完成证明。保持7B，用户选择等待资源；不启动3B回退，不降低6.5GiB准入线，不重跑已经STARTED的失败槽。

工程：PARTIAL。研究：INSUFFICIENT_EVIDENCE。真实生成{n}/{len(tasks)}个计划槽，{eos}自然EOS；其余情况见RESULTS.csv。本地旧结果、首轮公开评分、源码冻结和失败均保留。

入口：code/为独立实验源码，data/为冻结输入、真实Token/正文、质量锁和逐候选公开分数。先读FINAL_DECISION.md、REPRODUCE.md和LICENSES.md。私密密钥、采样seed、DPAPI文件、模型和环境不发布。
''')
save(V/'FINAL_DECISION.md',f'''# 决策与未完成边界

工程：PARTIAL；研究：INSUFFICIENT_EVIDENCE；当前行动：保持7B，按账本继续从未启动的槽位，资源不足时等待，不用3B替代。没有宣称整个任务COMPLETE或新算法GAP_OBSERVED。

真实生成{n}/{len(tasks)}个基础计划槽，{eos}自然EOS；质量作者PROVISIONAL：{dict(qc)}。只覆盖{evalrec['independent_positive_source_chapters']}个已生成正样本章节，CAL2章节，预留TEST实际生成{evalrec['TEST_chapters_generated']}章节。接收方/周期/裁剪并非独立文档。

A. 仅给公开文本并保留可信发行版本库，可用精确哈希/指纹恢复部分具体交付版本；相同B0正文的多个登记必须AMBIGUOUS。此结果不是新接收人身份恢复、法律归责或篡改认证。
B. 在模拟时钟150，旧E1的{len(older)}份实际文本、新E2的{len(newer)}份实际文本均保留原版本；许可撤销独立输出。真实可信时间戳、密钥泄露后的抗伪造、生产PKI均未证明。
C. 所有方法检索相同已发行版本；完整原样正文的精确匹配优势不稀奇。逐密钥Greenlist与真实32bit MPAC公开解码分别报告；不能把优化后的MPAC颜色统计阳性当完整发行码成功，也不把32bit失败推广至更短payload或PRMB/DMW。
D. 知识、改动、长度、速度逐例保存。一个方法出现遗漏不构成普遍因果结论。语义强攻击未完成，不能声称强改写鲁棒性。
E. 现有登记、轮换、历史保留能力有工程集成价值；没有足够独立评价证明新的机制缺口或方法优势。不得据此开发新算法。

全局1%错误接受目标未认证。CAL仅2章，冻结秩3超过2，主统计阈值为∞而拒识；这不算防御成功。有限CAL最大值、原始排名及名义Bonferroni仅诊断；未知独立测试FPR分母0。
''')
save(V/'RESULT.md',f'''# 实际结果快照 {a.round}

真实生成{n}次，{eos}次自然EOS；质量{dict(qc)}，其余{len(tasks)-n}个计划槽位在本快照NOT_RUN。模型为原有Qwen2.5-7B Q4_K_M CPU，不是云端FP32；付费API/GPU均0。

## 全部已观察输出
{qchecks}

## 相同完整发行版本索引下的公开全文结果
以下DEV FULL表包含实际改写与B0完全相同原文副本；不是独立文档检出率，有限阈值均未认证FPR。
{fptable}

完整逐查询、逐候选、裁剪结果分别见ATTRIBUTION_RESULTS.csv、RAW_RANKS.csv、WM_SCORES.jsonl、FP_SCORES.csv。B0重复正文的不同接收方/周期不强选第一名。私有历史只在评分结束后作实现对齐诊断，不替代公开分数。

知识审阅人为当前助手，方法标签从后续审核卡移除，但作者可能记得执行，不称独立真人盲审。全部FAIL/UNKNOWN引句见ERROR_CASES.md。旧判定不重写。
''')
errors=[]
for r in actual:
 if r['overall_quality']!='PASS':errors.append(f'## {r["task_id"]}\n状态：{r["overall_quality"]} / {r["status"]}\n'+r['evidence'])
save(V/'ERROR_CASES.md','''# 全部失败、歧义及技术中断

覆盖遗漏与事实错误分开；内存保护截断不是自动认定的知识错误。

'''+ '\n\n'.join(errors)+'''

另有指纹评分首次词频构造NameError，原脚本与日志保存；修复后完成，不涉及真实生成重试。
生命周期v1漏检未来发行时钟与泄露周期新发行、早于发行的许可事件；新离线StrictRegister已补守卫，v1及原18项测试保留。本轮实际记录均issued_at<=150，因此当前实际关联结果未改。此修复不是水印算法。
''')
save(V/'REPRODUCE.md','''# 复现与保密边界

真实运行依赖现有7B两分片GGUF、冻结HF tokenizer、llama.cpp b12110原生DLL和旧原生日志桥；SHA见MODEL_IDENTITY.json/ENGINE_READONLY_REUSE.json。不得把本分支当成官方HF generate原样复现。新机器须显式配置只读资产路径、重新冻结新实验，不能编辑旧冻结后称同一试验。

生成代码最终首个forward之前冻结在GENERATION_CODE_FREEZE.json；freeze.json保留更早准备版源码SHA，之后的事前兼容补丁有单独冻结，不能声称freeze.json所有早期源码字段都仍为现值。输入和任务SHA保持原样。

受控本机续跑：先核对STATE、RUN_MANIFEST、资源和open_stages，不重复已有任务；确认>=6.5GiB空闲、无自有重复进程后执行 `python -B experiments/hsw_audit_epoch_20261107_01/run_generation.py --phase s2`。S2双来源准入锁之前不得执行s3；禁止重跑63Token内存截断槽。实际密钥及生成seed由同一Windows账户DPAPI读取，未发布。

公开可复算：签名记录、正文SHA、MinHash1617配对在首轮可无秘密检查，执行 `python -B code/public_archive_check.py <本发布目录>`；后续轮相同接口，具体数量以该轮输出为准。MiniLM须相同既有英文checkpoint，权重不在发布物中。

水印实际公开分数完全复算需要受控取得历史检测密钥，仅有hash不足以复算。PUBLIC_METHOD_FIXTURE.json给出明确无安全用途的测试key=1234567和未加水印作者句子，演示两个官方检测接口；它不是真实有效水印样本。可运行public_method_fixture.py，指定本地Tokenizer及固定TextSeal源码路径，并核对输出。采样seed与实际私钥不公开，不能声称实际生成逐字公众可重现。

质量作者PROVISIONAL；公开正文可被真人复核。CAL仅2章，不宣称1%FPR。无付费/新模型/新云资源/强攻击。
''')
save(V/'PROTOCOL_AMENDMENTS.md','''# 追加修订记录（不覆盖原冻结）

1. 首个真实forward之前，GENERATION_CODE_FREEZE.json锁定原生适配器和executor；旧freeze.json仍保留准备版代码SHA。
2. 首个DEV探针已知Top1负结果后、CAL/TEST评分前，PUBLIC_DECODER_v2.json预先增列官方MPAC confidence-list公开解码。旧Top1完整保留；未把gold码或私有位置提供给解码器。不是独立盲测。
3. 内存保护中断后，用户明确保持7B，等待资源空闲。准入线6.5GiB、输出上限、全部方法参数与槽位不变，已STARTED失败不重跑。
4. 新离线生命周期守卫lifecycle_v2.py修复时间/泄露检查，不修改原v1和实际生成路径；实际asof150记录兼容性另测，不以修复覆盖旧证据。
''')
save(V/'RUN_SNAPSHOT.json',{'utc':now,'round':a.round,'engineering':'PARTIAL','research':'INSUFFICIENT_EVIDENCE','included_actual_task_ids':sorted(actualids),
 'new_generations':n,'planned_base_slots':len(tasks),'natural_EOS':eos,'quality':dict(qc),'CAL_sources':2,'TEST_chapters_generated':evalrec['TEST_chapters_generated'],
 'keep7B_wait_user_directive':True,'private_detector_material_required_for_actual_watermark_recompute':True})
print(json.dumps({'status':'VERSIONED_DELIVERY_BUILT','path':str(V),'actual':n}))
