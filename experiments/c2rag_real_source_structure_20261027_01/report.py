"""Post-process the frozen audit, verify rational countermodels and report ALL tasks."""
import ast
from collections import Counter
from fractions import Fraction as F
import hashlib
import itertools
import json
from core.paths import PROJECT_ROOT
from experiments.c2rag_real_source_structure_20261027_01.analyze import OUT, load_module


def read(n):return json.loads((OUT/n).read_text(encoding='utf8'))


def write(n,s):
    with (OUT/n).open('x',encoding='utf8') as f:f.write(s)


def rational(expr,world):
    """Small independent Fraction evaluator; no SymPy/Horn/model imports."""
    def walk(n):
        if isinstance(n,ast.Name):return F(world[n.id])
        if isinstance(n,ast.Constant) and isinstance(n.value,int):return F(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp):
            x,y=walk(n.left),walk(n.right)
            if isinstance(n.op,ast.Add):return x+y
            if isinstance(n.op,ast.Sub):return x-y
            if isinstance(n.op,ast.Mult):return x*y
            if isinstance(n.op,ast.Div):return x/y
            if isinstance(n.op,ast.Pow) and y.denominator==1:return x**int(y)
        raise ValueError(ast.dump(n))
    return walk(ast.parse(expr,mode='eval').body)


def verify_countermodels(tasks,math):
    checked=0;ratios=[]
    for t in tasks:
        for cert in math[t['task_id']].values():
            if cert['status']!='NONUNIQUE':continue
            a,b=cert['actual_world'],cert['alternate_world']
            if t['positivity']:assert all(F(x)>0 for x in b.values())
            if t['task_id']=='T06':assert F(b['F'])>F(b['f'])
            if t['task_id']=='T09':ratios.append(F(b['d'])/F(b['h']))
            different=False
            for field,expr in t['fields'].items():
                x,y=rational(expr,a),rational(expr,b)
                rounded=t.get('rounded_fields',{}).get(field)
                if rounded:
                    target=F(rounded['reported']);step=F(rounded['step'])
                    if field in cert['known']:assert target-step/2<=y<target+step/2
                    if field in t['target_fields'] and not target-step/2<=y<target+step/2:different=True
                else:
                    if field in cert['known']:assert x==y
                    if field in t['target_fields'] and x!=y:different=True
            assert different
            checked+=1
    # Audit the qualitative approximation premise in every saved alternate world.
    assert all(x<F(1,100) for x in ratios)
    return {'fraction_countermodels_verified':checked,'t09_max_compression_height_ratio':str(max(ratios)),
            't09_check':'all saved countermodels d/h<1%; verification only, no new target/risk rule'}


CLASSIFICATION={
 'T01':('四类观察任取二即危险；最多保留一个信息类','四部完全冲突图，简单计数；与T02同族'),
 'T02':('四类观察任取二即危险；最多保留一个信息类','同T01，不算新独立结构'),
 'T03':('直接R单项危险，V与I二选一；单位说明中性','直接目标过滤＋二类互斥，简单规则'),
 'T04':('PH ∧ [PC ∨ (V ∧ Rc)]；详细解答候选有信息支配','二元与三元重叠，但只是小型AND/OR固定规则'),
 'T05':('直接K单项危险，m与v²二选一；单位说明中性','与T03同构，简单规则'),
 'T06':('{N法,WA}、{C法,N}、{C法,d}、{N,WA,d}；N法/C法同请求不可兼选','合法动作有重叠二元/三元，等效正确解法信息不可比；仍是4条固定禁集'),
 'T07':('{m,Kf} 或 {m,v0²,W} 或 {v0²,W,Kf}','重叠二元/三元；3条固定规则可精确解释'),
 'T08':('{K,f} 或 {v²,m,f}','能量捷径＋三元原始量；2条固定规则'),
 'T09':('{E,d} 或 {m,h,d}，cm/m信息等价','两条固定规则；单位替换不算新结构'),
 'T10':('h与A同类；A、v0²、B三类中任两类即危险','三类选一的简单计数，与单一三元选二不同但仍简单'),
 'T11':('两个独立动量乘积，完整目标需4名接收者','k≤3内无完整恢复；四人恢复在承诺边界之外'),
 'T12':('{J,t} 或 {m,v,t}，ms/s信息等价','与T09同构；两条固定规则，非新增独立结构'),
}


def main():
    tasks=read('contracts.json');summaries=read('summary.json');witness=read('minimal_unsafe_witnesses.json')
    math=read('math_certificates.json')['results'];rows=read('release_combinations.json')
    ref=load_module('reference')
    checks=verify_countermodels(tasks,math)
    structural=[]
    for t in tasks:
        equivalences=[];dominated=[];incomparable=[]
        for q in t['requests']:
            acts=[a for a in t['actions'] if a['request_id']==q['request_id']]
            for a,b in itertools.combinations(acts,2):
                x=ref.closure(a['reveals'],t['rules']);y=ref.closure(b['reveals'],t['rules'])
                if x==y:equivalences.append([a['action_id'],b['action_id']])
                elif x<y:dominated.append({'prefer_less_information':a['action_id'],'more_information':b['action_id']})
                elif y<x:dominated.append({'prefer_less_information':b['action_id'],'more_information':a['action_id']})
                else:incomparable.append([a['action_id'],b['action_id']])
        removed={x[1] for x in equivalences}|{d['more_information'] for d in dominated}
        retained_min=[w for w in witness if w['task_id']==t['task_id'] and not set(w['actions'])&removed]
        structural.append({'task_id':t['task_id'],'description':CLASSIFICATION[t['task_id']],
                           'equivalent_same_request':equivalences,'information_dominated_same_request':dominated,
                           'incomparable_same_request':incomparable,'post_reduction_minimal_unsafe_count':len(retained_min),
                           'post_reduction_minima':[w['actions'] for w in retained_min],
                           'source_family': 'same_package_examples7.2_to7.5' if t['task_id'] in ['T05','T06','T07','T08'] else t['family']})
    write('structure_classification.json',json.dumps(structural,ensure_ascii=False,indent=2))
    write('countermodel_verification.json',json.dumps(checks,ensure_ascii=False,indent=2))
    selection=read('selection_register.json');selected=[x for x in selection if x.get('selected')]
    excluded=Counter(x.get('excluded_reason','unknown') for x in selection if not x.get('selected'))
    total=len(rows);coal=sum(x['all_coalition_checks'] for x in summaries)
    status=Counter(x['math_risk'] for x in rows)
    unique_math=sum(len(v) for v in math.values())
    three=[w for w in witness if any(c['genuine_three_person'] for c in w['coalitions'])]
    body=['# 任务与来源表\n\nEXPLORATORY。12个来源题目，0条真实学生请求；48个研究者子请求。原题只在评测端，学生查询不含隐藏数值。所有保护均为作者模拟实例策略，不是教材版权限制。\n',
          '|任务|原始教材例题与定位|资产族|公开前提与保护目标|候选数|\n|---|---|---|---|---:|']
    for t in tasks:
        s=t['source'];body.append(f'|{t["task_id"]} {t["title"]}|[{s["book"]} · {s["example_heading"]}]({s["url"]}#{s["question"]["id"]})|{next(x["source_family"] for x in structural if x["task_id"]==t["task_id"])}|{t["public_background"]}; 目标 {", ".join(t["target_fields"])}|{len(t["actions"])}|')
    body+=['\n## 选择/排除\n',f'固定顺序选中{len(selected)}题，排除登记{sum(excluded.values())}条（是登记记录数，不是独立题目数）：`{dict(excluded)}`。全量登记selection_register.json；不因难度、无泄露或简单同构排除。仅覆盖代数、基础力学/电学；上限截断后其他教材来源未进入，不外推到全部教学领域。',
           '\n## 逐任务契约与实际动作\n']
    for t in tasks:
        body+=[f'### {t["task_id"]} {t["title"]}\n',f'原题：{t["source"]["question"]["text"]}\n',
               f'实例目标：{t["protected_target"]}。权限：主条件r0–r3对完整目标均未授权；允许局部子问。',
               f'关系依据：{t["reasoning"]}',f'公开前提：{t["public_background"]}',
               f'原HTML：`{t["source"]["local_html"]}`；SHA256 `{t["source"]["html_sha256"]}`。',
               '\n|动作|接收者/轮次|正常请求|实际正确回答|直接信息|字节|\n|---|---|---|---|---|---:|']
        for a in t['actions']:
            body.append(f'|{a["action_id"]}|r{a["recipient"]}/第{a["round"]}轮|{a["query"]}|{a["reply"]}|{", ".join(a["reveals"]) or "仅公开背景"}|{a["utf8_bytes"]}|')
        body.append(f'\n预算与正确标准：{json.dumps(t["budgets"],ensure_ascii=False)}。仅给正确请求答案计1，跳过为0；本轮不运行拒答/控制策略。\n')
    write('TASKS_AND_SOURCES.md','\n'.join(body))

    proof=['# 最小不安全集合与独立见证\n\n每项均为实际合法动作，不同时选择同请求两个答案。所有数学证明和两世界反例在math_certificates.json，Fraction独立复验在countermodel_verification.json。UNIQUE为公开方程下可唯一恢复完整目标，NONUNIQUE有具体反世界；不是小模型输出格式评分。\n',
           '## 两个代表性案例\n',
           '### T06：净功的两种解法，信息并不相同\n',
           '原题Example7.3明确让学生分别用净力与各分力功求净功；本轮正常子请求允许任选一种。N法给N=115N,d=.8m,W=92J；C法给WA=96J,摩擦功−4J,W=92J。两者都正确且各自不唯一确定输入F,f,d。',
           'N法再交WA：F=96/.8=120，f=120−115=5；C法再交N：d=(96−4)/115=.8，继而F=120,f=5；C法再交d也恢复。这三对是危险组合，不能化成两个信息类任选多数。',
           '真正三人见证：r1第2轮拿N=115，r2第3轮拿WA=96，r3第4轮拿d=.8。三人联立F=WA/d=120,f=F−N=5。任意两人均有反世界：仅N,WA时可取F=240,f=125,d=.4；仅N,d可取F=121,f=6,d=.8；仅WA,d可取F=120,f=6,d=.8。每人仅一个已交付回答，既无单人提前累积，也无内部恶意Agent。具体自动生成反世界以JSON为准。',
           'N法与C法若同时出现也可重构，但它们属于同一请求互斥答案：本轮合法组合已排除，不能拿这个非法集合制造风险。后续只需净力子问时N法兼容；只需推力功子问时C法兼容。说明正确答案的内容选择影响后续兼容性，但本轮没有测真实需求频率或调度收益。\n',
           '### T04：热/冷功率的重叠组合\n',
           '原题20.7 part(a)要求热态与冷态功率。P热=VI=30W；P冷≈411W，冷电阻.350Ω。公开规律不受保护。只给两种功率就直接获得目标；另一条路径是r0电压12V、r1热功率30W、r2冷电阻.350Ω，算出冷功率144/.350≈411W，三人共同恢复两种功率。',
           '任意两人不足：{V,P热}不确定冷电阻；{V,R冷}不确定热电流；{P热,R冷}可同时改变V与I而保持乘积30，从而改变冷功率。三人目标唯一、单人无历史累积。',
           '详细计算候选比只报功率透露更多数值，并非算法独立优势；去掉这些信息支配候选，仍保留{P热,P冷}与{V,P热,R冷}两条重叠限制。约411W按区间观测，未用它反推出精确电阻。该结构仍能写成P热 ∧ [P冷 ∨ (V ∧ R冷)]的小固定规则。\n',
           '## 全部任务的最小集合\n']
    for t in tasks:
        tw=[w for w in witness if w['task_id']==t['task_id']]
        proof.append(f'### {t["task_id"]} {t["title"]}：{len(tw)}个\n')
        if not tw:proof.append('k≤3没有完整目标的最小不安全集合；T11仅全部四人并集恢复，单个动量仍可部分恢复，不能把“无完整恢复”写成零信息泄露。\n')
        for w in tw:
            proof.append('- `{'+', '.join(w['actions'])+'}`')
            for cl in w['coalitions']:
                cert=math[t['task_id']][cl['math_key']]
                proof.append(f'  - 联盟{cl["members"]}；观察`{cl["math_key"]}`；证明`{cert["uniqueness_certificates"]}`。')
                if cl['genuine_three_person']:
                    proof.append('  - 三人见证：所有单人/两人子联盟均NONUNIQUE；具体反世界：')
                    for p in cl['all_proper_coalitions']:
                        pc=math[t['task_id']][p['math_key']]
                        proof.append(f'    - {p["members"]}：{pc["alternate_world"]}；替代目标{pc["alternate_target"]}。')
        proof.append('')
    write('MINIMAL_UNSAFE.md','\n'.join(proof))

    audit=[f'''# STRUCTURE AUDIT · 实源教学任务组合泄露结构验证

**结论：已找到适合下一轮“小规模受控算法比较”的组合结构；真实需求外部效度仍不足。** 超过R32的严格二类多数结构，但没有发现成熟闭包/固定规则处理不了的新推断机制。本轮决定 **ANALYZE**，仅建议一个后续比较，不自动执行。

EXPLORATORY，作者契约标注，无双人独立标注；12道原教材题，48个作者子请求，0真实学生日志。全部受保护目标是模拟实例授权；教材公开公式/文本没有被冒称秘密。学生若能查原题则目标不再保密，见可见性对照。

## 结果与分母

枚举{total}个合法释放组合、{coal}个size≤3联盟视图；每请求最多一个候选。ExactK3与set参考全部向量一致，方程判据与闭包风险逐联盟0分歧。{unique_math}个不同观察集合完成独立数学检查，其中{checks['fraction_countermodels_verified']}组NONUNIQUE证据经另一份Fraction解释器复验；UNKNOWN=0仅限这些冻结契约。所有实际reply/接收者/轮次/字节与各联盟可见字段均保留。

合法组合状态：SAFE={status['SAFE']}，UNSAFE={status['UNSAFE']}，UNKNOWN={status.get('UNKNOWN',0)}；**这些是枚举组合数，不是攻击成功率、真实需求发生率或独立样本数。** 共{len(witness)}个原始动作最小不安全集合，{len(three)}个三人最小见证（单位等价回答会重复，归并后另报）。有真实三人见证的题为T04/T06/T07/T08/T09/T12；后三类存在结构同构，不能作为6个独立新机制。

正常安全非空释放每题均有；同内容全部联盟显式授权时误报警0/{total}。T11是k上限对照：4人各持一个输入，4人总并集恢复两个动量，任何≤3人不完整恢复，且可能部分恢复。原题/网页完全公开可见的对照下，12题完整实例均可直接计算，模拟安全问题消失。不要把关闭网页访问当作真实版权事实。

|任务|候选|合法组合|不安全组合|最小集合|三人最小集合|数学/闭包分歧|
|---|---:|---:|---:|---:|---:|---:|''']
    for s in summaries:audit.append(f'|{s["task_id"]}|{s["candidates"]}|{s["legal_schedules"]}|{s["schedule_status"].get("UNSAFE",0)}|{s["minimal_unsafe_count"]}|{s["three_person_witnesses"]}|{len(s["horn_math_disagreements"])}|')
    audit+=['\n## 是否仍为简单问题：全任务逐项\n',
            '|任务|完整解释|判断|等价/支配去重后最小集合数|\n|---|---|---|---:|']
    for x in structural:audit.append(f'|{x["task_id"]}|{x["description"][0]}|{x["description"][1]}|{x["post_reduction_minimal_unsafe_count"]}|')
    audit+=['''
T04/T06/T07/T08/T09/T12均存在同一动作参与多条最小不安全组合；不是单一三元选两类，也不是把各禁集拆为互不相关的独立组。T01/T02/T10仍是一般化的简单信息类计数；T03/T05是直接目标过滤与二类互斥；T11是独立乘积和联盟上限。

最有价值的来源证据是T06：原题本身支持两种完整正确解法，信息集合不可比较、与后续不同子问的兼容性不同。T04详细答案仅为更短正确答案的信息超集，单凭它不能证明复杂回答选择；去掉支配候选后仍有两条重叠限制，但AND/OR固定规则足够。T09/T12单位转换只产生等价动作，不算额外结构；条件均为固定公开前提，没有伪造条件冲突。来源未提供实际异质授权，故只检查统一模拟主策略和全授权对照，不宣称已证明多权限交互。

**所有题均能由少量精确固定规则/公开方程穷举解决。** 发现超出“二类多数”≠排除了所有简单解释；本轮没有证明更大规模的计算困难、真实语言自动解析性能、未来需求预测价值或新的算法贡献。没有测性能领先，也没有重跑R32。

## 真实来源与作者设计的边界

原始教材题、数值、热冷状态、两种功法、能量定理和分支条件有本地HTML可定位。受保护目标粒度、将题分成4个请求、分给4个学生、隐藏来源身份、权限和候选表达均为研究者构造。所谓“实源”修饰教材题，不表示真实课堂已经存在这样的四人请求序列。

T05–T08同包裹且共享先前计算，不是4个独立资产；本轮按单任务状态清空，**没有**测试跨这4题的持久联合历史。12题只来自2本教材、7个页级来源；来源族/语义重复在表中保留，不能做独立样本置信区间。T01/T02同仿射族，T09/T12的最小禁集同构。选取上限与登记顺序使样本偏向基础定量物理，非全部教学代表样本。

## 判据、精度与失败/缺口

闭包只认识作者结构化的正确关系，未验证自然语言抽取；也未运行RAG/生成或任意自然语言攻击。数学证明器读到隐藏实例数值用于核验真值，但检测端只接收公开规则与实际已交付字段。两实现同闭包不是充分证据，额外独立方程检查与显式反世界补足本批契约的数值可恢复性。

教材数值按名义有理数；T07/T08/T09/T12的未舍入平方/能量/力属于作者透明计算表达，不冒称逐字教材答案。T04冷功率用整瓦区间且禁止精确逆用，其余保护目标是名义量，并不宣称穷尽所有舍入容差下的近似重构。对实际测量误差、更宽参数域、外部检索、隐式前提，当前结论不适用。T09近似忽略压缩期间重力功；所有保存反世界满足d/h<1%，具体最大值见countermodel_verification.json，不能推广到不满足近似的情形。

没有因简单结果排除题目；T11完整保留为阴性组合。没有脚本失败后调目标、调题或调参数；主运行一次，执行记录execution_started.json。最初git只读拉取因连接中断失败，R32改由GitHub连接器读取，未改历史结果。UNKNOWN=0是这批明确契约的覆盖结果，不是自动解析器零未知。

## 验证与复现

冻结见freeze.json；PROTOCOL在结构枚举前落盘。ExactK3/参考文件SHA256与R32 source_manifest一致。源文件前后SHA256相同；只新增独立experiments定义和var/results产物，不修改生产控制器。模型/付费API调用0。run.cmd test本目录test_audit.py：2 passed，检查同请求互斥、身份累积、k边界和精确联盟授权。报告后处理不修改冻结数据/主结果。

复现：先在新的RESULTS_DIR子目录运行prepare_sources、freeze、analyze、report（本目录脚本当前OUT固定，需在新实验副本中设置新运行名，避免覆盖）。主解释器.venv-langgraph；数学子进程使用已安装SymPy1.13.1的.venv。所有写入拒绝覆盖；无需安装包、训练或下载模型。完整证据链见TASKS_AND_SOURCES.md、contracts.json、release_combinations.json、minimal_unsafe_witnesses.json、math_certificates.json与MANIFEST.sha256.json。
''']
    write('STRUCTURE_AUDIT.md','\n'.join(audit))
    write('NEXT_STEPS.md','''# 下一步唯一建议（本轮不执行）

ANALYZE。允许进入一次极小规模、预先注册的回答选择/安全可行性比较，以T06来源支持的“两种正确功法”为唯一机制族，T04作可简化对照。比较静态规范回答/固定禁集规则、现有ExactK3与独立穷举参考；同候选、同接收者/轮次、同总字节及查询预算，有限未来需求情景预先冻结，分别报告正确任务数、完整实例恢复和真实字节。先问“信息不可比的正确答案是否带来真实可行性差异”，不训练预测器，不以更强解析器给新方案制造优势。

若规则规范回答已经达到穷举可行结果，停止将该问题包装成新调度算法；若有可解释差异，也只证明作者情景中的选择价值。要讨论实际收益，另需合法、去标识且与表现无关选取的真实请求序列/教师任务流程，以及独立契约标注；当前没有这类证据。

尚不能决定：真实需求频率、真实不同权限的组合效应、跨题持久历史、更宽自然语言条件和舍入容差。不要通过同题换数字/换身份扩样，不自动扩量或训练。
''')
    write('decision.json',json.dumps({'decision':'ANALYZE','completion':'COMPLETE_SINGLE_ROUND_STOP',
          'structure_gate':'source_supported_overlapping_pair_triple_constraints_and_incomparable_correct_answer_choices',
          'algorithm_novelty_proven':False,'simple_fixed_rules_sufficient_for_this_batch':True,
          'real_student_logs':0,'source_problems':12,'author_requests':48,
          'legal_combinations':total,'coalition_checks':coal,'minimal_unsafe_sets':len(witness),
          'primary_math_unknown':status.get('UNKNOWN',0),'independent_math_fieldsets':unique_math,
          'next_round_executed':False},ensure_ascii=False,indent=2))
    write('README.md','''# C²-RAG 实源教学组合结构审计

先读STRUCTURE_AUDIT.md；协议PROTOCOL.md；来源和实际动作TASKS_AND_SOURCES.md；逐案例证明MINIMAL_UNSAFE.md；全量组合与独立数学证据JSON；后续唯一建议NEXT_STEPS.md。所有授权作者模拟，所有请求研究者构造，EXPLORATORY，无模型调用。本轮已停止。
''')
    paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='MANIFEST.sha256.json')
    write('MANIFEST.sha256.json',json.dumps({str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},ensure_ascii=False,indent=2))
    print(json.dumps({'legal_combinations':total,'coalitions':coal,'minimal_sets':len(witness),'three_person_raw_sets':len(three),
                      'math_fieldsets':unique_math,'countermodel_checks':checks,'status':dict(status)},ensure_ascii=False))


if __name__=='__main__':main()
