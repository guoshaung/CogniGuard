"""MVP integration tests for the SCE-LocGuard API wrapper.

These tests do not require checkpoints, CUDA, or Stable Diffusion cache. If the
real runtime is absent, they assert that the wrapper fails explicitly instead
of fabricating successful outputs.
"""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from protection.supporting.image_watermark.api.schemas import AIGCAttackRequest, EmbedRequest, VerifyRequest
from protection.supporting.image_watermark.api.server import app
from protection.supporting.image_watermark.api.service import SCELocGuardService


def dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class TestSCELocGuardApiMvp(unittest.TestCase):
    def test_export_report_resolves_historical_index_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ", {"SCE_LOCGUARD_API_JOB_ROOT": "", "SCE_LOCGUARD_REGISTRY_DIR": ""}
        ):
            root = Path(tmpdir)
            service = SCELocGuardService(project_root=tmpdir)
            job_id = "embed_legacy"
            report = service.default_job_root / job_id / "embed_report.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({"job_type": "embed", "job_id": job_id}), encoding="utf-8")
            service.job_index_dir.mkdir(parents=True)
            index_path = service.job_index_dir / f"{job_id}.json"
            for prefix in ("dfg_locguard/api_jobs", "outputs/sce_locguard_api_jobs"):
                with self.subTest(prefix=prefix):
                    index_path.write_text(
                        json.dumps({"report_json_path": str(root / prefix / job_id / report.name)}),
                        encoding="utf-8",
                    )
                    self.assertEqual(service.export_report(job_id)["job_type"], "embed")
            index_path.write_text("{}", encoding="utf-8")
            self.assertEqual(service.export_report(job_id)["status"], "error")

    def test_historical_environment_paths_resolve_in_project_root(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "SCE_LOCGUARD_API_JOB_ROOT": "dfg_locguard/api_jobs",
                "SCE_LOCGUARD_REGISTRY_DIR": "outputs/registry",
            },
        ):
            service = SCELocGuardService(project_root=tmpdir)
            self.assertEqual(service.default_job_root, Path(tmpdir).resolve() / "var/outputs/sce_locguard_api_jobs")
            self.assertEqual(service.payload_registry_dir, Path(tmpdir).resolve() / "var/outputs/registry")

    def test_health_and_capabilities_work(self):
        client = TestClient(app)
        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        caps = client.get("/api/v1/capabilities")
        self.assertEqual(caps.status_code, 200)
        payload = caps.json()
        self.assertIn("embed_real_pipeline_available", payload)
        self.assertFalse(payload["supports_vlm"])
        self.assertTrue(payload["supports_64bit_capsule"])
        self.assertTrue(payload["registry_aided_decoding"])
        self.assertTrue(payload["registry_error_correction_enabled"])
        self.assertEqual(payload["registry_hamming_radius"], 1)
        self.assertEqual(payload["registry_minimum_distance_required"], 3)

    def test_schema_serialization(self):
        embed = EmbedRequest(
            image_path="input.png",
            owner_id="owner",
            semantic_metadata={"risk": "medium"},
            output_dir=None,
        )
        attack = AIGCAttackRequest(
            image_path="watermarked.png",
            attack_type="inpainting",
            mode="localized_composite",
        )
        verify = VerifyRequest(image_path="attacked.png")
        self.assertEqual(dump(embed)["owner_id"], "owner")
        self.assertEqual(dump(attack)["attack_type"], "inpainting")
        self.assertTrue(dump(verify)["return_overlay"])

    def test_localization_thresholds_are_frozen_and_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "SCE_LOCGUARD_RECOVERY_THRESHOLD": "",
                "SCE_LOCGUARD_TAMPER_AREA_THRESHOLD": "",
                "SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN": "",
            },
        ):
            service = SCELocGuardService(project_root=tmpdir)
            self.assertAlmostEqual(service.recovery_threshold, 0.28)
            self.assertAlmostEqual(service.tamper_area_threshold, 0.001)
            self.assertEqual(service.localization_channel_vote_min, 1)
            self.assertEqual(service._attack_regime(0.001), "no_tamper_detected")
            self.assertEqual(service._attack_regime(0.0011), "localized_tamper_candidate")
            caps = dump(service.capabilities())
            self.assertAlmostEqual(caps["recovery_threshold"], 0.28)
            self.assertAlmostEqual(caps["tamper_area_threshold"], 0.001)
            self.assertEqual(caps["localization_postprocessing"], "none")
            self.assertEqual(
                caps["localization_mask_rule_version"],
                "editguard_residual_channel_vote_v2",
            )
            self.assertEqual(caps["localization_residual_channels"], 3)
            self.assertEqual(caps["localization_channel_aggregation"], "k_of_3")
            self.assertEqual(caps["localization_channel_vote_min"], 1)
            self.assertEqual(
                caps["localization_residual_threshold_rule"],
                "abs_gt_recovery_threshold_per_channel",
            )
            self.assertEqual(caps["registry_hamming_radius"], 1)
            self.assertEqual(caps["registry_minimum_distance_required"], 3)
            constraints = service._constraints()
            self.assertEqual(
                constraints["registry_aided_decoding"],
                "closed_set_unique_nearest_neighbor",
            )
            self.assertFalse(constraints["corrected_matches_are_exact"])

    def test_localization_threshold_environment_override_is_validated(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "SCE_LOCGUARD_RECOVERY_THRESHOLD": "0.31",
                "SCE_LOCGUARD_TAMPER_AREA_THRESHOLD": "0.002",
            },
        ):
            service = SCELocGuardService(project_root=tmpdir)
            self.assertAlmostEqual(service.recovery_threshold, 0.31)
            self.assertAlmostEqual(service.tamper_area_threshold, 0.002)

        for name, value in (
            ("SCE_LOCGUARD_RECOVERY_THRESHOLD", "nan"),
            ("SCE_LOCGUARD_RECOVERY_THRESHOLD", "0"),
            ("SCE_LOCGUARD_TAMPER_AREA_THRESHOLD", "1"),
            ("SCE_LOCGUARD_TAMPER_AREA_THRESHOLD", "not-a-number"),
        ):
            with self.subTest(name=name, value=value), tempfile.TemporaryDirectory() as tmpdir, patch.dict(
                "os.environ", {name: value}
            ):
                with self.assertRaises(ValueError):
                    SCELocGuardService(project_root=tmpdir)

    def test_editguard_model_is_loaded_once_per_service(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SCELocGuardService(project_root=tmpdir)

            class FakeStage:
                calls = 0

                @classmethod
                def load_editguard_model(cls, *_args):
                    cls.calls += 1
                    return object()

            first = service._get_editguard_model(FakeStage)
            second = service._get_editguard_model(FakeStage)

            self.assertIs(first, second)
            self.assertEqual(FakeStage.calls, 1)

    def test_invalid_image_path_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SCELocGuardService(project_root=tmpdir)
            response = service.embed(
                EmbedRequest(
                    image_path=str(Path(tmpdir) / "missing.png"),
                    owner_id="owner",
                    output_dir=str(Path(tmpdir) / "jobs"),
                )
            )
            self.assertEqual(response.status, "error")
            self.assertIn("not found", response.message.lower())

    def test_service_creates_job_dirs_without_fake_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            image_path = tmp / "input.png"
            Image.new("RGB", (32, 32), "white").save(image_path)
            service = SCELocGuardService(project_root=tmpdir)
            response = service.embed(
                EmbedRequest(
                    image_path=str(image_path),
                    owner_id="owner",
                    output_dir=str(tmp / "jobs"),
                )
            )
            self.assertIn(response.status, {"ok", "not_implemented"})
            self.assertTrue(response.job_id)
            report = service.export_report(response.job_id or "")
            self.assertEqual(report["job_type"], "embed")
            if response.status != "ok":
                self.assertEqual(response.implementation_level, "skeleton")
                self.assertFalse(response.watermarked_image_path)

    def test_attack_missing_model_returns_model_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            image_path = tmp / "watermarked.png"
            Image.new("RGB", (32, 32), "white").save(image_path)
            service = SCELocGuardService(project_root=tmpdir)
            response = service.attack_aigc(
                AIGCAttackRequest(
                    image_path=str(image_path),
                    attack_type="inpainting",
                    mode="localized_composite",
                    output_dir=str(tmp / "jobs"),
                )
            )
            self.assertIn(response.status, {"ok", "model_unavailable"})
            self.assertTrue(response.job_id)
            if response.status != "ok":
                self.assertEqual(response.implementation_level, "skeleton")
                self.assertFalse(response.attacked_image_path)

    def test_demo_fails_explicitly_if_runtime_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            image_path = tmp / "input.png"
            Image.new("RGB", (32, 32), "white").save(image_path)
            service = SCELocGuardService(project_root=tmpdir)
            summary = service.demo(
                image_path=str(image_path),
                owner_id="owner",
                attack_type="inpainting",
                mode="localized_composite",
                output_dir=str(tmp / "demo"),
            )
            self.assertIn(summary["status"], {"ok", "not_implemented"})
            if summary["status"] != "ok":
                self.assertIn(summary["failed_stage"], {"embed", "attack", "verify"})
                self.assertTrue((tmp / "demo" / "demo_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
