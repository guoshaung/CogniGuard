# B2 开发预注册

附件 SHA-256 为 `48f6d15098b4c507fbe975a9a8eb89b2a3a2decc7810e445ca5493c836b3aa1e`。保留第 1 至 6 节和附录 A–D5 原文。附录 D 的优先顺序沿用用户约定。

~~~text
1. 方法定义（预注册）
1.1 框架词集合 F
F = {"Here,", "In this case,"}。

依据阶段 0 的上下文诊断：

二者带上下文的正向 NLI 分别为 82% 和 80%；
都不在 PDTB-2.0 附录 A 的连接词清单中；
在 R_build 中分别出现于 20 篇和 28 篇文档。
"that is" 的 NLI 通过率虽然最高（98%），但它表示复述关系，按"指向当前情境、不与上一句建立逻辑关系"的语义标准排除。在 B2_PREREG.md 中如实写明这一判断及理由。

1.2 槽位
对文本 x，切分句子，沿用 EVAL-03 的结构规则排除标题、小节标签和题干。
讲解句 s_i 是一个槽位，当且仅当：它的前一句 s_{i−1} 含有至少一个知识锚点，并且 s_i 本身不以连接词开头。
槽位的锚点签名 a_i = s_{i−1} 中全部锚点经规范化（大小写、空白、公式规范化，与 EVAL-03 的抽取器一致）后排序拼接的字符串。
1.3 标记函数
u_i = HMAC-SHA256(K, a_i) 映射到 [0, 1) 的值；
当 u_i < γ 时，槽位 i 为标记槽位，否则为非标记槽位；
γ 是待选参数，见第 6 节。
1.4 嵌入
在标记槽位中，用 EVAL-03 的 3B 打分模型对"插入 Here," 和"插入 In this case," 两种方案打分（只打分，不生成）。
按分数从高到低选择插入。约束：
每个槽位最多插入一次；
同一个框架词在全文中最多出现 ⌈m_max/2⌉ 次，含原文已有的出现次数；
总插入数不超过 m_max。
每插入一次就计算预测 p 值（按 1.5 节的检验）；p < 10⁻³ 时停止。
达到 m_max 或标记槽位用完时 p 仍 ≥ 10⁻³：判为不可加水印，原文不变。
编辑证书与恢复验证同 EVAL-03：插入的片段 + 首字母小写记录，Restore(x̃, E) = x。
1.5 检测（文内自校准，不使用背景频率 q）
对可疑文本 y：

重新识别槽位、计算锚点签名和标记；
设 S = 槽位总数，M = 标记槽位数，N = 以 F 中框架词开头的槽位数，X = 其中属于标记槽位的数量；
零假设：框架词的出现与密钥标记无关。在给定 S、M、N 的条件下，X 服从超几何分布 Hypergeometric(S, M, N)；
p 值 = P(X ≥ x)，p < 0.01 判为有水印；
N = 0 或 M = 0 时不做检验，判为未检出。
这一检验不需要估计任何背景频率。它唯一的前提是框架词在自然文本中的出现与密钥标记无关，第 2 节会对此做实证检验。

2. 零假设有效性检验（R_calib，只用 CPU）
在 R_calib 全部未加水印的文档上，用 1000 个随机密钥 × 每个候选 γ 计算 p 值。
报告 α = 0.001、0.01、0.05 时的经验误报率，以及 p 值的 QQ 图数据。
报告自然文本中框架词落在标记槽位的比例，与 γ 比较（应接近 γ）。
若某个 γ 的经验误报率 > α，该 γ 不合格。
3. 嵌入模拟（R 中的生成讲解，≥300 篇）
网格：γ ∈ {0.10, 0.20, 0.30}，m_max ∈ {3, 4, 5}。每个配置报告：

覆盖率（总体，以及按长度分箱 <100 / 100–200 / 200–400 / >400 词）；
平均插入次数，同一框架词的最大重复次数；
证书与恢复：必须 100% 通过，否则停下并报告；
无攻击检出率（应为 100%）。
4. 摘录检出
对每个配置的水印输出，取开头、中段、结尾 100 词摘录，以及开头、中段 200 词摘录。报告检出率，并与 EVAL-03 已归档的 T4/T5 摘录检出率并列作为参照（标注为不同数据、不同方法）。

5. 伪造攻击
随机攻击者：不知道密钥，在 R_calib 中 200 段未加水印文本的随机槽位插入 3、4、5 个框架词，报告被判为有水印的比例。
学习攻击者：观察 N = 10、50 份水印输出，记录"哪些锚点签名之后出现了框架词"，以此推断这些签名为标记签名；再在 200 段未加水印文本中，只在前一句含有已学到签名的槽位插入框架词。报告被判为有水印的比例，以及目标文本中出现已学到签名的槽位比例。这一项衡量"常见锚点被反复看到后，标记是否泄露"。
擦除：删除所有框架词后仍检出的比例（预期接近 0，如实报告）。
6. 参数选择规则（预注册，先冻结）
对每个 (γ, m_max)：

资格：第 2 节在 α = 0.01 下经验误报率 ≤ 0.01，且证书 100% 通过；
目标：J = 覆盖率 − 学习攻击者（N = 50）的伪造接受率，取最大者；
同分（J 相差 < 0.02）：选更小的 m_max（插入更少、更自然），再选更小的 γ；
若没有任何配置合格，停下并报告，不得放宽。
选定的 (γ*, m_max*) 与全部规则一起冻结后，才能进入 T6 的生成和评测（另发任务书）。
~~~

~~~text
附录 A：需要复用的已冻结组件（找不到就停下报告，不要自己重写）
组件	来源
模拟资料库 R（R_build / R_calib 划分、≥300 篇生成讲解）	EVAL-04 阶段 0：RAG_CORPUS_MANIFEST / CORPUS_MINING_FREEZE.json、R_GENERATION_FREEZE.json
句子切分、结构规则（标题 / 小节标签 / 题干识别，含 Markdown 标题）	EVAL-03 冻结版本（T5 使用的 Markdown 适配解析器）
知识锚点抽取器及规范化	EVAL-03 冻结版本（与 CertInsert 的锚点密钥所用的完全相同）
3B 打分模型及上下文窗口	EVAL-03 冻结版本（只打分，不生成）
编辑证书与 Restore 校验	EVAL-03 冻结版本
上下文 NLI 诊断结果	context_nli_diagnostic_20261114/RESULT.md（框架词集合 F 的依据）
figure_counts.json 格式	FIGURE_COUNTS_SCHEMA.md；本任务新增字段写在 B2_DEV_RESULT.md 末尾
在 B2_PREREG.md 中逐项写明所用文件的路径和 sha256。

附录 B：补充定义（作为预注册的一部分一起冻结）
"以连接词开头"的判定：句首片段（1–4 个词，后接逗号）属于以下任一集合即算：阶段 0 挖掘出的 47 个真实性候选、PDTB-2.0 附录 A 的 100 个词形、F 本身。这类句子不能作为槽位。
原文中已有的框架词：如果某个槽位在原文中已经以 F 中的词开头，它在检测中照常计入 N，并且根据标记与否计入 X。嵌入时不得在这类槽位重复插入。
开发密钥：嵌入使用一个开发密钥 K_dev，由操作系统随机数生成，只保存在本地不提交的文件中；仓库里只放 SHA-256 承诺值。零假设检验用的 1000 个随机密钥同样只提交承诺值。
插入打分：沿用 EVAL-03 的 Δlog-prob 打分与上下文窗口；"Here," 和 "In this case," 插入后，后一个词的首字母小写，与 EVAL-03 一致。
预测 p 值：嵌入过程中直接对当前候选输出运行第 1.5 节的检测器（同一份代码），不另写近似公式。
学习攻击者的"签名相同"：规范化后的锚点签名字符串完全相同才算相同，不做模糊匹配。
超几何 p 值：用精确计算（例如 scipy.stats.hypergeom 的 sf(x−1, S, M, N)），并对小样本做单元测试：手算 3 个例子与代码结果一致。
长度分箱：按讲解正文词数（不含题干），与 EVAL-03 / T5 的口径相同。
附录 C：完成标准与停止点
第 2–5 节的全部表格都有数字（或标明 NOT_RUN 及原因）；
第 6 节选出 (γ*, m_max*)，或明确报告"无合格配置"；
已推送到 codex/hsw-st，并回读核验；
然后停止，不生成 T6，也不进入下一阶段。
附录 D：对可执行性检查三个问题的答复（优先于正文和附录 B，一并写入预注册）
D1 槽位识别
连接词清单：阶段 0 的 47 个真实性候选 ∪ PDTB-2.0 附录 A 的 100 个词形，不含 F。
先剥离框架词，再判断槽位资格：判断句子 s_i 是否为槽位时，若它以 F 中的框架词开头，先在概念上去掉这个框架词，再看剩余部分是否以清单中的连接词开头。否则，嵌入一个框架词就会让这个槽位在检测时失去资格，检验无法成立。剥离只用于判断资格和计算 N，不改动文本。
前一句的锚点不受影响：插入框架词不会改变任何锚点。
D2 以锚点签名为单位计数（主检验），并以实测误报率判定资格
同一文档内锚点签名重复时，多个槽位共享同一个标记，逐槽位计数会违反超几何检验的可交换性前提。因此主检验改为以"签名单元"为单位：
文档内每个不同的锚点签名构成一个单元，标记由 u(签名) < γ 决定；
单元"含框架词" = 该签名对应的任一槽位以 F 开头；
S = 单元总数，M = 标记单元数，N = 含框架词的单元数，X = 其中的标记单元数；p 值 = 超几何上尾 P(X ≥ x)。
零假设下，各单元的标记是独立同分布的 Bernoulli(γ)，且与框架词无关，所以条件于 M 的超几何检验是精确的。
嵌入与之一致：每个标记单元最多插入一次，插在该签名第一次出现后的那个槽位；预测 p 值用同一检测器计算。
逐槽位计数的版本保留为探索性统计量，单独报告，不参与资格判定。
资格：α = 0.01（检测阈值）和 α = 0.001（嵌入目标）两档的 R_calib 经验误报率都必须 ≤ α（按点估计，不加宽限）；α = 0.05 只报告，不作资格条件。第 6 节第 1 条按此执行。
另报告每篇文档中重复签名所占比例。
D3 学习攻击的分母与缺额
观察数统一：用于排名的观察数 N_rank = min(50, 各合格配置中成功水印输出数的最小值)。所有配置都按同一个 N_rank 排名，避免低覆盖配置因为"被观察得少"而占便宜。N = 10 和 N = 50（可评估时）照常单独报告。
某配置成功水印输出少于 10 篇：该配置不参与排名，记为 NOT_RANKABLE_LOW_COVERAGE。
目标文本：分母固定为 200 段 R_calib 未加水印文本。目标文本中没有任何"已学到签名"的槽位时，攻击者无从插入，记为未被接受，仍计入分母；另报告至少有一个可攻击槽位的目标文本比例。
第 6 节的 J 改用 N_rank 下的伪造接受率。
D4 历史摘录参照
历史参照只用 EVAL-03 已汇总的 T5 开头 / 中段 100 词检出率（batch02-adjusted FINAL 的 figure_counts.json 中 detection.T5 的 crop_first100、crop_middle100），以及 T4 的 100 词记录。其他窗口没有历史参照，标注 N/A。不得为此打开任何 T1–T6 原文。
D5 学习攻击每篇插入次数
排名用（主口径）：攻击者尽力而为，强度与被测配置无关。在目标文本中，凡是锚点签名属于"已学到的标记签名"的单元都插入一次框架词（每单元最多一次，与 D2 的单元定义一致），不设上限，也不受被测配置的 m_max 约束。理由：若按 m_max 封顶，小 m_max 的配置面对的攻击者天然更弱，排名会系统性地偏向它们。
辅助口径（只报告，不参与排名）：按各配置的 m_max 封顶插入；可用单元不足时插满。
两种口径下，目标文本中可攻击单元为零时，都按 D3 记为未被接受，仍计入 200 的分母。
另报告：每篇目标文本实际插入次数的分布，以及插入位置中真正属于标记单元的比例（反映攻击者学到的签名有多准）。
~~~

## 执行细节

- 复用 EVAL-03 的 spaCy 管线，对内联公式按原长度遮蔽后分句。Markdown 结构适配使用 R 文档附带的题干，未带题干的文档传空字符串。槽位位于正文，用相邻分句定义签名。提取前句锚点前剥离框架词。排序的锚点用 UTF-8 JSON 字符串数组编码。HMAC 按完整 256 bit 大端整数与精确的 γ 阈值比较。
- 保留旧证书组装函数要求的 8 词间距。首字母小写记入证书。如果单字符小写改变 Unicode 长度，该处不插入。嵌入仅考虑每签名的首个槽位，不在已有框架词的槽位上插。已含框架词的签名增加插入不会增加检验的 N 或 X，因此只对未含框架词的单元打分。预测与复核使用同一检测器。
- 打分沿用总 Δlog-prob、前五句至后一句窗口、每次贪心更新后按已插入内容重算、高分优先及偏移/字母序破同分。沿用 1024 token 不截断、每文档每配置 250,000 前向 token / 300 秒、阶段 7,200 秒上限。未成标时归还原文。
- 主签名单元口径及槽位探索口径对全 893 篇 R_calib × 1,000 个随机密钥计算。无检验 QQ 用 p=1 并单列分母。长度分箱为 <100、100–199、200–400、>400。嵌入固定所有 300 篇，不补样本。
- 摘录用空白词窗口，长度不足时保留全文。条件分母为成功加水印的文档。只引用历史汇总。
- 从 R_calib 的未加水印自然文档按固定哈希顺序取 200 篇。随机攻击以相同种子抽取无框架词槽位，少于 3/4/5 时插满。学习观察在各配置的成功文档内按同一哈希顺序取前 N。目标每次从原文开始。学习攻击按位置顺序对已学签名的第一个可插槽插入，每单元最多一次，主口径不限量，辅助取前 m_max 个。框架词固定交替。
- 攻击生成只接收文本公开槽位和已观察签名。真实标记比例只在离线评价时计算。零可插入按 D3/D5 记未接受。擦除删除已识别的句首框架词，沿用首字母大写，不使用证书。
- 排除误报超标、证书失败和成功数不足 10 篇的配置后计算统一 N_rank。计算最大 J 后，以严格 <0.02 确定并列集合，优先较小 m_max，再选较小 γ。无排名候选时记录无合格配置。
- T1–T6 原文均不参与。密钥由操作系统随机生成，仅保存在本地忽略目录。公开文件仅含各密钥 SHA-256 承诺。

## 附录 A 路径与哈希

- `experiments/hsw_certinsert_eval04_20261113/CORPUS_MINING_FREEZE.json`　`00a777f411436cce0cf1a4392359a4b64966b76c4451bd91f9daee36d38fd9f7`
- `experiments/hsw_certinsert_eval04_20261113/R_GENERATION_FREEZE.json`　`bd37c6dca8bdd0169cf6ff55a1699e08dce4239653202142da3ade0de5e03ea6`
- `var/results/hsw-st/certinsert_eval04_20261113/stage0/RAG_CORPUS_MANIFEST.json`　`3964079af608ccb40cabfecc76164bd375a1e0e40f05858a0a3a11dccc1b6d9a`
- `var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json`　`612af82f42d24f63844c66025229407e7d2f1c1f40db55a9d48c0efd49635387`
- `var/results/hsw-st/certinsert_eval04_20261113/stage0/ATTESTED_CANDIDATES.json`　`b2814f7b834e51d356656f2be6b36ddb6fe925a66c57cb8ae834c9a52f75b9ab`
- `experiments/hsw_certinsert_eval04_20261113/mine_r.py`　`6e82d8bb8cceb400eac4dd350a9552e7555fad382f909ef327df7dd103957727`
- `experiments/hsw_certinsert_eval04_20261113/context_nli_diagnostic_20261114/RESULT.md`　`ae4d9813d5c12f57f668a22a03de07cc1993e9190413de33cca288b7821aaf46`
- `experiments/hsw_certinsert_eval04_20261113/context_nli_diagnostic_20261114/report.py`　`71763a5a457531f1edc5fb266efcfd1be0353477a637b38bcc7fb364b128d578`
- `var/results/hsw-st/certinsert_eval04_20261113/context_nli_diagnostic_20261114/pdtb-annotation-manual.pdf`　`5f0052449055f512fad09b24fb1c10e9127ad0f72fa5c42d9e18564194cc55b3`
- `experiments/hsw_certinsert_eval_20261111_02/structure_adapter.py`　`844d9c3095cad8615f0d4e225d311d9f23c5b77545324833524130e7ae4fec49`
- `experiments/hsw_english_replication_20261110_01/capacity_shared_v32.py`　`0e7993f7247abd8d1a1cd8fa4506cf4238cca01f4efb7e92883c88316255efcb`
- `experiments/hsw_english_replication_20261110_01/e1_detector.py`　`e1fcee3d04a4d024e5cc7a713c39e6de07bde0c66f9a8aad01d8a5a1ebb277f4`
- `experiments/hsw_english_replication_20261110_01/e1_v4r7f_anchors.py`　`eec35e11921459c81e59b920ffc8842b031d94038a698cd66dfbb5d45854f9b9`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/protocol_v4/revision07_final/COURSE_TERMS.json`　`59f28bd7a388396c108316b738783d61a3510a294e201b350ded5ddad333a912`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/attack_three_seed_round01/FINGERPRINT_FREEZE.json`　`7ab411b842f0e9067c5d2a652b4d07fd5d45e7fa42a84bcffaeed29758dbd2d9`
- `experiments/hsw_english_replication_20261110_01/e1_long_context_run.py`　`aebc1b0401e7a3c5a8a898872527da1601e8633d440ac8d61534f73396682868`
- `experiments/hsw_english_replication_20261110_01/e1_register_core.py`　`8d13be14a50201e538562292292d67941c58aaefec2d511abb3066b2ea1baacc`
- `experiments/hsw_insertion_feasibility_20261109_01/run05_gpu_scorer.py`　`43fda01d67f3a7f19c5fa6af08c9fe68f9e750673221b764482712e2565e7131`
- `var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/gpu_score_bridge.dll`　`beb98a75f53cebbcc8ae293ae7be16a0cf1c4eec01ca958f12131e3662e6a8cf`
- `var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime/ggml-base.dll`　`3a0399fa51102a86824255beda9d021ea7e8cd2bd8ca448a43a9a80aa4829290`
- `var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime/ggml.dll`　`06dfdff8b7b834c757ec5b5411abfc0f732604fb595eaaffbdc6da563523e8a1`
- `var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime/ggml-cuda.dll`　`8fce7588c2906312694c056a028e846ae48db3675d5d83e6084fcf72e4b0dd76`
- `var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime/llama.dll`　`211b91d86e67c49f12eb97992b45ae4c2fc797d6edab48637835a877c808890e`
- `experiments/hsw_certinsert_eval03_batch2_adjusted_20261112/T5_INSERTION_ADAPTER_FREEZE.json`　`bfe101c00239409a9d27b500391a4e90417fd4395d1d9de4d19e3662b47f6df9`
- `experiments/hsw_certinsert_eval03_lite_20261112/FIGURE_COUNTS_SCHEMA.md`　`b14f34492797c268451aa16b2cef4853710597fbcd54db0919769a7ce77b38ac`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02_adjusted/publication_FINAL/figure_counts.json`　`be6c0a996f9fd8ca8de081b6cec1aa06dcf7ae7bb3dd31a7dbb11861a9294365`
- CogniGuard 主项目 `assets/models/qwen2.5-3b-instruct-q4_k_m.gguf`　`626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`
