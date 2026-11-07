"""Final sources, knowledge duties, finite tasks and secret commitments BEFORE generation."""
from pathlib import Path
import hashlib,json,re,secrets
from bootstrap import E,R,save,digest,OLD
from secrets_store import store

assert not (R/'freeze.json').exists()
assert json.loads((R/'COMPONENT_TEST.json').read_text())['status']=='PASS'
sources=json.loads((R/'inputs/DATA_MANIFEST.json').read_text())
obligations={
 'S01':['Accuracy requires an accepted reference; precision concerns repeated independent measurements under the same conditions.',
 'Reference11.0in; repeated11.1,11.2,10.9in;12in less accurate; range0.3in; alternative10.9,11.1,11.9 less precise.',
 'Do not exchange accuracy/precision or assert that precision requires the reference.'],
 'S02':['Acceleration proportional to net external vector force, same direction; inverse to mass for given force.',
 'a=F_net/m and F_net=sum(F)=ma, variable roles unchanged; scalar magnitude F_net=ma not arbitrary one component.',
 'Do not add universal conditions outside classical passage, or replace net external force by every individual force.'],
 'S03':['Work dW=F dot dr=|F||dr|cos(theta); integrate along pathAtoB.',
 'Forces may vary with position and paths may vary; no unsupported path independence.'],
 'S04':['K=(1/2)mv^2 lacks velocity direction; momentum vector p=m v includes it.',
 'Do not equate momentum to kinetic energy, or square v in momentum.'],
 'S05':['Rigid-body equilibrium has zero linear and angular acceleration relative to an inertial frame.',
 'Equilibrium can have constant linear/angular velocity; static equilibrium is rest in selected frame.',
 'Do not claim every equilibrium is rest or omit the inertial/selected-frame condition.'],
 'S06':['Earthsurface distanceR_E, Moonabout60R_E and accelerationabout1/(60^2)g.',
 'Inverse square gravitational magnitude proportional productm1m2/r^2; spherical area proportionalr^2.',
 'F12 is force on object1 exerted byobject2, rhat12 points1toward2. Do not reverse the acted-on object.'],
 'S07':['Most gauges zero at atmospheric pressure; gauge pressure is relative to atmospheric pressure.',
 'Insidepressure aboveatmospheric ->positive gauge; partially evacuated rigidchamber ->belowatmospheric ->negative gauge.',
 'Do not change negative gauge pressure into negative absolute pressure.'],
 'S08':['No friction; periodT measures one complete oscillation, usuallyseconds.',
 'Frequencyf counts oscillationsperunit time; f=1/T; Hz=cycle/s=s^-1.',
 'Do not exchange frequency/period or claim all oscillations need the same T.']}
reviews=[]
for s in sources:
 sid=s['source_id'];old=R/'inputs'/f'{sid}.txt';text=old.read_text(encoding='utf-8')
 # All selection amendments precede outputs; original preparations are retained.
 if sid=='S05':
  text=' '.join(re.split(r'(?<=[.!?])\s+',text)[:3])
 if sid=='S07':
  text='\n\n'.join(text.split('\n\n')[1:])
 final=R/'inputs'/f'{sid}_frozen.txt';save(final,text)
 reviews.append({'source_id':sid,'original_preparation_sha256':digest(old),'frozen_sha256':digest(final),
   'quality':'PASS','reviewer':'current assistant author PROVISIONAL, not external human gold',
   'basis':obligations[sid],'detection_seen':False,
   'selection_amendment':('First3 complete sentences only; retains scope definitions without later broad generalization' if sid=='S05' else
    'Original first paragraph had3000psi~207atm conversion discrepancy (3000/14.6959487755~204.14); retained original, excludes that whole paragraph BEFORE generation; selected adjacent next2paragraphs' if sid=='S07' else None),
   'raw_selected_source_or_input_overwritten':False})
 s['frozen_path']=str(final);s['public_body_sha256']=digest(final);s['quality']='PASS_PROVISIONAL';s['words']=len(text.split())
save(R/'inputs/SOURCE_QUALITY_LOCK.json',reviews);save(R/'inputs/DATA_MANIFEST_FROZEN.json',sources)

tasks=[];private={'sampling_seeds':{},'B2_keys':{},'epoch_keys':{e:secrets.randbits(31)|1 for e in ['E1','E2']}}
messages=set()
def add_source(s,recipients):
 for recipient in recipients:
  for epoch in ['E1','E2']:
   pair=f'{s["source_id"]}_{recipient}_{epoch}';private['sampling_seeds'][pair]=secrets.randbits(31)
   for method in ['C0','B2','B3']:
    issue=f'ISSUE_{pair}_{method}';code=secrets.randbits(32)
    while code in messages:code=secrets.randbits(32)
    messages.add(code)
    if method=='B2':private['B2_keys'][issue]=secrets.randbits(31)|1
    tasks.append({'task_id':issue,'issue_id':issue,'pair_id':pair,'source_id':s['source_id'],'source_split':s['split'],
      'recipient_pseudonym':recipient,'epoch':epoch,'content_version':'v1','method':method,
      'key_id':('KEY_'+issue if method=='B2' else 'MPAC_'+epoch if method=='B3' else 'NONE'),
      'message_code':format(code,'032b'),'source_sha256':s['public_body_sha256'],'source_path':s['frozen_path'],
      'status':'NOT_RUN','stage':'S2' if s['split']=='DEV' else 'S3','parent_issue_id':None})
for s in sources:
 if s['split']=='DEV':add_source(s,['R01','R02','R03'])
 elif s['split']=='TEST':add_source(s,['R01','R02'])
# Two independent chapters' unmarked controls remain UNREGISTERED (negative calibration).
for s in sources:
 if s['split']=='CAL':
  pair=s['source_id']+'_NULL';private['sampling_seeds'][pair]=secrets.randbits(31)
  tasks.append({'task_id':pair,'pair_id':pair,'source_id':s['source_id'],'source_split':'CAL','method':'C0',
    'source_path':s['frozen_path'],'source_sha256':s['public_body_sha256'],'stage':'CAL','status':'NOT_RUN',
    'issue_id':None,'epoch':None,'key_id':'NONE','message_code':None,'recipient_pseudonym':None,'parent_issue_id':None})
# One legal B->C-style parent relation, made independently from trusted S01 author text.
s=sources[0];pair='S01_REISSUE_E2';private['sampling_seeds'][pair]=secrets.randbits(31)
for method in ['C0','B2','B3']:
 issue=pair+'_'+method;code=secrets.randbits(32)
 while code in messages:code=secrets.randbits(32)
 messages.add(code)
 if method=='B2':private['B2_keys'][issue]=secrets.randbits(31)|1
 tasks.append({'task_id':issue,'issue_id':issue,'pair_id':pair,'source_id':'S01','source_split':'DEV','recipient_pseudonym':'R04',
  'epoch':'E2','method':method,'content_version':'v1','message_code':format(code,'032b'),'key_id':'KEY_'+issue if method=='B2' else 'MPAC_E2' if method=='B3' else 'NONE',
  'source_path':s['frozen_path'],'source_sha256':s['public_body_sha256'],'stage':'REISSUE','status':'NOT_RUN',
  'parent_issue_id':'ISSUE_S01_R01_E1_'+method})
store(R/'private/RUN_SECRETS.dpapi',private)
commitments={k:{a:hashlib.sha256(str(b).encode('ascii')).hexdigest() for a,b in v.items()} for k,v in private.items()}
save(R/'KEY_AND_RNG_COMMITMENTS.json',commitments)
save(R/'TASKS_FROZEN.json',tasks)
probe=[t['task_id'] for t in tasks[:3]]
cfg={'task':'HSW-AUDIT-EPOCH-01','version':1,'source_language':'English only, no translation',
 'model':'Qwen2.5-7B-Instruct original official Q4_K_M, native CPU adaptation; not cloud FP32',
 'model_path':str(OLD/'assets/models/qwen2.5-7b-instruct-q4_k_m-official/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf'),
 'tokenizer_path':str(OLD/'assets/models/qwen2.5-7b-q4km-dequant-f16-hsw-repro02'),
 'temperature':.8,'top_p':.95,'max_new_tokens':640,'context':4096,'threads':2,
 'B2':'official TextSeal toolkit Greenlist: gamma.25/delta2/ngram2/after_toppFalse/v2freshseen; not dualTextSeal',
 'B3':'official MPAC32bits/radix4/gamma.25/delta2/CPU additivePRF h2/positionPRF enabled, nofeedback, nofixedpositions',
 'special_tokens':'EOS151643/151645 natural; no min length; invalid padded token causes FAIL, no replacement',
 'attempt_ceiling':96,'outer_user_attempt_ceiling':256,'generated_token_ceiling':30000,
 'model_wall_seconds_ceiling':7200,'disk_ceiling_bytes':3*2**30,'API_calls':0,'GPU_seconds':0,
 'primary_false_accept_target':.01,'calibration_source_count':2,'insufficient_alpha_policy':'rank ceil((n+1)*(1-alpha)) beyond n -> infinite threshold -> REJECT; target1% NOT_CERTIFIED',
 'nominal_reference':'B2 Bonferroni full family includes all issued keys,2epochs, declared transform/window variants; not an empirical guarantee',
 'formats':['metadata_removed','LF_CRLF','collapse_whitespace'],
 'fragments':[50,100,200],'positions':['start','middle','end'],
 'fragment_policy':'fixed independently re-encoded text IDs; strict UTF8 token-boundary slices only; no favorable offset replacement',
 'stress_null_candidates':[1,8,32,128,512],'stress_queries':'predeclared S01 unmarked FULL and START50 only; unusedkeys not genuine recipients',
 'probe_tasks':probe,'probe_admission':'true logits finite; A bytes; public detector recomputable; EOS; knowledge before score. Each independent method can fail without blocking others.',
 'S3_gate':'For each method: both DEV sources have at least one EOS and A/finite PASS; source sample quality reviewed, knowledge FAIL retained. No post-output tuning. Method numerical/A failure pauses that method.',
 'source_split':'2DEV/2CAL/4TEST chapters; CAL never registered or issued; fourTEST chapters only exploratory.',
 'planned_tasks':len(tasks),'semantic_attack':'At most4 feasibility slots after baseline; existing validStrong0 inherited; no followup32 without valid faithful strong generation.',
 'public_detection_inputs':'Only suspect public bytes plus complete candidate registry, historical method material; no true source/recipient/epoch/private generation IDs.',
 'fingerprints':'char3 MinHash128, English all-MiniLM-L6-v2 meanpool/L2 windows, equal lexical-semantic mixture; identical candidate issued corpus for all. Existing Chinese BGE not silently primary on English.',
 'registration':'Separate experimental delivery per arm. Public 32bit code is arbitrary issue reference, not cryptographic auth tag. No secret is embedded as text.',
 'posthoc_system':'Rewrite the provided author passage faithfully in clear English. Preserve every scientific claim, equation, variable binding, value, unit, comparison, negation and condition. Do not add facts or examples. Keep approximately the same level of detail. Output only the rewritten passage.',
 'posthoc_user_prefix':'Rephrase this complete passage without changing its scientific meaning:\n\n<source>\n',
 'posthoc_user_suffix':'\n</source>',
 'quality':'author PROVISIONAL, nonblind to source; method labels hidden in review exports where feasible; locks BEFORE score computation',
 'B0':'unmarked identical author copies + signed register, AMBIGUOUS when same bytes have several registered identities',
 'simulation_clock':'E1newissue[0,100),E2[100,200),historical audit retained to900/1000;asof150;revocation130 independent; compromised key explicitly downgraded'}
save(R/'CONFIG_FROZEN.json',cfg)
files={str(p.relative_to(R)):digest(p) for p in [R/'TASKS_FROZEN.json',R/'CONFIG_FROZEN.json',R/'inputs/DATA_MANIFEST_FROZEN.json',R/'inputs/SOURCE_QUALITY_LOCK.json',R/'KEY_AND_RNG_COMMITMENTS.json']}
for p in sorted(E.glob('*.py')):files[str(p.relative_to(E))]=digest(p)
save(R/'freeze.json',{'kind':'BEFORE_FIRST_ACTUAL_GENERATION','files':files,'probe_tasks':probe,'attempts_at_freeze':0,'true_production_security':False})
save(E/'PROTOCOL.md','''# HSW-AUDIT-EPOCH-01 冻结协议

本轮为真实作者材料＋模拟交付生命周期。准确机器方案、任务全集及输入SHA见run01/CONFIG_FROZEN.json、TASKS_FROZEN.json和freeze.json。所有正式生成前固定，不从结果改阈值、密钥、样本或攻击器。上限96次尝试（低于用户256），30000生成Token、累计模型墙钟7200秒、输出3GiB；无重试、付费、GPU或下载模型。达到任一上限标剩余NOT_RUN，不补齐。

工作树codex/hsw-st从d019基线新建，原共享目录的未提交研究变更未擅自迁入。源码/模型/环境和冻结历史只读共享，缓存、日志、临时、数据库、DPAPI密钥及结果全位于本树。原始正文优先8个实际OpenStax历史CC-BY4章节片段；2DEV/2CAL/4TEST，CAL不发行。原准备稿中的单位换算/表述问题另存、事前选择原作者相邻合法span；不改旧文件、不修补模型输出。

S1为18项真实库/SQLite软件夹具，不算水印效果。S2开发2篇×3接收方×2周期，C0/官方Greenlist/官方MPAC三臂；先同一S01三臂最小探针，再执行未启动DEV槽。S3技术合格方法自动进入4个预留TEST章节×2接收方×2周期三臂的有限矩阵；这是更低矩阵，不要求耗尽最多8×4×2×3。两个CAL原文可各作一次未标记改写但不放进发行库；另做一个直接从S01可信原文产生R04版本并登记parent的单例。代码、参数、种子及任务只能按冻结表读取。

所有改写从作者正文独立生成，不让Qwen回答题目，不从另一实验臂继续改写。相同canonicalpair共享采样seed，各方法只改变指定嵌入；Greenlist和MPAC不是相同PRF，差异按完整方法而非单因素因果解释。模型为原有7BQ4 CPU，不冒充云FP32。Tokenizer取完整合法ID域与真实152064输出头分别核验，EOS保留，A公开字节为硬门槛，BPE重分词B另记而不替换公开分数。

公开检测器仅读取可疑文本和预允许候选登记/历史检测材料。不得提供真实source、issue、recipient、epoch或生成轨迹。所有原文/无水印及带水印版本均供强指纹索引。先来源/交付关联，再独立查询asof150许可；换钥不改旧身份，撤销不抹水印，受损密钥报告KEY_COMPROMISED，原样私下转发不能认定新接收人。

完整身份必须issue_id及recipient/content_version/epoch一致，不把来源相同当接收方正确。全部预登记槽保留PASS/FAIL/UNKNOWN/技术失败/NOT_RUN，拒识不是成功。作者质量审核先锁定，再揭示分数，不冒充真人金标。多bit方法只使用独立提取top1码；不将真实gold message喂给解码器。官方低层API中的固定dummyBER不参与解码/选择，已用0/1两dummy验证提取不变。

整体误报目标1%，但仅2个CAL独立章节。按预定rank最大统计量，当rank超样本数，主阈值∞、拒识并写目标未认证。另列完整排名/未认证nominal Bonferroni诊断，不把单keyz或比特准确率当全局归因正确。任何多key/epoch/窗口扫描都属于同一个查询家族。额外512nullkey压力仅DEV两个冻结查询，不是新增512接收方。TEST不能重选margin或阈值，小样本逐例，不制造独立性或显著性。

无模型攻击先做元数据删除、LF→CRLF、空白折叠和固定start/mid/end50/100/200Token；UTF8边界不合法记不可用，不换偏移。改写可行性最多4次既有不同模型；如有效强仍0就停攻击分支。任何方法失败不阻止其他无依赖工作。旧RQ2和其他研究任务不动。

输出工程COMPLETED/PARTIAL/EXTERNAL_BLOCKER与研究INTEGRATE_EXISTING/GAP_OBSERVED/INSUFFICIENT_EVIDENCE分开。只提交本轮安全文件到research-sync独立evidence分支并建draftPR，不改CogniGuard origin，不自动合并。
''')
print(json.dumps({'status':'FROZEN_BEFORE_GENERATION','planned_base_tasks':len(tasks),'probe':probe,'secret_values_logged':False}))
