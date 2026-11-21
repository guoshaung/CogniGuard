"""Run one pinned official WAM case and emit native, auditable artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from protection.supporting.image_watermark.official_baselines.wam_official_adapter import (
    OfficialWamBackend,
    WamOfficialAdapter,
)


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _load_binary_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    with Image.open(path) as image:
        mask = np.asarray(image.convert("L"), dtype=np.uint8) > 127
    if mask.shape != shape:
        raise ValueError(f"Mask {path} has shape {mask.shape}, expected {shape}.")
    return mask


def _save_rgb(path: Path, image: np.ndarray) -> None:
    Image.fromarray(image, mode="RGB").save(path)


def _save_mask(path: Path, mask: np.ndarray) -> None:
    Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--message-bits", required=True, help="Exactly 32 bits.")
    parser.add_argument("--embedding-mask", type=Path)
    parser.add_argument(
        "--attacked-input",
        type=Path,
        help="Optional attacked watermarked image. Defaults to the clean WAM output.",
    )
    parser.add_argument(
        "--attack-gt-tamper-mask",
        type=Path,
        help="Aligned binary attack GT; localization is omitted when absent.",
    )
    parser.add_argument("--attack-id")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    original = _load_rgb(args.input)
    embedding_mask = None
    if args.embedding_mask:
        embedding_mask = _load_binary_mask(args.embedding_mask, original.shape[:2])

    backend = OfficialWamBackend(args.repo_root, args.checkpoint, device=args.device)
    adapter = WamOfficialAdapter(backend)
    embedded = adapter.embed(original, args.message_bits, embedding_mask=embedding_mask)
    attacked = (
        _load_rgb(args.attacked_input)
        if args.attacked_input
        else embedded.watermarked_image
    )
    support = None
    if embedding_mask is not None:
        if attacked.shape[:2] != embedding_mask.shape:
            raise ValueError(
                "A caller-supplied embedding mask cannot be reused after a geometry change; "
                "provide an aligned evaluation workflow instead."
            )
        support = embedding_mask
    gt_tamper = None
    if args.attack_gt_tamper_mask:
        gt_tamper = _load_binary_mask(args.attack_gt_tamper_mask, attacked.shape[:2])
    verified = adapter.verify(
        attacked,
        args.message_bits,
        embedding_support_mask=support,
        attack_gt_tamper_mask=gt_tamper,
        attack_id=args.attack_id,
    )

    output = args.output_dir.resolve()
    if output == output.parent:
        raise ValueError("Output directory cannot be a filesystem root.")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite output path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".wam-case-tmp-{uuid.uuid4().hex}"
    staging.mkdir(exist_ok=False)

    report = {
        "schema_version": "cogniguard.wam.case.v1",
        "method_id": "wam_official_mit_sa1b",
        "paper_eligible": False,
        "paper_eligibility_status": "single_case_smoke_is_not_paper_eligible",
        "comparison_partition": {
            "common_metrics": embedded.record["common_metrics"]
            | verified.record["common_metrics"],
            "native_wam_32bit_detection_recovery": {
                "message": verified.record["native_32bit_message_recovery"],
                "detection": verified.record["native_watermark_detection"],
            },
            "localization_same_attack_gt_separate_table": verified.record[
                "localization_same_attack_gt"
            ],
            "cogniguard_64bit_registry_metrics": "not_applicable",
        },
        "embed": embedded.record,
        "verify": verified.record,
        "artifacts": {
            "watermarked": "watermarked.png",
            "embedding_mask": "embedding_mask.png",
            "watermark_probability": "watermark_probability.png",
            "watermark_mask": "watermark_mask.png",
            "predicted_tamper_mask": (
                "predicted_tamper_mask.png"
                if verified.predicted_tamper_mask is not None
                else None
            ),
        },
    }
    try:
        _save_rgb(staging / "watermarked.png", embedded.watermarked_image)
        _save_mask(staging / "embedding_mask.png", embedded.embedding_mask)
        Image.fromarray(
            np.rint(verified.watermark_probability * 255.0).astype(np.uint8),
            mode="L",
        ).save(staging / "watermark_probability.png")
        _save_mask(staging / "watermark_mask.png", verified.watermark_mask)
        if verified.predicted_tamper_mask is not None:
            _save_mask(
                staging / "predicted_tamper_mask.png",
                verified.predicted_tamper_mask,
            )
        report_tmp = staging / ".report.json.tmp"
        report_tmp.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_tmp.replace(staging / "report.json")
        if output.exists():
            raise FileExistsError(f"Output path appeared during run: {output}")
        staging.rename(output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(output / "report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
