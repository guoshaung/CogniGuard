"""In-memory education integration using synthetic data and an offline answer."""

import json

from cogniguard.integrations.education import (
    AccessScope,
    ProfileRecord,
    ProtectionPipeline,
    StudentProfile,
    TeacherResource,
)


def run_example() -> dict:
    profile = StudentProfile(
        "student-demo",
        local_only_fields={"address": "SYNTHETIC_PRIVATE_ADDRESS"},
        profile_records=[
            ProfileRecord("mastery-demo", "mastery", "一元一次方程", 0.4, 1.0, 0.1),
        ],
    )
    resources = [
        TeacherResource.from_dict(
            {
                "resource_id": "resource-demo",
                "chunk_id": "chunk-demo",
                "content": "一元一次方程通过移项和系数化为一求解。",
                "knowledge": "一元一次方程",
                "difficulty": "basic",
                "resource_type": "question_bank",
                "copyright_level": 0.5,
                "policy": {"allow_quote": False, "allow_summary": True},
            }
        )
    ]
    # One pipeline per authorized student/session keeps its budget state local.
    # Profile filtering and resource return policy are enabled; optional
    # lifecycle governance and watermark hooks are not configured in this example.
    pipeline = ProtectionPipeline(
        {"fopd": {"use_enhanced_fopd": False}},
        resources,
        guard=None,
        watermark=None,
        generator=None,
    )
    result = pipeline.run(
        profile,
        {
            "request_id": "request-demo",
            "student_id": profile.student_id,
            "question": "解方程 2x+3=7",
            "expected_knowledge": "一元一次方程",
            "need_resource": True,
        },
        # In an online application this scope must come from a verified session.
        access=AccessScope(profile.student_id),
    )
    # result.to_dict() contains internal diagnostics and must not be sent to a
    # model. TeachingInput is the minimized text view for a future trusted adapter;
    # its text remains untrusted input. This example invokes no model.
    return {
        "answer": result.answer,
        "selected_record_ids": [item.record.record_id for item in result.selected],
        "return_mode": result.controlled.mode if result.controlled else "none",
        "teaching_input": result.teaching_input.to_dict(),
        "lifecycle_governance_enabled": False,
        "watermark_enabled": False,
        "execution_mode": "offline_rule_based",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2))
