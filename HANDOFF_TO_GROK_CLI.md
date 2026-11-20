# 交给 Grok CLI 的交接提示词（整份复制即可）

把下面从 `BEGIN_PROMPT` 到 `END_PROMPT` 的内容 **原样粘贴** 给 Grok CLI 作为首条任务。  
工作目录必须是：`/Users/MBP/Exp/RSILab`

---

BEGIN_PROMPT

# 任务：MM-FOPD-R — 用 xAI Grok API 在 EvoMemBench 上复刻 NO-MEM vs ACE

你是 **Grok CLI**（可开多个 sub-agent）。不要再问「是否继续」；按清单做到收尾文档写完为止。

## 0. 背景（只读）

- 工作区：`/Users/MBP/Exp/RSILab`
- Chat 侧已写好预注册与适配层，但 **不能 clone / 不能跑满量评测**。你来接棒执行。
- 已有目录：`mmfopd-repro/`（必读）
  - `R_PREREG.md` — 预注册（模型已改为 Grok）
  - `DEVIATIONS.md` — 偏离
  - `R_RESULT.md` — 待你回填数字
  - `final_decision.md` — 判定
  - `RUNBOOK.md` — 步骤
  - `adapters/xai_openai_client.py` — xAI OpenAI 兼容客户端
  - `adapters/patch_evomem_to_xai.md` — 接入说明
  - `.env.example` — 环境变量模板
  - `per_item.csv` — 表头占位
- **不要**使用 `reflexion/`、MAS-Lab、A-Evolve 任何代码。
- **不要**修改 EvoMemBench 的评分 / `run_batch_evaluate` 逻辑；只允许换 LLM 客户端。
- **不要**把 API Key 写进 git；只用 `mmfopd-repro/.env`（已在根 `.gitignore`）。
- 预算硬顶：**150 元人民币**。冒烟外推超预算 → 停止满量，写 R_RESULT 说明。
- 密钥：从环境或用户本机已有配置读取 `XAI_API_KEY`；**禁止向用户索要 key 明文写入聊天日志**。若缺失，写明要用户在 `.env` 自行填好后重跑，不要编造结果。

## 1. 科学问题（用户修订版）

在 **同一套 EvoMemBench 代码**、**同一子任务 CrossEp-Tool（CROSSEP-TOOL，4 环境 ×50=200，只做第一阶段）** 上，用 **xAI Grok（OpenAI 兼容 API）** 跑：

| 组 | 脚本（以仓库为准） |
|---|---|
| NO-MEM | `scripts/run_eval_no_memory_inenv_fc.sh` |
| ACE | `scripts/run_eval_ace_inenv_allcrossenv_fc.sh` |

回答：ACE 相对 NO-MEM 的增益方向是否还在；并与论文 arXiv **2605.18421** 表内数字并列（模型不同 → 标注 *not same-model strict repro*）。

原文曾用 DeepSeek-V3.2 + 方舟 batch；本次 **故意换 Grok**（用户要求），记入 DEVIATIONS。

## 2. Sub-agent 分工（建议并行）

**Agent A — 代码与论文**
1. `git clone https://github.com/DSAIL-Memory/EvoMemBench.git mmfopd-repro/EvoMemBench`（若已存在则 `git fetch` + 记录 SHA）
2. `git rev-parse HEAD` → 写入 `R_PREREG.md`（参考历史 HEAD 曾为 `3efc221`，以实际为准）
3. 读 README / scripts，确认 BFCL、依赖、启动方式
4. 打开论文 arXiv 2605.18421，**抄录** CrossEp-Tool 上 NO-MEM 与 ACE（或同义基线/自进化记忆）的成功率、分环境、token（若有）；注明表号/页码。若无 ACE 行，按原任务书改 SkillWeaver 并记 DEVIATIONS
5. 安装依赖（conda/venv 按仓库文档）

**Agent B — 模型接入**
1. 确认 `XAI_API_KEY`、`XAI_BASE_URL=https://api.x.ai/v1`、`XAI_MODEL=<控制台精确 id>`
2. 将 `mmfopd-repro/adapters/xai_openai_client.py` 接到仓库内 ArkBatchClient / OpenAI client 导入路径（见 `patch_evomem_to_xai.md`）
3. **最小 diff**：只换 endpoint/client；temperature/max_tokens/tools 原样透传
4. 所有客户端 diff 路径追加到 `DEVIATIONS.md`
5. 单次 ping：`chat.completions` 返回正常再继续

**Agent C — 冒烟与预算**
1. `bash scripts/run_smoke_tests.sh --only no_memory --limit 1`（路径以仓库为准）
2. ACE：`--limit-per-subset 2` 或仓库等价参数
3. 从日志统计 token，外推 **200×2 组** 费用（人民币）
4. 写入 `R_RESULT.md` 预算节；若 >150 元 → **禁止满量**，直接收尾并说明

**Agent D — 满量评测（仅预算通过后）**
1. 跑 NO-MEM 全量第一阶段
2. 跑 ACE 全量第一阶段
3. 原始输出保留在仓库默认 `cross_episode_results/runs/...`
4. 复制 summary / per_sample 到 `mmfopd-repro/artifacts/{no_mem,ace}/`
5. 不改评分脚本；用仓库官方汇总

**Agent E — 分析与文档收尾（评测结束后）**
1. 填 `per_item.csv`：sample_id, env, no_mem_success, ace_success, 四分类（both_win / only_ace / only_no_mem / both_fail）
2. 总体 + 分环境成功率；样本 bootstrap 95% CI（对样本重采样）
3. 与论文数字并列；ACE−NO-MEM 增益方向
4. 随机抽 10 条 ACE playbook，各用 2–4 句判断：可复用操作经验 vs 空话
5. 汇总 token（agent vs memory 若可分）、总费用、墙钟
6. 更新 `R_RESULT.md`、`final_decision.md`、`DEVIATIONS.md`
7. git：提交到分支 `codex/mmfopd-repro`（不要 commit `.env`）；可 push

## 3. 判定规则（写进 final_decision）

- **严格同模型复现**：本次不适用（已换 Grok）
- **Grok 迁移信号成功**：
  1. 全流程跑通且未改评分；
  2. ACE−NO-MEM 增益方向与原文一致（原文已抄录）
- **部分**：只满足一条件
- **失败**：跑不通 / 无合法 per-sample；或增益方向相反
- 教学任务迁移：仅当 Grok 线给出可解释信号后再谈；否则停止 MM-FOPD 探索

## 4. 红线

- 禁止伪造 per-sample 或成功率
- 禁止为凑数改解码参数、换子任务、缩样本（除非预算条款触发「停跑」）
- 禁止手写替代官方 judge
- 禁止提交密钥
- 跨环境 12 对默认 **不做**（第一阶段做完再写 R_RESULT；用户没加时再做）

## 5. 完成定义

同时满足才算完成：

1. `EvoMemBench` commit SHA 已写入预注册  
2. 论文表数字已抄录（或明确论文无该项并已切换对照方法）  
3. 冒烟日志 + 费用外推已写  
4. 若预算允许：两组 200 条结果 + artifacts  
5. `R_RESULT.md` / `per_item.csv` / `final_decision.md` 已更新  
6. DEVIATIONS 含全部 diff 与模型 id  

现在开始：先 `ls mmfopd-repro` 与 clone，再开 sub-agent 并行。

END_PROMPT

---

## 给用户的三句口令（可选，粘贴 CLI 前说）

1. 工作目录：`/Users/MBP/Exp/RSILab`  
2. 密钥只放 `mmfopd-repro/.env`，不要贴到对话里  
3. 完整任务见 `mmfopd-repro/HANDOFF_TO_GROK_CLI.md` 里 BEGIN_PROMPT 段
