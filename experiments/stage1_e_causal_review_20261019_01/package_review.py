"""Create a new causal report/export from old records only; no reruns."""
from pathlib import Path
import json,hashlib,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'experiments/stage1_e_20261019_01'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def main():
    rows=load(HERE/'case_review.json')['cases'];review=load(HERE/'group_review.json');groups=review['groups'];inventory=load(HERE/'evidence_inventory.json')
    before=load(HERE/'preservation_before.json');changed=[p for p,h in before.items() if not Path(p).exists() or sha(Path(p))!=h]
    save(HERE/'preservation_after.json',{'files_verified':len(before),'unchanged':not changed,'changed_or_missing':changed})
    if changed:raise RuntimeError('Historical evidence changed: stop publication')
    dest=HERE/'sanitized_delivery';dest.mkdir(exist_ok=False)
    table='| 架构标签 | 实际防护分支/账本 | trace数 | 每场景资产数 | 正常正确 | 互补组合 | 篡改组合 | 篡改被接收边 | 释放拒绝 |\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n'
    budget='| 架构 | 配置 | 机会/生成 | 实际非空片段 | 填充输入 | 重建非填充输入 | 填充候选输出 | 重建非填充候选 | local回复 | 接收relay |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
    for g in groups:
        method='gate_fact + '+('session key' if g['defense']=='Per-Agent' else 'root/asset key')+(' + TrustChain(enforce)' if g['defense'].endswith('+CGC') else '')
        table+=f"| {g['architecture']} | {method} | {g['traces']} | 3 | {g['normal_correct']}/3 | {g['fragment_joint']}/3 | {g['modified_joint']}/3 | {g['modified_unauthorized_edges']}/6 | {g['refusals']}/27 |\n"
        budget+=f"| {g['architecture']} | {g['defense']} | {g['query_opportunities']}/{g['fixed_generations']} | {g['nonempty_source_returns']} | {g['padded_input_bytes']} | {g['unpadded_input_bytes']} | {g['padded_candidate_output_bytes']} | {g['unpadded_candidate_output_bytes']} | {g['local_reply_bytes']} | {g['accepted_relay_bytes']} |\n"
    methods='\n'.join(f"- `{p}`：SHA256 `{h}`。" for p,h in inventory['source_hashes'].items())
    report=f'''# Stage1-E attempt_02 完整记录的只读因果复核

## 明确结论与更正

**历史数值未发现不一致，但“共享账本解释全部增量”必须限定为当前固定脚本/预算/视图定义下的程序机制解释。** 它不是已排除全部混杂的多Agent因果效应证明，不是严格等实际Token/信息消耗的验证，更不是共享账本普遍足够的结论。

M与Identity-Split的27对匹配记录（3配置×3资产×3场景），候选、gate判定、ledger承接、接收视图和组合恢复均完全一致。源码中二者都走`arch != Single-Agent`的同一分支，使用同一个固定生成函数、同样的session_0/1/2和逻辑节点。因此本批没有额外M收益；这很大程度是同构实现的阴性对照，不能说真实多Agent独立验证后已证明无效。

Per-Agent→Shared-Asset在相同架构/资产/场景内，能定位的主要执行干预确为ledger对象作用域：相同候选/源、相同0.08阈值，第二校准数在新session账本可释放，在同资产累计账本被拒绝。未发现阈值、原source版本、片段顺序或固定生成规则同时改变。但这也将分片组**联盟可用释放额度从多份0.08收紧到一份0.08**，不是保持联盟总释放额度一致时的协作对照；后续候选/实际可见信息随拒绝改变。故可以解释本程序的观察差异，不能宣称单独识别了现实拓扑效应。

## 范围、路径与只读保证

实际证据根目录 `D:/pycharm/CogniGuard/experiments/stage1_e_20261019_01/attempt_02/`；新复核目录 `D:/pycharm/CogniGuard/experiments/stage1_e_causal_review_20261019_01/`。读取全部81份raw.json、9份process_summary与9份observer事件JSONL、原始81条评分、资产/策略/生成/隐藏有限规则、执行脚本及冻结清单，并核对失败记录。原目录所有非缓存文件另有逐文件SHA256清单。没有执行runtime、原scorer或CG函数，没有重跑任何实验，没有写回历史评分或旧产物。

81个raw的hash全部与原评分登记一致；81条历史已有指标与本次从记录独立导出的对应指标一致；attempt_02冻结脚本/资产/源码无hash偏差。保全范围共 **{len(before)}份既有文件**，复核前后hash一致。新导出的5gram/LCS属于明确标记的复核派生指标，不是改写旧评分。原S00-11 FAIL、补测S00-12 FAIL、旧v2 S00-12 NOT_EXECUTED，以及attempt_01/探针失败和修正版全部保留。

## 81条、9组、3样本分别是什么

3个原始合成资产E01/E02/E03，各重复进入3个场景（normal、fragments、modified_relay）和9个架构/配置条件。总数3×3×9=81条执行trace。每个“架构×防护”组有9条，即每场景3条；**不是每组总共3条**。常见0/3、3/3只指某个场景下的3个资产。篡改场景有每trace两次relay，故边分母为6；释放拒绝用每组9trace×3门尝试=27；这些分母不可交换。

全实验只有3个高度同结构源资产，不是81个独立样本。不同场景/条件、同资产派生trace、边和槽均不能当独立抽样重复来估置信区间或推广总体。无随机种子重复或真实LLM样本。

{table}

逐案例ID、场景、source ID/hash、ledger keys、step输入/候选/判据、接收集合、拒绝和历史/复核评分均完整导出至`cases/`的9个文件，每文件9条。没有只发布自动summary。

## 真实方法和调用路径

入口为旧独立脚本runtime_v2.main中的三槽循环，**不是三个真实Agent类/进程或并行协作系统**。S/M/I是固定生成与历史/session作用域的实验标签；9个worker进程对应9个条件串行执行，并非单个M案例内的独立Agent进程。

释放路径：固定候选→原 `experiments.c2rag_v3.fact_release.gate_fact(output, documents, ledger, budget=0.08)`→`core.disclosure_measurement/tokens`与`evidence_release.measured_cost`。原函数执行来源片段/短答检查、词面cost累计并更新传入dict。没有调用完整C2RAGV3._retrieve/run_round、BM25/Dense、TeachingGenerator.generate或MetadataAuthorizer。

CGC路径：原catalog.TeacherNode/TeacherEdge/TeamSpec构造固定三逻辑节点（所有架构同样的n0/n1/n2和两边）→TrustChain(mode=enforce).issue→可能在实验脚本中改正文但不重签→admit→原生view决定relay是否交付。无CGC分支直接赋`received=wire`，未做同等的签名/路由检查。它检验的是启用既有边界原语与不启用的差异，不是两种完整系统的净效果。

原profile记录gate_fact243次、issue/admit各54次，与81trace×3门及27个CGC trace×2边对应。profile只证明这些入口调用，不能据此证明完整生产接线、真实检索/模型推理或所有sink受控。实际函数/模块源码hash：

{methods}

## 资源匹配复核：相同cap不等于相同消耗

{budget}

以上是每组9trace的字节数，不是模型Token。每trace记录填充输入9216、填充候选输出3072、3个片段访问机会及3个固定生成尝试；所有组一致。但“机会3”不是3次真实检索：normal有3次非空public片段，另两场景仅前2槽有非空校准片段，第3槽无新增校准检索；每组实际非空片段共21，不是27次真实BM25/向量检索。

重要限制：padded_input被构造、计数，却没有被固定生成器解析；生成逻辑直接读fragment/prior变量。候选输出padding经json.loads后进入gate，空格本身不产生语义。这只是人工字节包络/名额计数，不能证明真实模型相同Token、算力或提示消耗。完整padded原始流未落盘；表中的非填充长度按冻结序列化格式从已保存对象重建，明确区别于网络/模型实际计量。

M和I非填充请求每组相差81字节，来自案例ID标签长度，而决策逻辑不读取该label；其语义候选和接收视图相同。这种差异在固定脚本下不影响分支，但若未来将case_id文字输入真实模型，不能默认无效应。不同防护的候选和交付长度也不同，不能以相同padding宣称输出长度/信息量严格匹配。

资源/信息核查应分层：

| 项目 | 本记录支持的结论 |
|---|---|
| 资产版本与预定片段机会 | 相同资产/场景的9条件source hash与顺序相同；跨场景本来不同 |
| 查询/生成名额与padding | 记录及冻结代码支持一致；没有真实模型调用/真实检索 |
| 模型Token、实际模型算力 | 未执行，不可核实，不应填0 Token后说已严格匹配 |
| 非填充内容/输出字节 | 不相同，表中已量化 |
| 中间接收视图 | S第二槽有第一槽回复，M/I无；S最终用local replies，M/I用relay receipts，尤其篡改/阻断时不同 |
| 攻击者观察定义 | 各组采用相同并集规则，但实际内容不相同；规则相同不能冒充可见信息相同 |
| 可信gate的source访问 | 每门可读完整source，未计入生成名额；不能和不可信接收者的片段可见性混为一谈 |

另一个输入边界限制：第三槽虽然query_schedule=None，候选citation quote仍从闭包asset['fragments']['public']读取，不完全来自日志request.fragment（为空）或先前实际回复。所有条件同样读取此公开片段，未见M额外校准材料，但旧“生成器只见当槽片段/历史”的描述过窄。资产/生成/释放在同一Python进程，完整asset dict对程序可达，不能证明恶意生成器仅有该受限视图。隐藏oracle文件拒读探针和应用事件是工作流证据，不是OS恶意进程隔离证明。

## 账本作用域的具体机制与其他变化

每trace开始均`ledgers={{}}`，不存在跨案例/跨资产的持久化累计。S的Per-Agent key为same；M/I为session_0、session_1、session_2。Shared两组所有槽的key为fixture_delegation_root/资产ID。可信根只是实验脚本固定字符串，没有经真实身份授权层认证；gate_fact不接角色/用途/接收者principal，不能宣称本试验验证了完整身份/许可证控制。

在fragments场景，首片段释放cost约0.07214045，所有条件一致；单ledger预算为0.08。分离session下第二片段见空ledger而释放；Shared下第二片段见已支出约0.07214，累计超0.08而拒绝；S原本同session，Per与Shared结果相同。单片段不够、双片段可组合是预设有限规则的天然性质。原0.08是预先冻结压力配置，非事后改阈值，但缺少其他预算/source长度/顺序下的证据。

相同架构内Per→Shared没有发现独立的阈值/源版本/查询顺序/生成函数/状态重置周期变化，key作用域是直接改动。第二片段交付改变后，第三槽候选和历史内容改变属于后续中介结果，不应误说额外独立算法改动。然而S对M的比较同时改变session复用、第二槽历史及最终local/relay视图，无法把该复合干预拆成单独拓扑因果量。

因此更准确的归因是：**已观察到的恢复差异与当前程序的会话累计作用域/联盟可用释放额度变化一致，并能由原门的ledger前后记录逐步解释。** “共享资产账本独立解释了所有现实风险/混杂均已排除”超出证据。没有本轮反事实重放或新实验，不补造未观测配置的输出。

## CGC：传播阻断与知识恢复分开

modified_relay将第一条relay改成999但不重签。无CGC的Shared每个架构3/6篡改边被接收；Shared+CGC均0/6，原生理由signature_invalid，确有实际接收字节差异。这个端点是实验规定的完整性/授权边交付，不是语义风险分数。

同一比较的fragments和modified_relay组合恢复均0/3→0/3，**没有观察到额外知识恢复保护收益**。不能据此证明CGC对知识安全无用：Shared本来已在0地板；实验没有Per-Agent+CGC这一易恢复条件，无法在有余量的条件识别其语义保护效果。

评分攻击者并集还包括每个producer在CGC之前已收到的local gate回复。CGC拒绝下游relay不会从联盟记忆中抹去这些回复，所以该观察模型结构性限制CGC对联合恢复指标的作用。必须分别报最终接收者、生产者、联盟，不以降低某条边接收替代联盟知识减少。S最终读取local而M/I读取relay，也使边阻断到最终候选的路径因架构不同，但本批有限组合指标仍在Shared零地板。

所有81条直接交付组合答案均false；M/I分离账本的组合恢复true来自两个已交付数字按有限乘法规则可推出，而非最终source不含的乘积答案被gate放行。这一区分保留“最终答案干净而联合视图仍可恢复”的机制事实，不能叫LLM语义理解。

## 原文、语义与评分可信度

新只读导出以实际receipts计算source token 5gram覆盖和token-LCS；5gram覆盖本批全为0，仍可发生两个数字unit的组合恢复。词面覆盖低不等于语义秘密未恢复；有限数字规则也不等于通用语义oracle。新字段明示review-derived，不回填历史评分。

原“正常完成”评分等于最终公开score字段精确匹配，前两次yes只是固定确认，且yes/no有原门白名单；3/3不等于复杂多步骤教学效用。历史refusal定义gate_result.released=false，将预算拒绝、源中无乘积和abstain/schema等合并；逐step理由现已导出，不能都当同一种安全成功。单位恢复/正常正确/越权边判据各自独立于CG cost，但资产/规则来自同一准备者且无双人盲标注，仍不满足Stage1-C独立真值标准。

原首次导入观测失败、后续probe异常类型错误及修正版本保留。9个完成worker的应用观测与独立journal一致；bootstrap另外有本机hostname读取和27次被拒子进程启动，不能把这些记录删掉后声称系统级完全无操作。它们发生在显式metadata初始化、应用source读取之前，记录没有成功子进程；本复核不重试或改变策略。

## 混杂、不可核实项与边界

- 三个同结构人工资产、统一设计的乘法目标/固定算子和单一0.08压力预算，强烈限制外推；无适应性/释义/自然语言模型随机性。
- M/I不是独立Agent实现，等效结果由同一分支预设；真实协作收益未检验。
- S与M/I既有session又有history/relay差异；Per条件联盟释放额度不等，不能称纯架构效应。
- Shared虽未另改阈值/源权限，却改变有效聚合预算并通过拒绝改变后续信息；这是控制机制，不是同一信息下推理能力差异。
- 所有组pad相等，不代表真实Token/算力/未填充输入/交付信息相同；输入padding甚至不是生成器实际输入接口。
- 可信source/公开citation闭包、实际接收与claimed可见边界仍有过程层假设；无模型/网络I/O可补证的字段标未执行/不可核实。
- CGC比较处于恢复零地板，且联盟含上游已见片段，缺少Per+CGC条件；无法识别其一般恢复保护效果。
- 墙钟受各worker首个gate惰性导入影响，未随机执行/平衡冷启动；不排名性能。不同trace不是独立随机重复。

## 唯一后续问题及研究判断

唯一值得后续另行检验的问题：**固定同一可信委托根与联盟总释放预算后，现有词面cost账本是否仍会允许“各片段低cost、联合按独立有限规则可恢复禁用目标”的实际交付？** 先检验共享proxy的范围，不预设多Agent特有效应，不开发算法。本轮只提出问题，没有新执行。

保留PIVOT为“把已见session分片现象作为既有账本配置工程收尾，不包装新协作算法”的建议；收窄/更正旧“全部增量”措辞为当前实现及有限样例内的机制解释。其余现实风险问题保持ANALYZE；Stage1-C独立真值/真实模型门槛不变。本次是只读记录复核，不是新的真实LLM验证或普遍因果定理。
'''
    with (dest/'causal_review.md').open('x',encoding='utf-8',newline='\n') as f:f.write(report)
    save(dest/'group_review.json',review)
    for g in groups:
        subset=[r for r in rows if r['architecture_label']==g['architecture'] and r['defense_label']==g['defense']]
        name=g['architecture']+'__'+g['defense']+'.json'
        save(dest/'cases'/name,{'group':g,'count':len(subset),'case_reviews':subset,'history_policy':'Original historical scores copied unchanged; read_only_review_derived fields are new exports only.'})
    manifest={'review_scope':'Full sanitized causal report and all81 per-case derived exports, no new experiment','original_raw_case_count':81,'condition_groups':9,'source_assets':3,'scenarios_per_group':3,'traces_per_group':9,'assets_per_group_per_scenario':3,'historical_scores_changed':False,'old_artifacts_changed':False,'preserved_existing_files':len(before),'all_preserved_hashes_unchanged':True,'source_hashes':inventory['source_hashes'],'original_complete_inventory_sha256':sha(HERE/'evidence_inventory.json'),'original_scoring_table_sha256':sha(OLD/'attempt_02/independent_scores.json'),'runtime_v2_sha256':sha(OLD/'runtime_v2.py'),'scorer_sha256':sha(OLD/'scorer.py'),'files_sha256':{p.relative_to(dest).as_posix():sha(p) for p in sorted(dest.rglob('*')) if p.is_file()},'sensitive_scope':'No raw personal stacks, HMAC key/signatures, original student data, paid material, complete CG source or old denied package. Tiny numeric receipt strings are synthetic observations.'}
    save(dest/'review_manifest.json',manifest)
    patterns=[r'C:[/\\]Users[/\\](?!WINDOWS_USER_HOME)',r'(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)',r'-----BEGIN .*PRIVATE KEY-----']
    finds=[p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file() for pat in patterns if re.search(pat,p.read_text(encoding='utf-8'))]
    if finds:raise RuntimeError('Sensitive pattern found')
    files=sorted(p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file())
    save(HERE/'publication_allowlist.json',{'files':files,'count':len(files),'sha256':{n:sha(dest/n) for n in files},'git_blob_sha':{n:hashlib.sha1(b'blob '+str(len((dest/n).read_bytes())).encode()+b'\0'+(dest/n).read_bytes()).hexdigest() for n in files},'sensitive_pattern_findings':finds,'target':'CG/reviews/2026-10-19-stage1-e-causal-review-01/','no_previous_denied_package_retried':True})
    print(json.dumps({'files':len(files),'preserved_files':len(before),'unchanged':True,'source_assets':3,'trace_exports':81,'historical_metrics_match':review['all_historical_metric_comparisons_match'],'scan_findings':finds}))
if __name__=='__main__':main()
