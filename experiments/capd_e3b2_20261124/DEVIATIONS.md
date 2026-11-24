# 与任务书 `E3B2_TASK_FOR_CLAUDE.md` 的差别（全部发生在冻结之前）

| 项目 | 任务书 | 实际 | 原因 |
|---|---|---|---|
| 攻击者 | 百炼 `glm-5.3`，关闭思考模式 | 百炼 `kimi-k3` | `glm-5.3` 无法关闭思考模式。2026-11-24 试调时，平台对 `enable_thinking=false` 和 `thinking.type=disabled` 都返回 400："The value of the enable_thinking parameter is restricted to True"。按任务书第 6 节改用 kimi-k3 |
| 攻击者温度 | 0.7 | 平台默认值（请求中不传 temperature） | 百炼对 kimi-k3 返回 400："Parameter 'temperature'=0.7 is not supported for kimi-k3 model" |
| P1 模型名 | "DeepSeek 官方 API 的通用模型" | `deepseek-flash` | 官方 `/models` 只列出 `deepseek-flash` 和 `deepseek-v4-pro` 两个模型 |
| 攻击规模 | 100 个秘密（超预算时可降到 60） | 按费用规则在 50 元以内尽量多做，预计约 34 个 | 每次调用约 0.025 元，降到 60 个秘密也需约 75 元。规则在冻结前写定，只取决于费用（预注册第 6 节） |
| 被攻击的视图 | 未指明用哪个模型的改写 | 只用 P1 的改写 | 预算 |
| H3 的统计量 | 命中率的 95% 上界 | p(s\*) 均值的 t 上界；命中率加 Wilson 上界作为敏感性分析 | 每个视图只有 5 次采样，命中率版本会把 \|𝒮_u\| ≥ 4 的视图机械地判为超标（预注册第 5 节） |
| 改写提示词 | 原文 | 原文 + "用英文输出，只输出改写后的话" | 题目、单元名称和两个计量器都是英文的 |

## 冻结之后（2026-11-24）

| 项目 | 情况 | 处理 |
|---|---|---|
| 百炼账户欠费，攻击中断 | 攻击开始约 17 分钟后，百炼对所有模型返回 400："Access denied, please make sure your account is in good standing"（错误码 `#overdue`）。中断时 kimi-k3 正式攻击完成 12 个秘密，另有 6 个只完成一部分，其余 82 个没有合法输出；欠费之前的改写已全部完成 | 这是外部的账户中断，不是模型失败，所以**只对这一种错误**加了重试开关 `attack.py --retry-denied`。账户恢复后，按冻结的攻击顺序和 50 元上限继续跑。其他失败仍然记为缺失。在攻击完成之前，不看任何 A2 的结果 |
| 攻击者再次替换，A2 从头重跑（用户决定，2026-11-24） | 用户充值后，百炼按量付费账户仍然欠费；之后改开 token plan。token plan 上没有 kimi-k3；glm-5.3 仍然关不掉思考模式；**glm-5.2 可以关闭思考模式，接受 temperature 0.7**，试调 5/5 输出合法 JSON | 攻击者改为 token plan 上的 `glm-5.2`，temperature 0.7。A2 在全部 100 个秘密上从头重跑，按冻结的攻击顺序进行，每个视图 5 次采样。token plan 是套餐计费，不对 50 元上限计费，所以预注册第 6 节"按预算截断"的规则在这里不起作用，按任务书原定的 100 个秘密执行。kimi-k3 已经得到的部分结果（`items_attack_kimi-k3_unused.jsonl`，仓库外）一直没有打开，**不参与分析**。H2–H4 的统计量和阈值不变。这次替换发生在看到任何 A2 结果之前 |
