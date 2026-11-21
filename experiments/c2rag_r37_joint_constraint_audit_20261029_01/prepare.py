"""Freeze verification scope, not a fictitious preregistration of unseen outcomes."""
import time

from experiments.c2rag_r37_joint_constraint_audit_20261029_01.common import (
    OUT, PROJECT_ROOT, R32, R35, sha, write,
)


def main():
    OUT.mkdir(exist_ok=False)
    paths = list(R32.glob('*.md')) + [R32/'decision.json', R32/'evidence.tar.gz']
    for name in ['banks.json', 'replays.json', 'evaluated_replays.json', 'oracles.json',
                 'independent_verification.json', 'PROTOCOL.md', 'RESULT.md',
                 'NOVELTY_AND_DECISION.md', 'FAILURES_AND_LIMITATIONS.md', 'complete_results.csv',
                 'snapshot/engines.py', 'snapshot/reference.py']:
        paths.append(R35/name)
    for directory, names in [
        ('c2rag_real_source_structure_20261027_01', ['contracts.json','STRUCTURE_AUDIT.md','TASKS_AND_SOURCES.md','PROTOCOL.md']),
        ('c2rag_r34_20261028_02', ['PROTOCOL.md','METHOD_COMPARISON.md','FAILURES.md','GLOBAL_UNION_REDUCTION.md','decision.json']),
        ('c2rag_r36_authorization_audit_20261029_01', ['PROTOCOL.md','RESULT.md','decision.json','VERIFICATION.json']),
    ]:
        paths.extend(R35.parent/directory/n for n in names)
    paths.extend(PROJECT_ROOT/'experiments'/p for p in [
        'c2rag_r34_20261028_02/planner.py', 'c2rag_r35_20261029_01/core.py',
        'c2rag_r35_20261029_01/prepare.py'])
    write('PROTOCOL.md', '''# R37 有界分析与既有证据复核协议

EXPLORATORY，2026-10-29。唯一问题：来源支持的教学需求是否呈现超出二类多数、且未被强简单基线/成熟优化解释的长期释放约束？
这是已见R32–R36的回顾审计及数学证书核验，不是新的未见数据实验预注册。已先完整阅读R32报告/协议、原始归档结构及失败记录；后续强基线负结果也已知。不得声称盲测或新增独立资产。

## 固定范围

以research-sync main 3615483a9ac0dc0fc07853278371d5a83a0dc599为接续版本。R32报告/协议/决定与固定远端逐文本核对；归档Git blob SHA1必须等于0bd48b1815c376bcf5e304dd442aac83e8425d40。
读取全部510条R32旧方法轨迹、102条旧请求及独立评分；按实际交付文本重算效用、字节、联盟视图与风险，核对原OPT证书与多数公式。不重新运行A1/A2，不调参数，不运行旧研究队列。
最小数学案例固定复用R35第一个同时含重叠二元/三元最小支持的契约L3：ab→TARGET、bcd→TARGET；不是新设计的教学数据。核验全部16个观察子集和全部256条四轮请求流，不按方法表现挑流。
仅重计旧NoGate、Counter4、G-Shared，以及uniform/error0的Simple、A2、B-SAA、MenuRecourse实际交付；同一方法旧请求256×4，保持原r0,r1,r2,r0、权限、候选和124字节预算。各流离线值用16个交付/空答计划独立复核（4096计划），不运行新控制器/MILP。
手算展示L3的b,a,c,d（长期冲突）和b,c,d,a（三人前缀），均已在旧完整枚举中；它们不是新独立实验，也不以表现挑选资产。三人前缀使用原前三个不同接收者；不改身份/权限，不引入未授权教师材料。
Boolean独立评分器枚举所有满足公开规则的32个世界；观察者只读实际query/reply，隐藏名义TARGET不能用于恢复判断。无模型输出格式问题。无匹配/冲突应UNKNOWN并停止，不填安全。
核验计时600秒wall上限，超时/断言保留INCOMPLETE，不扩预算；计时从audit入口开始。不新增合成资产、seed或主方法运行。只新增独立定义/结果目录，不改历史、生产或Stage1-C真值。

## 实验前置门槛与停止

只有出现未被旧R34/R35排除、且来源或明确SYNTHETIC合同支持的独立机制缺口，才值得另立少量性能实验。超过二类多数、某贪心失败、存在三元禁集，均不单独通过此门槛。
本轮已有L3属于已被强菜单/MILP解释的类，故这里只做证书复核，不启动新性能实验；新算法增益记NOT_TESTED，已有数据明确标REUSED。真实任务代表性及机构授权依R36保留缺口。
保留全部256流及所有无差异/退步计数，不用重复流扩资产分母。CPU/模型Token/GPU/付费API/训练/新教育数据下载均不发生；用实际UTF8字节。

## 数学与撞车审查

建立有限知识/公开Horn规则、按时间/接收者/候选定义的动作、持续视图、逐目标未授权联盟及任务效用模型。区分风险判断、离线优化与非预知在线控制。
明确二元禁集=图独立集，三元及以上=弱超图独立集（禁止整条边，不是强独立集每边至多一项）；回答候选和预算加入标准0-1整数规划。不声称约化后已多项式求解，也不把NP难度当创新。
三人能暴露PairExact遗漏的恢复，但在三名实际无权接收者均可合谋、相同候选、单调风险和非绑定预算下，并不自动破坏全局并集和菜单充分性。
分析未来真值/分布/预测包的不同信息假设；不得将Offline差距或逐场景全知的乐观上界当在线可实现算法收益。公开一手论文/官方求解文档只作查重，不下载新教育资料。

完成报告及脱敏同步后停止。没有自动训练、扩量、生产集成或新算法候选实现。
''')
    write('freeze.json', {'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                          'retrospective_not_unseen_preregistration': True,
                          'protocol_sha256': sha((OUT/'PROTOCOL.md').read_bytes()),
                          'sources': {p.relative_to(PROJECT_ROOT).as_posix(): sha(p.read_bytes()) for p in paths}})
    print('Frozen retrospective verification scope; no new algorithm experiment authorized by a positive gate.')


if __name__ == '__main__':
    main()
