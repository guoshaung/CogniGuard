# OpenStax 来源追踪传播框架

受控 Pilot 从已冻结的 38 份 OpenStax 讲解选取 12 份，数学、物理、统计各四份。保留完整底稿、原题、来源 URL 和底稿 SHA-256。每份在受控传播中以三条可计算验证的事实摘要发行。每条事实有原句、轻度改写和强度较高的改写。两位发行人各发行同样的来源文本，原始发行人由实验干预记录。完全相同的公开文本可来自两条发行记录。

`cases.jsonl` 包含 552 个端点。其中 540 个来自 180 条传播链在第 1、3、5 轮的观察，另外 12 个是独立无来源输入。每条传播链含 1、2 或 3 个来源。每轮的 `units` 记录实际输出、事实、来源和发行 ID。原样转发保持投递后的字节，摘要随机删除事实，轻改写替换约四分之一的事实表述，强改写替换约三分之二且每偶数轮丢掉首条事实，截断保留当前前缀约 70% 的完整事实。样本在进入第一轮前按同一规则排列和打乱。摘要和截断以事实边界为单位，因此同一事实的部分保留尚未建模。

第 5 轮，原样转发和轻改写保留 100% 的受控事实，强改写 59.26%，摘要 3.70%，截断 0%。摘要保留 11.11% 的来源，截断保留 0%。这些比例由受控操作决定。语义标签沿用事实记录，不能估计真实模型的删改规律。轻改写的个别支持条件有所简化，例如抛体首句未重复重力数值。事实保留统计的口径是已标注的核心主张。

发行分配依固定序号奇偶，部分来源只在划分内出现一种发行 ID。发行级结论同时受发行分布和内容歧义影响。端点按整条传播链分组校准与测试。校准 138 条，测试 414 条。各组中的重复观察共享上游文本，样本独立性以传播链为单位。

```powershell
python -B experiments/hsw_provenance/propagation/build.py --out var/results/hsw-st/provenance_20261124/replay_12
python -B experiments/hsw_provenance/propagation/build.py --all --out var/results/hsw-st/provenance_20261124/controlled_38
```

38 份底稿扩展已运行，生成 76 条发行记录和 1,748 个端点。所用全量事实仍是 OpenStax 讲解的短摘录。全部端点的来源与事实子集、分轮兼容和未标记回放一致性由构建器检查。受控数据 GPU 小时为 0。真实模型的传播保留度另行核对。

## 文件

- `sources.json` 保存完整底稿、用于受控试验的三事实摘录和改写真值。
- `releases.json` 保存发行关联及公开文本摘要。
- `cases.jsonl` 保存端点与分轮证据。供评测器输入的查询只读 `text`。
- `retention.json` 保存源和事实保留率。
- `config.json` 保存样本范围、种子规则、校准划分及哈希。
- `build.replay_marked` 在同一保留事实和改写决策下运输行对齐载体。任何原句改写都替换整句载体，转发继续保留其字节。该规则提供严格控制，不能估计生成模型在只保留载体时造成的错误归因。

## 本地模型传播预检

在 CPU 上运行 Qwen2.5-0.5B-Instruct。模型完成两条五轮传播链的摘要与改写，共六次调用，输出 674 token，累计 16.11 秒，平均每次 2.68 秒。转发与截断使用确定性文本操作。单来源链在第 1、3、5 轮分别保留 3/3、3/3、1/3 条事实。三来源链分别保留 9/9、5/9、1/9。融合摘要删除了书架分组的全部事实，并把电容电压 6.32 V 错写成 RC 的值，后两次改写延续这一知识错误。所有十份输出都由 Codex 阅读并批注，原文本、配置和证据位于 `var/results/hsw-st/provenance_20261124/model_smoke_05b`。7B 的本机纯 CPU 测试因 4.1 GiB 内存需求高于可用 2.1 GiB 而失败。0.5B 的结果只适用于这两条示例。

```powershell
python -B experiments/hsw_provenance/propagation/llm_smoke.py --model qwen2.5:0.5b-instruct --out var/results/hsw-st/provenance_20261124/model_smoke_05b
python -B experiments/hsw_provenance/propagation/model_smoke_review.py
```
