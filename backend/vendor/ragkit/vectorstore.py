"""In-memory vector store with cosine similarity search."""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass
class Document:
    id: str
    text: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class SearchResult:
    document: Document
    score: float


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vectors must have the same dimensions")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """Minimal vector store: add, delete, and top-k cosine search."""

    def __init__(self):
        self._vectors: Dict[str, List[float]] = {}
        self._documents: Dict[str, Document] = {}

    def __len__(self) -> int:
        return len(self._documents)

    def add(self, document: Document, vector: Sequence[float]) -> None:
        if not vector:
            raise ValueError("vector must not be empty")
        self._documents[document.id] = document
        self._vectors[document.id] = list(vector)

    def delete(self, document_id: str) -> bool:
        existed = document_id in self._documents
        self._documents.pop(document_id, None)
        self._vectors.pop(document_id, None)
        return existed

    def get(self, document_id: str) -> Optional[Document]:
        return self._documents.get(document_id)

    def search(self, query_vector: Sequence[float], k: int = 4,
               metadata_filter: Optional[Dict] = None) -> List[SearchResult]:
        if k <= 0:
            raise ValueError("k must be positive")
        scored = []
        for doc_id, vector in self._vectors.items():
            document = self._documents[doc_id]
            if metadata_filter and not all(
                document.metadata.get(key) == value for key, value in metadata_filter.items()
            ):
                continue
            scored.append(SearchResult(document, cosine_similarity(query_vector, vector)))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]
