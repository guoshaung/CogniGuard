# 公开方法与重叠核查（S0，非效果结论）

## 后处理与工具包名称

[ICML 2026论文](https://proceedings.mlr.press/v306/fernandez26b.html)以及[方法/实验全文](https://arxiv.org/html/2512.16904v1)研究先有正文、再由语言模型改写嵌入统计水印。方法§3/附录A区分采样、PRF、去重和检验；实验§4比较模型、计算分配、语义相似、长度及代码功能。原文也指出仅去重不足以保证任意密钥的理论p值有效，并用大量无标记材料核验，而非靠单key阈值承诺误报。本轮不做其大规模复现或用相似度替代知识正确性。

本地已核验[官方代码](https://github.com/facebookresearch/textseal) commit `0b76bc64013081c570b8633d3d3585e3ee9a495a`。本轮B2明确是**TextSeal工具包Greenlist**，不是Gumbel-max、双密钥TextSeal或TextSeal2。双密钥也不是多bit消息或完整换钥协议。官方Greenlist在before-top-p模式加入logit偏置，单keyp由官方独立公开检测返回；它的密钥规则和历史HSW-PCG64不是同一种实现。所有归因另加登记及整体扫描规则。

## 真多比特候选审查与事前选择

[NAACL 2024论文](https://aclanthology.org/2024.naacl-long.224/)方法§3.2/算法1把位置分配与多色词表结合：由公开历史重建消息位置，按对应位/进制数字偏置，提取时累计颜色计数并取每位多数。附录A与§4比较长度、消息量、质量及攻击，不能把bit准确率当整条交付身份成功。[官方MPAC源码](https://github.com/bangawayoo/mb-lm-watermarking)固定 `07911026575f01400bc03d76a4f2aff498d0911f`，Apache2.0；无需另一个代理模型。本轮选择它是因为明确许可、现有CPU Torch兼容和可用逐步processor，不是看新结果选赢家。将其接入Qwen原文改写是工程适配，非原论文原样复现。

[ICLR 2024 Balance-Marking](https://proceedings.iclr.cc/paper_files/paper/2024/hash/abdc8c031aa6c6917c3b593166e5e340-Abstract-Conference.html) §3–4把消息区分和质量约束共同写入编码目标，再用代理语言模型构造概率平衡划分；实验还涉及提取代价、容量及攻击。其[官方实现](https://github.com/lancopku/codable-watermarking-for-llm)的完整Balance路径依赖额外代理模型和Tokenizer兼容；本轮无权下载新权重，不以省掉代理模型的Vanilla-Mark冒充Balance。它是已核查强近邻，不是本轮已运行方法。

[USENIX Security 2025论文](https://www.usenix.org/conference/usenixsecurity25/presentation/qu-watermarking)§3–4采用伪随机片段分配、消息编码及增强恢复，并给出与具体条件有关的鲁棒界；§5比较消息匹配、提取时间及攻击。代码入口为作者[Zenodo归档](https://zenodo.org/records/14729410)及关联的segment-watermark仓库。该方法优先被纳入审查；本轮实际选择MPAC为第一多bit适配路线。没有运行USENIX算法时，不借用其97.6%等论文结果作为本机指标，也不将其界移植到另一PRF/语言。

[USENIX Security 2026 DMW](https://www.usenix.org/conference/usenixsecurity26/presentation/zhai)方法§4以句子语义投影为位串，联合稳健性/质量失真代价，用周期优化STC选择满足码约束的改动，再重建句子；§5包含容量、质量及攻击评估。这直接覆盖“有代价的消息嵌入、语义稳定与质量权衡”近邻。单纯增加issueID、风险名词或签名不能据此声称新机制；本轮不假装已复现其投影模型与STC。

## 离平台关联与密钥周期

[C2PA 2.3 Soft Binding](https://spec.c2pa.org/specifications/specifications/2.3/softbinding/Decoupled.html)讨论元数据脱离后，通过水印/内容指纹向保留的repository查回manifest。它与本轮“文本关联登记”高度重叠，不自动解决中文接收方水印，也不认证法律归属。可疑文本不能凭空恢复已经彻底丢失的映射。

[NIST originator usage](https://csrc.nist.gov/glossary/term/originator_usage_period)与[recipient usage](https://csrc.nist.gov/glossary/term/recipient_usage_period)区分用于新保护与处理历史保护的使用期限。本轮借此明确旧key停止新发行≠历史检测材料立即删除，未声称获得NIST认证或前向/后向安全。

## 可运行性与研究定位

本轮能够独立检验登记、epoch切换、旧身份保留、许可状态独立、全候选公开检测及重复文本歧义。这些是可用系统能力，而非新水印算法。只有在同输入、同候选和可解释整体误归因/拒识工作点下，出现可复核的准确性—保真—修改—成本代价，才讨论机制改进；尚不能因为多key命中就认定新研究信号。
