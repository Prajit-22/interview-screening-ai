"""Embedding interfaces and dependency-free implementations.

An embedder maps text to a dense vector. ``HashingEmbedder`` and
``TfIdfEmbedder`` run anywhere with zero downloads; bring your own embedder
(sentence-transformers, OpenAI, Ollama, ...) by implementing ``embed``.
"""

import hashlib
import math
import unicodedata
from typing import List, Protocol, Sequence


def _is_token_char(char: str) -> bool:
    # Letters and digits in any script, combining marks (accents, Indic vowel
    # signs), and apostrophes stay inside a token. Everything else splits.
    return char == "'" or char.isalnum() or unicodedata.category(char).startswith("M")


def tokenize(text: str) -> List[str]:
    """Lowercase, NFC-normalize, and split into word tokens in any script.

    Text in scripts without spaces between words (Chinese, Japanese) comes
    back as one token per unbroken run; bring a segmenter if you need more.
    """
    tokens: List[str] = []
    current: List[str] = []
    for char in unicodedata.normalize("NFC", text).lower():
        if _is_token_char(char):
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


class Embedder(Protocol):
    """Anything that turns text into a fixed-length float vector."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> List[float]: ...


class HashingEmbedder:
    """Feature-hashing embedder: deterministic, fast, dependency-free.

    Each token is hashed into ``dimensions`` buckets; the resulting counts
    are L2-normalized. Retrieval quality is below a neural embedder but the
    pipeline shape is identical, which makes it ideal for tests, demos, and
    offline development.
    """

    def __init__(self, dimensions: int = 256):
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> List[float]:
        vector = [0.0] * self._dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "little") % self._dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class TfIdfEmbedder:
    """Corpus-aware TF-IDF embedder fitted on a document set.

    Vocabulary is fixed at ``fit`` time; ``embed`` is stable afterwards, so
    vectors can be stored and compared across calls.
    """

    def __init__(self, max_features: int = 512):
        if max_features <= 0:
            raise ValueError("max_features must be positive")
        self.max_features = max_features
        self.vocabulary: dict = {}
        self.idf: List[float] = []

    @property
    def dimensions(self) -> int:
        return len(self.vocabulary)

    def fit(self, documents: Sequence[str]) -> "TfIdfEmbedder":
        document_freq: dict = {}
        for doc in documents:
            for token in set(tokenize(doc)):
                document_freq[token] = document_freq.get(token, 0) + 1
        most_common = sorted(document_freq.items(), key=lambda kv: (-kv[1], kv[0]))
        self.vocabulary = {token: i for i, (token, _) in enumerate(most_common[: self.max_features])}
        n_docs = max(1, len(documents))
        self.idf = [0.0] * len(self.vocabulary)
        for token, i in self.vocabulary.items():
            self.idf[i] = math.log((1 + n_docs) / (1 + document_freq[token])) + 1.0
        return self

    def embed(self, text: str) -> List[float]:
        if not self.vocabulary:
            raise RuntimeError("TfIdfEmbedder must be fit before embed")
        counts: dict = {}
        tokens = tokenize(text)
        for token in tokens:
            if token in self.vocabulary:
                counts[token] = counts.get(token, 0) + 1
        vector = [0.0] * len(self.vocabulary)
        for token, count in counts.items():
            i = self.vocabulary[token]
            vector[i] = (count / max(1, len(tokens))) * self.idf[i]
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector
