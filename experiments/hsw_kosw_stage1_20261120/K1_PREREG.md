# K1_PREREG — Windows KOSW阶段1

日期：2026-11-20。以下第1–8节按用户任务书原文预注册，阶段2不执行。

1. 环境（Windows，CUDA GPU）
conda create -n kosw python=3.11 -y && conda activate kosw
pip install "torch>=2.2" --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers scipy numpy pandas scikit-learn sympy pint tqdm
# Ollama for Windows：https://ollama.com/download （已安装可跳过）
ollama pull qwen2.5:7b-instruct
嵌入模型（固定，不得更换）：sentence-transformers/all-mpnet-base-v2，维度 d = 768，输出 L2 归一化。把模型的 revision 哈希写入 PREREG。
生成模型（固定）：qwen2.5:7b-instruct（Ollama），temperature 0.8，top_p 0.95，每次调用的种子写入日志。
锚点抽取、结构规则、句子切分：复用 EVAL-03 的冻结实现，从 experiments/ 下对应目录导入，不得重写。
2. 数据准备
从 R_build 的 train 和 heldout 中各取讲解句。只取满足以下条件的句子：长度 8–60 词；不是标题或题干（按 EVAL-03 结构规则判断）。

train 取 3000 句，heldout 取 1000 句，按种子随机抽取。
记录每句的锚点集合 A(s)，即公式、数值带单位、术语的规范化串。
3. 构造三类句对（核心数据）
每个原句 x 构造下列三类变体，记录 (x, x', 类型)。

3.1 知识对 K：最小的、改变知识的编辑（自动生成，不用大模型）
对每个含锚点的句子，从下列规则中随机选一条可用的，生成 1–2 个变体：

规则	做法	必须通过的校验
K-formula	用 SymPy 解析公式（失败就跳过），然后三选一：交换两个变量 / 把一个 * 换成 / / 把一个指数加 1	sympy.simplify(old - new) != 0，即确实不等价
K-number	把一个数值乘以 {0.5, 2, 10} 中的一个，单位不变	新值 ≠ 旧值
K-unit	把单位换成同量纲的另一单位，但数值不换算（例如 5 m → 5 cm）	用 pint 验证物理量确实改变
K-term	把一个术语换成它的"同类术语"（见下）	新术语 ≠ 旧术语
K-polarity	increases↔decreases、higher↔lower、more↔less、positive↔negative 互换，或在系动词后插入 not	只改一处
同类术语表的构造（自动）：把 train 中所有术语锚点各自编码成向量，每个术语取余弦最近的 5 个同学科术语作为候选，再去掉词形相同的（单复数、大小写）。写入 term_siblings.json。

3.2 改写对 S：改写措辞、不改知识（模拟攻击者）
用 Ollama 生成，每句生成 2 个，提示词固定为：

Rewrite the following sentence in different words. Keep every formula, number, unit and technical term exactly as written. Do not add or remove information. Output only the rewritten sentence.
Sentence: {x}
只保留锚点集合逐字一致的结果（A(x') == A(x)）。

3.3 讲解对 P：小幅调整讲解角度（模拟水印要做的事）
每句生成 2 个，提示词固定为：

Rewrite the following sentence with a slightly different explanatory emphasis or framing (for example, what is highlighted first, or how the step is motivated). Keep every formula, number, unit and technical term exactly as written. Do not add new facts. Keep the length within ±20%. Output only the rewritten sentence.
Sentence: {x}
只保留锚点逐字一致、且长度在 ±20% 以内的结果。

数量要求：train 上 K、S、P 三类都要 ≥ 2000 对，heldout 上都 ≥ 600 对。不够就停下报告。

4. 估计三个子空间（核心算法，照抄实现）
记 e(·) 为嵌入向量（768 维，已归一化），句对差值 Δ = e(x') − e(x)。

4.1 三个协方差矩阵（只用 train）
import numpy as np, scipy.linalg as sl
def cov(D):                # D: (n, 768)，每行一个 Δ
    return D.T @ D / len(D)
CK, CS, CP = cov(DK), cov(DS), cov(DP)
delta = 1e-3 * np.trace(CS) / 768      # 正则项，固定
I = np.eye(768)
4.2 知识子空间 U_K：知识编辑动得多、改写动得少的方向
解广义特征值问题 C_K v = λ (C_S + δI) v，取最大的 r_K = 32 个特征向量：

lamK, VK = sl.eigh(CK, CS + delta*I)          # 升序
UK = VK[:, ::-1][:, :32]
UK, _ = np.linalg.qr(UK)                      # 正交化，得到 768×32 的正交基
4.3 载体子空间 U_C：讲解调整动得多，改写和知识编辑都动得少，并且与 U_K 正交
PK_perp = I - UK @ UK.T                        # 投影到 U_K 的正交补
A = PK_perp @ CP @ PK_perp
B = PK_perp @ (CS + CK) @ PK_perp + delta*I
lamC, VC = sl.eigh(A, B)
UC = VC[:, ::-1][:, :16]                        # r_C = 16
UC = PK_perp @ UC
UC, _ = np.linalg.qr(UC)                        # 768×16 正交基
保存 UK.npy、UC.npy、lamK.npy、lamC.npy，以及它们的 sha256。

直观含义：λ_C 表示"讲解调整在这个方向上的移动，是改写和知识编辑的多少倍"。λ_C 越大，水印放在这个方向上就越不怕改写，也越不碰知识。

5. 测量（全部在 heldout 上）
5.1 知识可分性（G1）
特征为 UK.T @ Δ（32 维）。在 train 上训练逻辑回归，区分 K 对（正类）与 S 对、P 对（负类）；在 heldout 上报告 AUC，按 K 的五种规则分别报告。 同时报告一个对照：只用余弦距离 1 − cos(e(x), e(x')) 做分类的 AUC。这一项用来证明"子空间方法优于简单相似度"，论文要用。

5.2 载体强度（G2）
报告 λ_C 的前 16 个值。

5.3 改写泄漏（G3）
每维能量比：

ρ_S = ( mean ||UC.T @ Δ_S||² / 16 ) / ( mean ||Δ_S||² / 768 )
ρ_S < 1 表示改写在载体方向上的移动小于平均水平。用同样的公式计算 ρ_P（讲解对），并报告 ρ_P / ρ_S。

5.4 知识安全（G4）
用同样的公式算 K 对的 ρ_K，即知识编辑在载体方向上的移动。

5.5 容量模拟（G5）——不改原文，只模拟
对 heldout 中每个原句 x，把它的 P 变体当作候选集合，最多 4 个。补生成到 4 个，提示词与 3.3 相同。
随机抽 1000 个密钥。每个 (句子, 密钥) 生成一个随机单位向量 r ∈ R^16（用 np.random.default_rng(seed)，seed 由密钥与句子编号决定；真正的 HMAC 留到阶段 2）。
句分数：s(y) = ⟨r, u(y)⟩，其中 u(y) = UC.T e(y) / ||UC.T e(y)||。
每句选得分最高的候选，记增益 g = max_c s(c) − s(x)；原句得分也算一个候选，所以 g ≥ 0。
报告 g 的均值与分布，以及达到 p < 10⁻³ 所需的句子数 n*：
零假设下 s 的方差 = 1/16，每句标准化得分 z = 4·s
所选候选的 E[z] = 4·E[max_c s(c)]
n* = (3.09 / E[z])²   # 3.09 是单侧 p = 10⁻³ 对应的正态分位数
5.6 零假设核对（G6）
在 R_calib 的未加水印讲解上，用 1000 个随机密钥计算每篇的统计量 T = Σ_j 4·s_j / √n。报告：

T 的均值、方差，以及与 N(0, 1) 的 KS 检验；
单侧 α = 0.01、0.001 的经验误报率。
理论依据：对任意固定文本，r 在球面上均匀分布，所以 s 的分布由维数唯一确定（(s+1)/2 ~ Beta(7.5, 7.5)），与领域无关。这一步检验实现是否正确。

6. 产出
K1_RESULT.md：第 5 节所有数字，加上第 8 节的逐条判定；
pairs_train.jsonl、pairs_heldout.jsonl（只存句子 ID 与变体文本，不存密钥）；
UK.npy、UC.npy、lam*.npy，以及 sha256；
figure_counts.json 中新增字段 kosw_stage1；
每类句对抽 20 个例子写入 EXAMPLES.md，便于人工检查 P 对是否真的"只是小幅调整讲解角度"。
7. 时间与算力估计
生成：约 4000 句 × (2 + 2 + 2) 个变体 ≈ 24000 次调用，每次约 40 token。GPU 上 7B 模型通常每秒几十到上百 token，预计数小时内完成（以实测为准，写入日志）。
嵌入与特征分解：几分钟。
8. 门槛（预注册，全部在 heldout 上）
编号	条件	门槛
G1	知识可分性 AUC（子空间方法）	≥ 0.90，并且比余弦对照高 ≥ 0.05
G2	载体强度	至少 8 个 λ_C ≥ 2
G3	改写泄漏	ρ_S ≤ 0.5，且 ρ_P / ρ_S ≥ 2
G4	知识安全	ρ_K ≤ 0.5
G5	容量	n* ≤ 10 句（中位数）
G6	零假设	KS 检验 p > 0.01；α = 0.01 与 0.001 的经验误报 ≤ α
全部通过：进入阶段 2，即在 R 上真正嵌入水印并做攻击测试。阶段 2 的任务书另发。
G6 不通过：说明实现有错误，修好后只重跑 G6，并记入 DEVIATIONS。
其他任一项不通过：停止，写明是哪一条、数值是多少。这本身就是一个可报告的结论：在该嵌入模型的空间里，不存在满足条件的载体方向。

## 评分前固定的执行细节

- 嵌入模型：sentence-transformers/all-mpnet-base-v2，revision e8c3b32edf5434bc2275fc9bab85f82640a19130；768维、L2归一化。先做术语编码，卸载后才加载Ollama，生成完卸载Ollama再编码完整句对。
- 随机种子2026112001。R_build文档按SHA256(KOSW-K1|document|ID)排序，前floor(0.7N)为train；句池由固定种子抽样。只读R_CORPUS中build/calib与该语料所含300篇生成讲解，不额外打开原测试文件。
- 复用capacity_shared_v32.nlp、e1_v4r7f_anchors.anchors、structure_adapter.split/allowed_offset，不重写这些组件。结构判断输入仅R自带题干；整句须不与受保护跨度重叠。
- K每句在可用的五规则中均匀随机选规则，再选一项编辑，固定随机产生1–2个不重复变体；公式解析失败跳过该公式，不换解析规则追求数量。数值变体单位文本不动。
- 同类术语仅从train中的T:锚点取得，按冻结spaCy lemma排除同词形，按余弦降序/字母序取五个同学科候选；heldout术语不用于建表。
- Ollama固定qwen2.5:7b-instruct，temperature=.8、top_p=.95、单请求顺序执行、num_predict=256；用任务原提示、每次记录种子。截断原样记录，只按任务锚点与P长度条件保留。拒绝项不重试；技术中断记录启动标记，不静默补调用。
- 每句S和P先各2次；heldout P另补2次，供G5候选最多4项使用。这两项不计入初始P最低数量门槛。K最低数量不够时先停止，避免无用的生成。
- 阶段3生成数量达到门槛后，严格用给定协方差、广义特征值与QR步骤；G2报告train估计的lamC前16值（任务原算法），其余评测使用heldout。
- G1 LogisticRegression(max_iter=1000,random_state=2026112001)，其他sklearn默认；余弦单特征用同样训练/留出方式。规则子类AUC与共同S/P负类对比，无该规则时报告不可用，不补样本。
- G5每个heldout原句使用最多4个通过锚点/长度检查的P候选加原句，原句保证gain>=0。1000个随机诊断密钥各32字节，仅留本地、公开SHA256；每句对1000密钥求E[z]与n*，再报告句间n*中位数。E[z]<=0记无有限n*。
- G6每个R_calib文档使用相同8–60词讲解句筛选；每个密钥下句方向由密钥和文档内句ID派生、标准正态向量归一化。零合格句文档标不可评分。T统计按全部可评分文本×密钥组合报告，同时保留组合相关性的统计边界。
- 不将KS或经验FPR一次未达标自动归为代码错误；先检查实现，仅有具体实现错误才按任务允许修复G6，禁止通过换种子、丢弃文本或调显著性门槛取得通过。
- 失败结论限定为这次固定模型/样本/算法未通过门槛，不声称已经证明所有可能载体方向均不存在。

## 已核对资产与数据

- Ollama digest: 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e
- 数据准备：{"seed": 2026112001, "available_sentences": {"train": 10305, "heldout": 4507}, "requested": {"train": 3000, "heldout": 1000}, "status": "PREPARED_NO_PAIR_COMPUTATION"}
- 数据与代码承诺见K1_FREEZE.json；预注册未推送前第3步不运行。
