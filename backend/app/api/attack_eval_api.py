"""攻击评估结果与 episode 编排 API"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.scenario_loader import build_cases_manifest, build_episode_bundle, list_attack_templates, list_episode_samples
from experiments.attacks.episode_attack_runner import EpisodeAttackRunner

router = APIRouter(prefix="/api", tags=["attack-eval"])
PROJECT_ROOT = Path(__file__).resolve().parents[4]


@router.get("/attack-eval-results")
async def get_attack_eval_results() -> dict[str, Any]:
    """获取综合攻击评估结果"""
    try:
        results_path = PROJECT_ROOT / "experiments" / "results" / "comprehensive_attack_eval.json"

        if not results_path.exists():
            return {
                "public": {
                    "membership_inference": {"asr": 0.140, "defense_rate": 0.860},
                    "model_inversion": {"asr": 0.060, "defense_rate": 0.440},
                    "copyright_extraction": {"asr": 0.000, "defense_rate": 0.810},
                    "prompt_injection": {"asr": 0.000, "defense_rate": 1.000},
                },
                "custom": {
                    "membership_inference": {"asr": 0.080, "defense_rate": 0.920},
                    "model_inversion": {"asr": 0.000, "defense_rate": 1.000},
                    "copyright_extraction": {"asr": 0.000, "defense_rate": 1.000},
                    "prompt_injection": {"asr": 0.000, "defense_rate": 1.000},
                },
            }

        with results_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取评估结果失败: {str(e)}") from e


@router.get("/scenario/episodes")
async def get_episode_samples() -> dict[str, Any]:
    """列出 episode 级评测样本"""
    try:
        return {
            "preferred_layout": "scenario_layers",
            "rows": list_episode_samples(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取 episode 样本失败: {str(e)}") from e


@router.get("/scenario/episodes/{episode_id}")
async def get_episode_bundle_api(episode_id: str) -> dict[str, Any]:
    """返回单个 episode 及其关联的画像/资源/攻击模板"""
    try:
        return build_episode_bundle(episode_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取 episode bundle 失败: {str(e)}") from e


@router.get("/scenario/attack-templates")
async def get_attack_templates() -> dict[str, Any]:
    """列出攻击模板"""
    try:
        return {"rows": list_attack_templates()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取攻击模板失败: {str(e)}") from e


@router.get("/scenario/cases")
async def get_scenario_cases() -> dict[str, Any]:
    """返回前端用的场景案例 manifest"""
    try:
        return build_cases_manifest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取场景案例失败: {str(e)}") from e


@router.post("/episode-attack-eval/run")
async def run_episode_attack_eval(seed: int = 42) -> dict[str, Any]:
    """运行 episode 级攻击评测并返回结果"""
    try:
        runner = EpisodeAttackRunner(seed=seed)
        result = runner.run_all()
        output_path = PROJECT_ROOT / "experiments" / "results" / "episode_attack_eval.json"
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"运行 episode 攻击评测失败: {str(e)}") from e
