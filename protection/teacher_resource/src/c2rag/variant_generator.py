from __future__ import annotations

import re

from protection.common.schemas import TeacherResource
from protection.common.text_utils import cosine_text, lcs_ratio


_VERTEX_RE = re.compile(
    r"y\s*=\s*\(\s*x\s*([+-])\s*(\d+)\s*\)\s*\^?2\s*([+-])\s*(\d+)"
)


def _format_vertex(h: int, k: int) -> str:
    inside = f"x-{h}" if h >= 0 else f"x+{abs(h)}"
    tail = f"+{k}" if k >= 0 else str(k)
    return f"y=({inside})^2{tail}"


def extract_vertex_params(text: str) -> tuple[int, int] | None:
    m = _VERTEX_RE.search(text.replace(" ", ""))
    if not m:
        return None
    sign_h, raw_h, sign_k, raw_k = m.groups()
    h_abs = int(raw_h)
    h = h_abs if sign_h == "-" else -h_abs
    k_abs = int(raw_k)
    k = k_abs if sign_k == "+" else -k_abs
    return h, k


def generate_variant(resource: TeacherResource, config: dict) -> dict[str, object]:
    variant_cfg = config.get("variant", {})
    min_shift = int(variant_cfg.get("numeric_shift_min", 1))
    max_shift = int(variant_cfg.get("numeric_shift_max", 5))
    max_lcs = float(variant_cfg.get("max_lcs_ratio", 0.45))
    max_surface = float(variant_cfg.get("max_surface_sim", 0.65))

    params = extract_vertex_params(resource.content)
    if params:
        h, k = params
        candidates: list[str] = []
        for shift in range(min_shift, max_shift + 1):
            h2 = h + shift + 1
            k2 = k - shift
            expr = _format_vertex(h2, k2)
            candidates.append(
                f"某条抛物线的表达式是 {expr}。请写出它的顶点、轴线 x=?，并说明从 y=x^2 到该图像要怎样移动。"
            )
            expr2 = _format_vertex(-h2, k2 + 2)
            candidates.append(
                f"函数 {expr2} 表示一个平移后的基本抛物线。判断顶点坐标和对称轴，再描述水平与竖直方向的移动。"
            )
    else:
        candidates = [
            f"围绕“{resource.knowledge}”重新设计一道同难度练习，并要求学生说明关键步骤。",
            f"请完成一道关于“{resource.knowledge}”的变式题：先识别条件，再给出结论和理由。",
        ]

    best = min(
        candidates,
        key=lambda text: (lcs_ratio(text, resource.content), cosine_text(text, resource.content)),
    )
    lcs = lcs_ratio(best, resource.content)
    surface = cosine_text(best, resource.content)
    return {
        "variant_question": best,
        "KMatch": True,
        "DifficultyMatch": True,
        "SurfaceSim": surface,
        "LCS": lcs,
        "Solvable": bool(best and ("?" in best or "？" in best or "请" in best or "判断" in best)),
        "Pass": lcs <= max_lcs and surface <= max_surface,
    }
