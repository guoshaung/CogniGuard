# ICML 2025 多比特文本水印复现核查

**原生能力复现受阻，阶段判定 BLOCKED。** 官方输入、评测源码和公开预训练资产已核对。主论文 TinyLlama 权重在作者公开 GitHub 与 Hugging Face 名录中未找到。作者后来发布的 Qwen 演示使用不同模型，原入口在同一张 CUDA 卡上加载两套 7B 编码器和 1.5B 解码器，再加载 MPNet。本机 RTX 4070 总显存 8,188 MiB，低于单套未量化 7B 编码器的 BF16 权重内存。预检停在资源门槛，实际模型预测数为 0。 [论文](https://proceedings.mlr.press/v267/xu25k.html) · [官方固定版本](https://github.com/xiaojunxu/multi-bit-text-watermark/tree/7439ecee8891c6e8226f02fa8c1a650d3e10aaff)

## 原论文和发布版协议

- 主论文在 C4 RealNewsLike 上默认 128 Token，使用两套 TinyLlama-1.1B 改写器和同架构解码器。作者先用 Pegasus 改写对做监督初始化，用 JS 散度拉开两套编码器，再训练句级判别器，最后以 PPO 联合优化水印、语义相似和 KL。主设定报告 10,000 步、batch 4、λw=0.1、λs=1.0、λk=0.02。附录 Table 7 使用 Llama-2-7B。
- 每个句子承载一位。官方实现根据当前位选择改写器的 logits，句界推进载荷位置。解码器独立给每句评分，分数大于 0 判 1。官方评测用与待检 key 对齐的有符号平均分做文档 ROC AUC，对照为原人类文本。Bit Accuracy 按已解出的句子位计算，随输出句数变化。完整载荷恢复应把缺位也记为失败。错误载荷接受率需要预先冻结的接受规则和独立负例，论文 AUC 无法替代这两项。
- 原论文的扰动为 5%、10%、20% 随机词元替换，逐句英语→西班牙语→英语回译、Llama-2-7B 逐句改写和 Pegasus 逐句改写。另报告见过部分扰动的 AdvT 行。重分句、整篇摘要、多来源融合和多轮传播属于迁移验证。
- 2025 年 7 月的公开演示采用两个 Qwen2.5-7B Instruct 检查点、一个 Qwen2.5-1.5B 判别器和 GitHub 发布的 value head。默认 batch 4，Best-of-4，512 的输入长度参数，最多新增 512 Token，示例为交替 1/0 的 key。最终选择结合位准确、MPNet、ROUGE-L 等分数。运行环境记载 Python 3.11、PyTorch 2.4.1、H100 128 GB。依赖清单锁定 torch 2.4.1+cu118、Transformers 4.46.3、datasets 3.1.0。 [官方演示](https://github.com/xiaojunxu/multi-bit-text-watermark/blob/7439ecee8891c6e8226f02fa8c1a650d3e10aaff/watermark_demo.py) · [官方评测](https://github.com/xiaojunxu/multi-bit-text-watermark/blob/7439ecee8891c6e8226f02fa8c1a650d3e10aaff/eval_utils.py)

## 官方结果和本机实际记录

论文 Table 1 报告 AUC 0.9981、Bit Accuracy 0.9563、平均 5.57 位、MPNet 相似度 0.8739。Table 3 普通训练版本的 Llama 改写后 AUC 0.8649、Bit Accuracy 0.7137，AdvT 为 0.9239 与 0.8487。完整载荷恢复率及错误载荷接受率未在这些表中报告。这里是论文原值，本机六项指标全部记为未测。

本机运行了原版句界函数，两个官方 demo 原文各分成 8 句。验收了官方 C4 文件的 10,000 行和文件摘要。这个句数反映输入，实际生成句数和载荷尚未观测。官方 value head 已下载并记录 SHA-256。Hugging Face 两套编码器各有七个权重分片，每套约 30.46 GB，解码器约 3.09 GB。解码器已实测 HTTP 206，1 MiB 区间约 74 KB/s，六分钟传输预算仅能下载约 30 MiB。此路径可访问，无法在本轮提供完整权重。 [固定配置](CONFIG.json) · [预检结果](preflight.json)

**语义质量实查。** Table 6 公布的一对文本中，退休缴费用于覆盖总成本的比例从 50% 改为 5%，而论文报告的相似度仍为 0.8947。另一对文本把每年出现腹泻的频次陈述改成“比以前更容易生病”。这是对公布样例的逐条检查，无法给出 OpenStax 的知识保真率。 [论文附录 Table 6](https://raw.githubusercontent.com/mlresearch/v267/main/assets/xu25k/xu25k.pdf)

## 相关方法和迁移门槛

- SemStamp 对句嵌入做 LSH 划分并在生成时拒绝不合格的句子，k-SemStamp 用 k-means 分区替代 LSH。两者公开目标是检测生成文本的水印，CogniGuard 若以来源 ID 为目标，需要另行设计载荷与验证。 [SemStamp](https://arxiv.org/abs/2310.03991) · [k-SemStamp](https://aclanthology.org/2024.findings-acl.98/)
- HSPMark 参考实现用前句滑动窗的语义嵌入与训练 MLP 生成投影，检测按后续词元累积软证据恢复多位消息。它和 Xu 等人的每句改写器选择有不同的生成约束。公开实现列有 24-bit 生成结果和改写攻击脚本，本轮只做机制对照。 [HSPMark](https://github.com/Kcrystal55zz/HSPMark/tree/HEAD/HSP-Watermark)

迁移状态为 **未启动**。38 份历史材料留作开发，独立留出、载荷位数、拒绝阈值和生成预算须在原生能力可运行后冻结。迁移协议应保留同源发行共享载荷、两种真实传播模型、长度分层、1/3/5 跳、相同文本与候选核验预算，以及全来源和内容候选内两种随机基线。相对 BGE+NLI 增量和风险感知分配的两道门槛均仍待验证。历史 R1 STOP 仍归于 `06d9259`。

预检复现使用固定提交的原仓库。临时目录包含 `gen_utils.py`、`watermark_demo.py` 和 `watermark_test_text.txt`。可选加入官方 `data/c4-len128-test.json`，保留文件名。调用 `python experiments/rkw_official_multibit/upstream_preflight.py <该目录>`。原生模型实验尚无可执行的 TinyLlama 检查点来源，当前配置是资源核查记录。公开 Qwen 的官方入口仍为作者仓库内的 `python watermark_demo.py`，通过资源门槛后需先冻结其运行方案。
