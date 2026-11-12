# HSW-CERTINSERT-EVAL-03-LITE：扩大样本量（用于 arXiv v2 主表）

目标：把主结果的分母从几十扩到几百。方法完全冻结，不调任何参数。
预计总耗时：单卡 1–2 天，其中大部分是基线和压缩攻击的生成时间。
零付费 API。不修改 EVAL-01、EVAL-02 的任何文件。

## 0. 冻结（跑任何测试之前完成，并 commit）
- 方法：revision 09 + EVAL-02 的 Markdown 解析器 + 域内零假设校准（与 EVAL-02 相同）。冻结文件的 sha256 写入 `EVAL_FREEZE.json`。
- 新测试集 **T4**：从 OpenStax 中所有未被 T1/T2/T3/校准集使用过的章节里抽取 worked examples。
  - 目标 **400 篇**，physics、chemistry、biology 尽量均衡；biology 没有合格样例就如实记录，不得编造。
  - 抽样脚本和种子先冻结；与已有数据集做去重检查，结果写入 `DISJOINTNESS.json`。
- 新 LLM 生成集 **T5**：本地 7B 模型只看 OpenStax 题干生成讲解，**200 篇**。生成参数冻结，不重试、不修复。
- 不相交的未加水印对照：**1000 篇** in-domain worked-example 段落，加上 300 篇 held-out 通用段落（沿用旧的）。

## 1. 便宜部分：全量跑（T4 全部 400 篇 + T5 全部 200 篇）
| 系统 | 说明 |
|---|---|
| CertInsert | 冻结方法 |
| RC 随机连接词 | 相同词表、相同停止规则、相同检测器；不用锚点 keying（用全局 key 的随机 k=4 列表），不做结构保护，位置随机 |
| 指纹 | 全部样本 |

攻击（都是确定性的或只用 CPU）：无攻击、截图 OCR（PaddleOCR，参数沿用旧的）、开头 100 词摘录、中段 100 词摘录。

## 2. 贵的部分：固定子集，必须 100% 跑完
- 从 T4 中按种子抽 **100 篇**，KGW 和 Unigram 重写必须 100/100 完成。算力不够就减少攻击种类，**不允许少跑样本**。
- 压缩攻击：在这 100 篇上，对 CertInsert、RC、KGW、Unigram、指纹各做 1 次 70% 目标压缩。
- 每份压缩输出都要记录实际长度比，以及数值和公式是否完整。

## 3. 误报
- CertInsert、RC、KGW、Unigram 在 1000 篇 in-domain 段落和 300 篇通用段落上分别报告误报率。
- 共现检验：对 1000 个随机 key，在 in-domain 段落上算 p 值，报告 α = 0.001、0.01、0.05 时的经验误报率（Pr[p<α]）。

## 4. 报告口径
每个系统、每种攻击都要给出 planned、available、eligible，条件率和无条件率（以 planned 为分母），以及按源文本做 cluster bootstrap 的 95% 区间。
- 配对表：100 篇子集上所有系统都有输出的源。
- 容量：T4、T5 按长度分箱（<100、100–200、200–400、>400 词）。
- 交付 `figure_counts.json`，字段与论文 `figures/make_figures.py` 中的数组一一对应。

## 5. 不做（留给 v2 之后）
PostMark、人工自然度评审。
