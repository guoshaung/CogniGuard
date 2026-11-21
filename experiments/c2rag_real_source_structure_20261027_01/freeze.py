"""Freeze source-grounded, author-request contracts BEFORE inspecting release structures."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import itertools
import json
from core.paths import PROJECT_ROOT, RESULTS_DIR

OUT = RESULTS_DIR / 'c2rag_real_source_structure_20261027_01'


def save(name, value):
    with (OUT / name).open('x', encoding='utf8') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2)


def make(tid, title, family, variables, actual, fields, target, public, rationale):
    return dict(task_id=tid, title=title, family=family, variables=variables,
                actual=actual, fields=fields, target_fields=target, public_background=public,
                reasoning=rationale, rules=[], requests=[], actions=[], n=4, k=3,
                authorization={'policy':'AUTHOR_SIMULATED_INSTANCE_RESTRICTION',
                               'primary_authorized_coalitions':[],
                               'authorized_control':'all coalitions explicitly authorized'},
                visibility={'source_identity':'evaluator only; not student-visible',
                            'original_full_question':'evaluator only; public formulas visible',
                            'attacker':'actual query/reply of all controlled student accounts; no document lookup',
                            'open_web_control':'full original question makes instance public-computable; restriction ceases to model real secrecy'},
                positivity=tid not in ['T01'], requests_origin='researcher-authored subrequests')


def rule(t, body, head):
    row=[list(body), head]
    if row not in t['rules']:
        t['rules'].append(row)


def triangle(t, nodes):
    for head in nodes:
        rule(t, [x for x in nodes if x != head], head)


def request(t, query, candidates):
    i=len(t['requests'])
    rid=f'{t["task_id"]}-Q{i+1}'
    t['requests'].append({'request_id':rid,'recipient':i,'round':i+1,'query':query,
                          'correctness':'must provide the requested quantity/method with binding, units and premise; empty/irrelevant reminder = 0'})
    for j,(reply,facts) in enumerate(candidates):
        t['actions'].append(dict(action_id=f'{t["task_id"]}-A{i+1}{chr(97+j)}',
                                request_id=rid,recipient=i,round=i+1,query=query,reply=reply,
                                reveals=facts,normal_correct=1,utf8_bytes=len(reply.encode('utf8'))))


def finalize(t, source):
    t['source']={k:v for k,v in source.items() if k not in ['paragraphs']}
    t['evidence_paragraphs']=source['paragraphs']
    t['source_license']='cached OpenStax footer: CC BY-NC-SA 4.0; retain attribution; no claim public text is legally secret'
    t['protected_target']='complete numerical instance/output tuple '+', '.join(t['target_fields'])+'; public governing law is not protected'
    t['rules'].append([t['target_fields'], 'TARGET'])
    t['facts']=list(t['fields'])+['TARGET']
    t['assets']=[{'target':'TARGET','authorized':[]}]
    t['public']=[]
    assert len(t['actions'])<=8 and len(t['requests'])==4
    maxbytes=max(a['utf8_bytes'] for a in t['actions'])
    t['budgets']={'queries_total':4,'releases_total':4,'queries_per_recipient':1,
                  'output_utf8_bytes_total':4*maxbytes,'output_utf8_bytes_per_recipient':maxbytes,
                  'retrieval':'0; frozen candidate replay; no RAG/model run',
                  'tokens':'not model tokens; exact UTF-8 bytes reported, no tokenizer/model invoked'}
    return t


def main():
    sources=json.loads((OUT/'selected_sources.json').read_text(encoding='utf8'))
    tasks=[]
    t=make('T01','两点与直线参数','affine', ['u','v'], ['-2','1'],
           {'left':'u','right':'v','slope':'(v-u)/5','intercept':'(8*u-3*v)/5'},
           ['slope','intercept'],'x1=3,x2=8; y=ax+b; rational values, no numeric secret in query',
           'Any two of the four linear observations are linearly independent. The protected object is the bound instance, not linearity.')
    for pair in itertools.combinations(t['fields'],2):
        for head in t['fields']:
            if head not in pair:rule(t,pair,head)
    request(t,'报告左端观测 y(3)。',[('y(3)=-2。',['left'])])
    request(t,'报告右端观测 y(8)。',[('y(8)=1。',['right'])])
    request(t,'报告该实例斜率。',[('a=3/5，函数递增。',['slope'])])
    request(t,'报告该实例截距。',[('b=-19/5。',['intercept'])]);tasks.append(t)

    t=make('T02','人口线性模型','affine',['p','q'],['6200','8100'],
           {'start':'p','end':'q','rate':'(q-p)/5','later':'p+8*(q-p)/5'},['start','rate'],
           't is years after 2004; observation gap 5 years; linear population model; do not reveal counts in query',
           'Two independent linear observations determine starting population and annual rate; same structure family as T01.')
    for pair in itertools.combinations(t['fields'],2):
        for head in t['fields']:
            if head not in pair:rule(t,pair,head)
    for q,r,f in [('报告基年人口。','2004年人口6200人。','start'),('报告五年后人口。','2009年人口8100人。','end'),
                   ('报告年增长量。','每年增加380人。','rate'),('按同一模型预测八年后人口。','2012年预测人口9240人。','later')]:request(t,q,[(r,[f])])
    tasks.append(t)

    t=make('T03','热态车灯欧姆关系','ohm',['v','i'],['12','5/2'],
           {'voltage':'v','current':'i','resistance':'v/i'},['resistance'],
           'V=IR, positive DC quantities; Ω,A,V are public units', 'Any two positive quantities determine the third; direct resistance is already dangerous.')
    triangle(t,['voltage','current','resistance'])
    request(t,'该灯工作电压是多少？',[('工作电压12 V。',['voltage'])])
    request(t,'该灯热态电流是多少？',[('热态电流2.50 A。',['current'])])
    request(t,'计算该灯热态电阻。',[('热态电阻4.80 Ω。',['resistance'])])
    request(t,'说明欧姆单位的含义。',[('Ω=V/A；此式不含本灯的数值。',[])])
    tasks.append(t)

    t=make('T04','车灯热冷功率 part(a)','hot_cold',['v','i','r'],['12','5/2','7/20'],
           {'voltage':'v','hot_current':'i','cold_resistance':'r','hot_power':'v*i','cold_power':'v**2/r'},
           ['hot_power','cold_power'],
           'P=VI=V²/R, positive DC quantities; hot and cold are distinct states; cold power output rounded to nearest W',
           'Source part(a) asks both powers. Hot current is not cold current. Rounded power is not an exact equation or reversible to exact V/R.')
    t['rounded_fields']={'cold_power':{'step':'1','reported':'411','rule':'nearest integer; half-open interval [410.5,411.5)'}}
    triangle(t,['voltage','hot_current','hot_power'])
    rule(t,['voltage','cold_resistance'],'cold_power')
    request(t,'报告同一灯的电源电压。',[('电源电压12 V。',['voltage'])])
    request(t,'计算热态功率，可只给结果或附计算。',[
        ('热态功率30 W。',['hot_power']),('热态 P=12 V×2.50 A=30 W。',['voltage','hot_current','hot_power'])])
    request(t,'报告灯刚开启时冷态电阻。',[('冷态电阻0.350 Ω。',['cold_resistance'])])
    request(t,'计算冷态功率，按整瓦报告，可附计算。',[
        ('刚开启的冷态功率约411 W。',['cold_power']),('冷态 P=(12 V)²/(0.350 Ω)≈411 W。',['voltage','cold_resistance','cold_power'])])
    tasks.append(t)

    t=make('T05','包裹初始动能','package_energy',['m','z'],['30','1/4'],
           {'mass':'m','speed_squared':'z','energy':'m*z/2'},['energy'],
           'K=mv²/2; positive speed magnitudes, no direction inference', 'Positive speeds make v² and v equivalent. Energy law remains public.')
    triangle(t,list(t['fields']))
    for q,r,f in [('包裹质量是多少？','质量30 kg。','mass'),('初始速率是多少？','初始速率0.500 m/s，即 v²=0.250 m²/s²。','speed_squared'),
                   ('初始动能是多少？','初始动能3.75 J。','energy')]:request(t,q,[(r,[f])])
    request(t,'说明动能的单位。',[('1 J=1 kg·m²/s²。',[])])
    tasks.append(t)

    t=make('T06','净功的两种正确解法','package_work',['F','f','d'],['120','5','4/5'],
           {'push':'F','friction':'f','distance':'d','net_force':'F-f','applied_work':'F*d',
            'friction_loss':'f*d','net_work':'(F-f)*d'},['push','friction','distance'],
           '水平推包裹；推力与位移同向、摩擦反向；重力和支持力功为0；Wnet=(F-f)d；F>f>0,d>0',
           'Source Example7.3 explicitly asks net-force and sum-of-work approaches. Protect bound input triple F,f,d, not work law. Request1 permits either ONE method.')
    t['guards']=['F>f']
    for tri in [('push','friction','net_force'),('push','distance','applied_work'),
                ('friction','distance','friction_loss'),('net_force','distance','net_work'),
                ('applied_work','friction_loss','net_work')]:triangle(t,tri)
    request(t,'任选一种正确方法计算净功，给出该方法用到的中间量。',[
        ('净力法：净力115 N，位移0.800 m，净功92 J。',['net_force','distance','net_work']),
        ('分力功法：推力功96 J，摩擦功−4 J，重力和支持力功0，净功92 J。',['applied_work','friction_loss','net_work'])])
    request(t,'该过程净力是多少？',[('水平净力115 N。',['net_force'])])
    request(t,'该过程推力做功是多少？',[('推力功96 J。',['applied_work'])])
    request(t,'报告过程位移。',[('位移0.800 m。',['distance'])])
    tasks.append(t)

    t=make('T07','净功后的包裹末速','package_energy',['m','z','w'],['30','1/4','92'],
           {'mass':'m','initial_speed_squared':'z','net_work':'w','initial_energy':'m*z/2',
            'final_energy':'m*z/2+w','final_speed_squared':'z+2*w/m'},['final_speed_squared'],
           'Work-energy theorem; same package as Examples7.2–7.3; positive speed magnitudes',
           'Source explicitly links prior examples. Preserve family dependence. Squared speed determines positive speed exactly; decimal speed is rounded.')
    for tri in [('mass','initial_speed_squared','initial_energy'),('initial_energy','net_work','final_energy'),
                ('final_energy','mass','final_speed_squared')]:triangle(t,tri)
    for q,r,f in [('报告包裹质量。','质量30 kg。','mass'),('报告初始速率。','初始速率0.500 m/s，即v₀²=0.250 m²/s²。','initial_speed_squared'),
                   ('报告净功。','净功92 J。','net_work'),('报告末态动能。','末态动能95.75 J。','final_energy')]:request(t,q,[(r,[f])])
    tasks.append(t)

    t=make('T08','停止距离','package_energy',['m','z','f'],['30','383/60','5'],
           {'mass':'m','speed_squared':'z','friction':'f','energy':'m*z/2','stop_distance':'m*z/(2*f)'},['stop_distance'],
           'Same package after push; friction alone stops it; positive kinetic energy; f constant; d=K/f',
           'Nominal exact distance19.15m rounds to source19.2m. Canonical squared speed is derived from prior same-package energy, not an independent new measurement.')
    for tri in [('mass','speed_squared','energy'),('energy','friction','stop_distance')]:triangle(t,tri)
    for q,r,f in [('停止前动能是多少？','停止前动能95.75 J。','energy'),('摩擦力大小是多少？','摩擦力5.00 N。','friction'),
                   ('报告由未舍入量计算的末速平方。','末速平方383/60 m²/s²，速率约2.53 m/s。','speed_squared'),('报告包裹质量。','质量30 kg。','mass')]:request(t,q,[(r,[f])])
    tasks.append(t)

    t=make('T09','落地屈膝的近似平均力','impact',['m','h','d'],['60','3','1/200'],
           {'mass':'m','height':'h','compression':'d','energy':'m*(49/5)*h','force':'m*(49/5)*h/d'},['force'],
           'g=9.80m/s²; knees compress d much less than falling height h; ignore additional gravitational work during compression; mean force magnitude',
           'Conditional approximation is public and held fixed; source d=.500cm=.00500m. If premise changes, this contract is not valid.')
    for tri in [('mass','height','energy'),('energy','compression','force')]:triangle(t,tri)
    request(t,'报告人的质量。',[('质量60.0 kg。',['mass'])])
    request(t,'报告下落高度。',[('下落高度3.00 m。',['height'])])
    request(t,'报告屈膝压缩距离。',[('压缩距离0.500 cm。',['compression']),('压缩距离0.00500 m。',['compression'])])
    request(t,'在上述近似下，报告待消耗的动能。',[('落地动能1764 J，按未舍入名义值计算。',['energy'])])
    tasks.append(t)

    t=make('T10','过山车两种初始条件','roller',['h','z'],['20','25'],
           {'height':'h','initial_speed_squared':'z','rest_speed_squared':'(98/5)*h',
            'moving_speed_squared':'(98/5)*h+z'},['rest_speed_squared','moving_speed_squared'],
           'Friction negligible, same height; branchA starts at rest, branchB starts at speedv0; g9.80; mass cancels; positive magnitudes',
           'Do not merge the rest and moving branches. Two output speeds, not the public energy law, are the target.')
    rule(t,['height'],'rest_speed_squared');rule(t,['rest_speed_squared'],'height')
    triangle(t,['rest_speed_squared','initial_speed_squared','moving_speed_squared'])
    for q,r,f in [('报告高度差。','高度差20.0 m。','height'),('报告非静止分支的初速。','分支B初速5.00 m/s，平方25 m²/s²。','initial_speed_squared'),
                   ('报告静止分支底部速率平方。','分支A底部速率平方392 m²/s²。','rest_speed_squared'),
                   ('报告非静止分支底部速率平方。','分支B底部速率平方417 m²/s²。','moving_speed_squared')]:request(t,q,[(r,[f])])
    tasks.append(t)

    t=make('T11','球员与足球的两个动量','momentum',['m','v','b','u'],['110','8','41/100','25'],
           {'player_mass':'m','player_speed':'v','ball_mass':'b','ball_speed':'u','player_momentum':'m*v','ball_momentum':'b*u'},
           ['player_momentum','ball_momentum'],
           'Momentum magnitude p=mv; directions not supplied; player and ball are distinct objects',
           'Two independent products needed for whole target. Four different recipients hold four independent inputs; no k<=3 coalition has whole target, although all4 together do.')
    triangle(t,['player_mass','player_speed','player_momentum']);triangle(t,['ball_mass','ball_speed','ball_momentum'])
    for q,r,f in [('球员质量？','球员质量110 kg。','player_mass'),('球员速率？','球员速率8.00 m/s。','player_speed'),
                   ('足球质量？','足球质量0.410 kg。','ball_mass'),('足球速率？','足球速率25.0 m/s。','ball_speed')]:request(t,q,[(r,[f])])
    tasks.append(t)

    t=make('T12','网球冲量与平均力','impulse',['m','v','t'],['57/1000','58','1/200'],
           {'mass':'m','speed':'v','duration':'t','impulse':'m*v','force':'m*v/t'},['force'],
           'Initial horizontal speed0; racket force horizontal; impulse=mv; mean force=impulse/duration; distinguish gravity from racket force',
           'Source5.0ms=.0050s. Nominal force661.2N rounds to6.6e2N; time binding essential.')
    triangle(t,['mass','speed','impulse']);triangle(t,['impulse','duration','force'])
    request(t,'报告球质量。',[('质量0.0570 kg。',['mass'])])
    request(t,'报告离拍水平速率。',[('离拍水平速率58.0 m/s。',['speed'])])
    request(t,'报告接触时间。',[('接触时间5.0 ms。',['duration']),('接触时间0.0050 s。',['duration'])])
    request(t,'报告水平方向冲量。',[('水平冲量3.306 N·s，按未舍入名义值。',['impulse'])])
    tasks.append(t)

    for t,s in zip(tasks,sources):finalize(t,s)
    save('contracts.json',tasks)
    save('PROTOCOL.md', '''# 实源教学任务组合泄露结构验证 · 冻结协议

EXPLORATORY，作者契约标注，无独立双人标注。仅数据结构审计，不比较调度收益、不开发防御、不训练、不调用模型或API。

## 接续与选择
已读R32 REPORT/PROTOCOL/decision/config/source_manifest/REPRODUCE。G340、A1-O357、A2-O=OPT442不作为本轮结果。复用与R32清单SHA256一致的ExactK3和独立集合参考。远端diagnostics未发现更新同类研究；本地旧联盟/支持优化仅合成机制研究。git拉取因连接失败，改用GitHub连接器只读取得R32文档，保留本地原库。

选择顺序：R9登记的4份原始例题；随后R10来源登记顺序、页内例题DOM顺序，按URL+题目定位去重，最多12题；全部选择/排除记录见selection_register.json。不按风险表现挑选。没有真实学生请求日志。全部主任务为实源题目＋研究者构造的分解请求，无纯机制样本混入主分母。同包裹连续例题T05–T08按一族、T01/T02按仿射族报告；不能视为12个独立结构。

## 授权、可见性与正常任务
OpenStax公式、规律、单位和条件始终公开。保护对象仅是作者模拟应用中绑定的实例数值/答案。公开教材本身可自由查阅，因此学生若看到完整原题/可检索来源，通常可直接得到目标：这是显式可见性边界，不声称真正版权秘密或真实教学需求。
4名不同持续身份学生；联盟上限k=3；全部主联盟对完整目标未授权，局部子问题可请求。实际动作=回答+接收者+轮次；每人一个请求，轮次1–4。同一请求最多一个答案，允许跳过，不允许把两种正确解法同时交付。攻击者看到其控制身份的真实query/reply及公开背景，不看评测真值或未交付内容。契约与原题/来源仅评测端；查询不得自带隐藏数值。
候选均冻结为对应子请求正确答案；空答/提醒不是答对。预算一致：4请求/4释放，每人1请求，UTF8字节预算取4倍最大候选且个人限最大候选，不绑定；不估计模型Token、不运行检索/生成。无需优化器/需求预测器。

## 关系与独立判据
contracts.json冻结变量、单位绑定、条件、公开函数、目标、候选与规则。精确有理数用于教材名义数值；T04冷功率按整瓦区间观察，不能逆用约411W作为精确411方程；其他派生平方/名义未舍入量明确标为研究者的计算表示，并保留原教材舍入说明。
先枚举每请求 skip/一种答案的全部合法组合；用原ExactK3与独立set固定点核对所有联盟闭包。最小不安全=合法且危险、删去任一动作后安全。另用独立SymPy1.13.1子进程（旧.venv，不安装依赖）验证数学含义：Groebner余式为0证明目标唯一；不唯一需给出满足已知观察但目标不同的正有理数世界。rounded观察按区间，不作精确等式。找不到证明/反模型均UNKNOWN，不计为安全。枚举布尔规则相符不能代替数学证据。
反模型搜索预注册顺序：单变量固定为原值乘1/2、2、1+1/100000、1-1/100000、加减1，再求解其余变量；自由变量取名义原值或上述固定比例；只接受满足所有等式、正值与前提的可核验解。此有限搜索只找反例，不用于证明唯一。评测真值仅证明器可见，检测器仅接收冻结的公共关系和已交付知识。
对三人见证逐一验证三人恢复、每对不恢复、每个人累积视图不恢复；若仅Horn安全而数学未知则不能声称三人独有风险。正常安全释放、全部联盟显式授权、全原题可见分别作为对照。T11四人完整恢复不算k<=3违规。

## 结构审查与停止
报告原始动作及按等价信息归并后的结构；相同请求更详细但同样正确的答案作为信息支配选择另行标注，不删除原结果。检查二类互斥、单一三元、独立分组、一般计数/固定规则，以及来源支持的重叠限制/解法选择。存在高阶集合或重叠不代表算法创新；来源无真实不同权限时不编造。
全量保留12题、失败、UNKNOWN，不调题/域/规则求更好结果。冻结后只执行一次主检查，脚本错误修复必须在执行日志记载。完成后停止，不进入算法比较/模型训练/扩量。
''')
    paths=[OUT/'contracts.json',OUT/'PROTOCOL.md',OUT/'selected_sources.json',OUT/'selection_register.json']
    paths+=sorted((PROJECT_ROOT/'experiments/c2rag_real_source_structure_20261027_01').glob('*.py'))
    save('freeze.json',{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
                        'sha256':{str(p.relative_to(PROJECT_ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                        'before_structure_evaluation':True})
    print('Frozen 12 source tasks, no structure evaluation performed.')


if __name__=='__main__':main()
