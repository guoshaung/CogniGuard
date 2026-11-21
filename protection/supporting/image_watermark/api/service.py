"""Service wrapper for SCE-LocGuard research pipelines.

This module upgrades the first API skeleton into a real MVP wrapper where the
existing callable research pipeline can be reused safely. It keeps the
watermarking method unchanged:

- no training
- no VLM
- no 128-bit payload
- no watermark embedding modification
- blind verification does not read the original image or GT mask

When a required model/checkpoint/cache is unavailable, the service returns a
clear `not_implemented` or `model_unavailable` response instead of fabricating
masks, reports, or payload status.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from core.paths import resolve_project_path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from .schemas import (
    AIGCAttackRequest,
    AIGCAttackResponse,
    CapabilityResponse,
    EmbedRequest,
    EmbedResponse,
    ReportRegion,
    VerifyRequest,
    VerifyResponse,
)


BICUBIC = getattr(Image, "Resampling", Image).BICUBIC
NEAREST = getattr(Image, "Resampling", Image).NEAREST
ATTACK_TYPES = {"object_removal", "inpainting", "local_replacement", "local_style_edit"}
DEFAULT_PAYLOAD_SEED = 20260624
DEFAULT_INFERENCE_SEED = 20260802
DEFAULT_RECOVERY_THRESHOLD = 0.28
DEFAULT_TAMPER_AREA_THRESHOLD = 0.001
DEFAULT_LOCALIZATION_CHANNEL_VOTE_MIN = 1
DEFAULT_LOCALIZATION_MIN_COMPONENT_AREA_RATIO = 0.0
LOCALIZATION_CHANNEL_COUNT = 3
LOCALIZATION_MASK_RULE_VERSION_V2 = "editguard_residual_channel_vote_v2"
LOCALIZATION_MASK_RULE_VERSION_V3 = "editguard_residual_channel_vote_cc8_v3"
LOCALIZATION_CHANNEL_AGGREGATION = "k_of_3"
LOCALIZATION_RESIDUAL_THRESHOLD_RULE = "abs_gt_recovery_threshold_per_channel"
LOCALIZATION_CHANNEL_VOTE_VALUES = (0, 255, 510, 765)
LOCALIZATION_COMPONENT_CONNECTIVITY = 8
LOCALIZATION_COMPONENT_AREA_ROUNDING = "ceil_height_times_width"
LOCALIZATION_POSTPROCESSING_NONE = "none"
LOCALIZATION_POSTPROCESSING_CC8 = "connected_component_min_area_ratio_v1"
REGISTRY_CORRECTION_RADIUS = 1
REGISTRY_MINIMUM_DISTANCE = 2 * REGISTRY_CORRECTION_RADIUS + 1


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def validate_localization_channel_votes(pred_mask_raw: Any) -> np.ndarray:
    """Validate EditGuard's summed RGB votes and return a safe uint16 copy.

    EditGuard converts each of three binary residual channels to 0/255 before
    summing them, so every pixel must be one of exactly four values.  Keeping
    this validation separate from the service makes the fail-closed contract
    directly testable and prevents a premature uint8 conversion from wrapping
    510 or 765.
    """

    try:
        raw = np.asarray(pred_mask_raw)
    except Exception as exc:
        raise ValueError(
            "EditGuard localization channel votes must be a numeric 2D array."
        ) from exc
    if raw.ndim != 2 or any(size <= 0 for size in raw.shape):
        raise ValueError(
            "EditGuard localization channel votes must be a non-empty 2D array."
        )
    if np.issubdtype(raw.dtype, np.bool_) or not (
        np.issubdtype(raw.dtype, np.integer)
        or np.issubdtype(raw.dtype, np.floating)
    ):
        raise ValueError(
            "EditGuard localization channel votes must have a real numeric dtype."
        )
    if not bool(np.isfinite(raw).all()):
        raise ValueError("EditGuard localization channel votes must all be finite.")
    allowed = np.asarray(LOCALIZATION_CHANNEL_VOTE_VALUES, dtype=np.uint16)
    if not bool(np.isin(raw, allowed).all()):
        observed = np.unique(raw)
        preview = observed[:8].tolist()
        raise ValueError(
            "EditGuard localization channel votes may contain only "
            f"{list(LOCALIZATION_CHANNEL_VOTE_VALUES)}; observed {preview}."
        )
    return raw.astype(np.uint16, copy=True)


def aggregate_localization_channel_votes(
    pred_mask_raw: Any,
    min_votes: int,
    *,
    min_component_area_ratio: float = 0.0,
) -> np.ndarray:
    """Return the validated k-of-3 mask with optional CC8 area filtering."""

    if isinstance(min_votes, bool) or not isinstance(min_votes, (int, np.integer)):
        raise ValueError("localization_channel_vote_min must be an integer from 1 to 3.")
    normalized_min_votes = int(min_votes)
    if not 1 <= normalized_min_votes <= LOCALIZATION_CHANNEL_COUNT:
        raise ValueError("localization_channel_vote_min must be an integer from 1 to 3.")
    raw = validate_localization_channel_votes(pred_mask_raw)
    threshold = np.uint16(255 * normalized_min_votes)
    aggregated = raw >= threshold
    if (
        isinstance(min_component_area_ratio, bool)
        or not isinstance(min_component_area_ratio, (int, float, np.integer, np.floating))
        or not math.isfinite(float(min_component_area_ratio))
        or not 0.0 <= float(min_component_area_ratio) < 1.0
    ):
        raise ValueError(
            "localization_min_component_area_ratio must be a finite value in [0, 1)."
        )
    normalized_ratio = float(min_component_area_ratio)
    if normalized_ratio == 0.0:
        return aggregated.astype(np.uint8)

    minimum_pixels = int(math.ceil(normalized_ratio * aggregated.size))
    labels, component_count = ndimage.label(
        aggregated,
        structure=np.ones((3, 3), dtype=np.uint8),
    )
    if component_count == 0:
        return np.zeros_like(aggregated, dtype=np.uint8)
    component_sizes = np.bincount(labels.ravel())
    keep = np.zeros(component_count + 1, dtype=np.bool_)
    keep[1:] = component_sizes[1:] >= minimum_pixels
    return keep[labels].astype(np.uint8)


class SCELocGuardService:
    """Thin service layer around SCE-LocGuard / EditGuard-style code."""

    def __init__(
        self,
        project_root: str,
        localization_channel_vote_min: Optional[int] = None,
    ):
        self.project_root = Path(project_root).expanduser().resolve()
        default_job_raw = os.environ.get("SCE_LOCGUARD_API_JOB_ROOT", "").strip()
        self.default_job_root = (
            resolve_project_path(default_job_raw, self.project_root)
            if default_job_raw
            else self.project_root / "var" / "outputs" / "sce_locguard_api_jobs"
        ).resolve()
        self.job_index_dir = self.default_job_root / "_index"
        registry_raw = os.environ.get("SCE_LOCGUARD_REGISTRY_DIR", "").strip()
        self.payload_registry_dir = (
            resolve_project_path(registry_raw, self.project_root)
            if registry_raw
            else self.default_job_root / "_payload_registry"
        ).resolve()
        self.ckpt_path = self.project_root / 'assets' / 'checkpoints' / "clean.pth"
        self.opt_path = self.project_root / 'third_party' / 'editguard' / "options" / "test_editguard.yml"
        self.recovery_threshold = self._probability_from_env(
            "SCE_LOCGUARD_RECOVERY_THRESHOLD", DEFAULT_RECOVERY_THRESHOLD
        )
        self.tamper_area_threshold = self._probability_from_env(
            "SCE_LOCGUARD_TAMPER_AREA_THRESHOLD", DEFAULT_TAMPER_AREA_THRESHOLD
        )
        self.localization_channel_vote_min = self._resolve_localization_channel_vote_min(
            localization_channel_vote_min
        )
        self.localization_min_component_area_ratio = self._probability_from_env(
            "SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO",
            DEFAULT_LOCALIZATION_MIN_COMPONENT_AREA_RATIO,
        )
        self.attack_model_id = os.environ.get(
            "SCE_LOCGUARD_INPAINT_MODEL_ID",
            "stable-diffusion-v1-5/stable-diffusion-inpainting",
        ).strip()
        self.attack_model_revision = os.environ.get(
            "SCE_LOCGUARD_INPAINT_MODEL_REVISION", ""
        ).strip() or None
        self.deterministic_mode_requested = os.environ.get(
            "SCE_LOCGUARD_DETERMINISTIC", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.deterministic_mode_enabled = bool(
            self.deterministic_mode_requested
            and os.environ.get("CUBLAS_WORKSPACE_CONFIG") in {":4096:8", ":16:8"}
            and os.environ.get("PYTHONHASHSEED", "").strip().isdigit()
        )
        self._gpu_lock = threading.RLock()
        self._registry_lock = threading.RLock()
        self.registry_correction_radius = REGISTRY_CORRECTION_RADIUS
        self.registry_minimum_distance = REGISTRY_MINIMUM_DISTANCE
        self._registry_codebook_cache: Optional[Tuple[Dict[str, Any], ...]] = None
        self._registry_codebook_min_distance: Optional[int] = None
        self._registry_codebook_fingerprint: Optional[
            Tuple[Tuple[str, int, int, int], ...]
        ] = None
        self._research_modules_cache: Tuple[Any, Any, Any] | None = None
        self._editguard_model_cache: Any | None = None
        self._attack_pipe_cache: Dict[Tuple[str, str, str, str, str], Any] = {}
        configured_secret = os.environ.get("SCE_LOCGUARD_REGISTRY_SECRET", "").strip()
        self.registry_secret_configured = len(configured_secret) >= 32
        self.registry_secret_too_short = bool(configured_secret) and not self.registry_secret_configured
        self.registry_secret = (
            configured_secret or "cogniguard-development-registry-secret-not-for-paper"
        ).encode("utf-8")
        if self.deterministic_mode_enabled:
            self._set_runtime_seed(DEFAULT_INFERENCE_SEED)

    def capabilities(self) -> CapabilityResponse:
        editguard_ok, editguard_notes = self._editguard_runtime_available()
        attack_ok, attack_notes = self._attack_runtime_available()
        notes = editguard_notes + attack_notes
        registry_codebook_valid = True
        registry_codebook_records = 0
        registry_codebook_min_distance: Optional[int] = None
        try:
            registry_codebook_records = len(self._get_registry_codebook())
            registry_codebook_min_distance = self._registry_codebook_min_distance
        except (OSError, RuntimeError, ValueError):
            registry_codebook_valid = False
            notes.append(
                "The source registry codebook is invalid or corrupted; closed-set correction "
                "is disabled and paper mode is not ready."
            )
        if not self.registry_secret_configured:
            notes.append(
                "SCE_LOCGUARD_REGISTRY_SECRET is missing or shorter than 32 characters; "
                "source binding is not paper-eligible."
            )
        if not self.deterministic_mode_enabled:
            notes.append(
                "The deterministic runtime contract is incomplete; paper runs must set "
                "SCE_LOCGUARD_DETERMINISTIC, CUBLAS_WORKSPACE_CONFIG, and PYTHONHASHSEED "
                "before Python starts, then pass explicit request seeds."
            )
        notes.append(
            "The JSON source registry is safe only with one API process; use a transactional "
            "database before multi-worker or multi-node deployment."
        )
        notes.extend(
            [
                "Single-image embed uses the existing EditGuard image_hiding() path when checkpoint/CUDA are available.",
                "Single-image verify uses image_recovery() with the fixed localization template; it does not access original image or GT mask.",
                "The 64-bit source capsule contains a 16-bit registry id, 32-bit truncated HMAC tag, 8-bit nonce, and 8-bit checksum.",
                "After exact verification fails, a fixed-radius-1 closed-set registry lookup may correct one raw bit error only when the candidate is unique.",
                "The registry binding rejects random/id-collision forgery but does not by itself prevent copying or replaying a valid watermark.",
                "Stage8E/Stage8F full batch report calibration is not run inside the API MVP; verification report is a lightweight rule-based readout.",
            ]
        )
        return CapabilityResponse(
            embed_real_pipeline_available=editguard_ok,
            attack_real_pipeline_available=attack_ok,
            verify_real_pipeline_available=editguard_ok,
            supports_64bit_capsule=True,
            supports_vlm=False,
            supports_single_image=True,
            source_registry_enabled=True,
            registry_secret_configured=self.registry_secret_configured,
            paper_mode_ready=bool(
                editguard_ok
                and attack_ok
                and self.registry_secret_configured
                and self.deterministic_mode_enabled
                and registry_codebook_valid
            ),
            deterministic_mode_enabled=self.deterministic_mode_enabled,
            service_singleton=True,
            registry_backend="json_single_process",
            capsule_schema="hmac_source_capsule_v1",
            source_auth_tag_bits=32,
            replay_resistant=False,
            registry_aided_decoding=True,
            registry_error_correction_enabled=True,
            registry_hamming_radius=self.registry_correction_radius,
            registry_minimum_distance_required=self.registry_minimum_distance,
            registry_codebook_records=registry_codebook_records,
            registry_codebook_min_distance=registry_codebook_min_distance,
            registry_codebook_valid=registry_codebook_valid,
            recovery_threshold=self.recovery_threshold,
            tamper_area_threshold=self.tamper_area_threshold,
            **self._localization_channel_vote_response_fields(),
            attack_model_id=self.attack_model_id,
            attack_model_revision=self.attack_model_revision,
            notes=notes,
        )

    def embed(self, request: EmbedRequest) -> EmbedResponse:
        image_path, error = self._validate_input_image(request.image_path)
        if error:
            return EmbedResponse(status="error", implementation_level="skeleton", message=error)

        job_id, job_dir = self._create_phase_dir(request.output_dir, "embed")
        editguard_ok, notes = self._editguard_runtime_available()
        capsule_bits, payload_id, auth_hash = self._build_capsule_preview(
            request.owner_id, request.semantic_metadata
        )
        if not editguard_ok:
            response = EmbedResponse(
                status="not_implemented",
                job_id=job_id,
                implementation_level="skeleton",
                payload_id=payload_id,
                capsule_bits=capsule_bits,
                auth_hash=auth_hash,
                message="Real single-image embed is unavailable: " + "; ".join(notes),
            )
            self._write_job_report(job_id, "embed", job_dir, request, response, {"notes": notes})
            return response

        self._gpu_lock.acquire()
        try:
            effective_seed = request.seed if request.seed is not None else DEFAULT_INFERENCE_SEED
            self._set_runtime_seed(effective_seed)
            stage1, s8c, _attack_mod = self._load_research_modules()
            model = self._get_editguard_model(stage1)
            original = self._load_rgb_512(image_path)
            binding_metadata = dict(request.semantic_metadata)
            binding_metadata["host_rgb512_sha256"] = hashlib.sha256(original.tobytes()).hexdigest()
            binding_id = self._payload_binding_id(request.owner_id, binding_metadata)
            payload_id = binding_id[:16]
            payload, payload_seed = self._build_unique_registered_payload(
                payload_id=payload_id,
            )
            message = s8c.bits_to_message(payload["bits"])
            data = stage1.image_to_editguard_batch(original)
            data["MES"] = message
            model.feed_data(data)
            model.mes = message
            watermarked = model.image_hiding()

            source_copy = job_dir / "input.png"
            watermarked_path = job_dir / "watermarked.png"
            payload_path = job_dir / "payload.json"
            Image.fromarray(original).save(source_copy)
            Image.fromarray(watermarked).save(watermarked_path)
            auth_hash = self._payload_auth_hash(payload["bits"], payload_id)
            copyright_id = int(payload["copyright_id"])
            self._write_json(
                payload_path,
                {
                    "payload_variant": "H1_registry_hmac_capsule_64",
                    "owner_reference": hmac.new(
                        self.registry_secret,
                        request.owner_id.encode("utf-8"),
                        hashlib.sha256,
                    ).hexdigest()[:16],
                    "semantic_metadata_keys": sorted(request.semantic_metadata),
                    "semantic_metadata_sha256": self._canonical_sha256(request.semantic_metadata),
                    "capsule_schema": "hmac_source_capsule_v1",
                    "payload_id": payload_id,
                    "copyright_id": copyright_id,
                    "payload_seed": payload_seed,
                    "payload": payload,
                    "capsule_bits": self._bits_to_string(payload["bits"]),
                    "auth_hash": auth_hash,
                    "auth_level": self._registry_auth_level(),
                    "note": (
                        "Payload fields are 16-bit registry id, 32-bit truncated HMAC tag, "
                        "8-bit nonce, and 8-bit integrity checksum. Copy/replay remains a "
                        "separate threat and is not prevented by this capsule alone."
                    ),
                },
            )
            self._register_payload(
                copyright_id=copyright_id,
                owner_id=request.owner_id,
                semantic_metadata=binding_metadata,
                payload_id=payload_id,
                payload_seed=payload_seed,
                capsule_bits=self._bits_to_string(payload["bits"]),
                auth_hash=auth_hash,
                embed_job_id=job_id,
            )
            response = EmbedResponse(
                status="ok",
                job_id=job_id,
                implementation_level="real_pipeline",
                watermarked_image_path=str(watermarked_path),
                payload_id=payload_id,
                copyright_id=copyright_id,
                capsule_bits=self._bits_to_string(payload["bits"]),
                auth_hash=auth_hash,
                payload_seed=payload_seed,
                source_registry_registered=True,
                auth_level=self._registry_auth_level(),
                capsule_schema="hmac_source_capsule_v1",
                seed=effective_seed,
                psnr=self._psnr(original, watermarked),
                message="Watermarked image generated with existing EditGuard image_hiding() pipeline.",
            )
            self._write_job_report(
                job_id,
                "embed",
                job_dir,
                request,
                response,
                {
                    "input_image": self._file_reference(image_path),
                    "payload_path": str(payload_path),
                    "watermarked_image_path": str(watermarked_path),
                },
            )
            return response
        except Exception as exc:
            response = EmbedResponse(
                status="not_implemented",
                job_id=job_id,
                implementation_level="skeleton",
                payload_id=payload_id,
                capsule_bits=capsule_bits,
                auth_hash=auth_hash,
                message=f"Real embed pipeline failed to connect: {type(exc).__name__}: {exc}",
            )
            self._write_job_report(job_id, "embed", job_dir, request, response, {"exception": repr(exc)})
            return response
        finally:
            self._gpu_lock.release()

    def attack_aigc(self, request: AIGCAttackRequest) -> AIGCAttackResponse:
        image_path, error = self._validate_input_image(request.image_path)
        if error:
            return AIGCAttackResponse(
                status="error",
                implementation_level="skeleton",
                attack_type=request.attack_type,
                mode=request.mode,
                message=error,
            )
        if request.attack_type not in ATTACK_TYPES:
            return AIGCAttackResponse(
                status="error",
                implementation_level="skeleton",
                attack_type=request.attack_type,
                mode=request.mode,
                message=f"Unsupported attack_type: {request.attack_type}",
            )

        job_id, job_dir = self._create_phase_dir(request.output_dir, "attack")
        attack_ok, notes = self._attack_runtime_available()
        if not attack_ok:
            response = AIGCAttackResponse(
                status="model_unavailable",
                job_id=job_id,
                implementation_level="skeleton",
                attack_type=request.attack_type,
                mode=request.mode,
                source_image_path=str(image_path),
                message="Real AIGC attack model/cache is unavailable: " + "; ".join(notes),
            )
            self._write_job_report(job_id, "attack", job_dir, request, response, {"notes": notes})
            return response

        self._gpu_lock.acquire()
        try:
            effective_seed = request.seed if request.seed is not None else self._job_seed(job_id)
            self._set_runtime_seed(effective_seed)
            _stage1, _s8c, attack_mod = self._load_research_modules()
            pipe_args = self._attack_args(request)
            pipe = self._get_attack_pipe(attack_mod, pipe_args)
            source = self._load_pil_512(image_path)
            mask, mask_source = self._load_or_create_attack_mask(request.mask_path, source.size, request.attack_type)
            previous_prompt = attack_mod.PROMPTS.get(request.attack_type)
            if request.prompt:
                attack_mod.PROMPTS[request.attack_type] = request.prompt

            start = time.time()
            try:
                diffusion = attack_mod.generate_with_diffusers(
                    pipe,
                    source,
                    mask,
                    request.attack_type,
                    effective_seed,
                    pipe_args,
                )
            finally:
                if request.prompt:
                    if previous_prompt is None:
                        attack_mod.PROMPTS.pop(request.attack_type, None)
                    else:
                        attack_mod.PROMPTS[request.attack_type] = previous_prompt
            runtime = time.time() - start
            mask_arr = np.asarray(mask.convert("L"), dtype=np.float32) / 255.0
            src_arr = np.asarray(source.convert("RGB"), dtype=np.float32)
            diff_arr = np.asarray(diffusion.convert("RGB"), dtype=np.float32)
            if request.mode == "localized_composite":
                alpha = mask_arr[:, :, None]
                attacked_arr = (alpha * diff_arr + (1.0 - alpha) * src_arr).clip(0, 255).astype(np.uint8)
                outside_preserved = bool(np.max(np.abs(attacked_arr[mask_arr < 0.5].astype(np.float32) - src_arr[mask_arr < 0.5])) <= 1.0) if np.any(mask_arr < 0.5) else True
            else:
                attacked_arr = diff_arr.clip(0, 255).astype(np.uint8)
                outside_preserved = False

            mask_path = job_dir / "attack_mask.png"
            diffusion_path = job_dir / "diffusion_output.png"
            attacked_path = job_dir / "attacked.png"
            source_path = job_dir / "source.png"
            source.save(source_path)
            mask.save(mask_path)
            diffusion.save(diffusion_path)
            Image.fromarray(attacked_arr).save(attacked_path)
            response = AIGCAttackResponse(
                status="ok",
                job_id=job_id,
                implementation_level="real_pipeline",
                attack_type=request.attack_type,
                mode=request.mode,
                source_image_path=str(source_path),
                attacked_image_path=str(attacked_path),
                diffusion_output_path=str(diffusion_path),
                mask_path=str(mask_path),
                outside_mask_preserved=outside_preserved,
                seed=effective_seed,
                message=f"AIGC attack generated with cached diffusers inpainting model in {runtime:.2f}s; mask_source={mask_source}.",
            )
            self._write_job_report(
                job_id,
                "attack",
                job_dir,
                request,
                response,
                {
                    "mask_source": mask_source,
                    "runtime_seconds": runtime,
                    "model_id": pipe_args.model_id,
                    "model_revision": pipe_args.model_revision,
                    "hf_cache_dir": pipe_args.model_cache_dir,
                },
            )
            return response
        except Exception as exc:
            response = AIGCAttackResponse(
                status="model_unavailable",
                job_id=job_id,
                implementation_level="skeleton",
                attack_type=request.attack_type,
                mode=request.mode,
                source_image_path=str(image_path),
                message=f"Real AIGC attack pipeline failed to connect: {type(exc).__name__}: {exc}",
            )
            self._write_job_report(job_id, "attack", job_dir, request, response, {"exception": repr(exc)})
            return response
        finally:
            self._gpu_lock.release()

    def verify(self, request: VerifyRequest) -> VerifyResponse:
        image_path, error = self._validate_input_image(request.image_path)
        if error:
            return VerifyResponse(
                status="error",
                implementation_level="skeleton",
                auth_status="not_evaluated",
                payload_recovered=False,
                capsule_recovered=False,
                attack_regime="unknown",
                reports=[],
                **self._localization_channel_vote_response_fields(),
                message=error,
            )

        job_id, job_dir = self._create_phase_dir(request.output_dir, "verify")
        editguard_ok, notes = self._editguard_runtime_available()
        if not editguard_ok:
            response = VerifyResponse(
                status="not_implemented",
                job_id=job_id,
                implementation_level="skeleton",
                auth_status="not_evaluated",
                payload_recovered=False,
                capsule_recovered=False,
                attack_regime="unknown",
                reports=[],
                report_json_path=str(job_dir / "verify_report.json"),
                **self._localization_channel_vote_response_fields(),
                message="Real single-image blind verify is unavailable: " + "; ".join(notes),
            )
            self._write_job_report(job_id, "verify", job_dir, request, response, {"notes": notes})
            return response

        self._gpu_lock.acquire()
        try:
            effective_seed = request.seed if request.seed is not None else DEFAULT_INFERENCE_SEED
            self._set_runtime_seed(effective_seed)
            stage1, _s8c, _attack_mod = self._load_research_modules()
            model = self._get_editguard_model(stage1)
            suspect = self._load_rgb_512(image_path)
            data = stage1.image_to_editguard_batch(suspect)
            data["MES"] = None
            model.feed_data(data)
            pred_mask_raw, recmessage = model.image_recovery(self.recovery_threshold)
            raw_localization_votes = validate_localization_channel_votes(pred_mask_raw)
            if raw_localization_votes.shape != suspect.shape[:2]:
                raise ValueError(
                    "EditGuard localization channel votes must match the recovered "
                    f"image shape {suspect.shape[:2]}; observed "
                    f"{raw_localization_votes.shape}."
                )
            pred_mask = aggregate_localization_channel_votes(
                raw_localization_votes,
                self.localization_channel_vote_min,
                min_component_area_ratio=(
                    self.localization_min_component_area_ratio
                ),
            )
            recovered_bits = self._recovered_bits(recmessage)
            decoded = self._decode_source_payload(recovered_bits)
            decoded = self._bind_decoded_payload_to_registry(decoded)
            predicted_mask_area_ratio = float(pred_mask.mean())
            attack_regime = self._attack_regime(predicted_mask_area_ratio)
            regions = (
                []
                if attack_regime == "no_tamper_detected"
                else self._regions_from_mask(
                    pred_mask, suspect, decoded.get("auth_status", "invalid")
                )
            )
            raw_vote_artifact = self._save_raw_localization_votes(
                job_dir, raw_localization_votes
            )
            pred_mask_path = job_dir / "predicted_mask.png"
            overlay_path = job_dir / "overlay.png"
            report_path = job_dir / "verify_report.json"
            Image.fromarray(pred_mask * 255).save(pred_mask_path)
            overlay_result = None
            if request.return_overlay:
                overlay_result = self._save_overlay(suspect, pred_mask, regions, overlay_path)
            response = VerifyResponse(
                status="ok",
                job_id=job_id,
                implementation_level="real_pipeline",
                auth_status=decoded["auth_status"],
                integrity_check_passed=bool(decoded["integrity_check_passed"]),
                raw_integrity_check_passed=bool(
                    decoded.get("raw_integrity_check_passed", False)
                ),
                corrected_integrity_check_passed=bool(
                    decoded.get("corrected_integrity_check_passed", False)
                ),
                source_registry_match=bool(decoded["source_registry_match"]),
                exact_registry_match=bool(decoded.get("exact_registry_match", False)),
                registry_record_found=bool(decoded.get("registry_record_found", False)),
                correction_applied=bool(decoded.get("correction_applied", False)),
                registry_hamming_distance=decoded.get("registry_hamming_distance"),
                correction_radius=int(
                    decoded.get("correction_radius", self.registry_correction_radius)
                ),
                correction_candidate_count=int(
                    decoded.get("correction_candidate_count", 0)
                ),
                correction_ambiguous=bool(decoded.get("correction_ambiguous", False)),
                registered_owner_id=decoded.get("registered_owner_id"),
                registered_payload_id=decoded.get("registered_payload_id"),
                payload_recovered=bool(decoded["source_registry_match"]),
                capsule_recovered=bool(decoded["capsule_recovered"]),
                bit_accuracy=None,
                recovered_capsule_bits=(
                    self._bits_to_string(recovered_bits) if request.return_recovered_bits else None
                ),
                predicted_mask_path=str(pred_mask_path),
                overlay_path=str(overlay_result) if overlay_result else None,
                report_json_path=str(report_path),
                attack_regime=attack_regime,
                predicted_mask_area_ratio=predicted_mask_area_ratio,
                recovery_threshold=self.recovery_threshold,
                tamper_area_threshold=self.tamper_area_threshold,
                **self._localization_channel_vote_response_fields(),
                raw_localization_votes_path=raw_vote_artifact["path"],
                raw_localization_votes_sha256=raw_vote_artifact["sha256"],
                raw_localization_votes_histogram=raw_vote_artifact["histogram"],
                raw_localization_votes_dtype=raw_vote_artifact["dtype"],
                raw_localization_votes_shape=raw_vote_artifact["shape"],
                raw_localization_votes_encoding=raw_vote_artifact["encoding"],
                capsule_schema="hmac_source_capsule_v1",
                seed=effective_seed,
                reports=regions,
                message=(
                    "Blind verification completed with existing EditGuard image_recovery(). "
                    "No original image or GT mask was accessed. bit_accuracy is unavailable in blind mode."
                ),
            )
            self._write_job_report(
                job_id,
                "verify",
                job_dir,
                request,
                response,
                {
                    "input_image": self._file_reference(image_path),
                    "predicted_mask_area_ratio": predicted_mask_area_ratio,
                    "recovery_threshold": self.recovery_threshold,
                    "tamper_area_threshold": self.tamper_area_threshold,
                    **self._localization_channel_vote_evidence(
                        raw_votes=raw_localization_votes
                    ),
                    "raw_localization_votes_artifact": raw_vote_artifact,
                    "recovered_bits": self._bits_to_string(recovered_bits),
                    "decoded_payload": decoded,
                    "verification_mode": "blind",
                    "original_image_accessed": False,
                    "gt_mask_accessed": False,
                },
            )
            return response
        except Exception as exc:
            response = VerifyResponse(
                status="not_implemented",
                job_id=job_id,
                implementation_level="skeleton",
                auth_status="not_evaluated",
                payload_recovered=False,
                capsule_recovered=False,
                attack_regime="unknown",
                reports=[],
                report_json_path=str(job_dir / "verify_report.json"),
                **self._localization_channel_vote_response_fields(),
                message=f"Real blind verify pipeline failed to connect: {type(exc).__name__}: {exc}",
            )
            self._write_job_report(job_id, "verify", job_dir, request, response, {"exception": repr(exc)})
            return response
        finally:
            self._gpu_lock.release()

    def export_report(self, job_id: str) -> Dict[str, Any]:
        if not self._is_safe_job_id(job_id):
            return {"status": "error", "message": "Invalid job_id format."}
        index_path = self.job_index_dir / f"{job_id}.json"
        if not index_path.exists():
            return {"status": "error", "message": "job_id not found."}
        index = self._read_json(index_path)
        report_path = self._resolve_path(index.get("report_json_path", ""))
        if not report_path.is_file():
            return {
                "status": "error",
                "message": "job report record exists, but report file is missing.",
                "job_id": job_id,
            }
        return self._read_json(report_path)

    def demo(
        self,
        image_path: str,
        owner_id: str,
        attack_type: str,
        mode: str,
        output_dir: str,
    ) -> Dict[str, Any]:
        out = self._resolve_path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        embed = self.embed(
            EmbedRequest(
                image_path=image_path,
                owner_id=owner_id,
                semantic_metadata={},
                output_dir=str(out),
            )
        )
        self._write_json(out / "demo_embed_response.json", _model_to_dict(embed))
        if embed.status != "ok" or not embed.watermarked_image_path:
            summary = {
                "status": "not_implemented",
                "failed_stage": "embed",
                "embed_response": _model_to_dict(embed),
                "message": "Demo stopped because embed did not produce a real watermarked image.",
            }
            self._write_json(out / "demo_summary.json", summary)
            return summary
        attack = self.attack_aigc(
            AIGCAttackRequest(
                image_path=embed.watermarked_image_path,
                attack_type=attack_type,  # type: ignore[arg-type]
                output_dir=str(out),
                mode=mode,  # type: ignore[arg-type]
            )
        )
        self._write_json(out / "demo_attack_response.json", _model_to_dict(attack))
        if attack.status != "ok" or not attack.attacked_image_path:
            summary = {
                "status": "not_implemented",
                "failed_stage": "attack",
                "embed_response": _model_to_dict(embed),
                "attack_response": _model_to_dict(attack),
                "message": "Demo stopped because AIGC attack did not produce a real attacked image.",
            }
            self._write_json(out / "demo_summary.json", summary)
            return summary
        verify = self.verify(VerifyRequest(image_path=attack.attacked_image_path, output_dir=str(out)))
        self._write_json(out / "demo_verify_response.json", _model_to_dict(verify))
        summary = {
            "status": "ok" if verify.status == "ok" else "not_implemented",
            "failed_stage": None if verify.status == "ok" else "verify",
            "embed_response": _model_to_dict(embed),
            "attack_response": _model_to_dict(attack),
            "verify_response": _model_to_dict(verify),
        }
        self._write_json(out / "demo_summary.json", summary)
        return summary

    def run_subprocess(self, command: list[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            cwd=cwd or str(self.project_root),
            check=False,
            text=True,
            capture_output=True,
        )

    def _validate_input_image(self, image_path: str) -> Tuple[Optional[Path], Optional[str]]:
        if not image_path:
            return None, "image_path is required."
        path = self._resolve_path(image_path)
        if not path.exists():
            return None, "Input image path not found."
        if not path.is_file():
            return None, "Input image path is not a file."
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}:
            return None, "Input file extension is not a supported image type."
        return path.resolve(), None

    def _create_phase_dir(self, output_dir: Optional[str], phase: str) -> Tuple[str, Path]:
        root = self._resolve_path(output_dir) if output_dir else self.default_job_root
        job_id = f"{phase}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
        phase_dir = root.resolve() / job_id / phase
        phase_dir.mkdir(parents=True, exist_ok=False)
        return job_id, phase_dir

    def _write_job_report(
        self,
        job_id: str,
        job_type: str,
        job_dir: Path,
        request: Any,
        response: Any,
        extra: Dict[str, Any],
    ) -> None:
        report_path = job_dir / f"{job_type}_report.json"
        payload = {
            "job_id": job_id,
            "job_type": job_type,
            "created_at": self._now(),
            "request": self._sanitize_request_for_report(request),
            "response": _model_to_dict(response),
            "constraints": self._constraints(),
        }
        payload.update(extra)
        self._write_json(report_path, payload)
        self._save_index(job_id, job_type, job_dir, report_path)

    def _load_research_modules(self) -> Tuple[Any, Any, Any]:
        if self._research_modules_cache is not None:
            return self._research_modules_cache
        script_dir = self.project_root / 'protection' / 'image_watermark' / "scripts"
        code_dir = self.project_root / 'third_party' / 'editguard'
        for path in (script_dir, code_dir):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import generate_editguard_outputs_stage1 as stage1
        import run_stage8c_robust_payload_semantic_capsule_audit as s8c
        import run_stage10a_real_aigc_attack_subset as attack_mod

        self._research_modules_cache = (stage1, s8c, attack_mod)
        return self._research_modules_cache

    def _get_editguard_model(self, stage1: Any) -> Any:
        if self._editguard_model_cache is None:
            self._editguard_model_cache = stage1.load_editguard_model(
                self.project_root, self.opt_path, self.ckpt_path
            )
        return self._editguard_model_cache

    def _get_attack_pipe(self, attack_mod: Any, pipe_args: Any) -> Any:
        key = (
            str(pipe_args.model_id),
            str(getattr(pipe_args, "model_revision", None) or ""),
            str(pipe_args.model_cache_dir),
            str(pipe_args.device),
            str(pipe_args.dtype),
        )
        if key not in self._attack_pipe_cache:
            self._attack_pipe_cache[key] = attack_mod.load_diffusers_pipe(
                pipe_args, self.project_root
            )
        return self._attack_pipe_cache[key]

    def _set_runtime_seed(self, seed: int) -> None:
        normalized = int(seed)
        random.seed(normalized)
        np.random.seed(normalized % (2**32))
        try:
            import torch

            torch.manual_seed(normalized)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(normalized)
            if self.deterministic_mode_enabled:
                os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
                torch.backends.cudnn.benchmark = False
                torch.backends.cudnn.deterministic = True
                torch.use_deterministic_algorithms(True, warn_only=True)
        except ImportError:
            return

    def _editguard_runtime_available(self) -> Tuple[bool, List[str]]:
        notes: List[str] = []
        if not self.ckpt_path.exists():
            notes.append(f"missing checkpoint: {self.ckpt_path}")
        if not self.opt_path.exists():
            notes.append(f"missing EditGuard option file: {self.opt_path}")
        try:
            import torch

            if not torch.cuda.is_available():
                notes.append("CUDA is unavailable; current EditGuard test path expects CUDA.")
        except Exception as exc:
            notes.append(f"torch import failed: {type(exc).__name__}: {exc}")
        return len(notes) == 0, notes or ["EditGuard checkpoint/config/CUDA are available."]

    def _attack_runtime_available(self) -> Tuple[bool, List[str]]:
        notes: List[str] = []
        cache_dir = self._hf_cache_dir()
        marker = cache_dir / f"models--{self.attack_model_id.replace('/', '--')}"
        if not marker.exists():
            notes.append(f"missing cached inpainting model: {marker}")
        try:
            import torch

            if not torch.cuda.is_available():
                notes.append("CUDA is unavailable for diffusers inpainting.")
        except Exception as exc:
            notes.append(f"torch import failed: {type(exc).__name__}: {exc}")
        try:
            import diffusers  # noqa: F401
        except Exception as exc:
            notes.append(f"diffusers import failed: {type(exc).__name__}: {exc}")
        return len(notes) == 0, notes or ["Cached Stable Diffusion inpainting model is available."]

    def _attack_args(self, request: AIGCAttackRequest) -> Any:
        import argparse
        import torch

        return argparse.Namespace(
            model_id=self.attack_model_id,
            model_revision=self.attack_model_revision,
            model_cache_dir=str(self._hf_cache_dir()),
            device="cuda" if torch.cuda.is_available() else "cpu",
            dtype="fp16" if torch.cuda.is_available() else "fp32",
            allow_model_download=False,
            num_inference_steps=30,
            guidance_scale=7.5,
            strength=0.95,
        )

    def _hf_cache_dir(self) -> Path:
        return resolve_project_path(os.environ.get("HF_HOME") or "assets/models/hf_cache", self.project_root).resolve()

    def _resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return resolve_project_path(path, self.project_root)
        project_candidate = resolve_project_path(path, self.project_root)
        if project_candidate.exists() or not path.exists():
            return project_candidate
        return path.resolve()

    def _load_rgb_512(self, path: Path) -> np.ndarray:
        return np.asarray(Image.open(path).convert("RGB").resize((512, 512), BICUBIC), dtype=np.uint8)

    def _load_pil_512(self, path: Path) -> Image.Image:
        return Image.open(path).convert("RGB").resize((512, 512), BICUBIC)

    def _load_or_create_attack_mask(self, mask_path: Optional[str], size: Tuple[int, int], attack_type: str) -> Tuple[Image.Image, str]:
        if mask_path:
            path = self._resolve_path(mask_path)
            if not path.exists():
                raise FileNotFoundError(f"mask_path not found: {path}")
            mask = Image.open(path).convert("L").resize(size, NEAREST)
            if np.asarray(mask, dtype=np.uint8).max() == 0:
                raise ValueError(f"mask_path is empty: {path}")
            return mask, "provided_mask"
        width, height = size
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        if attack_type in {"object_removal", "local_replacement"}:
            box = [int(width * 0.36), int(height * 0.34), int(width * 0.66), int(height * 0.66)]
            draw.ellipse(box, fill=255)
        else:
            box = [int(width * 0.30), int(height * 0.32), int(width * 0.70), int(height * 0.68)]
            draw.rounded_rectangle(box, radius=24, fill=255)
        return mask, "auto_demo_mask"

    def _decode_source_payload(self, bits: List[int]) -> Dict[str, Any]:
        if len(bits) < 64:
            return {
                "auth_status": "invalid",
                "auth_success": False,
                "integrity_check_passed": False,
                "raw_integrity_check_passed": False,
                "corrected_integrity_check_passed": False,
                "source_registry_match": False,
                "exact_registry_match": False,
                "registry_record_found": False,
                "capsule_recovered": False,
                "correction_applied": False,
                "registry_hamming_distance": None,
                "correction_radius": self.registry_correction_radius,
                "correction_candidate_count": 0,
                "correction_ambiguous": False,
                "reason": "recovered_bit_length_lt_64",
            }
        bits = [int(v) for v in bits[:64]]
        observed = bits[56:64]
        expected = self._checksum_bits(bits[:56], 8)
        auth_success = observed == expected
        capsule = {
            "copyright_id": self._bits_to_int(bits[0:16]),
            "binding_tag": self._bits_to_int(bits[16:48]),
            "nonce": self._bits_to_int(bits[48:56]),
            "checksum_bits": self._bits_to_string(observed),
        }
        return {
            "auth_status": "checksum_valid_unregistered" if auth_success else "invalid",
            "auth_success": False,
            "integrity_check_passed": auth_success,
            "raw_integrity_check_passed": auth_success,
            "corrected_integrity_check_passed": False,
            "source_registry_match": False,
            "exact_registry_match": False,
            "registry_record_found": False,
            "capsule_recovered": auth_success,
            "correction_applied": False,
            "registry_hamming_distance": None,
            "correction_radius": self.registry_correction_radius,
            "correction_candidate_count": 0,
            "correction_ambiguous": False,
            "capsule_bits": self._bits_to_string(bits),
            "semantic_capsule": capsule,
        }

    # Kept as a narrow compatibility alias for older tests/tools. New code and
    # reports use the HMAC source-capsule name above.
    def _decode_p2_payload(self, bits: List[int]) -> Dict[str, Any]:
        return self._decode_source_payload(bits)

    def _bind_decoded_payload_to_registry(self, decoded: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(decoded)
        result.setdefault(
            "raw_integrity_check_passed", bool(result.get("integrity_check_passed"))
        )
        result.setdefault("corrected_integrity_check_passed", False)
        result.setdefault("correction_applied", False)
        result.setdefault("registry_hamming_distance", None)
        result.setdefault("correction_radius", self.registry_correction_radius)
        result.setdefault("correction_candidate_count", 0)
        result.setdefault("correction_ambiguous", False)

        recovered_capsule_bits = str(result.get("capsule_bits") or "")

        # Preserve the existing exact-match path and return immediately on success.
        if result.get("integrity_check_passed"):
            capsule = result.get("semantic_capsule") or {}
            copyright_id = capsule.get("copyright_id")
            record = self._read_payload_registry(copyright_id)
            if not record:
                result["auth_status"] = "checksum_valid_unregistered"
            else:
                result["registry_record_found"] = True
                if record.get("schema_version") != "cogniguard_source_registry_v2":
                    result["auth_status"] = "legacy_registry_record_unsupported"
                    return result
                recovered_hash = hashlib.sha256(
                    recovered_capsule_bits.encode("utf-8")
                ).hexdigest()
                payload_id = str(record.get("payload_id") or "")
                recovered_auth_hash = self._payload_auth_hash(
                    [int(bit) for bit in recovered_capsule_bits], payload_id
                )
                nonce = int(capsule.get("nonce") or 0)
                expected_id, expected_tag = self._source_capsule_identity(payload_id, nonce)
                keyed_fields_match = bool(
                    int(copyright_id) == expected_id
                    and int(capsule.get("binding_tag") or -1) == expected_tag
                )
                exact_match = bool(
                    keyed_fields_match
                    and len(recovered_capsule_bits) == 64
                    and hmac.compare_digest(
                        recovered_hash, str(record.get("capsule_bits_sha256") or "")
                    )
                    and hmac.compare_digest(
                        recovered_auth_hash, str(record.get("auth_hash") or "")
                    )
                )
                if exact_match:
                    result.update(
                        {
                            "auth_status": "registered_source",
                            "auth_success": True,
                            "source_registry_match": True,
                            "exact_registry_match": True,
                            "registry_hamming_distance": 0,
                            "registered_owner_id": record.get("owner_id"),
                            "registered_payload_id": record.get("payload_id"),
                            "registry_auth_level": record.get("auth_level"),
                        }
                    )
                    return result
                result.update(
                    {
                        "auth_status": "registry_payload_mismatch",
                        "auth_success": False,
                        "source_registry_match": False,
                        "exact_registry_match": False,
                    }
                )

        # Closed-set correction is deliberately separate from exact authentication.
        # A corrupt codebook, no match, or an ambiguous match all fail closed.
        try:
            correction = self._find_unique_registry_candidate(
                recovered_capsule_bits,
                radius=self.registry_correction_radius,
            )
        except (OSError, RuntimeError, ValueError):
            return result

        result["correction_candidate_count"] = correction["candidate_count"]
        result["correction_ambiguous"] = correction["ambiguous"]
        candidate = correction.get("candidate")
        distance = correction.get("distance")
        if candidate is None or distance != 1:
            return result

        # Revalidate the selected record from disk so a stale cache cannot turn a
        # concurrent removal or out-of-band registry corruption into acceptance.
        live_record = self._read_payload_registry(candidate.get("copyright_id"))
        try:
            live_candidate = self._validate_registry_record(live_record or {})
        except (RuntimeError, ValueError):
            result["correction_candidate_count"] = 0
            return result
        if (
            live_candidate["capsule_int"] != candidate["capsule_int"]
            or live_candidate["record"] != candidate["record"]
        ):
            result["correction_candidate_count"] = 0
            return result

        record = live_candidate["record"]
        result.update(
            {
                "auth_status": "registered_source_corrected",
                "auth_success": True,
                "source_registry_match": True,
                "exact_registry_match": False,
                "registry_record_found": True,
                "capsule_recovered": True,
                "corrected_integrity_check_passed": True,
                "correction_applied": True,
                "registry_hamming_distance": distance,
                "registered_owner_id": record.get("owner_id"),
                "registered_payload_id": record.get("payload_id"),
                "registry_auth_level": record.get("auth_level"),
            }
        )
        return result

    def _regions_from_mask(self, pred_mask: np.ndarray, image: np.ndarray, auth_status: str) -> List[ReportRegion]:
        try:
            import cv2

            num, labels, stats, centroids = cv2.connectedComponentsWithStats(pred_mask.astype(np.uint8), 8)
        except Exception:
            return []
        height, width = pred_mask.shape
        image_area = float(height * width)
        reports: List[ReportRegion] = []
        for idx in range(1, num):
            area = int(stats[idx, cv2.CC_STAT_AREA])
            if area <= 0:
                continue
            x = int(stats[idx, cv2.CC_STAT_LEFT])
            y = int(stats[idx, cv2.CC_STAT_TOP])
            w = int(stats[idx, cv2.CC_STAT_WIDTH])
            h = int(stats[idx, cv2.CC_STAT_HEIGHT])
            region_mask = labels == idx
            area_ratio = float(area / image_area)
            cx, cy = centroids[idx]
            center_score = self._center_score(float(cx), float(cy), width, height)
            crop_values = image[region_mask]
            gray = crop_values.mean(axis=1) if crop_values.size else np.asarray([0.0])
            contrast = float(np.std(gray) / 255.0)
            brightness = float(np.mean(gray) / 255.0)
            severity = self._severity_from_region(area_ratio, center_score)
            change_type = self._change_type_from_region(area_ratio, contrast, brightness, center_score)
            confidence = float(min(1.0, 0.25 + 3.0 * area_ratio + 0.35 * contrast + 0.20 * center_score))
            reports.append(
                ReportRegion(
                    region_id=len(reports) + 1,
                    bbox=[x, y, x + w, y + h],
                    area_ratio=area_ratio,
                    change_type=change_type,
                    severity=severity,
                    auth_status=auth_status,
                    confidence=confidence,
                )
            )
        return reports

    def _save_overlay(self, image: np.ndarray, pred_mask: np.ndarray, regions: List[ReportRegion], path: Path) -> Path:
        base = Image.fromarray(image).convert("RGBA")
        overlay = Image.new("RGBA", base.size, (255, 0, 0, 0))
        mask = Image.fromarray((pred_mask.astype(np.uint8) * 110), mode="L")
        red = Image.new("RGBA", base.size, (255, 0, 0, 110))
        overlay.paste(red, (0, 0), mask)
        out = Image.alpha_composite(base, overlay).convert("RGB")
        draw = ImageDraw.Draw(out)
        for region in regions:
            if len(region.bbox) == 4:
                draw.rectangle(region.bbox, outline=(255, 255, 0), width=2)
                draw.text((region.bbox[0] + 2, region.bbox[1] + 2), f"{region.region_id}:{region.severity}", fill=(255, 255, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(path)
        return path

    def _recovered_bits(self, remesg: Any) -> List[int]:
        arr = remesg.detach().float().cpu().numpy().reshape(-1)
        return [int(v > 0) for v in arr]

    def _build_capsule_preview(self, owner_id: str, metadata: Dict[str, Any]) -> Tuple[str, str, str]:
        payload_id = self._payload_binding_id(owner_id, metadata)[:16]
        copyright_id, binding_tag = self._source_capsule_identity(payload_id, 0)
        prefix = (
            self._int_to_bits(copyright_id, 16)
            + self._int_to_bits(binding_tag, 32)
            + self._int_to_bits(0, 8)
        )
        bits = prefix + self._checksum_bits(prefix, 8)
        capsule_bits = self._bits_to_string(bits)
        auth_hash = self._payload_auth_hash(bits, payload_id)
        return capsule_bits, payload_id, auth_hash

    def _payload_binding_id(self, owner_id: str, metadata: Dict[str, Any]) -> str:
        canonical = json.dumps(
            {"owner_id": owner_id, "semantic_metadata": metadata or {}},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hmac.new(self.registry_secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def _canonical_sha256(self, payload: Any) -> str:
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _sanitize_request_for_report(self, request: Any) -> Dict[str, Any]:
        payload = _model_to_dict(request)
        for field in ("image_path", "mask_path"):
            raw_path = payload.pop(field, None)
            if raw_path:
                payload[field.replace("_path", "_reference")] = self._file_reference(raw_path)
        payload.pop("output_dir", None)
        owner_id = payload.pop("owner_id", None)
        if owner_id:
            payload["owner_reference"] = hmac.new(
                self.registry_secret,
                str(owner_id).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()[:16]
        metadata = payload.pop("semantic_metadata", None)
        if metadata is not None:
            payload["semantic_metadata_keys"] = sorted(metadata) if isinstance(metadata, dict) else []
            payload["semantic_metadata_sha256"] = self._canonical_sha256(metadata)
        prompt = payload.pop("prompt", None)
        if prompt:
            payload["prompt_sha256"] = hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()
        return payload

    def _file_reference(self, value: str | Path) -> Dict[str, Any]:
        path = self._resolve_path(str(value))
        reference: Dict[str, Any] = {"suffix": path.suffix.lower()}
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            reference["sha256"] = digest.hexdigest()
            reference["size_bytes"] = path.stat().st_size
        else:
            reference["path_sha256"] = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
        return reference

    def _payload_auth_hash(self, bits: List[int], payload_id: str) -> str:
        message = f"{payload_id}|{self._bits_to_string(bits)}".encode("utf-8")
        return hmac.new(self.registry_secret, message, hashlib.sha256).hexdigest()[:16]

    def _capsule_bits_for_identity(self, payload_id: str, nonce: int) -> List[int]:
        copyright_id, binding_tag = self._source_capsule_identity(payload_id, nonce)
        prefix = (
            self._int_to_bits(copyright_id, 16)
            + self._int_to_bits(binding_tag, 32)
            + self._int_to_bits(nonce, 8)
        )
        return prefix + self._checksum_bits(prefix, 8)

    def _validate_registry_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Reconstruct and authenticate one registry codeword without trusting stored bits."""
        if not isinstance(record, dict):
            raise ValueError("Invalid registry record.")
        if record.get("schema_version") != "cogniguard_source_registry_v2":
            raise ValueError("Unsupported registry record schema.")
        if record.get("capsule_schema") != "hmac_source_capsule_v1":
            raise ValueError("Unsupported capsule schema.")

        payload_id = record.get("payload_id")
        owner_id = record.get("owner_id")
        if not isinstance(payload_id, str) or not payload_id:
            raise ValueError("Invalid registry payload id.")
        if not isinstance(owner_id, str) or not owner_id:
            raise ValueError("Invalid registry owner id.")
        try:
            copyright_id = int(record.get("copyright_id"))
            payload_seed = int(record.get("payload_seed"))
            nonce_value = record.get("nonce")
            nonce = (
                int(nonce_value)
                if nonce_value is not None
                else payload_seed - DEFAULT_PAYLOAD_SEED
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid registry capsule identity fields.") from exc
        if payload_seed != DEFAULT_PAYLOAD_SEED + nonce:
            raise ValueError("Registry payload seed and nonce disagree.")

        bits = self._capsule_bits_for_identity(payload_id, nonce)
        expected_copyright_id = self._bits_to_int(bits[:16])
        if copyright_id != expected_copyright_id:
            raise ValueError("Registry copyright id failed keyed reconstruction.")
        capsule_bits = self._bits_to_string(bits)
        capsule_hash = hashlib.sha256(capsule_bits.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(
            capsule_hash, str(record.get("capsule_bits_sha256") or "")
        ):
            raise ValueError("Registry capsule hash validation failed.")
        expected_auth_hash = self._payload_auth_hash(bits, payload_id)
        if not hmac.compare_digest(
            expected_auth_hash, str(record.get("auth_hash") or "")
        ):
            raise ValueError("Registry authentication validation failed.")
        return {
            "copyright_id": copyright_id,
            "payload_id": payload_id,
            "nonce": nonce,
            "capsule_bits": capsule_bits,
            "capsule_int": int(capsule_bits, 2),
            "record": dict(record),
        }

    def _registry_directory_fingerprint(
        self,
    ) -> Tuple[Tuple[str, int, int, int], ...]:
        if not self.payload_registry_dir.exists():
            return ()
        fingerprint: List[Tuple[str, int, int, int]] = []
        try:
            paths = sorted(self.payload_registry_dir.glob("*.json"))
            for path in paths:
                stat = path.stat()
                fingerprint.append(
                    (path.name, int(stat.st_size), int(stat.st_mtime_ns), int(stat.st_ctime_ns))
                )
        except OSError as exc:
            raise RuntimeError("Registry changed while its fingerprint was read.") from exc
        return tuple(fingerprint)

    def _load_registry_codebook_locked(self) -> Tuple[Dict[str, Any], ...]:
        fingerprint_before = self._registry_directory_fingerprint()
        entries: List[Dict[str, Any]] = []
        if self.payload_registry_dir.exists():
            for path in sorted(self.payload_registry_dir.glob("*.json")):
                try:
                    raw_record = self._read_json(path)
                    entry = self._validate_registry_record(raw_record)
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                    raise RuntimeError("Registry codebook validation failed.") from exc
                expected_path = self._registry_path(entry["copyright_id"])
                if expected_path is None or path.name != expected_path.name:
                    raise RuntimeError("Registry codebook path validation failed.")
                entries.append(entry)

        seen_ids: set[int] = set()
        seen_codewords: set[int] = set()
        minimum_distance: Optional[int] = None
        for index, entry in enumerate(entries):
            copyright_id = int(entry["copyright_id"])
            codeword = int(entry["capsule_int"])
            if copyright_id in seen_ids or codeword in seen_codewords:
                raise RuntimeError("Registry codebook contains duplicate records.")
            seen_ids.add(copyright_id)
            seen_codewords.add(codeword)
            for previous in entries[:index]:
                distance = self._hamming_distance64(
                    codeword, int(previous["capsule_int"])
                )
                minimum_distance = (
                    distance
                    if minimum_distance is None
                    else min(minimum_distance, distance)
                )
                if distance < self.registry_minimum_distance:
                    raise RuntimeError("Registry codebook minimum distance validation failed.")

        fingerprint_after = self._registry_directory_fingerprint()
        if fingerprint_before != fingerprint_after:
            raise RuntimeError("Registry changed while the codebook was loaded.")
        self._registry_codebook_cache = tuple(entries)
        self._registry_codebook_min_distance = minimum_distance
        self._registry_codebook_fingerprint = fingerprint_after
        return self._registry_codebook_cache

    def _load_registry_codebook(self) -> Tuple[Dict[str, Any], ...]:
        with self._registry_lock:
            return self._load_registry_codebook_locked()

    def _get_registry_codebook(self) -> Tuple[Dict[str, Any], ...]:
        with self._registry_lock:
            current_fingerprint = self._registry_directory_fingerprint()
            if (
                self._registry_codebook_cache is None
                or self._registry_codebook_fingerprint != current_fingerprint
            ):
                return self._load_registry_codebook_locked()
            return self._registry_codebook_cache

    def _find_unique_registry_candidate(
        self, raw_capsule_bits: str, *, radius: int
    ) -> Dict[str, Any]:
        if radius not in {0, 1, 2}:
            raise ValueError("Registry Hamming radius must be 0, 1, or 2.")
        if len(raw_capsule_bits) != 64 or any(
            bit not in {"0", "1"} for bit in raw_capsule_bits
        ):
            return {
                "candidate": None,
                "distance": None,
                "candidate_count": 0,
                "ambiguous": False,
            }

        raw_value = int(raw_capsule_bits, 2)
        candidates: List[Tuple[int, Dict[str, Any]]] = []
        for entry in self._get_registry_codebook():
            distance = self._hamming_distance64(raw_value, int(entry["capsule_int"]))
            if distance <= radius:
                candidates.append((distance, entry))
        if len(candidates) != 1:
            return {
                "candidate": None,
                "distance": None,
                "candidate_count": len(candidates),
                "ambiguous": len(candidates) > 1,
            }
        distance, candidate = candidates[0]
        return {
            "candidate": candidate,
            "distance": distance,
            "candidate_count": 1,
            "ambiguous": False,
        }

    def _hamming_distance64(self, left: int, right: int) -> int:
        return (int(left) ^ int(right)).bit_count()

    def _build_unique_registered_payload(
        self,
        *,
        payload_id: str,
    ) -> Tuple[Dict[str, Any], int]:
        with self._registry_lock:
            codebook = self._get_registry_codebook()
            entries_by_id = {
                int(entry["copyright_id"]): entry for entry in codebook
            }
            for nonce in range(256):
                seed = DEFAULT_PAYLOAD_SEED + nonce
                bits = self._capsule_bits_for_identity(payload_id, nonce)
                copyright_id = self._bits_to_int(bits[:16])
                binding_tag = self._bits_to_int(bits[16:48])
                payload = {
                    "capsule_schema": "hmac_source_capsule_v1",
                    "copyright_id": copyright_id,
                    "binding_tag": binding_tag,
                    "nonce": nonce,
                    "bits": bits,
                }
                capsule_bits = self._bits_to_string(bits)
                existing = entries_by_id.get(copyright_id)
                if existing is not None:
                    if (
                        existing["payload_id"] == payload_id
                        and hmac.compare_digest(
                            capsule_bits, str(existing["capsule_bits"])
                        )
                    ):
                        return payload, seed
                    continue
                candidate_int = int(capsule_bits, 2)
                if all(
                    self._hamming_distance64(candidate_int, int(entry["capsule_int"]))
                    >= self.registry_minimum_distance
                    for entry in codebook
                ):
                    return payload, seed
        raise RuntimeError("Could not allocate a collision-free 16-bit copyright id.")

    def _source_capsule_identity(self, payload_id: str, nonce: int) -> Tuple[int, int]:
        if not 0 <= int(nonce) <= 0xFF:
            raise ValueError(f"Capsule nonce must fit in 8 bits: {nonce}")
        digest = hmac.new(
            self.registry_secret,
            f"hmac_source_capsule_v1|{payload_id}|{int(nonce)}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return int.from_bytes(digest[:2], "big"), int.from_bytes(digest[2:6], "big")

    def _registry_path(self, copyright_id: Any) -> Path | None:
        try:
            normalized = int(copyright_id)
        except (TypeError, ValueError):
            return None
        if normalized < 0 or normalized > 0xFFFF:
            return None
        return self.payload_registry_dir / f"{normalized:05d}.json"

    def _read_payload_registry(self, copyright_id: Any) -> Dict[str, Any] | None:
        path = self._registry_path(copyright_id)
        if path is None or not path.exists():
            return None
        try:
            payload = self._read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _register_payload(
        self,
        *,
        copyright_id: int,
        owner_id: str,
        semantic_metadata: Dict[str, Any],
        payload_id: str,
        payload_seed: int,
        capsule_bits: str,
        auth_hash: str,
        embed_job_id: str,
    ) -> None:
        with self._registry_lock:
            path = self._registry_path(copyright_id)
            if path is None:
                raise ValueError(f"Invalid copyright id: {copyright_id}")
            codebook = self._get_registry_codebook()
            existing = next(
                (
                    entry
                    for entry in codebook
                    if int(entry["copyright_id"]) == int(copyright_id)
                ),
                None,
            )
            if len(capsule_bits) != 64 or any(bit not in {"0", "1"} for bit in capsule_bits):
                raise ValueError("Capsule bits must be exactly 64 binary digits.")
            capsule_hash = hashlib.sha256(capsule_bits.encode("utf-8")).hexdigest()
            if existing is not None:
                same_record = bool(
                    existing["payload_id"] == payload_id
                    and hmac.compare_digest(
                        str(existing["capsule_bits"]), capsule_bits
                    )
                )
                if same_record:
                    return
                raise RuntimeError(f"Copyright id collision for {copyright_id}.")
            metadata_canonical = json.dumps(
                semantic_metadata or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            nonce = int(payload_seed) - DEFAULT_PAYLOAD_SEED
            record = {
                "schema_version": "cogniguard_source_registry_v2",
                "capsule_schema": "hmac_source_capsule_v1",
                "copyright_id": copyright_id,
                "owner_id": owner_id,
                "payload_id": payload_id,
                "payload_seed": payload_seed,
                "nonce": nonce,
                "capsule_bits_sha256": capsule_hash,
                "semantic_metadata_sha256": hashlib.sha256(
                    metadata_canonical.encode("utf-8")
                ).hexdigest(),
                "auth_hash": auth_hash,
                "auth_level": self._registry_auth_level(),
                "embed_job_id": embed_job_id,
                "created_at": self._now(),
            }
            new_entry = self._validate_registry_record(record)
            distances = [
                self._hamming_distance64(
                    int(new_entry["capsule_int"]), int(entry["capsule_int"])
                )
                for entry in codebook
            ]
            if any(distance < self.registry_minimum_distance for distance in distances):
                raise RuntimeError("Registry codeword minimum distance validation failed.")

            self._write_json(path, record)
            self._registry_codebook_cache = tuple(
                sorted(
                    (*codebook, new_entry),
                    key=lambda entry: int(entry["copyright_id"]),
                )
            )
            self._registry_codebook_fingerprint = self._registry_directory_fingerprint()
            new_minimum = min(distances) if distances else None
            if self._registry_codebook_min_distance is None:
                self._registry_codebook_min_distance = new_minimum
            elif new_minimum is not None:
                self._registry_codebook_min_distance = min(
                    self._registry_codebook_min_distance, new_minimum
                )

    def _registry_auth_level(self) -> str:
        return "hmac_registry" if self.registry_secret_configured else "development_registry"

    def _checksum_bits(self, payload_bits: List[int], length: int = 8) -> List[int]:
        digest = hashlib.sha256(self._bits_to_string(payload_bits).encode("utf-8")).digest()
        out: List[int] = []
        for byte in digest:
            out.extend([(byte >> shift) & 1 for shift in range(7, -1, -1)])
            if len(out) >= length:
                return out[:length]
        return out[:length]

    def _bits_to_string(self, bits: List[int]) -> str:
        return "".join(str(int(bit)) for bit in bits)

    def _bits_to_int(self, bits: List[int]) -> int:
        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        return value

    def _int_to_bits(self, value: int, length: int) -> List[int]:
        normalized = int(value)
        if normalized < 0 or normalized >= (1 << length):
            raise ValueError(f"Value {normalized} does not fit in {length} bits.")
        return [(normalized >> shift) & 1 for shift in range(length - 1, -1, -1)]

    def _psnr(self, a: np.ndarray, b: np.ndarray) -> Optional[float]:
        mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
        if mse <= 0:
            return None
        return float(20.0 * math.log10(255.0 / math.sqrt(mse)))

    def _center_score(self, cx: float, cy: float, width: int, height: int) -> float:
        max_dist = math.sqrt((width / 2.0) ** 2 + (height / 2.0) ** 2)
        dist = math.sqrt((cx - width / 2.0) ** 2 + (cy - height / 2.0) ** 2)
        return float(max(0.0, 1.0 - dist / max_dist))

    def _severity_from_region(self, area_ratio: float, center_score: float) -> str:
        score = min(1.0, 8.0 * area_ratio + 0.35 * center_score)
        if score >= 0.75:
            return "critical"
        if score >= 0.50:
            return "high"
        if score >= 0.25:
            return "medium"
        return "low"

    def _change_type_from_region(self, area_ratio: float, contrast: float, brightness: float, center_score: float) -> str:
        if brightness < 0.18 and area_ratio > 0.002:
            return "removal_or_occlusion"
        if contrast > 0.22:
            return "texture_change"
        if area_ratio > 0.03 or center_score > 0.75:
            return "risk_region_change"
        if brightness > 0.70:
            return "color_change"
        return "unknown"

    def _attack_regime(self, pred_area_ratio: float) -> str:
        if pred_area_ratio > 0.80:
            return "global_rerendering_or_watermark_laundering"
        if pred_area_ratio > self.tamper_area_threshold:
            return "localized_tamper_candidate"
        return "no_tamper_detected"

    def _resolve_localization_channel_vote_min(
        self, explicit_value: Optional[int]
    ) -> int:
        if explicit_value is None:
            raw = os.environ.get(
                "SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN", ""
            ).strip()
            if not raw:
                return DEFAULT_LOCALIZATION_CHANNEL_VOTE_MIN
            if not re.fullmatch(r"[1-3]", raw):
                raise ValueError(
                    "SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN must be an "
                    "integer from 1 to 3."
                )
            return int(raw)
        if isinstance(explicit_value, bool) or not isinstance(
            explicit_value, (int, np.integer)
        ):
            raise ValueError(
                "localization_channel_vote_min must be an integer from 1 to 3."
            )
        normalized = int(explicit_value)
        if not 1 <= normalized <= LOCALIZATION_CHANNEL_COUNT:
            raise ValueError(
                "localization_channel_vote_min must be an integer from 1 to 3."
            )
        return normalized

    def _localization_channel_vote_response_fields(self) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            "localization_postprocessing": self._localization_postprocessing(),
            "localization_mask_rule_version": (
                LOCALIZATION_MASK_RULE_VERSION_V3
                if self.localization_min_component_area_ratio > 0.0
                else LOCALIZATION_MASK_RULE_VERSION_V2
            ),
            "localization_residual_channels": LOCALIZATION_CHANNEL_COUNT,
            "localization_channel_aggregation": LOCALIZATION_CHANNEL_AGGREGATION,
            "localization_channel_vote_min": self.localization_channel_vote_min,
            "localization_residual_threshold_rule": LOCALIZATION_RESIDUAL_THRESHOLD_RULE,
        }
        if self.localization_min_component_area_ratio > 0.0:
            fields.update(
                {
                    "localization_component_connectivity": (
                        LOCALIZATION_COMPONENT_CONNECTIVITY
                    ),
                    "localization_min_component_area_ratio": (
                        self.localization_min_component_area_ratio
                    ),
                    "localization_component_area_rounding": (
                        LOCALIZATION_COMPONENT_AREA_ROUNDING
                    ),
                }
            )
        return fields

    def _localization_postprocessing(self) -> str:
        return (
            LOCALIZATION_POSTPROCESSING_CC8
            if self.localization_min_component_area_ratio > 0.0
            else LOCALIZATION_POSTPROCESSING_NONE
        )

    def _localization_channel_vote_evidence(
        self, *, raw_votes: np.ndarray | None = None
    ) -> Dict[str, Any]:
        evidence = self._localization_channel_vote_response_fields()
        evidence["resolved_raw_vote_threshold"] = (
            255 * self.localization_channel_vote_min
        )
        if self.localization_min_component_area_ratio > 0.0:
            if raw_votes is not None:
                normalized_votes = validate_localization_channel_votes(raw_votes)
                pre_filter = normalized_votes >= (
                    255 * self.localization_channel_vote_min
                )
                minimum_pixels = int(
                    math.ceil(
                        self.localization_min_component_area_ratio
                        * pre_filter.size
                    )
                )
                labels, component_count = ndimage.label(
                    pre_filter,
                    structure=np.ones((3, 3), dtype=np.uint8),
                )
                component_sizes = (
                    np.bincount(labels.ravel())
                    if component_count
                    else np.asarray([pre_filter.size], dtype=np.int64)
                )
                retained = component_sizes[1:] >= minimum_pixels
                evidence.update(
                    {
                        "resolved_min_component_pixels": minimum_pixels,
                        "pre_filter_mask_area_ratio": float(pre_filter.mean()),
                        "pre_filter_component_count": int(component_count),
                        "retained_component_count": int(
                            np.count_nonzero(retained)
                        ),
                        "discarded_foreground_pixels": int(
                            component_sizes[1:].sum()
                            - component_sizes[1:][retained].sum()
                        ),
                    }
                )
        return evidence

    def _save_raw_localization_votes(
        self, job_dir: Path, pred_mask_raw: np.ndarray
    ) -> Dict[str, Any]:
        raw_votes = validate_localization_channel_votes(pred_mask_raw)
        artifact_path = job_dir / "raw_localization_channel_votes.uint16.png"
        temporary = artifact_path.with_name(
            f".{artifact_path.name}.{uuid4().hex}.tmp"
        )
        try:
            with temporary.open("wb") as handle:
                raw_vote_image = Image.fromarray(raw_votes)
                if raw_vote_image.mode != "I;16":
                    raise RuntimeError(
                        "Raw localization vote artifact must use Pillow I;16 mode."
                    )
                raw_vote_image.save(
                    handle,
                    format="PNG",
                    compress_level=6,
                )
            os.replace(temporary, artifact_path)
        finally:
            temporary.unlink(missing_ok=True)
        digest = hashlib.sha256()
        with artifact_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        histogram = {
            str(value): int(np.count_nonzero(raw_votes == value))
            for value in LOCALIZATION_CHANNEL_VOTE_VALUES
        }
        return {
            "path": str(artifact_path),
            "sha256": digest.hexdigest(),
            "dtype": str(raw_votes.dtype),
            "shape": [int(size) for size in raw_votes.shape],
            "encoding": "lossless_png_16bit_grayscale_I;16",
            "histogram": histogram,
        }

    def _probability_from_env(self, name: str, default: float) -> float:
        raw = os.environ.get(name, "").strip()
        if not raw:
            return float(default)
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be a finite number strictly between 0 and 1.") from exc
        if not math.isfinite(value) or not 0.0 < value < 1.0:
            raise ValueError(f"{name} must be a finite number strictly between 0 and 1.")
        return value

    def _job_seed(self, job_id: str) -> int:
        return int(hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:8], 16)

    def _save_index(self, job_id: str, job_type: str, job_dir: Path, report_path: Path) -> None:
        self.job_index_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self.job_index_dir / f"{job_id}.json",
            {
                "job_id": job_id,
                "job_type": job_type,
                "job_dir": str(job_dir),
                "report_json_path": str(report_path),
                "created_at": self._now(),
            },
        )

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)

    def _read_json(self, path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _constraints(self) -> Dict[str, Any]:
        return {
            "no_training": True,
            "no_vlm": True,
            "no_128bit_payload": True,
            "watermark_embedding_modified": False,
            "verification_is_blind": True,
            "original_image_api_input": False,
            "gt_mask_api_input": False,
            "semantic_report_type": "coarse_rule_based",
            "robust_payload_bits": 64,
            "payload_integrity": "8_bit_checksum",
            "source_binding": (
                "32_bit_hmac_tag_plus_exact_server_registry_plus_"
                "closed_set_unique_radius_1_correction"
            ),
            "registry_aided_decoding": "closed_set_unique_nearest_neighbor",
            "registry_error_correction_enabled": True,
            "registry_hamming_radius": self.registry_correction_radius,
            "registry_minimum_distance_required": self.registry_minimum_distance,
            "corrected_matches_are_exact": False,
            "recovery_threshold": self.recovery_threshold,
            "tamper_area_threshold": self.tamper_area_threshold,
            **self._localization_channel_vote_evidence(),
            "capsule_schema": "hmac_source_capsule_v1",
            "known_limitation": "valid_watermark_copy_or_replay_requires_separate_detection",
            "registry_secret_configured": self.registry_secret_configured,
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_safe_job_id(self, job_id: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", job_id or ""))

    def copy_artifact(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
