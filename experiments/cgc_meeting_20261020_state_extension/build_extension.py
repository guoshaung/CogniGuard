"""Build versioned audit extension from immutable v1 and isolated probe outputs."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import shutil

O=Path(__file__).parent
ROOT=O.parents[1]
V1=ROOT/'experiments/cgc_meeting_20261020'
def put(n,s):
    s=s.replace('47个',f'{len(manifest)}个').replace('47文件',f'{len(manifest)}文件').replace('47/47',f'{len(manifest)}/{len(manifest)}').replace('新增18个',f'新增{len(manifest)-29}个')
    s=s.replace('日期2026-10-19', '核查始于2026-10-19；扩充版交付2026-10-20（Asia/Shanghai）')
    s=s.replace('core/pipeline.py:10','core/pipeline.py:9').replace('core/access.py:23','core/access.py:20').replace('_run_attack_turn:1648','_run_attack_turn:1642')
    (O/n).write_text(s.strip()+'\n',encoding='utf-8')
def load(n):return json.loads((O/n).read_text(encoding='utf-8'))
symbols=load('source_symbol_index.json');results=load('state_probe_results.json');ver=load('state_probe_verification.json')
manifest=load('source_manifest.json')
def cite(path,symbol):
    item=next(x for x in symbols if x['path']==path and x['symbol']==symbol)
    return f'`{path}:{item["line"]}` `{symbol}`'
def evidence(pid):return next(x['observation'] for x in results if x['probe_id']==pid)
P='cogniguard/protection/cg/protocol.py';G='core/langgraph_runtime/pipeline.py';D='core/langgraph_runtime/teachers/dag.py';S='core/langgraph_runtime/teachers/store.py';C='cogniguard/demo/classroom_session.py'
# Neither run nor edit baseline script/metrics: preserve first-round evidence bytes.
for name in ('cgc_control_ablation.csv','cgc_real_comparison.svg'):
    shutil.copyfile(V1/name,O/name)

targets={'CGController','AgentOrchestrator','LifecycleGuard','LangGraphProtectionPipeline','ProtectionPipeline',
         'TeacherDAGGenerator','TrustChain','SQLiteTeacherAuditStore','PrivacyBudgetLedger','ExposureBudget',
         'BudgetManager','DualBudgetLedger','WatermarkPolicy','run_classroom_turn','run_classroom_graph',
         '_initial_state','save_run','sync_catalogs','guard_envelope','measure_and_commit','produce_controlled_resource'}
calls=[]
for path in manifest:
    class Visitor(ast.NodeVisitor):
        def __init__(self):self.scope=[]
        def visit_FunctionDef(self,node):
            self.scope.append(node.name);self.generic_visit(node);self.scope.pop()
        visit_AsyncFunctionDef=visit_FunctionDef
        def visit_ClassDef(self,node):
            self.scope.append(node.name);self.generic_visit(node);self.scope.pop()
        def visit_Call(self,node):
            name=ast.unparse(node.func)
            if name.split('.')[-1] in targets:
                calls.append({'path':path,'line':node.lineno,'scope':'.'.join(self.scope) or '<module>',
                              'called_expression':name,'keyword_names':[x.arg for x in node.keywords],
                              'evidence_level':'static_call_expression_not_runtime_trace'})
            self.generic_visit(node)
    Visitor().visit(ast.parse((ROOT/path).read_text(encoding='utf-8-sig')))
(O/'entrypoint_callsite_index.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')

states=[
('classroom_controller','CGController','cogniguard/agents/agent_orchestrator.py:50','session_id/student_id fields; BudgetManager object','same injected controller or manager','memory only','no restore API found','no per-controller lock','S01 S02 S03 S04'),
('classroom_budget','BudgetManager',P+':256','round_id; session_id; student_id (three separate maps)','manager instance','memory only','fresh instance empty','check+write not cross-instance transaction','S01 S02 S03 S04'),
('governance_trust','LifecycleGuard','cogniguard/governance/lifecycle.py:20','session_id','guard instance','memory only','fresh guard empty','no internal global lock','S05 S06'),
('governance_audit','AuditLedger','cogniguard/governance/audit.py:15','list order / previous hash','ledger instance','memory only','no external head anchor','no cross-process chain transaction','S07'),
('privacy_domain','PrivacyBudgetLedger','protection/student_profile/src/fopd/privacy_budget.py:23','subject_id','DomainServices/pipeline instance','memory only','fresh instance empty','pipeline.run RLock only','S08 S12 S13 S19'),
('copyright_domain','ExposureBudget','protection/teacher_resource/src/c2rag/exposure_budget.py:9','chunk_id; recent deque','pipeline instance','memory only','fresh instance empty','pipeline.run RLock only','S09 S12 S13'),
('framework_session','LangGraphProtectionPipeline',G+':266','random session_id; pinned subject; round_number','one pipeline instance','checkpointer=False','new pipeline resets state','RLock around same-instance run','S12 S13 S20'),
('teacher_chain','TrustChain','core/langgraph_runtime/teachers/chain.py:59','run_id; graph; message_id,target','one TeacherFrame per __call__','key/_seen not persisted','new chain has new key and empty _seen','RLock in admit; frame lock','S16'),
('teacher_run_store','SQLiteTeacherAuditStore',S+':53','run_id; source,target; catalog hash','all callers of same DB file','SQLite transaction: runs/nodes/edges/final/catalog text','audits/catalogs reopen; no budget/state recovery','DB locks per store transaction; not gate/sink transaction','S15 S17'),
('experimental_v3','DualBudgetLedger','experiments/evaluation/cg_v3_budget.py:33','privacy student,session; copyright session; detail resource,chunk,session','same harness/ledger object','snapshot export only','no restore/import found in this class','no cross-process transaction','S10'),
('watermark_domain','WatermarkPolicy','protection/audit_trace/src/watermark_policy.py:24','watermark_id','same policy instance','dict; external main may export results','new policy empty','no internal shared lock','STATIC'),
('dashboard_client_state','classroom_session._initial_state',C+':203','client session_state dictionary','client-returned state per request','returned JSON; no authoritative state fetch in handler','client can resend state; not server recovery','no version/CAS check found in traced handler','STATIC'),
('dashboard_recent_watermarks','RECENT_WATERMARK_SESSIONS','server.py:111','session_id','one server process','memory capped at 12 sessions','restart empty; missing state may fall back to demo','ThreadingHTTPServer; no cache lock found','STATIC'),
('fastapi_dialogue','dialogue_sessions','cogniguard/api/dialogue_api.py:59','case_index + round_count string','one API process; cg new on every request','memory dict; cumulative_disclosure separate from BudgetManager','restart empty','no lock found in traced module','S14 plus STATIC'),
]
with (O/'cgc_state_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['state_id','owner','source','key','sharing_scope','persistence','restart_behavior','concurrency_boundary','probe_ids']);w.writerows(states)
with (O/'cgc_state_probe_matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['probe_id','proposition','verified','unit','scope','observation_file'])
    for r in results:w.writerow([r['probe_id'],r['title'],r['expectation_verified'],'one synthetic component proposition, not attack trial',r['scope'],'state_probe_results.json#'+r['probe_id']])

put('cgc_real_implementation_audit.md',f'''
# CGC真实实现核查 · 源码与状态扩充版

日期2026-10-19；用于2026-10-20组会。根目录`D:/pycharm/CogniGuard`。本版追踪47个源码文件、静态调用表达式及20项隔离原生组件探针；不修改正式代码、不启动服务、不执行Stage1、不调用模型。本版是新增目录，第一版报告、原实验和冻结集保留。前版29个源码hash与本次完全一致；新增18个入口/状态相关源码也在探针前后hash一致。

## 先按实际入口区分四套控制路径

1. **可复用课堂AgentOrchestrator：已实现路由和逐消息治理。** `cogniguard/agents/agent_orchestrator.py:748`可注入cg_controller；默认创建CGController。`run_protected_flow:793`进入protected_flow_graph，固定诊断→资源→教学→评估→更新审批/最终审计。实例内预算与审计成立；跨请求共享取决于可信调用方是否复用这个对象。
2. **框架ProtectionPipeline：领域服务真实运行，额外治理为可选。** `core/pipeline.py:10`将公共名绑定到LangGraphProtectionPipeline。{cite(G,'LangGraphProtectionPipeline.__init__')}接受guard/watermark/generator，默认None。`main.py:98`离线入口没有传guard；`core/langgraph_runtime/__main__.py:273`只有--governance分支创建guard；`teachers/runner.py:63`按question新建pipeline，虽DAG有来源边界，不能称复用了跨题领域预算。
3. **轻量看板server.py：课堂状态演示是另一实现。** `server.py:1044`起的/api/dialogue/next-round→run_classroom_turn，直接传payload.session_state及cg_ablation；classroom_graph.initialize→{cite(C,'_initial_state')}。`_learning_turn_steps:665`使用dict、固定成本表、教学模板与状态更新，并不是CGController.dispatch的默认调用。底层有LangGraph不等于同一安全控制器。
4. **FastAPI dialogue_api.py：独立入口，存在契约不一致。** {cite('cogniguard/api/dialogue_api.py','dialogue_next_round')}每请求new CGController，session key为case_index+round_count，构造cg没有传该session/student。`:178`发送dialogue_diagnosis_request；当前CapabilityRegistry只有diagnosis_request。S14用原生registry确认前者拒绝、后者放行。没有启动该服务，故不宣称当前线上全部对话报错；server.py的同名URL走第3条，不受这条静态调用链直接代表。

## 七类能力结论与真实输入输出

### 1. capability/工具权限：IMPLEMENTED，身份绑定PARTIAL

{cite(P,'CapabilityRegistry.route_allowed')}：sender/receiver/type→bool、reason、required_caps。`CGController.dispatch:190`先构造消息并授权，才调用receiver；返回结果再次授权。`cogniguard/governance/capability.py:22`只匹配principal.kind/destination/purpose，principal_id和roles不参与，S05确认不同ID同kind都满足同grant；这是授权策略粒度，不能替代可信会话认证。

`core/access.py:23` AccessScope.authorize有真正的student/resource范围检查；S13原生图在authorize即拒绝越权，隐私/版权账本均空，值得保留为正向证据。历史MiMo tool_request仍是结构化数据，最终sandbox无真实I/O，不能用0/4模拟越权读宣称真实工具安全。

### 2. 来源/信任边界：运行内IMPLEMENTED，跨运行恢复PARTIAL

`TrustChain.issue:67`输出绑定run/graph/source/prompt/parents/hop/labels/text hash的HMAC消息；`admit:76`按格式、边、run/graph/sender/prompt、签名、label scope、祖先、duplicate判断，输出MessageView/None与收据。S16首条允许、同链重复拒绝；新建同名run的链仍拒绝旧签名，因为密钥重建。不存在从SQLite恢复旧密钥/_seen的路径。来源认证不判断正文正确；S18显示课堂RiskScorer对相同字段结构的正常/注入正文给同分，不能把字段风险叫内容语义风险。

### 3. 中间传播控制：IMPLEMENTED，路径覆盖PARTIAL

`teachers/dag.py:128` execute_teacher先chain.admit，再content_assessor/handoff，再构造最小base_view与upstream，最后backend生成并签发。`finish_teachers:252`执行最终检查。历史FinalOnly/FullCGC差异是中间EvidenceAssessor source/task/tool-scope准入；不是整个生产课堂控制器或三领域联合优化的对照。

**更精确的课堂规则执行顺序：** {cite(P,'PolicyRouter.evaluate')}先route；收集forbidden/raw并对raw立即拒绝；计算risk并检查deny阈值；检查累计预算（超限先DEGRADE）；再处理可sanitize字段；再risk degrade；最后ALLOW。第一版将“字段检查”概括在风险/预算之前，若指返回SANITIZE的优先级则不够精确，应以本顺序为准。

{cite('cogniguard/agents/agent_orchestrator.py','CGController._authorize_message')}在上述结果之后检查合规拒绝、处理DENY/DEFER、变换与重新评分、consume、超限拒绝、合规事件、可选guardrail、append审计。BudgetManager.consume本身会再次check并在不允许时不写入；不能仅用“外层先check后consume”就断言必然超支。类中仍无跨进程事务或自身锁；本轮没有并发压力/真实HTTP测试，竞争风险只标静态。

### 4. 审计/持久化：部分IMPLEMENTED，不是独立见证

AuditChain/AuditLedger是内存hash链；S07单记录改写verify失败，但整链替换成另一条自洽链verify通过。这只证明没有独立锚点时的验证边界，不是外部攻击者能获得写权限的实证。

{cite(S,'SQLiteTeacherAuditStore.save_run')}持久化运行/边/最终决策元数据；{cite(S,'SQLiteTeacherAuditStore.sync_catalogs')}还真实保存system_text与skill instructions。**更正存储描述：不能说这个数据库永远不存prompt；不保存的是每次运行的完整模型回复、接收正文、HMAC密钥和控制账本。** S15重新打开临时SQLite，保留2/2运行、4/4节点、2/2边和1/1 prompt版本。teacher_edges表甚至没有delivered_content_hash列，历史接收hash核验需要独立raw JSON日志，不能只凭DB重新验证消息字节。

S17在临时DB用原生SQLite触发器模拟插入失败：两个离线生成节点已执行、graph completed=True；save_run抛IntegrityError，DB事务回滚为run/node/edge均0。调用者未获得成功返回。这支持“持久化失败会报错”，但没有把已执行生成和未来外部sink副作用原子回滚；不是生产修复。

### 5. 跨Agent/会话历史：PARTIAL

BudgetManager同对象共享，S01两个PolicyRouter共享manager能看见先前0.4支出；S03新对象、S04新进程均不继承。S02进一步发现round_id独立作key：若外层共享manager而不同session/student复用round-1，第二人也会被首人的round支出影响。因此不能只把manager变成全局单例便宣称共享完成。

S12原生框架图在govern_input因capability拒绝之前，已在measure_privacy/control_resource扣费；交付失败后隐私值1.0、版权约0.153125保留。S20原subject绑定与round_number也保留；S13的前置AccessScope拒绝则尚未扣费。必须区分“输出阻断”“DB事务回滚”“领域预算回滚”。LifecycleDecision.rollback_required只是决定字段，没有自动撤销其他对象的调用。

S06同session先高风险quarantine、trust=0.85，下一条当前clean证据仍allow；历史trust目前主要被记录，不是evaluate重新判定的输入。不能把存在trust_by_session叫自适应闭环。实验V3另有previous_state机制，S10同asset换session后双预算起点为0；不是统一跨会话资产历史。

### 6. 三领域调用：PARTIAL

框架确实调用MM-FOPD选择/卡片和C²-RAG检索/受控返回，但guard_envelope只收到少量exhausted/cost/provenance bool，三domain risk均0，candidate列表空。HSW可选SelectiveHSWSTAdapter本身会检查检测/保真；S11说明其通用ProtectedText.evidence细节在guard投影时丢失。直接构造坏hook结果的S11不等于绕过该严格adapter。

领域隐私原值字面曝光与抽象信息须分清：S19原生context_card将mastery=0.42变成“理解不稳定”，selection_cost=1、released_exposure=0，原因是卡片不含字符串0.42。这是最小化收益与计量局限并存，不能把0解释成没有释放任何画像信息。S09版权ledger按chunk_id，两个人工不同asset同名chunk共享支出；是否真实资产ID冲突NOT TESTED。

### 7. 联合候选/效用/预算：正式NOT IMPLEMENTED；实验IMPLEMENTED

本次47个相关源码中的构造/调用索引见entrypoint_callsite_index.json，未发现backend/core调用实验composer。V3 compose_candidates:228/select_plan:305及harness:435真实存在，11候选、双代理预算、固定效用评分必须承认；不能算正式主流程已完成。S10只验证实验ledger作用域，不是性能/优化增益。

## 已实现与缺口图

```mermaid
flowchart LR
  I[已实现] --> A[可信调用方范围授权/路由]
  I --> B[运行内HMAC与中间内容准入]
  I --> C[SQLite运行元数据及prompt/skill目录]
  P[部分实现] --> D[同对象预算/状态与可选领域证据]
  N[正式未实现] -.-> E[跨重启共享内容历史/独立锚点]
  N -.-> F[主流程联合候选与校准效用]
  X[实验V3单列] --> Y[11候选双代理预算启发式]
```

20/20是20个不同组件命题的验证结果，各一次合成探针，不是20次独立攻击成功/失败，不能换算ASR。实际探针耗时{ver['elapsed_seconds']}秒。
''')

put('cgc_cross_agent_state_audit.md',f'''
# CGC状态所有权、恢复与持久化审计 · 扩充版

日期2026-10-19。真实源码47文件hash、精确类/方法行号见source_manifest.json/source_symbol_index.json。14种状态容器逐项登记在cgc_state_inventory.csv；20项原生隔离探针逐项输入/输出、限制见state_probe_results.json。

## 1. 可信身份与状态key必须分开审计

- 课堂CGController.session_id/student_id是构造参数，默认default_session/anonymous_student。外层复用/注入能共享对象，但没有自动认证这些字符串的逻辑。CapabilityRegistry针对固定agent名字，框架CapabilityPolicy针对kind/destination/purpose，S05确认principal_id不参与该策略。
- AccessScope在可信调用方构造，授权真实核对学生ID与资源权限；graph.authorize还把_subject固定到首个通过授权的学生。S13/S20分别说明前置拒绝不扣费，以及后置拒绝后subject绑定仍留存。这是主体隔离与恢复语义问题，不是已观测跨学生泄露。
- BudgetManager.used_by_round仅round_id；used_by_session仅session_id；used_by_student仅student_id。共享对象下两个不同subject/session若同名round会共用round桶（S02：0.4+0.2超0.5，只round超限）。是否可合并状态，必须先规定全局ID唯一性与身份授权，不是单纯改为共享dict。

## 2. 哪些历史真实影响决策

- 同manager的used_by_student/session/round会进PolicyRouter预算判定；S01真实观察到共享支出0.4。独立manager不共享（S03），两个新解释器也不共享（S04）。
- PrivacyBudgetLedger按subject累计，ExposureBudget按chunk累计及recent_hits焦点；在同pipeline有RLock覆盖一次run。不同pipeline实例各自持有新ledger，teacher_worker按question新建，因此没有跨题累计保证。
- LifecycleGuard.trust_by_session会更新，但evaluate只看当前capability、boundary、risk与constraints；S06历史trust=0.85后当前clean仍allow。不要把“记录了历史”与“历史影响了后续决策”混为一谈。
- V3 previous_state与audit head可影响实验决策；预算由同harness ledger持有。S10证明同asset session2的E_priv/E_copy为0，而session1为0.4/0.6。跨session是否应共享取决于策略，但当前没有统一asset根历史控制承诺。
- WatermarkPolicy.register/recover_source有真实运行内recovery dict，main.py水印入口确实使用，不是纯接口占位；该类本身无跨进程恢复。领域日志输出不能自动变成CGC可消费历史。

## 3. 图执行顺序决定“释放/扣费/拒绝”的语义

`core/langgraph_runtime/pipeline.py:236` build_graph明确先control_resource→measure_privacy→prepare_teaching→govern_input→generate→watermark→govern_output。领域预算在框架治理许可之前已更新。S12同一次原生图里：隐私记账1.0、版权0.153125；govern_input capability拒绝，generate没有执行、completed=False，两个账本仍保留。若目标是“仅对外成功释放扣费”，当前语义不一致；若是“所有内部生成/访问也收费”，则须明确命名并将这与对外曝光指标分开。不能未经定义就称该行为是隐私泄露或安全修复。

```mermaid
sequenceDiagram
  participant U as 可信调用方
  participant P as 原生ProtectionPipeline
  participant D as 领域ledger
  participant G as LifecycleGuard
  U->>P: run(AccessScope)
  P->>P: authorize并绑定subject
  P->>D: 受控资源生成/曝光update
  P->>D: 画像measure_and_commit
  P->>G: govern_input
  G-->>P: capability_denied
  P-->>U: PermissionError / 未交付答案
  Note over P,D: 观察到ledger及subject绑定保留，没有自动回滚
```

## 4. 持久化审计到底持有什么

SQLiteTeacherAuditStore schema version4真实保存teacher_runs、teacher_nodes、teacher_edges、teacher_final_decisions，以及teacher_prompt_versions.system_text和teacher_skill_versions.instructions。sync_catalogs与load_*检查目录hash并支持重载目录；这是已实现的配置持久化。

它没有privacy/copyright预算表、已释放正文集合、TrustState、TrustChain._seen、HMAC key、外部见证head或事务性sink receipt。teacher_edges也不含交付内容hash；raw JSON历史记录有hash，所以第一版336边核验仍成立，但不能说DB单独提供同等字节见证。S15新进程重开保留2/2运行、4/4节点、2/2边、1/1 prompt目录，同时新BudgetManager为空。它不是“没有数据库”，也不是“有数据库便恢复了全局状态”。

S17临时DB插入失败时内部事务完整回滚且异常阻止成功返回，正向保证应保留；但生成节点已经完成，不能用数据库回滚推导模型调用/工具/未来sink一起撤销。暂未实测断电、OS崩溃、真实多进程竞争、模型端副作用和异步外部输出。

## 5. 两个对话入口的状态承诺

**server.py看板路径：** handler:1044附近把payload.session_state直接传给run_classroom_turn。classroom_graph.initialize:57→classroom_session._initial_state:203，对传入dict做浅拷贝、setdefault与学习状态normalize。未在所追踪handler中发现向服务器持久状态读取/校验客户端版本或验证previous_audit_hash的步骤；构造水印时再次把给定previous_hash写进新记录，不等于核验旧链。cg_ablation由请求给定，是真实演示控制开关，但不是原生PolicyRouter/TrustChain的五组对照接口。

课堂字典预算与策略有固定成本表：return_mode对应0.08/0.06/0.04/0.02等；privacy每轮固定扣0.012。_route_status根据cut_node_ids输出固定allow/bypass_observed与风险；_run_attack_turn:1648从ATTACK_LIBRARY取既定decision/effect，攻击prompt覆盖文本不重算风险。这些是可运行演示，不能充当真实模型安全分数或服务器已实现身份防重放的证据。

server._register_watermark_session:166保存最近水印round到进程字典，最多12个session；_candidate_rounds:236缺少真实记录会回退_demo_watermark_rounds。data_source='real'是代码标签，不保证原生CGC/水印检测真实运行。ThreadingHTTPServer使用该共享dict，所追踪代码未见锁或版本检查；这是静态边界，未启动服务实施并发/篡改攻击。

**FastAPI路径：** dialogue_sessions用case_index+round_count作key；每次请求新CGController，没有注入旧manager/session/student。session.cumulative_disclosure只是响应状态累计，没有送进新的BudgetManager。诊断消息contract不匹配由S14验证；HTTP错误与实际部署NOT TESTED。其request.is_attack条件才触发预置关键词检测，这类用户提供的标签也不应成为独立安全评测条件。

## 6. 三领域数据丢失点与接口图

MM-FOPD选中record与实际卡片被领域代码使用，但guard只接actual_cost/exhausted；S19显示字面计量会把抽象mastery释放计0。C²-RAG有asset/chunk/source_trace，guard只接简化来源bool/exhausted，S09同chunk键作用域需唯一性保证。HSW detailed evidence经过ProtectedText时保留在frame，guard不消费detected/Z/fidelity，S11验证投影的所有risk=0、candidate=[]。SelectiveHSWSTAdapter自身检查是另一层真实保障，不能抹去。

```mermaid
flowchart LR
  M[MM-FOPD 原生选择/卡片/字面计量] -->|cost/exhausted| E[EvidenceEnvelope]
  C[C²-RAG 受控返回/领域曝光] -->|exhausted/来源bool| E
  H[可选HSW严格adapter] --> P[ProtectedText provenance + evidence]
  P -->|provenance_valid| E
  P -.->|未消费 detected/Z/fidelity| G[LifecycleGuard]
  E --> G
  M -.->|未接 具体内容历史/校准风险| J[正式跨域联合决策 未实现]
  C -.->|未接 全局asset根历史| J
  G -.->|未接| S[重启恢复/独立持久化见证]
  D[SQLite运行及prompt/skill目录] --> R[可重开审计/配置]
  D -.->|没有恢复调用| S
```

## 7. 并发与旁路：已测与未测

已测同实例对象共享、跨新实例/进程重置、原生图拒绝后状态保留、临时SQLite事务失败、run内签名去重。没有改正式类或猴补它的决策函数。未测真实多进程并发压力、OS重启、恶意进程隔离、所有文件/向量库/网络sink的拦截。RLock保护单pipeline与单TrustChain，SQLite事务保护该次写库，三者不组成全局原子release事务。

当前CGC只对经过其接口的动作审计；未中介sink仍不会被自动发现。不能把演示路线被标bypass_observed当成任意旁路的自动观察。全局状态的下一步问题应先明确可信资产根、可见历史内容及释放提交边界，再考虑校准风险或联合优化算法。
''')

baseline_failure=(V1/'cgc_failure_cases.md').read_text(encoding='utf-8')
put('cgc_failure_cases.md',f'''
# CGC失败案例、状态反例与证据边界 · 扩充版

本版新增20项隔离原生组件探针与入口静态审计，均不是新模型安全样本。历史80 trial的原始数字不变；cgc_control_ablation.csv按字节保留第一版，CapabilityOnly/ContextBoundaryOnly仍NOT RUN。

## 新增应当展示的反例与正向控制

- **S02，共享对象仍有key冲突条件：** 不同session/student同round_id，在共享manager下第二人只因round桶超限而受影响。不能默认一个共享加性计数器就具备正确全局主体作用域。
- **S04/S15，持久审计与控制恢复不是一回事：** 前进程可见0.4支出，下一新进程默认manager空；临时SQLite却保留2/2运行。没有生产服务重启试验，不能宣称已经观测线上丢失或已经修复。
- **S06，trust记录不构成闭环：** 高风险quarantine后trust=0.85，同session下一clean证据仍allow，与新guard相同。没有新的学习机制。
- **S07，hash链锚点边界：** 单条改动可检测，整体替换后verify可通过；本探针已拥有整个内存ledger写权，不等于证明远程攻击者具备该权限。
- **S12/S13/S20，三种拒绝时机：** AccessScope早期拒绝账本空；后置治理拒绝保留隐私1.0/版权0.153125与subject绑定；跨subject复用再拒绝。没有答案外泄，问题是记账/回滚语义及可用性边界。
- **S11，水印证据投影：** trusted hook可返回provenance_valid=True而详细detected=False的ProtectedText；guard只接来源bool仍allow。它不经过SelectiveHSWSTAdapter，不能包装成绕过真实KGW验证的攻击。
- **S17，审计失败正确地阻止成功返回，但不是统一回滚：** 2个离线生成节点完成，临时SQLite触发失败后run/node/edge为0，抛IntegrityError。没有真实模型/文件外发，也没有生产修复。
- **S18/S19，风险计量边界：** 同note字段的普通/恶意正文RiskScorer同分；mastery数值变为抽象类别后字面exposure可0。前者不代表所有后置guard允许，后者不代表零画像信息。
- **S14，FastAPI契约不一致：** dialogue_diagnosis_request在原生registry无契约，canonical diagnosis_request允许；未发HTTP，未确认部署该路径。server.py同URL是另一条课堂图路径。
- **静态前端边界：** 课堂attack分支取ATTACK_LIBRARY既定decision，水印preview有固定True与默认置信度；不能用截图宣称真实内容检测、完整链验证或自动审计旁路。

## 第一版历史证据（保留原文；相对路径对应上一目录）

{baseline_failure}

## 执行与保全补充

最终探针20/20预期命题核验通过，实际{ver['elapsed_seconds']}秒；模型0、付费API0、Stage1 0、生产库写入0。20是不同命题计数，不是同分布攻击分母。第一次试跑在临时SQLite文件清理阶段遇Windows句柄占用；仅修改新probe脚本的连接关闭方式后重跑，旧源码未改，失败试跑不计为完成。最终47/47源码前后hash一致，上一版29/29hash仍一致。
''')

put('group_meeting_cgc.md',f'''
# 2026-10-20组会：CGC源码与全局状态扩充结论

**决策仍为ANALYZE。** 已实现中间控制，尚未形成可验证的全局释放状态闭环。第一版的历史结果不变；本版用47个源码文件、14类状态容器、20项隔离原生探针，把作用域/持久化/回滚边界核实到可重复观察。

## 图1：已实现与未完成

```mermaid
flowchart LR
  R[CGC已实现] --> C[权限/路由/最小输入]
  R --> H[运行内签名/边授权/中间准入]
  R --> D[审计元数据及prompt/skill持久目录]
  R --> P[PARTIAL 同对象预算/领域证据]
  R -.-> G[缺口 跨重启共享内容历史]
  R -.-> W[缺口 独立锚点/全通道见证]
  R -.-> J[缺口 正式联合候选/校准效用]
  X[实验V3] --> Y[11候选双代理预算评分 单列]
```

## 图2：真实模型历史对照

![历史真实MiMo对照](cgc_real_comparison.svg)

NoDefense中间危险交付10/10、最终攻击1/10、正常答对9/10；FinalOnly为5/10、0/10、9/10；FullCGC为1/10、0/10、9/10。onward继续传播分别1/10、1/10、0/10。包含第一跳的传播计数与最终ASR不得混说。每方法相同10攻击源任务及10正常任务，不把80 trial或336边当独立攻击源。

中间source/task/tool-scope准入具有独立机制证据：原FinalOnly固定接收消息79条，打开原生handoff检查拒5/79，关闭拒0/79，涉及4/10攻击链；正常误拒0/10链。CapabilityOnly/ContextBoundaryOnly完整端到端消融仍NOT RUN。

## 图3：三领域接口与未接状态

```mermaid
flowchart LR
  M[MM-FOPD] -->|cost/exhausted| E[可选Envelope]
  C[C²-RAG] -->|exhausted/来源bool| E
  H[HSW严格adapter] --> P[ProtectedText]
  P -->|provenance_valid| E
  P -.->|未消费 Z/保真详情| G[LifecycleGuard]
  E --> G
  M -.->|未接具体内容历史/风险| J[正式联合选择]
  C -.->|未接跨session资产历史| J
  G -.-> S[跨重启共享控制状态]
  DB[SQLite审计与prompt/skill目录] -.->|没有恢复接口| S
```

## 本版最有价值的三条状态事实

1. **有数据库，不等于恢复控制状态。** 原生临时SQLite跨新进程保留2/2运行与prompt目录，默认新BudgetManager仍为空；控制账本没有自动恢复链。真实服务重启未测，结论限定组件/源码。
2. **阻断最终交付，不等于撤销之前的记账。** 原生图capability拒绝时没有生成答案，但领域privacy=1.0、copyright≈0.153125仍记在对象里；前置AccessScope拒绝则尚未扣费。rollback_required不是完整事务回滚。
3. **看板演示状态不等于原生控制状态。** server.py课堂接口接收客户端session_state，预算与attack decision含模板/固定表；另一FastAPI入口每次new controller且消息contract不一致。不能把前端完整图或固定watermark preview当端到端全局安全证据。

20/20是20个不同组件命题的单次合成核验，**不是20次攻击成功率**。探针{ver['elapsed_seconds']}秒，零新模型/付费调用，未运行Stage1，未触碰生产库或正式源码。跨进程并发压力、真实服务重启、所有sink覆盖仍NOT TESTED。

## 约2分钟中文讲解词

这次我继续核查CGC的真实源码和全局状态，新增审阅了入口、账本、审计库和课堂演示路径。结论还是：CGC已经具备有用的运行时控制，但还不是完成部署的联合安全优化器。

已有真实MiMo结果保持不变。同十个攻击任务里，FinalOnly有五条链出现危险交付，FullCGC是一条；最终攻击成功都是零比十，正常答对都是九比十。所以独立证据支持中间消息准入，不能支持最终安全进一步提升。

这次最重要的扩充是把状态边界实际测出来。我用原生组件做了二十个隔离合成探针，没有调用模型。首先，同一个预算对象可以共享历史，但新对象和新进程默认从空状态开始。SQLite可以保留运行记录和prompt目录，却没有自动恢复预算。其次，原生图可能先更新领域预算，再由治理层拒绝交付；拒绝后账本和主体绑定仍然保留。因此审计持久化、输出阻断和状态回滚是不同能力。

我还发现入口必须分清。看板的课堂流程主要传回客户端状态，并使用固定成本和预置攻击决策；另一条FastAPI流程每请求创建新控制器，还有消息类型与权限契约不一致。我们没有启动线上服务验证，所以这些是具体源码和组件边界，不能说所有线上服务已经故障，也不能用演示界面证明全局控制已完成。

下一步我建议只聚焦一个问题：在可信主体和资产身份下，怎样证明每次实际释放都读到了完整共享历史，并正确提交到可恢复状态？先把这个闭环验证清楚，再讨论条件内容风险和联合候选优化。本轮决策是ANALYZE。

## 交付与证据

本目录包含完整扩充版五份交付；cgc_state_inventory.csv列14类状态，cgc_state_probe_matrix.csv和state_probe_results.json列20探针，source_symbol_index.json使用类限定方法名防同名混淆，entrypoint_callsite_index.json注明静态调用不冒充动态trace。历史CSV与SVG按字节复制第一版，未重新生成历史结果。
''')

put('README.md',f'''
# CGC源码与状态审计扩充版

日期2026-10-19；组会2026-10-20；决定ANALYZE。优先阅读[group_meeting_cgc.md](group_meeting_cgc.md)，再读[cgc_real_implementation_audit.md](cgc_real_implementation_audit.md)与[cgc_cross_agent_state_audit.md](cgc_cross_agent_state_audit.md)。

第一版路径为`../cgc_meeting_20261020/`，保留原始历史重算证据。当前五份报告新增入口、状态作用域和持久化边界；历史CSV/SVG与前版字节相同。20项探针是20个不同组件命题，不是攻击ASR样本，不会填入CapabilityOnly/ContextBoundaryOnly的NOT RUN单元格。

- `probe_state.py`：在本地CogniGuard仓库根执行`python experiments/cgc_meeting_20261020_state_extension/probe_state.py`。不连接模型/服务；只在新临时目录写合成SQLite，结束关闭删除。
- `state_probe_results.json`：每项输入条件、观察值、限制；`state_probe_verification.json`：{ver['probe_count']}命题/{ver['verified_expectations']}验证、耗时{ver['elapsed_seconds']}秒、源码前后hash。
- `cgc_state_inventory.csv`：14个状态容器，owner/key/scope/persistence/restart/lock与探针对应。
- `entrypoint_callsite_index.json`：47个指定源码范围内匹配目标名称的静态调用表达式，不是完整调用图，也不是部署启用证明。
- `source_manifest.json`与`source_symbol_index.json`：固定当前真实字节与类限定符号行号。

新增探针未执行Stage1、OS重启或多进程压力测试；未修改正式代码、生产库、冻结集、历史实验。第一次试跑只有新探针临时文件清理失败，关闭SQLite连接后通过最终重跑；没有把失败试跑算完成。源码47/47在最终运行前后未变，上一版29/29同样未变。

同步仅这些报告、源码索引/hash与人工合成探针结果，不上传临时数据库、真实模型回复、学生资料、凭据或secret。SQLite存prompt/skill正文的发现来自代码和新合成库，不读取/上传历史prompt正文。
''')

assert all(r['expectation_verified'] for r in results)
assert not ver['source_changes_during_probes']
assert not ver['source_changes_since_v1']
print('Built expanded five deliverables, 14-state inventory, 20-probe matrix and static callsite index')
