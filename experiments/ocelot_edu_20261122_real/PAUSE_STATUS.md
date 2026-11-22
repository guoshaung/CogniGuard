# OCELOT-Edu 阶段 1b 暂停

暂停方式是 `kill -INT`。没有使用 Ctrl+Z，也没有使用 `kill -9`。预注册、旧目录和已有结果文件没有改。资产原文和 `.env` 不在仓库里。

## Git

HEAD：`185d9b684703bff8d28a14c08a5e04198139a8ad`

分支：`codex/ocelot-repro`

## 模型

暂停时 Ollama 已加载 `qwen2.5:7b`，清单短 ID `845dbda0ea48`，上下文 32768，GPU。中断后该模型仍在显存里，保留时间约 2 小时。

| 名称 | 清单短 ID | 清单 sha256 | 权重 digest | 规格 |
| --- | --- | --- | --- | --- |
| qwen2.5:7b | 845dbda0ea48 | 156bcbf71df68f7a6581fb4ab306ed921b8114d82b6eaeab5c0442785ea9b4c3 | sha256:2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730 | 7.6B，Q4_K_M |
| qwen2.5:7b-instruct | 845dbda0ea48 | 156bcbf71df68f7a6581fb4ab306ed921b8114d82b6eaeab5c0442785ea9b4c3 | sha256:2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730 | 与上一行同一份权重 |
| llama3.1:8b | 46e0c10c039e | 3fc95d284915704cf140b825abf5150af0d32fde95f55c081c9602d49d4547c0 | sha256:667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29 | 8.0B，Q4_K_M |

DeepSeek 模型名是 `deepseek-flash`。攻击阶段还没开始，这次暂停没有调用它。

## 停在哪里

阶段：`cost`。`arms`、`smoke`、`attack`、`decide` 都还没开始。没有 `cost_table.json`、`labels.jsonl`、`scores.jsonl`、`decision.json`。

代价网格一共 2280 条（5 个包 × 57 个视图 × 2 个模型 × 4 次抽样）。已写入 662 条，全部是 `qwen2.5:7b`，没有重复键。还剩 1618 条：这个模型还剩 478 条，然后是 `llama3.1:8b` 的 1140 条。

最后一条完整记录：`qwen2.5:7b`，`PKG-03`，视图 `U1,U7,U8,U9`，抽样 1。

中断前该文件末行和行数在两次读取里一致，末行是完整 JSON，并且以换行结束。随后进程退出。日志末行是 `EXIT:130`。

## 检查点和缓存

检查点：`experiments/ocelot_edu_20261122_real/artifacts/cost_checkpoint.jsonl`

- 条数：662
- 唯一键：662
- 解析失败：0
- sha256：`c227e57ac08cbbf876a28349f3739205a33e62dce9b51302d219347a615ea2a8`

缓存：`experiments/ocelot_edu_20261122_real/artifacts/cache/` 里没有文件。条数 0。代价阶段直接把计数写入检查点，不经过这层缓存。

日志 `artifacts/cost.log` 只留在本机，不提交。

## 恢复

可以从这条检查点接着跑。`cost` 会跳过已经写过的（模型、包、视图、抽样）组合，并追加新行。检查点不要删，不要改。

在仓库根目录执行：

```text
/usr/local/bin/python3 -u -m experiments.ocelot_edu_20261122_real.ocelot_edu.run_experiment cost
```

本机 `PATH` 上的 `python3` 是 3.15，没有 `cryptography`。上面这条用的是 3.14，恢复时不要换成另一个解释器。

看到日志里的 `COST_TABLE` 并且 `artifacts/cost_table.json` 已经写好之后，再按预注册继续。在那之前不要启动后面的阶段：

```text
/usr/local/bin/python3 -u -m experiments.ocelot_edu_20261122_real.ocelot_edu.run_experiment arms
/usr/local/bin/python3 -u -m experiments.ocelot_edu_20261122_real.ocelot_edu.run_experiment smoke
/usr/local/bin/python3 -u -m experiments.ocelot_edu_20261122_real.ocelot_edu.run_experiment attack
/usr/local/bin/python3 -u -m experiments.ocelot_edu_20261122_real.ocelot_edu.run_experiment decide
```
