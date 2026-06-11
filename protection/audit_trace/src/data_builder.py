"""生成模拟教育数据集、教师资源与干净基线文本。"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from utils import project_root, resolve_path, write_jsonl


def _teacher_pool() -> list[dict[str, Any]]:
    return [
        {
            "resource_id": "teacher_math_001",
            "title": "二次函数与图像",
            "chunks": ["chunk_020", "chunk_021", "chunk_022", "chunk_023"],
        },
        {
            "resource_id": "teacher_math_002",
            "title": "数列基础",
            "chunks": ["chunk_010", "chunk_011", "chunk_012"],
        },
        {
            "resource_id": "teacher_math_003",
            "title": "平面几何",
            "chunks": ["chunk_030", "chunk_031"],
        },
    ]


def build_teacher_resources(path: Path) -> None:
    rows = []
    for t in _teacher_pool():
        rows.append(
            {
                "resource_id": t["resource_id"],
                "title": t["title"],
                "chunks": t["chunks"],
            }
        )
    write_jsonl(path, rows)


def _pick_trace(rng: random.Random) -> list[dict[str, Any]]:
    t = rng.choice(_teacher_pool())
    cid = rng.choice(t["chunks"])
    return [
        {
            "resource_id": t["resource_id"],
            "chunk_id": cid,
            "return_mode": rng.choice(["outline", "snippet", "full"]),
            "retrieval_score": round(rng.uniform(0.72, 0.95), 2),
            "copyright_level": round(rng.uniform(0.65, 0.92), 2),
        }
    ]


def _templates() -> list[dict[str, Any]]:
    return [
        {
            "topic": "二次函数顶点式",
            "question": "已知 y=(x-2)^2-3，求顶点坐标和对称轴方程。",
            "draft": (
                "本题给出的是二次函数的顶点式 y=(x-2)^2-3。根据顶点式的结构，可以直接读出顶点坐标为 (2,-3)，"
                "对称轴为直线 x=2。建议学生先回忆顶点式 y=a(x-h)^2+k 的含义，再代入比较 h 与 k。"
            ),
            "terms": ["二次函数", "顶点式", "对称轴"],
            "formulas": ["y=(x-2)^2-3", "x=2"],
            "numbers": ["2", "-3"],
        },
        {
            "topic": "判别式与根个数",
            "question": "方程 x^2-5x+6=0 有几个实根？",
            "draft": (
                "对一元二次方程 x^2-5x+6=0，可先计算判别式 Δ=b^2-4ac。这里 a=1,b=-5,c=6，"
                "Δ=(-5)^2-4*1*6=1>0，因此有两个不相等的实根。随后可用因式分解得到根为 2 与 3。"
            ),
            "terms": ["判别式", "一元二次方程", "因式分解"],
            "formulas": ["x^2-5x+6=0", "Δ=b^2-4ac"],
            "numbers": ["1", "-5", "6", "2", "3"],
        },
        {
            "topic": "等差数列通项",
            "question": "等差数列首项 a_1=3，公差 d=2，求 a_10。",
            "draft": (
                "等差数列通项公式为 a_n=a_1+(n-1)d。代入 a_1=3、d=2、n=10，"
                "得到 a_10=3+(10-1)*2=21。注意先算 (n-1)d 再加首项，避免括号错误。"
            ),
            "terms": ["等差数列", "公差", "通项公式"],
            "formulas": ["a_n=a_1+(n-1)d", "a_10=21"],
            "numbers": ["3", "2", "10", "21"],
        },
    ]


def build_dataset(
    dataset_path: Path,
    clean_path: Path,
    num_samples: int,
    num_clean: int,
    subject: str,
    seed: int,
) -> None:
    rng = random.Random(seed)
    templates = _templates()
    rows: list[dict[str, Any]] = []
    for i in range(num_samples):
        tpl = templates[i % len(templates)]
        sid = f"{subject}_{i+1:04d}"
        rows.append(
            {
                "sample_id": sid,
                "subject": subject,
                "topic": tpl["topic"],
                "question": tpl["question"],
                "draft_answer": tpl["draft"] + f"（模拟草稿片段 #{i}）",
                "source_trace": _pick_trace(rng),
                "protected_terms": tpl["terms"],
                "protected_formulas": tpl["formulas"],
                "protected_numbers": tpl["numbers"],
            }
        )
    write_jsonl(dataset_path, rows)

    clean_rows = []
    clean_templates = [
        "函数是描述变量之间关系的数学对象，常用解析式、图像与表格表示。",
        "在平面直角坐标系中，一次函数图像是一条直线，斜率决定倾斜程度。",
        "概率用于刻画随机事件发生的可能性大小，取值在 0 到 1 之间。",
        "向量既有大小又有方向，在物理与几何中广泛使用。",
        "导数表示函数在某点的瞬时变化率，几何意义是切线斜率。",
    ]
    for j in range(num_clean):
        clean_rows.append({"text": clean_templates[j % len(clean_templates)]})
    write_jsonl(clean_path, clean_rows)


def ensure_data_files(cfg: dict[str, Any]) -> None:
    root = project_root()
    data_cfg = cfg.get("data") or {}
    ds = resolve_path(data_cfg.get("dataset_path", "data/sample_edu_dataset.jsonl"), root)
    tr = resolve_path(data_cfg.get("teacher_resources_path", "data/teacher_resources.jsonl"), root)
    cl = resolve_path(data_cfg.get("clean_baseline_path", "data/clean_baseline.jsonl"), root)
    if not tr.exists() or tr.stat().st_size == 0:
        build_teacher_resources(tr)
    need = (not ds.exists()) or ds.stat().st_size == 0
    if need:
        build_dataset(
            ds,
            cl,
            int(data_cfg.get("num_samples", 100)),
            int(data_cfg.get("num_clean_baselines", 30)),
            str(data_cfg.get("subject", "math")),
            int(data_cfg.get("random_seed", 42)),
        )
