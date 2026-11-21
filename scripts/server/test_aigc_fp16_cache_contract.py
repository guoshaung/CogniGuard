from __future__ import annotations

import argparse
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from protection.supporting.image_watermark.scripts import run_stage10a_real_aigc_attack_subset as attack_script
from scripts.server import preflight_image_watermark as preflight


MODEL_REVISION = "8a4288a76071f7280aedbdb3253bdb9e9d5d84bb"
OTHER_REVISION = "0" * 40


class _FakePipe:
    def __init__(self) -> None:
        self.to_calls: list[str] = []
        self.progress_calls: list[bool] = []

    def to(self, device: str):
        self.to_calls.append(device)
        return self

    def set_progress_bar_config(self, *, disable: bool) -> None:
        self.progress_calls.append(disable)


def _loader_args(tmpdir: str, *, device: str, dtype: str) -> argparse.Namespace:
    return argparse.Namespace(
        model_id=preflight.DEFAULT_MODEL_ID,
        model_revision=MODEL_REVISION,
        model_cache_dir=str(Path(tmpdir) / "hf"),
        device=device,
        dtype=dtype,
        allow_model_download=False,
    )


class TestDiffusersFp16LoaderContract(unittest.TestCase):
    def _fake_diffusers(self, from_pretrained):
        module = types.ModuleType("diffusers")

        class FakePipeline:
            pass

        FakePipeline.from_pretrained = from_pretrained
        module.StableDiffusionInpaintPipeline = FakePipeline
        return module

    def test_cuda_fp16_explicitly_selects_fp16_safetensors(self):
        calls: list[tuple[str, dict[str, object]]] = []
        fake_pipe = _FakePipe()

        def from_pretrained(model_id: str, **kwargs):
            calls.append((model_id, kwargs))
            return fake_pipe

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            attack_script, "require_diffusers_model"
        ), patch.object(attack_script.torch.cuda, "is_available", return_value=True), patch.dict(
            sys.modules, {"diffusers": self._fake_diffusers(from_pretrained)}
        ):
            result = attack_script.load_diffusers_pipe(
                _loader_args(tmpdir, device="cuda", dtype="fp16"), Path(tmpdir)
            )

        self.assertIs(result, fake_pipe)
        self.assertEqual(len(calls), 1)
        model_id, kwargs = calls[0]
        self.assertEqual(model_id, preflight.DEFAULT_MODEL_ID)
        self.assertEqual(kwargs["revision"], MODEL_REVISION)
        self.assertIs(kwargs["torch_dtype"], torch.float16)
        self.assertEqual(kwargs["variant"], "fp16")
        self.assertIs(kwargs["use_safetensors"], True)
        self.assertIs(kwargs["local_files_only"], True)
        self.assertEqual(fake_pipe.to_calls, ["cuda"])

    def test_cpu_path_does_not_force_fp16_variant(self):
        calls: list[dict[str, object]] = []
        fake_pipe = _FakePipe()

        def from_pretrained(_model_id: str, **kwargs):
            calls.append(kwargs)
            return fake_pipe

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            attack_script, "require_diffusers_model"
        ), patch.object(attack_script.torch.cuda, "is_available", return_value=True), patch.dict(
            sys.modules, {"diffusers": self._fake_diffusers(from_pretrained)}
        ):
            attack_script.load_diffusers_pipe(
                _loader_args(tmpdir, device="cpu", dtype="fp16"), Path(tmpdir)
            )

        self.assertIs(calls[0]["torch_dtype"], torch.float32)
        self.assertNotIn("variant", calls[0])
        self.assertNotIn("use_safetensors", calls[0])
        self.assertEqual(fake_pipe.to_calls, [])

    def test_cuda_fp32_path_remains_compatible_without_fp16_variant(self):
        calls: list[dict[str, object]] = []
        fake_pipe = _FakePipe()

        def from_pretrained(_model_id: str, **kwargs):
            calls.append(kwargs)
            return fake_pipe

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            attack_script, "require_diffusers_model"
        ), patch.object(attack_script.torch.cuda, "is_available", return_value=True), patch.dict(
            sys.modules, {"diffusers": self._fake_diffusers(from_pretrained)}
        ):
            attack_script.load_diffusers_pipe(
                _loader_args(tmpdir, device="cuda", dtype="fp32"), Path(tmpdir)
            )

        self.assertIs(calls[0]["torch_dtype"], torch.float32)
        self.assertNotIn("variant", calls[0])
        self.assertNotIn("use_safetensors", calls[0])
        self.assertEqual(fake_pipe.to_calls, ["cuda"])

    def test_cuda_fp16_loader_failure_is_not_retried_with_other_weights(self):
        call_count = 0

        def from_pretrained(_model_id: str, **_kwargs):
            nonlocal call_count
            call_count += 1
            raise TypeError("variant is unsupported")

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            attack_script, "require_diffusers_model"
        ), patch.object(attack_script.torch.cuda, "is_available", return_value=True), patch.dict(
            sys.modules, {"diffusers": self._fake_diffusers(from_pretrained)}
        ):
            with self.assertRaisesRegex(RuntimeError, "No fallback"):
                attack_script.load_diffusers_pipe(
                    _loader_args(tmpdir, device="cuda", dtype="fp16"), Path(tmpdir)
                )

        self.assertEqual(call_count, 1)


def _preflight_args(cache_root: Path, revision: str = MODEL_REVISION) -> argparse.Namespace:
    return argparse.Namespace(
        hf_cache=str(cache_root),
        model_id=preflight.DEFAULT_MODEL_ID,
        model_revision=revision,
        require_hf_cache=True,
    )


def _stage_complete_snapshot(cache_root: Path, revision: str = MODEL_REVISION) -> Path:
    snapshot = (
        cache_root
        / f"models--{preflight.DEFAULT_MODEL_ID.replace('/', '--')}"
        / "snapshots"
        / revision
    )
    for relative_path in preflight.INPAINTING_FP16_REQUIRED_FILES:
        path = snapshot / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-cache-entry")
    return snapshot


class TestPreflightFp16CacheContract(unittest.TestCase):
    def test_exact_revision_with_all_fourteen_files_passes(self):
        self.assertEqual(len(preflight.INPAINTING_FP16_REQUIRED_FILES), 14)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _stage_complete_snapshot(root)
            report = preflight.CheckReport()
            preflight.check_hf_cache(_preflight_args(root), root, report)

        row = report.checks[-1]
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["details"]["complete_snapshots"], [MODEL_REVISION])
        self.assertTrue(row["details"]["required_revision_available"])

    def test_missing_fp16_weight_rejects_directory_only_cache(self):
        missing_file = "unet/diffusion_pytorch_model.fp16.safetensors"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            snapshot = _stage_complete_snapshot(root)
            (snapshot / missing_file).unlink()
            report = preflight.CheckReport()
            preflight.check_hf_cache(_preflight_args(root), root, report)

        row = report.checks[-1]
        self.assertEqual(row["status"], "error")
        self.assertIn(missing_file, row["details"]["missing_files_by_snapshot"][MODEL_REVISION])
        self.assertFalse(row["details"]["required_revision_available"])

    def test_complete_different_revision_does_not_satisfy_requested_revision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _stage_complete_snapshot(root, MODEL_REVISION)
            report = preflight.CheckReport()
            preflight.check_hf_cache(_preflight_args(root, OTHER_REVISION), root, report)

        row = report.checks[-1]
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["details"]["complete_snapshots"], [MODEL_REVISION])
        self.assertFalse(row["details"]["required_revision_available"])

    def test_mutable_revision_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _stage_complete_snapshot(root, MODEL_REVISION)
            report = preflight.CheckReport()
            preflight.check_hf_cache(_preflight_args(root, "main"), root, report)

        row = report.checks[-1]
        self.assertEqual(row["status"], "error")
        self.assertFalse(row["details"]["required_revision_is_exact_commit"])


if __name__ == "__main__":
    unittest.main()
