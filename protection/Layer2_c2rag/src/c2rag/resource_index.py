from __future__ import annotations

from protection.fopd_c2rag_mvp.src.common.schemas import TeacherResource
from protection.fopd_c2rag_mvp.src.common.text_utils import SimpleTfidfVectorizer, cosine_sparse


class ResourceIndex:
    def __init__(self, resources: list[TeacherResource]) -> None:
        self.resources = resources
        self.vectorizer = SimpleTfidfVectorizer()
        self.texts = [f"{r.content} {r.knowledge} {r.difficulty}" for r in resources]
        self.vectors = self.vectorizer.fit_transform(self.texts)

    def similarity(self, query: str, resource: TeacherResource) -> float:
        try:
            idx = self.resources.index(resource)
        except ValueError:
            return 0.0
        q_vec = self.vectorizer.transform_one(query)
        return cosine_sparse(q_vec, self.vectors[idx])
