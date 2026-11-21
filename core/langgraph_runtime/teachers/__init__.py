"""Compatibility package; implementations live in cogniguard.workflows.teachers."""
from importlib import import_module as _import_module


def __getattr__(name):
    return getattr(_import_module("cogniguard.workflows.teachers"), name)

__all__ = ["PromptLibrary", "TeamCatalog", "TeacherDAGGenerator",
           "OfflineTeacherBackend", "JsonTeacherBackend", "SQLiteTeacherAuditStore", "SkillLibrary"]
