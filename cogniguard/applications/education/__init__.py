"""Protected classroom, conversation and case-study application entry points."""

__all__ = ["run_case_study", "run_classroom_turn", "run_conversation"]


def __getattr__(name):
    if name == "run_case_study":
        from .case_study import run_case_study

        return run_case_study
    if name == "run_classroom_turn":
        from .classroom import run_classroom_turn

        return run_classroom_turn
    if name == "run_conversation":
        from .conversation import run_conversation

        return run_conversation
    raise AttributeError(name)
