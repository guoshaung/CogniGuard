"""Shared request/response schemas for the SCE-LocGuard service layer."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    """Path-based request for registering or embedding a host image."""

    image_path: str = Field(..., description="Path to the host image.")
    owner_id: str = Field(..., description="Owner or copyright identifier.")
    semantic_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Compact semantic metadata to be encoded into the 64-bit capsule.",
    )
    output_dir: Optional[str] = Field(default=None, description="Directory for API job artifacts.")
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Explicit inference seed. Paper experiments must provide it.",
    )
    strict: bool = Field(default=True, description="Return explicit failure instead of fallback behavior.")


class EmbedResponse(BaseModel):
    """Response returned by the embed/register endpoint."""

    status: str
    job_id: Optional[str] = None
    implementation_level: Literal["real_pipeline", "one_image_batch_wrapper", "skeleton"] = "skeleton"
    watermarked_image_path: Optional[str] = None
    payload_id: Optional[str] = None
    copyright_id: Optional[int] = None
    capsule_bits: Optional[str] = None
    auth_hash: Optional[str] = None
    payload_seed: Optional[int] = None
    source_registry_registered: bool = False
    auth_level: str = "not_registered"
    capsule_schema: str = "hmac_source_capsule_v1"
    seed: Optional[int] = None
    psnr: Optional[float] = None
    message: str


class AIGCAttackRequest(BaseModel):
    """Request for a local AIGC editing attack."""

    image_path: str = Field(..., description="Path to a watermarked image.")
    attack_type: Literal["object_removal", "inpainting", "local_replacement", "local_style_edit"]
    mask_path: Optional[str] = Field(default=None, description="Optional local edit mask.")
    prompt: Optional[str] = Field(default=None, description="Optional inpainting prompt.")
    output_dir: Optional[str] = Field(default=None, description="Directory for API job artifacts.")
    mode: Literal["unconstrained", "localized_composite"] = "localized_composite"
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Explicit diffusion seed. Paper experiments must provide it.",
    )
    strict: bool = Field(default=True, description="Return explicit failure if the model/cache is unavailable.")


class AIGCAttackResponse(BaseModel):
    """Response returned by the AIGC attack endpoint."""

    status: str
    job_id: Optional[str] = None
    implementation_level: Literal["real_pipeline", "one_image_batch_wrapper", "skeleton"] = "skeleton"
    attack_type: Optional[str] = None
    mode: Optional[str] = None
    source_image_path: Optional[str] = None
    attacked_image_path: Optional[str] = None
    diffusion_output_path: Optional[str] = None
    mask_path: Optional[str] = None
    outside_mask_preserved: Optional[bool] = None
    seed: Optional[int] = None
    message: str


class VerifyRequest(BaseModel):
    """Path-based blind verification request."""

    image_path: str = Field(..., description="Path to the possibly tampered image.")
    output_dir: Optional[str] = Field(default=None, description="Directory for API job artifacts.")
    strict: bool = Field(default=True, description="Return explicit failure instead of fallback behavior.")
    return_overlay: bool = Field(default=True, description="Save a mask overlay visualization when possible.")
    return_recovered_bits: bool = Field(
        default=False,
        description="Return recovered bits for controlled evaluation; disabled for normal clients.",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Explicit inference seed recorded for reproducibility.",
    )


class ReportRegion(BaseModel):
    """One localized region in a verification report."""

    region_id: int
    bbox: List[int] = Field(
        default_factory=list,
        description="Bounding box as [x1, y1, x2, y2].",
    )
    area_ratio: float = 0.0
    change_type: str = "unknown"
    severity: str = "unknown"
    auth_status: str = "not_evaluated"
    confidence: float = 0.0


class VerifyResponse(BaseModel):
    """Response returned by the blind verification endpoint."""

    status: str
    job_id: Optional[str] = None
    implementation_level: Literal["real_pipeline", "one_image_batch_wrapper", "skeleton"] = "skeleton"
    auth_status: str = "not_evaluated"
    integrity_check_passed: bool = False
    raw_integrity_check_passed: bool = False
    corrected_integrity_check_passed: bool = False
    source_registry_match: bool = False
    exact_registry_match: bool = False
    registry_record_found: bool = False
    correction_applied: bool = False
    registry_hamming_distance: Optional[int] = None
    correction_radius: int = 1
    correction_candidate_count: int = 0
    correction_ambiguous: bool = False
    registered_owner_id: Optional[str] = None
    registered_payload_id: Optional[str] = None
    payload_recovered: bool = False
    capsule_recovered: bool = False
    bit_accuracy: Optional[float] = None
    recovered_capsule_bits: Optional[str] = None
    predicted_mask_path: Optional[str] = None
    overlay_path: Optional[str] = None
    report_json_path: Optional[str] = None
    attack_regime: str = "unknown"
    predicted_mask_area_ratio: Optional[float] = None
    recovery_threshold: Optional[float] = None
    tamper_area_threshold: Optional[float] = None
    localization_postprocessing: str = "none"
    localization_mask_rule_version: str = "editguard_residual_channel_vote_v2"
    localization_residual_channels: int = Field(default=3, ge=3, le=3)
    localization_channel_aggregation: Literal["k_of_3"] = "k_of_3"
    localization_channel_vote_min: int = Field(default=1, ge=1, le=3)
    localization_residual_threshold_rule: str = "abs_gt_recovery_threshold_per_channel"
    localization_component_connectivity: Optional[int] = Field(
        default=None, ge=8, le=8
    )
    localization_min_component_area_ratio: Optional[float] = Field(
        default=None, gt=0.0, lt=1.0
    )
    localization_component_area_rounding: Optional[str] = None
    raw_localization_votes_path: Optional[str] = None
    raw_localization_votes_sha256: Optional[str] = None
    raw_localization_votes_histogram: Dict[str, int] = Field(default_factory=dict)
    raw_localization_votes_dtype: Optional[str] = None
    raw_localization_votes_shape: List[int] = Field(default_factory=list)
    raw_localization_votes_encoding: Optional[str] = None
    capsule_schema: str = "hmac_source_capsule_v1"
    seed: Optional[int] = None
    reports: List[ReportRegion] = Field(default_factory=list)
    message: str


class CapabilityResponse(BaseModel):
    """Runtime capability probe for callers."""

    embed_real_pipeline_available: bool
    attack_real_pipeline_available: bool
    verify_real_pipeline_available: bool
    supports_64bit_capsule: bool = True
    supports_vlm: bool = False
    supports_single_image: bool
    source_registry_enabled: bool = True
    registry_secret_configured: bool = False
    paper_mode_ready: bool = False
    deterministic_mode_enabled: bool = False
    service_singleton: bool = False
    registry_backend: str = "json_single_process"
    capsule_schema: str = "hmac_source_capsule_v1"
    source_auth_tag_bits: int = 32
    replay_resistant: bool = False
    registry_aided_decoding: bool = True
    registry_error_correction_enabled: bool = True
    registry_hamming_radius: int = 1
    registry_minimum_distance_required: int = 3
    registry_codebook_records: int = 0
    registry_codebook_min_distance: Optional[int] = None
    registry_codebook_valid: bool = True
    recovery_threshold: float = 0.28
    tamper_area_threshold: float = 0.001
    localization_postprocessing: str = "none"
    localization_mask_rule_version: str = "editguard_residual_channel_vote_v2"
    localization_residual_channels: int = Field(default=3, ge=3, le=3)
    localization_channel_aggregation: Literal["k_of_3"] = "k_of_3"
    localization_channel_vote_min: int = Field(default=1, ge=1, le=3)
    localization_residual_threshold_rule: str = "abs_gt_recovery_threshold_per_channel"
    localization_component_connectivity: Optional[int] = Field(
        default=None, ge=8, le=8
    )
    localization_min_component_area_ratio: Optional[float] = Field(
        default=None, gt=0.0, lt=1.0
    )
    localization_component_area_rounding: Optional[str] = None
    attack_model_id: str = "stable-diffusion-v1-5/stable-diffusion-inpainting"
    attack_model_revision: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
