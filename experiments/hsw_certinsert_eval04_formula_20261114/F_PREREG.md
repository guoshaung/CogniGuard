# HSW EVAL-04-F 开发预注册

附件 SHA-256 为 `7ad2070d600848c31f6522cdd666daf45f28a0e542637873dce309f75aa10a20`。以下保留第 1、2、6 节原文。

## 1. 符号载体的定义（预注册）

### 1.1 可插入点（"符号槽位"）
讲解正文中（不含标题、小节标签、题干，沿用 EVAL-03 结构规则）满足以下之一的位置：
- **方程**：EVAL-03 锚点抽取器识别出的、含等号且至少含两个符号变量的公式；
- **带单位的数值**：数值后跟一个可识别的物理单位；
- **长小数或大数**：绝对值 < 0.001 或 ≥ 10,000 的纯数值。

同一句中最多使用一个符号槽位，取第一个符合条件的位置。

### 1.2 允许的插入类型（只限这三类）
| 类型 | 生成方式 | 验证方式 | 插入格式 |
|---|---|---|---|
| 变形 | 用 SymPy 把方程解出另一个变量（只取唯一解；多解、无解、含不等式或函数方程的跳过） | SymPy 化简"原式 − 新式"为 0，或代入 20 组随机数值检验 | ` (equivalently, <新式>)` |
| 单位换算 | 用 pint 换算成同量纲的另一个常用单位（SI 前缀变化或常见替代单位） | pint 反向换算回原值，相对误差 < 1e-9 | ` (i.e., <新值和单位>)` |
| 计数写法 | 科学计数法与普通写法互换 | 数值完全相等 | ` (i.e., <新写法>)` |

- 插入位置：紧跟在原公式或数值之后、句末标点之前。
- 每个符号槽位最多插入一次。
- 公式用原文同样的格式书写（LaTeX 或纯文本），由同一个渲染器校验能否正常解析。

### 1.3 密钥选择
- 每个符号槽位有若干个合法的变体（例如解出不同变量、换算成不同单位），记为候选集 V_i，按规范化字符串排序。
- 锚点签名 a_i = 该公式或数值本身的规范化字符串（与 EVAL-03 锚点抽取器的规范化一致）。
- 密钥选中的变体 v*_i = V_i[ HMAC-SHA256(K, a_i) mod |V_i| ]。
- 只有 |V_i| ≥ 2 的槽位才计入检验（只有一个变体时，无法区分"选中"与"未选中"）。

### 1.4 嵌入
- 按 3B 打分模型的 Δlog-prob 从好到差排列可插入的符号槽位，依次插入密钥选中的变体，直到合并后的预测 p 值 < 10⁻³（见 1.6），或达到每篇上限 m_f = 3 处。
- 编辑证书扩展：每条记录写明插入位置、插入文本、类型和验证方式；Restore(x̃, E) = x 必须逐字节成立。

### 1.5 符号载体的检测（文内自校准）
- 对可疑文本 y，找出所有"原式后紧跟括号等价形式"的位置，以及每个位置的候选集 V_i。
- 设 n = 出现了括号等价形式、且 |V_i| ≥ 2 的位置数，X = 其中插入的恰好是 v*_i 的数量。
- 零假设：插入的变体与密钥无关，各位置独立地以概率 1/|V_i| 恰好命中。p_f = Poisson-binomial 上尾 P(ΣB_i ≥ X)，其中 B_i ~ Bernoulli(1/|V_i|)。
- n = 0 时符号载体不提供证据，p_f = 1。

### 1.6 两种载体合并
- 句首插入载体使用 EVAL-03 冻结的检测器，得到 p_s；
- 合并 p 值：Fisher 法，T = −2(ln p_s + ln p_f)，服从自由度为 4 的卡方分布；
- 合并后 p < 0.01 判为有水印，嵌入目标为 p < 10⁻³；
- 只用句首插入时，嵌入与检测行为与 EVAL-03 完全相同。

---
## 2. 零假设有效性检验（R_calib，只用 CPU）
- 统计 R_calib 中自然出现"原式后跟 equivalently / i.e. 括号等价形式"的位置数。
- 用 1000 个随机密钥计算 p_f 和合并 p 值，报告 α = 0.001、0.01、0.05 的经验误报率，以及 QQ 数据。
- 资格：α = 0.01 与 α = 0.001 两档都必须 ≤ α（点估计，不加宽限）。
## 6. 判定规则（预注册）
满足以下全部条件，才把符号载体纳入 T6 评测：
1. 第 2 节两档 α 的经验误报率达标；
2. 第 3 节中，合并后的覆盖率比只用句首插入**高出至少 10 个百分点**（在 R 的 300 篇生成讲解上，总体口径）；
3. 所有插入变体 100% 通过符号或单位验证，且证书 100% 可还原；
4. 学习攻击（N = 50）的伪造接受率不高于只用句首插入时的伪造接受率（按 EVAL-03 同一攻击方法在 R 上重测）。

任一条件不满足：停止，在 `F_DEV_RESULT.md` 中写明未通过的条件和数值，不得放宽。

## 冻结执行口径

- 冻结的 EVAL-03 Markdown 结构、分句、锚点、句首选词、背景频率、证书和 3B 的前五句至后一条句子上下文沿用。句首 6% 词数预算、8 词间距及机械不变式沿用。3B 使用旧 CPU 桥、0 GPU 层、4 线程、1024 token 不截断。旧模型的 EVAL-03 GPU 运行时间上限不移植到 CPU。保存逐条记录以便复核。
- 每句首个完整且在正文内的符号槽位进入生成和验证。方程只用能被冻结抽取器识别的完整表达式，带分隔符公式优先识别。利用 SymPy 解出唯一实解，排除原式已显式解出的变量。按恒定非零比例验证双向残差等价，拒绝新增未经证明的定义域条件。KaTeX 同时检查原公式和改写式的排版，ANTLR 校验 LaTeX，数字计算用 Decimal。单一科学计数式或普通数值改写通常只有一个变体，仍记录容量，但不提供密钥区分。
- 物理单位从冻结家庭取候选，依次是长度 m/mm/cm/km、面积 m²/cm²/mm²/km²、体积 L/mL/µL/m³/cm³、质量 kg/g/mg/µg、时间 s/ms/µs/min/h、速度 m/s/km/h/cm/s、力 N/mN/kN、能量 J/mJ/kJ/Wh、功率 W/mW/kW、压力 Pa/kPa/MPa/bar、频率 Hz/kHz/MHz、温度 K/°C/°F、电量 C/mC/µC、电流 A/mA/µA、电压 V/mV/kV、电阻 Ω/kΩ/MΩ、物质的量 mol/mmol/µmol、浓度 mol/L/mmol/L/µmol/L。Pint 反算，渲染精度上限为 12 位有效数字。零值用绝对误差。按冻结公式规范化排序去重。
- HMAC 摘要按大端整数与候选数取模。复用句首真实密钥。符号开发密钥和 1000 组校准密钥采用操作系统随机性。校准按每把随机密钥重建原句首词表排列和同一符号命中模型。无符号证据时 p_f=1，按字面 Fisher 公式计算合并 p；单载体保留各自公式。重复签名的标记相关、离散 p 值及两载体相关可能偏离 Fisher 的理论前提，实测校准和 QQ 并列报告。
- 先用原句首流程实跑基线，再从同样的句首尝试构造合并组，按冻结 3B Δlog-prob 排列符号增量，最多三处。失败时保留原文；符号单独按 p_f 停止；合并按 Fisher 停止。各臂将自然阳性和实际插入分开记录。200 正文词在 100–200 箱。
- 近失使用归档实际末次预测 p 和容量预测下界分列。使用 [0.001,0.05]，只取 CertInsert 的 UNWATERMARKABLE 状态，恢复批按相同 ID 覆盖旧失败记录。读字段仅限 ID、状态及数值，不读取历史题目与结果正文。
- 伪造从 R_calib 含合法符号变体的文档按固定哈希顺序取最多 200 篇，随机插 1、2、3 处，分列实际插满和计划分母。学习观察按固定哈希顺序，句首按 EVAL-03 文本频率超额排序及 m=4/8 复核，以 m=8 判定。符号攻击者只读公开可见等价写法，尝试所有已见签名，观察不足则条件标为 NOT_RUN。使用相同目标比较。所有随机抽取命名种子 EVAL04-F-20261114。
- 开发门槛未全部得到支持则停止。T1–T6 原文与 T6 生成均不属于本轮。

## 依赖版本

- sympy 1.14.0
- pint 0.24.4
- antlr4-python3-runtime 4.11.1
- flexparser 0.4
- flexcache 0.3
- numpy 1.26.4
- scipy 1.14.1
- spacy 3.7.5
- en-core-web-sm 3.7.1
- torch 2.12.0
- transformers 4.57.6
- katex 0.17.0

## 冻结组件 SHA-256

- `var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json` `612af82f42d24f63844c66025229407e7d2f1c1f40db55a9d48c0efd49635387`
- `var/results/hsw-st/certinsert_eval04_20261113/stage0/RAG_CORPUS_MANIFEST.json` `3964079af608ccb40cabfecc76164bd375a1e0e40f05858a0a3a11dccc1b6d9a`
- `experiments/hsw_certinsert_eval04_20261113/CORPUS_MINING_FREEZE.json` `00a777f411436cce0cf1a4392359a4b64966b76c4451bd91f9daee36d38fd9f7`
- `experiments/hsw_certinsert_eval_20261111_02/structure_adapter.py` `844d9c3095cad8615f0d4e225d311d9f23c5b77545324833524130e7ae4fec49`
- `experiments/hsw_certinsert_eval_20261111_01/prepare_cpu.py` `7fd8b5ad6e607ec83120b6d09f2af946e3046eece7fe4ad00eccae3e475e61c5`
- `experiments/hsw_certinsert_eval_20261111_01/common.py` `245ab0331704c2204ec216cee2d4d8e6150eb5e7223ea1a295826be9d4798d8e`
- `experiments/hsw_certinsert_eval03_lite_20261112/FIGURE_COUNTS_SCHEMA.md` `b14f34492797c268451aa16b2cef4853710597fbcd54db0919769a7ce77b38ac`
- `experiments/hsw_certinsert_eval03_lite_20261112/insert_batch1.py` `67b84d91dd2a599a0d97894c1d58af30faa235350d18450a7460ed3e7a5e25c3`
- `experiments/hsw_certinsert_eval03_batch2_adjusted_20261112/prepare_attacks.py` `4cfe1c19c004c54be4c109278b0b5c91be07e04459cd15e838726f6d9ca26864`
- `experiments/hsw_certinsert_eval03_batch2_adjusted_20261112/evaluate_t5.py` `f68c25895384006bc510c47f0cc9799a6e84c3fe541bf0fed1eed1cc28a13cbc`
- `var/results/hsw-st/certinsert_eval_20261111_02/run01/DOMAIN_FREQUENCIES.json` `439476bfa7267f1fd7d2a5db854b892bd1ab82721913cce46e161c32c97eb100`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/prepared_batch1/CAPACITY.json` `2450db7a0234ed6e69b4b06b47dcda399446d80bb57de986afb2bc772f3b2fe5`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/prepared_batch1/SCALE.json` `a1b45fc79fa092268a70ea7239f595b0798e5b1d199b94790758bc67dbe47f75`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/scoring_recovery01/INSERT_T4_all_RESULT.json` `8b345822eb06ca65112db20fc9082c208554cb535e36bdd6d50eca81ef3bf39c`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/INSERT_T4_all_RESULT.json` `0e6dff87af6e8264a6818fba4d35e90e6d3e7cfa228e4380892241efe5dcf413`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02_adjusted/T5_insertion/INSERT_T5_all_RESULT.json` `f0e2e93821986dcbbcac374cfd264b94dbd7f4dc702cfe529d092bee367c40fe`
- `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02_adjusted/T5_prepared/CAPACITY.json` `99e7020c85a4a56b1c1c0ea690b7688b0dcc74dbc3783de7ccd3acc711fa206e`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/development_round01/FREEZE.json` `4da3a1dc311123e7c72a88531dd65c3d8fe455bae8715eadc0749f78546418d2`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/development_round01/SECTABLE_CORPUS.json` `2188c8bd80454d71c94b817ae24693ffe2a8f01f92138f799ab09507b9bf2327`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/protocol_v4/revision09/VOCABULARY.json` `51399ba5520ef485bf98a3f8358f6c278c21fbbeb5df746da553c717a8789516`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/protocol_v4/revision09/FREEZE.json` `fd0864ddacf11e800d8baf40fea531edd8482d51b424fd16f464532e2b8dfce2`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/protocol_v4/revision07_final/COURSE_TERMS.json` `59f28bd7a388396c108316b738783d61a3510a294e201b350ded5ddad333a912`
- `var/results/hsw-st/english_replication_20261110_01/e1_guarded/attack_three_seed_round01/FINGERPRINT_FREEZE.json` `7ab411b842f0e9067c5d2a652b4d07fd5d45e7fa42a84bcffaeed29758dbd2d9`
- `experiments/hsw_insertion_feasibility_20261109_01/run05_scorer.py` `ff0958f4102805eabb7d1f6188846ba159f71f960d3396d48734925ce341a2f9`
- `experiments/hsw_insertion_feasibility_20261109_01/run05_score_bridge.c` `a3f2746e69a133f1189c0dfc18beb2778d8231e9a982d30681ad3aacb845a104`
- `var/results/hsw-st/insertion_feasibility_20261109_01/run05/v2/score_bridge.dll` `88c0735c5082d54ba6e4e852634f7ea4dfe43d6969e875d51c704bfd083a2c00`
- `experiments/hsw_english_replication_20261110_01/capacity_shared_v32.py` `0e7993f7247abd8d1a1cd8fa4506cf4238cca01f4efb7e92883c88316255efcb`
- `experiments/hsw_english_replication_20261110_01/e1_detector.py` `e1fcee3d04a4d024e5cc7a713c39e6de07bde0c66f9a8aad01d8a5a1ebb277f4`
- `experiments/hsw_english_replication_20261110_01/e1_v4r7f_anchors.py` `eec35e11921459c81e59b920ffc8842b031d94038a698cd66dfbb5d45854f9b9`
- `experiments/hsw_english_replication_20261110_01/e1_v4r8_selector.py` `e9aabe1e95e5cc11ea3bc1eb6a43da7e38e4d7ca244a2149ce93067e936bfa8c`
- `experiments/hsw_english_replication_20261110_01/e1_v4r8_capacity.py` `24227efb964acfd5c756aba2e8544a4967ae09f1eb2ada750d32b90a4c5340b5`
- `experiments/hsw_english_replication_20261110_01/e1_v4r7f_prepare.py` `2dfed95f2adefdd1c999f129ec2edc8dbe0f6b255cbd874e8fda15d50a81e9cd`
- `experiments/hsw_english_replication_20261110_01/e1_v4r3_core.py` `1e45b615e2cb42ebbb954be54d2f4c07fe8659d8f944d412958c268513849ba1`
- `experiments/hsw_english_replication_20261110_01/e1_long_context_run.py` `aebc1b0401e7a3c5a8a898872527da1601e8633d440ac8d61534f73396682868`
- `experiments/hsw_english_replication_20261110_01/e1_register_core.py` `8d13be14a50201e538562292292d67941c58aaefec2d511abb3066b2ea1baacc`
- 主项目 `assets/models/qwen2.5-3b-instruct-q4_k_m.gguf` `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`
- 主项目 `visualization/node_modules/katex/dist/katex.js` `6c900894155f53725496bd311d677cb3eb7614c0af52566294040a815850fec4`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/llama.dll` `211b91d86e67c49f12eb97992b45ae4c2fc797d6edab48637835a877c808890e`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml.dll` `06dfdff8b7b834c757ec5b5411abfc0f732604fb595eaaffbdc6da563523e8a1`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-base.dll` `3a0399fa51102a86824255beda9d021ea7e8cd2bd8ca448a43a9a80aa4829290`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/libomp.dll` `a12116ba72d1d6820407cf30be23da04ce79d6bb8a71a5ee71759c5a1faa6f1c`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-alderlake.dll` `1de7a0d14d70bd741f2e4cdfa959176fee26680d6fbc78c717c0bd19e20b6233`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-cannonlake.dll` `1451909b84c223739247088a0e03db0f89bcd83461f2af43f53d794727afddcd`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-cascadelake.dll` `74d79278bd20143d3e7deeb2b5c033555f9d621016a7152b5190a2fcbf30265c`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-cooperlake.dll` `737f0e96f23ca7d66c8dc55eace36ebbfd47770a9a228c804ffff5bf66f933a8`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-haswell.dll` `85d9ffd6f84fd0ec01586420b935ac4d5a5c9a1ab76b533eb3ddc060c1fe2869`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-icelake.dll` `41ca727e74b171983ea9afe0250553706c09225c10a8c6ad72a619f9189279a8`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-ivybridge.dll` `39752b7667cb34b3bbd06178fac83803f6089771d43873a9c81015d2a98c280b`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-piledriver.dll` `65bef2ae4f69256d9aff053a6fff1abdbd33acdbc51ede863d8bc5bd43c53ee8`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-sandybridge.dll` `5359624dee5670cb299c08f4a49347f7a6f4d0df35ed4c0a91164e4d771b3e23`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-sapphirerapids.dll` `a7a395d0e49f182240c9a2ed1d623398911506bdae418baf161354541aa06a89`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-skylakex.dll` `6bd53dc5731c5b9e4d3fbf98a9dc5b3ce76d357be9a579bc6c8cedac035462e8`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-sse42.dll` `1e1700e6b6eef26b6abb0bc68669b6ee9fdad2b8d00058e491cb5160eb54afc2`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-x64.dll` `81877c8787f9d5680b990f4cf5f8b89ba5b02ee5064b36abfd53d9d2ffb50916`
- 主项目 `var/cache/hsw_k12_pilot01_runtime/b12110/ggml-cpu-zen4.dll` `b5c1eec79e83878303acfa774f1275d9e025493b2c23f2a01af09fe985cdc21a`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/.gitattributes` `98ccb431c012ebfe976280fbd45aea4cec7409935868ccecf3954370f96732a1`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/config.json` `953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/config_sentence_transformers.json` `061ca9d39661d6c6d6de5ba27f79a1cd5770ea247f8d46412a68a498dc5ac9f3`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/data_config.json` `32edcb108fc2516b920734a862ae0692bcae1c5d45d5f8d972cb0d53434a4c54`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/model.safetensors` `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/modules.json` `84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/README.md` `dcd602d2fd35c203a247304a06fec6654a12f7941b739f9221a064fe8dc3b7f0`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/sentence_bert_config.json` `fc1993fde0a95c24ec6c022539d41cf6e2f7c9721e5415d6fb6897472a9cd4b7`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/special_tokens_map.json` `303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/tokenizer.json` `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/tokenizer_config.json` `acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/train_script.py` `f9b98b9d203d728cbf93ccdbae84131ab926541b56196f11d1385fed0b4d1a07`
- 主项目 `assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/vocab.txt` `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`
