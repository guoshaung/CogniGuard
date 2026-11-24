# E9/E10 检索记录（2026-11-25）

结论：**BLOCKED**。没有找到已冻结的 CA-PD E9 或 E10 协议。远程分支 `docs/research-sync-20261124`（`1de55a0471097e16cdaf1bdb4f2c1929271413de`）上的两份文件自己写明「草案，未冻结」，并且写明冻结之前不得跑网格。本检出 HEAD `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609` 里没有这两份文件。水印 `stage9` / `stage10` 脚本不是 CA-PD E9/E10。

下面每条都是实际执行的命令和结果。没有打开含密钥的文件内容。

## 1. 本仓库分支与工作树

命令（目录 `/Users/MBP/Exp/CogniGuard/CogniGuard`）：

```
git branch -a
git worktree list
```

`git worktree list`：

```
/Users/MBP/Exp/CogniGuard/CogniGuard                 893c6b3 [dev/confidential-secrets]
/Users/MBP/Exp/CogniGuard/data-confidential-datasets 44fd1f6 [data/confidential-datasets]
/Users/MBP/Exp/CogniGuard/e3b2                       1bb9a6a [exp/e3b2-paraphrase]
/Users/MBP/Exp/CogniGuard/e5-synthetic               dd913fd [exp/e5-synthetic]
/Users/MBP/Exp/CogniGuard/e6-eedi                    f16a2b1 [exp/e6-eedi]
/Users/MBP/Exp/CogniGuard/predicate-meter            d4c9b3c [dev/predicate-meter]
```

`git branch -a` 有本地与 `origin` 的 main、codex/*、data/confidential-datasets、dev/confidential-secrets、dev/multi-principal、dev/predicate-meter、docs/multi-principal、exp/capd-eval、exp/e3b2-paraphrase、exp/e5-synthetic、exp/e6-eedi、exp/e7-sumleaks、资源测溯源返还。本地 `git branch -a` **没有** `docs/research-sync-20261124`。没有名为 E9 或 E10 的分支。

另外存在的 grok 工作树（均在 `dev/confidential-secrets`，`893c6b3`）：

- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d1-71f2-bab2-9aaefa8a29cf`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6dda8a04b8e5`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6de9760b7b95`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6dff7c8a8d34`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6e0ea5c57d54`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6e1f7ea0930e`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c90-4db2-7140-9947-ed9266fb747d`
- `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c90-4db2-7140-9947-edae789b7021`

## 2. 提交说明

命令：

```
git log --all --oneline --regexp-ignore-case --grep='E9\|E10\|PREREG_E9\|PREREG_E10' -n 80
git log --all --oneline --regexp-ignore-case --grep='PREREG_E9' -n 20
git log --all --oneline --regexp-ignore-case --grep='PREREG_E10' -n 20
git log --all --oneline --regexp-ignore-case --grep='E9/E10' -n 20
git log --all --oneline --regexp-ignore-case --grep='E9' -n 30
git log --all --oneline --regexp-ignore-case --grep='E10' -n 30
```

`PREREG_E9`、`PREREG_E10`、`E9/E10`、单独的 `E10`：空。

单独的 `E9` 以及第一条组合式 grep 只命中：

```
51420f4 Revert "Add discrete-secret fields and value commitments to targets"
```

正文是 `This reverts commit 5eb9f669c601b93c9e5f7cfe998ad970cb087049.`。子串 `e9` 出现在该哈希的 `cfe998` 里，不是实验编号。

## 3. `git grep`（各工作树的 HEAD）

命令（对每个工作树）：

```
git -C "$wt" grep -n -I -e 'PREREG_E9' -e 'PREREG_E10' -e 'E9/E10' HEAD
```

本仓库 HEAD 以及第 1 节列出的 5 个兄弟工作树、8 个 grok 工作树：全部 `GIT_GREP_EMPTY`。没有匹配行。

本检出里已有的扫描备注 `experiments/parallel_x_20261124/x4_consistency/results/e9_e10_status.txt` 只写了「BLOCKED: no frozen E9/E10 definition in this checkout」。它不在 HEAD 上，所以 `git grep HEAD` 看不到它。

## 4. 文件名

命令：

```
find /Users/MBP/Exp/CogniGuard /Users/MBP/Documents \
  \( -iname '*e9*' -o -iname '*e10*' -o -iname '*PREREG*' \) -print
```

未剪枝时 `COUNT=4330`。绝大多数是内容哈希文件名（OCELOT 缓存 JSON、`.pnpm-store`、`node_modules`、`.git` 包），没有打开这些文件。

去掉 `.git`、`node_modules`、`.pnpm-store`、`__pycache__`、`cache`、`artifacts` 以及纯十六进制长文件名之后，与协议相关的名字是已冻结的 E2–E7 预注册，以及图像水印 stage9/stage10。**没有** `PREREG_E9*`、`PREREG_E10*`、`capd_e9*`、`capd_e10*`。

预注册文件名（不是 E9/E10）：

- `/Users/MBP/Documents/PREREG_E2.md`
- `/Users/MBP/Documents/PREREG_E3a.md`
- `/Users/MBP/Documents/PREREG_E3b.md`
- `/Users/MBP/Documents/oneTask/PREREG_E5.md`
- `/Users/MBP/Exp/CogniGuard/CogniGuard/experiments/capd_e3b_20261123/PREREG_E3b.md`
- `e3b2` 上的 `PREREG_E3B2.md`、`PREREG_E3B2C.md`、`PREREG_E5.md`、`PREREG_E6.md`、`PREREG_E7.md` 及对应 `.sha256`
- `e5-synthetic` 上的 `PREREG_E5.md` / `.sha256`
- `e6-eedi` 上的 `PREREG_E5.md`、`PREREG_E6.md` 及 `.sha256`
- 各工作树的 `scripts/server/image_watermark_preregistration.py`（图像水印，不是 CA-PD E9/E10）

水印脚本（每个 CogniGuard 工作树各一份，不是 CA-PD 协议）：`run_stage9_full_evaluation.py`，以及 `run_stage10a_*`、`run_stage10b_editguard_baseline_extraction.py`。

另有扫描自己写下的 `experiments/parallel_x_20261124/x4_consistency/results/e9_e10_status.txt`。

## 5. GitHub PR

`gh auth status`：已登录 `github.com` 账号 `guoshaung`，范围 gist、read:org、repo、workflow。不记录令牌。

命令：

```
gh pr list --repo guoshaung/CogniGuard --state all --limit 50 --json number,title,state,headRefName,body
```

共 14 个 PR。标题或正文里真正出现 E9/E10 的只有：

- **#13 OPEN**，分支 `docs/research-sync-20261124`。标题：`Record 2026-11-24 research decisions, formal definition v0.1, and E9/E10 drafts`。正文写明两份文件是草案、未冻结：
  - `docs/research/prereg_drafts/PREREG_E9_SCALABILITY_DRAFT.md`：DP 与朴素联盟枚举的正确性和耗时，参数 N、k、m、p。
  - `docs/research/prereg_drafts/PREREG_E10_UNION_BUDGET_DRAFT.md`：全体联合视图预算这个强基线。

- **#14 OPEN** 的「e9」只是提交号 `2e963d8` 里的子串，不是 E9 协议。该 PR 冻结的是 Gate 0–2 和 Gate W0。

其余 PR（#1–#12）的标题和正文没有 E9/E10。#8、#12 提到的是 `PREREG_E5` 与 `PREREG_E3B2C`。

远程分支确认：

```
git ls-remote origin refs/heads/docs/research-sync-20261124
1de55a0471097e16cdaf1bdb4f2c1929271413de	refs/heads/docs/research-sync-20261124
```

用 `gh api` 读了该分支上两个文件的开头，没有检出该分支。文件头原文：

```
# E9：联盟检查的正确性与可扩展性，预注册草案（未冻结）
> 状态：草案。冻结时搬到 `experiments/capd_e9_<日期>/`，提交本文件并写入 sha256。冻结之前不得运行第 4 节的网格。
```

```
# E10：同一有界共谋约束下的可用性比较，以及全体联合视图预算强基线，预注册草案（未冻结，修订 2）
> 状态：草案。冻结时搬到 `experiments/capd_e10_<日期>/`，提交本文件并写入 sha256。冻结之前不得运行第 4 节的网格。
```

草案里有提议的参数和假设。按文件自己的状态，这些**不是**冻结指标，本次扫描不采用、不运行。

## 6. 搜过且没有冻结定义的位置

1. 本检出 `dev/confidential-secrets` @ `893c6b3` 的 `git branch -a`、`git log --all --grep`、`git grep HEAD`。
2. 工作树 `data-confidential-datasets`、`e3b2`、`e5-synthetic`、`e6-eedi`、`predicate-meter` 的 HEAD。
3. 上面 8 个 grok `subagent-*` 工作树的 HEAD。
4. `/Users/MBP/Exp/CogniGuard` 与 `/Users/MBP/Documents` 的文件名（含未剪枝的 4330 条哈希名，未读内容）。
5. `https://github.com/guoshaung/CogniGuard` 的全部 14 个 PR 标题和正文。
6. 远程 `docs/research-sync-20261124` @ `1de55a0` 上的草案文件头。

状态保持 **BLOCKED**。
