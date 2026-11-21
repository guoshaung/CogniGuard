"""Pinned, machine-readable contract for the official Watermark Anything baseline.

This module intentionally describes WAM's *native* task.  WAM recovers a
32-bit message and predicts a per-pixel watermark-presence mask.  It is not a
CogniGuard 64-bit HMAC capsule implementation and it does not perform source
registry lookup or error-correcting registry search.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WamPinnedContract:
    """Integrity and semantic contract for one official WAM release."""

    method_id: str
    repository_url: str
    repository_commit: str
    checkpoint_variant: str
    checkpoint_url: str
    checkpoint_sha256_evidence_url: str
    checkpoint_filename: str
    checkpoint_bytes: int
    checkpoint_sha256: str
    checkpoint_license: str
    checkpoint_license_evidence_url: str
    params_relative_path: str
    params_sha256: str
    message_bits: int
    detector_channels: int
    watermark_detection_channels: int
    message_logit_channels: int
    scaling_w: float
    scaling_i: float
    detector_size: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


OFFICIAL_WAM_MIT = WamPinnedContract(
    method_id="wam_official_mit_sa1b",
    repository_url="https://github.com/facebookresearch/watermark-anything.git",
    repository_commit="2c08af04d037d5667c02f6ddebbda9ff04581c3e",
    checkpoint_variant="WAM MIT checkpoint trained on a subset of SA-1B",
    checkpoint_url=("https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth"),
    checkpoint_sha256_evidence_url=(
        "https://huggingface.co/facebook/watermark-anything/blob/main/checkpoint.pth"
    ),
    checkpoint_filename="wam_mit.pth",
    checkpoint_bytes=377_825_938,
    checkpoint_sha256=(
        "90ef232384e023bd63245eb0c131abd69d2afc7b8f17a71ccedceb542bf009e2"
    ),
    checkpoint_license="MIT",
    checkpoint_license_evidence_url=(
        "https://github.com/facebookresearch/watermark-anything/blob/"
        "2c08af04d037d5667c02f6ddebbda9ff04581c3e/README.md#license"
    ),
    params_relative_path="assets/checkpoints/params.json",
    params_sha256=("d133a504d126b56b3e980add9fc014d718e3635a0f5740d8d6dc3190007fb476"),
    message_bits=32,
    detector_channels=33,
    watermark_detection_channels=1,
    message_logit_channels=32,
    scaling_w=2.0,
    scaling_i=1.0,
    detector_size=256,
)


NATIVE_SEMANTICS: dict[str, Any] = {
    "semantic_scope": "wam_native_32bit_message_and_watermark_presence",
    "message_bits": 32,
    "detector_output": {
        "channels": 33,
        "watermark_presence_channels": 1,
        "per_pixel_message_logit_channels": 32,
    },
    "source_registry_mapping": "none",
    "cogniguard_64bit_hmac_capsule_equivalent": False,
    "registry_exact_match": "not_applicable",
    "registry_corrected_match": "not_applicable",
    "comparison_policy": {
        "common_table": [
            "psnr_db",
            "ssim",
            "lpips_when_same_evaluator_is_supplied",
            "embed_latency_ms",
            "detect_aggregate_and_decode_latency_ms",
        ],
        "native_wam_table": [
            "native_32bit_raw_bit_accuracy",
            "native_32bit_raw_exact",
            "per_pixel_watermark_presence_score_and_detected_area",
        ],
        "image_level_presence_threshold": (
            "not_defined_by_pinned_official_contract; do not invent one"
        ),
        "localization_table": (
            "separate; only rows sharing the same spatial attack ground-truth mask"
        ),
    },
}


def pinned_provenance() -> dict[str, Any]:
    """Return a JSON-serializable copy of the frozen official contract."""

    return {
        "official_release": OFFICIAL_WAM_MIT.to_dict(),
        "native_semantics": {
            **NATIVE_SEMANTICS,
            "detector_output": dict(NATIVE_SEMANTICS["detector_output"]),
            "comparison_policy": dict(NATIVE_SEMANTICS["comparison_policy"]),
        },
    }


def validate_contract(contract: WamPinnedContract) -> None:
    """Reject contracts that could silently change the baseline's semantics."""

    if contract.message_bits != 32:
        raise ValueError("Official WAM baseline must retain its native 32-bit message.")
    if contract.watermark_detection_channels != 1:
        raise ValueError("Official WAM must expose exactly one detection channel.")
    if contract.message_logit_channels != 32 or contract.detector_channels != 33:
        raise ValueError("Official WAM detector must expose 1 + 32 channels.")
    if contract.scaling_w != 2.0:
        raise ValueError("Frozen official WAM baseline requires scaling_w=2.0.")
    if contract.scaling_i != 1.0:
        raise ValueError("Frozen official WAM baseline requires scaling_i=1.0.")
    if contract.checkpoint_license != "MIT":
        raise ValueError("Only the MIT/SA-1B WAM checkpoint is accepted.")
    if len(contract.repository_commit) != 40:
        raise ValueError("Pinned repository commit must be a full 40-character SHA.")
    for label, digest in (
        ("checkpoint", contract.checkpoint_sha256),
        ("params", contract.params_sha256),
    ):
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"Pinned {label} SHA256 is invalid.")


validate_contract(OFFICIAL_WAM_MIT)
