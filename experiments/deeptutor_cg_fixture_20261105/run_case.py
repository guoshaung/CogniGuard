"""Synthetic-only SDK smoke; the remote model is a loopback deterministic fixture."""
import json
import os
import subprocess
from pathlib import Path

from cogniguard.integrations.education import (
    AccessScope,
    ProfileConsentPolicy,
    ProfileRecord,
    ProtectionPipeline,
    StudentProfile,
    TeacherResource,
    run_protected_education,
)
from core.paths import PROJECT_ROOT


def main():
    root = Path(__file__).resolve().parent
    python = PROJECT_ROOT / "var/tmp/deeptutor-venv/Scripts/python.exe"
    sent = []
    event_types = []

    def generator(teaching):
        safe_view = teaching.to_dict()
        sent.append(safe_view)
        env = os.environ.copy()
        env["DEEPTUTOR_HOME"] = str(PROJECT_ROOT / "var/tmp/deeptutor-home")
        result = subprocess.run(
            [str(python), str(root / "deeptutor_worker.py")],
            input=json.dumps(safe_view, ensure_ascii=True), text=True,
            encoding="utf-8", capture_output=True, timeout=60, check=True, env=env,
        )
        data = json.loads(result.stdout.strip().splitlines()[-1])
        event_types.extend(data["event_types"])
        return data["answer"]

    profile = StudentProfile("synthetic-student", {"address": "SECRET_ADDRESS_927"}, [
        ProfileRecord("mastery", "mastery", "一元一次方程", 0.4, 1, 0.1),
        ProfileRecord("preference", "preference", "一元一次方程", "SECRET_PREFERENCE_927", 1, 0.1),
    ])
    resource = TeacherResource.from_dict({
        "resource_id":"synthetic-resource", "chunk_id":"synthetic-chunk",
        "content":"一元一次方程通过移项和系数化为一求解。",
        "knowledge":"一元一次方程", "difficulty":"basic", "resource_type":"question_bank",
        "copyright_level":0.5, "policy":{"allow_quote":False,"allow_summary":True},
    })
    pipeline = ProtectionPipeline({"fopd":{"use_enhanced_fopd":False}}, [resource], generator=generator)
    policy = ProfileConsentPolicy("fixture-v1", "teaching-agent", "learning", {"mastery":"automatic","preference":"ask"})
    result = run_protected_education(
        pipeline, profile,
        {"student_id":"synthetic-student","question":"请讲解 2x+3=7。", "expected_knowledge":"一元一次方程", "need_resource":True},
        access=AccessScope("synthetic-student"), consent_policy=policy,
    )
    assert len(sent) == 1
    assert "SECRET_ADDRESS_927" not in json.dumps(sent, ensure_ascii=False)
    assert "SECRET_PREFERENCE_927" not in json.dumps(sent, ensure_ascii=False)
    unsafe = os.getenv("CG_FIXTURE_UNSAFE") == "1"
    if unsafe:
        assert "SECRET_PREFERENCE_927" not in result["answer"]
        assert not result["output_validation"]["allowed"]
    else:
        assert "x=2" in result["answer"]
        assert result["output_validation"]["allowed"]
    assert result["profile_consent_requests"][0]["field"] == "preference"
    print(json.dumps({"answer":result["answer"], "delivery_allowed":result["output_validation"]["allowed"],
                      "pending_field":result["profile_consent_requests"][0]["field"],
                      "minimized_context":True,"sdk_event_types":event_types,
                      "model":"deterministic loopback fixture; no real model"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
