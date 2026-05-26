from __future__ import annotations

from src.c2rag.exposure_budget import ExposureBudget
from src.c2rag.resource_index import ResourceIndex
from src.common.schemas import RetrievedResource, Task, TeacherResource
from src.common.text_utils import difficulty_match


class CopyrightAwareRetriever:
    def __init__(
        self,
        resources: list[TeacherResource],
        exposure_budget: ExposureBudget,
        config: dict,
    ) -> None:
        self.resources = resources
        self.index = ResourceIndex(resources)
        self.budget = exposure_budget
        c2 = config.get("c2rag", {})
        self.top_k = int(c2.get("top_k_resources", 3))
        self.weights = c2.get("score_weights", {})

    def retrieve(self, ag2_request: dict, task: Task, context_card: str) -> list[RetrievedResource]:
        query = " ".join(
            str(ag2_request.get(k, ""))
            for k in ["question", "knowledge", "difficulty", "teaching_goal", "resource_type"]
        )
        scored: list[RetrievedResource] = []
        for resource in self.resources:
            rel = self.index.similarity(query, resource)
            fit = 1.0 if resource.knowledge == ag2_request.get("knowledge") else 0.0
            pedfit = difficulty_match(str(ag2_request.get("difficulty", task.difficulty)), resource.difficulty)
            exposure = self.budget.get(resource.chunk_id)
            focus = self.budget.focus(resource.chunk_id)
            score = (
                float(self.weights.get("rel", 0.45)) * rel
                + float(self.weights.get("fit", 0.20)) * fit
                + float(self.weights.get("pedfit", 0.10)) * pedfit
                - float(self.weights.get("copyright", 0.15)) * resource.copyright_level
                - float(self.weights.get("exposure", 0.20)) * exposure
                - float(self.weights.get("focus", 0.10)) * focus
            )
            scored.append(
                RetrievedResource(
                    resource=resource,
                    score=score,
                    components={
                        "rel": rel,
                        "fit": fit,
                        "pedfit": pedfit,
                        "copyright": resource.copyright_level,
                        "exposure": exposure,
                        "focus": focus,
                    },
                )
            )
        return sorted(scored, key=lambda x: x.score, reverse=True)[: self.top_k]
