"""Bindings to the existing business services; no HTTP routing lives here.

Import fallbacks preserve the dashboard's optional-model behavior.
"""

from core.paths import PROJECT_ROOT

__all__ = [
    "PROJECT_ROOT",
    "run_demo",
    "load_demo_case",
    "run_classroom_turn",
    "run_free_chat",
    "attack_image_watermark",
    "decode_data_url_or_base64",
    "detect_image_watermark",
    "image_file_response",
    "watermark_artifact_response",
    "build_cases_manifest",
    "list_attack_templates",
    "list_episode_samples",
    "get_runtime_status",
    "run_all_attacks",
    "build_agent_communications",
    "build_attack_results",
    "build_audit_traces",
    "build_c2rag_cases",
    "build_dashboard_metrics",
    "build_demo_workflow",
    "build_mm_fopd_cases",
]

# Import research visualization data projections
try:
    from cogniguard.api.dashboard_data import (
        build_agent_communications,
        build_attack_results,
        build_audit_traces,
        build_c2rag_cases,
        build_dashboard_metrics,
        build_demo_workflow,
        build_mm_fopd_cases,
    )
except ImportError:
    build_agent_communications = None
    build_attack_results = None
    build_audit_traces = None
    build_c2rag_cases = None
    build_dashboard_metrics = None
    build_demo_workflow = None
    build_mm_fopd_cases = None

# Import actual CogniGuard demo components
try:
    from cogniguard.applications.education.case_study import run_case_study as run_demo
    from cogniguard.applications.education.cases import load_demo_case
except ImportError:
    run_demo = None
    load_demo_case = None

try:
    from cogniguard.applications.education.classroom import run_classroom_turn
except ImportError:
    run_classroom_turn = None

try:
    from cogniguard.applications.education.conversation import run_conversation as run_free_chat
except ImportError:
    run_free_chat = None

try:
    from cogniguard.protection.image_watermarking import (
        attack_image_watermark,
        decode_data_url_or_base64,
        detect_image_watermark,
        image_file_response,
        watermark_artifact_response,
    )
except ImportError:
    attack_image_watermark = None
    decode_data_url_or_base64 = None
    detect_image_watermark = None
    image_file_response = None
    watermark_artifact_response = None

try:
    from cogniguard.scenario_loader import (
        build_cases_manifest,
        list_attack_templates,
        list_episode_samples,
    )
except ImportError:
    build_cases_manifest = None
    list_attack_templates = None
    list_episode_samples = None

try:
    from cogniguard.runtime.mode import get_runtime_status
except ImportError:
    get_runtime_status = None

# Import actual watermark attack component
try:
    from protection.audit_trace.src.attacks import run_all_attacks
except ImportError:
    run_all_attacks = None
