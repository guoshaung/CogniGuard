"""FastAPI server for the SCE-LocGuard service wrapper."""

from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .schemas import (
    AIGCAttackRequest,
    AIGCAttackResponse,
    CapabilityResponse,
    EmbedRequest,
    EmbedResponse,
    VerifyRequest,
    VerifyResponse,
)
from .service import SCELocGuardService


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAX_INFLIGHT_REQUESTS = max(1, int(os.environ.get("SCE_LOCGUARD_MAX_INFLIGHT", "2")))
_INFERENCE_SLOTS = threading.BoundedSemaphore(MAX_INFLIGHT_REQUESTS)
# These values are intentionally captured once when the API process imports this
# module.  Formal runners use them as a public, per-process attestation so a
# readiness probe cannot silently talk to an older service already bound to the
# configured port.  The nonce is not a secret and must never be reused as one.
RUN_INSTANCE_NONCE = os.environ.get("SCE_LOCGUARD_RUN_INSTANCE_NONCE", "")
API_JOB_ROOT = str(
    Path(
        os.environ.get("SCE_LOCGUARD_API_JOB_ROOT")
        or (DEFAULT_PROJECT_ROOT / "var" / "outputs" / "sce_locguard_api_jobs")
    )
    .expanduser()
    .resolve()
)


def _project_root() -> str:
    return os.environ.get("SCE_LOCGUARD_PROJECT_ROOT") or str(DEFAULT_PROJECT_ROOT)


@lru_cache(maxsize=1)
def get_service() -> SCELocGuardService:
    return SCELocGuardService(project_root=_project_root())


app = FastAPI(
    title="SCE-LocGuard API",
    version="0.2.0",
    description=(
        "Lightweight wrapper around the SCE-LocGuard / EditGuard-style "
        "watermark forensic pipeline."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "sce-locguard",
        "algorithm_mode": "wrapper",
        "project_root_configured": bool(_project_root()),
        "single_image_pipeline": "mvp_runtime_detected_by_capabilities",
        "service_lifecycle": "process_singleton",
        "run_instance_nonce": RUN_INSTANCE_NONCE,
        "api_job_root": API_JOB_ROOT,
        "max_inflight_requests": MAX_INFLIGHT_REQUESTS,
        "constraints": {
            "no_training": True,
            "no_vlm": True,
            "robust_payload_bits": 64,
            "capsule_schema": "hmac_source_capsule_v1",
            "source_auth_tag_bits": 32,
            "verification_mode": "blind",
            "uvicorn_workers_required": 1,
        },
    }


@app.get("/api/v1/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    return get_service().capabilities()


@app.post("/api/v1/watermark/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    response = _run_inference(lambda: get_service().embed(request))
    if response.status == "error":
        raise HTTPException(status_code=400, detail={"status": response.status, "message": response.message})
    return response


@app.post("/api/v1/attack/aigc", response_model=AIGCAttackResponse)
def attack_aigc(request: AIGCAttackRequest) -> AIGCAttackResponse:
    response = _run_inference(lambda: get_service().attack_aigc(request))
    if response.status == "error":
        raise HTTPException(status_code=400, detail={"status": response.status, "message": response.message})
    return response


@app.post("/api/v1/watermark/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest) -> VerifyResponse:
    response = _run_inference(lambda: get_service().verify(request))
    if response.status == "error":
        raise HTTPException(status_code=400, detail={"status": response.status, "message": response.message})
    return response


@app.get("/api/v1/watermark/report/{job_id}")
def export_report(job_id: str) -> dict:
    response = get_service().export_report(job_id)
    if response.get("status") == "error":
        raise HTTPException(status_code=404, detail=response)
    return response


def _run_inference(call):
    if not _INFERENCE_SLOTS.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail={
                "status": "busy",
                "message": "The single-GPU inference queue is full; retry later.",
            },
        )
    try:
        return call()
    finally:
        _INFERENCE_SLOTS.release()
