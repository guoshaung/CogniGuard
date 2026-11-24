# Chronology 基线

Chang 与 Echizen 的论文发表于 Royal Society Open Science，DOI 为 10.1098/rsos.251988。论文 PDF 和两个出版方补充附件已下载，附件哈希见 `upstream.json`。出版方集合中两条记录标题分别指向主程序和多轮运行脚本，但实际 ZIP 只包含 PDF、EPS 图和系统元数据，另一个 TXT 只包含图注。原作者实现、随机种子和精确的 Llama checkpoint 仍缺失。 [论文全文](https://arxiv.org/html/2504.12612v2) · [出版方附件集合](https://doi.org/10.6084/m9.figshare.c.8536973)

## 论文设置

- 同一个 1B Llama 实例扮演所有智能体，身份随机分派，无角色专属提示。初始文本为图灵 1950 年论文末段。每一步只给当前智能体上一步生成的文本与续写指令。使用温度 0.3、top-k 1000、top-p 0.9、每步最多 150 个生成 token。
- 每个可能的有序身份历史对应词表上的定重二进制向量。嵌入器在生成每个 token 时给向量命中的词加 logit bias。检测器对可见文本重分词，穷举码字，以命中数最大者给出解码。下一轮把已解码的历史前缀与当轮身份连接，再重新嵌入完整历史。这个机制要求协作方部署同一词表和码本。
- 论文扫描智能体数 2–4、时序长度 3–6、偏置强度 1–3，每格 100 个试次。报告逐步身份符号准确率、生成困惑度，以及 WordNet 词语替换从 0% 到 70% 的稳健性。 [论文 §3–4](https://arxiv.org/html/2504.12612v2)

## 实现差异

`reproduce.py` 按论文重实现码本、加偏采样、公开文本解码与反馈。选用公开镜像 `unsloth/Llama-3.2-1B`，冻结修订 `9535bd9b1d1dea6acafbdc4813b728796aeb28da`。论文未列出模型仓库、模型修订、具体 prompt 格式、码本种子或 tie-breaking。此处使用普通续写提示、自定种子与固定顺序处理并列票数。

最小设置的码本有 `3^3=27` 个状态。论文写明基码字宽度等于状态数，按 50% 覆盖生成定重向量，再重复和补齐到模型词表。当宽度为 27、词表为 128256 时，重复 4750 次产生 61750 个 1，最后 6 位无法补足到 64128 个。本实现将奇数基码字宽度加 1，使公开文本解码比较仍使用覆盖率相同的唯一向量。该实现选择影响码本及结果，应与作者脚本区分。

## 模块自检

用相同码本、150 个独立 Token 和均匀合成词表，生成 300 条一组。在偏置强度 0、1、2、3 下，精确码字解码分别为 16/300、299/300、300/300、300/300。这只验证加偏采样与码字解码管线，输入为合成 Token。复现运行命令见下方。

## 真实语言模型试跑

同一组 2 个智能体、3 步链、每种偏置 2 条链，CPU 运行。无偏置在第一、二、三步的正确完整前缀数分别为 1/2、0/2、0/2，逐符号准确率分别为 50.0%、50.0%、33.3%。偏置 2 时分别为 1/2、1/2、0/2，逐符号准确率为 50.0%、50.0%、16.7%。总生成时间 453.6 秒，单步平均 37.8 秒，GPU-hours 为 0。

偏置 2 的一条链首步把 `[1,0,0]` 解码为 `[2,2,2]`，历史错误进入后继嵌入。另一条链首两步正确，第三步在 2 个生成 token 后结束，公开文本只有 1 个可重分词 token。另有多条续写偏移到程序代码或重复内容，留存原文供复核。该样本量及模型、码本差异限制了对论文准确率的直接比较。逐步原始数据、参数和图保存在 `var/results/hsw-st/provenance/chronology/llama-smoke`。

```powershell
python experiments/hsw_provenance/chronology/reproduce.py --out var/results/hsw-st/provenance/chronology/token-smoke
python experiments/hsw_provenance/chronology/reproduce.py --out var/results/hsw-st/provenance/chronology/llama-smoke --model D:/pycharm/CogniGuard/assets/models/chronology-llama32-1b-9535bd9 --trials 2 --bias 0 2
python experiments/hsw_provenance/chronology/summarize.py var/results/hsw-st/provenance/chronology/llama-smoke
```

本论文测量逐轮主动重嵌的参与者历史。在 HSW-ST 评测中应保留两个独立标签，实际参与过传播的发行方，以及终稿中确有证据支持的发行方。协作传播继续携带某发行身份时，已删去的知识也可能被错误归因。论文实验没有评估无配合改写中被动存活的水印、多源融合、发行 ID 恢复或知识正确性。
