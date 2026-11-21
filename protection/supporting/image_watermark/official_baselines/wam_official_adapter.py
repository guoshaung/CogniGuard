"""Independent adapter for Meta's pinned official Watermark Anything model.

The adapter deliberately does not plug WAM into CogniGuard's 64-bit registry.
It evaluates WAM in its native 32-bit message-recovery and per-pixel
watermark-presence setting.  A mock backend can be injected for contract tests;
the official backend always performs the pinned fail-closed preflight before it
imports or deserializes model code/weights.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np
from PIL import Image

from protection.supporting.image_watermark.official_baselines.wam_official_contract import (
    NATIVE_SEMANTICS,
    OFFICIAL_WAM_MIT,
    pinned_provenance,
)
from protection.supporting.image_watermark.official_baselines.wam_official_preflight import (
    WamPreflightError,
    _device_index,
    require_ready,
    run_preflight,
)


class WamAdapterError(RuntimeError):
    """Base error for invalid inputs, outputs, or runtime state."""


class WamDependencyError(WamAdapterError):
    """Raised when the independent official runtime is unavailable."""


class WamOutputContractError(WamAdapterError):
    """Raised when a backend violates WAM's native output contract."""


@dataclass(frozen=True)
class WamDetectionOutput:
    """Native detector outputs before message aggregation."""

    watermark_probability: np.ndarray  # H x W, sigmoid of channel 0
    message_logits: np.ndarray  # 32 x H x W, channels 1:33


class WamBackend(Protocol):
    """Injectable backend boundary used by the independent adapter."""

    def embed(self, image_rgb: np.ndarray, message_bits: np.ndarray) -> np.ndarray:
        """Return a full-frame WAM candidate in RGB uint8 format."""

    def detect(self, image_rgb: np.ndarray) -> WamDetectionOutput:
        """Return one mask-probability channel and 32 message-logit channels."""

    def runtime_provenance(self) -> dict[str, Any]:
        """Return immutable release/runtime provenance for the result row."""


@dataclass(frozen=True)
class WamEmbedResult:
    watermarked_image: np.ndarray
    embedding_mask: np.ndarray
    record: dict[str, Any]


@dataclass(frozen=True)
class WamVerifyResult:
    watermark_probability: np.ndarray
    watermark_mask: np.ndarray
    predicted_tamper_mask: np.ndarray | None
    record: dict[str, Any]


def _validate_image(image: np.ndarray, label: str) -> np.ndarray:
    array = np.asarray(image)
    if array.dtype != np.uint8:
        raise WamAdapterError(f"{label} must be RGB uint8, got {array.dtype}.")
    if array.ndim != 3 or array.shape[2] != 3:
        raise WamAdapterError(f"{label} must have shape HxWx3, got {array.shape}.")
    if array.shape[0] < 2 or array.shape[1] < 2:
        raise WamAdapterError(f"{label} is too small for evaluation: {array.shape}.")
    return np.ascontiguousarray(array)


def _validate_message(message_bits: np.ndarray | str) -> np.ndarray:
    if isinstance(message_bits, str):
        if len(message_bits) != OFFICIAL_WAM_MIT.message_bits or any(
            bit not in "01" for bit in message_bits
        ):
            raise WamAdapterError("WAM message must be exactly 32 binary characters.")
        return np.fromiter((bit == "1" for bit in message_bits), dtype=np.bool_)
    bits = np.asarray(message_bits)
    if bits.shape != (OFFICIAL_WAM_MIT.message_bits,):
        raise WamAdapterError(
            "WAM retains its native 32-bit message; 64-bit capsules are not accepted."
        )
    if not np.logical_or(bits == 0, bits == 1).all():
        raise WamAdapterError("WAM message values must be binary (0 or 1).")
    return bits.astype(np.bool_, copy=False)


def _validate_mask(mask: np.ndarray, shape: tuple[int, int], label: str) -> np.ndarray:
    array = np.asarray(mask)
    if array.shape != shape:
        raise WamAdapterError(f"{label} must have shape {shape}, got {array.shape}.")
    if array.dtype == np.bool_:
        return np.ascontiguousarray(array)
    if not np.logical_or(array == 0, array == 1).all():
        raise WamAdapterError(f"{label} must be binary.")
    return np.ascontiguousarray(array.astype(np.bool_))


def _mask_sha256(mask: np.ndarray) -> str:
    header = json.dumps(list(mask.shape), separators=(",", ":")).encode("ascii")
    return hashlib.sha256(header + b"\0" + mask.astype(np.uint8).tobytes()).hexdigest()


def _message_string(bits: np.ndarray) -> str:
    return "".join("1" if bool(bit) else "0" for bit in bits)


def _resize_probability(probability: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    if probability.shape == shape:
        return probability.astype(np.float32, copy=False)
    pil = Image.fromarray(probability.astype(np.float32), mode="F")
    resized = pil.resize((width, height), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32)


def _quality_metrics(
    original: np.ndarray,
    watermarked: np.ndarray,
    ssim_evaluator: Callable[[np.ndarray, np.ndarray], float] | None,
    lpips_evaluator: Callable[[np.ndarray, np.ndarray], float] | None,
) -> dict[str, Any]:
    delta = original.astype(np.float64) - watermarked.astype(np.float64)
    mse = float(np.mean(delta * delta))
    psnr_db = None if mse == 0.0 else float(10.0 * math.log10((255.0**2) / mse))
    if ssim_evaluator is None:
        try:
            from skimage.metrics import structural_similarity
        except Exception as exc:  # quality output is part of the executable contract
            raise WamDependencyError(
                "scikit-image is required to compute the shared SSIM metric."
            ) from exc
        min_side = min(original.shape[0], original.shape[1])
        win_size = min(7, min_side if min_side % 2 == 1 else min_side - 1)
        if win_size < 3:
            raise WamAdapterError("Images must be at least 3 pixels per side for SSIM.")
        ssim = float(
            structural_similarity(
                original,
                watermarked,
                channel_axis=2,
                data_range=255,
                win_size=win_size,
            )
        )
        ssim_status = "computed_with_pinned_scikit_image"
    else:
        ssim = float(ssim_evaluator(original, watermarked))
        ssim_status = "computed_with_caller_supplied_shared_evaluator"
    if not math.isfinite(ssim):
        raise WamOutputContractError("SSIM evaluator returned a non-finite value.")
    lpips_value: float | None = None
    lpips_status = "not_computed_no_shared_evaluator"
    if lpips_evaluator is not None:
        lpips_value = float(lpips_evaluator(original, watermarked))
        if not math.isfinite(lpips_value):
            raise WamOutputContractError("LPIPS evaluator returned a non-finite value.")
        lpips_status = "computed_with_caller_supplied_shared_evaluator"
    return {
        "psnr_db": psnr_db,
        "identical_images": mse == 0.0,
        "ssim": ssim,
        "ssim_status": ssim_status,
        "lpips": lpips_value,
        "lpips_status": lpips_status,
    }


def _segmentation_metrics(
    prediction: np.ndarray, target: np.ndarray
) -> dict[str, float]:
    prediction = prediction.astype(np.bool_, copy=False)
    target = target.astype(np.bool_, copy=False)
    tp = int(np.logical_and(prediction, target).sum())
    fp = int(np.logical_and(prediction, ~target).sum())
    fn = int(np.logical_and(~prediction, target).sum())
    union = tp + fp + fn
    pred_count = tp + fp
    target_count = tp + fn
    iou = 1.0 if union == 0 else tp / union
    dice_denominator = 2 * tp + fp + fn
    dice = 1.0 if dice_denominator == 0 else (2 * tp) / dice_denominator
    precision = (
        1.0
        if pred_count == 0 and target_count == 0
        else (0.0 if pred_count == 0 else tp / pred_count)
    )
    recall = (
        1.0
        if target_count == 0 and pred_count == 0
        else (0.0 if target_count == 0 else tp / target_count)
    )
    return {
        "iou": float(iou),
        "dice": float(dice),
        "precision": float(precision),
        "recall": float(recall),
    }


class WamOfficialAdapter:
    """Evaluate an injected WAM backend without changing native semantics."""

    # The official detector emits logits.  A zero logit is the only audited
    # pixel/bit boundary (sigmoid probability 0.5).  WAM does not publish an
    # image-level threshold, so this adapter never fabricates one.
    watermark_pixel_probability_threshold: float = 0.5
    message_logit_threshold: float = 0.0

    def __init__(
        self,
        backend: WamBackend,
        *,
        ssim_evaluator: Callable[[np.ndarray, np.ndarray], float] | None = None,
        lpips_evaluator: Callable[[np.ndarray, np.ndarray], float] | None = None,
    ) -> None:
        self.backend = backend
        self.ssim_evaluator = ssim_evaluator
        self.lpips_evaluator = lpips_evaluator

    def embed(
        self,
        image_rgb: np.ndarray,
        message_bits: np.ndarray | str,
        *,
        embedding_mask: np.ndarray | None = None,
    ) -> WamEmbedResult:
        """Embed one native 32-bit message.

        If no mask is supplied, an explicit all-ones mask is used.  This makes
        full-image embedding unambiguous and mirrors the official notebook's
        ``mask_percentage >= 0.999`` behavior.
        """

        image = _validate_image(image_rgb, "image_rgb")
        bits = _validate_message(message_bits)
        height, width = image.shape[:2]
        if embedding_mask is None:
            mask = np.ones((height, width), dtype=np.bool_)
            mask_mode = "full_image_all_ones"
        else:
            mask = _validate_mask(embedding_mask, (height, width), "embedding_mask")
            mask_mode = "caller_supplied_binary_mask"
        if not mask.any():
            raise WamAdapterError(
                "Embedding mask is empty; no watermark would be applied."
            )

        started = time.perf_counter()
        candidate = _validate_image(
            self.backend.embed(image, bits.astype(np.uint8)), "backend embed output"
        )
        embed_latency_ms = (time.perf_counter() - started) * 1000.0
        if candidate.shape != image.shape:
            raise WamOutputContractError(
                f"Backend changed image shape from {image.shape} to {candidate.shape}."
            )
        composed = np.where(mask[..., None], candidate, image).astype(np.uint8)
        quality = _quality_metrics(
            image, composed, self.ssim_evaluator, self.lpips_evaluator
        )
        record = {
            "schema_version": "cogniguard.wam.embed.v1",
            "method_id": OFFICIAL_WAM_MIT.method_id,
            "semantic_scope": NATIVE_SEMANTICS["semantic_scope"],
            "native_message": {
                "bit_length": 32,
                "embedded_bits": _message_string(bits),
            },
            "embedding": {
                "mask_mode": mask_mode,
                "mask_area_fraction": float(mask.mean()),
                "mask_sha256": _mask_sha256(mask),
            },
            "common_metrics": {
                **quality,
                "embed_latency_ms": float(embed_latency_ms),
            },
            "registry_mapping": "none",
            "cogniguard_64bit_hmac_capsule_equivalent": False,
            "runtime_provenance": self.backend.runtime_provenance(),
        }
        return WamEmbedResult(
            watermarked_image=np.ascontiguousarray(composed),
            embedding_mask=mask,
            record=record,
        )

    def verify(
        self,
        attacked_image_rgb: np.ndarray,
        expected_message_bits: np.ndarray | str,
        *,
        embedding_support_mask: np.ndarray | None = None,
        attack_gt_tamper_mask: np.ndarray | None = None,
        attack_id: str | None = None,
    ) -> WamVerifyResult:
        """Detect WAM, recover its native message, and optionally score localization.

        Localization is emitted only when the caller supplies an aligned spatial
        attack ground-truth mask.  Its record is intentionally marked for a
        separate, same-GT table.
        """

        image = _validate_image(attacked_image_rgb, "attacked_image_rgb")
        expected = _validate_message(expected_message_bits)
        shape = image.shape[:2]
        support = (
            np.ones(shape, dtype=np.bool_)
            if embedding_support_mask is None
            else _validate_mask(embedding_support_mask, shape, "embedding_support_mask")
        )
        started = time.perf_counter()
        detection = self.backend.detect(image)

        probability = np.asarray(detection.watermark_probability, dtype=np.float32)
        logits = np.asarray(detection.message_logits, dtype=np.float32)
        if probability.ndim != 2:
            raise WamOutputContractError(
                f"Detection channel must be HxW, got {probability.shape}."
            )
        if logits.ndim != 3 or logits.shape[0] != 32:
            raise WamOutputContractError(
                f"Message logits must be 32xHxW, got {logits.shape}."
            )
        if logits.shape[1:] != probability.shape:
            raise WamOutputContractError(
                "Detection and message-logit spatial shapes do not match."
            )
        if not np.isfinite(probability).all() or not np.isfinite(logits).all():
            raise WamOutputContractError("Detector returned non-finite values.")
        if (probability < 0.0).any() or (probability > 1.0).any():
            raise WamOutputContractError(
                "Detection channel must be sigmoid probabilities in [0, 1]."
            )

        detector_mask = probability > self.watermark_pixel_probability_threshold
        detected_pixels = int(detector_mask.sum())
        decoded: np.ndarray | None = None
        bit_accuracy: float | None = None
        raw_exact = False
        decode_status = "no_watermarked_pixels_detected"
        if detected_pixels:
            pooled_logits = logits[:, detector_mask].mean(axis=1)
            decoded = pooled_logits > self.message_logit_threshold
            bit_accuracy = float((decoded == expected).mean())
            raw_exact = bool(np.array_equal(decoded, expected))
            decode_status = "decoded_from_predicted_watermark_pixels"

        score_summary = {
            "mean_probability": float(probability.mean()),
            "max_probability": float(probability.max()),
            "p50_probability": float(np.quantile(probability, 0.50)),
            "p95_probability": float(np.quantile(probability, 0.95)),
        }
        # End-to-end native decode timing includes model inference, pixel-mask
        # construction, score aggregation, message pooling, and bit decisions.
        detect_latency_ms = (time.perf_counter() - started) * 1000.0

        resized_probability = np.clip(_resize_probability(probability, shape), 0.0, 1.0)
        watermark_mask = (
            resized_probability > self.watermark_pixel_probability_threshold
        )

        localization: dict[str, Any] | None = None
        predicted_tamper: np.ndarray | None = None
        if attack_gt_tamper_mask is not None:
            gt_tamper = _validate_mask(
                attack_gt_tamper_mask, shape, "attack_gt_tamper_mask"
            )
            predicted_tamper = np.logical_and(support, ~watermark_mask)
            expected_watermark = np.logical_and(support, ~gt_tamper)
            localization = {
                "table_scope": "separate_same_attack_gt_only",
                "attack_id": attack_id,
                "attack_gt_tamper_mask_sha256": _mask_sha256(gt_tamper),
                "embedding_support_mask_sha256": _mask_sha256(support),
                "native_watermark_presence": _segmentation_metrics(
                    watermark_mask, expected_watermark
                ),
                "derived_tamper_from_watermark_absence_within_support": (
                    _segmentation_metrics(predicted_tamper, gt_tamper)
                ),
            }

        record = {
            "schema_version": "cogniguard.wam.verify.v1",
            "method_id": OFFICIAL_WAM_MIT.method_id,
            "semantic_scope": NATIVE_SEMANTICS["semantic_scope"],
            "native_32bit_message_recovery": {
                "bit_length": 32,
                "expected_bits": _message_string(expected),
                "recovered_bits": None if decoded is None else _message_string(decoded),
                "raw_bit_accuracy": bit_accuracy,
                "raw_exact": raw_exact,
                "decode_status": decode_status,
                "error_correction": "none",
            },
            "native_watermark_detection": {
                "pixel_logit_threshold": 0.0,
                "pixel_probability_threshold": (
                    self.watermark_pixel_probability_threshold
                ),
                "pixel_threshold_origin": "official_logit_greater_than_zero",
                "image_level_watermark_present": None,
                "image_level_decision_status": (
                    "not_computed_no_pinned_official_image_level_threshold"
                ),
                "detector_pixel_count": int(probability.size),
                "detected_pixel_count": detected_pixels,
                "detected_area_fraction": float(detector_mask.mean()),
                "presence_score_summary": score_summary,
                "output_channels": {
                    "watermark_presence": 1,
                    "message_logits": 32,
                    "total": 33,
                },
            },
            "localization_same_attack_gt": localization,
            "common_metrics": {
                "detect_aggregate_and_decode_latency_ms": float(detect_latency_ms),
                # Compatibility alias with clarified scope above.
                "detect_and_decode_latency_ms": float(detect_latency_ms),
            },
            "registry_mapping": "none",
            "registry_lookup_performed": False,
            "cogniguard_64bit_hmac_capsule_equivalent": False,
            "runtime_provenance": self.backend.runtime_provenance(),
        }
        return WamVerifyResult(
            watermark_probability=np.ascontiguousarray(resized_probability),
            watermark_mask=np.ascontiguousarray(watermark_mask),
            predicted_tamper_mask=None
            if predicted_tamper is None
            else np.ascontiguousarray(predicted_tamper),
            record=record,
        )


class OfficialWamBackend:
    """Concrete backend using only the pinned official repository and weights."""

    def __init__(
        self,
        repo_root: str | Path,
        checkpoint_path: str | Path,
        *,
        device: str = "cuda",
    ) -> None:
        self.repo_root = Path(repo_root).expanduser().resolve()
        self.checkpoint_path = Path(checkpoint_path).expanduser().resolve()
        self.device_name = device
        try:
            self._requested_cuda_index = _device_index(device)
        except WamPreflightError as exc:
            raise WamDependencyError(str(exc)) from exc
        self._preflight = run_preflight(
            self.repo_root,
            self.checkpoint_path,
            device=device,
            check_dependencies=True,
        )
        require_ready(self._preflight)
        self._load_pinned_model()

    def _load_pinned_model(self) -> None:
        repo_string = str(self.repo_root)
        for module_name, loaded in tuple(sys.modules.items()):
            if module_name != "watermark_anything" and not module_name.startswith(
                "watermark_anything."
            ):
                continue
            module_file_value = getattr(loaded, "__file__", None)
            if module_file_value:
                module_file = Path(module_file_value).resolve()
                try:
                    module_file.relative_to(self.repo_root)
                except ValueError as exc:
                    raise WamDependencyError(
                        f"A different {module_name} module is already imported. "
                        "Use a clean, independent WAM environment."
                    ) from exc
            elif module_name == "watermark_anything":
                namespace_paths = {
                    Path(value).resolve() for value in getattr(loaded, "__path__", ())
                }
                expected_namespace = (self.repo_root / "watermark_anything").resolve()
                if namespace_paths != {expected_namespace}:
                    raise WamDependencyError(
                        "The watermark_anything namespace includes a path outside "
                        "the pinned repository."
                    )
            else:
                raise WamDependencyError(
                    f"Imported module {module_name} has no auditable __file__."
                )

        # The audited checkout must win import resolution even when a similarly
        # named wheel/site-package exists later on sys.path.
        sys.path[:] = [
            entry
            for entry in sys.path
            if not entry or Path(entry).expanduser().resolve() != self.repo_root
        ]
        sys.path.insert(0, repo_string)
        if Path(sys.path[0]).resolve() != self.repo_root:
            raise WamDependencyError("Pinned WAM repository is not sys.path[0].")

        def require_repo_module(name: str, relative: str) -> Any:
            module = importlib.import_module(name)
            actual = Path(getattr(module, "__file__", "")).resolve()
            expected = (self.repo_root / relative).resolve()
            if actual != expected:
                raise WamDependencyError(
                    f"Module {name} resolved to {actual}, expected {expected}."
                )
            return module

        try:
            import omegaconf
            import torch

            root_module = importlib.import_module("watermark_anything")
            root_paths = {
                Path(value).resolve() for value in getattr(root_module, "__path__", ())
            }
            expected_root = (self.repo_root / "watermark_anything").resolve()
            if root_paths != {expected_root}:
                raise WamDependencyError(
                    "watermark_anything namespace did not resolve exclusively to "
                    "the pinned repository."
                )
            augmenter_module = require_repo_module(
                "watermark_anything.augmentation.augmenter",
                "watermark_anything/augmentation/augmenter.py",
            )
            transforms_module = require_repo_module(
                "watermark_anything.data.transforms",
                "watermark_anything/data/transforms.py",
            )
            models_module = require_repo_module(
                "watermark_anything.models", "watermark_anything/models/__init__.py"
            )
            require_repo_module(
                "watermark_anything.models.wam", "watermark_anything/models/wam.py"
            )
            jnd_module = require_repo_module(
                "watermark_anything.modules.jnd", "watermark_anything/modules/jnd.py"
            )
            Augmenter = augmenter_module.Augmenter
            default_transform = transforms_module.default_transform
            normalize_img = transforms_module.normalize_img
            unnormalize_img = transforms_module.unnormalize_img
            Wam = models_module.Wam
            build_embedder = models_module.build_embedder
            build_extractor = models_module.build_extractor
            JND = jnd_module.JND
        except Exception as exc:
            if isinstance(exc, WamDependencyError):
                raise
            raise WamDependencyError(
                "Pinned official WAM modules could not be imported."
            ) from exc

        if self.device_name.startswith("cuda"):
            index = int(self._requested_cuda_index or 0)
            if not torch.cuda.is_available() or index >= torch.cuda.device_count():
                raise WamDependencyError(
                    f"Requested CUDA device cuda:{index} is unavailable."
                )
            resolved_device = f"cuda:{index}"
        else:
            resolved_device = "cpu"

        params_path = self.repo_root / OFFICIAL_WAM_MIT.params_relative_path
        params = json.loads(params_path.read_text(encoding="utf-8"))
        embedder_cfg = omegaconf.OmegaConf.load(
            self.repo_root / params["embedder_config"]
        )
        extractor_cfg = omegaconf.OmegaConf.load(
            self.repo_root / params["extractor_config"]
        )
        augmenter_cfg = omegaconf.OmegaConf.load(
            self.repo_root / params["augmentation_config"]
        )
        attenuation_cfg = omegaconf.OmegaConf.load(
            self.repo_root / params["attenuation_config"]
        )
        embedder = build_embedder(
            params["embedder_model"],
            embedder_cfg[params["embedder_model"]],
            OFFICIAL_WAM_MIT.message_bits,
        )
        extractor = build_extractor(
            extractor_cfg.model,
            extractor_cfg[params["extractor_model"]],
            params["img_size"],
            OFFICIAL_WAM_MIT.message_bits,
        )
        augmenter = Augmenter(**augmenter_cfg)
        attenuation = JND(
            **attenuation_cfg[params["attenuation"]],
            preprocess=unnormalize_img,
            postprocess=normalize_img,
        )
        model = Wam(
            embedder,
            extractor,
            augmenter,
            attenuation,
            scaling_w=OFFICIAL_WAM_MIT.scaling_w,
            scaling_i=OFFICIAL_WAM_MIT.scaling_i,
            roll_probability=0.0,
            img_size_extractor=OFFICIAL_WAM_MIT.detector_size,
        )
        try:
            state_dict = torch.load(
                self.checkpoint_path, map_location="cpu", weights_only=True
            )
            model.load_state_dict(state_dict, strict=True)
        except Exception as exc:
            raise WamDependencyError(
                "Pinned checkpoint failed safe weights-only deserialization or strict load."
            ) from exc
        self._torch = torch
        self._default_transform = default_transform
        self._unnormalize_img = unnormalize_img
        self._device = torch.device(resolved_device)
        self._model = model.to(self._device).eval()
        parameter_device = next(self._model.parameters()).device
        if parameter_device.type != self._device.type or (
            self._device.type == "cuda"
            and int(parameter_device.index or 0) != int(self._device.index or 0)
        ):
            raise WamDependencyError(
                f"Loaded model device {parameter_device} does not match {self._device}."
            )
        if float(self._model.scaling_w) != OFFICIAL_WAM_MIT.scaling_w:
            raise WamOutputContractError("Loaded model scaling_w changed unexpectedly.")

    def embed(self, image_rgb: np.ndarray, message_bits: np.ndarray) -> np.ndarray:
        image = _validate_image(image_rgb, "image_rgb")
        bits = _validate_message(message_bits)
        pil = Image.fromarray(image, mode="RGB")
        tensor = self._default_transform(pil).unsqueeze(0).to(self._device)
        message = self._torch.from_numpy(bits.astype(np.float32)).unsqueeze(0)
        message = message.to(self._device)
        with self._torch.inference_mode():
            output = self._model.embed(tensor, message)["imgs_w"]
            rgb = self._unnormalize_img(output).clamp(0.0, 1.0)[0]
        array = rgb.permute(1, 2, 0).mul(255.0).round().byte().cpu().numpy()
        return np.ascontiguousarray(array)

    def detect(self, image_rgb: np.ndarray) -> WamDetectionOutput:
        image = _validate_image(image_rgb, "image_rgb")
        pil = Image.fromarray(image, mode="RGB")
        tensor = self._default_transform(pil).unsqueeze(0).to(self._device)
        with self._torch.inference_mode():
            preds = self._model.detect(tensor)["preds"]
            if tuple(preds.shape[:2]) != (1, OFFICIAL_WAM_MIT.detector_channels):
                raise WamOutputContractError(
                    f"Official detector returned shape {tuple(preds.shape)}, expected 1x33xHxW."
                )
            probability = self._torch.sigmoid(preds[0, 0]).float().cpu().numpy()
            logits = preds[0, 1:].float().cpu().numpy()
        return WamDetectionOutput(
            watermark_probability=np.ascontiguousarray(probability),
            message_logits=np.ascontiguousarray(logits),
        )

    def runtime_provenance(self) -> dict[str, Any]:
        return {
            **pinned_provenance(),
            "verified_artifacts": dict(self._preflight["artifacts"]),
            "runtime": dict(self._preflight["runtime"]),
            "weights_deserialization": "torch.load(weights_only=True), strict state_dict",
            "scaling_w_runtime": OFFICIAL_WAM_MIT.scaling_w,
            "adapter_backend_injected": False,
            "real_official_runtime": True,
            "official_repo_sys_path_index": 0,
            "runtime_device": str(self._device),
        }
