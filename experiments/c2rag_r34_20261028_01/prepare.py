"""Freeze all definitions and streams before any method performance is produced."""
import itertools
import json
import random
import re
import shutil
from html.parser import HTMLParser
from experiments.c2rag_r34_20261028_01.common import *
from experiments.c2rag_r34_20261028_01.models import SPECS, worlds, evaluate

class Paragraphs(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.stack=[];self.buf=[];self.ident=''
    def handle_starttag(self,tag,attrs):
        if tag=='p':self.buf=[];self.ident=dict(attrs).get('id','');self.stack.append('p')
    def handle_data(self,data):
        if self.stack:self.buf.append(data)
    def handle_endtag(self,tag):
        if tag=='p' and self.stack:
            self.rows.append((self.ident,' '.join(' '.join(self.buf).split())));self.stack.pop()

def main():
    OUT.mkdir(exist_ok=True);assert not (OUT/'freeze.json').exists()
    banks=[];truth=[];sources=[];events=[];gold=[]
    for spec in SPECS:
        source=PROJECT_ROOT/'experiments/c2rag_r10_20261020_01/local_sources'/spec['page']
        raw=source.read_bytes();html=raw.decode('utf8');parser=Paragraphs();parser.feed(html)
        found=[{'locator':i,'text':t} for i,t in parser.rows if spec['phrase'].lower() in t.lower()]
        assert found,(spec['id'],'Source phrase unavailable')
        licenses=sorted(set(re.findall(r'https?://creativecommons.org/licenses/[^\s"<>]+',html)))
        assert any('by-nc-sa/4.0' in link for link in licenses),spec['id']
        book,page=spec['page'][:-5].split('__',1)
        sources.append({'asset':spec['id'],'url':f'https://openstax.org/books/{book}/pages/{page}',
            'cached_path':source.relative_to(PROJECT_ROOT).as_posix(),'sha256':sha(raw),'attribution':'OpenStax',
            'license':'CC BY-NC-SA 4.0 (cached footer)', 'license_links':licenses,'paragraphs':found[:2],
            'distinction':'Public background only; original synthetic domains, nominal values, requests and authorization; S06 Boolean law authored, not quoted biology'})
        ws=worlds(spec);nom=evaluate(spec,spec['nominal']);obs=list(spec['observations']);J=len(obs)
        target=tuple(nom[f] for f in spec['target']);minimal=[];table=[]
        for bits in range(1<<J):
            compatible=[i for i,w in enumerate(ws) if all(w[spec['observations'][o]]==nom[spec['observations'][o]] for j,o in enumerate(obs) if bits&(1<<j))]
            unique=all(tuple(ws[i][f] for f in spec['target'])==target for i in compatible)
            assert compatible
            table.append({'bits':bits,'compatible_worlds':compatible,'recover':unique,
                'alternative_world':next((i for i in compatible if tuple(ws[i][f] for f in spec['target'])!=target),None)})
            if unique and not any(m&bits==m for m in minimal):minimal.append(bits)
        # Numeric ordering has every proper submask before its superset.
        rules=[([obs[j] for j in range(J) if m&(1<<j)],'TARGET') for m in minimal]
        authorized=[m for m in range(1,16) if m.bit_count()<=3 and m&8]
        case={'n':4,'facts':obs+['TARGET'],'public':[],'rules':rules,'assets':[{'target':'TARGET','authorized':authorized}]}
        queries=[]
        for qi,(request,variants) in enumerate(spec['queries']):
            answers=[]
            for ai,atoms in enumerate(variants):
                values={o:{'value':nom[spec['observations'][o]],'unit':spec['units'][o]} for o in atoms}
                reply=json.dumps(values,ensure_ascii=False,sort_keys=True,separators=(',',':'))
                answers.append({'id':f'{spec["id"]}-Q{qi}-A{ai}','facts':atoms,'reply':reply,'correct':True})
            answers.sort(key=lambda a:(len(a['reply'].encode('utf8')),a['id']))
            queries.append({'id':qi,'request':request,'answers':answers,'question_family':f'{spec["id"]}-Q{qi}'})
        bank={'id':spec['id'],'title':spec['title'],'subject':spec['subject'],'family':spec['family'],'split':spec['split'],
            'source_type':'licensed background + SYNTHETIC instance','trusted_recipient':3,
            'authorization':'Coalition union entitlement: contains authorized advanced learner r3 => permitted; all other coalitions unauthorized. Not strict least-clearance noninterference.',
            'case':case,'observations':obs,'queries':queries,'budget_bytes':8*max(len(a['reply'].encode('utf8')) for q in queries for a in q['answers']),
            'recipient_schedule':[0,1,2,3,0,1,2,3],'query_budget':8,'per_recipient_query_budget':2,
            'public_background':{'equations':spec['equations'],'domains':spec['variables'],'same_instance_across_questions':True,
                'source_laws_public':True,'nominal_source_instance_public':False,'query_type_set':list(range(len(queries)))}}
        banks.append(bank)
        truth.append({'id':spec['id'],'spec':spec,'worlds':ws,'nominal':nom,'target_fields':spec['target'],
            'table':table,'minimal_obs_sets':[[obs[j] for j in range(J) if m&(1<<j)] for m in minimal]})
        K=len(queries)
        for family in ['uniform','biased']:
            for s in [0,1,2]:
                sid=f'{spec["id"]}-{family}-{s}';rng=random.Random(seed(sid,'demand'));mode='U' if family=='uniform' else rng.randrange(K)
                weights=[1/K]*K if mode=='U' else [.7 if i==mode else .3/(K-1) for i in range(K)]
                qs=rng.choices(range(K),weights=weights,k=8)
                seq=[{'step':t,'q':q,'recipient':t%4,'asset_id':spec['id'],'question_id':f'{spec["id"]}-Q{q}'} for t,q in enumerate(qs)]
                hint_rng=random.Random(seed(sid,'hint'));alphabet=['U',*range(K)]
                hints={'none':hint_rng.choice(alphabet)}
                hints['strong']=mode if hint_rng.random()<.9 else hint_rng.choice(alphabet)
                hints['misleading']=hint_rng.choice([x for x in alphabet if x!=mode])
                events.append({'id':sid,'asset':spec['id'],'family':family,'seed':s,'events':seq,'hints':hints})
                gold.append({'stream':sid,'latent_mode':mode,'distribution':weights})
    write('public/banks.json',banks);write('private/truth.json',truth);write('events.json',events)
    write('private/generation_gold.json',gold);write('sources.json',sources)
    write('HISTORY_READ_AUDIT.md',"""# 历史证据接续

Latest inspected main a9fe2bdcd4b055236c6e1e37abeb9f85dbfec73f (2026-10-28).
Read latest four remote reports and local protocols/data/planners. Local and remote
structure/cross-question/imperfect reports match normalized text. R32 differs only
in trailing newline (splitlines diff empty); remote saved historical_remote/.
R32 G340/A1O357/A2O=OPT442, two-class majority, no new evidence here.
real-source:12 tasks but T05–08 one instance; small overlapping fixed rules.
cross-question:Reset=Shared=8/16, Reset single-person leak, Shared=OPT8.
imperfect:64 streams/two structures; strong Simple371>A2365, OPT397;
no Simple-Oracle; causal forecast boundary repaired, uniform first cases not causal
hint gains. Those failures retained; no old results changed/repackaged.
R34 removes old all-unauthorized/fresh-receiver shortcut; same ExactK3 semantics.
""")
    write('PROTOCOL.md',"""# C²-RAG R34 冻结协议 · EXPLORATORY

## 问题与样本
检验强固定菜单Simple是否仍接近OPT。六份独立任务族，不是换数字/身份的六份复制品。
S01弹簧比值、S02包裹功差、S03理想气体乘除为结构开发组；S04稀释和比、S05二次式对称量、S06酶实验布尔合取为作者结构留出组。
留出不是盲测/独立标注：同一研究者设计；方法定义完全相同、冻结后不调参。
S02是已见T06结构的合成域扩展，只作开发，非新增未见证据。S01是旧二选一同构负对照。
其他六实例的结构是否同构必须另审计，不预设6种新结构。公开OpenStax公式不保密。
本批只检验有限、明确列出的参数世界；连续域、自然语言、测量噪声、拒答侧信道不在判据内。
S06是作者定义布尔实验，不声称教材真实酶作用可化成该逻辑。合格覆盖限于这些模型。

## 冻结和来源
public/banks.json、private/truth.json、sources.json、events.json、gold、代码及ExactK3/set参考快照在freeze.json哈希冻结。
在任何方法表现之前冻结，不挑选/改难度/改种子。仅一次完整主执行；工程异常保存failed并另编号，不修改契约。
每实例固定完整目标，任一未授权联盟能完全恢复即违规；另外报告目标组成字段和原始参数恢复。
有限世界包括反事实参数，不向观察者透露名义完整输入。观察者知道有限域、公开方程、资产关联、收到的query/reply和身份。
候选是授权检索端的正确结构化答案，观察者只能看到实际交付答案；不运行检索/生成模型。
目标公式/物理规律保持公开；只保护模拟实例值/元组。教师私有资料与真实受限版权均未使用。

## 请求、权限、预算
每资产uniform/biased各seed0,1,2，共6流8请求=48任务；总36流288任务。
种子SHA256([20261028,stream,channel])前16hex；均匀q iid或先均匀选主q，再以.7主类/.3其余抽取；需求不响应控制行为。
四接收者r0..r3、固定0,1,2,3重复两遍，跨题同一实例实际交付历史持续；不靠复制身份作独立资产。
r3模拟已获完整目标授权；联盟含r3即具合法union entitlement，其余联盟均无目标授权。
这是明确的联盟联合权利政策，非“所有成员必须有权”；直接交给无权单人仍判越权。
所有主方法检查全部k<=3联盟；独立另报恰1/2/3和最小见证。常规预算8请求、每人2，字节8*最长候选；均不绑定。
拒答为空文本/0字节/0效用；合法正确候选1；同题两种答案任务效用相当。实际候选以UTF8字节、ID排，无语义评分伪装。

## 方法（完全冻结，不开发新防御）
M0 NoGate每次最短正确答案。M1 G-Shared安全正确候选优先，字节/ID平局。
M2 Fixed Rules从空历史枚举可全局兼容固定菜单，以可回答题型最多、总字节少、菜单ID小预选，不看实际需求。
M3 Simple-Prior：同固定菜单类，每步重选；未来32情景iid均匀。
M4 Simple-Forecast：同菜单，未来32情景Bayes后验。M5 A2-Forecast：当前各安全候选含EMPTY，后续G逐步rollout，非情景OPT。
M6 Simple-Oracle只替换为真实有序后缀（32份同情景）；M7 A2-Oracle同样；M8独立认证完整未来OPT。
菜单每题型选择一个原正确候选或EMPTY；对r3统一自由G，避免用忽略异质授权的弱菜单。
Simple安全性：在当前真实状态后，枚举固定未来身份日程中该菜单所有可能题型的联盟可见合并；逐联盟恰当权限验证。
重复接收者允许累积，任一联盟可容纳的distinct菜单知识数受该联盟剩余请求数限制；不沿用旧新身份捷径。
此兼容性对未知未来保守，即使Oracle也不改变方法类。必须额外报告保守性/菜单限制造成的差距。
预登记诊断StaticMenu-Oracle：真实全部请求上穷举同固定菜单类最佳安全计划（r3自由），不强求所有可能未来安全。
它是离线静态参照，不是在线候选新算法；若它已=OPT，不把现有Simple的策略差距当作结构复杂性证明。
所有打分32*当前效用+32情景后续效用之和；排序score大、即时效用大、当前字节少、当前ID小，Simple再菜单ID元组小。
G rollout顺序和实际完全相同。未来recipients日程公开；只有query types被预测。

## 预测、误差与因果归因
条件none/strong/misleading；uniform家族的latent只有U，biased latent为各主类。
none提示与mode独立；strong以.9给正确mode否则在U+各类均匀抽；misleading强制异mode但预测器仍假设.9。
Bayes只读公开family、hint和当前prefix，逐流/条件独立stdin子进程，收到当前输出后才给下一前缀，禁止读证据文件/联网。
32情景每次先抽latent，再抽剩余q；各条件相同随机数种子。Prior不看family/hint/prefix。
strong-none反映新增提示效果，misleading-none为失配损失；同信息A2-Simple为规划差异。
预测Brier/logloss/准确率只在评分端读真实下一q；uniform条件一致作为阴性对照，不误称提示收益。
Oracle差距只是理想信息下的策略不足；在线-OPT差距不能当成可实现算法增益。

## 独立真值、控制和消融
公开有限域精确有理数/布尔枚举，生成所有观察子集的最小目标恢复支持，编译Horn规则供原ExactK3。
独立验证器重新按另写的方程/真值函数计算每个world及每个subset反世界，按实际JSON文本和单位重建视图。
ExactK3、set参考、直接世界消元三者逐前缀交叉核验；UNKNOWN保留，不能算安全；不靠LLM格式失败。
主数据不另行增加攻击负载。对NoGate实际交付提取直接/单题/跨题、同人/多人最小支持，检查删任一动作/拆题均不恢复。
预登记控制：S01二选一；M2固定禁集；全部授权；名义原题完全公开（TARGET公知+全授权，安全问题消失）。
另对每条NoGate实际轨迹计算k1/2/3威胁边界与全未授权权限对照；它们不是新独立资产/方法获胜样本。
同一query重复与跨query互补均保留；不保证随机流含每种组合，缺失明确报告，不补挑流。

## OPT、预算和停止
主OPT前缀DFS遍历全部合法候选计划，只剪去已经不安全的前缀；最多3^8=6561完整计划（实际按query分支数）。
独立OPT用笛卡尔积穷举全部计划、实际字段/世界过滤，目标完成数最大、字节最少、答案ID序列最小；未完成不标OPT。
每流主方法+OPT CPU60秒，独立穷举CPU60秒；主执行总CPU1800秒、独立验证1800秒。不事后扩预算。
全流程无模型、GPU、付费API、训练、新数据下载或生产修改。主执行一次，所有无差异、Simple>A2、UNKNOWN、失败保留。
输出逐资产/结构/方法和结构留出分层；独立资产为主单位，36流/多方法不冒充36个资产。不凭6个作者模型声称总体显著性。
本轮只完成R34及同步后停止。决策ANALYZE/PIVOT/PROCEED/STOP依实测；即使差距正也先排除简单菜单解释，不实现新候选。
""")
    (OUT/'snapshot').mkdir(exist_ok=True)
    for n in ['engines.py','reference.py']:shutil.copyfile(BASE/n,OUT/'snapshot'/n)
    files={p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file()}
    code={p.name:sha(p.read_bytes()) for p in SOURCE.glob('*.py')}
    write('freeze.json',{'phase':'before any method performance','created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sha256':files,'code_sha256':code,'assets':6,'streams':36,'requests':288})
    print('Frozen: six assets, 36 streams, 288 requests; method outcomes not evaluated')

if __name__=='__main__':main()
