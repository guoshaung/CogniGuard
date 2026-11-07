# HSW-AUDIT-EPOCH-01 冻结协议

本轮为真实作者材料＋模拟交付生命周期。准确机器方案、任务全集及输入SHA见run01/CONFIG_FROZEN.json、TASKS_FROZEN.json和freeze.json。所有正式生成前固定，不从结果改阈值、密钥、样本或攻击器。上限96次尝试（低于用户256），30000生成Token、累计模型墙钟7200秒、输出3GiB；无重试、付费、GPU或下载模型。达到任一上限标剩余NOT_RUN，不补齐。

工作树codex/hsw-st从d019基线新建，原共享目录的未提交研究变更未擅自迁入。源码/模型/环境和冻结历史只读共享，缓存、日志、临时、数据库、DPAPI密钥及结果全位于本树。原始正文优先8个实际OpenStax历史CC-BY4章节片段；2DEV/2CAL/4TEST，CAL不发行。原准备稿中的单位换算/表述问题另存、事前选择原作者相邻合法span；不改旧文件、不修补模型输出。

S1为18项真实库/SQLite软件夹具，不算水印效果。S2开发2篇×3接收方×2周期，C0/官方Greenlist/官方MPAC三臂；先同一S01三臂最小探针，再执行未启动DEV槽。S3技术合格方法自动进入4个预留TEST章节×2接收方×2周期三臂的有限矩阵；这是更低矩阵，不要求耗尽最多8×4×2×3。两个CAL原文可各作一次未标记改写但不放进发行库；另做一个直接从S01可信原文产生R04版本并登记parent的单例。代码、参数、种子及任务只能按冻结表读取。

所有改写从作者正文独立生成，不让Qwen回答题目，不从另一实验臂继续改写。相同canonicalpair共享采样seed，各方法只改变指定嵌入；Greenlist和MPAC不是相同PRF，差异按完整方法而非单因素因果解释。模型为原有7BQ4 CPU，不冒充云FP32。Tokenizer取完整合法ID域与真实152064输出头分别核验，EOS保留，A公开字节为硬门槛，BPE重分词B另记而不替换公开分数。

公开检测器仅读取可疑文本和预允许候选登记/历史检测材料。不得提供真实source、issue、recipient、epoch或生成轨迹。所有原文/无水印及带水印版本均供强指纹索引。先来源/交付关联，再独立查询asof150许可；换钥不改旧身份，撤销不抹水印，受损密钥报告KEY_COMPROMISED，原样私下转发不能认定新接收人。

完整身份必须issue_id及recipient/content_version/epoch一致，不把来源相同当接收方正确。全部预登记槽保留PASS/FAIL/UNKNOWN/技术失败/NOT_RUN，拒识不是成功。作者质量审核先锁定，再揭示分数，不冒充真人金标。多bit方法只使用独立提取top1码；不将真实gold message喂给解码器。官方低层API中的固定dummyBER不参与解码/选择，已用0/1两dummy验证提取不变。

整体误报目标1%，但仅2个CAL独立章节。按预定rank最大统计量，当rank超样本数，主阈值∞、拒识并写目标未认证。另列完整排名/未认证nominal Bonferroni诊断，不把单keyz或比特准确率当全局归因正确。任何多key/epoch/窗口扫描都属于同一个查询家族。额外512nullkey压力仅DEV两个冻结查询，不是新增512接收方。TEST不能重选margin或阈值，小样本逐例，不制造独立性或显著性。

无模型攻击先做元数据删除、LF→CRLF、空白折叠和固定start/mid/end50/100/200Token；UTF8边界不合法记不可用，不换偏移。改写可行性最多4次既有不同模型；如有效强仍0就停攻击分支。任何方法失败不阻止其他无依赖工作。旧RQ2和其他研究任务不动。

输出工程COMPLETED/PARTIAL/EXTERNAL_BLOCKER与研究INTEGRATE_EXISTING/GAP_OBSERVED/INSUFFICIENT_EVIDENCE分开。只提交本轮安全文件到research-sync独立evidence分支并建draftPR，不改CogniGuard origin，不自动合并。
