"""Same-state comparison of CA-PD and the Woodruff–Staddon quota.

The worlds, authorization, witnesses, requests, and utility definition come
from exp/cogniguard-nowm-phase1 at 2d8e9b8. Every rule reads one shared
knowledge map. A writer may record a delivery after the decision; the other
rules do not record their own decisions, so the maps do not diverge.

Utility follows METHOD.md §5: a safe request is authorized and CA-PD(k)-safe
on the true holdings at that moment, including the writer's earlier deliveries.
Normal-task utility is 1 - unnecessary refusals / safe requests. The harmful
rate is allowed dangerous requests / dangerous requests.

Run from the phase-1 worktree so its packages win:

  cd /Users/MBP/Exp/CogniGuard/nowm
  PYTHONPATH=/Users/MBP/Exp/CogniGuard/nowm \\
    python /Users/MBP/Exp/CogniGuard/CogniGuard/experiments/classical_inference_20261125/compare.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PHASE1 = "2d8e9b8a88abaf847c7d20fd8137508f32c4dabf"
LAYERS = ("receipts", "nli", "true")
WRITERS = ("external", "capd", "quota")
KS = (1, 2, 3)
ORG = "school"


def _load_baseline():
    path = Path(__file__).with_name("baseline.py")
    spec = importlib.util.spec_from_file_location("classical_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _percentile(samples, q):
    if not samples:
        return None
    ordered = sorted(samples)
    return ordered[int(q * (len(ordered) - 1))] * 1e6


def _example_kind(quota_allow, union_allow, capd_allow, oracle_safe, q3_quota, quota_unsafe):
    if q3_quota:
        return "q3_quota"
    if (not quota_allow) and capd_allow and oracle_safe:
        return "q2_quota"
    if quota_unsafe:
        return "quota_unsafe"
    if (not union_allow) and capd_allow and oracle_safe:
        return "q2_union"
    if union_allow and (not capd_allow) and oracle_safe:
        return "q3_union"
    return None


def _key(prop, k, layer, writer):
    return f"{prop}|k={k}|{layer}|{writer}"


def _view(layer, receipts, deliveries, untracked, state, principals):
    if layer == "receipts":
        return {p: receipts[p] | frozenset(deliveries[p]) for p in principals}
    if layer == "true":
        return {p: receipts[p] | frozenset(deliveries[p]) | untracked[p] for p in principals}
    return state.knowledge("confirmed")


def replay(world, k, layer, writer, verified, principals, baseline, frozen):
    """Score quota, union, and CA-PD on one shared trajectory. Return counters."""
    from cogniguard.governance.reconstruction import check_release

    deliveries = {p: set() for p in principals}
    untracked = {p: set() for p in principals}
    state = frozen.SecurityState(world.receipts) if layer == "nli" else None
    quota_rule = frozen.B2_Quota(k)
    union_rule = frozen.B4_Union()
    capd_rule = frozen.CAPD(k)
    counts = Counter()
    examples = []
    seen = set()
    latency = {"quota": [], "union": [], "capd": []}
    for event in world.events:
        if event.kind == "untracked":
            untracked[event.principal].update(event.units)
            continue
        if event.kind == "observation":
            if state is not None:
                state.apply(verified[id(event)])
            continue
        truth = {
            p: world.receipts[p] | frozenset(deliveries[p]) | untracked[p] for p in principals
        }
        view = _view(layer, world.receipts, deliveries, untracked, state, principals)
        registry = world.access(event.t)
        authorized = all(
            registry.is_authorized(event.principal, unit[0], event.purpose, ORG, event.t)
            for unit in event.units
        )
        release = event.units
        t0 = time.perf_counter()
        quota_allow = baseline.ws04_quota_allows(
            world.targets, event.principal, release, view, k
        )
        latency["quota"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        union_allow = baseline.union_proxy_allows(
            world.targets, event.principal, release, view, k
        )
        latency["union"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        verdict = check_release(world.targets, event.principal, set(release), view, k)
        latency["capd"].append(time.perf_counter() - t0)
        capd_allow = verdict.safe
        if quota_allow != quota_rule.allows(world.targets, event.principal, release, view):
            raise RuntimeError("quota baseline diverged from phase-1 B2")
        if union_allow != union_rule.allows(world.targets, event.principal, release, view):
            raise RuntimeError("union proxy diverged from phase-1 B4")
        if capd_allow != capd_rule.allows(world.targets, event.principal, release, view):
            raise RuntimeError("CA-PD wrapper diverged from phase-1 CAPD")
        oracle = check_release(world.targets, event.principal, set(release), truth, k)
        oracle_safe = oracle.safe
        counts["requests"] += 1
        counts["authorized"] += authorized
        counts["too_large"] += any(item.reason == "too_large" for item in verdict.violations)
        if not authorized:
            continue
        counts["safe"] += oracle_safe
        counts["danger"] += not oracle_safe
        inside = baseline.quota_state_within_cap(world.targets, view, k)
        counts["inside_cap"] += inside
        for name, allow in (("quota", quota_allow), ("union", union_allow), ("capd", capd_allow)):
            counts[f"{name}_allow"] += allow
            counts[f"{name}_unneeded"] += (not allow) and oracle_safe
            counts[f"{name}_harmful"] += allow and (not oracle_safe)
        counts["quota_eq_capd"] += quota_allow == capd_allow
        counts["union_eq_capd"] += union_allow == capd_allow
        # Classical denies, CA-PD safely allows.
        counts["q2_quota"] += (not quota_allow) and capd_allow and oracle_safe
        counts["q2_union"] += (not union_allow) and capd_allow and oracle_safe
        # Classical safely allows, CA-PD denies.
        q3_quota = quota_allow and (not capd_allow) and oracle_safe
        q3_union = union_allow and (not capd_allow) and oracle_safe
        counts["q3_quota"] += q3_quota
        counts["q3_union"] += q3_union
        counts["q3_quota_inside"] += q3_quota and inside
        quota_unsafe = quota_allow and (not capd_allow) and (not oracle_safe)
        counts["quota_unsafe"] += quota_unsafe
        counts["quota_unsafe_inside"] += quota_unsafe and inside
        counts["union_unsafe"] += union_allow and (not capd_allow) and (not oracle_safe)
        if layer == "true":
            counts["capd_matches_oracle"] += capd_allow == oracle_safe
            counts["capd_oracle_mismatch"] += capd_allow != oracle_safe
        kind = _example_kind(
            quota_allow, union_allow, capd_allow, oracle_safe, q3_quota, quota_unsafe
        )
        if kind is not None and kind not in seen:
            seen.add(kind)
            examples.append(
                {
                    "kind": kind,
                    "request": event.request_id,
                    "principal": event.principal,
                    "units": list(event.units[0]),
                    "oracle_safe": oracle_safe,
                    "quota": quota_allow,
                    "union": union_allow,
                    "capd": capd_allow,
                    "inside_cap": inside,
                }
            )
        write = (writer == "capd" and capd_allow) or (writer == "quota" and quota_allow)
        if write:
            deliveries[event.principal].update(release)
            if state is not None:
                state.record_delivery(event.principal, release)
    return counts, examples, latency


def _rate(num, den):
    return None if not den else num / den


def _finish(counts):
    out = dict(counts)
    for name in ("quota", "union", "capd"):
        out[f"{name}_utility"] = _rate(counts["safe"] - counts[f"{name}_unneeded"], counts["safe"])
        out[f"{name}_harmful_rate"] = _rate(counts[f"{name}_harmful"], counts["danger"])
    out["quota_eq_rate"] = _rate(counts["quota_eq_capd"], counts["authorized"])
    out["union_eq_rate"] = _rate(counts["union_eq_capd"], counts["authorized"])
    return out


def _fmt(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render(summary):
    lines = [
        "# CA-PD 与经典推断控制：同一状态下的对比",
        "",
        f"基准提交：`exp/cogniguard-nowm-phase1@{summary['phase1_commit']}`。",
        "授权、见证、请求流和效用定义与该提交的 Phase 1 相同。",
        "每一格里，配额、全局并集代理和 CA-PD 读同一份知识；只有 writer 的放行会写入后续状态。",
        "没有为了制造差异而改见证或威胁模型。",
        "",
        "## 复现了哪一条规则",
        "",
        summary["reading"],
        "",
        "## 主表（真实状态，writer = capd：后续状态只写入 CA-PD 在真实状态上允许的交付）",
        "",
        "效用的分母是决策时刻真实状态上的安全请求。CA-PD 在这一层上就是该安全定义。",
        "",
        "| 传播 | k | 授权请求 | 安全/危险 | 配额=CA-PD | 配额拒绝且 CA-PD 安全放行 | 配额安全放行且 CA-PD 拒绝 | 配额不安全放行 | 配额效用 | CA-PD 效用 | 配额危险率 | CA-PD 危险率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for prop in ("low", "high"):
        for k in KS:
            cell = summary["cells"][_key(prop, k, "true", "capd")]
            lines.append(
                "| {prop} | {k} | {authorized} | {safe}/{danger} | {eq} | {q2} | {q3} | {unsafe} | {qu} | {cu} | {qh} | {ch} |".format(
                    prop=prop,
                    k=k,
                    authorized=cell["authorized"],
                    safe=cell["safe"],
                    danger=cell["danger"],
                    eq=cell["quota_eq_capd"],
                    q2=cell["q2_quota"],
                    q3=cell["q3_quota"],
                    unsafe=cell["quota_unsafe"],
                    qu=_fmt(cell["quota_utility"]),
                    cu=_fmt(cell["capd_utility"]),
                    qh=_fmt(cell["quota_harmful_rate"]),
                    ch=_fmt(cell["capd_harmful_rate"]),
                )
            )
    lines += [
        "",
        "## 五个问题",
        "",
        summary["answers"],
        "",
        "## 延迟（全部共享轨迹上的判定时间，不含世界生成和证据回放）",
        "",
        "| 规则 | 调用次数 | P50 (μs) | P95 (μs) |",
        "|---|---:|---:|---:|",
    ]
    for name, label in (
        ("quota", "WS04 配额"),
        ("union", "全局并集代理"),
        ("capd", "CA-PD"),
    ):
        item = summary["latency"][name]
        lines.append(
            f"| {label} | {item['n']} | {_fmt(item['p50_us'])} | {_fmt(item['p95_us'])} |"
        )
    lines += [
        "",
        "## 其余共享轨迹",
        "",
        "external：不写入任何请求交付，只比较发行、未记录获得和（nli 层）已确认观察。",
        "quota：只写入配额允许的交付。",
        "并集列是更强的保证，不与 k-安全放在同一安全水平里。",
        "",
        "| 轨迹 | 配额=CA-PD | 配额过拒（安全） | 配额安全放行而 CA-PD 拒绝 | 其中配额不变量成立 | 配额不安全放行 | 并集过拒 | 并集安全放行而 CA-PD 拒绝 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for layer in LAYERS:
        for writer in WRITERS:
            totals = Counter()
            for prop in ("low", "high"):
                for k in KS:
                    totals.update(summary["cells"][_key(prop, k, layer, writer)])
            lines.append(
                "| {layer}/{writer} | {eq} | {q2} | {q3} | {q3in} | {unsafe} | {uq2} | {uq3} |".format(
                    layer=layer,
                    writer=writer,
                    eq=totals["quota_eq_capd"],
                    q2=totals["q2_quota"],
                    q3=totals["q3_quota"],
                    q3in=totals["q3_quota_inside"],
                    unsafe=totals["quota_unsafe"],
                    uq2=totals["q2_union"],
                    uq3=totals["q3_union"],
                )
            )
    lines += [
        "",
        f"真实状态上 CA-PD 与 Oracle 不一致的授权请求：{summary['capd_oracle_mismatch']}。",
        f"配额不变量成立时，配额放行但 CA-PD 拒绝的次数：{summary['quota_unsafe_or_q3_inside']}。",
        f"保守拒绝（too_large）：{summary['too_large']}。",
        f"决策前知识已经超出配额的授权请求：{summary['outside_cap']} / {summary['authorized']}。",
        f"初始发行已经超出配额的世界数：{json.dumps(summary['initial_quota_violations'], ensure_ascii=False)}。",
        "",
        "## 例子",
        "",
    ]
    if not summary["examples"]:
        lines.append("没有记录到配额与 CA-PD 的分歧。")
    else:
        for item in summary["examples"]:
            lines.append(
                "- `{kind}` seed {seed} `{cell}` {request} {principal} {units}："
                "oracle_safe={oracle_safe}，quota={quota}，union={union}，"
                "capd={capd}，配额不变量={inside_cap}".format(**item)
            )
    lines += [
        "",
        "## Phase 1 已发表的在线轨迹",
        "",
        "下面的数来自 `2d8e9b8` 的 `results/formal/runs.jsonl.gz`。",
        "每条规则写入自己的交付，第一次分歧之后知识状态不再相同。这里只作对照，不代替上表。",
        "",
        summary["online_note"],
        "",
    ]
    return "\n".join(lines) + "\n"


def _online_note(runs_path: Path):
    if not runs_path.exists():
        return "正式运行日志不在这台机器上，没有重算在线轨迹。"
    import gzip

    buckets = {}
    with gzip.open(runs_path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            if row["rule"] not in {"B2", "B4"} and not str(row["rule"]).startswith("CAPD"):
                continue
            if row["layer"] not in {"nli", "true"}:
                continue
            if str(row["rule"]).startswith("CAPD") and row["rule"] != f"CAPD(k={row['k']})":
                continue
            key = (row["prop"], row["k"], row["layer"], row["rule"])
            buckets.setdefault(key, []).append(row)
    lines = [
        "| 传播 | k | 层 | 规则 | 危险放行率均值 | 效用均值 | P50 μs 均值 |",
        "|---|---:|---|---|---:|---:|---:|",
    ]
    for key in sorted(buckets):
        rows = buckets[key]
        harm = sum(r["harmful_rate"] or 0 for r in rows) / len(rows)
        util = [r["utility"] for r in rows if r["utility"] is not None]
        utility = sum(util) / len(util) if util else None
        p50 = sum(r["p50_us"] for r in rows) / len(rows)
        prop, k, layer, rule = key
        lines.append(
            f"| {prop} | {k} | {layer} | {rule} | {_fmt(harm)} | {_fmt(utility)} | {_fmt(p50)} |"
        )
    return "\n".join(lines)


READING = """\
最接近 CA-PD 的可复现披露规则是 Woodruff–Staddon 2004 的共谋配额，不是 PIR 协议。

能读到的原文依据：ePrint 2004/130 的摘要和被检索索引到的正文写明，单用户定义不够实现共谋抵抗；做法是让每个用户在每条推断通道上拿到更少的对象，而且这个限制只依赖该用户已经做了多少次查询，不依赖查询内容。正文把共谋抵抗留到 Section 8。公开讲稿把同一规则概括为：c-共谋抵抗把长度为 m 的通道收成 (m−1)/c。用户审阅原文后的记录给出同一个上限 ⌊(|W|−1)/k⌋。ePrint 的 PDF 在本环境返回 HTTP 403，所以这里不引用 Section 8 的逐句原文。PIR/SPIR 不实现：它隐藏查询，不改变哪些交付满足配额。

Staddon 2003 只读到 ACM 摘要。摘要中的 c-共谋抵抗和 crowd control（很多人已经拿走过通道中除最后一个以外的对象时，谁也不能再拿最后一个）是性质，不是可执行的令牌分配。Sec. 3–4 的令牌构造没有全文，因此不实现令牌方案，也不把令牌方案说成与 CA-PD 等价。全局并集是 crowd control 的代理，保证强于 k-安全，单独报告。

Toland、Farkas、Eastman 2010（Computers & Security）的 Elsevier 全文没有打开。2005 年同一组作者的 D²Mon 性能论文可以读到 Algorithm 1：每个用户一份历史库，用 UpCon 丢掉过期元组，再用 DiIE 对 Horn 子句做闭合，然后由强制访问控制判断闭合结果是否非法。这是单个用户的查询历史加数据库依赖，不是人数不超过 k 的联盟覆盖一个见证。2010 年论文有一节题为推断合作预防，正文未读到，所以不实现一个猜测出来的合作规则。
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nowm", type=Path, default=Path("/Users/MBP/Exp/CogniGuard/nowm"))
    parser.add_argument("--data", type=Path, default=Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/nowm_phase1"))
    parser.add_argument("--repo", type=Path, default=Path("/Users/MBP/Exp/CogniGuard/CogniGuard"))
    parser.add_argument("--seeds", default="0-29")
    args = parser.parse_args()
    sha = subprocess.check_output(["git", "-C", str(args.nowm), "rev-parse", "HEAD"], text=True).strip()
    if sha != PHASE1:
        raise SystemExit(f"phase-1 worktree is {sha}, expected {PHASE1}")
    sys.path.insert(0, str(args.nowm))
    from cogniguard.provenance.state import SecurityState
    from experiments.cogniguard_nowm_phase1 import policies as policies
    from experiments.cogniguard_nowm_phase1 import world as world_mod
    from experiments.cogniguard_nowm_phase1.world import PRINCIPALS

    frozen = argparse.Namespace(
        SecurityState=SecurityState,
        B2_Quota=policies.B2_Quota,
        B4_Union=policies.B4_Union,
        CAPD=policies.CAPD,
    )
    baseline = _load_baseline()
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    real = world_mod.load_real(args.repo, args.data / "real_cache.json")
    nli_path = args.data / "nli_judgments.jsonl"
    verifier = world_mod.verifier_for(nli_path)
    cells = {}
    examples = []
    example_slots = set()
    latency = {"quota": [], "union": [], "capd": []}
    initial = Counter()
    for seed in seeds:
        for prop in ("low", "high"):
            world = world_mod.build(real, nli_path, seed, prop)
            verified = {
                id(event): verifier.verify(event.observation, event.artifact)
                for event in world.events
                if event.kind == "observation"
            }
            receipts = {p: world.receipts.get(p, frozenset()) for p in PRINCIPALS}
            for k in KS:
                if not baseline.quota_state_within_cap(world.targets, receipts, k):
                    initial[f"{prop}|k={k}"] += 1
            for k in KS:
                for layer in LAYERS:
                    for writer in WRITERS:
                        counts, found, lats = replay(
                            world, k, layer, writer, verified, PRINCIPALS, baseline, frozen
                        )
                        cell = _finish(counts)
                        cell.update(seed_note=f"{seed}/{prop}")
                        key = _key(prop, k, layer, writer)
                        cells.setdefault(key, Counter())
                        # Keep summed counts; rates are recomputed after the sum.
                        for name, value in counts.items():
                            cells[key][name] += value
                        for name in latency:
                            latency[name].extend(lats[name])
                        keep = writer == "capd" and (
                            layer == "true" or (layer == "nli" and any(i["kind"] == "q3_quota" for i in found))
                        )
                        if keep:
                            for item in found:
                                if layer == "nli" and item["kind"] != "q3_quota":
                                    continue
                                slot = (item["kind"], prop, k)
                                if slot in example_slots:
                                    continue
                                example_slots.add(slot)
                                examples.append({"cell": key, "seed": seed, **item})
            print(f"seed {seed} {prop}", flush=True)
    finished = {key: _finish(counter) for key, counter in cells.items()}
    authorized = sum(finished[_key(p, k, "true", "capd")]["authorized"] for p in ("low", "high") for k in KS)
    outside = sum(
        finished[_key(p, k, "true", "capd")]["authorized"] - finished[_key(p, k, "true", "capd")]["inside_cap"]
        for p in ("low", "high")
        for k in KS
    )
    mismatch = sum(finished[_key(p, k, "true", w)]["capd_oracle_mismatch"] for p in ("low", "high") for k in KS for w in WRITERS)
    too_large = sum(finished[_key(p, k, layer, w)]["too_large"] for p in ("low", "high") for k in KS for layer in LAYERS for w in WRITERS)
    q3_true_capd = _sum_cells(finished, "true", "capd", "q3_quota")
    q2_true_capd = _sum_cells(finished, "true", "capd", "q2_quota")
    unsafe_true = _sum_cells(finished, "true", "capd", "quota_unsafe")
    inside_break = 0
    for layer in LAYERS:
        for writer in WRITERS:
            inside_break += _sum_cells(finished, layer, writer, "q3_quota_inside")
            inside_break += _sum_cells(finished, layer, writer, "quota_unsafe_inside")
    answers = _answers(finished, q2_true_capd, q3_true_capd, unsafe_true, mismatch)
    summary = {
        "phase1_commit": sha,
        "seeds": f"{lo}-{hi or lo}",
        "reading": READING.strip(),
        "answers": answers,
        "cells": finished,
        "latency": {
            name: {
                "n": len(samples),
                "p50_us": _percentile(samples, 0.50),
                "p95_us": _percentile(samples, 0.95),
            }
            for name, samples in latency.items()
        },
        "examples": examples,
        "initial_quota_violations": dict(initial),
        "authorized": authorized,
        "outside_cap": outside,
        "capd_oracle_mismatch": mismatch,
        "quota_unsafe_or_q3_inside": inside_break,
        "too_large": too_large,
        "online_note": _online_note(
            args.nowm / "experiments/cogniguard_nowm_phase1/results/formal/runs.jsonl.gz"
        ),
    }
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    text = _render(summary)
    (Path(__file__).parent / "RESULT.md").write_text(text)
    print(f"wrote {out / 'summary.json'} and RESULT.md")


def _sum_cells(cells, layer, writer, field):
    return sum(cells[_key(prop, k, layer, writer)][field] for prop in ("low", "high") for k in KS)


def _answers(cells, q2, q3, unsafe, mismatch):
    gaps = []
    utility_lines = []
    for prop in ("low", "high"):
        for k in KS:
            cell = cells[_key(prop, k, "true", "capd")]
            if cell["quota_eq_capd"] != cell["authorized"]:
                gaps.append(f"{prop}/k={k}")
            utility_lines.append(
                f"{prop}/k={k}：配额效用 {_fmt(cell['quota_utility'])}，"
                f"危险率 {_fmt(cell['quota_harmful_rate'])}；"
                f"CA-PD 效用 {_fmt(cell['capd_utility'])}，"
                f"危险率 {_fmt(cell['capd_harmful_rate'])}"
            )
    where = "、".join(gaps) if gaps else "无"
    nli_capd = cells[_key("high", 2, "nli", "capd")]["q3_quota"]
    nli_external = cells[_key("high", 2, "nli", "external")]["q3_quota"]
    nli_quota = cells[_key("high", 2, "nli", "quota")]["q3_quota"]
    third = (
        f"3. 在真实状态上不存在：writer=capd 的合计是 {q3} 条。"
        "全部层、全部 writer 上，只要决策前的知识还在配额不变量里，"
        "配额放行而 CA-PD 拒绝的次数是 0。"
        f"配额在真实状态上另有 {unsafe} 条放行，CA-PD 拒绝且 Oracle 判为不安全。"
        "nli 层只有 high/k=2 出现配额放行、CA-PD 拒绝、真实状态却安全的判定："
        f"external {nli_external} 条，writer=capd {nli_capd} 条，writer=quota {nli_quota} 条。"
        "抽查 seed 4、high、k=2、q119：nli 把 math-01:f1 记在 S3 和 TA 上，真实持有里没有；"
        "CA-PD 因此看到联盟 (S1, S3) 并拒绝，配额不看 S3，所以放行。"
        "这不是配额在真实威胁模型上安全地放宽了 CA-PD，而是配额忽略了 nli 的误确认。"
        "全局并集没有出现“安全放行而 CA-PD 拒绝”。并集多出的拒绝是更强保证。"
    )
    parts = [
        (
            "1. 在 k=1 上等价，在 k≥2 上不等价。"
            f"真实状态、writer=capd 的不一致格子：{where}。"
            f"CA-PD 与同一真实状态上的 Oracle 不一致 {mismatch} 次。"
            "k=1 时配额上限是 |W|−1，和单人补全是同一条规则。"
        ),
        (
            f"2. 存在。配额拒绝而 CA-PD 安全放行共 {q2} 条"
            "（真实状态，writer=capd，两种传播、k=1..3 合计）。这些请求是 k-安全的。"
        ),
        third,
        (
            "4. 安全标签用决策时刻真实状态上的 CA-PD(k)。"
            "在这个分母上，CA-PD 的效用是 1。配额效用如下，差就是过拒："
            + "；".join(utility_lines)
            + "。k≥2 时配额的危险率大于 0，所以它没有达到 CA-PD 已经达到的安全水平："
            "其他主体可以持有超过 ⌊(|W|−1)/k⌋ 的单元，配额不看这些持有。"
            "并集的危险率不高于 CA-PD，效用更低，那是更强保证下的损失。"
        ),
        (
            "5. 配额对每个被本次放行碰到的见证做一次交集，不随其他主体人数做组合，也不随 k 枚举联盟。"
            "CA-PD 对每个受影响见证在缺失单元上做集合覆盖，上界 O(|masks|·2^m)；"
            "m>20 才保守拒绝。本数据见证大小不超过 5，too_large 见上文。"
            "并集代理先求全体持有的并。实测 P50/P95 见上表。配额更快。"
            "这个速度差不构成 CA-PD 相对配额的效率优势。"
        ),
    ]
    return "\n\n".join(parts)


if __name__ == "__main__":
    main()
