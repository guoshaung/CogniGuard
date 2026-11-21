from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime, timezone
from typing import Any


GRADE_LEVELS = ("Grade 7", "Grade 8", "Grade 9")
SUBJECTS = ("mathematics",)
KNOWLEDGE_POINTS = (
    "quadratic vertex form",
    "linear equation solving",
    "fraction simplification",
    "proportional relationship",
    "function graph interpretation",
    "arithmetic sequence",
)

ERROR_TYPES = {
    "quadratic vertex form": (
        "confuses horizontal shift direction",
        "reads vertex coordinates in reverse order",
        "forgets axis of symmetry",
    ),
    "linear equation solving": (
        "does not preserve equation balance",
        "sign error when moving terms",
        "divides by coefficient too early",
    ),
    "fraction simplification": (
        "adds denominators directly",
        "misses common factor",
        "reduces only numerator",
    ),
    "proportional relationship": (
        "confuses ratio with difference",
        "sets up inverse proportion",
        "forgets unit consistency",
    ),
    "function graph interpretation": (
        "misreads intercept",
        "confuses slope direction",
        "uses point coordinates inconsistently",
    ),
    "arithmetic sequence": (
        "uses n instead of n minus one",
        "confuses common difference and first term",
        "arithmetic slip in substitution",
    ),
}

QUESTION_BANK = {
    "quadratic vertex form": "For y=(x-2)^2-3, find the vertex and axis of symmetry.",
    "linear equation solving": "Solve 3x+5=20 and explain each step.",
    "fraction simplification": "Simplify 6/8 and explain why the value stays equivalent.",
    "proportional relationship": "If 4 notebooks cost 12 yuan, how much do 7 notebooks cost?",
    "function graph interpretation": "A line passes through (0,2) and (2,6). Find its slope.",
    "arithmetic sequence": "For a1=3 and d=2, find a10.",
}


class ProfileGenerator:
    """Creates anonymous metadata and synthetic learning histories."""

    def __init__(self, seed: int = 20260526) -> None:
        self.rng = random.Random(seed)

    def generate_basic_metadata(self, index: int) -> dict[str, Any]:
        student_id = f"stu_{index + 1:03d}"
        salt = uuid.UUID(int=self.rng.getrandbits(128)).hex
        student_hash = hashlib.sha256(f"{student_id}:{salt}".encode("utf-8")).hexdigest()[
            :16
        ]
        return {
            "student_id": student_id,
            "student_hash": f"hash_{student_hash}",
            "grade_level": self.rng.choice(GRADE_LEVELS),
            "subject": self.rng.choice(SUBJECTS),
            "created_time": datetime.now(timezone.utc).isoformat(),
        }

    def generate_learning_history(
        self, student_hash: str, task_id: str | None = None
    ) -> dict[str, Any]:
        knowledge_point = self.rng.choice(KNOWLEDGE_POINTS)
        total_attempts = self.rng.randint(4, 22)
        correct_count = self.rng.randint(0, total_attempts)
        accuracy = round(correct_count / total_attempts, 3)
        errors = self.rng.sample(
            list(ERROR_TYPES[knowledge_point]),
            k=self.rng.randint(1, min(2, len(ERROR_TYPES[knowledge_point]))),
        )
        recent_wrong_questions = [
            {
                "question_id": f"q_{knowledge_point.replace(' ', '_')}_{idx + 1}",
                "question_text": QUESTION_BANK[knowledge_point],
                "wrong_error_type": self.rng.choice(ERROR_TYPES[knowledge_point]),
            }
            for idx in range(self.rng.randint(1, 3))
        ]

        return {
            "student_hash": student_hash,
            "task_id": task_id or f"task_{uuid.UUID(int=self.rng.getrandbits(128)).hex[:10]}",
            "knowledge_point": knowledge_point,
            "total_attempts": total_attempts,
            "correct_count": correct_count,
            "accuracy": accuracy,
            "average_response_time": round(self.rng.uniform(18.0, 135.0), 2),
            "common_error_types": errors,
            "recent_wrong_questions": recent_wrong_questions,
        }

    def current_error_for(self, history: dict[str, Any]) -> str:
        errors = history.get("common_error_types") or ["not_enough_evidence"]
        return str(errors[0])

    def question_for(self, knowledge_point: str) -> str:
        return QUESTION_BANK.get(knowledge_point, "Solve the given math problem.")
