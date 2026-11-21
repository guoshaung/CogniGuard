"""Fail-closed tests for EditGuard RGB localization channel voting."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from protection.supporting.image_watermark.api.schemas import VerifyRequest
from protection.supporting.image_watermark.api.service import (
    LOCALIZATION_RESIDUAL_THRESHOLD_RULE,
    SCELocGuardService,
    aggregate_localization_channel_votes,
    validate_localization_channel_votes,
)


def dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class _FakeRecoveredMessage:
    def detach(self):
        return self

    def float(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return np.zeros((1, 64), dtype=np.float32)


class _FakeStage:
    @staticmethod
    def image_to_editguard_batch(image):
        return {"image": image}


class _FakeModel:
    def __init__(self, raw_votes):
        self.raw_votes = raw_votes
        self.fed_data = None

    def feed_data(self, data):
        self.fed_data = data

    def image_recovery(self, _threshold):
        return self.raw_votes, _FakeRecoveredMessage()


def _decoded_payload():
    return {
        "auth_status": "invalid",
        "integrity_check_passed": False,
        "raw_integrity_check_passed": False,
        "corrected_integrity_check_passed": False,
        "source_registry_match": False,
        "exact_registry_match": False,
        "registry_record_found": False,
        "correction_applied": False,
        "registry_hamming_distance": None,
        "correction_radius": 1,
        "correction_candidate_count": 0,
        "correction_ambiguous": False,
        "registered_owner_id": None,
        "registered_payload_id": None,
        "capsule_recovered": False,
    }


def _install_verify_fakes(service, raw_votes):
    model = _FakeModel(raw_votes)
    service._editguard_runtime_available = lambda: (True, [])
    service._load_research_modules = lambda: (_FakeStage, None, None)
    service._get_editguard_model = lambda _stage: model
    service._decode_source_payload = lambda _bits: {}
    service._bind_decoded_payload_to_registry = lambda _decoded: _decoded_payload()
    service._regions_from_mask = lambda *_args: []
    return model


class TestLocalizationChannelVotePureFunctions(unittest.TestCase):
    def test_one_two_and_three_of_three_masks_and_k1_historical_equivalence(self):
        raw = np.asarray([[0, 255, 510, 765]], dtype=np.uint64)

        np.testing.assert_array_equal(
            aggregate_localization_channel_votes(raw, 1),
            (raw > 0).astype(np.uint8),
        )
        np.testing.assert_array_equal(
            aggregate_localization_channel_votes(raw, 2),
            np.asarray([[0, 0, 1, 1]], dtype=np.uint8),
        )
        np.testing.assert_array_equal(
            aggregate_localization_channel_votes(raw, 3),
            np.asarray([[0, 0, 0, 1]], dtype=np.uint8),
        )

        validated = validate_localization_channel_votes(raw)
        self.assertEqual(validated.dtype, np.dtype("uint16"))
        self.assertEqual(int(validated[0, 3]), 765)

    def test_invalid_raw_vote_arrays_fail_closed(self):
        invalid_arrays = (
            np.zeros((2, 2, 1), dtype=np.uint16),
            np.zeros((0, 2), dtype=np.uint16),
            np.asarray([[0, np.nan]], dtype=np.float64),
            np.asarray([[0, np.inf]], dtype=np.float64),
            np.asarray([[0, 254]], dtype=np.uint16),
            np.asarray([[False, True]], dtype=np.bool_),
            np.asarray([[0 + 0j, 255 + 0j]], dtype=np.complex64),
            np.asarray([[0, "255"]], dtype=object),
        )
        for raw in invalid_arrays:
            with self.subTest(dtype=raw.dtype, shape=raw.shape):
                with self.assertRaises(ValueError):
                    validate_localization_channel_votes(raw)

    def test_invalid_min_votes_fail_closed(self):
        raw = np.zeros((1, 1), dtype=np.uint16)
        for value in (0, 4, -1, 1.0, True, "2", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    aggregate_localization_channel_votes(raw, value)

    def test_cc8_relative_area_filter_uses_ceil_and_diagonal_connectivity(self):
        raw = np.zeros((4, 5), dtype=np.uint16)
        raw[0, 0] = 255
        raw[1, 1] = 255
        raw[3, 4] = 255

        kept = aggregate_localization_channel_votes(
            raw,
            1,
            min_component_area_ratio=0.10,
        )
        expected = np.zeros_like(raw, dtype=np.uint8)
        expected[0, 0] = 1
        expected[1, 1] = 1
        np.testing.assert_array_equal(kept, expected)

        removed = aggregate_localization_channel_votes(
            raw,
            1,
            min_component_area_ratio=0.1000001,
        )
        np.testing.assert_array_equal(removed, np.zeros_like(raw, dtype=np.uint8))

    def test_invalid_component_area_ratios_fail_closed(self):
        raw = np.zeros((2, 2), dtype=np.uint16)
        for value in (-0.1, 1.0, True, "0.005", None, np.nan, np.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    aggregate_localization_channel_votes(
                        raw,
                        1,
                        min_component_area_ratio=value,
                    )


class TestLocalizationChannelVoteService(unittest.TestCase):
    def test_verify_applies_v3_cc8_area_filter_and_records_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN": "1",
                "SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO": "0.005",
            },
        ):
            root = Path(tmpdir)
            image_path = root / "suspect.png"
            Image.new("RGB", (512, 512), "white").save(image_path)
            raw = np.zeros((512, 512), dtype=np.uint16)
            raw.reshape(-1)[:1311] = 255
            raw[-1, -1] = 255
            service = SCELocGuardService(project_root=tmpdir)
            _install_verify_fakes(service, raw)

            payload = dump(
                service.verify(
                    VerifyRequest(
                        image_path=str(image_path),
                        output_dir=str(root / "jobs"),
                        return_overlay=False,
                        seed=23,
                    )
                )
            )

            self.assertEqual(payload["status"], "ok")
            self.assertEqual(
                payload["localization_mask_rule_version"],
                "editguard_residual_channel_vote_cc8_v3",
            )
            self.assertEqual(
                payload["localization_postprocessing"],
                "connected_component_min_area_ratio_v1",
            )
            self.assertEqual(payload["localization_component_connectivity"], 8)
            self.assertEqual(payload["localization_min_component_area_ratio"], 0.005)
            self.assertEqual(
                payload["localization_component_area_rounding"],
                "ceil_height_times_width",
            )
            predicted = np.asarray(Image.open(payload["predicted_mask_path"]))
            self.assertEqual(int(np.count_nonzero(predicted)), 1311)
            self.assertEqual(int(predicted[-1, -1]), 0)
            report = json.loads(
                Path(payload["report_json_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(report["resolved_raw_vote_threshold"], 255)
            self.assertEqual(report["resolved_min_component_pixels"], 1311)

    def test_constructor_environment_and_capabilities_record_frozen_rule(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {"SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN": "2"},
        ):
            service = SCELocGuardService(project_root=tmpdir)
            self.assertEqual(service.localization_channel_vote_min, 2)
            service._editguard_runtime_available = lambda: (False, [])
            service._attack_runtime_available = lambda: (False, [])
            caps = dump(service.capabilities())
            self.assertEqual(
                caps["localization_mask_rule_version"],
                "editguard_residual_channel_vote_v2",
            )
            self.assertEqual(caps["localization_residual_channels"], 3)
            self.assertEqual(caps["localization_channel_aggregation"], "k_of_3")
            self.assertEqual(caps["localization_channel_vote_min"], 2)
            self.assertEqual(
                caps["localization_residual_threshold_rule"],
                LOCALIZATION_RESIDUAL_THRESHOLD_RULE,
            )
            self.assertNotIn("localization_rule_version", caps)
            self.assertNotIn("localization_channel_vote_rule", caps)

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {"SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN": "3"},
        ):
            explicit = SCELocGuardService(
                project_root=tmpdir, localization_channel_vote_min=1
            )
            self.assertEqual(explicit.localization_channel_vote_min, 1)

        for value in ("0", "4", "1.0", "true", "-1"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmpdir, patch.dict(
                "os.environ",
                {"SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN": value},
            ):
                with self.assertRaises(ValueError):
                    SCELocGuardService(project_root=tmpdir)

        for value in (0, 4, 2.0, True):
            with self.subTest(explicit=value), tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(ValueError):
                    SCELocGuardService(
                        project_root=tmpdir,
                        localization_channel_vote_min=value,
                    )

    def test_verify_saves_uint16_raw_votes_and_uses_aggregated_mask_everywhere(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "suspect.png"
            Image.new("RGB", (512, 512), "white").save(image_path)
            raw = np.zeros((512, 512), dtype=np.uint64)
            raw[0, 0] = 255
            raw[0, 1] = 510
            raw[0, 2] = 765
            service = SCELocGuardService(
                project_root=tmpdir, localization_channel_vote_min=2
            )
            model = _install_verify_fakes(service, raw)

            response = service.verify(
                VerifyRequest(
                    image_path=str(image_path),
                    output_dir=str(root / "jobs"),
                    return_overlay=False,
                    seed=7,
                )
            )

            payload = dump(response)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(
                payload["localization_mask_rule_version"],
                "editguard_residual_channel_vote_v2",
            )
            self.assertEqual(payload["localization_residual_channels"], 3)
            self.assertEqual(payload["localization_channel_aggregation"], "k_of_3")
            self.assertEqual(payload["localization_channel_vote_min"], 2)
            self.assertEqual(
                payload["localization_residual_threshold_rule"],
                LOCALIZATION_RESIDUAL_THRESHOLD_RULE,
            )
            self.assertEqual(
                payload["predicted_mask_area_ratio"], 2.0 / float(512 * 512)
            )
            self.assertIsNotNone(model.fed_data)

            raw_path = Path(payload["raw_localization_votes_path"])
            with Image.open(raw_path) as raw_image:
                raw_loaded = np.asarray(raw_image).copy()
            np.testing.assert_array_equal(raw_loaded, raw.astype(np.uint16))
            self.assertNotEqual(raw_loaded.dtype, np.dtype("uint8"))
            self.assertGreaterEqual(raw_loaded.dtype.itemsize, 2)
            self.assertEqual(int(raw_loaded[0, 2]), 765)
            self.assertEqual(
                hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                payload["raw_localization_votes_sha256"],
            )
            self.assertEqual(
                payload["raw_localization_votes_histogram"],
                {"0": 512 * 512 - 3, "255": 1, "510": 1, "765": 1},
            )
            self.assertEqual(payload["raw_localization_votes_dtype"], "uint16")
            self.assertEqual(payload["raw_localization_votes_shape"], [512, 512])
            self.assertEqual(
                payload["raw_localization_votes_encoding"],
                "lossless_png_16bit_grayscale_I;16",
            )

            predicted = np.asarray(Image.open(payload["predicted_mask_path"]))
            np.testing.assert_array_equal(predicted[0, :4], [0, 255, 255, 0])

            report = json.loads(
                Path(payload["report_json_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                report["localization_mask_rule_version"],
                "editguard_residual_channel_vote_v2",
            )
            self.assertEqual(report["localization_residual_channels"], 3)
            self.assertEqual(report["localization_channel_aggregation"], "k_of_3")
            self.assertEqual(report["localization_channel_vote_min"], 2)
            self.assertEqual(
                report["localization_residual_threshold_rule"],
                LOCALIZATION_RESIDUAL_THRESHOLD_RULE,
            )
            self.assertEqual(report["resolved_raw_vote_threshold"], 510)
            self.assertNotIn("localization_channel_vote", report)
            artifact = report["raw_localization_votes_artifact"]
            self.assertEqual(artifact["dtype"], "uint16")
            self.assertEqual(artifact["shape"], [512, 512])
            self.assertEqual(
                artifact["encoding"], "lossless_png_16bit_grayscale_I;16"
            )
            self.assertEqual(artifact["sha256"], payload["raw_localization_votes_sha256"])
            self.assertEqual(artifact["histogram"], payload["raw_localization_votes_histogram"])

    def test_invalid_model_votes_do_not_create_mask_or_raw_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "suspect.png"
            Image.new("RGB", (512, 512), "white").save(image_path)
            invalid = np.zeros((512, 512), dtype=np.uint16)
            invalid[0, 0] = 254
            service = SCELocGuardService(
                project_root=tmpdir, localization_channel_vote_min=2
            )
            _install_verify_fakes(service, invalid)

            response = service.verify(
                VerifyRequest(
                    image_path=str(image_path),
                    output_dir=str(root / "jobs"),
                    return_overlay=False,
                )
            )

            payload = dump(response)
            self.assertEqual(payload["status"], "not_implemented")
            self.assertEqual(payload["localization_channel_vote_min"], 2)
            self.assertIn("may contain only", payload["message"])
            report_path = Path(payload["report_json_path"])
            self.assertTrue(report_path.exists())
            job_dir = report_path.parent
            self.assertFalse((job_dir / "predicted_mask.png").exists())
            self.assertFalse(list(job_dir.glob("raw_localization_channel_votes*")))

    def test_wrong_model_vote_shape_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "suspect.png"
            Image.new("RGB", (512, 512), "white").save(image_path)
            service = SCELocGuardService(
                project_root=tmpdir, localization_channel_vote_min=2
            )
            _install_verify_fakes(service, np.zeros((2, 2), dtype=np.uint16))

            response = service.verify(
                VerifyRequest(
                    image_path=str(image_path),
                    output_dir=str(root / "jobs"),
                    return_overlay=False,
                )
            )

            payload = dump(response)
            self.assertEqual(payload["status"], "not_implemented")
            self.assertIn("must match the recovered image shape", payload["message"])
            job_dir = Path(payload["report_json_path"]).parent
            self.assertFalse((job_dir / "predicted_mask.png").exists())
            self.assertFalse(list(job_dir.glob("raw_localization_channel_votes*")))


if __name__ == "__main__":
    unittest.main()
