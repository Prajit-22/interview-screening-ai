"""Retrievers: BM25 lexical search, vector search, and hybrid fusion."""

import math
from collections import Counter
from typing import Dict, List, Optional, Sequence

from .embeddings import Embedder, tokenize
from .vectorstore import Document, InMemoryVectorStore, SearchResult


class BM25Retriever:
    """Okapi BM25 over an in-memory corpus. No embeddings required."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: Dict[str, Document] = {}
        self._term_freqs: Dict[str, Counter] = {}
        self._doc_lengths: Dict[str, int] = {}
        self._doc_freq: Counter = Counter()
        self._avg_length = 0.0

    def __len__(self) -> int:
        return len(self._documents)

    def add(self, document: Document) -> None:
        if document.id in self._documents:
            self.delete(document.id)
        tokens = tokenize(document.text)
        self._documents[document.id] = document
        self._term_freqs[document.id] = Counter(tokens)
        self._doc_lengths[document.id] = len(tokens)
        for token in set(tokens):
            self._doc_freq[token] += 1
        self._recompute_avg()

    def delete(self, document_id: str) -> bool:
        if document_id not in self._documents:
            return False
        for token in self._term_freqs[document_id]:
            self._doc_freq[token] -= 1
            if self._doc_freq[token] <= 0:
                del self._doc_freq[token]
        del self._documents[document_id]
        del self._term_freqs[document_id]
        del self._doc_lengths[document_id]
        self._recompute_avg()
        return True

    def search(self, query: str, k: int = 4,
               metadata_filter: Optional[Dict] = None) -> List[SearchResult]:
        if k <= 0:
            raise ValueError("k must be positive")
        scored = []
        for doc_id, document in self._documents.items():
            if metadata_filter and not all(
                document.metadata.get(key) == value for key, value in metadata_filter.items()
            ):
                continue
            score = self._score(query, doc_id)
            if score > 0:
                scored.append(SearchResult(document, score))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]

    def _score(self, query: str, doc_id: str) -> float:
        n_docs = len(self._documents)
        score = 0.0
        term_freqs = self._term_freqs[doc_id]
        doc_len = self._doc_lengths[doc_id]
        for token in set(tokenize(query)):
            tf = term_freqs.get(token, 0)
            if tf == 0:
                continue
            df = self._doc_freq.get(token, 0)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            norm = 1 - self.b + self.b * doc_len / max(self._avg_length, 1e-9)
            score += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return score

    def _recompute_avg(self) -> None:
        lengths = self._doc_lengths.values()
        self._avg_length = sum(lengths) / len(lengths) if lengths else 0.0


class VectorRetriever:
    """Dense retrieval over an InMemoryVectorStore using any Embedder."""

    def __init__(self, embedder: Embedder, store: Optional[InMemoryVectorStore] = None):
        self.embedder = embedder
        self.store = store if store is not None else InMemoryVectorStore()

    def __len__(self) -> int:
        return len(self.store)

    def add(self, document: Document) -> None:
        self.store.add(document, self.embedder.embed(document.text))

    def delete(self, document_id: str) -> bool:
        return self.store.delete(document_id)

    def search(self, query: str, k: int = 4,
               metadata_filter: Optional[Dict] = None) -> List[SearchResult]:
        return self.store.search(self.embedder.embed(query), k=k, metadata_filter=metadata_filter)


class HybridRetriever:
    """Reciprocal-rank fusion of a lexical and a dense retriever."""

    def __init__(self, lexical: BM25Retriever, dense: VectorRetriever, rrf_k: int = 60):
        if rrf_k < 0:
            raise ValueError("rrf_k must be nonnegative")
        self.lexical = lexical
        self.dense = dense
        self.rrf_k = rrf_k

    def add(self, document: Document) -> None:
        self.lexical.add(document)
        self.dense.add(document)

    def delete(self, document_id: str) -> bool:
        return self.lexical.delete(document_id) | self.dense.delete(document_id)

    def search(self, query: str, k: int = 4,
               metadata_filter: Optional[Dict] = None) -> List[SearchResult]:
        if k <= 0:
            raise ValueError("k must be positive")
        fused: Dict[str, float] = {}
        documents: Dict[str, Document] = {}
        for retriever in (self.lexical, self.dense):
            for rank, result in enumerate(retriever.search(query, k=k * 2, metadata_filter=metadata_filter)):
                doc_id = result.document.id
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)
                documents[doc_id] = result.document
        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [SearchResult(documents[doc_id], score) for doc_id, score in ranked]
