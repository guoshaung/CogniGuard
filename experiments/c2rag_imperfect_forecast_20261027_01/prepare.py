import itertools
import json
import random
from datetime import datetime,timezone
from experiments.c2rag_imperfect_forecast_20261027_01.common import *


def draw(rng,prob):
    u=rng.random();s=0
    for i,p in enumerate(prob):
        s+=p
        if u<s:return i
    return len(prob)-1


def main():
    deadline();old=RESULTS_DIR/'c2rag_real_source_structure_20261027_01'
    docs=read('prior_documents.json')
    # Compare pinned API mirrors to normalized local documents and original archived inputs.
    for d in docs:
        b=d['content'].encode('utf8')
        assert __import__('hashlib').sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==d['sha']
    r32=old/'r32_evidence'
    receipt=json.loads(next(d['content'] for d in docs if d['label']=='r32' and d['name']=='evidence_receipt.json'))
    assert sha((r32/'evidence.tar.gz').read_bytes())==receipt['archive_sha256']
    sm=json.loads(next(d['content'] for d in docs if d['label']=='structure' and d['name']=='UPLOAD_MANIFEST.json'))
    assert sha((old/'contracts.json').read_bytes())==sm['sha256']['contracts.json']
    history=RESULTS_DIR/'c2rag_cross_question_history_20261027_02'
    hm=json.loads(next(d['content'] for d in docs if d['label']=='history' and d['name']=='UPLOAD_MANIFEST.json'))
    for n in ['instance.json','replay.json']:
        assert sha((history/n).read_bytes())==hm['archive_members_raw_sha256'][n]
        write('regression/'+n,json.loads((history/n).read_text(encoding='utf8')))
    kin=next(x for x in json.loads((r32/'inputs/assets.json').read_text(encoding='utf8')) if x['id']=='kinetic')
    t06=next(x for x in json.loads((old/'contracts.json').read_text(encoding='utf8')) if x['task_id']=='T06')
    banks={}
    for name,raw in [('kinetic',kin),('T06',t06)]:
        if name=='kinetic':
            queries=[{'query':q['query'],'answers':[{'id':f'kinetic-q{q["qid"]}','reply':q['answer'],'facts':q['facts']}]} for q in raw['questions']]
            case={'n':8,'facts':raw['facts'],'public':raw['public'],'rules':raw['rules'],
                  'assets':[{'target':raw['target'],'authorized':[]}]}
        else:
            queries=[{'query':q['query'],'answers':[{'id':a['action_id'],'reply':a['reply'],'facts':a['reveals']} for a in raw['actions'] if a['request_id']==q['request_id']]} for q in raw['requests']]
            case={k:raw[k] for k in ['facts','public','rules','assets']}|{'n':8}
        for q in queries:
            q['answers'].append({'id':'EMPTY','reply':'','facts':[]})
            q['answers'].sort(key=lambda a:(-int(bool(a['reply'])),len(a['reply'].encode('utf8')),a['id']))
        maximum=max(len(a['reply'].encode('utf8')) for q in queries for a in q['answers'])
        banks[name]={'queries':queries,'case':case,'source_contract':raw,'budget_bytes':maximum*8,'per_recipient_bytes':maximum}
    write('public/banks.json',banks)
    model={'label':'SYNTHETIC','length':8,'scenarios':32,'bias_probability':0.7,
           'hint_alphabet':'U plus all dominant question-type modes','hint_mix':{'none':0,'weak':0.5,'strong':0.9,'misleading':0.9},
           'visible':'family, hint, prefix INCLUDING current arrived question; not future requests, latent mode, actual RNG seeds or OPT',
           'family_public':True}
    write('public/model.json',model)
    streams=[];gold=[];forecast_inputs=[]
    for structure,bank in banks.items():
        k=len(bank['queries']);modes=['U']+list(range(k))
        for family in ['uniform','biased']:
            for index in range(16):
                sid=f'{structure}-{family}-{index:02d}'
                mode_rng=random.Random(seed(sid,'latent'))
                hidden='U' if family=='uniform' else mode_rng.randrange(k)
                dist=[1/k]*k if hidden=='U' else [0.7 if q==hidden else 0.3/(k-1) for q in range(k)]
                request_rng=random.Random(seed(sid,'requests'))
                actual=[draw(request_rng,dist) for _ in range(8)]
                hints={}
                for condition in ['none','weak','strong','misleading']:
                    rng=random.Random(seed(sid,'hint',condition))
                    if condition=='misleading':h=rng.choice([m for m in modes if m!=hidden])
                    else:h=hidden if rng.random()<model['hint_mix'][condition] else rng.choice(modes)
                    hints[condition]=h
                    for t in range(8):
                        forecast_inputs.append({'stream_id':sid,'structure':structure,'family':family,'condition':condition,
                            'hint':h,'prefix':actual[:t+1],'step':t,'length':8,'types':k,
                            'scenario_seed':seed(sid,'scenario',t)})
                for t in range(8):
                    forecast_inputs.append({'stream_id':sid,'structure':structure,'family':family,'condition':'prior',
                       'hint':None,'prefix':[],'step':t,'length':8,'types':k,'scenario_seed':seed(sid,'scenario',t)})
                streams.append({'id':sid,'structure':structure,'family':family,'requests':[{'recipient':t,'qid':q} for t,q in enumerate(actual)]})
                gold.append({'stream_id':sid,'hidden_mode':hidden,'true_distribution':dist,'hints':hints,
                    'seeds':{'latent':seed(sid,'latent'),'requests':seed(sid,'requests'),
                             'hints':{c:seed(sid,'hint',c) for c in hints}}})
    write('events.json',streams);write('private/generation_gold.json',gold)
    write('public/forecast_inputs.json',forecast_inputs)
    (OUT/'snapshot').mkdir(exist_ok=True)
    for n in ['engines','reference']:
        (OUT/'snapshot'/f'{n}.py').open('xb').write((old/'snapshot'/f'{n}.py').read_bytes())
    write('PROTOCOL.md','''# 不完美预测下的前瞻释放 · 冻结协议

SYNTHETIC / EXPLORATORY；两个既有实例结构，不是新教育资产或真实教学预测。开始2026-10-27 13:27:59UTC，总时限120分钟（15:27:59UTC），准备/执行/验证/报告共用，超时INCOMPLETE，不调参、不扩量、不训练、模型/付费API/GPU0。

## 固定来源及任务
R32固定9bb10e557698fd8ded5aaf3534cc9ffe9c2456b1；结构审查固定6b60c733a8d7a751734521d4c93d23fb58410dad；跨题历史固定923b2766d82bb9a7e3b1679174d4e51915257d0a。已读各报告/协议与对应输入，归档字节哈希与固定提交清单相符；可读文本换行差异不误作数据变化。
仅R32 kinetic原m6kg/v4m/s两绑定回答、原完整输入目标；T06原两种功法与净力/推力功/位移子问，原F120N/f5N/d.8m输入三元组目标。公开规律/正值前提和模拟授权不变，结构各自单独状态，不混实例。原OpenStax CC BY-NC-SA4.0署名沿用；不称公开教材公式为秘密。
每结构32条流：uniform16，biased16，固定顺序kinetic/T06、uniform/biased、索引00–15。每流8请求，r0–r7各一次，k≤3完整目标均未授权，持久交付历史。正常答效用1、EMPTY效用0；只表示独立接收者的合成服务任务数，不是学习收益或新增信息量。每流总8请求、8交付上限、8×该结构最长回答字节，个人1请求/最长回答字节，均不绑定。

## 需求与提示模拟
所有seed=SHA256(20261027|streamID|channel)前64位，先latent再hint再独立requests随机流（生成调用顺序不影响独立rng）。uniform公开固定U模式、q类型均匀，biased隐藏主题在K题型均匀抽取，其概率.7其他均分.3。提示字母表U与K主题：none独立均匀；weak以.5采用真模式否则独立均匀；strong以.9采用真模式否则独立均匀；misleading从其他模式均匀抽取，但预测器按strong的似然更新。.5/.9不是预测准确率。公开family意味着uniform流提示和前缀不能增加需求预测能力；保留此阴性对照。
真实需求固定跨四条件。预测在当前请求已发生、下一请求发生前生成，visible prefix包含当前请求。预测器独立进程仅可读取public/model与public/forecast_inputs；没有hidden mode、真实后缀、真实生成种子、金标/OPT字段。按公开噪声模型做Bayes：family限定模式先验，hint似然与此前真实请求似然相乘。misleading故意错配。每步用独立scenario_seed抽32个后验模式和其未来顺序情景；无剩余时仍存32空情景。
同一stream/step所有条件和prior用共同随机数；uniform条件下32情景与prior逐字相同。prior只iid均匀，不读hint/前缀学习或family潜在相关性。none在biased上仍能通过前缀学习，不能当固定prior。Simple/A2在同条件逐字读取同一情景文件并保存其哈希。

## 方法与平局
当前候选均包括EMPTY。所有非空原答案正确。G-Shared选安全即时效用最大，平局字节短、ID小。A2-Forecast当前各安全候选（含EMPTY）得分=当前效用+32情景的后续安全G rollout均值；按预测顺序更新新接收者视图/非绑定预算，不用A1独立机会损失、不调用每情景离线OPT。A2-Oracle仅替换为真实有序后缀，理想参考。rollout状态不可变副本，不污染真实状态。
Simple枚举固定菜单：每题型选一个原正确候选或EMPTY（kinetic4/T06 24菜单）。兼容当前历史与当前候选，并对最多3个不同未来题型的全部组合用同安全判据验证（每个未来接收者仅一答，重复相同事实不会增加所需联盟人数，足够覆盖k≤3全部可能危险组合；若剩余人数更少则据此限制）。这保证菜单未来响应不能相互冲突。得分=当前效用+32同一情景的菜单可服务次数均值；忽略顺序，每步可重新选菜单；原N/C两种功法均保留。kinetic退化为两类事实预测计数。
Simple-Prior/A2-Prior使用固定iid均匀情景；Simple/A2其余相同。评分以32倍整数计算避免浮点平局；均按score大、即时效用大、当前字节小、当前ID字典序小。Simple再以菜单候选ID元组字典序小。安全G与Oracle相同平局。OPT精确所有合法候选计划，完整序列可见；按总效用大、总字节小、候选ID序列字典序小选代表。Oracle/OPT不参与同信息主比较。

## 核验与预算
复用冻结ExactK3和独立set闭包，运行适配仅缓存不可变视图的同义k≤3安全计算；实际选择逐步与原ExactK3核对，独立评分器按真实回答文本重建视图、预算、效用及所有≤3联盟。T06所有128字段子集另用精确方程/反世界核验，支持重复功法出现的新组合，不查旧最小禁集打分。跨题历史旧16请求只作只读回归，不作为增益负载或生产漏洞证据。
每流精确OPT最多3^8计划；独立set评分穷举全部计划复核，不完整不标OPT。预测质量在评测侧读取真实下一请求计算logloss/Brier/argmax准确率；控制器不可读取评分数据。完整记录候选评分、情景hash、实际交付和一次本地CPU/wall开销，不作系统性能承诺。
各阶段检查全局deadline。可在同配置预算内续跑未开始任务，已完成结果不覆盖；工程错误保留失败、修复及受影响范围，不挑最好重跑。任何语义/判据差异STOP/INCOMPLETE，不调整种子、lambda、题目、阈值或提示可靠度。

## 全量报告与案例
总64条独立合成流、512请求；多方法/4提示条件/32预测情景不是额外独立样本。分结构×分布×提示报告任务数、拒答、越权/UNKNOWN、配对deltaG、deltaPrior、A2−Simple、OPT差距、胜平负、预测质量和开销。保留所有G=OPT、退步、预测失败；不作总体教育外推或独立知识资产统计。默认不报置信区间。
案例在冻结stream顺序、条件none/weak/strong/misleading、方法Simple/A2顺序选第一项：Forecast>G；A2≠Simple；misleading Forecast<G。缺项写未出现，不造例。回答Q1未来信息价值与Q2同信息联合规划价值，条件性决策，不宣称创新。完成同步停止。
''')
    inputfiles=[OUT/'events.json',OUT/'private/generation_gold.json',OUT/'public/banks.json',OUT/'public/model.json',OUT/'public/forecast_inputs.json',OUT/'PROTOCOL.md',OUT/'prior_documents.json']
    inputfiles+=sorted((OUT/'snapshot').glob('*'))+sorted((OUT/'regression').glob('*'))+sorted(SOURCE.glob('*'))
    write('freeze.json',{'deadline_epoch':DEADLINE,'start_epoch':START,'sha256':{str(p.relative_to(PROJECT_ROOT)):sha(p.read_bytes()) for p in inputfiles if p.is_file()}})
    print('Frozen 64 streams and all forecast input prefixes; no method evaluated.')


if __name__=='__main__':main()
