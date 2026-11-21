"""Local engineering runs of teacher combinations, not model-quality scores."""

from __future__ import annotations

import os
import random
from pathlib import Path

from core.access import AccessScope
from core.inputs import load_inputs

from ..experiments import ROOT, dependencies, sha256, write_new
from ..pipeline import LangGraphProtectionPipeline
from .catalog import PromptLibrary, TeamCatalog
from .dag import TeacherDAGGenerator, effective_prompt_hash, skill_fragment
from .skills import SkillLibrary
from .store import SQLiteTeacherAuditStore


def teacher_worker(job, output: Path, *, monitor=None):
    if os.environ.get("PYTHONHASHSEED") != str(job.seed):
        raise ValueError("Teacher worker requires a fixed interpreter hash seed")
    random.seed(job.seed)
    job.validate()
    source_library = PromptLibrary(job.teacher_prompts)
    source_skills = SkillLibrary(ROOT / "configs/teacher-skills.yaml")
    source_catalog = TeamCatalog(job.teacher_teams, source_library)
    if (job.expected_prompt_sha256 and source_library.sha256 != job.expected_prompt_sha256) or (
        job.expected_team_catalog_sha256
        and source_catalog.sha256 != job.expected_team_catalog_sha256
    ):
        raise ValueError("Teacher catalogs changed before worker execution")
    config, profiles, questions, resources = load_inputs(
        job.config, job.profiles, job.questions, job.resources
    )
    if not questions:
        raise ValueError("Teacher evaluation input is empty")
    output.mkdir(parents=True, exist_ok=False)
    audit_store = SQLiteTeacherAuditStore(output / "teacher_audit.sqlite3")
    audit_store.sync_catalogs(source_library, source_skills)
    library = audit_store.load_prompt_catalog(
        source_library.sha256, expected_count=len(source_library.inventory())
    )
    skills = audit_store.load_skill_catalog(
        source_skills.sha256, expected_count=len(source_skills.inventory())
    )
    catalog = TeamCatalog(job.teacher_teams, library)
    team = catalog.get(job.team)
    write_new(
        output / "manifest.json",
        {
            "status": "TEACHER_DAG_ENGINEERING_ONLY",
            "team": job.team,
            "team_hash": team.sha256,
            "trust_mode": job.trust_mode,
            "prompt_library_hash": library.sha256,
            "skill_library_hash": skills.sha256,
            "team_catalog_hash": catalog.sha256,
            "prompt_source": "sqlite_verified_snapshot",
            "prompt_versions": [
                {
                    "node": n.id,
                    "teacher": n.teacher,
                    "version": n.prompt,
                    "teacher_index": team.order().index(n.id),
                    "hash": effective_prompt_hash(
                        library.get(n.teacher, n.prompt), skill_fragment(skills, n.teacher)
                    ),
                    "backend_binding": n.backend,
                    "view_fields": list(n.view_fields),
                }
                for n in team.nodes
            ],
            "inputs": {
                k: sha256(getattr(job, k)) for k in ("config", "profiles", "questions", "resources")
            },
            "seed": job.seed,
            "dependencies": dependencies(),
            "teacher_backend": "offline_fixture",
            "handoff_guard_mode": "enforce",
            "blocked_input_recovery": "trusted_offline_fallback",
            "audit_database": "teacher_audit.sqlite3",
            "audit_database_content": "topology_decisions_and_counts_only",
            "budget_scope": "per_question",
            "checkpointing": False,
            "limitation": "No real-model calls; topology/control validation is not teaching quality or attack ASR.",
        },
    )
    rows, teaching_runs, pipeline_traces = [], [], []
    for question in questions:
        profile = profiles[question["student_id"]]
        generator = TeacherDAGGenerator(
            team,
            library,
            trust_mode=job.trust_mode,
            max_workers=job.workers,
            monitor=monitor,
            handoff_guard_mode="enforce",
            on_blocked="fallback",
            audit_store=audit_store,
            skills=skills,
        )
        pipeline = LangGraphProtectionPipeline(config, resources, generator=generator)
        result = pipeline.run(profile, question, access=AccessScope(profile.student_id))
        rows.append({"result": result.to_dict(), "teacher_metrics": generator.last_run["metrics"]})
        teaching_runs.append(generator.last_run)
        pipeline_traces.append(pipeline.last_trace)
    write_new(output / "rows.json", rows)
    write_new(output / "teacher-transcripts.json", teaching_runs)
    write_new(output / "node-traces.json", pipeline_traces)
    write_new(output / "dag.mermaid.json", {"mermaid": generator.graph.get_graph().draw_mermaid()})
    write_new(
        output / "summary.json",
        {
            "status": "TEACHER_DAG_ENGINEERING_ONLY",
            "team": job.team,
            "trust_mode": job.trust_mode,
            "question_count": len(rows),
            "teachers_per_question": len(team.nodes),
            "teacher_invocations": sum(x["teacher_metrics"]["teachers_executed"] for x in rows),
            "edges_accepted": sum(x["teacher_metrics"]["edges_accepted"] for x in rows),
            "edges_blocked": sum(x["teacher_metrics"]["edges_blocked"] for x in rows),
            "model_calls": 0,
            "teacher_backend": "offline_fixture",
            "audit_db_counts": audit_store.counts(),
            "limitation": "Do not interpret fixture text or signatures as proof of pedagogy/security efficacy.",
        },
    )
