"""Metadata-only selection and freeze, before reading candidate content."""
import time
from experiments.c2rag_r36_authorization_audit_20261029_01.common import *

FAMILIES=[
 ('F01','master_teacher_resources',['data/datasets/education_scenarios/teacher_resources.jsonl','data/datasets/manifest.json']),
 ('F02','layered_teacher_resources',['data/scenario_layers/teacher_resources/*.jsonl','data/scenario_layers/manifest.json']),
 ('F03','teaching_requests_and_recipient_context',['data/scenario_layers/scenario_orchestration/*.jsonl','data/scenario_layers/synthetic_profiles/*.jsonl','data/datasets/education_scenarios/student_profiles.jsonl']),
 ('F04','local_multimodal_teaching_records',['data/raw/history/*.json','data/processed/educational_semantics/*.json','data/processed/manifest.json','scripts/generate_synthetic_multimodal_data.py','scripts/build_episode_dataset.py']),
 ('F05','public_math_question_copies',['data/datasets/gsm8k/*.jsonl','data/datasets/math/*.jsonl','data/datasets/manifest.json']),
 ('F06','cached_public_OpenStax',['experiments/c2rag_r10_20261020_01/local_sources/*.html','experiments/relation_closure_20261019_01/document_preparation/local_source_snapshots/*.html','experiments/c2rag_r9_real_text_20261019_01/source_registry.json']),
 ('F07','existing_KARC_pilot',['data/benchmarks/karc_pilot_20261025_v3/README.md','data/benchmarks/karc_pilot_20261025_v3/DATASET_CARD.md',
    'data/benchmarks/karc_pilot_20261025_v3/DATA_MODEL.md','data/benchmarks/karc_pilot_20261025_v3/EXISTING_DATA_REVIEW.md',
    'data/benchmarks/karc_pilot_20261025_v3/ISSUES_AND_UNCERTAINTIES.md','data/benchmarks/karc_pilot_20261025_v3/asset.schema.json',
    'data/benchmarks/karc_pilot_20261025_v3/asset_index.json','data/benchmarks/karc_pilot_20261025_v3/documents/*.md',
    'data/benchmarks/karc_pilot_20261025_v3/private/*.json','data/benchmarks/karc_pilot_20261025_v3/public/*.json']),
 ('F08','teacher_Agent_role_configurations',['configs/teacher-teams.yaml','configs/teacher-prompts.yaml','configs/teacher-skills.yaml','configs/qasc-communication-prompts.yaml',
    'cogniguard/workflows/teachers/catalog.py','cogniguard/workflows/teachers/chain.py']),
 ('F09','knowledge_resource_loader_and_application_policy',['protection/teacher_resource/README.md','protection/teacher_resource/src/c2rag/resource_index.py',
    'cogniguard/integrations/education.py','cogniguard/applications/education/*.py','cogniguard/agents/protected_orchestrator.py']),
 ('F10','local_application_test_records',['data/test/cg_test_log.jsonl']),
]

def main():
    OUT.mkdir(exist_ok=False);selection=[];hashes={}
    for ident,title,patterns in FAMILIES:
        paths=sorted({p for pattern in patterns for p in PROJECT_ROOT.glob(pattern) if p.is_file()},key=lambda p:p.relative_to(PROJECT_ROOT).as_posix().encode('utf8'))
        files=[]
        for p in paths:
            rel=p.relative_to(PROJECT_ROOT).as_posix();b=p.read_bytes();hashes[rel]=sha(b)
            files.append({'path':rel,'bytes':len(b),'sha256':sha(b)})
        selection.append({'family':ident,'title':title,'patterns':patterns,'files':files,
            'missing_patterns':[pattern for pattern in patterns if not any(p.is_file() for p in PROJECT_ROOT.glob(pattern))],
            'selection_reason':'predeclared source category; all matching files in UTF8 path order, never by positive structure'})
    # Metadata-only extension census, not additional selected evidence. Explicitly
    # exclude models/generated reports and do not search personal home directories.
    census=[]
    for root in ['data','assets/resources','assets/documents','assets/knowledge']:
        for p in sorted((PROJECT_ROOT/root).rglob('*')):
            if p.is_file() and p.suffix.lower() in ['.pdf','.docx','.txt']:
                census.append({'path':p.relative_to(PROJECT_ROOT).as_posix(),'bytes':p.stat().st_size,
                    'disposition':'not selected: freeze only registered sources; metadata census retained'})
    write('source_selection.json',selection);write('original_document_census.json',census)
    write('PROTOCOL.md',"""# R36 来源/授权/答案可用性冻结协议

EXPLORATORY，纯只读审计。唯一问题：本地已有真实教学资料中，是否有来源支持的角色授权/答案可用性，使未授权知识视图无法由单个≤3人联盟覆盖，并能严格打破相应强固定菜单等价性？
不生成新教学资产/身份/权限/问题，不改旧数据，不运行防御或训练。许可不明材料只在本地读取，不对外发布原文/姓名/问答。
不将Agent教学角色当成现实用户授权，不将公开公式/公开题解称为受限秘密，不把合成Pilot/演示配置当真实教学证据。

## 来源冻结
十来源族F01–F10按source_selection.json固定顺序。每族所有匹配文件按相对路径UTF8字节排序，JSONL全部记录不抽有利行；GSM8K train/test只作来源与字段/权限扫描，不下载/重跑问答。
角色/权限/答案字段的全文定位和项目代码仅作语境核查，不执行生产控制器或历史runner。OpenStax仅检查已缓存公开教育来源与许可/身份边界。
文件哈希在任何候选语义/结构判断前冻结。original_document_census只保存指定本地目录pdf/docx/txt元数据，不凭文件数声称已阅读或合格。
候选只可来自冻结文件；若引用必要依据缺失，记UNKNOWN/MISSING，不临时搜索新盘符或补写授权。没有执行结果筛选和实验样本扩量。
同一资源在master/layered、raw/processed、private/public等派生位置不算独立来源；报告ID/内容哈希重复和不确定来源关系。

## 证据层级与判据
1. real_teaching_origin：真实公开教材/题库或可追溯真实教学记录。SYNTHETIC/DEMO/研究者模拟为单独类别；许可/真实性不清不得默认为真实。
2. source_backed_principals：持续接收者及其角色由来源确定；Agent节点、会话别名、同一学生的身份碎片不自动变成不同学生。
3. issuer_bound_permissions：有资产所有者/机构授权来源、主体绑定、资产范围与许可动作。role、license、allowed_use字段本身不证明实际签发的访问许可。
4. specific_restricted_target：明确受限的具体实例/答案键/内部关系，粒度、依据、公开背景固定。完整原题可公开计算的目标只能作公开边界对照。
5. normal_request_and_correct_candidates：来源支持的正常任务及实际可交付正确答案，交给谁、哪一轮；多种解法不能自动作为同任务同效用替代。
6. source_backed_answer_availability：不同角色/接收者可用答案由来源或实际权限记录确定，不能研究者人为删候选制造优势。
7. coalition_authorization_semantics：来源支持的联合权限/允许合作对象/观察范围及k<=3威胁定义。单用户ACL不能擅自扩成任意三人共谋，安全结论需标明缺口。
8. actual_cross_question_instance_binding：多个请求绑定同一持续知识资产，不能把同名变量或不同题答案拼接。
每项SUPPORTED / NOT_SUPPORTED / UNKNOWN / SYNTHETIC_ONLY，给路径+行号/JSON pointer+hash及判断解释。缺证据不是证明不存在。
八项均SUPPORTED才进入真实任务结构核验；公开材料缺受限实例/权限或合成策略均不进入算法收益比较。

## 结构检查（仅对合格契约）
使用来源原有接收者、候选、顺序、授权和关系；不调数量/身份/权限。
逐目标列未授权≤3联盟及其真实可见视图V_C。若存在同样未授权C*且所有V_C⊆V_C*，则单联盟覆盖仍成立；不是简单比较接收者数量。
无覆盖联盟只说明旧充分性证明不适用，并不证明固定菜单有差距。多个不同角色同样不证明风险依赖多Agent。
强固定菜单必须允许以来源既定题型、可信角色/权限类和公开前提为键；不能把忽略角色的弱全局菜单当强基线。缺来源题型/权限类定义时UNKNOWN，不事后缩窄菜单类。
只有能在冻结合法动作上给出独立数学/逻辑恢复证据和菜单不足证书，才标CERTIFIED_MENU_BREAK。最多8请求/10候选动作用于审计穷举；超限记SCALE_LIMIT，不裁关键动作。
本轮不提出控制策略，不开发算法。无合格来源就不运行G/OPT或模拟攻击；差距应为NOT_EVALUATED/null，不填0。

## 工具与诚信
自动字段扫描只负责定位，不是语义/法律真值。研究助手逐来源复核，无独立人类双标，所有结果探索性。
小型覆盖函数单元测试为软件自检，不作为真实任务/三人见证。UNKNOWN、来源缺失、许可不清、合成和重复全部保留。
只用Python标准库和本地已有工具；模型/GPU/付费API/新数据下载0。全来源前后哈希不变；只在独立目录写产物。
同步只含脱敏结论、字段结构/计数、哈希、出处定位、脚本与缺口，不上传原始teacher_resource/学生记录、未核准教材原文、答题日志、生产代码或密钥。
完成一次来源审查及独立记录核验后同步固定提交、回读哈希并停止，不自动继续搜集或算法实现。
""")
    write('freeze.json',{'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'before_source_content_review':True,
        'source_sha256':hashes,'protocol_sha256':sha((OUT/'PROTOCOL.md').read_bytes()),
        'selection_sha256':sha((OUT/'source_selection.json').read_bytes()),
        'preparation_code_sha256':sha(Path(__file__).read_bytes()),'source_families':len(selection),'unique_source_files':len(hashes),
        'prior_research_sync_commit':'caedf0ca698473b61207782c3472b96a07230143'})
    print('Frozen',len(selection),'source families,',len(hashes),'unique files; no content judgments yet')

if __name__=='__main__':main()
