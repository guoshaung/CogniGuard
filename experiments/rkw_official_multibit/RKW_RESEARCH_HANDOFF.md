# RKW 研究交接

**归档决定（2026-11-25）**　接受 c3574c2 的开发 STOP。RKW 暂时退出 CogniGuard 主论文核心贡献，保留为独立后续研究。历史源码、阶段协议、失败样本与数据继续保存在研究分支及其固定提交。水印扩量和学生训练到此收尾。这项决定针对现有证据与实现范围，论文中对其他训练式水印的判断仍开放。

**已验证的逻辑**　现有 CA-PD 内核可据见证计算联合边际风险。在两个开发夹具中，任一单块的边际收益为零，两个相关块一起使请求从允许变为拒绝，实际改变了预算为两块时的分配结果。**仍待验证的效果**是风险感知冗余能否提高真实传播后的来源恢复，在 BGE+NLI 之上增加可用证据并改善治理效用。两组分配都未达到载体的初始嵌入门槛，策略之间的传播差异无实验估计。 [最新 STOP](https://github.com/guoshaung/CogniGuard/blob/c3574c2/experiments/rkw_official_multibit/witness_blocks/RESULT.md) · [实际判定差](https://github.com/guoshaung/CogniGuard/blob/c3574c2/experiments/rkw_official_multibit/witness_blocks/risk_results.json)

## 1. 数学模型与归因口径

令 $s$ 表示稳定的资产来源，$u$ 表示登记知识单元，$r$ 表示一次发行。同源发行共享 $c_s$。检测侧分别评价资产集合、来源–单元对，以及有可信证据支撑的传播继承。发行身份可单独计量。纯文本提供码字和内容兼容证据，实际持有者及传播事件需要可信上下文。pe-1.0 通过 RuleVerifier 将核验与入账分开，可信事件预算抵扣来自受信事件。 [形式模型](https://github.com/guoshaung/CogniGuard/blob/06d9259/experiments/rkw_risk_aware/FORMAL_MODEL.md) · [pe-1.0 接口](https://github.com/guoshaung/CogniGuard/tree/eec96b6/cogniguard/provenance)

观测文本为 $Y=T_H\circ\cdots\circ T_1(X_w)$。等先验二源分类错误率下界为 $(1-\mathrm{TV}(P_1,P_2))/2$。若两种来源的输出分布相同，最优错误率为 $1/2$。完整复制知识与码字也能使真实继承与复制得到同一观测。登记 $M$ 个来源至少需要 $\lceil\log_2 M\rceil$ 个身份位。实验区分原始载荷、可观测位与传播后的有效可区分信息。 [边界与容量](https://github.com/guoshaung/CogniGuard/tree/06d9259/experiments/rkw_risk_aware)

以符合保真条件的表达集定义各编码位置，开发集按操作估计 $Q_{j,T}(\hat z\mid z)$。符号结果分正确、替换、擦除和冲突。未改变知识的输出也可能擦除全部码字。按位置相加的对数似然属于条件独立近似，需检查共失效和窗口重叠。预算同时记录编码位置、编辑距离、长度、载荷和调用成本。检测使用最终文本和登记信息，理想上界使用金标仅限评分。 [原始方法与预注册](https://github.com/guoshaung/CogniGuard/blob/06d9259/experiments/rkw_risk_aware/PREREG.md) · [信道数据](https://github.com/guoshaung/CogniGuard/tree/06d9259/experiments/rkw_risk_aware/results)

### CA-PD 风险分配

令 $A_k(q,K)\in\{0,1\}$ 为权限已给定、账本为 $K$、联盟上限为 $k$ 时请求 $q$ 的放行判定。反事实补入经核验的持有证据 $D$，组合收益为

$$
G(D;K)=\mathbb E_q[\omega(q)(A_k(q,K)-A_k(q,K\oplus D))].
$$

单块权重 $r_i$ 来自单块反事实对请求、潜在持有者的期望。在线性近似中，在 $\sum_i b_i\le B$ 下最大化 $\sum_i r_i p_i(b_i)$，其中 $p_i$ 由开发传播估计。联合方案最大化 $\mathbb E_{D\sim P(D\mid b)}G(D;K)$，另计误确认的误拒损失。多个块的收益可能互补，且传播失效可能相关。实验需冻结请求分布、当前账本和预算，编码仅应用于已授权披露的内容。

实测固定 $k=2$、$f=0$、见证 $\{0,1,3\}$，请求单元 3。两个主题均满足 $G(\{0\})=G(\{1\})=G(\{2\})=0$，$G(\{0,1\})=1$，其余两对为零。均匀组按位置选 [0,2]，风险组选 [0,1]。早期 R0 检查还表明，已有一个相关单元时另一个的边际收益升为 1，联盟上限改为 1 时该夹具效应消失。以上是既有内核上的合成反事实。真实链的 $p_i$、收益分布、联合分配相对存活率分配的增量仍缺数据。 [早期 R0 夹具](https://github.com/guoshaung/CogniGuard/blob/06d9259/experiments/rkw_risk_aware/results/risk_checks.json) · [现行夹具代码](https://github.com/guoshaung/CogniGuard/blob/c3574c2/experiments/rkw_official_multibit/witness_blocks/risk.py)

## 2. 历史路线、基线与失败证据

- **HSW R35、R37N、R39。** R35 按知识修改风险调节 KGW 偏置，12 篇新输出为 10 PASS、1 FAIL、1 UNKNOWN，检出及联合成功均为 3/12，未达推进线。R37N 授权移交仍为 ANALYZE，100 token 片段 9/30→12/30 的区间含零。R39 使用逐资源 KGW 密钥，全文按预分配密钥检出 30/30，起始 50 token 唯一正确定位 2/30，MinHash 为 24/30，留出任一候选误报均为 3/117。R39 的优越性路线维持 STOP。 [R35](https://github.com/guoshaung/research-sync/blob/1b83872/CG/experiments/hsw_selective_r35_20261103/execution/RESULT.md) · [R37N](https://github.com/guoshaung/research-sync/blob/ee68a9d/CG/experiments/20261103-hsw-r37n-necessity/RESULT.md) · [R39](https://github.com/guoshaung/research-sync/blob/c882227/CG/experiments/20261103-hsw-r39-two-signals/recovery_20261104/RESULT.md)
- **CertInsert、KOSW、AFK。** CertInsert 与 KGW、Unigram、PostMark 旧对照主要评价存在性检测与保真。集成历史审计记录 EVAL-04 压缩后 CertInsert 检出 2.3%、KGW 27%。KOSW 几何探路的容量中位估计为 207.75 句，门槛为至多 10 句。AFK 锚点书写形式的有效证据为 0.64–0.79 bit，门槛为至少 7 bit。两项均停在载体可行性。 [历史审计与实验索引](https://github.com/guoshaung/CogniGuard/blob/0684a77/docs/integration/RKW_REVIEW_20261124.md)
- **首轮公开前缀、KBPW、Gate W0。** 首轮前缀编码发行人，来源来自内容检索。KBPW M1 编码发行，M2/M3 编码发行–事实，M3 用预测存活与显著性选位。12 来源、24 次发行、180 个试点端点中，各标记臂恢复的 28 个发行标签均来自转发或截断控制。模型摘要与两档改写实测均为零，理想可见码字上界分别为 0/53、4/54、3/54。主要损失来自码字消失。Gate W0 的 382 次带标末五词观察均裁掉句首载体。七类反例保存全删、部分删、残留复制、混合、事实不一致、同事实不同发行与独立同知识。 [初版试点](https://github.com/guoshaung/CogniGuard/blob/156428f/experiments/hsw_provenance/PILOT_RESULTS.md) · [KBPW 数学定义、输出和标签](https://github.com/guoshaung/CogniGuard/tree/065bb82/experiments/hsw_provenance_next) · [结构审计](https://github.com/guoshaung/CogniGuard/tree/631409e/experiments/gate_w0_real/closeout)
- **Chronology。** 按论文重实现的 Llama 3.2 1B 在偏置 2 下单轮唯一完整历史为 5/6，后续两条链第二及第三轮均为 0/2。原附件仅有图和图注。其评估对象是协作式参与历史。 [Chronology 诊断](https://github.com/guoshaung/CogniGuard/blob/065bb82/experiments/hsw_provenance_next/chronology/RESULT.md)
- **五位置来源码，06d9259，R1 STOP。** 12 个来源，五个二元等义表达位置，偶校验码共有 16 码、最小码距 2。原样往返 12/12，同源发行同码。90 次真实模型调用中，摘要恢复 0/12、强改写 0/12、两来源完整融合恢复 0/6。宽松可见码字在摘要和强改写各为 0/12。知识保留代理分别通过 12/12 和 11/12，其内正确符号分别为 1/60 和 0/55。六个自写来源族与融合截断限制外推。 [原始预测、事实记录与哈希](https://github.com/guoshaung/CogniGuard/tree/06d9259/experiments/rkw_risk_aware) · [失败分析](https://github.com/guoshaung/CogniGuard/blob/06d9259/experiments/rkw_risk_aware/FAILURE_ANALYSIS.md)
- **官方 Qwen 多比特。** RTX 5090 用作者公开 BF16 权重完成官方演示与 C4。两条入选演示 14/16 位正确，八位完整 0/2。单跳摘要、改写、同内容同码融合共五条带码输出，完整恢复 0/5。C4 有 8 条校准、16 条测试、96 个候选。无扰动 AUC 0.930、可观测位 97/120、完整四位 10/16、正确且接受 7/16、无标记误接受 0/16、错码 2/240。5%、10%、20% 随机词元替换后完整四位为 3/16、2/16、1/16。240 次错码比较共享 16 篇文本。该样本量支持开发诊断，1% FPR 的 TPR 尚无可靠估计。C4 生成实测 4.13 token/s。论文 TinyLlama 主表检查点仍未定位，公开 Qwen 的复现范围为作者发布版。 [C4 报告及数据](https://github.com/guoshaung/CogniGuard/blob/e609197/experiments/rkw_official_multibit/C4_RESULTS.md) · [实测传播](https://github.com/guoshaung/CogniGuard/blob/104c1d4/experiments/rkw_official_multibit/OFFICIAL_PROPAGATION.md)
- **训练继承与教师负结果。** CPU 初批仅完成历史对照的基座 9 条。fedd134 在 5090 完成 Qwen2.5-0.5B 基座、无标记 SFT、历史 RKW 文本 SFT、带标后干净再微调。两组各 12 样例、12 步，无标记和 RKW 各 2,196 与 2,166 个监督 token、1.18 与 0.94 秒。四组在同源新问法均完整恢复 0/12，未训练家族均弃权 6/6。RKW 自动规则命中 5/12，逐条核查 2 PASS、9 FAIL、1 UNKNOWN，保真条件下恢复 0/2。该同源新问法使用旧知识和来源路由提示。KGW 和 TextSeal 教师各检出 4/12 和 6/12，所有输出达到 48 token，知识合格均 0/12，干净对照 1/12。两臂教师预检未进入学生训练。 [CPU 诊断](https://github.com/guoshaung/CogniGuard/blob/d3d33e9/experiments/rkw_official_multibit/training/BLACKBOX_R0_CONTROL.md) · [GPU 与保真数据](https://github.com/guoshaung/CogniGuard/tree/fedd134/experiments/rkw_official_multibit/training/paired_r0) · [教师预检](https://github.com/guoshaung/CogniGuard/blob/fedd134/experiments/rkw_official_multibit/PAIRED_BASELINES.md)
- **见证知识块，c3574c2，STOP。** Qwen2.5-7B 在 768 token 上限生成九次，冻结六个通过事实核查的块。选中块内复用公开多比特模型重复 01 或 10，两个码字提供 1 bit 身份容量，预算两块。六次编码首两位正确 2/6，达到旧 C4 有符号分数门槛且保真 1/6，另有一块合句后不足两位。Llama 3.1 8B 对唯一合格速度块做摘要、改写、含未带码矩形的融合，恢复 0/3，配对干净对照命中 0/3。双带码来源与统一误报率尚待验证。TextSeal 事后改写在同底稿跑通，原生门槛 $p<0.001$ 检出且关键事实通过 2/6，保留其独立模型、载荷和误报口径。 [最后一轮全部产物](https://github.com/guoshaung/CogniGuard/tree/c3574c2/experiments/rkw_official_multibit/witness_blocks)

### 非水印基线与集成

既有资产含 SHA256、MinHash、BM25、BGE、重排序、主动文本变体、发行记录和签名凭证。27 个无水印模型端点的 137 个真实单元中，BGE 候选覆盖 125 个，词面确认 6 个。BGE+NLI 正确确认 99 个、错确认 4 个，F1 0.825。漏确认包含 12 个检索遗漏和 26 个候选内漏确认。候选内理想核验为 125/137。增强版确认 82 个、同样错确认 4 个。原固定见证过拒 4/835，危险放行 38/137 与正确确认数互为补数。 [内容基线及原输出](https://github.com/guoshaung/CogniGuard/blob/065bb82/experiments/hsw_provenance_next/baselines/real_comparison_metrics.json) · [核验与阈值](https://github.com/guoshaung/CogniGuard/tree/fcf1374/experiments/gate_w0_real/unit_checker)

Claude 在 0684a77 正式独立复现 99/4/38 和 F1 0.825。X3-E2E 23,040 次回放支持 H-Evidence 的四个变体，三个历史水印变体在 BGE+NLI 上的增量为零。结论对应 12 份 OpenStax 来源、15 条传播链和仿真治理见证。BGE+NLI 是独立研究延用的最强非水印对照。 [正式集成](https://github.com/guoshaung/CogniGuard/blob/0684a77/experiments/x3_e2e_integration/RESULT.md) · [判定汇总](https://github.com/guoshaung/CogniGuard/blob/0684a77/experiments/x3_e2e_integration/results/judgments_nli.json) · [接口交接](https://github.com/guoshaung/CogniGuard/issues/16#issuecomment-7131112696)

## 3. 知识保真与原始证据

- **条件、单位与矛盾。** KBPW 门槛探针把 4 mF 改成 4 μF，另有内能不变与增加 650 J 并存。学生输出在同一段写出 0 A 与 2 A，或给出正确的 1/4 同时声称第二次硬币一定与第一次相同。判定需覆盖答案、规则、单位、否定和解释。自动模式、作者式核查、独立人工标注和 UNKNOWN 保持各自口径。 [传播事实标注](https://github.com/guoshaung/CogniGuard/blob/065bb82/experiments/hsw_provenance_next/real/pilot/annotations.jsonl) · [RKW 学生逐条核查](https://github.com/guoshaung/CogniGuard/blob/fedd134/experiments/rkw_official_multibit/training/paired_r0/results/rkw_manual_review.jsonl)
- **相似度与局部事实。** Xu 等人的公开样例把 50% 改为 5%，MPNet 仍为 0.8947。Qwen 中文演示把 AUC 改成准确率。C4 有年度频次改变及提示词续写。最新块传播把 average speed 改成 average velocity，TextSeal 把长宽之和 13 米写成两边各 13 米。NLI 误确认包括互换书架与种类的约束，以及把热量换成功。 [论文附录](https://proceedings.mlr.press/v267/xu25k.html) · [C4 保真案例](https://github.com/guoshaung/CogniGuard/blob/e609197/experiments/rkw_official_multibit/C4_RESULTS.md) · [逐条编码及传播](https://github.com/guoshaung/CogniGuard/tree/c3574c2/experiments/rkw_official_multibit/witness_blocks) · [NLI 错误](https://github.com/guoshaung/CogniGuard/blob/fcf1374/experiments/gate_w0_real/unit_checker/results/errors.jsonl)

## 4. 复现、资产与文献

- **冻结和复算。** 五位置协议在 e2b1713 冻结，06d9259 含数据、源码和结果哈希。C4 预注册为 ac25788，native_metrics.py 从已保存的逐句分数复算。学生 GPU 方案在 e00b99b 冻结，配对任务及逐条结果在 fedd134。知识块编码配置在 7ca0e1f 与 b9e73fc 冻结，最终负结果在 c3574c2。后续复核可先读冻结输出。 [五位置复现](https://github.com/guoshaung/CogniGuard/blob/06d9259/experiments/rkw_risk_aware/REPRODUCE.md) · [C4 预注册](https://github.com/guoshaung/CogniGuard/blob/ac25788/experiments/rkw_official_multibit/NATIVE_PREREG.md) · [学生数据与复现](https://github.com/guoshaung/CogniGuard/blob/fedd134/experiments/rkw_official_multibit/training/paired_r0/README.md)
- **本地归档。** 38 份 OpenStax 开发底稿位于本地 hsw-st 工作树的 openstax_quality_20261123/ACCEPTED.json，已复核 SHA-256 为 ae85857bf1511dd57addbb01cf217fe06537686a5d359b3545d169b506233813。它们已经用于开发，独立确认需另行留出。原始 RKW 任务书位于本地附件目录 `C:/Users/guoshuang/.codex/attachments/88afe685-b7e1-4b12-899e-7e6ad4b4da3b/` 的 `已粘贴的文本.txt`，SHA-256 为 `5691fa67cc8e9b7a33ce5235421084b761d4d722a50900d1578c5ed7bea70f85`。仓库已有数学模型、阶段门槛和可复算数据，原始附件、完整 OpenStax 工作文件及权重缓存按本地归档取用。服务器缓存包含易失文件系统上的分片，重用时以清单中的 revision 和 SHA-256 核验。 [资产与权重清单](https://github.com/guoshaung/CogniGuard/blob/9394005/experiments/rkw_official_multibit/ASSETS_MANIFEST.json) · [服务器协议](https://github.com/guoshaung/CogniGuard/blob/ac25788/experiments/rkw_official_multibit/SERVER_PROTOCOL.md) · [资源采样](https://github.com/guoshaung/CogniGuard/blob/596e33d/experiments/rkw_official_multibit/results/performance_60s.jsonl)
- **语义与多比特编码。** KGW 是 token 绿名单历史对照。Xu 等人的公开方法用两个句级改写器与判别器。SemStamp 对句向量做 LSH 分区，k-SemStamp 使用聚类分区，原生任务为存在性检测。HSPMark 用相邻句的语义上下文累计 token 级多位证据。当前归档含后三种机制的对照说明。 [KGW](https://proceedings.mlr.press/v202/kirchenbauer23a.html) · [Xu 等论文](https://proceedings.mlr.press/v267/xu25k.html) · [Xu 等固定代码](https://github.com/xiaojunxu/multi-bit-text-watermark/tree/7439ecee8891c6e8226f02fa8c1a650d3e10aaff) · [SemStamp](https://arxiv.org/abs/2310.03991) · [k-SemStamp](https://aclanthology.org/2024.findings-acl.98/) · [HSPMark](https://github.com/Kcrystal55zz/HSPMark)
- **继承与语义事实签名。** TextSeal 复用官方事后改写接口，原生学生实验采用白盒 teacher forcing 聚合。ReasMark 用成对提示的推理轨迹长度评价模型行为。SemTrace Exact-12 从评审恢复已知文稿的事实签名，允许擦除。独立投稿需遵循各自访问条件，并为逐条盲归因建立可比的闭集扫描和拒识口径。 [三种基线核查](https://github.com/guoshaung/CogniGuard/blob/db4c2fe/experiments/rkw_official_multibit/INHERITANCE_BASELINES.md) · [TextSeal](https://arxiv.org/abs/2605.12456) · [ReasMark](https://aclanthology.org/2026.acl-long.2185/) · [SemTrace](https://arxiv.org/abs/2608.29575)
- **组合风险近邻。** Staddon 2003 和 Woodruff–Staddon 2004 的数据库共谋推断控制、联盟访问结构和覆盖问题是 CA-PD 的近邻。通用纠错码、集合覆盖与预算搜索是成熟组件。RKW 的贡献判定应依真实载体、风险分配或联合治理的增量，而非单独使用这些组件。 [数据库查新](https://github.com/guoshaung/CogniGuard/blob/b23c42c/docs/research/PRIOR_ART_AUDIT_20261124.md) · [早期集成历史审计](https://github.com/guoshaung/CogniGuard/blob/0684a77/docs/integration/RKW_REVIEW_20261124.md)

### 最短证据路径

- 阶段 R0/R1 的 `RESULTS_SHA256.json` 固定结果字节。`capacity.json` 与 `codebook.json` 支持原样容量核查，`channel_transitions.jsonl` 保留逐位正确、替换及擦除，`diagnostics.json` 保留复制与截断反例。 [结果目录](https://github.com/guoshaung/CogniGuard/tree/06d9259/experiments/rkw_risk_aware/results) · [结果哈希](https://github.com/guoshaung/CogniGuard/blob/06d9259/experiments/rkw_risk_aware/RESULTS_SHA256.json)
- 公开 Qwen 的 `c4_predictions.jsonl` 含 96 个候选和入选标志，`c4_native_scores.jsonl` 含 192 个带码、无码与扰动评分记录。以 Python 读取 JSONL 后调用 `native_metrics.summarize(rows)`，可与 `c4_native_metrics.json` 比对。权重与 value head 的固定版本见 CONFIG.json。 [C4 原始数据](https://github.com/guoshaung/CogniGuard/tree/e609197/experiments/rkw_official_multibit/results) · [评分脚本](https://github.com/guoshaung/CogniGuard/blob/e609197/experiments/rkw_official_multibit/native_metrics.py) · [权重配置](https://github.com/guoshaung/CogniGuard/blob/ac25788/experiments/rkw_official_multibit/CONFIG.json)
- 见证块的 `teacher_attempts.jsonl` 含全部九次底稿尝试，`official_blocks.jsonl` 含六个编码候选、逐句分数及 EOS，`propagation_raw.jsonl` 与 `propagation_scored.jsonl` 含配对传播输出及全部计分窗口。`risk.py` 独立核对选块逻辑，`DESIGN.json` 记录两块预算和继承自 C4 的诊断门槛。 [逐阶段数据与代码](https://github.com/guoshaung/CogniGuard/tree/c3574c2/experiments/rkw_official_multibit/witness_blocks)

## 5. 独立投稿保留的研究问题

1. **R1 载体存活。** 在独立留出的来源族及传播链中，能否同时保持事实与可区分的来源位。单列真实摘要、轻重改写、两源及三源融合和 1/3/5 跳。分别测位准确率、完整码、集合精确恢复、知识保留条件下召回、覆盖率与错归因。用同知识独立生成、完整复制、删知识留载体及无标记文本标定弱点。
2. **R2 来源增量。** 在同一文本、相同候选数和 NLI 调用预算及共同误报工作点下，估计联合证据相对 BGE+NLI 的来源–单元 F1 增量。另设等核验预算的 BGE 扩展候选，分报水印信号增量和编码改写的整体效应。窗口扫描、候选扩展和 Best-of-N 的选择过程都进入零假设校准。
3. **R3 风险分配。** 固定载体、码本、物理预算、检测器和门槛，比较均匀、仅存活率、仅风险、联合分配。主要比较是联合相对仅存活率的风险加权召回增量。同步评价普通召回、保真与误归因。在风险均匀、非均匀和存在严格互补三种情况下各自检验，以传播链或来源簇作统计单位。
4. **R4 治理。** 按 pe-1.0 用真实逐样本证据回放，保持权限、回执与请求一致。见证夹具应有多个缺失单元、重叠见证和多个候选联盟。报告危险放行、过拒及正常效用，区分授权与预算机制。同一个正确确认数及其恒等的放行减少量只算一次。
5. **学生继承。** 传播与知识保真门槛通过后，再用同来源未见题测自由生成继承，未训练来源测误归因。统一底座、教师事实、有效训练词元和更新预算，以未微调基座和无标记学生控制预训练记忆。编码器 LoRA、黑盒文本蒸馏、白盒诊断和蒸馏后干净再微调分开。任务效用、知识习得与载荷恢复使用各自独立指标。
