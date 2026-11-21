"""Independent privacy and copyright ledgers for CG V3 experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _rounded(value: float) -> float:
    return round(max(0.0, float(value)), 8)


@dataclass(slots=True)
class BudgetProjection:
    domain: str
    cost: float
    before: float
    after: float
    maximum: float
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "cost": self.cost,
            "before": self.before,
            "after": self.after,
            "maximum": self.maximum,
            "scope": self.scope,
        }


class DualBudgetLedger:
    """A non-destructive projection API plus post-execution consumption."""

    def __init__(self, privacy_max: float, copyright_max: float) -> None:
        self.privacy_max = float(privacy_max)
        self.copyright_max = float(copyright_max)
        self._privacy_by_student_session: dict[tuple[str, str], float] = {}
        self._privacy_by_round: dict[tuple[str, str, str], float] = {}
        self._copyright_by_resource: dict[tuple[str, str, str], float] = {}
        self._copyright_by_session: dict[str, float] = {}

    def project_privacy(self, student_id: str, session_id: str, round_id: str, cost: float) -> BudgetProjection:
        key = (student_id, session_id)
        before = self._privacy_by_student_session.get(key, 0.0)
        return BudgetProjection(
            domain="privacy",
            cost=_rounded(cost),
            before=_rounded(before),
            after=_rounded(before + cost),
            maximum=self.privacy_max,
            scope=f"student={student_id};session={session_id};round={round_id}",
        )

    def project_copyright(
        self,
        resource_id: str,
        chunk_ids: list[str],
        session_id: str,
        cost: float,
    ) -> BudgetProjection:
        before = self._copyright_by_session.get(session_id, 0.0)
        chunks = ",".join(sorted(chunk_ids)) or "<resource>"
        return BudgetProjection(
            domain="copyright",
            cost=_rounded(cost),
            before=_rounded(before),
            after=_rounded(before + cost),
            maximum=self.copyright_max,
            scope=f"resource={resource_id};chunks={chunks};session={session_id}",
        )

    def commit_privacy(self, student_id: str, session_id: str, round_id: str, cost: float) -> BudgetProjection:
        projection = self.project_privacy(student_id, session_id, round_id, cost)
        session_key = (student_id, session_id)
        round_key = (student_id, session_id, round_id)
        self._privacy_by_student_session[session_key] = projection.after
        self._privacy_by_round[round_key] = _rounded(self._privacy_by_round.get(round_key, 0.0) + cost)
        return projection

    def commit_copyright(
        self,
        resource_id: str,
        chunk_ids: list[str],
        session_id: str,
        cost: float,
    ) -> BudgetProjection:
        projection = self.project_copyright(resource_id, chunk_ids, session_id, cost)
        self._copyright_by_session[session_id] = projection.after
        for chunk_id in (chunk_ids or ["<resource>"]):
            key = (resource_id, chunk_id, session_id)
            self._copyright_by_resource[key] = _rounded(self._copyright_by_resource.get(key, 0.0) + cost / max(len(chunk_ids), 1))
        return projection

    def snapshot(self, student_id: str, session_id: str, round_id: str, resource_id: str = "", chunk_ids: list[str] | None = None) -> dict[str, Any]:
        privacy = self.project_privacy(student_id, session_id, round_id, 0.0)
        copyright_projection = self.project_copyright(resource_id, chunk_ids or [], session_id, 0.0)
        return {
            "privacy": {
                "E_priv": privacy.before,
                "B_priv_remaining": _rounded(self.privacy_max - privacy.before),
                "maximum": self.privacy_max,
                "round_used": _rounded(self._privacy_by_round.get((student_id, session_id, round_id), 0.0)),
            },
            "copyright": {
                "E_copy": copyright_projection.before,
                "B_copy_remaining": _rounded(self.copyright_max - copyright_projection.before),
                "maximum": self.copyright_max,
                "resource_used": _rounded(sum(
                    amount for (resource, _chunk, current_session), amount in self._copyright_by_resource.items()
                    if resource == resource_id and current_session == session_id
                )),
            },
        }

    def reset_session(self, session_id: str) -> None:
        self._privacy_by_student_session = {
            key: value for key, value in self._privacy_by_student_session.items() if key[1] != session_id
        }
        self._privacy_by_round = {
            key: value for key, value in self._privacy_by_round.items() if key[1] != session_id
        }
        self._copyright_by_session.pop(session_id, None)
        self._copyright_by_resource = {
            key: value for key, value in self._copyright_by_resource.items() if key[2] != session_id
        }

    def reset_student(self, student_id: str) -> None:
        self._privacy_by_student_session = {
            key: value for key, value in self._privacy_by_student_session.items() if key[0] != student_id
        }
        self._privacy_by_round = {
            key: value for key, value in self._privacy_by_round.items() if key[0] != student_id
        }

    def reset_resource(self, resource_id: str) -> None:
        affected_sessions = {
            session_id for (resource, _chunk, session_id), _amount in self._copyright_by_resource.items()
            if resource == resource_id
        }
        self._copyright_by_resource = {
            key: value for key, value in self._copyright_by_resource.items() if key[0] != resource_id
        }
        for session_id in affected_sessions:
            self._copyright_by_session[session_id] = _rounded(sum(
                amount for (_resource, _chunk, current_session), amount in self._copyright_by_resource.items()
                if current_session == session_id
            ))

    def export_snapshot(self) -> dict[str, Any]:
        return {
            "privacy_max": self.privacy_max,
            "copyright_max": self.copyright_max,
            "privacy_by_student_session": {"|".join(key): value for key, value in self._privacy_by_student_session.items()},
            "privacy_by_round": {"|".join(key): value for key, value in self._privacy_by_round.items()},
            "copyright_by_resource": {"|".join(key): value for key, value in self._copyright_by_resource.items()},
            "copyright_by_session": dict(self._copyright_by_session),
        }
